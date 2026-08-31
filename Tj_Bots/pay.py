import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, LabeledPrice, CallbackQuery
from config import ADMINS, FREE_DAILY_SEARCHES, PHOTO_URL
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

LIFETIME_SECONDS = 100 * 365 * 24 * 3600  # effectively forever
LIFETIME_DISPLAY_THRESHOLD = 5 * 365 * 24 * 3600  # anything left above this shows as lifetime, not a countdown

TIME_PACKAGES = {
    "time_1h": {"stars": 50, "hours": 1, "label": "שעה ללא הגבלה - 50 כוכבים"},
    "time_3h": {"stars": 125, "hours": 3, "label": "3 שעות ללא הגבלה - 125 כוכבים"},
    "time_24h": {"stars": 250, "hours": 24, "label": "24 שעות ללא הגבלה - 250 כוכבים"},
    "time_life": {"stars": 2000, "lifetime": True, "label": "לכל החיים ללא הגבלה - 2000 כוכבים"},
}

COUNT_PACKAGES = {
    "count_1": {"stars": 5, "searches": 1, "label": "חיפוש בודד - 5 כוכבים"},
    "count_20": {"stars": 50, "searches": 20, "label": "20 חיפושים - 50 כוכבים"},
    "count_60": {"stars": 125, "searches": 60, "label": "60 חיפושים - 125 כוכבים"},
    "count_150": {"stars": 250, "searches": 150, "label": "150 חיפושים - 250 כוכבים"},
}

ALL_PACKAGES = {**TIME_PACKAGES, **COUNT_PACKAGES}


def _today_str():
    return datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")


def _time_until_reset():
    now = datetime.now(ISRAEL_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    hours, remainder = divmod(int((tomorrow - now).total_seconds()), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


async def check_quota(user_id):
    """Read-only: True if the user is currently allowed to run a search."""
    if user_id in ADMINS:
        return True

    quota = await db.get_search_quota(user_id)

    if quota['unlimited_until'] > time.time():
        return True

    today = _today_str()
    free_used = quota['free_used'] if quota['free_date'] == today else 0
    if free_used < FREE_DAILY_SEARCHES:
        return True

    return quota['search_credits'] > 0


async def consume_search(user_id):
    """Call only after a search actually returned results - a search with no
    results doesn't cost anything."""
    quota = await db.get_search_quota(user_id)

    today = _today_str()
    if quota['free_date'] != today:
        await db.reset_free_usage(user_id, today)
        quota['free_used'] = 0

    if user_id in ADMINS:
        await db.increment_free_usage(user_id)
        return

    if quota['unlimited_until'] > time.time():
        return

    if quota['free_used'] < FREE_DAILY_SEARCHES:
        await db.increment_free_usage(user_id)
        return

    await db.use_search_credit(user_id)


def denial_text():
    return (
        "🚫 <b>נגמרו לך כל החיפושים (חינמיים ובתשלום).</b>\n"
        f"⏳ החיפושים החינמיים יתאפסו בעוד: <b>{_time_until_reset()}</b>\n"
        "🔎 ניתן לרכוש חיפושים נוספים בכוכבים 👇"
    )


def out_of_quota_markup(bot_username):
    return InlineKeyboardMarkup([[InlineKeyboardButton('🔎 קניית חיפושים', url=f'https://t.me/{bot_username}?start=buy')]])


ADMIN_INFINITY = '<tg-emoji emoji-id="5780517739756000213">♾</tg-emoji>'


async def _status_block(user_id):
    quota = await db.get_search_quota(user_id)
    today = _today_str()
    used_today = quota['free_used'] if quota['free_date'] == today else 0

    if user_id in ADMINS:
        lines = [
            "🆓 <b>חיפושים היום</b>",
            f"בוצעו: <b>{used_today}</b> מתוך {ADMIN_INFINITY}",
        ]
        return "<blockquote>" + "\n".join(lines) + "</blockquote>"

    free_left = max(FREE_DAILY_SEARCHES - used_today, 0)
    now = time.time()

    lines = [
        "🆓 <b>חיפושים חינמיים</b>",
        f"נוצלו: <b>{used_today}</b> מתוך <b>{FREE_DAILY_SEARCHES}</b> (נשארו: <b>{free_left}</b>)",
        f"⏳ מתאפס בעוד: <b>{_time_until_reset()}</b>",
        "",
        "💳 <b>חיפושים בתשלום</b>",
        f"יתרה: <b>{quota['search_credits']}</b>",
        "",
        "⏰ <b>מנוי זמן ללא הגבלה</b>",
    ]

    remaining = quota['unlimited_until'] - now
    if remaining > LIFETIME_DISPLAY_THRESHOLD:
        lines.append(f"פעיל: {ADMIN_INFINITY} (לכל החיים)")
    elif remaining > 0:
        hours, remainder = divmod(int(remaining), 3600)
        minutes = remainder // 60
        lines.append(f"פעיל עוד: <b>{hours:02d}:{minutes:02d}</b>")
    else:
        lines.append("לא פעיל")

    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


def _menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('⏰ חבילות זמן (חיפוש ללא הגבלה)', callback_data='pay_cat_time', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🔍 חבילות חיפושים', callback_data='pay_cat_count', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('חזרה ⋟', callback_data='home', style=enums.ButtonStyle.PRIMARY),
         InlineKeyboardButton('✘ סגור', callback_data='closea', style=enums.ButtonStyle.DANGER)],
    ])


