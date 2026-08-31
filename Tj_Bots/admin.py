import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import ADMINS, PHOTO_URL, AUTH_CHANNEL_FORCE
from database import db

ADM_INPUT = {}
USERS_PER_PAGE = 10

PROMPTS = {
    'ban_user': {'label': 'חסימת משתמש', 'prompt': "שלח את מזהה המשתמש לחסימה (ואפשר סיבה אחרי רווח).\nלדוגמה: <code>123456789 הפרת חוקים</code>", 'back': 'ban'},
    'unban_user': {'label': 'שחרור משתמש', 'prompt': "שלח את מזהה המשתמש לשחרור.", 'back': 'ban'},
    'ban_chat': {'label': 'חסימת קבוצה', 'prompt': "שלח את מזהה הקבוצה לחסימה (ואפשר סיבה אחרי רווח).", 'back': 'ban'},
    'unban_chat': {'label': 'שחרור קבוצה', 'prompt': "שלח את מזהה הקבוצה לשחרור.", 'back': 'ban'},
    'set_channel': {'label': 'שינוי ערוץ עדכונים', 'prompt': "שלח את שם המשתמש של הערוץ (בלי @).\nלדוגמה: <code>searchgram_bots</code>", 'back': 'settings'},
    'add_word': {'label': 'הוספת מילה חסומה', 'prompt': "שלח את המילה/הביטוי שברצונך לחסום מחיפוש.", 'back': 'words'},
    'del_word': {'label': 'הסרת מילה חסומה', 'prompt': "שלח את המילה שברצונך להסיר מהחסימה.", 'back': 'words'},
    'find_user': {'label': 'איתור משתמש', 'prompt': "שלח את מזהה המשתמש (ID) לבדיקה.", 'back': 'users'},
}


# ---------- markup builders ----------

def _panel_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📢 שידור הודעות', callback_data='bc_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🚫 ניהול חסימות', callback_data='adm_ban_menu', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('👥 משתמשים', callback_data='adm_users_1', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('⚙️ הגדרות מערכת', callback_data='adm_settings', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📊 סטטיסטיקות', callback_data='adm_stats', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('🔥 חיפושים פופולריים', callback_data='adm_popular', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📈 מד עומס שרת', callback_data='adm_load', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('⭐ תומכים בכוכבים', callback_data='adm_stars', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('📡 ערוצי מקור', callback_data='adm_channels', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)],
    ])


def _ban_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🚫 חסימת משתמש', callback_data='adm_ban_ban_user', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('✅ שחרור משתמש', callback_data='adm_ban_unban_user', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('🚫 חסימת קבוצה', callback_data='adm_ban_ban_chat', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('✅ שחרור קבוצה', callback_data='adm_ban_unban_chat', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _settings_menu_markup():
    locked = await db.get_config('bot_locked', False)
    auth_force = await db.get_config('auth_force', AUTH_CHANNEL_FORCE)
    lock_label = '🔒 הבוט נעול - לחץ לביטול' if locked else '🔓 הבוט פעיל - לחץ לנעילה'
    auth_label = '🔒 חיוב הרשמה: מופעל' if auth_force else '🔓 חיוב הרשמה: כבוי'
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lock_label, callback_data='adm_toggle_lock', style=enums.ButtonStyle.DANGER if locked else enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(auth_label, callback_data='adm_toggle_auth', style=enums.ButtonStyle.DANGER if auth_force else enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('✏️ שינוי ערוץ חיוב הרשמה', callback_data='adm_set_channel', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🚫 מילים חסומות בחיפוש', callback_data='adm_words_menu', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _words_menu_text_markup():
    words = await db.get_blocked_words()
    body = ", ".join(f"<code>{w}</code>" for w in words) if words else "אין מילים חסומות."
    text = f"🚫 <b>מילים חסומות בחיפוש</b>\n\n{body}"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ הוספת מילה', callback_data='adm_words_add', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('➖ הסרת מילה', callback_data='adm_words_del', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_settings', style=enums.ButtonStyle.PRIMARY)],
    ])
    return text, markup


def _back_markup(target='adm_home'):
    return InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data=target, style=enums.ButtonStyle.PRIMARY)]])


async def send_admin_panel(message, is_edit=False):
    text = "🛠 <b>פאנל ניהול</b>\n\nבחר פעולה:"
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=text), reply_markup=_panel_markup())
    else:
        await message.reply_photo(PHOTO_URL, caption=text, reply_markup=_panel_markup(), quote=True)


@Client.on_message(filters.command("admin") & filters.user(ADMINS))
async def admin_command(client, message):
    await send_admin_panel(message)


# ---------- users browser ----------

