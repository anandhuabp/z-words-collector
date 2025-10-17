#!/usr/bin/env python3
"""
Telegram Session Creator

Run this script ONCE to create a Telegram session file.
You'll need to enter the verification code sent to your Telegram app.

Usage:
    python create_session.py
"""

import os
import sys
from pathlib import Path
from telethon import TelegramClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SESSION_PATH = Path('session/z_worlds_collector_session')
SESSION_PATH.parent.mkdir(exist_ok=True)

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

# Validate environment variables
if not all([API_ID, API_HASH, PHONE_NUMBER]):
    print("ERROR: Missing required environment variables!")
    print("")
    print("Please create .env file with:")
    print("  API_ID=your_api_id")
    print("  API_HASH=your_api_hash")
    print("  PHONE_NUMBER=+79261234567")
    print("")
    print("Get API credentials from: https://my.telegram.org")
    sys.exit(1)

print("=" * 60)
print("Telegram Session Creator")
print("=" * 60)
print(f"Phone number: {PHONE_NUMBER}")
print(f"Session will be saved to: {SESSION_PATH}.session")
print("=" * 60)
print("")

# Check if session already exists
if Path(f"{SESSION_PATH}.session").exists():
    response = input("Session file already exists. Recreate? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

# Create client
client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)


async def main():
    """Create session with interactive authentication"""
    print("Connecting to Telegram...")
    print("")

    # Start with phone number (will prompt for code)
    await client.start(phone=PHONE_NUMBER)

    print("")
    print("=" * 60)
    print("SUCCESS! Session created successfully!")
    print("=" * 60)
    print(f"Session file: {SESSION_PATH}.session")
    print("")
    print("Next steps:")
    print("1. To deploy on server, transfer the session file:")
    print(f"   scp {SESSION_PATH}.session user@server:/opt/z-words-collector/session/")
    print("")
    print("2. Then deploy via GitHub Actions or run:")
    print("   docker compose up -d")
    print("")
    print("See DEPLOYMENT.md for detailed deployment instructions.")
    print("=" * 60)

    await client.disconnect()


if __name__ == '__main__':
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
