import os
import json
import gzip
import logging
from datetime import datetime, date
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TARGET_CHANNELS = os.getenv('TARGET_CHANNELS').split(',')
INITIAL_FETCH_LIMIT = int(os.getenv('INITIAL_FETCH_LIMIT', '5000'))

SESSION_PATH = Path('session/z_worlds_collector_session.session')
DATA_PATH = Path('data')

SESSION_PATH.parent.mkdir(exist_ok=True)
DATA_PATH.mkdir(exist_ok=True)

client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)


def load_index(channel_path: Path) -> Dict[str, Any]:
    """Load index.json for a channel"""
    index_file = channel_path / 'index.json'
    if index_file.exists():
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"index.json corrupted in {channel_path}. Creating a new one.")

    # Return a new index structure if file doesn't exist or is corrupted
    return {
        'channel_username': channel_path.name,
        'total_posts_archived': 0,
        'last_known_id': 0,
        'min_known_id': None,  # Track oldest downloaded message
        'first_post_date': None,
        'last_post_date': None,
        'last_updated': None,
        'data_files': []
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


async def fetch_messages_batch(channel_username: str, min_id: int = None, max_id: int = None, limit: int = None) -> List[Dict[str, Any]]:
    """Fetch a batch of messages and convert them to dict format"""
    messages_data = []
    message_count = 0

    # Build kwargs only with non-None values
    kwargs = {}
    if min_id is not None:
        kwargs['min_id'] = min_id
    if max_id is not None:
        kwargs['max_id'] = max_id
    if limit is not None:
        kwargs['limit'] = limit

    try:
        async for message in client.iter_messages(channel_username, **kwargs):
            if not message or (message.text is None and message.media is None):
                continue

            # Save full raw message for future reference
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
            message_count += 1

            # Progress indicator every 500 messages
            if message_count % 500 == 0:
                if limit:
                    logger.info(f"[{channel_username}] Progress: {message_count}/{limit} messages")
                else:
                    logger.info(f"[{channel_username}] Progress: {message_count} messages downloaded...")

    except FloodWaitError as e:
        logger.warning(f"[{channel_username}] Rate limit hit. Need to wait {e.seconds} seconds.")
        raise
    except Exception as e:
        logger.error(f"[{channel_username}] Error occurred: {e}", exc_info=True)
        raise

    return messages_data


async def fetch_channel(channel_username: str) -> None:
    """Fetch and store messages from a Telegram channel"""
    logger.info(f"[{channel_username}] Starting data collection...")
    channel_path = DATA_PATH / channel_username
    channel_path.mkdir(exist_ok=True)

    # Get channel info to show total posts
    try:
        entity = await client.get_entity(channel_username)
        # Try to get first message to check total count
        first_msg = await client.get_messages(entity, limit=1)
        if first_msg and len(first_msg) > 0:
            total_posts_in_channel = first_msg[0].id
            logger.info(f"[{channel_username}] Total posts in channel: ~{total_posts_in_channel}")
        else:
            total_posts_in_channel = None
    except Exception as e:
        logger.warning(f"[{channel_username}] Could not get channel info: {e}")
        total_posts_in_channel = None

    # Load index to get last known message ID
    index = load_index(channel_path)
    last_known_id = index['last_known_id']
    min_known_id = index.get('min_known_id')

    # Show progress
    if total_posts_in_channel:
        logger.info(f"[{channel_username}] Downloaded: {index['total_posts_archived']} / ~{total_posts_in_channel} posts")

    # Step 1: Fetch NEW messages (forward direction)
    new_messages_forward = []
    if last_known_id == 0:
        # First run: fetch last N messages
        if INITIAL_FETCH_LIMIT > 0:
            logger.info(f"[{channel_username}] First run: fetching last {INITIAL_FETCH_LIMIT} messages")
            new_messages_forward = await fetch_messages_batch(channel_username, limit=INITIAL_FETCH_LIMIT)
        else:
            logger.info(f"[{channel_username}] First run: fetching all messages (may take a long time)")
            new_messages_forward = await fetch_messages_batch(channel_username)
    else:
        # Fetch new messages after last_known_id
        logger.info(f"[{channel_username}] Checking for new messages (ID > {last_known_id})...")
        new_messages_forward = await fetch_messages_batch(channel_username, min_id=last_known_id)

        if new_messages_forward:
            logger.info(f"[{channel_username}] Found {len(new_messages_forward)} new messages")
        else:
            logger.info(f"[{channel_username}] No new messages found")

    # Step 2: Fetch OLD messages (backward direction - backfill)
    new_messages_backward = []
    if min_known_id and min_known_id > 1:
        logger.info(f"[{channel_username}] Backfill: fetching older messages (ID < {min_known_id})...")
        # Fetch older messages with limit to avoid downloading too much at once
        backfill_limit = INITIAL_FETCH_LIMIT if INITIAL_FETCH_LIMIT > 0 else 1000
        new_messages_backward = await fetch_messages_batch(channel_username, max_id=min_known_id, limit=backfill_limit)

        if new_messages_backward:
            logger.info(f"[{channel_username}] Downloaded {len(new_messages_backward)} older messages")
        else:
            logger.info(f"[{channel_username}] No older messages to download (reached beginning of channel)")

    # Combine all new messages
    all_new_messages = new_messages_forward + new_messages_backward

    if not all_new_messages:
        logger.info(f"[{channel_username}] No new data to save")
        return

    # Sort messages by ID
    all_new_messages.sort(key=lambda x: x['id'])

    # Track min and max IDs
    min_id_in_batch = min(msg['id'] for msg in all_new_messages)
    max_id_in_batch = max(msg['id'] for msg in all_new_messages)

    # Filename for today's data
    today_str = date.today().isoformat()
    output_filename = channel_path / f"{today_str}.json.gz"

    # Load existing messages from today's file if it exists
    existing_today_messages = []
    if output_filename.exists():
        try:
            file_data = load_gzip_json(output_filename)
            if isinstance(file_data, dict) and 'messages' in file_data:
                existing_today_messages = file_data['messages']
            elif isinstance(file_data, list):
                existing_today_messages = file_data
        except Exception as e:
            logger.warning(f"[{channel_username}] Failed to load {output_filename}: {e}")

    # Merge messages and remove duplicates by ID
    all_messages = existing_today_messages + all_new_messages
    unique_messages = {msg['id']: msg for msg in all_messages}.values()
    unique_messages = sorted(unique_messages, key=lambda x: x['id'])

    # Create file data with metadata
    file_data = {
        'metadata': {
            'collection_timestamp': datetime.now().isoformat(),
            'channel_username': channel_username,
            'total_messages': len(unique_messages),
            'min_id_in_batch': min_id_in_batch,
            'max_id_in_batch': max_id_in_batch,
            'date': today_str
        },
        'messages': list(unique_messages)
    }

    # Save to .json.gz
    save_gzip_json(output_filename, file_data)
    logger.info(f"[{channel_username}] Saved {len(all_new_messages)} new messages to {output_filename}")

    # Update index
    index['total_posts_archived'] += len(all_new_messages)
    index['last_known_id'] = max(max_id_in_batch, index['last_known_id'])

    # Update min_known_id
    if min_known_id is None:
        index['min_known_id'] = min_id_in_batch
    else:
        index['min_known_id'] = min(min_id_in_batch, min_known_id)

    index['last_updated'] = datetime.now().isoformat()

    # Update first and last post dates
    if all_new_messages:
        first_msg_date = all_new_messages[0]['date']
        last_msg_date = all_new_messages[-1]['date']

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

    # Check if file entry already exists in index
    existing_file_index = next((i for i, f in enumerate(index['data_files']) if f['filename'] == output_filename.name), None)
    if existing_file_index is not None:
        index['data_files'][existing_file_index] = file_info
    else:
        index['data_files'].append(file_info)

    # Save updated index
    save_index(channel_path, index)

    # Show final progress
    if total_posts_in_channel:
        progress_pct = (index['total_posts_archived'] / total_posts_in_channel) * 100
        logger.info(f"[{channel_username}] Progress: {index['total_posts_archived']} / ~{total_posts_in_channel} posts ({progress_pct:.1f}%)")
    else:
        logger.info(f"[{channel_username}] Total archived: {index['total_posts_archived']} posts")

async def main():
    await client.start(phone=PHONE_NUMBER)
    for channel in TARGET_CHANNELS:
        await fetch_channel(channel.strip())

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())