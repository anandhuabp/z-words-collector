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
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)


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
        'data_files': [],
        'deleted_messages': {
            'ids': [],  # List of detected deleted message IDs
            'count': 0,  # Total count of deleted messages
            'last_check': None  # Timestamp of last gap detection check
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


def detect_gaps(channel_path: Path, index: Dict[str, Any]) -> List[int]:
    """
    Detect missing message IDs (deleted messages) by checking gaps in the sequence.

    Returns:
        List of newly detected deleted message IDs
    """
    min_known_id = index.get('min_known_id')
    last_known_id = index.get('last_known_id')

    # Can't detect gaps if we don't have a range yet
    if not min_known_id or not last_known_id or min_known_id >= last_known_id:
        return []

    # Collect all message IDs we have
    existing_ids = set()

    # Read all data files to collect existing IDs
    for file_info in index.get('data_files', []):
        filepath = channel_path / file_info['filename']
        if filepath.exists():
            try:
                data = load_gzip_json(filepath)
                messages = data.get('messages', []) if isinstance(data, dict) else data
                for msg in messages:
                    existing_ids.add(msg['id'])
            except Exception as e:
                logger.warning(f"Failed to read {filepath} for gap detection: {e}")

    # Find gaps in the sequence
    expected_ids = set(range(min_known_id, last_known_id + 1))
    missing_ids = expected_ids - existing_ids

    # Get previously known deleted IDs
    known_deleted = set(index.get('deleted_messages', {}).get('ids', []))

    # Find new deleted IDs
    new_deleted_ids = sorted(missing_ids - known_deleted)

    return new_deleted_ids


async def fetch_messages_batch(channel_username: str, min_id: int = None, max_id: int = None, limit: int = None, retry_count: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch a batch of messages and convert them to dict format.

    Implements exponential backoff with FloodWaitError handling:
    - Respects Telegram's wait time from FloodWaitError
    - Saves partial progress before retry
    - Maximum 3 retry attempts

    Args:
        channel_username: Channel to fetch from
        min_id: Minimum message ID (exclusive)
        max_id: Maximum message ID (exclusive)
        limit: Maximum number of messages to fetch
        retry_count: Current retry attempt (internal use)

    Returns:
        List of message dictionaries
    """
    messages_data = []
    message_count = 0
    max_retries = 3

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
        # Telegram rate limit hit - need to wait
        wait_seconds = e.seconds

        if messages_data:
            logger.warning(
                f"[{channel_username}] FloodWaitError: Rate limit hit after {len(messages_data)} messages. "
                f"Telegram requires waiting {wait_seconds} seconds."
            )
        else:
            logger.warning(
                f"[{channel_username}] FloodWaitError: Rate limit hit immediately. "
                f"Telegram requires waiting {wait_seconds} seconds."
            )

        # Check if we can retry
        if retry_count >= max_retries:
            logger.error(
                f"[{channel_username}] Maximum retry attempts ({max_retries}) reached. "
                f"Returning {len(messages_data)} partial messages."
            )
            return messages_data

        # Wait as Telegram requested, with exponential backoff multiplier
        backoff_multiplier = 1.5 ** retry_count  # 1x, 1.5x, 2.25x
        actual_wait = wait_seconds * backoff_multiplier

        logger.info(
            f"[{channel_username}] Retry attempt {retry_count + 1}/{max_retries}. "
            f"Waiting {actual_wait:.1f} seconds (Telegram: {wait_seconds}s + backoff)..."
        )

        await asyncio.sleep(actual_wait)

        logger.info(f"[{channel_username}] Resuming after wait. Collected {len(messages_data)} messages so far.")

        # If we already collected some messages, adjust min_id/max_id to continue from where we stopped
        if messages_data:
            if max_id is not None:
                # Going backwards (backfill)
                new_max_id = min(msg['id'] for msg in messages_data)
                logger.info(f"[{channel_username}] Continuing backfill from message ID {new_max_id}")
                remaining_messages = await fetch_messages_batch(
                    channel_username,
                    min_id=min_id,
                    max_id=new_max_id,
                    limit=limit - len(messages_data) if limit else None,
                    retry_count=retry_count + 1
                )
            else:
                # Going forward (new messages)
                new_min_id = max(msg['id'] for msg in messages_data)
                logger.info(f"[{channel_username}] Continuing forward from message ID {new_min_id}")
                remaining_messages = await fetch_messages_batch(
                    channel_username,
                    min_id=new_min_id,
                    max_id=max_id,
                    limit=limit - len(messages_data) if limit else None,
                    retry_count=retry_count + 1
                )

            # Merge and deduplicate
            all_messages = messages_data + remaining_messages
            unique_messages = {msg['id']: msg for msg in all_messages}
            return list(unique_messages.values())
        else:
            # No messages collected yet, just retry with same parameters
            return await fetch_messages_batch(
                channel_username,
                min_id=min_id,
                max_id=max_id,
                limit=limit,
                retry_count=retry_count + 1
            )

    except Exception as e:
        logger.error(f"[{channel_username}] Unexpected error occurred: {e}", exc_info=True)
        if messages_data:
            logger.info(f"[{channel_username}] Returning {len(messages_data)} partial messages collected before error")
            return messages_data
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

    # Detect gaps (deleted messages)
    logger.info(f"[{channel_username}] Running gap detection...")
    new_deleted_ids = detect_gaps(channel_path, index)

    if new_deleted_ids:
        # Ensure deleted_messages structure exists
        if 'deleted_messages' not in index:
            index['deleted_messages'] = {'ids': [], 'count': 0, 'last_check': None}

        # Add newly detected deleted IDs
        index['deleted_messages']['ids'].extend(new_deleted_ids)
        index['deleted_messages']['count'] = len(index['deleted_messages']['ids'])
        index['deleted_messages']['last_check'] = datetime.now().isoformat()

        logger.info(f"[{channel_username}] Detected {len(new_deleted_ids)} newly deleted messages")
        if len(new_deleted_ids) <= 10:
            logger.info(f"[{channel_username}] Deleted IDs: {new_deleted_ids}")
        else:
            logger.info(f"[{channel_username}] Deleted IDs sample: {new_deleted_ids[:10]}... (showing first 10)")
    else:
        logger.info(f"[{channel_username}] No new gaps detected")

        # Update last_check even if no new gaps found
        if 'deleted_messages' not in index:
            index['deleted_messages'] = {'ids': [], 'count': 0, 'last_check': None}
        index['deleted_messages']['last_check'] = datetime.now().isoformat()

    # Show total deleted messages statistics
    total_deleted = index['deleted_messages']['count']
    if total_deleted > 0:
        deleted_pct = (total_deleted / (index['total_posts_archived'] + total_deleted)) * 100
        logger.info(f"[{channel_username}] Total deleted messages: {total_deleted} ({deleted_pct:.2f}% of all posts)")

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