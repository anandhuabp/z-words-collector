import os
import json
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TARGET_CHANNELS = os.getenv('TARGET_CHANNELS').split(',')

SESSION_PATH = Path('session/my_telegram_session.session')
DATA_PATH = Path('data')

SESSION_PATH.parent.mkdir(exist_ok=True)
DATA_PATH.mkdir(exist_ok=True)

client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

async def fetch_channel(channel_username):
    print(f"[{channel_username}] Начинаем работу...")
    channel_path = DATA_PATH / channel_username
    channel_path.mkdir(exist_ok=True)

    last_known_id = 0
    existing_files = sorted(list(channel_path.glob('*.json')), reverse=True)
    if existing_files:
        latest_file = existing_files[0]
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                latest_data = json.load(f)
                if latest_data:
                    last_known_id = max(msg['id'] for msg in latest_data)
                    print(f"[{channel_username}] Последнее известное ID: {last_known_id}. Ищем новые сообщения.")
        except (json.JSONDecodeError, IndexError):
            print(f"[{channel_username}] Файл {latest_file} пуст или поврежден. Скачиваем заново.")
            last_known_id = 0
    
    if last_known_id == 0:
        print(f"[{channel_username}] Данные не найдены. Запускаем полную загрузку.")

    new_messages_data = []
    async for message in client.iter_messages(channel_username, min_id=last_known_id):
        if not message or (message.text is None and message.media is None):
            continue

        message_data = {
            'id': message.id,
            'date': message.date.isoformat(),
            'text': message.text,
            'views': message.views,
            'forwards': message.forwards,
            'reactions': [
                {'emoji': r.reaction.emoticon, 'count': r.count}
                for r in message.reactions.results
            ] if message.reactions else []
        }
        new_messages_data.append(message_data)

    if not new_messages_data:
        print(f"[{channel_username}] Новых сообщений не найдено.")
        return

    new_messages_data.reverse() 
    
    today_str = date.today().isoformat()
    output_filename = channel_path / f"{today_str}.json"
    
    existing_today_data = []
    if output_filename.exists():
        with open(output_filename, 'r', encoding='utf-8') as f:
            try:
                existing_today_data = json.load(f)
            except json.JSONDecodeError:
                pass

    all_today_data = existing_today_data + new_messages_data

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_today_data, f, ensure_ascii=False, indent=2)

    print(f"[{channel_username}] Сохранено {len(new_messages_data)} новых сообщений в {output_filename}")

async def main():
    await client.start(phone=PHONE_NUMBER)
    for channel in TARGET_CHANNELS:
        await fetch_channel(channel.strip())

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())