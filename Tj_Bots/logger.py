from pyrogram import Client, enums
from config import LOG_CHANNEL
from database import db

@Client.on_message(group=-1)
async def global_logger(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        if not message.from_user: return
        
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "Unknown"
        
        is_new = await db.add_user(user_id, first_name)
        
        if is_new:
            try:
                log_text = (
                    "<b>╔════❰ <i>#NewUser</i> ❱════❍</b>\n"
                    "<b>║╭━━━━━━━━━━━━━━━➣</b>\n"
                    f"<b>║┣⪼ 🪪 ID:</b> <code>{user_id}</code>\n"
                    f"<b>║┣⪼ 🏷️ Name:</b> <a href='tg://user?id={user_id}'>{first_name}</a>\n"
                    f"<b>║┣⪼ 📌 Action:</b> Sent a message\n"
                    "<b>║╰━━━━━━━━━━━━━━━➣</b>\n"
                    "<b>╚═════════════════❍</b>"
 
                )
                await client.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
            except: pass

    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_new_group = await db.add_group(message.chat.id, message.chat.title)
        
        if is_new_group:
            chat = message.chat
            try:
                count = await client.get_chat_members_count(chat.id)
            except:
                count = "Unknown"

            group_link = chat.title
            try:
                invite_link = await chat.export_invite_link()
                if invite_link:
                    group_link = f"<a href='{invite_link}'>{chat.title}</a>"
            except:
                pass
            
            adder = message.from_user
            adder_name = adder.first_name if adder else "Unknown"
            adder_id = adder.id if adder else 0

            try:
                log_text = (
                    "<b>╔════❰ <i>#NewGroup</i> ❱════❍</b>\n"
                    "<b>║╭━━━━━━━━━━━━━━━➣</b>\n"
                    f"<b>║┣⪼ 💬 Group:</b> {group_link} (<code>{chat.id}</code>)\n"
                    f"<b>║┣⪼ 👥 Members:</b> <code>{count}</code>\n"
                    f"<b>║┣⪼ 📌 Active User:</b> <a href='tg://user?id={adder_id}'>{adder_name}</a>\n"
                    "<b>║╰━━━━━━━━━━━━━━━➣</b>\n"
                    "<b>╚═════════════════❍</b>"
                )
                await client.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                print(f"Error sending group log: {e}")
