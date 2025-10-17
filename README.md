# Z-Words Collector

An automated data pipeline for collecting, archiving, and analyzing posts from Russian pro-war ('Z') Telegram channels. Designed for historical and research applications.

## Features

- 📥 Automated Telegram channel data collection
- ⚡ **Daemon Mode** - Continuous monitoring for new posts (every 2 minutes)
- 💾 Incremental updates (fetches only new messages in real-time)
- 🔄 Periodic backfill (downloads older messages every 6 hours)
- 🗜️ Data compression with gzip (5-10x space savings)
- 📊 Metadata tracking (views, forwards, reactions)
- 🔍 Gap detection (tracks deleted messages)
- 🔁 Exponential backoff with FloodWaitError handling
- 📝 Rotating logs with per-channel files
- 🔄 Duplicate detection by message ID
- 🖥️ Server deployment with Docker Compose
- 🚀 **GitHub Actions SSH Deployment** - Automated deployment via SSH
- 🔒 Production-ready with health checks & auto-restart

## Prerequisites

- Python 3.10 or higher
- Telegram account with phone number
- Telegram API credentials (API_ID and API_HASH)

## First-Time Setup

### 1. Clone the repository

```bash
git clone https://github.com/de43gy/z-words-collector.git
cd z-words-collector
```

### 2. Create virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get Telegram API credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click on "API development tools"
4. Create a new application (any name/description)
5. Copy your **API_ID** and **API_HASH**

### 5. Configure environment variables

```bash
# Copy example file
cp .env.example .env

# Edit .env file with your credentials
```

Example `.env` configuration:

```env
# Telegram API credentials
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+79261234567

# Channels to collect (comma-separated, without @)
TARGET_CHANNELS=channel1,channel2,channel3

# Limit for first run (0 = unlimited, not recommended)
INITIAL_FETCH_LIMIT=5000
```

### 6. Run the parser for the first time

```bash
# Windows (if Unicode errors occur)
set PYTHONIOENCODING=utf-8
python parser.py

# Linux/macOS
python parser.py
```

