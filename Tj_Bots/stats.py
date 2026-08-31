from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import PHOTO_URL


def _get_size(size, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if size < factor:
            return f"{size:.2f}{unit}{suffix}"
        size /= factor


async def build_stats_text():
    MAX_DB_SIZE = 536870912

    users_count = await db.users.count_documents({})
    files_count = await db.files.count_documents({})
    groups_count = await db.groups.count_documents({})

    try:
        db_stats = await db.users.database.command("dbstats")
        used_bytes = db_stats['storageSize']
        used_size = _get_size(used_bytes)
        max_size = _get_size(MAX_DB_SIZE)

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

    return (
        f"📊 <u>**סטטיסטיקות הבוט:**</u>\n\n"
        f"🤖 <u>**סטטוס בוט:**</u>\n"
        f"★ **קבצים:** `{files_count}`\n"
        f"★ **משתמשים:** `{users_count}`\n"
        f"★ **קבוצות:** `{groups_count}`\n\n"
        f"{db_info}"
    )


@Client.on_message(filters.command("stats"))
async def stats_command(client, message):
    msg = await message.reply("<tg-emoji emoji-id='5451646226975955576'>⌛️</tg-emoji> **מעבד נתונים...**", quote=True)

    text = await build_stats_text()

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✘ סגור", callback_data="closea", style=enums.ButtonStyle.DANGER)]
    ])

    await msg.delete()
    await message.reply_photo(
        PHOTO_URL,
        caption=text,
        reply_markup=btn,
        quote=True
    )
