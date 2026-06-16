
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from config import UPDATE_CHANNEL, REQUEST_GROUP, PHOTO_URL, ADMINS, LOG_CHANNEL, AUTH_CHANNEL_FORCE
from database import db
from .utils import get_readable_size

async def send_file_with_fallback(client, chat_id, file_data, reply_to_id=None):
    try:
        await client.copy_message(
            chat_id=chat_id,
            from_chat_id=file_data['chat_id'],
            message_id=file_data['message_id'],
            caption=None,
            reply_to_message_id=reply_to_id
        )
        return True
    except:
        file_id = file_data.get('file_id')
        if not file_id:
            return False
            
        file_name = file_data.get('file_name', '')
        file_size = get_readable_size(file_data.get('file_size', 0))
        fallback_caption = f"**{file_name}**\n\n**💾 גודל: {file_size}**"
        
        try:
            await client.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=fallback_caption,
                reply_to_message_id=reply_to_id
            )
            return True
        except:
            try:
                await client.send_document(
                    chat_id=chat_id,
                    document=file_id,
                    caption=fallback_caption,
                    reply_to_message_id=reply_to_id
                )
                return True
            except:
                return False

@Client.on_message(filters.command("start"))
async def start_command(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        user_id = message.from_user.id
        
        if len(message.command) > 1:
            file_db_id = message.command[1]
            
            should_check = AUTH_CHANNEL_FORCE
            is_subbed = True
            
            if should_check:
                try:
                    await client.get_chat_member(UPDATE_CHANNEL, user_id)
                except:
                    is_subbed = False

            if not is_subbed:
                btn = [[InlineKeyboardButton('📣 להרשמה לערוץ', url=f'https://t.me/{UPDATE_CHANNEL}')],
                       [InlineKeyboardButton('↻ נסה שוב', callback_data=f"checksub_{file_db_id}")]]
                
                return await message.reply_text(
                    "**כדי להשתמש בבוט הזה עליך להיות מנוי לערוץ העדכונים שלו!🫰**",
                    reply_markup=InlineKeyboardMarkup(btn),
                    quote=True
                )

            file_data = await db.get_file(file_db_id)
            if file_data:
                success = await send_file_with_fallback(client, message.chat.id, file_data, message.id)
                if not success:
                    await message.reply("❌ הקובץ נמחק מהמקור או שאין לי גישה אליו.", quote=True)
            return

        bot_name = client.me.first_name
        bot_username = client.me.username
        bot_mention = f"[{bot_name}](https://t.me/{bot_username})"

        anim_msg = await message.reply_text(
             f"<blockquote>**__היי <tg-emoji emoji-id='5195448447062251797'>👋</tg-emoji>__**\n**__ברוכים הבאים ל- {bot_mention} <tg-emoji emoji-id='5325559344513691205'>😎</tg-emoji>__**</blockquote>", 
             quote=True
        )        
        await asyncio.sleep(1.0)
        
        await anim_msg.edit_text("<tg-emoji emoji-id='5456140674028019486'>⚡️</tg-emoji>")
        await asyncio.sleep(0.8)

        await anim_msg.edit_text("**__מתחיל בוט...__** <tg-emoji emoji-id='5929303842205207391'>😈</tg-emoji>")
        await asyncio.sleep(0.7)
        
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
        [InlineKeyboardButton("🔍 חיפוש באינליין 🔎", switch_inline_query_current_chat="", style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('✇ קבוצת בקשות ✇', url=REQUEST_GROUP, style=enums.ButtonStyle.SUCCESS), 
         InlineKeyboardButton('✇ ערוץ עדכונים ✇', url=f'https://t.me/{UPDATE_CHANNEL}', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('〄 עזרה 〄', callback_data='help', style=enums.ButtonStyle.PRIMARY), 
         InlineKeyboardButton('⍟ אודות ⍟', callback_data='about', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('⇋ להוספה לקבוצה ⇋', url=f"http://t.me/{client.me.username}?startgroup&admin=delete_messages", style=enums.ButtonStyle.SUCCESS)]
    ]
    
    txt = (f"**היי {user_mention} <tg-emoji emoji-id='5195448447062251797'>👋</tg-emoji>**\n"
            f"**ברוכים הבאים ל- {bot_mention}** <tg-emoji emoji-id='5325559344513691205'>😎</tg-emoji>\n\n"
           "**אני מנוע חיפוש סרטים וסדרות חדשני,**"
           "\n<b>התפקיד שלי זה לחפש סרטים בקבוצות,"
           "\nהוסיפו אותי לקבוצה שלכם ואני אמשיך מכאן.</b><tg-emoji emoji-id='5224607267797606837'>☄️</tg-emoji>\n\n"
           "<blockquote>**👨🏼‍💻מתכנת ראשי: @BOSS1480**</blockquote>")
    
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_photo(PHOTO_URL, caption=txt, reply_markup=InlineKeyboardMarkup(buttons), quote=True)

@Client.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data.startswith("checksub_"):
        file_db_id = data.split("_")[1]
        
        should_check = AUTH_CHANNEL_FORCE
        is_subbed = True
        
        if should_check:
            try:
                await client.get_chat_member(UPDATE_CHANNEL, user_id)
            except:
                is_subbed = False

        if not is_subbed:
            return await query.answer("❌ עדיין לא נרשמת לערוץ! עליך להירשם כדי לקבל את הקובץ.", show_alert=True)
        
        file_data = await db.get_file(file_db_id)
        if file_data:
            reply_to = query.message.reply_to_message.id if query.message.reply_to_message else None
            success = await send_file_with_fallback(client, query.message.chat.id, file_data, reply_to)
            if success:
                await query.message.delete()
            else:
                await query.answer("❌ הקובץ נמחק מהמקור או שאין לי גישה אליו.", show_alert=True)
        else:
            await query.answer("❌ הקובץ לא נמצא במסד הנתונים.", show_alert=True)
        return

    if data == "help_admin" and user_id not in ADMINS:
        return await query.answer("⛔ למנהלים בלבד.", show_alert=True)
    
    if data not in ["closea", "noop", "help_stats"]:
        try:
            await query.message.edit_media(
                InputMediaPhoto(PHOTO_URL, caption=""),
                reply_markup=None 
            )
            await asyncio.sleep(0.1)
        except:
            pass
    
    if data == "home":
        await send_home_message(client, query.message, user=query.from_user, is_edit=True)
    
    elif data == "help":
        user_mention = query.from_user.mention
        
        btns = [
            [InlineKeyboardButton('הגדרות קבוצה', callback_data='help_settings', style=enums.ButtonStyle.SUCCESS), InlineKeyboardButton('זכויות יוצרים', callback_data='help_copyright', style=enums.ButtonStyle.SUCCESS)],
            [InlineKeyboardButton('תוספות (Extra)', callback_data='help_extra', style=enums.ButtonStyle.SUCCESS), InlineKeyboardButton('מדריך שימוש', callback_data='help_guide', style=enums.ButtonStyle.SUCCESS)],
            [InlineKeyboardButton('הורדה מטיקטוק', callback_data='help_d', style=enums.ButtonStyle.SUCCESS),           InlineKeyboardButton('סטטיסטיקות', callback_data='help_stats', style=enums.ButtonStyle.SUCCESS)],
            [InlineKeyboardButton('🆕 העלאת תמונה', callback_data='help_telegraph', style=enums.ButtonStyle.PRIMARY),           InlineKeyboardButton('🆕 כלים לוידאו', callback_data='help_exthumb', style=enums.ButtonStyle.PRIMARY)],
            [InlineKeyboardButton('🏠 בית 🏠', callback_data='home', style=enums.ButtonStyle.DANGER)],          
        ]
        
        if user_id in ADMINS:
             btns.insert(0, [InlineKeyboardButton('👮‍♂️ פקודות מנהל 👮‍♂️', callback_data='help_admin', style=enums.ButtonStyle.DANGER)])

        await query.message.edit_media(
            InputMediaPhoto(PHOTO_URL, caption=f"<b>היי {user_mention},\nכאן תוכל לקבל עזרה עבור כל הפקודות שלי.</b>"), 
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "help_extra":
        txt = (
            "<b><u>פקודות נוספות (Extra Tools):</u></b>\n\n"
            "<b>◉ פונט טקסט:</b>\n"
            "<blockquote>• <code>/font</code> [טקסט] - הופך טקסט באנגלית לפונטים מיוחדים.</blockquote>\n\n"
            "<b>◉ שיתוף טקסט:</b>\n"
            "<blockquote>• <code>/share</code> [טקסט] - יוצר קישור שיתוף מהיר לטקסט שכתבתם.</blockquote>\n\n"
            "<b>◉ תמלול הודעות (TTS):</b>\n"
            "<blockquote>• <code>/tts</code> - הגיבו על הודעת טקסט, והבוט ישלח לכם אותה בהודעה קולית.</blockquote>\n\n"
            "<b>◉ העלאת טקסט (Paste):</b>\n"
            "<blockquote>• <code>/paste</code> - הגיבו על טקסט או קובץ כדי להעלות אותו ל-Pastebin ולקבל קישור.</blockquote>\n\n"
            "<b>◉ פרטים על משתמש:</b>\n"
            "<blockquote>• <code>/id</code> - מזהה משתמש/מזהה צ'אט.</blockquote>\n"
            "<blockquote>• <code>/info</code> - מידע על חשבון של משתמש, פרופיל, שם, יוזר וכו'...</blockquote>\n\n"
            "<b>◉ מזהה סטיקר</b>\n"
            "<blockquote>• <code>/stickerid</code> - מביא את הid של הסטיקר שהגיבו עליו.</blockquote>\n\n"
            "<b>◉ כלי מערכת:</b>\n"
            "<blockquote>• <code>/json</code> - קבלת המידע הטכני (JSON) של ההודעה.</blockquote>\n"
            "<blockquote>• <code>/written</code> [שם קובץ] - הופך את הטקסט לקובץ טקסט.</blockquote>"
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))

    elif data == "help_admin":
        txt = (
            "<b><u>לוח בקרה למנהלים:</u></b>\n\n"
            "<b>◉ ניהול תוכן:</b>\n"
            "<blockquote>• <code>/index</code> [link] - [start] - הוספת קבצים מערוץ (לפי טווח).\n"
            "• <code>/newindex</code> [ID] - מעקב אחרי תוכן חדש בערוץ.\n"
            "• <code>/channels</code> - ניהול ערוצים במעקב.</blockquote>\n\n"
            "<b>◉ משתמשים וקבוצות:</b>\n"
            "<blockquote>• <code>/ban</code> [ID] - חסימת משתמש.\n"
            "• <code>/unban</code> [ID] - שחרור משתמש.\n"
            "• <code>/ban_chat</code> [ID] - חסימת קבוצה.\n"
            "• <code>/unban_chat</code> [ID] - שחרור קבוצה.\n"
            "• <code>/leave</code> [ID] - יציאה מקבוצה (ללא חסימה).</blockquote>\n\n"
            "<b>◉ מערכת:</b>\n"
            "<blockquote>• <code>/clean</code> - אשף ניקוי נתונים.\n"
            "• <code>/broadcast</code> [-f] - שידור למנויים.\n"
            "• <code>/broadcast_groups</code> - שידור לקבוצות.\n"
            "• <code>/restart</code> - הפעלה מחדש.</blockquote>"
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))

    elif data == "help_guide":
        txt = (
            "<blockquote>"
            "⚙️ <b><u> מדריך לחיפוש ברובוט החיפוש</u></b> 💡\n\n"
            "כדי לבקש סרט או סדרה, יש לשים לב לדרך בה אתם מבקשים. חשוב לכתוב את השם המדויק של הסרט או הסדרה שברצונכם למצוא.\n\n"
            "<b><i><u>דוגמאות לחיפוש נכון </u></i></b>✔️\n"
            "אשמתי\n"
            "מהיר ועצבני\n\n"
            "<b><i><u>דוגמאות לא נכונות </u></i></b>❌\n"
            "יש הארי פוטר?\n"
            "אפשר הארי פוטר\n"
            "יש את הסרט הארי פוטר?\n\n"
            "<b>הבנתם? מעולה!</b>\n"
            "<b>נסו עכשיו בקבוצה!</b>\n\n"
            "<b>לא הבנתם</b> <b>⁉️</b>\n"
            "<b>אל תדאגו</b> ‼️\n"
            "אנחנו כאן כדי לעזור! הצוות המעולה שלנו תמיד זמין לענות על בקשות ⚡️\n"
            "זהו פשוט עוד דרך חכמה למענה מהיר יותר"
            "</blockquote>"
)

        btn = [[InlineKeyboardButton('למעבר לקבוצה 💬', url=REQUEST_GROUP, style=enums.ButtonStyle.SUCCESS)], [InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(btn))

    elif data == "help_copyright":
        txt = "<b>© זכויות יוצרים</b>\n\nהקבצים בבוט נאספים מטלגרם באופן אוטומטי. איננו מעלים תוכן בעצמנו."
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))
    
    elif data == "help_settings":
        txt = "<b>⚙️ הגדרות קבוצה</b>\n\nשלחו <code>/settings</code> בקבוצה כדי להגדיר:\n• מצב תצוגה (כפתורים/טקסט)\n• טריגר חיפוש (!)\n• כמות תוצאות"
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))

    elif data == "help_stats":
        try:
            await query.message.edit_caption("⏳ **מחשב נתונים...**")
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
                f"<blockquote>**★ בשימוש:** `{used_size}`\n"
                f"**★ מתוך:** `{max_size}`\n"
                f"★ **סטטוס:** [{bar}] `{percentage:.2f}%`</blockquote>"
            )
        except Exception as e:
            db_info = f"❌ לא ניתן לשלוף נתונים טכניים.\n`{e}`"

        txt = (
            f"📊 <u>**סטטיסטיקות הבוט:**</u>\n\n"
            f"🤖 <u>**סטטוס בוט:**</u>\n"
            f"<blockquote>★ **קבצים:** `{files}`\n"
            f"★ **משתמשים:** `{users}`\n"
            f"★ **קבוצות:** `{groups}`</blockquote>\n\n"
            f"{db_info}"
        )
        
        await query.message.edit_media(
            InputMediaPhoto(PHOTO_URL, caption=txt), 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY),
                 InlineKeyboardButton('↻ רענן', callback_data='help_stats', style=enums.ButtonStyle.SUCCESS)]
            ])
        )

    elif data == "about":
        bot_name = client.me.first_name
        bot_username = client.me.username
        bot_mention = f"[{bot_name}](https://t.me/{bot_username})"
        txt = (
            "<blockquote><b>╔════❰ 𝗔𝗯𝗼𝘂𝘁 𝗧𝗵𝗲 𝗕𝗼𝘁 ❱═❍⊱❁۪۪</b>\n"
            "<b>║╭━━━━━━━━━━━━━━━➣</b>\n"
            f"<b>║┣⪼ 🤖 ʙᴏᴛ : {bot_mention}</b>\n"
            "<b>║┣⪼ 👦 ᴄʀᴇᴀᴛᴏʀ : @BOSS1480</b>\n"
            f"<b>║┣⪼ 🤖 ᴜᴘᴅᴀᴛᴇ : <a href='https://t.me/{UPDATE_CHANNEL}'>Update Channel</a></b>\n"
            "<b>║┣⪼ 🗣️ ʟᴀɴɢᴜᴀɢᴇ : [Python](https://www.python.org/)</b>\n"
            "<b>║┣⪼ 📚 Lɪʙʀᴀʀʏ : [Pyrogram](https://docs.pyrogram.org/)</b>\n"
            "<b>║┣⪼ &lt;/&gt; Sᴏᴜʀᴄᴇ: : [GitHub](https://github.com/TJ-Bots/Search-Movies)</b>\n"
            "<b>║╰━━━━━━━━━━━━━━━➣</b>\n"
            "<b>╚══════════════════❍⊱❁۪۪</b></blockquote>"
        )
        btn = [
            [InlineKeyboardButton('🐙 𝚜𝚘𝚞𝚛𝚌𝚎 𝚌𝚘𝚍𝚎 🐙', url='https://github.com/TJ-Bots/Search-Movies', style=enums.ButtonStyle.SUCCESS)], 
            [InlineKeyboardButton('חזרה ⋟', callback_data='home', style=enums.ButtonStyle.PRIMARY), InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)]
        ]
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup(btn))

    elif data == "help_d":
        txt = (
            "<b><tg-emoji emoji-id='5443127283898405358'>📥</tg-emoji></b><b> </b><b><u>הורדה מטיקטוק:</u></b>\n\n\n<b>◉ </b><b><u>פקודה:</u></b>\n<blockquote>/d</blockquote>\n\n<b>◉ </b><b><u>איך משתמשים</u>?</b>\n<blockquote>שולחים את הפקודה ביחד עם קישור. אפשר גם להגיב לקישור עם הפקודה.</blockquote>"
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))


    elif data == "help_telegraph":
        txt = (
            "<tg-emoji emoji-id='5445355530111437729'>📤</tg-emoji> <b><u>העלאת תמונות ל: i.ibb.co</u></b> 🖼️\n\n\n<b>◉ </b><b><u>פקודה:</u></b>\n<blockquote>/telegraph</blockquote>\n\n<b>◉ </b><b><u>איך משתמשים?</u></b>\n<blockquote>פשוט מגיבים על תמונה עם הפקודה.</blockquote>"
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))


    elif data == "help_exthumb":
        txt = (
            "<tg-emoji emoji-id='5823268688874179761'>🔧</tg-emoji> <b><i>כלים לוידאו:</i>\n\n\n</b><b><tg-emoji emoji-id='5332679880599418983'>ℹ️</tg-emoji></b><b> </b><b><u>מידע על וידאו:</u></b>\n<b>◉ פקודה:</b>\n<blockquote>/mediainfo</blockquote>\n\n<b>🖼️ </b><b><u>חילוץ תמונה ממוזערת:</u></b>\n<b>◉ פקודה:</b>\n<blockquote>/extract_thumbnail</blockquote>\n\n\n<b><u>איך משתמשים?</u></b>\n<blockquote>מגיבים על וידאו/קובץ עם הפקודה שרוצים.</blockquote>"
        )
        await query.message.edit_media(InputMediaPhoto(PHOTO_URL, caption=txt), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='help', style=enums.ButtonStyle.PRIMARY)]]))


    elif data == "closea":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
        except:
            pass
    elif data == "noop":
        await query.answer()