def _packages_markup(packages):
    keyboard = [[InlineKeyboardButton(f"{p['label']} ⭐", callback_data=f"pay_buy_{key}", style=enums.ButtonStyle.SUCCESS)] for key, p in packages.items()]
    keyboard.append([InlineKeyboardButton('חזרה ⋟', callback_data='pay_menu', style=enums.ButtonStyle.PRIMARY)])
    return InlineKeyboardMarkup(keyboard)


async def _edit_photo(message, text, markup):
    await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=text), reply_markup=markup)


async def send_buy_menu(message, user_id, is_edit=False):
    status = await _status_block(user_id)
    text = f"🔎 <b>קניית חיפושים</b>\n\n{status}\n\nבחר את סוג החבילה שברצונך לרכוש:"
    if is_edit:
        await _edit_photo(message, text, _menu_markup())
    else:
        await message.reply_photo(PHOTO_URL, caption=text, reply_markup=_menu_markup(), quote=True)


@Client.on_message(filters.command("buy"))
async def buy_command(client, message):
    await send_buy_menu(message, message.from_user.id)


@Client.on_callback_query(filters.regex(r"^pay_"))
async def pay_callback(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "pay_menu":
        return await send_buy_menu(query.message, user_id, is_edit=True)

    if data == "pay_cat_time":
        text = "⏰ <b>בחר חבילת זמן:</b>\n\nבתקופת החבילה תוכל לחפש ללא הגבלה."
        return await _edit_photo(query.message, text, _packages_markup(TIME_PACKAGES))

    if data == "pay_cat_count":
        status = await _status_block(user_id)
        text = f"🔍 <b>בחר חבילת חיפושים:</b>\n\n{status}"
        return await _edit_photo(query.message, text, _packages_markup(COUNT_PACKAGES))

    if data.startswith("pay_buy_"):
        key = data[len("pay_buy_"):]
        package = ALL_PACKAGES.get(key)
        if not package:
            return await query.answer("❌ חבילה לא קיימת.", show_alert=True)

        await query.answer()
        await client.send_invoice(
            chat_id=query.message.chat.id,
            title=package['label'],
            description=f"רכישת {package['label']} עבור הבוט.",
            payload=f"pay|{key}|{user_id}",
            currency="XTR",
            prices=[LabeledPrice(label=package['label'], amount=package['stars'])],
        )


@Client.on_pre_checkout_query()
async def pay_pre_checkout(client, pre_checkout_query):
    payload = pre_checkout_query.invoice_payload or ""
    parts = payload.split("|")
    if len(parts) == 3 and parts[0] == "pay" and parts[1] in ALL_PACKAGES:
        return await pre_checkout_query.answer(ok=True)
    await pre_checkout_query.answer(ok=False, error_message="❌ החבילה לא נמצאה, נסה שוב.")


@Client.on_message(filters.successful_payment)
async def pay_successful(client, message):
    payload = message.successful_payment.invoice_payload or ""
    parts = payload.split("|")
    if len(parts) != 3 or parts[0] != "pay":
        return

    key = parts[1]
    package = ALL_PACKAGES.get(key)
    if not package:
        return

    user_id = message.from_user.id
    stars = message.successful_payment.total_amount

    if key in TIME_PACKAGES:
        kind = "time"
        if package.get('lifetime'):
            value = "lifetime"
            await db.extend_unlimited(user_id, LIFETIME_SECONDS)
            confirm = "✅ **הרכישה בוצעה בהצלחה!**\nקיבלת חיפוש ללא הגבלה לכל החיים! 🎉"
        else:
            value = package['hours']
            await db.extend_unlimited(user_id, package['hours'] * 3600)
            confirm = f"✅ **הרכישה בוצעה בהצלחה!**\nקיבלת חיפוש ללא הגבלה ל-{package['hours']} שעות."
    else:
        kind = "count"
        value = package['searches']
        await db.add_search_credits(user_id, package['searches'])
        confirm = f"✅ **הרכישה בוצעה בהצלחה!**\nקיבלת {package['searches']} חיפושים נוספים."

    await db.log_purchase(user_id, key, kind, stars, value)
    await message.reply_text(confirm, quote=True)

    user_mention = message.from_user.mention
    admin_text = (
        "💎 **רכישת חיפושים חדשה**\n\n"
        f"👤 משתמש: {user_mention} (`{user_id}`)\n"
        f"📦 חבילה: {package['label']}\n"
        f"⭐ כוכבים: {stars}"
    )
    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, admin_text)
        except Exception:
            pass


@Client.on_message(filters.command("status") & filters.user(ADMINS))
async def status_command(client, message):
    stats = await db.get_purchase_stats()

    lines = [
        "📊 **סטטוס רכישות כוכבים**\n",
        f"⭐ סה'כ כוכבים שנקנו: `{stats['total_stars']}`",
        f"🧾 סה'כ רכישות: `{stats['total_count']}`\n",
    ]

    if stats['packages']:
        lines.append("**לפי חבילה:**")
        for key, info in stats['packages'].items():
            label = ALL_PACKAGES.get(key, {}).get('label', key)
            lines.append(f"• {label} — `{info['count']}` רכישות, `{info['stars']}` ⭐")
    else:
        lines.append("עדיין לא בוצעו רכישות.")

    await message.reply_text("\n".join(lines), quote=True)
