# Z-Words Collector

An automated data pipeline for collecting, archiving, and analyzing posts from Russian pro-war ('Z') Telegram channels. Designed for historical and research applications.

## Features

- 📥 Automated Telegram channel data collection
- 💾 Incremental updates (fetches only new messages)
- 🗜️ Data compression with gzip (5-10x space savings)
- 📊 Metadata tracking (views, forwards, reactions)
- 🔄 Duplicate detection by message ID
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
