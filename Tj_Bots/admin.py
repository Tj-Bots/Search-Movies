import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ChatPrivileges
from config import ADMINS, PHOTO_URL, AUTH_CHANNEL_FORCE
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

ADM_INPUT = {}
ADM_SEARCH = {}
SUBADMIN_WIZARD = {}
USERS_PER_PAGE = 10

DURATION_PRESETS = {
    'perm': {'label': 'קבוע (לא פג תוקף)', 'seconds': None},
    'day': {'label': 'יום אחד', 'seconds': 86400},
    'week': {'label': 'שבוע', 'seconds': 7 * 86400},
    'month': {'label': 'חודש', 'seconds': 30 * 86400},
}

PERMISSIONS_CATALOG = {
    'perm_broadcast': {'label': '📢 שידור הודעות', 'prefixes': ['bc']},
    'perm_ban': {'label': '🚫 ניהול חסימות', 'prefixes': ['adm_ban', 'adm_unban']},
    'perm_users': {'label': '👥 משתמשים', 'prefixes': [
        'adm_users', 'adm_userview', 'adm_searchmgmt', 'adm_grant', 'adm_revoke',
        'adm_resetfree_', 'adm_history_', 'adm_dm_', 'adm_ban2_', 'adm_unban2_', 'adm_searchpage_',
    ]},
    'perm_groups': {'label': '💬 קבוצות', 'prefixes': ['adm_groups', 'adm_groupview', 'adm_gleave', 'adm_gadmins', 'adm_gdemote', 'adm_gpromote', 'adm_searchpage_']},
    'perm_settings': {'label': '⚙️ הגדרות מערכת', 'prefixes': ['adm_settings', 'adm_toggle_lock', 'adm_toggle_auth', 'adm_set_channel', 'adm_words']},
    'perm_payments': {'label': '💰 מערכת תשלומים', 'prefixes': ['adm_payments', 'adm_toggle_payments', 'adm_set_freelimit', 'adm_set_refratio', 'adm_packages', 'adm_pkg', 'adm_resetfree_all']},
    'perm_stats': {'label': '📊 סטטיסטיקות', 'prefixes': ['adm_stats']},
    'perm_popular': {'label': '🔥 חיפושים פופולריים', 'prefixes': ['adm_popular']},
    'perm_load': {'label': '📈 מד עומס שרת', 'prefixes': ['adm_load']},
    'perm_stars': {'label': '⭐ תומכים בכוכבים', 'prefixes': ['adm_stars']},
    'perm_channels': {'label': '📡 ערוצים', 'prefixes': ['adm_ch_', 'adm_channels']},
    'perm_appeals': {'label': '🔓 בקשות ערעור', 'prefixes': ['adm_appeal']},
}

EXEMPT_CALLBACKS = ("adm_confirm_yes", "adm_confirm_no", "adm_home", "noop")


def _get_perms_for_callback(data):
    best_len = -1
    perms = set()
    for perm_key, info in PERMISSIONS_CATALOG.items():
        for prefix in info['prefixes']:
            if data == prefix or data.startswith(prefix):
                if len(prefix) > best_len:
                    best_len = len(prefix)
                    perms = {perm_key}
                elif len(prefix) == best_len:
                    perms.add(perm_key)
    return perms


async def has_permission(user_id, data):
    if user_id in ADMINS:
        return True
    if data in EXEMPT_CALLBACKS:
        return True
    sub = await db.get_sub_admin(user_id)
    if not sub:
        return False
    perms_needed = _get_perms_for_callback(data)
    if not perms_needed:
        return False
    return bool(perms_needed & set(sub.get('permissions', [])))

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
    'set_refratio': {'label': 'קביעת יחס הזמנות לבונוס', 'prompt': "שלח כמה הזמנות נדרשות עבור קובץ בונוס אחד ליום (מספר בלבד).\nלדוגמה: <code>3</code>", 'back': 'payments'},
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

