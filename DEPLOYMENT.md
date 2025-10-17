# Deployment Guide

Complete guide for deploying Z-Words Collector on your server using Docker Compose with automated GitHub Actions SSH deployment.

## Deployment Methods

This guide covers **two deployment approaches**:

1. **GitHub Actions SSH Deployment (Recommended)** - Automated deployment via GitHub Actions using SSH
2. **Manual Server Setup** - Traditional server deployment with git clone

---

## Method 1: GitHub Actions SSH Deployment (Recommended)

### Prerequisites

**GitHub Repository:**
- Repository with this project
- GitHub Actions enabled

**Server Requirements:**
- **OS:** Ubuntu 20.04+ / Debian 11+ (or any Linux with Docker support)
- **RAM:** Minimum 1GB, recommended 2GB+
- **Disk:** At least 10GB free space (more as data grows)
- **CPU:** 1 core minimum, 2+ cores recommended
- **Network:** Stable internet connection
- **SSH Access:** SSH key-based authentication configured

**Software Requirements (on server):**
- Docker 20.10+
- Docker Compose 2.0+
- SSH server running

### Setup GitHub Actions Deployment

#### 1. Generate SSH Key for Deployment

On your local machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy
# Don't set a passphrase (press Enter twice)
```

Copy public key to server:

```bash
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub user@your-server
```

Test connection:

```bash
ssh -i ~/.ssh/github_actions_deploy user@your-server
```

#### 2. Configure GitHub Secrets and Variables

**Secrets (Settings → Secrets and variables → Actions → New repository secret):**

- `SSH_PRIVATE_KEY` - Content of `~/.ssh/github_actions_deploy` (entire file including `-----BEGIN OPENSSH PRIVATE KEY-----`)
- `API_ID` - Your Telegram API ID
- `API_HASH` - Your Telegram API hash
- `PHONE_NUMBER` - Your Telegram phone number (e.g., `+79261234567`)

**Variables (Settings → Secrets and variables → Actions → Variables tab):**

- `SSH_HOST` - Your server IP or hostname (e.g., `192.168.1.100`)
- `SSH_USER` - SSH username (e.g., `ubuntu`)
- `DEPLOY_PATH` - Deployment directory on server (e.g., `/opt/z-words-collector`)
- `TARGET_CHANNELS` - Channels to collect, comma-separated (e.g., `channel1,channel2`)
- `INITIAL_FETCH_LIMIT` - Messages to fetch on first run (e.g., `5000`)
- `BACKFILL_LIMIT` - Messages to backfill per run (e.g., `1000`)

#### 3. Prepare Server

Connect to your server and install Docker:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Log out and back in for group changes to take effect
exit
```

#### 4. Create Telegram Session

**Option A: Create locally and transfer**

On your local machine:

```bash
# Clone repository
git clone https://github.com/yourusername/z-words-collector.git
cd z-words-collector

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run parser once to create session
python parser.py
# Enter Telegram code when prompted
```

Transfer session to server:

```bash
scp session/z_worlds_collector_session.session user@your-server:/opt/z-words-collector/session/
```

**Option B: Create directly on server**

```bash
# SSH to server
ssh user@your-server

# Create deployment directory
mkdir -p /opt/z-words-collector/session
cd /opt/z-words-collector

# Install Python
sudo apt install python3 python3-pip python3-venv -y

# Create temporary venv
python3 -m venv venv
source venv/bin/activate

# Install Telethon
pip install telethon python-dotenv

# Create session with Python script
cat > create_session.py << 'EOF'
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = 'session/z_worlds_collector_session'

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def main():
    await client.start(phone=PHONE_NUMBER)
    print("Session created successfully!")
    await client.disconnect()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
EOF

# Create .env temporarily
cat > .env << EOF
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+79261234567
EOF

# Run session creation
python create_session.py

# Clean up
deactivate
rm -rf venv create_session.py .env
```

#### 5. Trigger Deployment

