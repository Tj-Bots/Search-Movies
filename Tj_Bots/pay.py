import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, CallbackQuery
from config import ADMINS, FREE_DAILY_SEARCHES
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

TIME_PACKAGES = {
    "time_1h": {"stars": 100, "hours": 1, "label": "100 כוכבים - שעה"},
    "time_3h": {"stars": 250, "hours": 3, "label": "250 כוכבים - 3 שעות"},
    "time_24h": {"stars": 500, "hours": 24, "label": "500 כוכבים - 24 שעות"},
}

COUNT_PACKAGES = {
    "count_20": {"stars": 100, "searches": 20, "label": "100 כוכבים - 20 חיפושים"},
    "count_60": {"stars": 250, "searches": 60, "label": "250 כוכבים - 60 חיפושים"},
    "count_150": {"stars": 500, "searches": 150, "label": "500 כוכבים - 150 חיפושים"},
}

ALL_PACKAGES = {**TIME_PACKAGES, **COUNT_PACKAGES}


def _today_str():
    return datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")


async def check_quota(user_id):
    if user_id in ADMINS:
        return True

    quota = await db.get_search_quota(user_id)

    if quota['unlimited_until'] > time.time():
        return True

    today = _today_str()
    if quota['free_date'] != today:
        await db.reset_free_usage(user_id, today)
        quota['free_used'] = 0

    if quota['free_used'] < FREE_DAILY_SEARCHES:
        await db.increment_free_usage(user_id)
        return True

    return await db.use_search_credit(user_id)


def out_of_quota_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton('💎 קניית כוכבים', callback_data='pay_menu')]])


def _menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('⏰ חבילות זמן (חיפוש ללא הגבלה)', callback_data='pay_cat_time')],
        [InlineKeyboardButton('🔍 חבילות חיפושים', callback_data='pay_cat_count')],
        [InlineKeyboardButton('⇠ חזרה', callback_data='pay_close')],
    ])


def _packages_markup(packages, back_to='pay_menu'):
    keyboard = [[InlineKeyboardButton(f"{p['label']} ⭐", callback_data=f"pay_buy_{key}")] for key, p in packages.items()]
    keyboard.append([InlineKeyboardButton('⇠ חזרה', callback_data=back_to)])
    return InlineKeyboardMarkup(keyboard)


async def _edit(message, text, markup):
    if message.photo:
        await message.edit_caption(text, reply_markup=markup)
    else:
        await message.edit_text(text, reply_markup=markup)


async def send_buy_menu(message, is_edit=False):
    text = '⏰🔍 בחר חבילת כוכבים:'
    if is_edit:
        await _edit(message, text, _menu_markup())
    else:
        await message.reply_text(text, reply_markup=_menu_markup(), quote=True)


@Client.on_message(filters.command("buy"))
async def buy_command(client, message):
    await send_buy_menu(message)


@Client.on_callback_query(filters.regex(r"^pay_"))
async def pay_callback(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "pay_menu":
        return await send_buy_menu(query.message, is_edit=True)

    if data == "pay_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if data == "pay_cat_time":
        return await _edit(query.message, '⏰ בחר חבילת כוכבים:', _packages_markup(TIME_PACKAGES))

    if data == "pay_cat_count":
        return await _edit(query.message, '🔍 בחר חבילת כוכבים:', _packages_markup(COUNT_PACKAGES))

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
        "💎 **רכישת כוכבים חדשה**\n\n"
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
