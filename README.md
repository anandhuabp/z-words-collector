# Z-Words Collector

An automated data pipeline for collecting, archiving, and analyzing posts from Russian pro-war ('Z') Telegram channels. Designed for historical and research applications.

## Features

- 📥 Automated Telegram channel data collection
- 💾 Incremental updates (fetches only new messages)
- 🔄 Automatic backfill (downloads older messages gradually)
- 🗜️ Data compression with gzip (5-10x space savings)
- 📊 Metadata tracking (views, forwards, reactions)
- 🔍 Gap detection (tracks deleted messages)
- 🔁 Exponential backoff with FloodWaitError handling
- 📝 Rotating logs with per-channel files
- 🔄 Duplicate detection by message ID
- 🤖 GitHub Actions automation (runs every 6 hours)
- 🐳 Docker support for easy deployment

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

## GitHub Actions Automation

The project includes automated data collection using GitHub Actions that runs every 6 hours.

### Setup GitHub Actions

**1. Enable GitHub Actions**

Go to your repository → Settings → Actions → General → Enable "Read and write permissions"

**2. Add Repository Secrets**

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `API_ID` | Telegram API ID | `12345678` |
| `API_HASH` | Telegram API Hash | `abcdef1234567890` |
| `PHONE_NUMBER` | Your phone number | `+79261234567` |
| `TARGET_CHANNELS` | Channels to collect | `channel1,channel2` |
| `INITIAL_FETCH_LIMIT` | Messages per run | `1000` |
| `TELEGRAM_SESSION` | Base64-encoded session file | See below |

**3. Create Telegram Session**

First, run the parser locally to create a session file:

```bash
python parser.py
# Enter your Telegram code when prompted
```

Then encode the session file to base64:

```bash
# Linux/macOS
base64 session/z_worlds_collector_session.session

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("session\z_worlds_collector_session.session"))
```

Copy the output and add it as `TELEGRAM_SESSION` secret.

**4. Enable Workflow**

The workflow will run automatically:
- **Every 6 hours** (00:00, 06:00, 12:00, 18:00 UTC)
- **Manually** via Actions tab → "Automated Data Collection" → "Run workflow"

### Manual Trigger

You can manually trigger data collection:

1. Go to Actions tab
2. Select "Automated Data Collection"
3. Click "Run workflow"
4. Optionally specify custom channels (comma-separated)

### Monitoring

**View workflow runs:**
- Go to Actions tab to see all runs
- Green ✅ = Success
- Red ❌ = Failed (check logs)

**Download artifacts:**
- Each run saves logs and session backup
- Go to specific run → Artifacts section
- Download `logs-{run_number}` or `session-backup-{run_number}`

### How It Works

1. **Checkout** - Clones repository
2. **Setup Python** - Installs Python 3.11
3. **Install dependencies** - Runs `pip install -r requirements.txt`
4. **Restore session** - Decodes session from secrets
5. **Run parser** - Executes `python parser.py`
6. **Save session** - Backs up session to artifacts
7. **Commit changes** - Pushes new data to repository
8. **Upload logs** - Saves logs as artifacts

### Customizing Schedule

Edit `.github/workflows/parser.yml`:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Every 6 hours
  # Examples:
  # - cron: '0 */12 * * *'  # Every 12 hours
  # - cron: '0 0 * * *'     # Daily at midnight
  # - cron: '0 9,21 * * *'  # Twice daily (9 AM, 9 PM)
```

### Troubleshooting

**Issue: Session expired**
- Re-run parser locally with 2FA code
- Update `TELEGRAM_SESSION` secret with new session

**Issue: Rate limits**
- Reduce `INITIAL_FETCH_LIMIT` secret (try 500)
- Increase schedule interval (every 12 hours instead of 6)

**Issue: Large data files**
- GitHub has 100MB file limit
- Consider using Git LFS or cloud storage for large files

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
├── parser.py              # Main collection script
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── .env                   # Your config (not in git)
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker orchestration
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
│   ├── parser.log                 # Main log file
│   ├── parser.log.1               # Rotated backup logs
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

To modify rotation settings, edit `parser.py`:

```python
# Main log: lines 62-66
maxBytes=10 * 1024 * 1024,  # Change to 50 * 1024 * 1024 for 50MB
backupCount=5                # Change to 10 for more backups

# Channel logs: lines 99-103
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
