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
        'winner_dm': "🎉 <b>מזל טוב, זכית בהגרלה!</b>\nקיבלת {months} חודשי פרימיום לטלגרם 🎁",
        'gift_fail': " (⚠️ שליחה נכשלה: {err})",
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
        'winner_dm': "🎉 <b>Congratulations, you won the giveaway!</b>\nYou received {months} months of Telegram Premium 🎁",
        'gift_fail': " (⚠️ failed to send: {err})",
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


@Client.on_callback_query(filters.regex(r"^ga_join_"))
async def handle_giveaway_join(client, query: CallbackQuery):
    giveaway_id = query.data[len("ga_join_"):]
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return await query.answer(_t(giveaway or {}, 'not_found'), show_alert=True)

    joined = await db.join_giveaway(giveaway_id, query.from_user.id)
    if not joined:
        return await query.answer(_t(giveaway, 'already_joined'), show_alert=True)

    await query.answer(_t(giveaway, 'joined_ok'), show_alert=True)
    giveaway = await db.get_giveaway(giveaway_id)
    try:
        await query.message.edit_text(_giveaway_text(giveaway), reply_markup=_giveaway_markup(giveaway_id, giveaway.get('lang', 'he')))
    except Exception:
        pass


async def draw_giveaway(client, giveaway):
    from .pay import gift_premium_subscription

    giveaway_id = giveaway['_id']
    participants = giveaway.get('participants', [])
    winner_count = min(giveaway['winner_count'], len(participants))
    winners = random.sample(participants, winner_count) if winner_count > 0 else []

    results = []
    for uid in winners:
        try:
            await gift_premium_subscription(uid, giveaway['months'], text="🎉")
            results.append((uid, True, None))
            try:
                await client.send_message(uid, _t(giveaway, 'winner_dm').format(months=giveaway['months']))
            except Exception:
                pass
        except Exception as e:
            results.append((uid, False, str(e)))

    await db.finish_giveaway(giveaway_id, [uid for uid, ok, _ in results if ok])

    if results:
        winners_text = "\n".join(
            f"🏆 <a href='tg://user?id={uid}'>{uid}</a>" + (_t(giveaway, 'gift_fail').format(err=err) if not ok else "")
            for uid, ok, err in results
        )
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

    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, f"🎉 <b>הגרלה הסתיימה</b>\n\n{announce}")
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
