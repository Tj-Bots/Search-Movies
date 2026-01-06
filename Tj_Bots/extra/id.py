import os
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def get_target_user(client, message):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        try:
            user_input = message.command[1]
            if user_input.isdigit():
                return await client.get_users(int(user_input))
            return await client.get_users(user_input)
        except:
            return None
    return message.from_user

def get_media_file_id(message):
    media = message.media
    if not media: return None, None
    
    if media == enums.MessageMediaType.PHOTO:
        return "Photo", message.photo.file_id
    elif media == enums.MessageMediaType.VIDEO:
        return "Video", message.video.file_id
    elif media == enums.MessageMediaType.AUDIO:
        return "Audio", message.audio.file_id
    elif media == enums.MessageMediaType.DOCUMENT:
        return "Document", message.document.file_id
    elif media == enums.MessageMediaType.STICKER:
        return "Sticker", message.sticker.file_id
    elif media == enums.MessageMediaType.ANIMATION:
        return "Animation", message.animation.file_id
    elif media == enums.MessageMediaType.VOICE:
        return "Voice", message.voice.file_id
    return None, None

@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    
    if chat_type == enums.ChatType.PRIVATE:
        user_id = message.chat.id
        first = message.from_user.first_name
        last = message.from_user.last_name or ""
        username = f"@{message.from_user.username}" if message.from_user.username else "None"
        dc_id = message.from_user.dc_id or "Unknown"
        
        text = (
            f"<b>➲ First Name:</b> {first}\n"
            f"<b>➲ Last Name:</b> {last}\n"
            f"<b>➲ Username:</b> {username}\n"
            f"<b>➲ Telegram ID:</b> <code>{user_id}</code>\n"
            f"<b>➲ Data Centre:</b> <code>{dc_id}</code>"
        )
        await message.reply_text(text, quote=True)

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        text = f"<b>➲ Chat ID:</b> <code>{message.chat.id}</code>\n"
        
        if message.reply_to_message:
            r_user = message.reply_to_message.from_user
            user_id = r_user.id if r_user else "Anonymous"
            text += f"<b>➲ Replied User ID:</b> <code>{user_id}</code>\n"
            
            m_type, file_id = get_media_file_id(message.reply_to_message)
            if file_id:
                text += f"<b>➲ {m_type} ID:</b> <code>{file_id}</code>\n"
        else:
            user_id = message.from_user.id if message.from_user else "Anonymous"
            text += f"<b>➲ User ID:</b> <code>{user_id}</code>\n"
            
            m_type, file_id = get_media_file_id(message)
            if file_id:
                text += f"<b>➲ {m_type} ID:</b> <code>{file_id}</code>\n"

        await message.reply_text(text, quote=True)

@Client.on_message(filters.command(["info"]))
async def who_is(client, message):
    status_message = await message.reply_text("`Fetching user info...`", quote=True)
    
    from_user = await get_target_user(client, message)
    
    if from_user is None:
        return await status_message.edit("❌ No valid user found.")
    
    message_out_str = ""
    message_out_str += f"<b>➲ First Name:</b> {from_user.first_name}\n"
    message_out_str += f"<b>➲ Last Name:</b> {from_user.last_name or 'None'}\n"
    message_out_str += f"<b>➲ Telegram ID:</b> <code>{from_user.id}</code>\n"
    message_out_str += f"<b>➲ Data Centre:</b> <code>{from_user.dc_id or 'Unknown'}</code>\n"
    message_out_str += f"<b>➲ Username:</b> @{from_user.username or 'None'}\n"
    message_out_str += f"<b>➲ User Link:</b> <a href='tg://user?id={from_user.id}'><b>Click Here</b></a>\n"
    
    if message.chat.type in [enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
        try:
            member = await message.chat.get_member(from_user.id)
            if member.joined_date:
                joined_date = member.joined_date.strftime("%Y.%m.%d %H:%M:%S")
                message_out_str += f"<b>➲ Joined Chat:</b> <code>{joined_date}</code>\n"
        except:
            pass

    chat_photo = from_user.photo
    if chat_photo:
        try:
            local_user_photo = await client.download_media(message=chat_photo.big_file_id)
            await message.reply_photo(
                photo=local_user_photo,
                quote=True,
                caption=message_out_str,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔐 סגור', callback_data='closea')]])
            )
            os.remove(local_user_photo)
        except:
            await message.reply_text(
                text=message_out_str,
                quote=True,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔐 סגור', callback_data='closea')]])
            )
    else:
        await message.reply_text(
            text=message_out_str,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔐 סגור', callback_data='closea')]])
        )
    
    await status_message.delete()