**First run process:**
1. Script will request authorization code from Telegram
2. Check your Telegram app (you'll receive a login code)
3. Enter the code in the terminal
4. If 2FA is enabled, enter your password
5. Session will be saved in `session/` folder
6. Data collection will start automatically

**Expected output:**
```
[channel1] Starting data collection...
[channel1] First run: fetching up to 5000 messages
[channel1] Progress: 500/5000 messages collected
[channel1] Progress: 1000/5000 messages collected
...
[channel1] Saved 5000 messages to data/channel1/2025-10-15.json.gz
[channel1] Updated index.json
```

## Regular Usage

After first-time setup, just run:

```bash
python parser.py
```

The parser will:
- Use saved session (no login required)
- Check `index.json` for last collected message ID
- Fetch only new messages (incremental update)
- Save data to compressed `.json.gz` files

## Project Reset

To reset the project to initial state (for testing or fresh start):

```bash
# Remove all collected data and session
rm -rf data/ session/ parser_output.log

# Now you can run first-time setup again
python parser.py
```

**Quick reset script** (optional):

Create `reset.sh` (Linux/macOS) or `reset.bat` (Windows):

```bash
#!/bin/bash
rm -rf data/ session/ parser_output.log
echo "Project reset to initial state"
```

Make it executable:
```bash
chmod +x reset.sh
./reset.sh
```

## Server Deployment

The project runs as a **daemon service** with **continuous monitoring** for new posts and **periodic backfill** of old posts.

**👉 See [DEPLOYMENT.md](DEPLOYMENT.md) for complete server deployment guide.**

### Quick Start (GitHub Actions SSH Deployment - Recommended)

```bash
# 1. Generate SSH key for deployment
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy
ssh-copy-id -i ~/.ssh/github_actions_deploy.pub user@your-server

# 2. Configure GitHub Secrets:
# - SSH_PRIVATE_KEY, API_ID, API_HASH, PHONE_NUMBER

# 3. Configure GitHub Variables:
# - SSH_HOST, SSH_USER, DEPLOY_PATH, TARGET_CHANNELS, INITIAL_FETCH_LIMIT, BACKFILL_LIMIT

# 4. Create Telegram session and transfer to server
python parser.py  # Enter Telegram code
scp session/z_worlds_collector_session.session user@server:/opt/z-words-collector/session/

# 5. Push to main branch - automatic deployment!
git push origin main
```

**Features:**
- ⚡ **Continuous monitoring** - Checks for new posts every 2 minutes
- 🔄 **Periodic backfill** - Downloads old posts every 6 hours
- 🚀 **Automated deployment** - Push to GitHub triggers SSH deployment
- 🔄 Auto-restart on failure
- 📝 Persistent logs and data
- 🏥 Health checks
- 💾 Data stored on your server (not in git)

**See [DEPLOYMENT.md](DEPLOYMENT.md) for:**
- GitHub Actions SSH deployment setup
- Manual server deployment
- Server requirements
- Configuration options
- Monitoring & troubleshooting
- Backup strategies

## Docker Usage

### Build and run

```bash
docker-compose up --build
```

### Run in background

```bash
docker-compose up -d
```

### View logs

```bash
docker-compose logs -f
```

### Stop and remove containers

```bash
docker-compose down
```

## Project Structure

```
z-words-collector/
├── parser_daemon.py       # Main daemon service (continuous monitoring)
├── parser.py              # One-time collection script (for testing/setup)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── .env                   # Your config (not in git)
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker orchestration
│
├── .github/
│   └── workflows/
│       └── deploy.yml     # GitHub Actions SSH deployment
│
├── session/               # Telegram session files (auto-created)
│   └── *.session
│
├── data/                  # Collected data (auto-created)
│   └── channel_name/
│       ├── index.json             # Channel metadata
│       └── YYYY-MM-DD.json.gz     # Daily data files
│
├── logs/                  # Log files (auto-created)
│   ├── daemon.log                 # Main daemon log file
│   ├── daemon.log.1               # Rotated backup logs
│   └── channel_name.log           # Per-channel logs
│
└── local_docs/            # Project documentation
```

## Data Format

### index.json (per channel)
```json
{
  "channel_username": "channel1",
  "total_posts_archived": 5000,
  "last_known_id": 12345,
  "first_post_date": "2025-01-01T10:00:00+00:00",
  "last_post_date": "2025-10-15T20:00:00+00:00",
  "last_updated": "2025-10-15T20:05:00.123456"
}
```

### Daily data files (YYYY-MM-DD.json.gz)
- Compressed JSON with metadata and messages
- Contains message text, views, forwards, reactions, media info
- Includes full raw Telethon message object

To read compressed data:
```python
import gzip
import json

with gzip.open('data/channel1/2025-10-15.json.gz', 'rt', encoding='utf-8') as f:
    data = json.load(f)
    messages = data['messages']
    for msg in messages:
        print(f"ID: {msg['id']}, Text: {msg['text']}")
```

## Logging

The parser uses **automatic log rotation** to prevent log files from consuming too much disk space.

### Log Files Structure

- **`logs/parser.log`** - Main log with all events from all channels
- **`logs/parser.log.1`** to **`logs/parser.log.5`** - Rotated backup logs
- **`logs/channel_name.log`** - Per-channel log files (e.g., `dva_majors.log`)

### Automatic Rotation

**Main log (`parser.log`):**
- Maximum size: 10 MB per file
- Backup files: 5
- Total max size: ~60 MB (10MB × 6 files)

**Per-channel logs:**
- Maximum size: 5 MB per file
- Backup files: 3
- Total max size per channel: ~20 MB (5MB × 4 files)

When a log file reaches its size limit, it's automatically rotated:
```
parser.log → parser.log.1 → parser.log.2 → ... → parser.log.5 (deleted)
```

### Log Format

**Main log:**
```
2025-10-15 22:53:07 - __main__ - INFO - [channel1] Starting data collection...
2025-10-15 22:53:08 - __main__ - INFO - [channel1] Progress: 500/1000 messages
```

**Channel-specific log:**
```
2025-10-15 22:53:07 - INFO - Starting data collection...
2025-10-15 22:53:08 - INFO - Progress: 500/1000 messages
```

### Log Levels

- **INFO** - Normal operations (progress, statistics, saved data)
- **WARNING** - Non-critical issues (FloodWaitError, corrupted files)
- **ERROR** - Critical errors (exceptions, failed operations)

### Viewing Logs

**Console output:**
```bash
python parser.py
```
Shows real-time logs in terminal

**Main log file:**
```bash
# Windows
type logs\parser.log

# Linux/macOS
cat logs/parser.log
tail -f logs/parser.log  # Follow in real-time
```

**Channel-specific log:**
```bash
# View specific channel log
cat logs/dva_majors.log
```

### What Gets Logged

- Collection start/end for each channel
- Total posts in channel
- Download progress (every 500 messages)
- New/backfill messages count
- Gap detection results (deleted messages)
- FloodWaitError handling and retries
- File save operations
- Final statistics (progress percentage, deleted messages)

### Changing Log Settings

To modify rotation settings, edit `parser_daemon.py`:

```python
# Find the logging configuration section
maxBytes=10 * 1024 * 1024,  # Change to 50 * 1024 * 1024 for 50MB
backupCount=5                # Change to 10 for more backups

# For channel logs
maxBytes=5 * 1024 * 1024,   # Change to 10 * 1024 * 1024 for 10MB
backupCount=3                # Change to 5 for more backups
```

## Troubleshooting

### Issue: "database is locked"
**Solution:** Delete `session/*.session-journal` and retry

### Issue: Parser hangs on first run
**Solution:** Reduce `INITIAL_FETCH_LIMIT` in `.env` (try 1000)

### Issue: UnicodeEncodeError on Windows
**Solution:**
```bash
set PYTHONIOENCODING=utf-8
python parser.py
```

### Issue: FloodWaitError
**Solution:** Wait the specified seconds. Telegram has rate limits. Parser saves partial data automatically.

### Issue: Can't find channel
**Solution:** Check channel username in `TARGET_CHANNELS` (without @). Make sure channel is public or you're a member.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file

## Disclaimer

This tool is for research and archival purposes only. Users are responsible for complying with Telegram's Terms of Service and applicable laws. The authors are not responsible for misuse of this tool.

---

**Status:** MVP Phase 1 Complete ✅
**Last Updated:** 2025-10-15
