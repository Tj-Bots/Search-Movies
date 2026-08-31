import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import ADMINS, PHOTO_URL, AUTH_CHANNEL_FORCE
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

ADM_INPUT = {}
ADM_SEARCH = {}
USERS_PER_PAGE = 10

PROMPTS = {
    'ban_user': {'label': 'חסימת משתמש', 'prompt': "שלח את מזהה המשתמש לחסימה (ואפשר סיבה אחרי רווח).\nלדוגמה: <code>123456789 הפרת חוקים</code>", 'back': 'ban'},
    'unban_user': {'label': 'שחרור משתמש', 'prompt': "שלח את מזהה המשתמש לשחרור.", 'back': 'ban'},
    'ban_chat': {'label': 'חסימת קבוצה', 'prompt': "שלח את מזהה הקבוצה לחסימה (ואפשר סיבה אחרי רווח).", 'back': 'ban'},
    'unban_chat': {'label': 'שחרור קבוצה', 'prompt': "שלח את מזהה הקבוצה לשחרור.", 'back': 'ban'},
    'set_channel': {'label': 'שינוי ערוץ עדכונים', 'prompt': "שלח את שם המשתמש של הערוץ (בלי @).\nלדוגמה: <code>searchgram_bots</code>", 'back': 'settings'},
    'add_word': {'label': 'הוספת מילה חסומה', 'prompt': "שלח את המילה/הביטוי שברצונך לחסום מחיפוש.", 'back': 'words'},
    'del_word': {'label': 'הסרת מילה חסומה', 'prompt': "שלח את המילה שברצונך להסיר מהחסימה.", 'back': 'words'},
    'find_user': {'label': 'איתור משתמש', 'prompt': "שלח מזהה (ID) או שם משתמש לחיפוש.", 'back': 'users'},
    'find_group': {'label': 'איתור קבוצה', 'prompt': "שלח מזהה (ID) או שם קבוצה לחיפוש.", 'back': 'groups'},
    'watch_channel': {'label': 'הוספת ערוץ למעקב', 'prompt': "שלח את מזהה (ID) הערוץ להוספה למעקב.\nלדוגמה: <code>-1001234567890</code>", 'back': 'channels'},
    'start_index': {'label': 'התחלת אינדוקס', 'prompt': "שלח קישור לערוץ (ואפשר טווח התחלה), בדיוק כמו בפקודת /index.\nלדוגמה: <code>https://t.me/c/1234/1000</code>\nאו: <code>https://t.me/c/1234/1000 - 500</code>", 'back': 'channels'},
    'set_freelimit': {'label': 'קביעת מכסת קבצים חינמית ליום', 'prompt': "שלח כמה קבצים חינמיים לאפשר ליום (מספר בלבד).\nלדוגמה: <code>7</code>", 'back': 'payments'},
}

USER_PROMPTS = {
    'grant_time': {'label': 'הענקת זמן ללא הגבלה', 'prompt': "שלח כמה שעות להעניק (מספר בלבד).\nלדוגמה: <code>24</code>"},
    'grant_credits': {'label': 'הענקת קבצים', 'prompt': "שלח כמה קבצים להעניק (מספר בלבד).\nלדוגמה: <code>20</code>"},
    'remove_credits': {'label': 'הסרת קבצים מהבנק', 'prompt': "שלח כמה קבצים להסיר (מספר בלבד)."},
    'send_dm': {'label': 'שליחת הודעה פרטית', 'prompt': "שלח את תוכן ההודעה שתישלח למשתמש."},
}


async def _notify_user(client, user_id, text):
    try:
        await client.send_message(user_id, text)
    except Exception:
        pass


PENDING_CONFIRM = {}


def _confirm_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ כן, בצע', callback_data='adm_confirm_yes', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('❌ ביטול', callback_data='adm_confirm_no', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _ask_confirm(query, description, on_confirm, on_cancel):
    admin_id = query.from_user.id
    PENDING_CONFIRM[admin_id] = {'confirm': on_confirm, 'cancel': on_cancel}
    await query.message.edit_caption(f"⚠️ <b>אישור פעולה</b>\n\n{description}", reply_markup=_confirm_markup())


# ---------- markup builders ----------

