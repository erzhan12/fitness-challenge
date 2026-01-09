# Fitness Challenge Bot

A Telegram bot built with Python, FastAPI, and OpenAI to help users track fitness challenges.

## Deployment: DigitalOcean Droplet + Telegram Webhook

This application is deployed on a DigitalOcean Droplet using Docker (GHCR) and Postgres for production.

### 1. Environment Variables

**Local Development:**
Create a `.env` file in the root directory (do NOT commit this):
```ini
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_SECRET_TOKEN=your_secret_token
LLM_API_KEY=your_openai_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
ADMIN_API_KEY=your_admin_key
TARGET_CHAT_ID=123456789
TZ=Asia/Almaty
```

**Production (GitHub Secrets):**
All secrets are managed via **GitHub Repository Secrets**. No `.env` file is needed on the server.

### 2. Local Docker Testing

Build and run the production image locally:
```bash
# Build
docker build -f deployment/docker/Dockerfile -t fitness-challenge .

# Run (passing local .env)
docker run --env-file .env -p 8001:8001 fitness-challenge
```

### 3. Server Provisioning (DigitalOcean)

**Step 1: Initial Setup & Update**
Connect as root and update:
```bash
ssh root@<YOUR_IP>
apt update && apt upgrade -y
# Reboot if required
[ -f /var/run/reboot-required ] && reboot
```

**Step 2: Verify Deployment User**
Since you already have a `deploy` user, verify it has the necessary permissions:
```bash
# Check if user exists
id deploy

# Verify user is in docker group (required)
groups deploy | grep docker || echo "⚠️  User not in docker group"

# If not in docker group, add it:
sudo usermod -aG docker deploy

# Verify user is in sudo group (optional, but useful)
groups deploy | grep sudo || echo "⚠️  User not in sudo group"

# If not in sudo group and you need it:
sudo usermod -aG sudo deploy
```

**Note:** You can use the same `deploy` user for both apps. Docker containers provide isolation, so user-level separation is not necessary.

**Step 3: Generate SSH Key for GitHub Actions (if not already done)**
If you already have a GitHub Actions SSH key set up, you can reuse it. Otherwise, run this **as the `deploy` user**:
```bash
# Check if key already exists
ls -la ~/.ssh/github_actions* || echo "Key not found, generating new one..."

# Generate key (only if it doesn't exist)
if [ ! -f ~/.ssh/github_actions ]; then
    ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions -N ""
    cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
fi

# View Private Key (Copy this for DO_SSH_PRIVATE_KEY in GitHub Secrets)
cat ~/.ssh/github_actions
```

**If you already have a GitHub Actions key:** You can reuse the same `DO_SSH_PRIVATE_KEY` secret for both repositories.

**Step 4: Configure Firewall (UFW)**
Back as root (or with sudo):
```bash
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
# Note: Port 8001 doesn't need to be exposed - Caddy will proxy to it internally
ufw enable
```

**Step 5: Install Docker**
```bash
# Remove old versions
apt remove docker docker-engine docker.io containerd runc -y

# Install deps
apt install -y ca-certificates curl gnupg lsb-release

# Add key & repo
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
```

**Step 6: Install & Configure Caddy**

**⚠️ Important:** If you have another app on this server, **DO NOT replace** the Caddyfile. Instead, **append** your configuration.

```bash
# Install (skip if already installed)
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Backup existing Caddyfile (if it exists)
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup.$(date +%Y%m%d) 2>/dev/null || true

# Edit Caddyfile
sudo nano /etc/caddy/Caddyfile
```

**If Caddy is NEW (no other apps):**
Replace contents with:
```
fitnesschallenge.habitreward.org {
    reverse_proxy localhost:8001
}
```

**If Caddy EXISTS (other apps running):**
**APPEND** this to the existing file (don't replace!):
```
fitnesschallenge.habitreward.org {
    reverse_proxy localhost:8001
}
```

**Example of combined Caddyfile:**
```
# Existing app (keep this!)
habitreward.org {
    reverse_proxy localhost:8000
}

# Your new fitness challenge app (add this)
fitnesschallenge.habitreward.org {
    reverse_proxy localhost:8001
}
```

```bash
# Validate configuration
sudo caddy validate --config /etc/caddy/Caddyfile

# Apply configuration
sudo systemctl reload caddy

# Verify Caddy is running
sudo systemctl status caddy
```

**Note:** Port 8001 is only accessible from localhost (via Caddy). It doesn't need to be exposed in the firewall.

**⚠️ Conflict Prevention:** Before deploying, check:
- Port availability: `sudo lsof -i :8001`
- Container name: `docker ps -a | grep fitness-challenge`
- See `CONFLICT_PREVENTION.md` for detailed conflict avoidance guide

### 4. DNS Setup (Namecheap)

Add an **A Record**:
*   Host: `fitnesschallenge`
*   Value: `<YOUR_DROPLET_IP>`

### 5. Telegram Webhook Setup

Run the registration script locally (after setting up `.env` with the new bot token):
```bash
python scripts/register_webhook.py
```
Or manually:
```bash
curl -F "url=https://fitnesschallenge.habitreward.org/telegram/webhook" \
     -F "secret_token=<YOUR_SECRET>" \
     https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook
```

### 6. GitHub Actions CI/CD

The workflow `.github/workflows/deploy.yml` runs on push to `main`.

**Required GitHub Secrets:**
*   `SERVER_HOST`: Droplet IP address (e.g., `206.189.40.240`).
*   `SSH_USER`: SSH username (e.g., `deploy`).
*   `SSH_PRIVATE_KEY`: The content of `~/.ssh/github_actions` (private key) you generated in Step 3.
*   `DEPLOY_PATH`: Deployment path on the server (e.g., `/home/deploy/fitness-challenge`).
*   `GITHUB_TOKEN`: GitHub Personal Access Token for GHCR authentication (optional, uses built-in token if not set).
*   `POSTGRES_DB`
*   `POSTGRES_USER`
*   `POSTGRES_PASSWORD`
*   `TELEGRAM_BOT_TOKEN`
*   `TELEGRAM_SECRET_TOKEN`
*   `LLM_API_KEY`
*   `LLM_BASE_URL`
*   `LLM_MODEL`
*   `SUPABASE_URL`
*   `SUPABASE_KEY`
*   `ADMIN_API_KEY`
*   `TARGET_CHAT_ID` (Optional)
