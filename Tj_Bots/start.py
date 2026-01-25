import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from config import UPDATE_CHANNEL, REQUEST_GROUP, PHOTO_URL, ADMINS, LOG_CHANNEL
from database import db

@Client.on_message(filters.command("start"))
async def start_command(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        user_id = message.from_user.id
        
        if len(message.command) > 1:
            file_db_id = message.command[1]
            try:
                await client.get_chat_member(UPDATE_CHANNEL, user_id)
            except:
                btn = [[InlineKeyboardButton('📣 להרשמה לערוץ', url=f'https://t.me/{UPDATE_CHANNEL}')],
                       [InlineKeyboardButton('↻ נסה שוב', url=f"https://t.me/{client.me.username}?start={file_db_id}")]]
                return await message.reply_text(
                    "**כדי להשתמש בבוט הזה עליך להיות מנוי לערוץ העדכונים שלו!🫰**",
                    reply_markup=InlineKeyboardMarkup(btn),
                    quote=True
                )

            file_data = await db.get_file(file_db_id)
            if file_data:
                try:
                    await client.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=file_data['chat_id'],
                        message_id=file_data['message_id'],
                        caption=None
                    )
                except:
                    await message.reply("❌ הקובץ נמחק מהמקור או שאין לי גישה אליו.", quote=True)
            return

        anim_msg = await message.reply_text("👋", quote=True)
        await asyncio.sleep(0.5)
        
        await anim_msg.edit_text("👀")
        await asyncio.sleep(1.0)
        
        await anim_msg.edit_text("⚡")
        await asyncio.sleep(1.5)
        
        await send_home_message(client, message)
        await anim_msg.delete()

    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply("היי! אני מוכן לחיפוש סרטים 🎬", quote=True)

@Client.on_message(filters.new_chat_members)
async def added_to_group(client, message):
    for member in message.new_chat_members:
        if member.id == client.me.id:
            await message.reply("תודה שהוספתם אותי! 🎬\nשלחו את שם הסרט/סדרה שתרצו לחפש.", quote=True)

async def send_home_message(client, message, user=None, is_edit=False):
    if not user:
        user = message.from_user
    
    user_mention = user.mention
    bot_name = client.me.first_name
    bot_username = client.me.username
    
    bot_mention = f"[{bot_name}](https://t.me/{bot_username})"
    
    buttons = [
        [InlineKeyboardButton('✇ קבוצת בקשות ✇', url=REQUEST_GROUP), 
         InlineKeyboardButton('✇ ערוץ עדכונים ✇', url=f'https://t.me/{UPDATE_CHANNEL}')],
        [InlineKeyboardButton('〄 עזרה 〄', callback_data='help'), 
         InlineKeyboardButton('⍟ אודות ⍟', callback_data='about')],
        [InlineKeyboardButton('⇋ להוספה לקבוצה ⇋', url=f"http://t.me/{client.me.username}?startgroup&admin=delete_messages")]
    ]
    
    txt = (f"**היי {user_mention} 👋**\n"
            f"**ברוך הבא ל- {bot_mention}** 😎\n\n"
           "**אני מנוע חיפוש סרטים וסדרות חדשני,**"
           "\n**התפקיד שלי זה לחפש סרטים בקבוצות,**"
           "\n**הוסיפו אותי לקבוצה שלכם ואני אמשיך מכאן.**")
    
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_photo(PHOTO_URL, caption=txt, reply_markup=InlineKeyboardMarkup(buttons), quote=True)