def _panel_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📢 שידור הודעות', callback_data='bc_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🚫 ניהול חסימות', callback_data='adm_ban_menu', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('👥 משתמשים', callback_data='adm_users_1', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('💬 קבוצות', callback_data='adm_groups_1', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('⚙️ הגדרות מערכת', callback_data='adm_settings', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📊 סטטיסטיקות', callback_data='adm_stats', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('🔥 חיפושים פופולריים', callback_data='adm_popular', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📈 מד עומס שרת', callback_data='adm_load', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('⭐ תומכים בכוכבים', callback_data='adm_stars', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('📡 ערוצים', callback_data='adm_channels_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)],
    ])


def _channels_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('➕ הוספת ערוץ למעקב', callback_data='adm_ch_add'),
         InlineKeyboardButton('▶️ התחלת אינדוקס', callback_data='adm_ch_index')],
        [InlineKeyboardButton('📋 ערוצים במעקב (לחיצה = הסרה)', callback_data='adm_ch_list')],
        [InlineKeyboardButton('📊 סטטוס אינדוקס חי', callback_data='adm_ch_status')],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _channels_list_text_markup():
    channels = await db.get_watched_channels()
    if not channels:
        text = "📋 <b>ערוצים במעקב</b>\n\nאין ערוצים ברשימה."
        keyboard = []
    else:
        text = "📋 <b>ערוצים במעקב</b>\n\nלחץ על ערוץ כדי להסיר אותו מהמעקב:"
        keyboard = [[InlineKeyboardButton(f"📡 {c}", callback_data=f"adm_ch_rm_{c}")] for c in channels]
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_channels_menu', style=enums.ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(keyboard)


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
        [InlineKeyboardButton('💰 מערכת תשלומים', callback_data='adm_payments_menu', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _payments_menu_markup():
    from .pay import is_payments_enabled, get_free_daily_limit
    enabled = await is_payments_enabled()
    limit = await get_free_daily_limit()
    pay_label = '💰 תשלומים בכוכבים: מופעל' if enabled else '🆓 תשלומים בכוכבים: כבוי (הכל חינם וללא הגבלה)'
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(pay_label, callback_data='adm_toggle_payments', style=enums.ButtonStyle.SUCCESS if enabled else enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton(f'✏️ קבצים חינמיים ליום: {limit}', callback_data='adm_set_freelimit', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_settings', style=enums.ButtonStyle.PRIMARY)],
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


async def _popular_text_markup():
    rows = await db.get_popular_searches(20)
    success, total = await db.get_search_stats_totals()

    if rows:
        lines = []
        for i, r in enumerate(rows):
            icon = '✅' if r.get('success_count', 0) > 0 else '❌'
            lines.append(f"{i + 1}. <code>{r['_id']}</code> - {r['count']} חיפושים {icon}")
        pct = (success / total * 100) if total else 0
        body = "\n".join(lines) + f"\n\n📊 אחוזי הצלחה כוללים: {pct:.1f}% ({success}/{total})"
        text = f"🔥 <b>{len(rows)} החיפושים הפופולריים ביותר:</b>\n\n{body}"
    else:
        text = "🔥 <b>חיפושים פופולריים</b>\n\nעדיין אין נתוני חיפושים."

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('🗑 מחק היסטוריית חיפושים פופולריים', callback_data='adm_popular_clear_ask', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])
    return text, markup


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
    from .pay import get_free_daily_limit
    user = await db.find_user(user_id)
    if not user:
        return f"❌ המשתמש <code>{user_id}</code> לא נמצא במסד הנתונים."

    quota = await db.get_search_quota(user_id)
    daily_limit = await get_free_daily_limit()
    ban_info = await db.get_ban_status(user_id)
    now = time.time()

    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    free_used = quota['free_used'] if quota['free_date'] == today else 0

    ban_line = f"🔴 חסום (סיבה: {ban_info.get('reason')})" if ban_info else "🟢 פעיל (לא חסום)"

    if quota['unlimited_until'] > now:
        remaining = quota['unlimited_until'] - now
        if remaining >= 3600:
            unlimited_line = f"כן (עוד כ-{int(remaining // 3600)} שעות)"
        else:
            unlimited_line = f"כן (עוד כ-{max(int(remaining // 60), 1)} דקות)"
    else:
        unlimited_line = "לא"

    return (
        f"👤 <b>{user.get('first_name', 'Unknown')}</b>\n"
        f"🪪 מזהה (ID): <code>{user_id}</code>\n\n"
        "<blockquote>"
        f"⏰ מנוי זמן ללא הגבלה: <b>{unlimited_line}</b>\n"
        f"💳 יתרת קבצים (בנק): <b>{quota['search_credits']}</b>\n"
        f"🆓 קבצים חינמיים היום: <b>{free_used}/{daily_limit}</b>\n"
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
        [InlineKeyboardButton('🎛 ניהול קבצים', callback_data=f'adm_searchmgmt_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('📚 היסטוריית חיפושים', callback_data=f'adm_history_{user_id}_{page}')],
        [InlineKeyboardButton('✉️ שלח הודעה פרטית', callback_data=f'adm_dm_{user_id}_{page}')],
        [ban_btn],
        [InlineKeyboardButton('חזרה לרשימה ⋟', callback_data=f'adm_users_{page}', style=enums.ButtonStyle.PRIMARY)],
    ])


def _search_mgmt_markup(user_id, page):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('💎 הענק זמן ללא הגבלה', callback_data=f'adm_grantt_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('🔍 הענק קבצים', callback_data=f'adm_grantc_{user_id}_{page}', style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton('➖ הסר קבצים מהבנק', callback_data=f'adm_revokec_{user_id}_{page}', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('❌ ביטול מנוי זמן ללא הגבלה', callback_data=f'adm_revoket_{user_id}_{page}', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('🔄 איפוס קבצים חינמיים היום', callback_data=f'adm_resetfree_{user_id}_{page}')],
        [InlineKeyboardButton('חזרה לפרטי משתמש ⋟', callback_data=f'adm_userview_{user_id}_{page}', style=enums.ButtonStyle.PRIMARY)],
    ])


async def _start_user_action(query, action, user_id, page, return_to='info'):
    info = USER_PROMPTS[action]
    admin_id = query.from_user.id
    ADM_INPUT[admin_id] = {
        'action': action, 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id,
        'target_user': user_id, 'back_page': page, 'return_to': return_to,
    }
    cancel_target = f'adm_searchmgmt_{user_id}_{page}' if return_to == 'mgmt' else f'adm_userview_{user_id}_{page}'
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=cancel_target)]])
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

    keyboard.append([InlineKeyboardButton('🔎 איתור לפי מזהה/שם', callback_data='adm_users_search', style=enums.ButtonStyle.PRIMARY)])
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)])

    return text, InlineKeyboardMarkup(keyboard)


