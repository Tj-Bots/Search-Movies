import re
from pyrogram import enums
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


async def is_chat_member(client, chat_id, user_id):
    """get_chat_member doesn't always raise for someone who isn't a member (e.g.
    channels can return a LEFT/BANNED member object instead of erroring), so the
    status has to be checked explicitly rather than relying on the call succeeding."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    return member.status not in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED)


async def get_missing_mandatory(client, user_id):
    from database import db
    channels = await db.get_mandatory_channels()
    missing = []
    for entry in channels:
        if not await is_chat_member(client, entry['id'], user_id):
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
