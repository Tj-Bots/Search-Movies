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


def _giveaway_text(giveaway):
    end_str = datetime.fromtimestamp(giveaway['end_time'], ISRAEL_TZ).strftime('%d/%m/%Y %H:%M')
    return (
        "🎉 <b>הגרלת טלגרם פרימיום!</b> 🎉\n\n"
        f"🎁 <b>פרס:</b> {giveaway['months']} חודשי פרימיום, ל-{giveaway['winner_count']} מנצחים\n"
        f"👥 <b>משתתפים:</b> {len(giveaway.get('participants', []))}\n"
        f"⏰ <b>ההגרלה מסתיימת:</b> {end_str}\n\n"
        "לחצו על הכפתור כדי להשתתף! בהצלחה 🍀"
    )


def _giveaway_markup(giveaway_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton('🎉 הצטרף להגרלה', callback_data=f'ga_join_{giveaway_id}', style=enums.ButtonStyle.SUCCESS)]])


async def post_giveaway(client, giveaway_id, giveaway):
    msg = await client.send_message(giveaway['chat_id'], _giveaway_text(giveaway), reply_markup=_giveaway_markup(giveaway_id))
    await db.set_giveaway_message(giveaway_id, msg.id)
    return msg


@Client.on_callback_query(filters.regex(r"^ga_join_"))
async def handle_giveaway_join(client, query: CallbackQuery):
    giveaway_id = query.data[len("ga_join_"):]
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.get('ended'):
        return await query.answer("❌ ההגרלה הזו הסתיימה או לא נמצאה.", show_alert=True)

    joined = await db.join_giveaway(giveaway_id, query.from_user.id)
    if not joined:
        return await query.answer("✅ אתה כבר רשום להגרלה!", show_alert=True)

    await query.answer("🎉 נרשמת בהצלחה להגרלה! בהצלחה 🍀", show_alert=True)
    giveaway = await db.get_giveaway(giveaway_id)
    try:
        await query.message.edit_text(_giveaway_text(giveaway), reply_markup=_giveaway_markup(giveaway_id))
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
            await gift_premium_subscription(uid, giveaway['months'], text="זכית בהגרלה! 🎉")
            results.append((uid, True, None))
            try:
                await client.send_message(uid, f"🎉 <b>מזל טוב, זכית בהגרלה!</b>\nקיבלת {giveaway['months']} חודשי פרימיום לטלגרם 🎁")
            except Exception:
                pass
        except Exception as e:
            results.append((uid, False, str(e)))

    await db.finish_giveaway(giveaway_id, [uid for uid, ok, _ in results if ok])

    if results:
        winners_text = "\n".join(
            f"🏆 <a href='tg://user?id={uid}'>{uid}</a>" + ("" if ok else f" (⚠️ שליחה נכשלה: {err})")
            for uid, ok, err in results
        )
    else:
        winners_text = "😔 לא היו משתתפים בהגרלה."

    announce = (
        "🎊 <b>ההגרלה הסתיימה!</b> 🎊\n\n"
        f"👥 סה'כ משתתפים: {len(participants)}\n\n"
        f"<b>המנצחים:</b>\n{winners_text}"
    )

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
