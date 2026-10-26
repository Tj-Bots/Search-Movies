import asyncio
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from config import ADMINS

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
        'winner_notice': "🎉 <b>מזל טוב, זכית בהגרלה!</b>\nמגיע לך {months} חודשי פרימיום לטלגרם - שולחים לך את זה עכשיו... 🎁",
        'gift_delay_fail': "⚠️ <b>מצטערים!</b> הייתה תקלה טכנית בשליחת הפרימיום. הצוות קיבל התראה ויטפל בזה איתך ישירות בהקדם.",
        'unreachable': "🚫 לא ניתן ליצור קשר (חסם/לא הפעיל את הבוט) - לא נשלח פרס",
        'gift_failed': "❌ שליחת הפרימיום נכשלה: {err}",
        'no_participants': "😔 לא היו משתתפים בהגרלה.",
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
        'winner_notice': "🎉 <b>Congratulations, you won the giveaway!</b>\nYou're getting {months} months of Telegram Premium - sending it now... 🎁",
        'gift_delay_fail': "⚠️ <b>Sorry!</b> There was a technical issue sending your Premium. Our team was notified and will follow up with you directly soon.",
        'unreachable': "🚫 Unreachable (blocked/never started the bot) - no prize sent",
        'gift_failed': "❌ Sending Premium failed: {err}",
        'no_participants': "😔 No one joined this giveaway.",
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


async def register_giveaway_participant(client, giveaway_id, user_id):
    """Registers user_id as a giveaway participant. Returns (ok, text) - the DM/alert text to show."""
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return False, _t(giveaway or {}, 'not_found')

    joined = await db.join_giveaway(giveaway_id, user_id)
    if not joined:
        return False, _t(giveaway, 'already_joined')

    giveaway = await db.get_giveaway(giveaway_id)
    await _update_giveaway_post(client, giveaway)
    return True, _t(giveaway, 'joined_ok')


@Client.on_callback_query(filters.regex(r"^ga_join_"))
async def handle_giveaway_join(client, query: CallbackQuery):
    giveaway_id = query.data[len("ga_join_"):]
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return await query.answer(_t(giveaway or {}, 'not_found'), show_alert=True)

    user_id = query.from_user.id
    if user_id in giveaway.get('participants', []):
        return await query.answer(_t(giveaway, 'already_joined'), show_alert=True)

    try:
        await client.send_message(user_id, _t(giveaway, 'joined_ok'))
    except Exception:
        bot_username = client.me.username
        return await query.answer(url=f"https://t.me/{bot_username}?start=ga_{giveaway_id}")

    ok, text = await register_giveaway_participant(client, giveaway_id, user_id)
    await query.answer(text, show_alert=True)


async def draw_giveaway(client, giveaway):
    """
    For each candidate: notify them by DM FIRST that they won, before actually
    gifting - this both confirms the bot can reach them and guarantees they're
    told about the prize before it's sent. If the notice fails (blocked bot /
    never started it) or the gift itself fails, that candidate is skipped and
    a replacement is drawn from the remaining pool, so a prize is never wasted
    on someone who can't receive it.
    """
    from .pay import gift_premium_subscription

    giveaway_id = giveaway['_id']
    participants = giveaway.get('participants', [])
    pool = list(participants)
    random.shuffle(pool)
    target = giveaway['winner_count']

    results = []  # (uid, ok, reason, detail)
    while pool and sum(1 for r in results if r[1]) < target:
        uid = pool.pop()
        try:
            await client.send_message(uid, _t(giveaway, 'winner_notice').format(months=giveaway['months']))
        except Exception as e:
            results.append((uid, False, 'unreachable', str(e)))
            continue

        try:
            await gift_premium_subscription(uid, giveaway['months'], text="🎉")
            results.append((uid, True, None, None))
        except Exception as e:
            results.append((uid, False, 'gift_failed', str(e)))
            try:
                await client.send_message(uid, _t(giveaway, 'gift_delay_fail'))
            except Exception:
                pass

    await db.finish_giveaway(giveaway_id, [uid for uid, ok, *_ in results if ok])

    winning_results = [r for r in results if r[1]]
    if winning_results:
        winners_text = "\n".join(f"🏆 <a href='tg://user?id={uid}'>{uid}</a>" for uid, ok, *_ in winning_results)
    else:
        winners_text = _t(giveaway, 'no_participants')

    announce = _t(giveaway, 'ended').format(count=len(participants), winners_text=winners_text)

    try:
        await client.edit_message_text(giveaway['chat_id'], giveaway['message_id'], announce)
    except Exception:
        try:
            await client.send_message(giveaway['chat_id'], announce)
        except Exception:
            pass

    failed_results = [r for r in results if not r[1]]
    admin_report = f"🎉 <b>הגרלה הסתיימה</b>\n\n{announce}"
    if failed_results:
        lines = []
        for uid, ok, reason, detail in failed_results:
            reason_text = _t(giveaway, 'unreachable') if reason == 'unreachable' else _t(giveaway, 'gift_failed').format(err=detail)
            lines.append(f"• <code>{uid}</code>: {reason_text}")
        admin_report += "\n\n⚠️ <b>מועמדים שדולגו (לא נשלח להם פרס):</b>\n" + "\n".join(lines)

    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, admin_report)
        except Exception:
            pass

    return results


async def giveaway_watcher_loop(app):
    while True:
        try:
            due = await db.get_due_giveaways()
            for giveaway in due:
                await draw_giveaway(app, giveaway)
        except Exception as e:
            print(f"Giveaway watcher error: {e}")
        await asyncio.sleep(60)