async def _render_user_info(user_id):
    user = await db.find_user(user_id)
    if not user:
        return f"❌ המשתמש <code>{user_id}</code> לא נמצא במסד הנתונים."

    quota = await db.get_search_quota(user_id)
    ban_info = await db.get_ban_status(user_id)
    ban_line = f"🚫 חסום (סיבה: {ban_info.get('reason')})" if ban_info else "✅ לא חסום"
    unlimited = quota['unlimited_until'] > time.time()

    return (
        f"👤 <b>{user.get('first_name', 'Unknown')}</b> — <code>{user_id}</code>\n\n"
        f"<blockquote>{ban_line}\n"
        f"💳 יתרת חיפושים בתשלום: <b>{quota['search_credits']}</b>\n"
        f"⏰ מנוי זמן ללא הגבלה: <b>{'פעיל' if unlimited else 'לא פעיל'}</b></blockquote>"
    )


async def _users_page_text_markup(page):
    users, total = await db.get_users_page(page, USERS_PER_PAGE)
    total_pages = max((total + USERS_PER_PAGE - 1) // USERS_PER_PAGE, 1)

    text = f"👥 <b>משתמשים ({total})</b>\n\nבחר משתמש לצפייה בפרטים:"

    keyboard = [
        [InlineKeyboardButton(f"👤 {u.get('first_name', 'Unknown')} — {u['_id']}", callback_data=f"adm_userview_{u['_id']}_{page}")]
        for u in users
    ] or [[InlineKeyboardButton('אין משתמשים', callback_data='noop')]]

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'adm_users_{page - 1}'))
    nav.append(InlineKeyboardButton(f'עמוד {page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'adm_users_{page + 1}'))
    keyboard.append(nav)

    keyboard.append([InlineKeyboardButton('🔎 איתור לפי מזהה', callback_data='adm_users_search', style=enums.ButtonStyle.PRIMARY)])
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)])

    return text, InlineKeyboardMarkup(keyboard)


# ---------- text-input flow (ban actions, settings, words, user lookup) ----------

def _is_awaiting_input(_, __, message):
    admin_id = message.from_user.id if message.from_user else None
    return admin_id in ADM_INPUT


@Client.on_message(filters.user(ADMINS) & filters.create(_is_awaiting_input))
async def admin_text_input(client, message):
    admin_id = message.from_user.id
    state = ADM_INPUT.pop(admin_id)
    action = state['action']
    panel_chat, panel_msg = state['panel_chat'], state['panel_msg']
    text_in = (message.text or "").strip()

    try:
        await message.delete()
    except Exception:
        pass

    if action in ('ban_user', 'unban_user', 'ban_chat', 'unban_chat'):
        parts = text_in.split(maxsplit=1)
        try:
            target_id = int(parts[0])
        except (IndexError, ValueError):
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מזהה לא תקין.", reply_markup=_ban_menu_markup())

        reason = parts[1] if len(parts) > 1 else "לא צוינה סיבה"

        if action == 'ban_user':
            await db.ban_user(target_id, reason)
            result = f"🚫 המשתמש <code>{target_id}</code> נחסם.\nסיבה: {reason}"
        elif action == 'unban_user':
            await db.unban_user(target_id)
            result = f"✅ המשתמש <code>{target_id}</code> שוחרר."
        elif action == 'ban_chat':
            await db.ban_chat(target_id, reason)
            result = f"🚫 הקבוצה <code>{target_id}</code> נחסמה.\nסיבה: {reason}"
            try:
                await client.send_message(target_id, f"🚫 קבוצה זו נחסמה.\nסיבה: {reason}")
                await client.leave_chat(target_id)
            except Exception:
                pass
        else:
            await db.unban_chat(target_id)
            result = f"✅ הקבוצה <code>{target_id}</code> שוחררה."

        return await client.edit_message_caption(panel_chat, panel_msg, caption=result, reply_markup=_ban_menu_markup())

    if action == 'set_channel':
        channel = text_in.lstrip('@').strip()
        if not channel:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ שם ערוץ לא תקין.", reply_markup=await _settings_menu_markup())
        await db.set_config('update_channel', channel)
        return await client.edit_message_caption(
            panel_chat, panel_msg, caption=f"✅ ערוץ העדכונים עודכן ל-<code>{channel}</code>.", reply_markup=await _settings_menu_markup()
        )

    if action == 'add_word':
        if not text_in:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ לא נשלחה מילה.", reply_markup=(await _words_menu_text_markup())[1])
        await db.add_blocked_word(text_in.lower())
        text, markup = await _words_menu_text_markup()
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"✅ נוספה מילה חסומה: <code>{text_in}</code>\n\n{text}", reply_markup=markup)

    if action == 'del_word':
        await db.remove_blocked_word(text_in.lower())
        text, markup = await _words_menu_text_markup()
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"✅ הוסרה מילה חסומה: <code>{text_in}</code>\n\n{text}", reply_markup=markup)

    if action == 'find_user':
        try:
            user_id = int(text_in)
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מזהה לא תקין.", reply_markup=_back_markup('adm_users_1'))

        text = await _render_user_info(user_id)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=_back_markup('adm_users_1'))


# ---------- callbacks ----------

