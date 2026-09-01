import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, LabeledPrice, CallbackQuery
from config import ADMINS, FREE_DAILY_SEARCHES, PHOTO_URL
from database import db

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

LIFETIME_SECONDS = 100 * 365 * 24 * 3600  # effectively forever
LIFETIME_DISPLAY_THRESHOLD = 5 * 365 * 24 * 3600  # anything left above this shows as lifetime, not a countdown

BASE_TIME_PACKAGES = {
    "time_1h": {"stars": 50, "hours": 1, "name": "שעה ללא הגבלה"},
    "time_3h": {"stars": 125, "hours": 3, "name": "3 שעות ללא הגבלה"},
    "time_24h": {"stars": 250, "hours": 24, "name": "24 שעות ללא הגבלה"},
    "time_life": {"stars": 2000, "lifetime": True, "name": "לכל החיים ללא הגבלה"},
}

BASE_COUNT_PACKAGES = {
    "count_1": {"stars": 5, "searches": 1, "name": "קובץ בודד"},
    "count_20": {"stars": 50, "searches": 20, "name": "20 קבצים"},
    "count_60": {"stars": 125, "searches": 60, "name": "60 קבצים"},
    "count_150": {"stars": 250, "searches": 150, "name": "150 קבצים"},
}


def _label(name, stars):
    return f"{name} - {stars} כוכבים"


async def _pkg_overrides():
    return await db.get_config('pkg_overrides', {})


async def get_time_packages(include_inactive=False):
    overrides = await _pkg_overrides()
    result = {}
    for key, p in BASE_TIME_PACKAGES.items():
        ov = overrides.get(key, {})
        active = ov.get('active', True)
        if not active and not include_inactive:
            continue
        stars = ov.get('stars', p['stars'])
        result[key] = {
            'stars': stars, 'hours': p.get('hours'), 'lifetime': p.get('lifetime', False),
            'name': p['name'], 'label': _label(p['name'], stars),
            'active': active, 'kind': 'time', 'custom': False,
        }
    for cp in await db.get_config('custom_time_pkgs', []):
        active = cp.get('active', True)
        if not active and not include_inactive:
            continue
        key = f"ctime_{cp['id']}"
        result[key] = {
            'stars': cp['stars'], 'hours': cp.get('hours'), 'lifetime': cp.get('lifetime', False),
            'name': cp['name'], 'label': _label(cp['name'], cp['stars']),
            'active': active, 'kind': 'time', 'custom': True,
        }
    return result


async def get_count_packages(include_inactive=False):
    overrides = await _pkg_overrides()
    result = {}
    for key, p in BASE_COUNT_PACKAGES.items():
        ov = overrides.get(key, {})
        active = ov.get('active', True)
        if not active and not include_inactive:
            continue
        stars = ov.get('stars', p['stars'])
        result[key] = {
            'stars': stars, 'searches': p['searches'],
            'name': p['name'], 'label': _label(p['name'], stars),
            'active': active, 'kind': 'count', 'custom': False,
        }
    for cp in await db.get_config('custom_count_pkgs', []):
        active = cp.get('active', True)
        if not active and not include_inactive:
            continue
        key = f"ccount_{cp['id']}"
        result[key] = {
            'stars': cp['stars'], 'searches': cp['searches'],
            'name': cp['name'], 'label': _label(cp['name'], cp['stars']),
            'active': active, 'kind': 'count', 'custom': True,
        }
    return result


async def get_all_packages(include_inactive=False):
    merged = {}
    merged.update(await get_time_packages(include_inactive))
    merged.update(await get_count_packages(include_inactive))
    return merged


def _pkg_list_key(key):
    if key.startswith('ctime_'):
        return 'custom_time_pkgs'
    if key.startswith('ccount_'):
        return 'custom_count_pkgs'
    return None


async def set_package_price(key, stars):
    list_key = _pkg_list_key(key)
    if list_key:
        pkg_id = key.split('_', 1)[1]
        items = await db.get_config(list_key, [])
        for it in items:
            if it['id'] == pkg_id:
                it['stars'] = stars
        await db.set_config(list_key, items)
    else:
        overrides = await _pkg_overrides()
        ov = overrides.get(key, {})
        ov['stars'] = stars
        overrides[key] = ov
        await db.set_config('pkg_overrides', overrides)


