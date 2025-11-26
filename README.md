# Fitness Challenge Bot

A Telegram bot built with Python, FastAPI, and OpenAI to help users track fitness challenges.

## Deployment: DigitalOcean Droplet + Telegram Webhook

This application is deployed on a DigitalOcean Droplet using Docker (GHCR) and Caddy as a reverse proxy.

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
docker build --target production -t fitness-challenge .

# Run (passing local .env)
docker run --env-file .env -p 8000:8000 fitness-challenge
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

**Step 2: Create Deployment User**
Create a secure user `deploy` for GitHub Actions to use:
```bash
# Create user
adduser deploy
# (Follow prompts, set a strong password)

# Add to docker and sudo groups
usermod -aG docker deploy
usermod -aG sudo deploy

# Setup SSH directory
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

**Step 3: Generate SSH Key for GitHub Actions**
Run this **as the `deploy` user** (`su - deploy`):
```bash
# Generate key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions -N ""

# Authorize it
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# View Private Key (Copy this for DO_SSH_PRIVATE_KEY in GitHub Secrets)
cat ~/.ssh/github_actions
```

**Step 4: Configure Firewall (UFW)**
Back as root (or with sudo):
```bash
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
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
```bash
# Install
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy

# Configure (/etc/caddy/Caddyfile)
# Replace contents with:
# fitnesschallenge.habitreward.org {
#     reverse_proxy localhost:8000
# }

# Apply
systemctl reload caddy
```

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
*   `DO_SSH_HOST`: Droplet IP address.
*   `DO_SSH_USER`: `deploy`
*   `DO_SSH_PRIVATE_KEY`: The content of `~/.ssh/github_actions` (private key) you generated in Step 3.
*   `TELEGRAM_BOT_TOKEN`
*   `TELEGRAM_SECRET_TOKEN`
*   `LLM_API_KEY`
*   `LLM_BASE_URL`
*   `LLM_MODEL`
*   `SUPABASE_URL`
*   `SUPABASE_KEY`
*   `ADMIN_API_KEY`
*   `TARGET_CHAT_ID` (Optional)
