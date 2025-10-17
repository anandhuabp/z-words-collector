#!/usr/bin/env python3
"""
Z-Words Collector Daemon

Continuous monitoring daemon for Telegram channels.
- Monitors new posts in real-time (every 2 minutes)
- Backfills old posts every 6 hours
- Detects deleted messages
"""

import os
import json
import gzip
import logging
import signal
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import asyncio


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        return super().default(obj)


load_dotenv()

# Paths configuration
SESSION_PATH = Path('session/z_worlds_collector_session.session')
DATA_PATH = Path('data')
LOGS_PATH = Path('logs')

# Create directories
SESSION_PATH.parent.mkdir(exist_ok=True)
DATA_PATH.mkdir(exist_ok=True)
LOGS_PATH.mkdir(exist_ok=True)

# Configuration
MONITOR_INTERVAL = 120  # Check for new posts every 2 minutes
BACKFILL_INTERVAL = 6 * 3600  # Backfill old posts every 6 hours
BACKFILL_LIMIT = int(os.getenv('BACKFILL_LIMIT', '1000'))  # Posts per backfill run


# Configure logging
def setup_logging():
    """Setup enhanced logging with rotation"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, datefmt=date_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Main rotating file handler
    main_log_file = LOGS_PATH / 'parser.log'
    file_handler = RotatingFileHandler(
        main_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return logging.getLogger(__name__)


logger = setup_logging()

# Environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TARGET_CHANNELS = os.getenv('TARGET_CHANNELS', '').split(',')
TARGET_CHANNELS = [ch.strip() for ch in TARGET_CHANNELS if ch.strip()]

if not all([API_ID, API_HASH, PHONE_NUMBER, TARGET_CHANNELS]):
    logger.error("Missing required environment variables!")
    sys.exit(1)

client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

# Global shutdown flag
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {sig}. Initiating graceful shutdown...")
    shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_index(channel_path: Path) -> Dict[str, Any]:
    """Load index.json for a channel"""
    index_file = channel_path / 'index.json'
    if index_file.exists():
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"index.json corrupted in {channel_path}")

    return {
        'channel_username': channel_path.name,
        'total_posts_archived': 0,
        'last_known_id': 0,
        'min_known_id': None,
        'first_post_date': None,
        'last_post_date': None,
        'last_updated': None,
        'last_backfill': None,  # Track last backfill run
        'data_files': [],
        'deleted_messages': {
            'ids': [],
            'count': 0,
            'last_check': None
        }
    }


def save_index(channel_path: Path, index_data: Dict[str, Any]) -> None:
    """Save index.json for a channel"""
    index_file = channel_path / 'index.json'
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)


def load_gzip_json(filepath: Path) -> Dict[str, Any]:
    """Load data from .json.gz file"""
    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        return json.load(f)


def save_gzip_json(filepath: Path, data: Dict[str, Any]) -> None:
    """Save data to .json.gz file"""
    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)


async def fetch_new_messages(channel_username: str, last_known_id: int) -> List[Dict[str, Any]]:
    """
    Fetch only new messages (ID > last_known_id).
    Used for continuous monitoring.
    """
    messages_data = []

    try:
        # Fetch without limit to get all new messages
        async for message in client.iter_messages(channel_username, min_id=last_known_id):
            if not message or (message.text is None and message.media is None):
                continue

            message_dict = message.to_dict()
            message_data = {
                'id': message.id,
                'date': message.date.isoformat(),
                'text': message.text,
                'views': message.views,
                'forwards': message.forwards,
                'edit_date': message.edit_date.isoformat() if message.edit_date else None,
                'reactions': [
                    {
                        'emoji': r.reaction.emoticon if hasattr(r.reaction, 'emoticon') else None,
                        'type': r.reaction.__class__.__name__,
                        'count': r.count
                    }
                    for r in message.reactions.results
                ] if message.reactions else [],
                'has_media': message.media is not None,
                'media_type': message.media.__class__.__name__ if message.media else None,
                'fwd_from': {
                    'from_id': str(message.fwd_from.from_id) if message.fwd_from and hasattr(message.fwd_from, 'from_id') else None,
                    'from_name': message.fwd_from.from_name if message.fwd_from and hasattr(message.fwd_from, 'from_name') else None,
                    'date': message.fwd_from.date.isoformat() if message.fwd_from and hasattr(message.fwd_from, 'date') else None
                } if message.fwd_from else None,
                'raw': message_dict
            }
            messages_data.append(message_data)

    except FloodWaitError as e:
        logger.warning(f"[{channel_username}] FloodWaitError: waiting {e.seconds}s")
        await asyncio.sleep(e.seconds)
        # Retry once
        return await fetch_new_messages(channel_username, last_known_id)
    except Exception as e:
        logger.error(f"[{channel_username}] Error fetching new messages: {e}", exc_info=True)

    return messages_data


async def fetch_old_messages(channel_username: str, min_known_id: int, limit: int) -> List[Dict[str, Any]]:
    """
    Fetch old messages (ID < min_known_id).
    Used for periodic backfill.
    """
    messages_data = []

    try:
        async for message in client.iter_messages(channel_username, max_id=min_known_id, limit=limit):
            if not message or (message.text is None and message.media is None):
                continue

            message_dict = message.to_dict()
            message_data = {
                'id': message.id,
                'date': message.date.isoformat(),
                'text': message.text,
                'views': message.views,
                'forwards': message.forwards,
                'edit_date': message.edit_date.isoformat() if message.edit_date else None,
                'reactions': [
                    {
                        'emoji': r.reaction.emoticon if hasattr(r.reaction, 'emoticon') else None,
                        'type': r.reaction.__class__.__name__,
                        'count': r.count
                    }
                    for r in message.reactions.results
                ] if message.reactions else [],
                'has_media': message.media is not None,
                'media_type': message.media.__class__.__name__ if message.media else None,
                'fwd_from': {
                    'from_id': str(message.fwd_from.from_id) if message.fwd_from and hasattr(message.fwd_from, 'from_id') else None,
                    'from_name': message.fwd_from.from_name if message.fwd_from and hasattr(message.fwd_from, 'from_name') else None,
                    'date': message.fwd_from.date.isoformat() if message.fwd_from and hasattr(message.fwd_from, 'date') else None
                } if message.fwd_from else None,
                'raw': message_dict
            }
            messages_data.append(message_data)

            if len(messages_data) % 500 == 0:
                logger.info(f"[{channel_username}] Backfill progress: {len(messages_data)}/{limit}")

    except FloodWaitError as e:
        logger.warning(f"[{channel_username}] FloodWaitError during backfill: waiting {e.seconds}s")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"[{channel_username}] Error during backfill: {e}", exc_info=True)

    return messages_data


def save_messages(channel_path: Path, messages: List[Dict[str, Any]], index: Dict[str, Any]) -> None:
    """Save messages to daily file and update index"""
    if not messages:
        return

    # Sort messages by ID
    messages.sort(key=lambda x: x['id'])

    # Filename for today's data
    today_str = date.today().isoformat()
    output_filename = channel_path / f"{today_str}.json.gz"

    # Load existing messages from today's file if it exists
    existing_messages = []
    if output_filename.exists():
        try:
            file_data = load_gzip_json(output_filename)
            if isinstance(file_data, dict) and 'messages' in file_data:
                existing_messages = file_data['messages']
            elif isinstance(file_data, list):
                existing_messages = file_data
        except Exception as e:
            logger.warning(f"Failed to load {output_filename}: {e}")

    # Merge and deduplicate
    all_messages = existing_messages + messages
    unique_messages = {msg['id']: msg for msg in all_messages}.values()
    unique_messages = sorted(unique_messages, key=lambda x: x['id'])

    # Create file data with metadata
    min_id = min(msg['id'] for msg in messages)
    max_id = max(msg['id'] for msg in messages)

    file_data = {
        'metadata': {
            'collection_timestamp': datetime.now().isoformat(),
            'channel_username': index['channel_username'],
            'total_messages': len(unique_messages),
            'min_id_in_batch': min_id,
            'max_id_in_batch': max_id,
            'date': today_str
        },
        'messages': list(unique_messages)
    }

    # Save to .json.gz
    save_gzip_json(output_filename, file_data)

    # Update index
    new_count = len([m for m in messages if m['id'] not in [em['id'] for em in existing_messages]])
    index['total_posts_archived'] += new_count
    index['last_known_id'] = max(max_id, index.get('last_known_id', 0))

    if index.get('min_known_id') is None:
        index['min_known_id'] = min_id
    else:
        index['min_known_id'] = min(min_id, index['min_known_id'])

    index['last_updated'] = datetime.now().isoformat()

    # Update first and last post dates
    if messages:
        first_msg_date = messages[0]['date']
        last_msg_date = messages[-1]['date']

        if index['first_post_date'] is None or first_msg_date < index['first_post_date']:
            index['first_post_date'] = first_msg_date
        if index['last_post_date'] is None or last_msg_date > index['last_post_date']:
            index['last_post_date'] = last_msg_date

    # Update data_files info
    file_info = {
        'filename': output_filename.name,
        'date': today_str,
        'posts_count': len(unique_messages)
    }

    existing_file_index = next((i for i, f in enumerate(index['data_files']) if f['filename'] == output_filename.name), None)
    if existing_file_index is not None:
        index['data_files'][existing_file_index] = file_info
    else:
        index['data_files'].append(file_info)

    save_index(channel_path, index)


async def monitor_channel(channel_username: str):
    """
    Continuous monitoring of new posts for a single channel.
    Runs in a loop, checking every MONITOR_INTERVAL seconds.
    """
    channel_path = DATA_PATH / channel_username
    channel_path.mkdir(exist_ok=True)

    logger.info(f"[{channel_username}] Starting continuous monitoring (interval: {MONITOR_INTERVAL}s)")

    while not shutdown_requested:
        try:
            index = load_index(channel_path)
            last_known_id = index['last_known_id']

            # Fetch new messages
            new_messages = await fetch_new_messages(channel_username, last_known_id)

            if new_messages:
                logger.info(f"[{channel_username}] Found {len(new_messages)} new messages")
                save_messages(channel_path, new_messages, index)
                logger.info(f"[{channel_username}] Saved new messages. Total: {index['total_posts_archived']}")
            else:
                logger.debug(f"[{channel_username}] No new messages")

        except Exception as e:
            logger.error(f"[{channel_username}] Error in monitor loop: {e}", exc_info=True)

        # Sleep before next check
        await asyncio.sleep(MONITOR_INTERVAL)


async def backfill_channel(channel_username: str):
    """
    Periodic backfill of old posts for a single channel.
    Runs every BACKFILL_INTERVAL seconds.
    """
    channel_path = DATA_PATH / channel_username
    channel_path.mkdir(exist_ok=True)

    logger.info(f"[{channel_username}] Starting backfill scheduler (interval: {BACKFILL_INTERVAL/3600:.1f}h)")

    while not shutdown_requested:
        try:
            index = load_index(channel_path)
            min_known_id = index.get('min_known_id')

            # Skip if we've reached the beginning
            if min_known_id and min_known_id > 1:
                logger.info(f"[{channel_username}] Starting backfill (ID < {min_known_id})")

                old_messages = await fetch_old_messages(channel_username, min_known_id, BACKFILL_LIMIT)

                if old_messages:
                    logger.info(f"[{channel_username}] Backfilled {len(old_messages)} old messages")
                    save_messages(channel_path, old_messages, index)
                    index['last_backfill'] = datetime.now().isoformat()
                    save_index(channel_path, index)
                else:
                    logger.info(f"[{channel_username}] Backfill complete - reached beginning of channel")
            else:
                logger.info(f"[{channel_username}] Backfill skipped - no min_known_id or reached beginning")

        except Exception as e:
            logger.error(f"[{channel_username}] Error in backfill: {e}", exc_info=True)

        # Sleep until next backfill
        await asyncio.sleep(BACKFILL_INTERVAL)


async def main():
    """Main daemon loop"""
    logger.info("=" * 60)
    logger.info("Z-Words Collector Daemon Starting")
    logger.info("=" * 60)
    logger.info(f"Target channels: {', '.join(TARGET_CHANNELS)}")
    logger.info(f"Monitor interval: {MONITOR_INTERVAL}s")
    logger.info(f"Backfill interval: {BACKFILL_INTERVAL/3600:.1f}h")
    logger.info("=" * 60)

    # Check if session exists
    if not SESSION_PATH.exists():
        logger.error("=" * 60)
        logger.error("ERROR: Telegram session file not found!")
        logger.error(f"Expected location: {SESSION_PATH}")
        logger.error("")
        logger.error("You must create a Telegram session BEFORE running the daemon.")
        logger.error("")
        logger.error("To create a session:")
        logger.error("1. Run locally: python create_session.py")
        logger.error("2. Enter the code from Telegram")
        logger.error("3. Transfer session file to server:")
        logger.error(f"   scp session/*.session user@server:{SESSION_PATH.parent}/")
        logger.error("")
        logger.error("See DEPLOYMENT.md for detailed instructions.")
        logger.error("=" * 60)
        sys.exit(1)

    # Connect using existing session (no phone parameter = no interactive auth)
    await client.start()
    logger.info("Telegram client connected")

    # Create tasks for all channels
    tasks = []

    for channel in TARGET_CHANNELS:
        channel = channel.strip()
        if not channel:
            continue

        # Monitor task (continuous)
        monitor_task = asyncio.create_task(monitor_channel(channel))
        tasks.append(monitor_task)

        # Backfill task (periodic)
        backfill_task = asyncio.create_task(backfill_channel(channel))
        tasks.append(backfill_task)

    logger.info(f"Started {len(tasks)} tasks ({len(TARGET_CHANNELS)} channels × 2)")

    # Wait for shutdown signal
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled")

    logger.info("Daemon shutdown complete")


if __name__ == '__main__':
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
