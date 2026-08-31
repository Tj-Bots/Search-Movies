from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import ADMINS, PHOTO_URL
from database import db

ADM_INPUT = {}

BAN_ACTIONS = {
    'ban_user': {'label': 'חסימת משתמש', 'prompt': "שלח את מזהה המשתמש לחסימה (ואפשר סיבה אחרי רווח).\nלדוגמה: <code>123456789 הפרת חוקים</code>"},
    'unban_user': {'label': 'שחרור משתמש', 'prompt': "שלח את מזהה המשתמש לשחרור."},
    'ban_chat': {'label': 'חסימת קבוצה', 'prompt': "שלח את מזהה הקבוצה לחסימה (ואפשר סיבה אחרי רווח)."},
    'unban_chat': {'label': 'שחרור קבוצה', 'prompt': "שלח את מזהה הקבוצה לשחרור."},
}


def _panel_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('📢 שידור הודעות', callback_data='bc_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🚫 ניהול חסימות', callback_data='adm_ban_menu', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📡 ערוצי מקור', callback_data='adm_channels', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('⭐ תומכים בכוכבים', callback_data='adm_stars', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('📊 סטטיסטיקות', callback_data='adm_stats', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)],
    ])


def _ban_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🚫 חסימת משתמש', callback_data='adm_ban_ban_user'),
         InlineKeyboardButton('✅ שחרור משתמש', callback_data='adm_ban_unban_user')],
        [InlineKeyboardButton('🚫 חסימת קבוצה', callback_data='adm_ban_ban_chat'),
         InlineKeyboardButton('✅ שחרור קבוצה', callback_data='adm_ban_unban_chat')],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])


def _back_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)]])


async def send_admin_panel(message, is_edit=False):
    text = "🛠 <b>פאנל ניהול</b>\n\nבחר פעולה:"
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=text), reply_markup=_panel_markup())
    else:
        await message.reply_photo(PHOTO_URL, caption=text, reply_markup=_panel_markup(), quote=True)


@Client.on_message(filters.command("admin") & filters.user(ADMINS))
async def admin_command(client, message):
    await send_admin_panel(message)


def _is_awaiting_ban_input(_, __, message):
    admin_id = message.from_user.id if message.from_user else None
    return admin_id in ADM_INPUT


@Client.on_message(filters.user(ADMINS) & filters.create(_is_awaiting_ban_input))
async def admin_ban_input(client, message):
    admin_id = message.from_user.id
    state = ADM_INPUT.pop(admin_id)
    action = state['action']

    try:
        await message.delete()
    except Exception:
        pass

    parts = (message.text or "").split(maxsplit=1)
    try:
        target_id = int(parts[0])
    except (IndexError, ValueError):
        await client.edit_message_caption(
            state['panel_chat'], state['panel_msg'],
            caption="❌ מזהה לא תקין.", reply_markup=_ban_menu_markup()
        )
        return

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

    await client.edit_message_caption(state['panel_chat'], state['panel_msg'], caption=result, reply_markup=_ban_menu_markup())


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
        if action not in BAN_ACTIONS:
            return
        ADM_INPUT[admin_id] = {'action': action, 'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='adm_ban_menu')]])
        text = f"✏️ <b>{BAN_ACTIONS[action]['label']}</b>\n\n{BAN_ACTIONS[action]['prompt']}"
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