async def toggle_package_active(key):
    list_key = _pkg_list_key(key)
    if list_key:
        pkg_id = key.split('_', 1)[1]
        items = await db.get_config(list_key, [])
        for it in items:
            if it['id'] == pkg_id:
                it['active'] = not it.get('active', True)
        await db.set_config(list_key, items)
    else:
        overrides = await _pkg_overrides()
        ov = overrides.get(key, {})
        ov['active'] = not ov.get('active', True)
        overrides[key] = ov
        await db.set_config('pkg_overrides', overrides)


async def delete_custom_package(key):
    list_key = _pkg_list_key(key)
    if not list_key:
        return
    pkg_id = key.split('_', 1)[1]
    items = await db.get_config(list_key, [])
    items = [it for it in items if it['id'] != pkg_id]
    await db.set_config(list_key, items)


async def add_custom_time_package(name, stars, hours=None, lifetime=False):
    items = await db.get_config('custom_time_pkgs', [])
    items.append({'id': uuid.uuid4().hex[:8], 'name': name, 'stars': stars, 'hours': hours, 'lifetime': lifetime, 'active': True})
    await db.set_config('custom_time_pkgs', items)


async def add_custom_count_package(name, searches, stars):
    items = await db.get_config('custom_count_pkgs', [])
    items.append({'id': uuid.uuid4().hex[:8], 'name': name, 'searches': searches, 'stars': stars, 'active': True})
    await db.set_config('custom_count_pkgs', items)


def _today_str():
    return datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")