@Client.on_callback_query(filters.regex(r"^adm_"))
async def admin_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if data == "adm_home":
        ADM_INPUT.pop(admin_id, None)
        return await send_admin_panel(query.message, is_edit=True)

    if data == "adm_ban_menu":
        return await query.message.edit_caption("🚫 <b>ניהול חסימות</b>\n\nבחר פעולה:", reply_markup=_ban_menu_markup())

    if data.startswith("adm_ban_"):
        action = data[len("adm_ban_"):]
        return await _start_input(query, action)

    if data == "adm_settings":
        return await query.message.edit_caption("⚙️ <b>הגדרות מערכת</b>\n\nבחר הגדרה:", reply_markup=await _settings_menu_markup())

    if data == "adm_toggle_lock":
        locked = await db.get_config('bot_locked', False)
        await db.set_config('bot_locked', not locked)
        return await query.message.edit_caption("⚙️ <b>הגדרות מערכת</b>\n\nבחר הגדרה:", reply_markup=await _settings_menu_markup())

    if data == "adm_toggle_auth":
        auth_force = await db.get_config('auth_force', AUTH_CHANNEL_FORCE)
        await db.set_config('auth_force', not auth_force)
        return await query.message.edit_caption("⚙️ <b>הגדרות מערכת</b>\n\nבחר הגדרה:", reply_markup=await _settings_menu_markup())

    if data == "adm_set_channel":
        return await _start_input(query, "set_channel")

    if data == "adm_words_menu":
        text, markup = await _words_menu_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_words_add":
        return await _start_input(query, "add_word")

    if data == "adm_words_del":
        return await _start_input(query, "del_word")

    if data == "adm_users_search":
        return await _start_input(query, "find_user")

    if data.startswith("adm_userview_"):
        rest = data[len("adm_userview_"):]
        user_id_str, _, back_page_str = rest.partition('_')
        try:
            user_id = int(user_id_str)
        except ValueError:
            return
        back_page = int(back_page_str) if back_page_str.isdigit() else 1
        text = await _render_user_info(user_id)
        return await query.message.edit_caption(text, reply_markup=_back_markup(f'adm_users_{back_page}'))

    if data.startswith("adm_users_"):
        try:
            page = int(data[len("adm_users_"):])
        except ValueError:
            page = 1
        text, markup = await _users_page_text_markup(page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_channels":
        channels = await db.get_watched_channels()
        body = "\n".join(f"• <code>{c}</code>" for c in channels) if channels else "אין ערוצים ברשימת המעקב."
        text = f"📡 <b>ערוצי מקור במעקב</b>\n\n{body}\n\nלהוספה/הסרה: <code>/newindex</code>, <code>/channels</code>."
        return await query.message.edit_caption(text, reply_markup=_back_markup())

    if data == "adm_stars":
        from .pay import build_purchase_stats_text
        text = await build_purchase_stats_text()
        return await query.message.edit_caption(text, reply_markup=_back_markup())

    if data == "adm_stats":
        from .stats import build_stats_text
        text = await build_stats_text()
        return await query.message.edit_caption(text, reply_markup=_back_markup())

    if data == "adm_popular":
        rows = await db.get_popular_searches(15)
        if rows:
            body = "\n".join(f"{i + 1}. <code>{r['_id']}</code> — {r['count']}" for i, r in enumerate(rows))
        else:
            body = "עדיין אין נתוני חיפושים."
        return await query.message.edit_caption(f"🔥 <b>חיפושים פופולריים</b>\n\n{body}", reply_markup=_back_markup())

    if data == "adm_load":
        try:
            import psutil
            cpu = await asyncio.get_event_loop().run_in_executor(None, psutil.cpu_percent, 0.3)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            def bar(pct):
                filled = int(pct / 10)
                return '▓' * filled + '░' * (10 - filled)

            text = (
                "📈 <b>מד עומס שרת</b>\n\n"
                f"<blockquote>🧠 CPU: [{bar(cpu)}] {cpu:.1f}%\n"
                f"💾 RAM: [{bar(mem.percent)}] {mem.percent:.1f}% ({mem.used // (1024**2)}MB/{mem.total // (1024**2)}MB)\n"
                f"🗄 דיסק: [{bar(disk.percent)}] {disk.percent:.1f}%</blockquote>"
            )
        except ImportError:
            text = "❌ חבילת <code>psutil</code> לא מותקנת. הרץ <code>pip install -r requirements.txt</code> ואתחל את הבוט."
        return await query.message.edit_caption(text, reply_markup=_back_markup())


async def _start_input(query, action):
    info = PROMPTS[action]
    admin_id = query.from_user.id
    ADM_INPUT[admin_id] = {'action': action, 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
    back_targets = {'ban': 'adm_ban_menu', 'settings': 'adm_settings', 'words': 'adm_words_menu', 'users': 'adm_users_1'}
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=back_targets[info['back']])]])
    text = f"✏️ <b>{info['label']}</b>\n\n{info['prompt']}"
    await query.message.edit_caption(text, reply_markup=markup)