# ---------- groups browser ----------

async def _render_group_info(client, chat_id):
    group = await db.find_group(chat_id)
    name = group.get('title', 'Unknown') if group else 'Unknown'
    ban_info = await db.get_chat_ban_status(chat_id)
    ban_line = f"🔴 חסומה (סיבה: {ban_info.get('reason')})" if ban_info else "🟢 פעילה (לא חסומה)"

    member_count = "לא ידוע"
    invite_line = "לא זמין (הבוט אינו חבר בקבוצה)"
    try:
        chat = await client.get_chat(chat_id)
        if chat.members_count:
            member_count = chat.members_count
        if chat.invite_link:
            invite_line = chat.invite_link
        else:
            invite_line = await client.export_chat_invite_link(chat_id)
    except Exception:
        pass

    return (
        f"💬 <b>{name}</b>\n"
        f"🪪 מזהה (ID): <code>{chat_id}</code>\n\n"
        "<blockquote>"
        f"👥 חברים: <b>{member_count}</b>\n"
        f"🚦 סטטוס: {ban_line}\n"
        f"🔗 קישור הזמנה: {invite_line}"
        "</blockquote>"
    )


def _group_actions_markup(chat_id, page, is_banned):
    ban_btn = (
        InlineKeyboardButton('✅ שחרר קבוצה', callback_data=f'adm_gunban_{chat_id}_{page}', style=enums.ButtonStyle.SUCCESS)
        if is_banned else
        InlineKeyboardButton('🚫 חסום קבוצה', callback_data=f'adm_gban_{chat_id}_{page}', style=enums.ButtonStyle.DANGER)
    )
    return InlineKeyboardMarkup([
        [ban_btn, InlineKeyboardButton('🚪 עזוב קבוצה', callback_data=f'adm_gleave_{chat_id}_{page}', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('חזרה לרשימה ⋟', callback_data=f'adm_groups_{page}', style=enums.ButtonStyle.PRIMARY)],
    ])


# ---------- name/id search results (paginated) ----------

def _search_results_text_markup(admin_id, page):
    state = ADM_SEARCH.get(admin_id)
    if not state:
        return None, None

    kind, term, matches = state['kind'], state['term'], state['matches']
    total = len(matches)
    total_pages = max((total + USERS_PER_PAGE - 1) // USERS_PER_PAGE, 1)
    page = max(1, min(page, total_pages))
    start = (page - 1) * USERS_PER_PAGE
    batch = matches[start:start + USERS_PER_PAGE]

    text = f"🔎 <b>נמצאו {total} תוצאות עבור '{term}':</b>"

    if kind == 'user':
        keyboard = [[InlineKeyboardButton(f"👤 {m.get('first_name', 'Unknown')} — {m['_id']}", callback_data=f"adm_userview_{m['_id']}_1")] for m in batch]
        back_target = 'adm_users_1'
    else:
        keyboard = [[InlineKeyboardButton(f"💬 {m.get('title', 'Unknown')} — {m['_id']}", callback_data=f"adm_groupview_{m['_id']}_1")] for m in batch]
        back_target = 'adm_groups_1'

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'adm_searchpage_{page - 1}'))
    nav.append(InlineKeyboardButton(f'עמוד {page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'adm_searchpage_{page + 1}'))
    keyboard.append(nav)

    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data=back_target, style=enums.ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(keyboard)


async def _groups_page_text_markup(page):
    groups, total = await db.get_groups_page(page, USERS_PER_PAGE)
    total_pages = max((total + USERS_PER_PAGE - 1) // USERS_PER_PAGE, 1)

    text = f"💬 <b>קבוצות ({total})</b>\n\nבחר קבוצה לצפייה בפרטים:"

    keyboard = [
        [InlineKeyboardButton(f"💬 {g.get('title', 'Unknown')} — {g['_id']}", callback_data=f"adm_groupview_{g['_id']}_{page}")]
        for g in groups
    ] or [[InlineKeyboardButton('אין קבוצות', callback_data='noop')]]

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton('⬅️', callback_data=f'adm_groups_{page - 1}'))
    nav.append(InlineKeyboardButton(f'עמוד {page}/{total_pages}', callback_data='noop'))
    if page < total_pages:
        nav.append(InlineKeyboardButton('➡️', callback_data=f'adm_groups_{page + 1}'))
    keyboard.append(nav)

    keyboard.append([InlineKeyboardButton('🔎 איתור לפי מזהה/שם', callback_data='adm_groups_search', style=enums.ButtonStyle.PRIMARY)])
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

    if action == 'start_index':
        from .index import start_indexing
        await start_indexing(client, message, text_in)
        try:
            await message.delete()
        except Exception:
            pass
        return await client.edit_message_caption(
            panel_chat, panel_msg, caption="✅ האינדוקס הופעל (ראה הודעת סטטוס למעלה).", reply_markup=_channels_menu_markup()
        )

    try:
        await message.delete()
    except Exception:
        pass

    if action == 'watch_channel':
        try:
            chat_id = int(text_in)
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מזהה לא תקין.", reply_markup=_channels_menu_markup())
        await db.add_watched_channel(chat_id)
        return await client.edit_message_caption(
            panel_chat, panel_msg, caption=f"✅ הערוץ <code>{chat_id}</code> נוסף למעקב.", reply_markup=_channels_menu_markup()
        )

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

    if action == 'set_freelimit':
        try:
            limit = int(text_in)
            if limit < 0:
                raise ValueError
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=await _payments_menu_markup())
        await db.set_config('free_daily_limit', limit)
        return await client.edit_message_caption(
            panel_chat, panel_msg, caption=f"✅ מכסת הקבצים החינמית עודכנה ל-<code>{limit}</code> ליום.", reply_markup=await _payments_menu_markup()
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
        if text_in.lstrip('-').isdigit():
            user_id = int(text_in)
            text = await _render_user_info(user_id)
            markup = await _user_actions_markup(user_id, 1)
            return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)

        matches = await db.search_users_by_name(text_in, 50)
        if not matches:
            ADM_INPUT[admin_id] = {'action': 'find_user', 'panel_chat': panel_chat, 'panel_msg': panel_msg}
            markup = InlineKeyboardMarkup([[InlineKeyboardButton('חזרה לרשימה ⋟', callback_data='adm_users_1', style=enums.ButtonStyle.PRIMARY)]])
            return await client.edit_message_caption(
                panel_chat, panel_msg,
                caption=f"❌ לא נמצאו משתמשים עבור '{text_in}'.\n\n🔎 שלח מונח חיפוש נוסף, או חזרה לרשימה:",
                reply_markup=markup
            )
        if len(matches) == 1:
            user_id = matches[0]['_id']
            text = await _render_user_info(user_id)
            markup = await _user_actions_markup(user_id, 1)
            return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)
        ADM_SEARCH[admin_id] = {'kind': 'user', 'term': text_in, 'matches': matches}
        text, markup = _search_results_text_markup(admin_id, 1)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)

    if action == 'find_group':
        if text_in.lstrip('-').isdigit():
            chat_id = int(text_in)
            text = await _render_group_info(client, chat_id)
            ban_info = await db.get_chat_ban_status(chat_id)
            markup = _group_actions_markup(chat_id, 1, bool(ban_info))
            return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)

        matches = await db.search_groups_by_name(text_in, 50)
        if not matches:
            ADM_INPUT[admin_id] = {'action': 'find_group', 'panel_chat': panel_chat, 'panel_msg': panel_msg}
            markup = InlineKeyboardMarkup([[InlineKeyboardButton('חזרה לרשימה ⋟', callback_data='adm_groups_1', style=enums.ButtonStyle.PRIMARY)]])
            return await client.edit_message_caption(
                panel_chat, panel_msg,
                caption=f"❌ לא נמצאו קבוצות עבור '{text_in}'.\n\n🔎 שלח מונח חיפוש נוסף, או חזרה לרשימה:",
                reply_markup=markup
            )
        if len(matches) == 1:
            chat_id = matches[0]['_id']
            text = await _render_group_info(client, chat_id)
            ban_info = await db.get_chat_ban_status(chat_id)
            markup = _group_actions_markup(chat_id, 1, bool(ban_info))
            return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)
        ADM_SEARCH[admin_id] = {'kind': 'group', 'term': text_in, 'matches': matches}
        text, markup = _search_results_text_markup(admin_id, 1)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)

    if action in ('grant_time', 'grant_credits', 'remove_credits', 'send_dm'):
        target_user = state['target_user']
        back_page = state['back_page']
        return_to = state.get('return_to', 'info')
        back_target = f'adm_searchmgmt_{target_user}_{back_page}' if return_to == 'mgmt' else f'adm_userview_{target_user}_{back_page}'

        if action == 'grant_time':
            try:
                hours = float(text_in)
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=_back_markup(back_target))
            await db.extend_unlimited(target_user, hours * 3600)
            note = f"✅ הוענקו {hours:g} שעות ללא הגבלה."
            await _notify_user(client, target_user, f"🎁 <b>קיבלת מתנה מהמנהל!</b>\nהוענקו לך {hours:g} שעות עם קבצים ללא הגבלה.")
        elif action == 'grant_credits':
            try:
                amount = int(text_in)
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=_back_markup(back_target))
            await db.add_search_credits(target_user, amount)
            note = f"✅ הוענקו {amount} קבצים."
            await _notify_user(client, target_user, f"🎁 <b>קיבלת מתנה מהמנהל!</b>\nהוענקו לך {amount} קבצים נוספים.")
        elif action == 'remove_credits':
            try:
                amount = int(text_in)
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=_back_markup(back_target))
            new_val = await db.remove_search_credits(target_user, amount)
            note = f"✅ הוסרו עד {amount} קבצים (יתרה כעת: {new_val})."
        else:
            try:
                await client.send_message(target_user, text_in)
                note = "✅ ההודעה נשלחה למשתמש."
            except Exception as e:
                note = f"❌ שליחה נכשלה: {e}"

        info_text = await _render_user_info(target_user)
        if return_to == 'mgmt':
            markup = _search_mgmt_markup(target_user, back_page)
            caption = f"🎛 <b>ניהול קבצים</b>\n\n{note}\n\n{info_text}"
        else:
            markup = await _user_actions_markup(target_user, back_page)
            caption = f"{note}\n\n{info_text}"
        return await client.edit_message_caption(panel_chat, panel_msg, caption=caption, reply_markup=markup)


