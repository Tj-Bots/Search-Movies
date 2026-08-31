import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import ADMINS, PHOTO_URL, AUTH_CHANNEL_FORCE, FREE_DAILY_SEARCHES
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

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

USER_PROMPTS = {
    'grant_time': {'label': 'הענקת זמן ללא הגבלה', 'prompt': "שלח כמה שעות להעניק (מספר בלבד).\nלדוגמה: <code>24</code>"},
    'grant_credits': {'label': 'הענקת חיפושים', 'prompt': "שלח כמה חיפושים להעניק (מספר בלבד).\nלדוגמה: <code>20</code>"},
    'send_dm': {'label': 'שליחת הודעה פרטית', 'prompt': "שלח את תוכן ההודעה שתישלח למשתמש."},
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
        [InlineKeyboardButton('👁 משתמשים חסומים', callback_data='adm_banlist_users_1'),
         InlineKeyboardButton('👁 קבוצות חסומות', callback_data='adm_banlist_chats_1')],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _banlist_text_markup(kind, page):
    per_page = 10
    if kind == 'users':
        rows, total = await db.get_banned_users_page(page, per_page)
        title = 'משתמשים חסומים'
    else:
        rows, total = await db.get_banned_chats_page(page, per_page)
        title = 'קבוצות חסומות'

    total_pages = max((total + per_page - 1) // per_page, 1)
    text = f"👁 <b>{title} ({total})</b>\n\nלחץ על מזהה כדי לשחרר:"

    keyboard = [
        [InlineKeyboardButton(f"🚫 {r['_id']} — {r.get('reason', '')}", callback_data=f"adm_unban1_{kind}_{r['_id']}_{page}")]
        for r in rows
    ] or [[InlineKeyboardButton('הרשימה ריקה', callback_data='noop')]]

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'adm_banlist_{kind}_{page - 1}'))
    nav.append(InlineKeyboardButton(f'{page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'adm_banlist_{kind}_{page + 1}'))
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_ban_menu', style=enums.ButtonStyle.PRIMARY)])

    return text, InlineKeyboardMarkup(keyboard)


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
    now = time.time()

    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    free_used = quota['free_used'] if quota['free_date'] == today else 0

    ban_line = f"🔴 חסום (סיבה: {ban_info.get('reason')})" if ban_info else "🟢 פעיל (לא חסום)"

    if quota['unlimited_until'] > now:
        hours_left = int((quota['unlimited_until'] - now) // 3600)
        unlimited_line = f"כן (עוד כ-{hours_left} שעות)"
    else:
        unlimited_line = "לא"

    return (
        f"👤 <b>{user.get('first_name', 'Unknown')}</b>\n"
        f"🪪 מזהה (ID): <code>{user_id}</code>\n\n"
        "<blockquote>"
        f"⏰ מנוי זמן ללא הגבלה: <b>{unlimited_line}</b>\n"
        f"💳 יתרת חיפושים (בנק): <b>{quota['search_credits']}</b>\n"
        f"🆓 חיפושים חינמיים היום: <b>{free_used}/{FREE_DAILY_SEARCHES}</b>\n"
        f"🚦 סטטוס חסימה: {ban_line}\n"
        f"⚠️ כמות עבירות (חיפושים אסורים): <b>{user.get('blocked_attempts', 0)}</b>"
        "</blockquote>"
    )


async def _user_actions_markup(user_id, page):
    ban_info = await db.get_ban_status(user_id)
    ban_btn = (
        InlineKeyboardButton('✅ שחרר משתמש', callback_data=f'adm_unban2_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS)
        if ban_info else
        InlineKeyboardButton('🚫 חסום משתמש', callback_data=f'adm_ban2_{user_id}_{page}', style=enums.ButtonStyle.DANGER)
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📚 היסטוריית חיפושים', callback_data=f'adm_history_{user_id}_{page}')],
        [InlineKeyboardButton('💎 הענק זמן ללא הגבלה', callback_data=f'adm_grantt_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS),
         InlineKeyboardButton('🔍 הענק חיפושים', callback_data=f'adm_grantc_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('✉️ שלח הודעה פרטית', callback_data=f'adm_dm_{user_id}_{page}')],
        [ban_btn],
        [InlineKeyboardButton('חזרה לרשימה ⋟', callback_data=f'adm_users_{page}', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _start_user_action(query, action, user_id, page):
    info = USER_PROMPTS[action]
    admin_id = query.from_user.id
    ADM_INPUT[admin_id] = {
        'action': action, 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id,
        'target_user': user_id, 'back_page': page,
    }
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=f'adm_userview_{user_id}_{page}')]])
    text = f"✏️ <b>{info['label']}</b>\n\n{info['prompt']}"
    await query.message.edit_caption(text, reply_markup=markup)


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
        markup = await _user_actions_markup(user_id, 1)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)

    if action in ('grant_time', 'grant_credits', 'send_dm'):
        target_user = state['target_user']
        back_page = state['back_page']

        if action == 'grant_time':
            try:
                hours = float(text_in)
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=_back_markup(f'adm_userview_{target_user}_{back_page}'))
            await db.extend_unlimited(target_user, hours * 3600)
            note = f"✅ הוענקו {hours:g} שעות ללא הגבלה."
        elif action == 'grant_credits':
            try:
                amount = int(text_in)
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=_back_markup(f'adm_userview_{target_user}_{back_page}'))
            await db.add_search_credits(target_user, amount)
            note = f"✅ הוענקו {amount} חיפושים."
        else:
            try:
                await client.send_message(target_user, text_in)
                note = "✅ ההודעה נשלחה למשתמש."
            except Exception as e:
                note = f"❌ שליחה נכשלה: {e}"

        info_text = await _render_user_info(target_user)
        markup = await _user_actions_markup(target_user, back_page)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"{note}\n\n{info_text}", reply_markup=markup)


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

    if data.startswith("adm_banlist_"):
        kind, _, page_str = data[len("adm_banlist_"):].rpartition('_')
        page = int(page_str) if page_str.isdigit() else 1
        text, markup = await _banlist_text_markup(kind, page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_unban1_"):
        kind, target_id_str, page_str = data[len("adm_unban1_"):].split('_')
        target_id = int(target_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        if kind == 'users':
            await db.unban_user(target_id)
        else:
            await db.unban_chat(target_id)
        text, markup = await _banlist_text_markup(kind, page)
        return await query.message.edit_caption(f"✅ שוחרר: <code>{target_id}</code>\n\n{text}", reply_markup=markup)

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
        markup = await _user_actions_markup(user_id, back_page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_ban2_") or data.startswith("adm_unban2_"):
        is_ban = data.startswith("adm_ban2_")
        rest = data[len("adm_ban2_"):] if is_ban else data[len("adm_unban2_"):]
        user_id_str, _, page_str = rest.partition('_')
        user_id = int(user_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        if is_ban:
            await db.ban_user(user_id, "נחסם דרך פרטי המשתמש")
        else:
            await db.unban_user(user_id)
        text = await _render_user_info(user_id)
        markup = await _user_actions_markup(user_id, page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_history_"):
        rest = data[len("adm_history_"):]
        user_id_str, _, page_str = rest.partition('_')
        user_id = int(user_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        rows = await db.get_user_search_history(user_id, 15)
        body = "\n".join(f"• <code>{r['query']}</code>" for r in rows) if rows else "אין היסטוריית חיפושים."
        text = f"📚 <b>היסטוריית חיפושים</b>\n\n{body}"
        return await query.message.edit_caption(text, reply_markup=_back_markup(f'adm_userview_{user_id}_{page}'))

    if data.startswith("adm_grantt_"):
        user_id_str, _, page_str = data[len("adm_grantt_"):].partition('_')
        return await _start_user_action(query, 'grant_time', int(user_id_str), int(page_str) if page_str.isdigit() else 1)

    if data.startswith("adm_grantc_"):
        user_id_str, _, page_str = data[len("adm_grantc_"):].partition('_')
        return await _start_user_action(query, 'grant_credits', int(user_id_str), int(page_str) if page_str.isdigit() else 1)

    if data.startswith("adm_dm_"):
        user_id_str, _, page_str = data[len("adm_dm_"):].partition('_')
        return await _start_user_action(query, 'send_dm', int(user_id_str), int(page_str) if page_str.isdigit() else 1)

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
                filled = int(pct * 8 / 100)
                return '▩' * filled + '□' * (8 - filled)

            gb = 1024 ** 3
            text = (
                "📈 <b>מד עומס שרת</b>\n\n"
                "<blockquote>"
                f"╭ CPU : {bar(cpu)} {cpu:.0f}%\n"
                f"┊ RAM : {bar(mem.percent)} {mem.percent:.0f}% ({mem.used / gb:.2f}GB/{mem.total / gb:.2f}GB)\n"
                f"╰ Disk : {bar(disk.percent)} {disk.percent:.0f}% ({disk.free / gb:.2f}GB free)"
                "</blockquote>"
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
