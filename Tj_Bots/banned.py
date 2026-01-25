from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import ADMINS, REQUEST_GROUP

SUPPORT_LINK = REQUEST_GROUP

@Client.on_message(group=-10)
async def ban_enforcer(client, message):
    if not message.from_user: return
    
    if message.from_user.id not in ADMINS:
        ban_info = await db.get_ban_status(message.from_user.id)
        if ban_info:
            if message.chat.type == enums.ChatType.PRIVATE:
                await message.reply(
                    f"🚫 **אתה חסום מהשימוש בבוט.**\nסיבה: `{ban_info.get('reason')}`\n\nלבירורים פנה לתמיכה.",
                    quote=True,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ תמיכה", url=SUPPORT_LINK)]])
                )
            message.stop_propagation()
            return

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        chat_ban_info = await db.get_chat_ban_status(message.chat.id)
        if chat_ban_info:
            try:
                await message.reply(
                    f"🚫 **קבוצה זו נחסמה לשימוש.**\nסיבה: `{chat_ban_info.get('reason')}`\n\nהבוט יוצא מהקבוצה כעת.",
                    quote=True,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ תמיכה", url=SUPPORT_LINK)]])
                )
                await client.leave_chat(message.chat.id)
            except: pass
            message.stop_propagation()

@Client.on_message(filters.command("ban") & filters.user(ADMINS))
async def ban_user_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("שימוש: `/ban [ID] [סיבה]`", quote=True)
    
    try:
        user_id = int(message.command[1])
        reason = " ".join(message.command[2:]) or "הפרת חוקים"
        
        await db.ban_user(user_id, reason)
        await message.reply(f"🚫 המשתמש `{user_id}` נחסם.\nסיבה: `{reason}`", quote=True)
    except Exception as e:
        await message.reply(f"שגיאה: {e}", quote=True)

@Client.on_message(filters.command("unban") & filters.user(ADMINS))
async def unban_user_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("שימוש: `/unban [ID]`", quote=True)
    
    try:
        user_id = int(message.command[1])
        await db.unban_user(user_id)
        await message.reply(f"✅ המשתמש `{user_id}` שוחרר מהחסימה.", quote=True)
    except:
        await message.reply("שגיאה בביצוע הפקודה.", quote=True)

@Client.on_message(filters.command("ban_chat") & filters.user(ADMINS))
async def ban_chat_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("שימוש: `/ban_chat [ID] [סיבה]`", quote=True)
    
    try:
        chat_id = int(message.command[1])
        reason = " ".join(message.command[2:]) or "הפרת חוקים"
        
        await db.ban_chat(chat_id, reason)
        await message.reply(f"🚫 הקבוצה `{chat_id}` נחסמה.\nסיבה: `{reason}`", quote=True)
        
        try:
            await client.send_message(chat_id, f"🚫 **קבוצה זו נחסמה.**\nסיבה: {reason}\nביי!")
            await client.leave_chat(chat_id)
        except: pass
        
    except Exception as e:
        await message.reply(f"שגיאה: {e}", quote=True)

@Client.on_message(filters.command("unban_chat") & filters.user(ADMINS))
async def unban_chat_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("שימוש: `/unban_chat [ID]`", quote=True)
    
    try:
        chat_id = int(message.command[1])
        await db.unban_chat(chat_id)
        await message.reply(f"✅ הקבוצה `{chat_id}` שוחררה מהחסימה.", quote=True)
    except:
        await message.reply("שגיאה.", quote=True)

@Client.on_message(filters.command("leave") & filters.user(ADMINS))
async def leave_chat_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("שימוש: `/leave [ID]`", quote=True)
    
    try:
        chat_id = int(message.command[1])
        await client.send_message(chat_id, "👋 **מנהל הבוט הורה לי לעזוב את הקבוצה. להתראות!**")
        await client.leave_chat(chat_id)
        await message.reply(f"✅ עזבתי את הקבוצה `{chat_id}`.", quote=True)
    except Exception as e:
        await message.reply(f"שגיאה: {e}", quote=True)
