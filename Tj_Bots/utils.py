import re
from config import ADMINS

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def clean_filename(name):
    name = re.sub(r'\b(.mkv|.mp4|.avi)\b', '', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip()

def mandatory_channel_url(entry):
    if entry.get('kind') == 'private':
        return entry.get('invite_link') or ''
    return f"https://t.me/{entry.get('id')}"


async def get_missing_mandatory(client, user_id):
    from database import db
    channels = await db.get_mandatory_channels()
    missing = []
    for entry in channels:
        try:
            await client.get_chat_member(entry['id'], user_id)
        except Exception:
            missing.append(entry)
    return missing


def mandatory_join_markup(missing, retry_callback_data):
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for entry in missing:
        kind_label = 'קבוצה' if entry.get('type') == 'group' else 'ערוץ'
        rows.append([InlineKeyboardButton(f"📣 הצטרף ל{kind_label}: {entry.get('title', '?')}", url=mandatory_channel_url(entry))])
    rows.append([InlineKeyboardButton('↻ נסה שוב', callback_data=retry_callback_data)])
    return InlineKeyboardMarkup(rows)


async def is_admin(client, chat_id, user_id):
    if user_id in ADMINS: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status.name in ["OWNER", "ADMINISTRATOR"]
    except:
        return False
