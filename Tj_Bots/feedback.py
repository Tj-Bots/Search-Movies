from pyrogram import Client, filters, ContinuePropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMINS
from database import db

AWAITING_FEEDBACK = {}

PROMPT_TEXT = (
    "👈🏻 שלח עכשיו הודעה שתרצה לשלוח לצוות התמיכה.\n\n"
    "<blockquote><i>💡 את הבקשה חייבים לשלוח בהודעה אחת, הודעות נוספות לא יועברו.</i></blockquote>"
)

CONTINUE_HINT = "<blockquote>↩️ <i>השב להודעה זו כדי להמשיך את השיחה.</i></blockquote>"


@Client.on_callback_query(filters.regex(r"^support_"))
async def support_callback(client, query):
    if query.data == "support_start":
        AWAITING_FEEDBACK[query.from_user.id] = {'panel_chat': query.message.chat.id, 'panel_msg': query.message.id}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='support_cancel')]])
        return await query.message.edit_caption(PROMPT_TEXT, reply_markup=markup)

    if query.data == "support_cancel":
        AWAITING_FEEDBACK.pop(query.from_user.id, None)
        from .start import send_home_message
        return await send_home_message(client, query.message, user=query.from_user, is_edit=True)


async def _relay_to_admins(client, message, user_id):
    username_part = f"@{message.from_user.username}" if message.from_user.username else "אין יוזרניים"
    info_text = (
        "📨 <b>פנייה חדשה לתמיכה</b>\n\n"
        f"👤 <b>{message.from_user.mention}</b> ({username_part})\n"
        f"[<code>{user_id}</code>]\n\n"
        "<blockquote>↩️ <i>כדי לענות, השב להודעה זו.</i></blockquote>"
    )
    profile_btn = InlineKeyboardMarkup([[InlineKeyboardButton('👤 פרופיל המשתמש', url=f"tg://openmessage?user_id={user_id}")]])

    for admin_id in ADMINS:
        try:
            await message.forward(admin_id)
            info_msg = await client.send_message(admin_id, info_text, reply_markup=profile_btn)
            await db.save_support_thread(admin_id, info_msg.id, user_id)
        except Exception:
            pass


def _is_awaiting_feedback(_, __, message):
    return bool(message.from_user) and message.from_user.id in AWAITING_FEEDBACK


@Client.on_message(filters.private & filters.create(_is_awaiting_feedback))
async def support_capture(client, message):
    user_id = message.from_user.id
    state = AWAITING_FEEDBACK.pop(user_id, None)

    await _relay_to_admins(client, message, user_id)

    try:
        await message.delete()
    except Exception:
        pass

    if state:
        try:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton('🏠 חזרה לבית', callback_data='home')]])
            await client.edit_message_caption(
                state['panel_chat'], state['panel_msg'],
                caption="✅ ההודעה שלך נשלחה לצוות התמיכה, נחזור אליך בהקדם!",
                reply_markup=markup
            )
        except Exception:
            pass


@Client.on_message(filters.user(ADMINS) & filters.private & filters.reply)
async def support_admin_reply(client, message):
    replied = message.reply_to_message
    user_id = await db.get_support_thread(message.chat.id, replied.id) if replied else None
    if not user_id:
        raise ContinuePropagation

    try:
        sent = await message.copy(user_id)
        hint = await client.send_message(user_id, CONTINUE_HINT, reply_to_message_id=sent.id)
        await db.save_continue_marker(user_id, sent.id)
        await db.save_continue_marker(user_id, hint.id)
        await message.reply("✅ נשלח למשתמש.", quote=True)
    except Exception as e:
        await message.reply(f"❌ שליחה נכשלה: {e}", quote=True)


def _is_continuation_reply(_, __, message):
    return bool(message.from_user) and message.reply_to_message is not None


@Client.on_message(filters.private & filters.reply & filters.create(_is_continuation_reply))
async def support_continue(client, message):
    if message.from_user.id in ADMINS:
        raise ContinuePropagation

    is_marker = await db.is_continue_marker(message.from_user.id, message.reply_to_message.id)
    if not is_marker:
        raise ContinuePropagation

    await _relay_to_admins(client, message, message.from_user.id)
    await message.reply("✅ ההודעה נשלחה לצוות התמיכה.", quote=True)
