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

async def is_admin(client, chat_id, user_id):
    if user_id in ADMINS: return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status.name in ["OWNER", "ADMINISTRATOR"]
    except:
        return False