def _time_until_reset():
    now = datetime.now(ISRAEL_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    hours, remainder = divmod(int((tomorrow - now).total_seconds()), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


async def is_payments_enabled():
    return await db.get_config('payments_enabled', True)


async def get_free_daily_limit():
    return await db.get_config('free_daily_limit', FREE_DAILY_SEARCHES)


async def check_quota(user_id):
    """Read-only: True if the user is currently allowed to run a search."""
    if user_id in ADMINS:
        return True

    if not await is_payments_enabled():
        return True

    quota = await db.get_search_quota(user_id)

    if quota['unlimited_until'] > time.time():
        return True

    today = _today_str()
    free_used = quota['free_used'] if quota['free_date'] == today else 0
    limit = await get_free_daily_limit() + quota['extra_daily_limit']
    if free_used < limit:
        return True

    return quota['search_credits'] > 0


async def consume_search(user_id):
    """Call only after a search actually returned results - a search with no
    results doesn't cost anything."""
    if not await is_payments_enabled():
        return

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

    limit = await get_free_daily_limit() + quota['extra_daily_limit']
    if quota['free_used'] < limit:
        await db.increment_free_usage(user_id)
        return

    await db.use_search_credit(user_id)


def denial_text():
    return (
        "🚫 <b>נגמרו לך כל הקבצים (חינמיים ובתשלום).</b>\n"
        f"⏳ הקבצים החינמיים יתאפסו בעוד: <b>{_time_until_reset()}</b>\n"
        "🔎 ניתן לרכוש קבצים נוספים בכוכבים 👇"
    )


def out_of_quota_markup(bot_username):
    return InlineKeyboardMarkup([[InlineKeyboardButton('🔎 קניית קבצים', url=f'https://t.me/{bot_username}?start=buy')]])


ADMIN_INFINITY = '<tg-emoji emoji-id="5780517739756000213">♾</tg-emoji>'


async def _status_block(user_id):
    quota = await db.get_search_quota(user_id)
    today = _today_str()
    used_today = quota['free_used'] if quota['free_date'] == today else 0

    if user_id in ADMINS:
        lines = [
            "🆓 <b>קבצים היום</b>",
            f"התקבלו: <b>{used_today}</b> מתוך {ADMIN_INFINITY}",
        ]
        return "<blockquote>" + "\n".join(lines) + "</blockquote>"

    if not await is_payments_enabled():
        return "<blockquote>🆓 <b>הבוט פתוח לגמרי בחינם וללא הגבלה כרגע.</b></blockquote>"

    limit = await get_free_daily_limit() + quota['extra_daily_limit']
    free_left = max(limit - used_today, 0)
    now = time.time()

    limit_line = f"נוצלו: <b>{used_today}</b> מתוך <b>{limit}</b> (נשארו: <b>{free_left}</b>)"
    if quota['extra_daily_limit']:
        limit_line += f"\n🔗 כולל <b>+{quota['extra_daily_limit']}</b> קבוע מהזמנות"

    lines = [
        "🆓 <b>קבצים חינמיים</b>",
        limit_line,
        f"⏳ מתאפס בעוד: <b>{_time_until_reset()}</b>",
        "",
        "💳 <b>קבצים בתשלום</b>",
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
        [InlineKeyboardButton('⏰ חבילות זמן (קבצים ללא הגבלה)', callback_data='pay_cat_time', style=enums.ButtonStyle.PRIMARY)],
        [InlineKeyboardButton('🔍 חבילות קבצים', callback_data='pay_cat_count', style=enums.ButtonStyle.PRIMARY)],
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
    text = f"🔎 <b>קניית קבצים</b>\n\n{status}\n\nבחר את סוג החבילה שברצונך לרכוש:"
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
        packages = await get_time_packages()
        text = "⏰ <b>בחר חבילת זמן:</b>\n\nבתקופת החבילה תוכל לקבל קבצים ללא הגבלה."
        return await _edit_photo(query.message, text, _packages_markup(packages))

    if data == "pay_cat_count":
        packages = await get_count_packages()
        status = await _status_block(user_id)
        text = f"🔍 <b>בחר חבילת קבצים:</b>\n\n{status}"
        return await _edit_photo(query.message, text, _packages_markup(packages))

    if data.startswith("pay_buy_"):
        key = data[len("pay_buy_"):]
        package = (await get_all_packages()).get(key)
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
    if len(parts) == 3 and parts[0] == "pay" and parts[1] in (await get_all_packages(include_inactive=True)):
        return await pre_checkout_query.answer(ok=True)
    await pre_checkout_query.answer(ok=False, error_message="❌ החבילה לא נמצאה, נסה שוב.")


@Client.on_message(filters.successful_payment)
async def pay_successful(client, message):
    payload = message.successful_payment.invoice_payload or ""
    parts = payload.split("|")
    if len(parts) != 3 or parts[0] != "pay":
        return

    key = parts[1]
    package = (await get_all_packages(include_inactive=True)).get(key)
    if not package:
        return

    user_id = message.from_user.id
    stars = message.successful_payment.total_amount

    if package['kind'] == "time":
        kind = "time"
        if package.get('lifetime'):
            value = "lifetime"
            await db.extend_unlimited(user_id, LIFETIME_SECONDS)
            confirm = "✅ **הרכישה בוצעה בהצלחה!**\nקיבלת קבצים ללא הגבלה לכל החיים! 🎉"
        else:
            value = package['hours']
            await db.extend_unlimited(user_id, package['hours'] * 3600)
            confirm = f"✅ **הרכישה בוצעה בהצלחה!**\nקיבלת קבצים ללא הגבלה ל-{package['hours']} שעות."
    else:
        kind = "count"
        value = package['searches']
        await db.add_search_credits(user_id, package['searches'])
        confirm = f"✅ **הרכישה בוצעה בהצלחה!**\nקיבלת {package['searches']} קבצים נוספים."

    await db.log_purchase(user_id, key, kind, stars, value)
    await message.reply_text(confirm, quote=True)

    user_mention = message.from_user.mention
    admin_text = (
        "💎 **רכישת קבצים חדשה**\n\n"
        f"👤 משתמש: {user_mention} (`{user_id}`)\n"
        f"📦 חבילה: {package['label']}\n"
        f"⭐ כוכבים: {stars}"
    )
    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, admin_text)
        except Exception:
            pass


async def build_purchase_stats_text():
    stats = await db.get_purchase_stats()

    lines = [
        "📊 **סטטוס רכישות כוכבים**\n",
        f"⭐ סה'כ כוכבים שנקנו: `{stats['total_stars']}`",
        f"🧾 סה'כ רכישות: `{stats['total_count']}`\n",
    ]

    if stats['packages']:
        all_packages = await get_all_packages(include_inactive=True)
        lines.append("**לפי חבילה:**")
        for key, info in stats['packages'].items():
            label = all_packages.get(key, {}).get('label', key)
            lines.append(f"• {label} — `{info['count']}` רכישות, `{info['stars']}` ⭐")
    else:
        lines.append("עדיין לא בוצעו רכישות.")

    return "\n".join(lines)


@Client.on_message(filters.command("status") & filters.user(ADMINS))
async def status_command(client, message):
    text = await build_purchase_stats_text()
    await message.reply_text(text, quote=True)