**Automatic Deployment:**
- Push to `main` branch triggers automatic deployment

**Manual Deployment:**
- Go to Actions tab in GitHub
- Select "Deploy to Server" workflow
- Click "Run workflow"

#### 6. Monitor Deployment

Check GitHub Actions logs:
- Go to repository → Actions tab
- Click on latest workflow run
- View logs for each step

Check server status:

```bash
ssh user@your-server
cd /opt/z-words-collector
docker compose ps
docker compose logs -f
```

---

## Method 2: Manual Server Setup

### Prerequisites

- **OS:** Ubuntu 20.04+ / Debian 11+ (or any Linux with Docker support)
- **RAM:** Minimum 1GB, recommended 2GB+
- **Disk:** At least 10GB free space (more as data grows)
- **CPU:** 1 core minimum, 2+ cores recommended
- **Network:** Stable internet connection

**Software Requirements:**
- Docker 20.10+
- Docker Compose 2.0+
- Git

---

## Initial Server Setup

### 1. Update system

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
```

### 3. Install Docker Compose

```bash
sudo apt install docker-compose-plugin -y

# Verify installation
docker compose version
```

### 4. Install Git

```bash
sudo apt install git -y
```

---

## Deployment Steps

### 1. Clone Repository

```bash
# Clone to /opt or your preferred location
cd /opt
sudo git clone https://github.com/de43gy/z-words-collector.git
cd z-words-collector

# Make current user owner (replace $USER with your username)
sudo chown -R $USER:$USER /opt/z-words-collector
```

### 2. Create Environment File

```bash
# Copy example file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Configuration:**

```env
# Telegram API credentials (from https://my.telegram.org)
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+79261234567

# Channels to collect (comma-separated, without @)
TARGET_CHANNELS=channel1,channel2,channel3

# Messages per run
INITIAL_FETCH_LIMIT=1000
```

**Save and exit:** Ctrl+O, Enter, Ctrl+X

### 3. Create Telegram Session

**Option A: Create session locally, then transfer**

On your local machine:
```bash
python parser.py
# Enter Telegram code when prompted
```

Transfer session to server:
```bash
# From local machine
scp session/z_worlds_collector_session.session user@your-server:/opt/z-words-collector/session/
```

**Option B: Create session directly on server**

```bash
# Install Python locally on server
sudo apt install python3 python3-pip python3-venv -y

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run parser once to create session
python parser.py
# Enter your Telegram code

# Deactivate venv
deactivate
```

### 4. Create Required Directories

```bash
mkdir -p data logs session
chmod 755 data logs session
```

### 5. Build and Start Services

```bash
# Build Docker image
docker compose build

# Start in detached mode
docker compose up -d
```

**Expected output:**
```
[+] Running 2/2
 ✔ Network z-words-network      Created
 ✔ Container z-words-parser     Started
```

---

## Managing the Service

### View Logs

```bash
# Follow logs in real-time
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# View scheduler logs only
docker compose logs -f parser
```

### Check Status

```bash
# Check if container is running
docker compose ps

# Check health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.State}}"
```

### Restart Service

```bash
docker compose restart
```

### Stop Service

```bash
docker compose stop
```

### Update Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d
```

---

## Monitoring

### Check Collected Data

```bash
# View channel directories
ls -lh data/

# Check specific channel
ls -lh data/channel_name/

# View index.json
cat data/channel_name/index.json | python3 -m json.tool
```

### Check Logs

```bash
# Main daemon logs
tail -f logs/daemon.log

# Channel-specific logs
tail -f logs/channel_name.log

# Docker logs
docker compose logs -f
```

### Disk Usage

```bash
# Check data directory size
du -sh data/

