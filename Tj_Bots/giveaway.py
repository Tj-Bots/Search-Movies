import asyncio
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from config import ADMINS
from .utils import is_chat_member

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

TEXTS = {
    'he': {
        'post': (
            "🎉 <b>הגרלת טלגרם פרימיום!</b> 🎉\n\n"
            "🎁 <b>פרס:</b> {months} חודשי פרימיום, ל-{winner_count} מנצחים\n"
            "👥 <b>משתתפים:</b> {count}\n"
            "⏰ <b>ההגרלה מסתיימת:</b> {end_str}\n\n"
            "לחצו על הכפתור כדי להשתתף! בהצלחה 🍀"
        ),
        'join_button': '🎉 הצטרף להגרלה',
        'already_joined': '✅ אתה כבר רשום להגרלה!',
        'joined_ok': '🎉 נרשמת בהצלחה להגרלה! בהצלחה 🍀',
        'not_found': '❌ ההגרלה הזו הסתיימה או לא נמצאה.',
        'not_member': '❌ עליך להצטרף לערוץ/לקבוצה של ההגרלה לפני ההרשמה.',
        'start_first': '❌ עליך לפתוח את הבוט בפרטי וללחוץ START, ואז לנסות להצטרף להגרלה שוב.',
        'removed_left': "🚫 <b>הוסרת מההגרלה</b>\nעזבת את {title} - כדי להשתתף שוב, הצטרף בחזרה לפני שההגרלה מסתיימת.",
        'winner_notice': "🎉 <b>מזל טוב, זכית בהגרלה!</b>\nמגיע לך {months} חודשי פרימיום לטלגרם 🎁",
        'no_participants': "😔 לא היו משתתפים בהגרלה.",
        'winners_pending': "⏳ המנצחים בטיפול, יעודכן בקרוב.",
        'ended': (
            "🎊 <b>ההגרלה הסתיימה!</b> 🎊\n\n"
            "👥 סה'כ משתתפים: {count}\n\n"
            "<b>המנצחים:</b>\n{winners_text}"
        ),
        'cancelled': "🚫 <b>ההגרלה בוטלה על ידי הצוות.</b>",
    },
    'en': {
        'post': (
            "🎉 <b>Telegram Premium Giveaway!</b> 🎉\n\n"
            "🎁 <b>Prize:</b> {months} months of Telegram Premium, for {winner_count} winners\n"
            "👥 <b>Participants:</b> {count}\n"
            "⏰ <b>Giveaway ends:</b> {end_str}\n\n"
            "Tap the button below to join! Good luck 🍀"
        ),
        'join_button': '🎉 Join the Giveaway',
        'already_joined': "✅ You're already entered!",
        'joined_ok': '🎉 You successfully entered the giveaway! Good luck 🍀',
        'not_found': "❌ This giveaway has ended or doesn't exist.",
        'not_member': "❌ You need to join the giveaway's channel/group before registering.",
        'start_first': "❌ You need to open the bot in private and tap START, then try joining the giveaway again.",
        'removed_left': "🚫 <b>You were removed from the giveaway</b>\nYou left {title} - to join again, come back before the giveaway ends.",
        'winner_notice': "🎉 <b>Congratulations, you won the giveaway!</b>\nYou're getting {months} months of Telegram Premium 🎁",
        'no_participants': "😔 No one joined this giveaway.",
        'winners_pending': "⏳ Winners are being processed, will be updated soon.",
        'ended': (
            "🎊 <b>The giveaway has ended!</b> 🎊\n\n"
            "👥 Total participants: {count}\n\n"
            "<b>Winners:</b>\n{winners_text}"
        ),
        'cancelled': "🚫 <b>This giveaway was cancelled by the team.</b>",
    },
}


def _t(giveaway, key):
    return TEXTS.get(giveaway.get('lang', 'he'), TEXTS['he'])[key]


def cancelled_text(giveaway):
    return _t(giveaway, 'cancelled')


def _giveaway_text(giveaway):
    end_str = datetime.fromtimestamp(giveaway['end_time'], ISRAEL_TZ).strftime('%d/%m/%Y %H:%M')
    return _t(giveaway, 'post').format(
        months=giveaway['months'],
        winner_count=giveaway['winner_count'],
        count=len(giveaway.get('participants', [])),
        end_str=end_str,
    )


def _giveaway_markup(giveaway_id, lang='he'):
    label = TEXTS.get(lang, TEXTS['he'])['join_button']
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f'ga_join_{giveaway_id}', style=enums.ButtonStyle.SUCCESS)]])


async def post_giveaway(client, giveaway_id, giveaway):
    msg = await client.send_message(
        giveaway['chat_id'], _giveaway_text(giveaway),
        reply_markup=_giveaway_markup(giveaway_id, giveaway.get('lang', 'he'))
    )
    await db.set_giveaway_message(giveaway_id, msg.id)
    return msg


