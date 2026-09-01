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

        # Referral bonus is granted here (not in start.py) because this handler runs in
        # group=-1, before start.py's group=0 handler even sees the update - by then
        # add_user() above has already made this user look "existing" to any later check.
        if is_new and message.text and message.text.startswith("/start"):
            parts = message.text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].startswith("r_"):
                try:
                    referrer_id = int(parts[1][len("r_"):])
                    if referrer_id != user_id:
                        await db.set_referred_by(user_id, referrer_id)
                        try:
                            ref_count = await db.get_referral_count(referrer_id)
                            ratio = await db.get_config('referral_ratio', 3)
                            remaining = (ratio - (ref_count % ratio)) if ratio > 0 else 0
                            hint = "🎁 קיבלת קובץ חינמי קבוע נוסף ליום!" if remaining == ratio else f"⏳ עוד {remaining} הזמנות לבונוס הבא."
                            await client.send_message(
                                referrer_id,
                                f"🎉 <b>משתמש חדש הצטרף דרך קישור ההזמנה שלך!</b> (סה'כ: {ref_count})\n{hint}"
                            )
                        except Exception:
                            pass
                except ValueError:
                    pass

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