# Check per channel
du -sh data/*/
```

---

## Configuration

### Adjust Monitoring and Backfill Intervals

The parser runs as a daemon with two separate intervals:

Edit `parser_daemon.py`:

```python
MONITOR_INTERVAL = 120  # Check for new posts every 2 minutes (120 seconds)
BACKFILL_INTERVAL = 6 * 3600  # Backfill old posts every 6 hours
BACKFILL_LIMIT = 1000  # Can also be set in .env
```

Or adjust via environment variables in `.env`:

```env
BACKFILL_LIMIT=500  # Fetch fewer old messages per backfill run
```

Rebuild and restart:
```bash
docker compose down
docker compose build
docker compose up -d
```

### Resource Limits

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Increase CPU
      memory: 1G       # Increase memory
```

Apply:
```bash
docker compose down
docker compose up -d
```

---

## Backup & Restore

### Backup Data

```bash
# Create backup directory
mkdir -p ~/backups

# Backup data
tar -czf ~/backups/z-words-data-$(date +%Y%m%d).tar.gz data/

# Backup logs
tar -czf ~/backups/z-words-logs-$(date +%Y%m%d).tar.gz logs/

# Backup session
cp session/z_worlds_collector_session.session ~/backups/
```

### Automated Backups (Optional)

Create backup script `/opt/z-words-collector/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backup/z-words-collector"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/data-$DATE.tar.gz -C /opt/z-words-collector data/

# Keep only last 7 days
find $BACKUP_DIR -name "data-*.tar.gz" -mtime +7 -delete
```

Add to crontab (daily at 2 AM):
```bash
crontab -e
0 2 * * * /opt/z-words-collector/backup.sh
```

### Restore Data

```bash
cd /opt/z-words-collector
tar -xzf ~/backups/z-words-data-YYYYMMDD.tar.gz
docker compose restart
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs

# Check .env file exists
ls -la .env

# Verify session file
ls -la session/
```

### Session Expired

```bash
# Stop container
docker compose stop

# Recreate session locally
python3 parser.py

# Or transfer new session from local machine
scp session/z_worlds_collector_session.session user@server:/opt/z-words-collector/session/

# Restart
docker compose start
```

### High Memory Usage

```bash
# Check container stats
docker stats z-words-parser

# Reduce INITIAL_FETCH_LIMIT in .env
nano .env
# Set INITIAL_FETCH_LIMIT=500

# Restart
docker compose restart
```

### Disk Full

```bash
# Check disk usage
df -h

# Clean Docker system
docker system prune -a

# Archive old data
cd data/
tar -czf ~/old-data.tar.gz channel_name/2024-*.json.gz
rm channel_name/2024-*.json.gz
```

### Rate Limits (FloodWaitError)

- Reduce `INITIAL_FETCH_LIMIT` to 500 or less
- Reduce `BACKFILL_LIMIT` to 500 or less
- Increase monitoring interval in `parser_daemon.py` (e.g., 5 minutes instead of 2)
- Increase backfill interval in `parser_daemon.py` (e.g., 12 hours instead of 6)
- Wait the specified time before retrying

---

## Security Best Practices

### 1. Firewall Configuration

```bash
# Install ufw
sudo apt install ufw

# Allow SSH (important!)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

### 2. Secure .env File

```bash
chmod 600 .env
```

### 3. Regular Updates

```bash
# Update system weekly
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker compose pull
docker compose up -d
```

### 4. Monitor Logs

Set up log monitoring to detect issues:

```bash
# Install logwatch
sudo apt install logwatch

# Or use your preferred monitoring solution
```

---

## Uninstallation

```bash
# Stop and remove containers
cd /opt/z-words-collector
docker compose down

# Remove data (CAUTION!)
sudo rm -rf /opt/z-words-collector

# Remove Docker image
docker rmi z-words-collector-parser
```

---

## Support

If you encounter issues:

1. Check logs: `docker compose logs`
2. Review this guide
3. Check GitHub Issues: https://github.com/de43gy/z-words-collector/issues
4. Create a new issue with:
   - Error messages
   - Docker logs
   - System info (`docker version`, `docker compose version`)

---

**Last Updated:** 2025-10-15
**Docker Compose Version:** 3.8
