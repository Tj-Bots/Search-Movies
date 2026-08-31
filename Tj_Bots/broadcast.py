import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from config import ADMINS, PHOTO_URL
from database import db

BC_STATE = {}

AUDIENCE_LABELS = {
    "users": "👥 משתמשים פרטיים",
    "groups": "💬 קבוצות",
    "all": "🌍 הכל (משתמשים + קבוצות)",
}

COLOR_CYCLE = ['normal', 'blue', 'green', 'red']
COLOR_STYLE_MAP = {
    'normal': None,
    'blue': enums.ButtonStyle.PRIMARY,
    'green': enums.ButtonStyle.SUCCESS,
    'red': enums.ButtonStyle.DANGER,
}
COLOR_DOT = {'normal': '⚪️', 'blue': '🔵', 'green': '🟢', 'red': '🔴'}


def _new_state(panel_chat, panel_msg):
    return {
        'panel_chat': panel_chat, 'panel_msg': panel_msg,
        'audience': None, 'text': None,
        'buttons': [], 'pin': False, 'mode': 'copy', 'step': None,
    }


def _build_buttons_markup(buttons):
    if not buttons:
        return None
    rows = []
    for b in buttons:
        style = COLOR_STYLE_MAP.get(b['color'])
        kwargs = {'url': b['url']}
        if style:
            kwargs['style'] = style
        rows.append([InlineKeyboardButton(b['label'], **kwargs)])
    return InlineKeyboardMarkup(rows)


def _composer_markup(state):
    audience_label = AUDIENCE_LABELS.get(state['audience'], '❗ לא נבחר')
    content_label = '📨 הודעה ✅' if state['text'] else '📨 הודעה'
    buttons_label = f"⌨️ כפתורים ✅{len(state['buttons'])}" if state['buttons'] else '⌨️ כפתורים'
    pin_label = '📌 נעיצה: ✓' if state['pin'] else '📌 נעיצה: ✘'
    mode_label = '🔁 Forward' if state['mode'] == 'forward' else '📋 Copy'

    buttons_view_btn = (
        InlineKeyboardButton('👀 צפה', callback_data='bc2_view_buttons')
        if state['buttons'] else
        InlineKeyboardButton('➖', callback_data='noop')
    )

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f'🎯 יעד: {audience_label}', callback_data='bc2_audience')],
        [InlineKeyboardButton(content_label, callback_data='noop'),
         InlineKeyboardButton('👀 צפה', callback_data='bc2_view_content')],
        [InlineKeyboardButton(buttons_label, callback_data='bc2_buttons'), buttons_view_btn],
        [InlineKeyboardButton(pin_label, callback_data='bc2_toggle_pin', style=enums.ButtonStyle.SUCCESS if state['pin'] else enums.ButtonStyle.DANGER),
         InlineKeyboardButton(mode_label, callback_data='bc2_toggle_mode')],
        [InlineKeyboardButton('👀 תצוגה מקדימה מלאה', callback_data='bc2_full_preview')],
        [InlineKeyboardButton('⬅ ביטול', callback_data='bc_cancel', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('✅ שדר עכשיו', callback_data='bc2_send', style=enums.ButtonStyle.SUCCESS)],
    ])


def _composer_text(state):
    text = "📢 <b>עריכת שידור</b>\n\n"
    if state['text']:
        preview = state['text'] if len(state['text']) <= 250 else state['text'][:250] + "…"
        text += f"<b>תוכן נוכחי:</b>\n<blockquote>{preview}</blockquote>\n\n"
    else:
        text += "📝 שלח לי כל הודעת טקסט בכל רגע - היא תיהפך לתוכן השידור.\n\n"
    text += "הגדר את שאר השדות ולחץ 'שדר עכשיו' כשסיימת."
    if state['buttons'] and state['mode'] == 'forward':
        text += "\n\n⚠️ במצב Forward לא ניתן לצרף כפתורים - הם לא יישלחו."
    return text


async def _render_composer(message, state):
    await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=_composer_text(state)), reply_markup=_composer_markup(state))


async def _refresh_composer(client, state):
    await client.edit_message_caption(
        state['panel_chat'], state['panel_msg'], caption=_composer_text(state), reply_markup=_composer_markup(state)
    )


