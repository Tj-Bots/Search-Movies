from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import ADMINS, PHOTO_URL

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_command(client, message):
    msg = await message.reply("אוסף נתונים...", quote=True)
    
    users_count = await db.users.count_documents({})
    files_count = await db.files.count_documents({})
    groups_count = await db.groups.count_documents({})
    
    text = (
        "**📊 <u>סטטיסטיקות הבוט:</u> 📊**\n\n"
        f" 📂 **מספר קבצים:** `{files_count}`\n"
        f" 👤 **מספר משתמשים:** `{users_count}`\n"
        f" 👥 **מספר קבוצות:** `{groups_count}`"
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