async def _panel_markup(user_id=None):
    all_rows = [
        ('perm_broadcast', [InlineKeyboardButton('📢 שידור הודעות', callback_data='bc_menu', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_ban', [InlineKeyboardButton('🚫 ניהול חסימות', callback_data='adm_ban_menu', style=enums.ButtonStyle.DANGER)]),
        ('perm_users', [InlineKeyboardButton('👥 משתמשים', callback_data='adm_users_1', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_groups', [InlineKeyboardButton('💬 קבוצות', callback_data='adm_groups_1', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_settings', [InlineKeyboardButton('⚙️ הגדרות מערכת', callback_data='adm_settings', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_stats', [InlineKeyboardButton('📊 סטטיסטיקות', callback_data='adm_stats', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_popular', [InlineKeyboardButton('🔥 חיפושים פופולריים', callback_data='adm_popular', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_load', [InlineKeyboardButton('📈 מד עומס שרת', callback_data='adm_load', style=enums.ButtonStyle.PRIMARY)]),
        ('perm_stars', [InlineKeyboardButton('⭐ תומכים בכוכבים', callback_data='adm_stars', style=enums.ButtonStyle.SUCCESS)]),
        ('perm_channels', [InlineKeyboardButton('📡 ערוצים', callback_data='adm_channels_menu', style=enums.ButtonStyle.PRIMARY)]),
    ]

    is_super = user_id is None or user_id in ADMINS
    if is_super:
        keyboard = [row for _, row in all_rows]
        keyboard.append([InlineKeyboardButton('👥 אדמינים משניים', callback_data='adm_subadmins_menu', style=enums.ButtonStyle.SUCCESS)])
    else:
        sub = await db.get_sub_admin(user_id)
        perms = set(sub.get('permissions', [])) if sub else set()
        keyboard = [row for perm_key, row in all_rows if perm_key in perms]
        if not keyboard:
            keyboard = [[InlineKeyboardButton('אין לך הרשאות פעילות בפאנל', callback_data='noop')]]

    keyboard.append([InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(keyboard)


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


async def _packages_menu_text_markup():
    from .pay import get_all_packages
    packages = await get_all_packages(include_inactive=True)
    text = "🎟 <b>ניהול חבילות ומחירים</b>\n\nלחץ על חבילה לעריכה:"
    keyboard = []
    for key, p in packages.items():
        icon = '🟢' if p['active'] else '🔴'
        star = '✨' if p['custom'] else ''
        keyboard.append([InlineKeyboardButton(f"{icon} {p['label']} {star}", callback_data=f"adm_pkgview_{key}")])
    keyboard.append([InlineKeyboardButton('➕ הוספת חבילת זמן', callback_data='adm_pkgaddtime'),
                      InlineKeyboardButton('➕ הוספת חבילת קבצים', callback_data='adm_pkgaddcount')])
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_payments_menu', style=enums.ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(keyboard)


async def _pkg_view_text_markup(key):
    from .pay import get_all_packages
    packages = await get_all_packages(include_inactive=True)
    p = packages.get(key)
    if not p:
        return None, None
    kind_label = 'חבילת זמן (ללא הגבלה)' if p['kind'] == 'time' else 'חבילת קבצים'
    text = (
        f"🎟 <b>{p['label']}</b>\n\n"
        f"<blockquote>"
        f"סוג: {kind_label}\n"
        f"מחיר: <b>{p['stars']}</b> כוכבים\n"
        f"סטטוס: {'🟢 פעילה' if p['active'] else '🔴 כבויה'}\n"
        f"מקור: {'✨ מותאמת אישית' if p['custom'] else 'ברירת מחדל'}"
        f"</blockquote>"
    )
    toggle_label = '🔴 כבה חבילה' if p['active'] else '🟢 הפעל חבילה'
    keyboard = [
        [InlineKeyboardButton('✏️ שנה מחיר', callback_data=f'adm_pkgprice_{key}', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(toggle_label, callback_data=f'adm_pkgtoggle_{key}', style=enums.ButtonStyle.DANGER if p['active'] else enums.ButtonStyle.SUCCESS)],
    ]
    if p['custom']:
        keyboard.append([InlineKeyboardButton('🗑 מחק חבילה', callback_data=f'adm_pkgdel_{key}_ask', style=enums.ButtonStyle.DANGER)])
    keyboard.append([InlineKeyboardButton('חזרה לרשימה ⋟', callback_data='adm_packages_menu', style=enums.ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(keyboard)


async def _payments_menu_markup():
    from .pay import is_payments_enabled, get_free_daily_limit
    enabled = await is_payments_enabled()
    limit = await get_free_daily_limit()
    pay_label = '💰 תשלומים בכוכבים: מופעל' if enabled else '🆓 תשלומים בכוכבים: כבוי (הכל חינם וללא הגבלה)'
    ratio = await db.get_config('referral_ratio', 3)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(pay_label, callback_data='adm_toggle_payments', style=enums.ButtonStyle.SUCCESS if enabled else enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton(f'✏️ קבצים חינמיים ליום: {limit}', callback_data='adm_set_freelimit', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(f'🔗 יחס הזמנות לבונוס: {ratio}', callback_data='adm_set_refratio', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🎟 ניהול חבילות ומחירים', callback_data='adm_packages_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🔄 איפוס מכסה יומית לכולם', callback_data='adm_resetfree_all_ask', style=enums.ButtonStyle.DANGER)],
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


async def send_admin_panel(message, is_edit=False, user_id=None):
    if user_id is None:
        user_id = message.from_user.id if message.from_user else None
    text = "🛠 <b>פאנל ניהול</b>\n\nבחר פעולה:"
    markup = await _panel_markup(user_id)
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=text), reply_markup=markup)
    else:
        await message.reply_photo(PHOTO_URL, caption=text, reply_markup=markup, quote=True)


async def _is_admin_or_sub(_, __, update):
    user = update.from_user
    if not user:
        return False
    if user.id in ADMINS:
        return True
    return await db.get_sub_admin(user.id) is not None


admin_or_sub_filter = filters.create(_is_admin_or_sub)


@Client.on_message(filters.command("admin") & admin_or_sub_filter)
async def admin_command(client, message):
    await send_admin_panel(message)


# ---------- users browser ----------

async def _render_user_info(user_id):
    from .pay import get_free_daily_limit
    user = await db.find_user(user_id)
    if not user:
        return f"❌ המשתמש <code>{user_id}</code> לא נמצא במסד הנתונים."

    quota = await db.get_search_quota(user_id)
    daily_limit = await get_free_daily_limit() + quota['extra_daily_limit']
    ref_count = await db.get_referral_count(user_id)
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
        f"🔗 הזמנות: <b>{ref_count}</b> (בונוס: <b>+{quota['extra_daily_limit']}</b> ליום)\n"
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
        [InlineKeyboardButton('👥 ניהול מנהלים', callback_data=f'adm_gadmins_{chat_id}_{page}', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('חזרה לרשימה ⋟', callback_data=f'adm_groups_{page}', style=enums.ButtonStyle.PRIMARY)],
    ])


MODERATOR_PRIVILEGES = ChatPrivileges(
    can_manage_chat=True, can_delete_messages=True, can_restrict_members=True,
    can_invite_users=True, can_pin_messages=True, can_manage_video_chats=True,
)


async def _render_group_admins(client, chat_id, page):
    try:
        admins = []
        async for m in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            admins.append(m)
    except Exception as e:
        return f"❌ לא ניתן לקבל את רשימת המנהלים: {e}", _back_markup(f'adm_groupview_{chat_id}_{page}')

    keyboard = []
    for m in admins:
        if m.user.is_bot:
            continue
        name = m.user.first_name or str(m.user.id)
        if m.status == enums.ChatMemberStatus.OWNER:
            keyboard.append([InlineKeyboardButton(f"👑 {name} (יוצר הקבוצה)", callback_data='noop')])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ הורד מניהול: {name}", callback_data=f'adm_gdemote_{chat_id}_{m.user.id}_{page}_ask', style=enums.ButtonStyle.DANGER)])

    keyboard.append([InlineKeyboardButton('➕ מנה מנהל חדש', callback_data=f'adm_gpromote_{chat_id}_{page}', style=enums.ButtonStyle.SUCCESS)])
    keyboard.append([InlineKeyboardButton('חזרה לקבוצה ⋟', callback_data=f'adm_groupview_{chat_id}_{page}', style=enums.ButtonStyle.PRIMARY)])
    text = "👥 <b>מנהלי הקבוצה</b>\n\nלחץ להורדה מניהול, או הוסף מנהל חדש:"
    return text, InlineKeyboardMarkup(keyboard)


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


@Client.on_message(admin_or_sub_filter & filters.create(_is_awaiting_input))
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
                appeal_url = f"https://t.me/{client.me.username}?start=appeal_{target_id}"
                appeal_markup = InlineKeyboardMarkup([[InlineKeyboardButton('📝 הגש ערעור', url=appeal_url)]])
                await client.send_message(target_id, f"🚫 קבוצה זו נחסמה.\nסיבה: {reason}", reply_markup=appeal_markup)
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

    if action == 'set_refratio':
        try:
            ratio = int(text_in)
            if ratio < 1:
                raise ValueError
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר לא תקין.", reply_markup=await _payments_menu_markup())
        await db.set_config('referral_ratio', ratio)
        return await client.edit_message_caption(
            panel_chat, panel_msg, caption=f"✅ יחס ההזמנות עודכן: <code>{ratio}</code> הזמנות לקובץ בונוס אחד ליום.", reply_markup=await _payments_menu_markup()
        )

    if action == 'gpromote':
        chat_id = state['chat_id']
        page = state['back_page']
        try:
            target_uid = int(text_in)
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מזהה לא תקין.", reply_markup=_back_markup(f'adm_gadmins_{chat_id}_{page}'))
        try:
            await client.promote_chat_member(chat_id, target_uid, privileges=MODERATOR_PRIVILEGES)
            note = f"✅ המשתמש <code>{target_uid}</code> מונה למנהל בקבוצה."
        except Exception as e:
            note = f"❌ שגיאה: {e}"
        text, markup = await _render_group_admins(client, chat_id, page)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"{note}\n\n{text}", reply_markup=markup)

    if action == 'subadmin_add_id':
        try:
            target_id = int(text_in)
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מזהה לא תקין.", reply_markup=_back_markup('adm_subadmins_menu'))
        if target_id in ADMINS:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ המשתמש הזה כבר מנהל ראשי.", reply_markup=_back_markup('adm_subadmins_menu'))
        SUBADMIN_WIZARD[admin_id] = {'target': target_id, 'perms': set()}
        return await client.edit_message_caption(
            panel_chat, panel_msg,
            caption=f"🎛 <b>בחר הרשאות עבור <code>{target_id}</code>:</b>\n\nלחץ על הרשאה כדי לסמן/לבטל, ואז 'המשך'.",
            reply_markup=_subadmin_perms_markup(admin_id)
        )

    if action == 'pkg_price':
        from .pay import set_package_price
        key = state.get('pkg_key')
        try:
            stars = int(text_in)
            if stars < 1:
                raise ValueError
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מחיר לא תקין.", reply_markup=_back_markup(f'adm_pkgview_{key}'))
        await set_package_price(key, stars)
        text, markup = await _pkg_view_text_markup(key)
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"✅ המחיר עודכן.\n\n{text}", reply_markup=markup)

    if action == 'pkg_add_time':
        from .pay import add_custom_time_package
        parts = [p.strip() for p in text_in.split(',')]
        if len(parts) != 3:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ פורמט לא תקין. יש לשלוח: שם,שעות (או 'לנצח'),מחיר בכוכבים", reply_markup=_back_markup('adm_packages_menu'))
        name, hours_str, stars_str = parts
        try:
            stars = int(stars_str)
            if stars < 1:
                raise ValueError
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מחיר לא תקין.", reply_markup=_back_markup('adm_packages_menu'))
        lifetime = hours_str in ('לנצח', 'infinite', 'forever')
        hours = None
        if not lifetime:
            try:
                hours = float(hours_str)
                if hours <= 0:
                    raise ValueError
            except ValueError:
                return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספר שעות לא תקין.", reply_markup=_back_markup('adm_packages_menu'))
        await add_custom_time_package(name, stars, hours=hours, lifetime=lifetime)
        text, markup = await _packages_menu_text_markup()
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"✅ החבילה '{name}' נוספה.\n\n{text}", reply_markup=markup)

    if action == 'pkg_add_count':
        from .pay import add_custom_count_package
        parts = [p.strip() for p in text_in.split(',')]
        if len(parts) != 3:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ פורמט לא תקין. יש לשלוח: שם,כמות קבצים,מחיר בכוכבים", reply_markup=_back_markup('adm_packages_menu'))
        name, amount_str, stars_str = parts
        try:
            amount = int(amount_str)
            stars = int(stars_str)
            if amount < 1 or stars < 1:
                raise ValueError
        except ValueError:
            return await client.edit_message_caption(panel_chat, panel_msg, caption="❌ מספרים לא תקינים.", reply_markup=_back_markup('adm_packages_menu'))
        await add_custom_count_package(name, amount, stars)
        text, markup = await _packages_menu_text_markup()
        return await client.edit_message_caption(panel_chat, panel_msg, caption=f"✅ החבילה '{name}' נוספה.\n\n{text}", reply_markup=markup)

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


# ---------- sub-admins ----------

async def _subadmins_list_text_markup():
    subs = await db.get_all_sub_admins()
    text = "👥 <b>אדמינים משניים</b>\n\n"
    keyboard = []
    if subs:
        for s in subs:
            status = 'קבוע' if s.get('is_permanent') else 'זמני'
            keyboard.append([InlineKeyboardButton(f"👤 {s['_id']} — {len(s.get('permissions', []))} הרשאות ({status})", callback_data=f"adm_subadmin_view_{s['_id']}")])
        text += "לחץ על אדמין לצפייה בפרטים או הסרה:"
    else:
        text += "אין כרגע אדמינים משניים."
    keyboard.append([InlineKeyboardButton('➕ הוספת אדמין משני', callback_data='adm_subadmin_add', style=enums.ButtonStyle.SUCCESS)])
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)])
    return text, InlineKeyboardMarkup(keyboard)


async def _subadmin_view_text_markup(user_id):
    sub = await db.get_sub_admin(user_id)
    if not sub:
        return None, None
    if sub.get('is_permanent'):
        expiry_line = 'קבוע (לא פג תוקף)'
    else:
        remaining = sub.get('expire_at', 0) - time.time()
        hours = max(int(remaining // 3600), 0)
        expiry_line = f"עוד כ-{hours} שעות"
    perm_labels = "\n".join(f"• {PERMISSIONS_CATALOG[p]['label']}" for p in sub.get('permissions', []) if p in PERMISSIONS_CATALOG)
    text = (
        f"👤 <b>אדמין משני: <code>{user_id}</code></b>\n\n"
        f"<blockquote>⏳ תוקף: {expiry_line}\n\n<b>הרשאות:</b>\n{perm_labels or 'אין הרשאות'}</blockquote>"
    )
    keyboard = [
        [InlineKeyboardButton('🗑 הסר אדמין משני', callback_data=f'adm_subadmin_remove_{user_id}_ask', style=enums.ButtonStyle.DANGER)],
        [InlineKeyboardButton('חזרה לרשימה ⋟', callback_data='adm_subadmins_menu', style=enums.ButtonStyle.PRIMARY)],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def _subadmin_perms_markup(admin_id):
    wizard = SUBADMIN_WIZARD[admin_id]
    keyboard = []
    for perm_key, info in PERMISSIONS_CATALOG.items():
        mark = '☑️' if perm_key in wizard['perms'] else '⬜️'
        keyboard.append([InlineKeyboardButton(f"{mark} {info['label']}", callback_data=f'adm_subadmin_permtoggle_{perm_key}')])
    keyboard.append([InlineKeyboardButton('✅ המשך', callback_data='adm_subadmin_perms_done', style=enums.ButtonStyle.SUCCESS)])
    keyboard.append([InlineKeyboardButton('❌ ביטול', callback_data='adm_subadmins_menu', style=enums.ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(keyboard)


def _subadmin_duration_markup():
    keyboard = [[InlineKeyboardButton(info['label'], callback_data=f'adm_subadmin_duration_{key}')] for key, info in DURATION_PRESETS.items()]
    keyboard.append([InlineKeyboardButton('❌ ביטול', callback_data='adm_subadmins_menu', style=enums.ButtonStyle.DANGER)])
    return InlineKeyboardMarkup(keyboard)


# ---------- callbacks ----------

@Client.on_callback_query(filters.regex(r"^adm_") & admin_or_sub_filter)
async def admin_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if not await has_permission(admin_id, data):
        return await query.answer("⛔ אין לך הרשאה לפעולה זו.", show_alert=True)

    if data not in ("adm_confirm_yes", "adm_confirm_no"):
        ADM_INPUT.pop(admin_id, None)

    if data.startswith("adm_appeal_approve_"):
        chat_id = int(data[len("adm_appeal_approve_"):])
        await db.unban_chat(chat_id)
        return await query.message.edit_text(f"✅ הקבוצה <code>{chat_id}</code> שוחררה מהחסימה.", reply_markup=None)

    if data == "adm_confirm_yes":
        pending = PENDING_CONFIRM.pop(admin_id, None)
        if not pending:
            return await query.answer("הפעולה פגה.", show_alert=True)
        return await pending['confirm']()

    if data == "adm_confirm_no":
        pending = PENDING_CONFIRM.pop(admin_id, None)
        if not pending:
            return await send_admin_panel(query.message, is_edit=True, user_id=admin_id)
        return await pending['cancel']()

    if data == "adm_home":
        ADM_INPUT.pop(admin_id, None)
        return await send_admin_panel(query.message, is_edit=True, user_id=admin_id)

    if data == "adm_subadmins_menu":
        SUBADMIN_WIZARD.pop(admin_id, None)
        text, markup = await _subadmins_list_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_subadmin_add":
        ADM_INPUT[admin_id] = {'action': 'subadmin_add_id', 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='adm_subadmins_menu')]])
        return await query.message.edit_caption("✏️ <b>הוספת אדמין משני</b>\n\nשלח את מזהה המשתמש (ID) שברצונך למנות.", reply_markup=markup)

    if data.startswith("adm_subadmin_view_"):
        target_id = int(data[len("adm_subadmin_view_"):])
        text, markup = await _subadmin_view_text_markup(target_id)
        if not text:
            return await query.answer("❌ האדמין לא נמצא.", show_alert=True)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_subadmin_remove_") and data.endswith("_ask"):
        target_id = int(data[len("adm_subadmin_remove_"):-len("_ask")])

        async def _do_remove():
            await db.remove_sub_admin(target_id)
            text, markup = await _subadmins_list_text_markup()
            await query.message.edit_caption(f"✅ האדמין הוסר.\n\n{text}", reply_markup=markup)

        async def _cancel_remove():
            text, markup = await _subadmin_view_text_markup(target_id)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, f"להסיר את <code>{target_id}</code> מרשימת האדמינים המשניים?", _do_remove, _cancel_remove)

    if data.startswith("adm_subadmin_permtoggle_"):
        perm_key = data[len("adm_subadmin_permtoggle_"):]
        wizard = SUBADMIN_WIZARD.get(admin_id)
        if not wizard:
            return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)
        if perm_key in wizard['perms']:
            wizard['perms'].discard(perm_key)
        else:
            wizard['perms'].add(perm_key)
        return await query.message.edit_reply_markup(_subadmin_perms_markup(admin_id))

    if data == "adm_subadmin_perms_done":
        wizard = SUBADMIN_WIZARD.get(admin_id)
        if not wizard:
            return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)
        if not wizard['perms']:
            return await query.answer("❌ יש לבחור לפחות הרשאה אחת.", show_alert=True)
        return await query.message.edit_caption("⏳ <b>בחר תוקף להרשאה:</b>", reply_markup=_subadmin_duration_markup())

    if data.startswith("adm_subadmin_duration_"):
        key = data[len("adm_subadmin_duration_"):]
        wizard = SUBADMIN_WIZARD.pop(admin_id, None)
        if not wizard or key not in DURATION_PRESETS:
            return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)
        seconds = DURATION_PRESETS[key]['seconds']
        is_permanent = seconds is None
        expire_at = None if is_permanent else time.time() + seconds
        target_id = wizard['target']
        await db.add_sub_admin(target_id, list(wizard['perms']), expire_at=expire_at, is_permanent=is_permanent)
        try:
            perm_labels = "\n".join(f"• {PERMISSIONS_CATALOG[p]['label']}" for p in wizard['perms'])
            await client.send_message(
                target_id,
                f"🎉 <b>מונית לאדמין משני בבוט!</b>\n\nההרשאות שלך:\n{perm_labels}\n\nהשתמש בפקודה /admin כדי לגשת לפאנל."
            )
        except Exception:
            pass
        text, markup = await _subadmins_list_text_markup()
        return await query.message.edit_caption(f"✅ האדמין המשני נוסף בהצלחה.\n\n{text}", reply_markup=markup)

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

    if data == "adm_set_refratio":
        return await _start_input(query, "set_refratio")

    if data == "adm_resetfree_all_ask":
        async def _do_resetfree_all():
            today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
            count = await db.reset_all_free_usage(today)
            await query.message.edit_caption(f"✅ המכסה היומית אופסה ל-{count} משתמשים.\n\n💰 <b>מערכת תשלומים</b>\n\nבחר הגדרה:", reply_markup=await _payments_menu_markup())

        async def _cancel_resetfree_all():
            await query.message.edit_caption("💰 <b>מערכת תשלומים</b>\n\nבחר הגדרה:", reply_markup=await _payments_menu_markup())

        return await _ask_confirm(query, "לאפס את המכסה היומית החינמית לכל המשתמשים בבוט?", _do_resetfree_all, _cancel_resetfree_all)

    if data == "adm_packages_menu":
        text, markup = await _packages_menu_text_markup()
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_pkgaddtime":
        admin_id = query.from_user.id
        ADM_INPUT[admin_id] = {'action': 'pkg_add_time', 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='adm_packages_menu')]])
        text = (
            "✏️ <b>הוספת חבילת זמן</b>\n\n"
            "שלח בפורמט: <code>שם החבילה,שעות,מחיר בכוכבים</code>\n"
            "לחבילת \"לכל החיים\" כתוב 'לנצח' במקום שעות.\n"
            "לדוגמה: <code>יומיים ללא הגבלה,48,300</code>"
        )
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "adm_pkgaddcount":
        admin_id = query.from_user.id
        ADM_INPUT[admin_id] = {'action': 'pkg_add_count', 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='adm_packages_menu')]])
        text = (
            "✏️ <b>הוספת חבילת קבצים</b>\n\n"
            "שלח בפורמט: <code>שם החבילה,כמות קבצים,מחיר בכוכבים</code>\n"
            "לדוגמה: <code>300 קבצים,300,400</code>"
        )
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_pkgview_"):
        key = data[len("adm_pkgview_"):]
        text, markup = await _pkg_view_text_markup(key)
        if not text:
            return await query.answer("❌ החבילה לא נמצאה.", show_alert=True)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_pkgprice_"):
        key = data[len("adm_pkgprice_"):]
        admin_id = query.from_user.id
        ADM_INPUT[admin_id] = {'action': 'pkg_price', 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id, 'pkg_key': key}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=f'adm_pkgview_{key}')]])
        return await query.message.edit_caption("✏️ <b>שינוי מחיר</b>\n\nשלח את המחיר החדש בכוכבים (מספר בלבד).", reply_markup=markup)

    if data.startswith("adm_pkgtoggle_"):
        from .pay import toggle_package_active
        key = data[len("adm_pkgtoggle_"):]
        await toggle_package_active(key)
        text, markup = await _pkg_view_text_markup(key)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_pkgdel_") and data.endswith("_ask"):
        key = data[len("adm_pkgdel_"):-len("_ask")]

        async def _do_pkgdel():
            from .pay import delete_custom_package
            await delete_custom_package(key)
            text, markup = await _packages_menu_text_markup()
            await query.message.edit_caption(text, reply_markup=markup)

        async def _cancel_pkgdel():
            text, markup = await _pkg_view_text_markup(key)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, "למחוק את החבילה לצמיתות?", _do_pkgdel, _cancel_pkgdel)

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

    if data.startswith("adm_gadmins_"):
        chat_id_str, _, page_str = data[len("adm_gadmins_"):].partition('_')
        chat_id = int(chat_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        text, markup = await _render_group_admins(client, chat_id, page)
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("adm_gdemote_") and data.endswith("_ask"):
        parts = data[len("adm_gdemote_"):-len("_ask")].split('_')
        chat_id, target_uid = int(parts[0]), int(parts[1])
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

        async def _do_gdemote():
            try:
                await client.promote_chat_member(chat_id, target_uid, privileges=ChatPrivileges(can_manage_chat=False))
                note = "✅ המשתמש הורד מניהול."
            except Exception as e:
                note = f"❌ שגיאה: {e}"
            text, markup = await _render_group_admins(client, chat_id, page)
            await query.message.edit_caption(f"{note}\n\n{text}", reply_markup=markup)

        async def _cancel_gdemote():
            text, markup = await _render_group_admins(client, chat_id, page)
            await query.message.edit_caption(text, reply_markup=markup)

        return await _ask_confirm(query, "להוריד את המשתמש מניהול הקבוצה?", _do_gdemote, _cancel_gdemote)

    if data.startswith("adm_gpromote_"):
        chat_id_str, _, page_str = data[len("adm_gpromote_"):].partition('_')
        chat_id = int(chat_id_str)
        page = int(page_str) if page_str.isdigit() else 1
        admin_id = query.from_user.id
        ADM_INPUT[admin_id] = {'action': 'gpromote', 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id, 'chat_id': chat_id, 'back_page': page}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data=f'adm_gadmins_{chat_id}_{page}')]])
        return await query.message.edit_caption("✏️ <b>מינוי מנהל חדש</b>\n\nשלח את מזהה המשתמש (ID) שברצונך למנות למנהל בקבוצה.\nהמשתמש חייב להיות חבר בקבוצה.", reply_markup=markup)

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