def _buttons_editor_markup(state):
    keyboard = []
    for i, b in enumerate(state['buttons']):
        style = COLOR_STYLE_MAP.get(b['color'])
        kwargs = {'callback_data': 'noop'}
        if style:
            kwargs['style'] = style
        keyboard.append([
            InlineKeyboardButton(b['label'], **kwargs),
            InlineKeyboardButton(f"{COLOR_DOT[b['color']]} 🔁", callback_data=f'bc2_color_{i}'),
        ])
    keyboard.append([InlineKeyboardButton('➕ הוסף כפתורים', callback_data='bc2_buttons_more')])
    if state['buttons']:
        keyboard.append([InlineKeyboardButton('🗑 מחק הכל', callback_data='bc2_buttons_clear_ask', style=enums.ButtonStyle.DANGER)])
    keyboard.append([InlineKeyboardButton('✅ סיום', callback_data='bc2_buttons_done', style=enums.ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(keyboard)


async def _show_buttons_editor(client, state):
    text = "⌨️ <b>עריכת כפתורים</b>\n\nלחץ 🔁 ליד כפתור כדי לשנות את צבעו:\nרגיל ⚪️ ← כחול 🔵 ← ירוק 🟢 ← אדום 🔴"
    await client.edit_message_caption(state['panel_chat'], state['panel_msg'], caption=text, reply_markup=_buttons_editor_markup(state))


@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_command(client, message):
    sent = await message.reply_photo(PHOTO_URL, caption="⏳", quote=True)
    state = _new_state(sent.chat.id, sent.id)
    BC_STATE[message.from_user.id] = state
    await _render_composer(sent, state)


def _is_awaiting_input(_, __, message):
    admin_id = message.from_user.id if message.from_user else None
    return admin_id in BC_STATE


@Client.on_message(filters.user(ADMINS) & filters.create(_is_awaiting_input))
async def broadcast_input(client, message):
    admin_id = message.from_user.id
    state = BC_STATE[admin_id]

    if state['step'] == 'await_buttons':
        new_buttons = _parse_buttons(message.text or "")
        try:
            await message.delete()
        except Exception:
            pass
        if new_buttons:
            state['buttons'].extend(new_buttons)
        state['step'] = None
        return await _show_buttons_editor(client, state)

    # default (idle) - any text message sent becomes the broadcast content
    if not message.text:
        return await message.reply("⚠️ נתמך כרגע טקסט בלבד - שלח הודעת טקסט.", quote=True)

    state['text'] = message.text
    try:
        await message.delete()
    except Exception:
        pass
    await _refresh_composer(client, state)


def _parse_buttons(text):
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        sep = '|' if '|' in line else ' - ' if ' - ' in line else None
        if not sep:
            continue
        label, url = line.split(sep, 1)
        label, url = label.strip(), url.strip()
        if not label or not url.startswith(('http://', 'https://', 'tg://')):
            continue
        rows.append({'label': label, 'url': url, 'color': 'normal'})
    return rows


@Client.on_callback_query(filters.regex(r"^bc"))
async def broadcast_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if data == "bc_menu":
        state = _new_state(query.message.chat.id, query.message.id)
        BC_STATE[admin_id] = state
        return await _render_composer(query.message, state)

    if data == "bc_cancel":
        BC_STATE.pop(admin_id, None)
        from .admin import send_admin_panel
        return await send_admin_panel(query.message, is_edit=True)

    state = BC_STATE.get(admin_id)
    if not state:
        return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)

    if data not in ("bc2_buttons", "bc2_buttons_more"):
        state['step'] = None

    if data == "bc2_audience":
        text = "🎯 <b>בחר יעד לשידור:</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(AUDIENCE_LABELS['users'], callback_data='bc2_aud_users')],
            [InlineKeyboardButton(AUDIENCE_LABELS['groups'], callback_data='bc2_aud_groups')],
            [InlineKeyboardButton(AUDIENCE_LABELS['all'], callback_data='bc2_aud_all')],
            [InlineKeyboardButton('🔙 חזרה לעריכה', callback_data='bc2_back')],
        ])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data.startswith("bc2_aud_"):
        state['audience'] = data[len("bc2_aud_"):]
        return await _refresh_composer(client, state)

    if data == "bc2_back":
        return await _refresh_composer(client, state)

    if data == "bc2_view_content":
        if not state['text']:
            return await query.answer("❌ עדיין לא הוגדרה הודעה.", show_alert=True)
        try:
            await client.send_message(state['panel_chat'], state['text'])
        except Exception as e:
            return await query.answer(f"❌ שגיאה: {e}", show_alert=True)
        return await query.answer()

    if data == "bc2_buttons":
        state['step'] = 'await_buttons'
        text = "⌨️ <b>שלח את הכפתורים</b>\n\nשורה אחת לכל כפתור, בפורמט:\n<code>טקסט - קישור</code>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('🔙 חזרה לעריכה', callback_data='bc2_back')]])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "bc2_view_buttons":
        if not state['buttons']:
            return await query.answer()
        return await _show_buttons_editor(client, state)

    if data == "bc2_buttons_more":
        state['step'] = 'await_buttons'
        text = "⌨️ <b>שלח כפתורים נוספים</b>\n\nשורה אחת לכל כפתור:\n<code>טקסט - קישור</code>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('🔙 חזרה', callback_data='bc2_view_buttons')]])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "bc2_buttons_clear_ask":
        text = "⚠️ <b>אישור מחיקה</b>\n\nלמחוק את כל הכפתורים?"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ כן, מחק הכל', callback_data='bc2_buttons_clear', style=enums.ButtonStyle.DANGER),
             InlineKeyboardButton('❌ ביטול', callback_data='bc2_view_buttons', style=enums.ButtonStyle.PRIMARY)],
        ])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "bc2_buttons_clear":
        state['buttons'] = []
        return await _refresh_composer(client, state)

    if data == "bc2_buttons_done":
        return await _refresh_composer(client, state)

    if data.startswith("bc2_color_"):
        idx = int(data[len("bc2_color_"):])
        if 0 <= idx < len(state['buttons']):
            cur = state['buttons'][idx]['color']
            state['buttons'][idx]['color'] = COLOR_CYCLE[(COLOR_CYCLE.index(cur) + 1) % len(COLOR_CYCLE)]
        return await query.message.edit_reply_markup(_buttons_editor_markup(state))

    if data == "bc2_toggle_pin":
        state['pin'] = not state['pin']
        return await _refresh_composer(client, state)

    if data == "bc2_toggle_mode":
        state['mode'] = 'forward' if state['mode'] == 'copy' else 'copy'
        return await _refresh_composer(client, state)

    if data == "bc2_full_preview":
        if not state['text']:
            return await query.answer("❌ יש להגדיר הודעה קודם.", show_alert=True)
        markup = _build_buttons_markup(state['buttons']) if state['mode'] == 'copy' else None
        try:
            await client.send_message(state['panel_chat'], state['text'], reply_markup=markup)
            return await query.answer("✅ תצוגה מקדימה נשלחה למעלה.")
        except Exception as e:
            return await query.answer(f"❌ שגיאה: {e}", show_alert=True)

    if data == "bc2_send":
        if not state['audience']:
            return await query.answer("❌ יש לבחור יעד קודם.", show_alert=True)
        if not state['text']:
            return await query.answer("❌ יש להגדיר הודעה קודם.", show_alert=True)
        await query.answer()
        return await _run_broadcast(client, admin_id, state)