async def _update_giveaway_post(client, giveaway):
    if not giveaway.get('message_id'):
        return
    try:
        await client.edit_message_text(
            giveaway['chat_id'], giveaway['message_id'], _giveaway_text(giveaway),
            reply_markup=_giveaway_markup(giveaway['_id'], giveaway.get('lang', 'he'))
        )
    except Exception:
        pass


def giveaway_result_text(status, giveaway):
    key = {'ok': 'joined_ok', 'already': 'already_joined', 'not_member': 'not_member', 'not_found': 'not_found'}.get(status, 'not_found')
    return _t(giveaway, key)


def _join_link_markup(giveaway):
    if not giveaway.get('invite_url'):
        return None
    label = '📣 Join' if giveaway.get('lang') == 'en' else '📣 הצטרף'
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=giveaway['invite_url'])]])


def giveaway_result_markup(status, giveaway):
    if status == 'not_member':
        return _join_link_markup(giveaway)
    return None


async def register_giveaway_participant(client, giveaway_id, user_id):
    """Registers user_id as a giveaway participant. Returns (status, giveaway) -
    status is one of 'ok', 'already', 'not_member', 'not_found'."""
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return 'not_found', giveaway or {}

    # Membership is always re-checked first, even for someone already in
    # participants - that way a stale entry (e.g. from before this check
    # existed, or someone who got removed and re-added) self-heals instead
    # of permanently bypassing the gate via the "already joined" shortcut.
    if not await is_chat_member(client, giveaway['chat_id'], user_id):
        if user_id in giveaway.get('participants', []):
            await db.remove_giveaway_participant(giveaway_id, user_id)
        return 'not_member', giveaway

    if user_id in giveaway.get('participants', []):
        return 'already', giveaway

    joined = await db.join_giveaway(giveaway_id, user_id)
    if not joined:
        return 'already', giveaway

    giveaway = await db.get_giveaway(giveaway_id)
    await _update_giveaway_post(client, giveaway)
    return 'ok', giveaway


async def _answer_via_start(client, query, giveaway_id, fallback_text):
    """answerCallbackQuery's url param only accepts a link that opens the bot
    itself (e.g. t.me/<bot>?start=...) - Telegram rejects an arbitrary external
    link (like a channel invite link) there, which raises and leaves the
    button looking dead if not caught. So any redirect always goes through the
    bot's own /start deep link, with a plain-text alert as a safety net."""
    try:
        bot_username = client.me.username
        await query.answer(url=f"https://t.me/{bot_username}?start=ga_{giveaway_id}")
    except Exception:
        await query.answer(fallback_text, show_alert=True)


@Client.on_callback_query(filters.regex(r"^ga_join_"))
async def handle_giveaway_join(client, query: CallbackQuery):
    giveaway_id = query.data[len("ga_join_"):]
    user_id = query.from_user.id

    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return await query.answer(_t(giveaway or {}, 'not_found'), show_alert=True)

    if not await is_chat_member(client, giveaway['chat_id'], user_id):
        if user_id in giveaway.get('participants', []):
            await db.remove_giveaway_participant(giveaway_id, user_id)
        return await _answer_via_start(client, query, giveaway_id, _t(giveaway, 'not_member'))

    if user_id in giveaway.get('participants', []):
        return await query.answer(_t(giveaway, 'already_joined'), show_alert=True)

    try:
        await client.send_message(user_id, _t(giveaway, 'joined_ok'))
    except Exception:
        return await _answer_via_start(client, query, giveaway_id, _t(giveaway, 'start_first'))

    status, giveaway = await register_giveaway_participant(client, giveaway_id, user_id)
    await query.answer(giveaway_result_text(status, giveaway), show_alert=True)


@Client.on_chat_member_updated()
async def handle_giveaway_member_left(client, update):
    new_status = update.new_chat_member.status if update.new_chat_member else None
    if new_status not in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED):
        return

    user = (update.new_chat_member.user if update.new_chat_member else None) or \
           (update.old_chat_member.user if update.old_chat_member else None)
    if not user:
        return

    active = await db.get_active_giveaways()
    for giveaway in active:
        if giveaway['chat_id'] != update.chat.id or user.id not in giveaway.get('participants', []):
            continue
        await db.remove_giveaway_participant(giveaway['_id'], user.id)
        giveaway = await db.get_giveaway(giveaway['_id'])
        await _update_giveaway_post(client, giveaway)
        try:
            await client.send_message(
                user.id, _t(giveaway, 'removed_left').format(title=giveaway.get('chat_title', '')),
                reply_markup=_join_link_markup(giveaway)
            )
        except Exception:
            pass


UNREACHABLE_MARKERS = ('blocked', 'not found', 'deactivated', 'chat not found', 'peer_id_invalid', 'user_id_invalid')