@Client.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "help_admin" and user_id not in ADMINS:
        return await query.answer("⛔ למנהלים בלבד.", show_alert=True)
    
    if data not in ["closea", "noop", "help_stats"]:
        try:
            await query.message.edit_media(
                InputMediaPhoto(PHOTO_URL, caption=""),
                reply_markup=None 
            )
            await asyncio.sleep(0.2)
        except:
            pass
    
    if data == "home":
        await send_home_message(client, query.message, user=query.from_user, is_edit=True)
    
    elif data == "help":
        user_mention = query.from_user.mention
        
        btns = [
            [InlineKeyboardButton('הגדרות קבוצה', callback_data='help_settings'), InlineKeyboardButton('זכויות יוצרים', callback_data='help_copyright')],
            [InlineKeyboardButton('תוספות (Extra)', callback_data='help_extra'), InlineKeyboardButton('מדריך שימוש', callback_data='help_guide')],
            [InlineKeyboardButton('⏎ חזרה', callback_data='home'),             InlineKeyboardButton('סטטיסטיקות', callback_data='help_stats')],
        ]
        
        if user_id in ADMINS:
             btns.insert(0, [InlineKeyboardButton('👮‍♂️ פקודות מנהל 👮‍♂️', callback_data='help_admin')])

        await query.message.edit_media(
            InputMediaPhoto(PHOTO_URL, caption=f"<b>היי {user_mention},\nכאן תוכל לקבל עזרה עבור כל הפקודות שלי.</b>"), 
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "help_extra":
        txt = (
            "<b><u>פקודות נוספות (Extra Tools):</u></b>\n\n"
            "<b>◉ פונט טקסט:</b>\n"
            "• <code>/font</code> [טקסט] - הופך טקסט באנגלית לפונטים מיוחדים.\n\n"
            "<b>◉ שיתוף טקסט:</b>\n"
            "• <code>/share</code> [טקסט] - יוצר קישור שיתוף מהיר לטקסט שכתבתם.\n\n"
            "<b>◉ תמלול הודעות (TTS):</b>\n"
            "• <code>/tts</code> - הגיבו על הודעת טקסט, והבוט ישלח לכם אותה בהודעה קולית.\n\n"
            "<b>◉ העלאת טקסט (Paste):</b>\n"
            "• <code>/paste</code> - הגיבו על טקסט או קובץ כדי להעלות אותו ל-Pastebin ולקבל קישור.\n\n"
            "<b>◉ פרטים על משתמש:</b>\n"
            "• <code>/id</code> - מזהה משתמש/מזהה צ'אט.\n"
            "• <code>/info</code> - מידע על חשבון של משתמש, פרופיל, שם, יוזר וכו'...\n\n"
            "<b>◉ מזהה סטיקר</b>\n"
            "• <code>/stickerid</code> - מביא את הid של הסטיקר שהגיבו עליו\n\n"
            "<b>◉ כלי מערכת:</b>\n"
            "• <code>/json</code> - קבלת המידע הטכני (JSON) של ההודעה.\n"
            "• <code>/written</code> [שם קובץ] - הופך את הטקסט לקובץ להורדה."
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏎ חזרה', callback_data='help')]]))

    elif data == "help_admin":
        txt = (
            "<b><u>לוח בקרה למנהלים:</u></b>\n\n"
            "<b>◉ ניהול תוכן:</b>\n"
            "• <code>/index</code> [link] - [start] - הוספת קבצים מערוץ (לפי טווח).\n"
            "• <code>/newindex</code> [ID] - מעקב אחרי תוכן חדש בערוץ.\n"
            "• <code>/channels</code> - ניהול ערוצים במעקב.\n\n"
            "<b>◉ משתמשים וקבוצות:</b>\n"
            "• <code>/ban</code> [ID] - חסימת משתמש.\n"
            "• <code>/unban</code> [ID] - שחרור משתמש.\n"
            "• <code>/ban_chat</code> [ID] - חסימת קבוצה.\n"
            "• <code>/unban_chat</code> [ID] - שחרור קבוצה.\n"
            "• <code>/leave</code> [ID] - יציאה מקבוצה (ללא חסימה).\n\n"
            "<b>◉ מערכת:</b>\n"
            "• <code>/clean</code> - אשף ניקוי נתונים.\n"
            "• <code>/broadcast</code> [-f] - שידור למנויים.\n"
            "• <code>/broadcast_groups</code> - שידור לקבוצות.\n"
            "• <code>/restart</code> - הפעלה מחדש."
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏎ חזרה', callback_data='help')]]))

    elif data == "help_guide":
        txt = (
    "⚙️ <b><u>מדריך לחיפוש ברובוט החיפוש</u></b> ⚙️\n\n"
    "<i>כדי לבקש סרט או סדרה, יש לשים לב לדרך בה אתם מבקשים.\n"
    "חשוב לכתוב את השם המדויק של הסרט או הסדרה שברצונכם למצוא.</i>\n\n"
    "<b><i><u>דוגמאות לחיפוש נכון ✔️</u></i></b>\n"
    "אשמתי\n"
    "מהיר ועצבני\n\n"
    "<b><i><u>דוגמאות לא נכונות ❌</u></i></b>\n"
    "יש הארי פוטר?\n"
    "אפשר הארי פוטר\n"
    "יש את הסרט הארי פוטר?\n\n"
    "<b>הבנתם? מעולה!\n"
    "נסו עכשיו בקבוצה!</b>"
)
        btn = [[InlineKeyboardButton('• למעבר לקבוצה •', url=REQUEST_GROUP)], [InlineKeyboardButton('⏎ חזרה', callback_data='help')]]
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(btn))

    elif data == "help_copyright":
        txt = "<b>© זכויות יוצרים</b>\n\nהקבצים בבוט נאספים מטלגרם באופן אוטומטי. איננו מעלים תוכן בעצמנו."
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏎ חזרה', callback_data='help')]]))
    
    elif data == "help_settings":
        txt = "<b>⚙️ הגדרות קבוצה</b>\n\nשלחו <code>/settings</code> בקבוצה כדי להגדיר:\n• מצב תצוגה (כפתורים/טקסט)\n• טריגר חיפוש (!)\n• כמות תוצאות"
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏎ חזרה', callback_data='help')]]))

    elif data == "help_stats":
        try:
            await query.message.edit_caption("⏳ **מנתח נתונים...**")
        except:
            pass

        def get_size(bytes, suffix="B"):
            factor = 1024
            for unit in ["", "K", "M", "G", "T", "P"]:
                if bytes < factor:
                    return f"{bytes:.2f}{unit}{suffix}"
                bytes /= factor

        MAX_DB_SIZE = 536870912

        users = await db.users.count_documents({})
        files = await db.files.count_documents({})
        groups = await db.groups.count_documents({})

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

        txt = (
            f"📊 <u>**סטטיסטיקות הבוט:**</u>\n\n"
            f"🤖 <u>**סטטוס בוט:**</u>\n"
            f"★ **קבצים:** `{files}`\n"
            f"★ **משתמשים:** `{users}`\n"
            f"★ **קבוצות:** `{groups}`\n\n"
            f"{db_info}"
        )
        
        await query.message.edit_media(
            InputMediaPhoto(PHOTO_URL, caption=txt), 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('⏎ חזרה', callback_data='help'),
                 InlineKeyboardButton('↻ רענן', callback_data='help_stats')]
            ])
        )


    elif data == "about":
        bot_username = client.me.username
        txt = (
            "<b>╔════❰ 𝗔𝗯𝗼𝘂𝘁 𝗧𝗵𝗲 𝗕𝗼𝘁 ❱═❍⊱❁۪۪</b>\n"
            "<b>║╭━━━━━━━━━━━━━━━➣</b>\n"
            f"<b>║┣⪼ 🤖 ʙᴏᴛ : <a href='https://t.me/{bot_username}'>Movie Search</a></b>\n"
            "<b>║┣⪼ 👦 ᴄʀᴇᴀᴛᴏʀ : @BOSS1480</b>\n"
            f"<b>║┣⪼ 🤖 ᴜᴘᴅᴀᴛᴇ : <a href='https://t.me/{UPDATE_CHANNEL}'>Update Channel</a></b>\n"
            "<b>║┣⪼ 🗣️ ʟᴀɴɢᴜᴀɢᴇ : [Python](https://www.python.org/)</b>\n"
            "<b>║┣⪼ 📚 Lɪʙʀᴀʀʏ : [Pyrogram](https://docs.pyrogram.org/)</b>\n"
            "<b>║╰━━━━━━━━━━━━━━━➣</b>\n"
            "<b>╚══════════════════❍⊱❁۪۪</b>"
        )
        btn = [
            [InlineKeyboardButton('≈ 𝚜𝚘𝚞𝚛𝚌𝚎 𝚌𝚘𝚍𝚎 ≈', url='https://t.me/TJSourceCode')], 
            [InlineKeyboardButton('⏎ חזרה', callback_data='home'), InlineKeyboardButton('✘ סגור', callback_data='closea')]
        ]
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(btn))
    elif data == "closea":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            pass
    elif data == "noop":
        await query.answer()