async def _run_broadcast(client, admin_id, state):
    panel_chat, panel_msg = state['panel_chat'], state['panel_msg']
    buttons_markup = _build_buttons_markup(state['buttons']) if state['mode'] == 'copy' else None

    targets = []
    if state['audience'] in ('users', 'all'):
        async for u in await db.get_all_users():
            targets.append(u['_id'])
    if state['audience'] in ('groups', 'all'):
        async for g in await db.get_all_groups():
            targets.append(g['_id'])

    total = len(targets)
    count = 0
    failed = 0
    start_time = time.time()
    last_update = start_time

    await client.edit_message_caption(panel_chat, panel_msg, caption="🚀 **מתחיל שידור...**", reply_markup=None)

    staged_msg = None
    if state['mode'] == 'forward':
        staged_msg = await client.send_message(panel_chat, state['text'])

    for target_id in targets:
        try:
            if state['mode'] == 'forward':
                sent = await client.forward_messages(target_id, panel_chat, staged_msg.id)
            else:
                sent = await client.send_message(target_id, state['text'], reply_markup=buttons_markup)

            if state['pin']:
                try:
                    msg_id = sent[0].id if isinstance(sent, list) else sent.id
                    await client.pin_chat_message(target_id, msg_id, disable_notification=False, both_sides=True)
                except Exception:
                    pass

            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

        if time.time() - last_update >= 3:
            done = count + failed
            elapsed = time.time() - start_time
            pct = (done / total * 100) if total else 100
            rate = done / elapsed if elapsed > 0 else 0
            eta = int((total - done) / rate) if rate > 0 else 0
            try:
                await client.edit_message_caption(
                    panel_chat, panel_msg,
                    caption=(
                        f"⏳ **משדר... ({pct:.0f}%)**\n"
                        f"📊 התקדמות: {done}/{total}\n"
                        f"✅ נשלח: {count}\n"
                        f"🚫 נכשל: {failed}\n"
                        f"⏱ זמן משוער שנותר: {eta}s"
                    )
                )
                last_update = time.time()
            except Exception:
                pass

    if staged_msg:
        try:
            await client.delete_messages(panel_chat, staged_msg.id)
        except Exception:
            pass

    BC_STATE.pop(admin_id, None)

    total_time = int(time.time() - start_time)
    mins, secs = divmod(total_time, 60)
    text = (
        f"✅ **השידור הסתיים.**\n\n"
        f"📫 נשלח ל: `{count}`\n"
        f"🚫 נכשל/נחסם: `{failed}`\n"
        f"👥 סה'כ יעדים: `{total}`\n"
        f"⏱ משך זמן: `{mins}m {secs}s`"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('חזרה לפאנל ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)]])
    await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)