async def _attempt_gift(uid, giveaway):
    """Tries to gift premium to uid. Returns (status, detail):
    'ok' - gifted successfully.
    'unreachable' - bot can't message this user at all (blocked/never started) - not admin-fixable.
    'held' - gift itself failed (e.g. not enough stars) - admin-fixable, needs manual retry."""
    from .pay import gift_premium_subscription
    try:
        await gift_premium_subscription(uid, giveaway['months'], text="🎉")
        return 'ok', None
    except Exception as e:
        err = str(e)
        if any(marker in err.lower() for marker in UNREACHABLE_MARKERS):
            return 'unreachable', err
        return 'held', err


def _retry_markup(giveaway_id, uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton('📤 שלח עכשיו', callback_data=f"garetry_{giveaway_id}:{uid}")]])


def _winners_announce_text(giveaway):
    winners = giveaway.get('winners', [])
    if winners:
        winners_text = "\n".join(f"🏆 <a href='tg://user?id={uid}'>{uid}</a>" for uid in winners)
    elif giveaway.get('pending_gifts'):
        winners_text = _t(giveaway, 'winners_pending')
    else:
        winners_text = _t(giveaway, 'no_participants')
    return _t(giveaway, 'ended').format(count=len(giveaway.get('participants', [])), winners_text=winners_text)


async def _publish_ended_announcement(client, giveaway):
    text = _winners_announce_text(giveaway)
    if giveaway.get('message_id'):
        try:
            return await client.edit_message_text(giveaway['chat_id'], giveaway['message_id'], text)
        except Exception:
            pass
    try:
        await client.send_message(giveaway['chat_id'], text)
    except Exception:
        pass


async def draw_giveaway(client, giveaway):
    """
    Draws winners without ever telling a candidate they won until the gift is
    actually confirmed. If a candidate is unreachable (blocked bot / never
    started it) that's nothing an admin can fix, so they're skipped and a
    replacement is drawn. If the gift itself fails (e.g. not enough stars),
    that's admin-fixable: the slot is held (not redrawn) and the admins get a
    "send now" button to retry once there's enough balance - the winner is
    never notified until it actually succeeds.
    """
    giveaway_id = giveaway['_id']
    participants = giveaway.get('participants', [])
    pool = list(participants)
    random.shuffle(pool)
    target = giveaway['winner_count']

    confirmed = []
    held = []  # [{'uid': ..., 'error': ...}]

    while pool and (len(confirmed) + len(held)) < target:
        uid = pool.pop()
        status, err = await _attempt_gift(uid, giveaway)
        if status == 'unreachable':
            continue
        if status == 'held':
            held.append({'uid': uid, 'error': err})
            continue
        confirmed.append(uid)
        try:
            await client.send_message(uid, _t(giveaway, 'winner_notice').format(months=giveaway['months']))
        except Exception:
            pass

    await db.finish_giveaway(giveaway_id, confirmed)
    if held:
        await db.set_giveaway_pending(giveaway_id, held)

    giveaway = await db.get_giveaway(giveaway_id)
    await _publish_ended_announcement(client, giveaway)

    announce = _winners_announce_text(giveaway)
    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, f"🎉 <b>הגרלה הסתיימה</b>\n\n{announce}")
        except Exception:
            pass
        for h in held:
            try:
                await client.send_message(
                    admin_id,
                    f"⚠️ <b>לא ניתן לשלוח פרימיום למנצח <code>{h['uid']}</code>:</b>\n{h['error']}\n\n"
                    "הזוכה עדיין לא קיבל שום הודעה על זכייתו. לחץ לנסות לשלוח שוב כשתהיה יתרת כוכבים מספקת:",
                    reply_markup=_retry_markup(giveaway_id, h['uid'])
                )
            except Exception:
                pass

    return confirmed, held


@Client.on_callback_query(filters.regex(r"^garetry_"))
async def handle_giveaway_retry_gift(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("⛔ למנהלים בלבד.", show_alert=True)

    giveaway_id, uid_str = query.data[len("garetry_"):].split(":")
    uid = int(uid_str)
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway:
        return await query.answer("ההגרלה לא נמצאה.", show_alert=True)

    status, err = await _attempt_gift(uid, giveaway)
    if status != 'ok':
        return await query.message.edit_text(
            f"❌ עדיין נכשל לשלוח למנצח <code>{uid}</code>:\n{err}",
            reply_markup=_retry_markup(giveaway_id, uid)
        )

    await db.resolve_giveaway_pending(giveaway_id, uid)
    try:
        await client.send_message(uid, _t(giveaway, 'winner_notice').format(months=giveaway['months']))
    except Exception:
        pass

    giveaway = await db.get_giveaway(giveaway_id)
    await _publish_ended_announcement(client, giveaway)
    await query.message.edit_text(f"✅ נשלח בהצלחה למנצח <code>{uid}</code>.")


async def giveaway_watcher_loop(app):
    while True:
        try:
            due = await db.get_due_giveaways()
            for giveaway in due:
                await draw_giveaway(app, giveaway)
        except Exception as e:
            print(f"Giveaway watcher error: {e}")
        await asyncio.sleep(60)
