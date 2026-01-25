from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import ADMINS, PHOTO_URL

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_command(client, message):
    msg = await message.reply("⏳ **אוסף נתונים...**", quote=True)
    
    def get_size(bytes, suffix="B"):
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bytes < factor:
                return f"{bytes:.2f}{unit}{suffix}"
            bytes /= factor

    MAX_DB_SIZE = 536870912

    users_count = await db.users.count_documents({})
    files_count = await db.files.count_documents({})
    groups_count = await db.groups.count_documents({})
    
    try:
        db_stats = await db.users.database.command("dbstats")
        used_bytes = db_stats['storageSize']
        used_size = get_size(used_bytes)
        max_size = get_size(MAX_DB_SIZE)
        
        percentage = (used_bytes / MAX_DB_SIZE) * 100
        
        bar_len = 10
        filled_len = int(bar_len * percentage / 100)
        bar = '▓' * filled_len + '░' * (bar_len - filled_len)
        
        db_info = (
            f"🗄 <u>**אחסון דאטה בייס:**</u>\n"
            f"**★ בשימוש:** `{used_size}`\n"
            f"**★ מתוך:** `{max_size}`\n"
            f"★ **סטטוס:** [{bar}] `{percentage:.2f}%`"
        )
    except Exception as e:
        db_info = f"❌ לא ניתן לשלוף נתונים טכניים.\n`{e}`"

    text = (
        f"📊 <u>**סטטיסטיקות הבוט:**</u>\n\n"
        f"★ <u>**סטטוס בוט:**</u>\n"
        f"★ **קבצים:** `{files_count}`\n"
        f"★ **משתמשים:** `{users_count}`\n"
        f"★ **קבוצות:** `{groups_count}`\n\n"
        f"{db_info}"
    )
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✘ סגור", callback_data="closea")]
    ])
    
    await msg.delete()
    await message.reply_photo(
        PHOTO_URL, 
        caption=text, 
        reply_markup=btn,
        quote=True
    )
    