# ---------- callbacks ----------

@Client.on_callback_query(filters.regex(r"^adm_"))
async def admin_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if data not in ("adm_confirm_yes", "adm_confirm_no"):
        ADM_INPUT.pop(admin_id, None)

    if data == "adm_confirm_yes":
        pending = PENDING_CONFIRM.pop(admin_id, None)
        if not pending:
            return await query.answer("הפעולה פגה.", show_alert=True)
        return await pending['confirm']()

    if data == "adm_confirm_no":
        pending = PENDING_CONFIRM.pop(admin_id, None)
        if not pending:
            return await send_admin_panel(query.message, is_edit=True)
        return await pending['cancel']()

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
        label = "המשתמש" if kind == 'users' else "הקבוצה"

        async def _do_unban1():
            if kind == 'users':
                await db.unban_user(target_id)
            else:
                await db.unban_chat(target_id)
            text, markup = await _banlist_text_markup(kind, page)
            await query.message.edit_caption(f"✅ שוחרר: <code>{target_id}</code>\n\n{text}", reply_markup=markup)

        async def _cancel_unban1():
            text, markup = await _banlist_text_markup(kind, page)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, f"לשחרר את {label} <code>{target_id}</code> מהחסימה?", _do_unban1, _cancel_unban1)

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

    if data == "adm_payments_menu":
        return await query.message.edit_caption("💰 <b>מערכת תשלומים</b>\n\nבחר הגדרה:", reply_markup=await _payments_menu_markup())

    if data == "adm_toggle_payments":
        from .pay import is_payments_enabled
        enabled = await is_payments_enabled()
        await db.set_config('payments_enabled', not enabled)
        return await query.message.edit_caption("💰 <b>מערכת תשלומים</b>\n\nבחר הגדרה:", reply_markup=await _payments_menu_markup())

    if data == "adm_set_freelimit":
        return await _start_input(query, "set_freelimit")

    if data == "adm_words_menu":
        text, markup = await _words_menu_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_words_add":
        return await _start_input(query, "add_word")

    if data == "adm_words_del":
        return await _start_input(query, "del_word")

    if data == "adm_users_search":
        return await _start_input(query, "find_user")

    if data.startswith("adm_searchpage_"):
        page = int(data[len("adm_searchpage_"):])
        text, markup = _search_results_text_markup(admin_id, page)
        if not text:
            return await query.answer("הפעולה פגה, חפש שוב.", show_alert=True)
        return await query.message.edit_caption(text, reply_markup=markup)

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

        async def _do_toggle():
            if is_ban:
                await db.ban_user(user_id, "נחסם דרך פרטי המשתמש")
            else:
                await db.unban_user(user_id)
            text = await _render_user_info(user_id)
            markup = await _user_actions_markup(user_id, page)
            await query.message.edit_caption(text, reply_markup=markup)

        if not is_ban:
            return await _do_toggle()

        async def _cancel_toggle():
            text = await _render_user_info(user_id)
            markup = await _user_actions_markup(user_id, page)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, f"לחסום את המשתמש <code>{user_id}</code>?", _do_toggle, _cancel_toggle)

    if data.startswith("adm_history_"):
        rest = data[len("adm_history_"):]
        user_id_str, _, page_str = rest.partition('_')
        user_id = int(user_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        rows = await db.get_user_search_history(user_id, 15)
        body = "\n".join(f"• <code>{r['query']}</code>" for r in rows) if rows else "אין היסטוריית חיפושים."
        text = f"📚 <b>היסטוריית חיפושים</b>\n\n{body}"
        return await query.message.edit_caption(text, reply_markup=_back_markup(f'adm_userview_{user_id}_{page}'))

    if data.startswith("adm_searchmgmt_"):
        user_id_str, _, page_str = data[len("adm_searchmgmt_"):].partition('_')
        user_id, page = int(user_id_str), int(page_str) if page_str.isdigit() else 1
        text = await _render_user_info(user_id)
        markup = _search_mgmt_markup(user_id, page)
        return await query.message.edit_caption(f"🎛 <b>ניהול קבצים</b>\n\n{text}", reply_markup=markup)

    if data.startswith("adm_grantt_"):
        user_id_str, _, page_str = data[len("adm_grantt_"):].partition('_')
        return await _start_user_action(query, 'grant_time', int(user_id_str), int(page_str) if page_str.isdigit() else 1, return_to='mgmt')

    if data.startswith("adm_grantc_"):
        user_id_str, _, page_str = data[len("adm_grantc_"):].partition('_')
        return await _start_user_action(query, 'grant_credits', int(user_id_str), int(page_str) if page_str.isdigit() else 1, return_to='mgmt')

    if data.startswith("adm_revokec_"):
        user_id_str, _, page_str = data[len("adm_revokec_"):].partition('_')
        return await _start_user_action(query, 'remove_credits', int(user_id_str), int(page_str) if page_str.isdigit() else 1, return_to='mgmt')

    if data.startswith("adm_revoket_"):
        user_id_str, _, page_str = data[len("adm_revoket_"):].partition('_')
        user_id, page = int(user_id_str), int(page_str) if page_str.isdigit() else 1
        await db.revoke_unlimited(user_id)
        await _notify_user(client, user_id, "ℹ️ מנוי הזמן ללא הגבלה שלך בוטל על ידי המנהל.")
        text = await _render_user_info(user_id)
        markup = _search_mgmt_markup(user_id, page)
        return await query.message.edit_caption(f"✅ מנוי הזמן בוטל.\n\n{text}", reply_markup=markup)

    if data.startswith("adm_resetfree_"):
        user_id_str, _, page_str = data[len("adm_resetfree_"):].partition('_')
        user_id, page = int(user_id_str), int(page_str) if page_str.isdigit() else 1
        today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
        await db.reset_free_usage(user_id, today)
        text = await _render_user_info(user_id)
        markup = _search_mgmt_markup(user_id, page)
        return await query.message.edit_caption(f"✅ הקבצים החינמיים היום אופסו.\n\n{text}", reply_markup=markup)

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

    if data == "adm_groups_search":
        return await _start_input(query, "find_group")

    if data.startswith("adm_groupview_"):
        rest = data[len("adm_groupview_"):]
        chat_id_str, _, page_str = rest.partition('_')
        try:
            chat_id = int(chat_id_str)
        except ValueError:
            return
        page = int(page_str) if page_str.isdigit() else 1
        text = await _render_group_info(client, chat_id)
        ban_info = await db.get_chat_ban_status(chat_id)
        markup = _group_actions_markup(chat_id, page, bool(ban_info))
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_gban_") or data.startswith("adm_gunban_"):
        is_ban = data.startswith("adm_gban_")
        rest = data[len("adm_gban_"):] if is_ban else data[len("adm_gunban_"):]
        chat_id_str, _, page_str = rest.partition('_')
        chat_id = int(chat_id_str)
        page = int(page_str) if page_str.isdigit() else 1

        async def _do_gtoggle():
            if is_ban:
                await db.ban_chat(chat_id, "נחסמה דרך פרטי הקבוצה")
            else:
                await db.unban_chat(chat_id)
            text = await _render_group_info(client, chat_id)
            markup = _group_actions_markup(chat_id, page, is_ban)
            await query.message.edit_caption(text, reply_markup=markup)

        if not is_ban:
            return await _do_gtoggle()

        async def _cancel_gtoggle():
            text = await _render_group_info(client, chat_id)
            ban_info = await db.get_chat_ban_status(chat_id)
            markup = _group_actions_markup(chat_id, page, bool(ban_info))
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, f"לחסום את הקבוצה <code>{chat_id}</code>?", _do_gtoggle, _cancel_gtoggle)

    if data.startswith("adm_gleave_"):
        chat_id_str, _, page_str = data[len("adm_gleave_"):].partition('_')
        chat_id = int(chat_id_str)
        page = int(page_str) if page_str.isdigit() else 1

        async def _do_gleave():
            try:
                await client.leave_chat(chat_id)
                await db.remove_group(chat_id)
                note = "✅ הבוט עזב את הקבוצה והוסרה מהרשימה."
            except Exception as e:
                note = f"❌ שגיאה: {e}"
            text, markup = await _groups_page_text_markup(page)
            await query.message.edit_caption(f"{note}\n\n{text}", reply_markup=markup)

        async def _cancel_gleave():
            text, markup = await _groups_page_text_markup(page)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, "הבוט יעזוב את הקבוצה ויידרש להזמין אותו מחדש כדי לחזור. להמשיך?", _do_gleave, _cancel_gleave)

    if data.startswith("adm_groups_"):
        try:
            page = int(data[len("adm_groups_"):])
        except ValueError:
            page = 1
        text, markup = await _groups_page_text_markup(page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_channels_menu":
        return await query.message.edit_caption("📡 <b>ערוצים</b>\n\nבחר פעולה:", reply_markup=_channels_menu_markup())

    if data == "adm_ch_add":
        return await _start_input(query, "watch_channel")

    if data == "adm_ch_index":
        return await _start_input(query, "start_index")

    if data == "adm_ch_list":
        text, markup = await _channels_list_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_ch_rm_"):
        chat_id = int(data[len("adm_ch_rm_"):])

        async def _do_ch_rm():
            await db.remove_watched_channel(chat_id)
            text, markup = await _channels_list_text_markup()
            await query.message.edit_caption(f"✅ הוסר: <code>{chat_id}</code>\n\n{text}", reply_markup=markup)

        async def _cancel_ch_rm():
            text, markup = await _channels_list_text_markup()
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, f"להסיר את הערוץ <code>{chat_id}</code> מהמעקב?", _do_ch_rm, _cancel_ch_rm)

    if data == "adm_ch_status":
        from .index import INDEX_PROGRESS
        running = {cid: p for cid, p in INDEX_PROGRESS.items() if p.get('running')}
        if not running:
            text = "📊 <b>סטטוס אינדוקס</b>\n\nאין אינדוקס פעיל כרגע."
            keyboard = []
        else:
            blocks = []
            keyboard = []
            for cid, p in running.items():
                elapsed = int(time.time() - p['started_at'])
                span = max(p['end'] - p['start'], 1)
                pct = ((p['current'] - p['start']) / span) * 100
                blocks.append(
                    f"📡 <b>{p['title']}</b>\n"
                    f"התקדמות: {p['current']}/{p['end']} ({pct:.0f}%)\n"
                    f"נשמרו: {p['saved']} | כפולים: {p['dups']}\n"
                    f"זמן שחלף: {elapsed}s"
                )
                keyboard.append([InlineKeyboardButton(f"🛑 עצור: {p['title']}", callback_data=f"stop_idx_{cid}")])
            text = "📊 <b>סטטוס אינדוקס חי</b>\n\n" + "\n\n".join(blocks)
        keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_channels_menu', style=enums.ButtonStyle.PRIMARY)])
        return await query.message.edit_caption(text, reply_markup=InlineKeyboardMarkup(keyboard))

    if data == "adm_stars":
        from .pay import build_purchase_stats_text
        text = await build_purchase_stats_text()
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('⚙️ הגדרות תשלומים', callback_data='adm_payments_menu', style=enums.ButtonStyle.PRIMARY)],
            [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
        ])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_stats":
        from .stats import build_stats_text
        text = await build_stats_text()
        return await query.message.edit_caption(text, reply_markup=_back_markup())

    if data == "adm_popular":
        text, markup = await _popular_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_popular_clear_ask":
        async def _do_clear():
            await db.clear_popular_searches()
            text, markup = await _popular_text_markup()
            await query.message.edit_caption(text, reply_markup=markup)

        async def _cancel_clear():
            text, markup = await _popular_text_markup()
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, "למחוק את כל היסטוריית החיפושים הפופולריים? לא ניתן לשחזר.", _do_clear, _cancel_clear)

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
    back_targets = {'ban': 'adm_ban_menu', 'settings': 'adm_settings', 'words': 'adm_words_menu', 'users': 'adm_users_1', 'groups': 'adm_groups_1', 'channels': 'adm_channels_menu', 'payments': 'adm_payments_menu'}
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=back_targets[info['back']])]])
    text = f"✏️ <b>{info['label']}</b>\n\n{info['prompt']}"
    await query.message.edit_caption(text, reply_markup=markup)
