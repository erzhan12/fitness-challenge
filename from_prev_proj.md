
### Step 2.2: Initial Server Connection

1. **Connect to your server:**

   **On Mac/Linux:**
   ```bash
   # Replace YOUR_IP with your actual droplet IP
   ssh -i ~/.ssh/do_habit_bot root@YOUR_IP

   # Example:
   # ssh -i ~/.ssh/do_habit_bot root@123.456.789.012

   # If prompted "Are you sure you want to continue connecting?":
   # Type: yes
   # Press ENTER
   ```

   **On Windows (PowerShell):**
   ```powershell
   ssh -i $env:USERPROFILE\.ssh\do_habit_bot root@YOUR_IP
   ```

2. **First-time connection:**
   - You should see a welcome message from Ubuntu
   - Your prompt will change to: `root@habit-reward-bot:~#`
   - ✅ You're now connected to your VPS!

3. **Update system packages:**
   ```bash
   apt update && apt upgrade -y
   ```
   - This will take 2-5 minutes
   - You'll see a lot of packages being updated
   - If prompted about kernel upgrades or services, choose default options

4. **Reboot if kernel was updated:**
   ```bash
   # Check if reboot is required:
   ls -l /var/run/reboot-required

   # If file exists, reboot:
   reboot

   # Wait 30 seconds, then reconnect:
   ssh -i ~/.ssh/do_habit_bot root@YOUR_IP
   ```

✅ **Checkpoint:** You should be connected to a fully updated Ubuntu server

---

## Phase 3: Server Configuration (20 minutes)

### Step 3.1: Install Docker

1. **Remove old Docker versions (if any):**
   ```bash
   apt remove docker docker-engine docker.io containerd runc -y
   ```

2. **Install prerequisites:**
   ```bash
   apt install -y ca-certificates curl gnupg lsb-release
   ```

3. **Add Docker's official GPG key:**
   ```bash
   mkdir -p /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   ```

4. **Add Docker repository:**
   ```bash
   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
   ```

5. **Install Docker:**
   ```bash
   apt update
   apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```
   - This takes 2-3 minutes

6. **Verify Docker installation:**
   ```bash
   docker --version
   # Should show: Docker version 24.x.x or higher

   systemctl status docker
   # Should show: "active (running)" in green
   # Press 'q' to exit
   ```

✅ **Checkpoint:** Docker is installed and running

### Step 3.2: Install Docker Compose

1. **Download Docker Compose:**
   ```bash
   DOCKER_COMPOSE_VERSION="2.24.0"
   curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   ```

2. **Make it executable:**
   ```bash
   chmod +x /usr/local/bin/docker-compose
   ```

3. **Verify installation:**
   ```bash
   docker-compose --version
   # Should show: Docker Compose version v2.24.0 or higher
   ```

✅ **Checkpoint:** Docker Compose is installed

### Step 3.3: Create Deployment User

1. **Create a dedicated user for deployment:**
   ```bash
   adduser deploy
   ```
   - Enter password: (create a strong password)
   - Re-enter password: (same password)
   - Full Name: Press ENTER (skip)
   - Room Number: Press ENTER (skip)
   - Work Phone: Press ENTER (skip)
   - Home Phone: Press ENTER (skip)
   - Other: Press ENTER (skip)
   - Is the information correct? Type: Y

2. **Add user to Docker group:**
   ```bash
   usermod -aG docker deploy
   ```

3. **Grant sudo privileges:**
   ```bash
   usermod -aG sudo deploy
   ```

4. **Set up SSH key for deploy user:**
   ```bash
   # Create SSH directory for deploy user
   mkdir -p /home/deploy/.ssh

   # Copy root's authorized_keys to deploy user
   cp ~/.ssh/authorized_keys /home/deploy/.ssh/

   # Set correct permissions
   chown -R deploy:deploy /home/deploy/.ssh
   chmod 700 /home/deploy/.ssh
   chmod 600 /home/deploy/.ssh/authorized_keys
   ```

5. **Test deploy user login:**
   ```bash
   # Open a NEW terminal window (keep current one open)
   # Try to connect as deploy user:
   ssh -i ~/.ssh/do_habit_bot deploy@YOUR_IP

   # If successful, you'll see deploy@habit-reward-bot:~$
   # Type 'exit' to close this test connection
   ```

✅ **Checkpoint:** Deploy user created and can connect via SSH

### Step 3.4: Configure Firewall

1. **Back in your root SSH session, configure UFW:**
   ```bash
   # Allow SSH (IMPORTANT - don't lock yourself out!)
   ufw allow 22/tcp

   # Allow HTTP
   ufw allow 80/tcp

   # Allow HTTPS
   ufw allow 443/tcp

   # Enable firewall (will ask for confirmation)
   ufw enable
   # Type: y
   # Press ENTER
   ```

2. **Verify firewall rules:**
   ```bash
   ufw status
   ```
   - Should show rules for 22, 80, and 443

✅ **Checkpoint:** Firewall is configured and active

### Step 3.5: Create Deployment Directory

1. **Switch to deploy user:**
   ```bash
   su - deploy
   # Enter the deploy user password you created
   ```

2. **Create deployment directory:**
   ```bash
   mkdir -p /home/deploy/habit_reward_bot
   cd /home/deploy/habit_reward_bot
   pwd
   # Should show: /home/deploy/habit_reward_bot
   ```

3. **Generate SSH key for GitHub Actions:**
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions -N ""
   ```

4. **Add public key to authorized_keys:**
   ```bash
   cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
   ```

5. **Display private key (you'll need this for GitHub):**
   ```bash
   cat ~/.ssh/github_actions
   ```
   - **COPY THE ENTIRE OUTPUT** (including "-----BEGIN OPENSSH PRIVATE KEY-----" and "-----END OPENSSH PRIVATE KEY-----")
   - Save it in a text file temporarily - you'll add this to GitHub Secrets
