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

def resolve_update_channel(cfg):
    """update_channel config can be a plain username string (legacy/public channel)
    or a {'kind': 'private'/'public', ...} dict (private channels have no username,
    so they need a stored invite link instead of a t.me/<username> URL)."""
    if isinstance(cfg, dict):
        if cfg.get('kind') == 'private':
            return cfg.get('id'), cfg.get('invite_link') or ''
        value = cfg.get('value', '')
        return value, f"https://t.me/{value}"
    return cfg, f"https://t.me/{cfg}"


async def is_admin(client, chat_id, user_id):
    if user_id in ADMINS: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status.name in ["OWNER", "ADMINISTRATOR"]
    except:
        return False
