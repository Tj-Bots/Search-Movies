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


def _new_state(panel_chat, panel_msg):
    return {
        'panel_chat': panel_chat, 'panel_msg': panel_msg,
        'audience': None, 'src_chat': None, 'src_msg': None,
        'buttons': None, 'pin': False, 'mode': 'copy', 'step': None,
    }


def _composer_markup(state):
    audience_label = AUDIENCE_LABELS.get(state['audience'], '❗ לא נבחר')
    content_status = '✅ הוגדר (למעלה 👆)' if state['src_msg'] else '➖ ריק'
    buttons_status = f"✅ {len(state['buttons'])} כפתורים" if state.get('buttons') else '➖ ריק'
    pin_label = '📌 נעיצה: ✓' if state['pin'] else '📌 נעיצה: ✘'
    mode_label = '🔁 Forward' if state['mode'] == 'forward' else '📋 Copy'

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f'🎯 יעד: {audience_label}', callback_data='bc2_audience')],
        [InlineKeyboardButton('📨 הודעה', callback_data='bc2_content'),
         InlineKeyboardButton(content_status, callback_data='bc2_view_content' if state['src_msg'] else 'noop')],
        [InlineKeyboardButton('⌨️ כפתורים', callback_data='bc2_buttons'),
         InlineKeyboardButton(buttons_status, callback_data='bc2_view_buttons' if state.get('buttons') else 'noop')],
        [InlineKeyboardButton(pin_label, callback_data='bc2_toggle_pin', style=enums.ButtonStyle.SUCCESS if state['pin'] else enums.ButtonStyle.DANGER),
         InlineKeyboardButton(mode_label, callback_data='bc2_toggle_mode')],
        [InlineKeyboardButton('👀 תצוגה מקדימה מלאה', callback_data='bc2_full_preview')],
        [InlineKeyboardButton('⬅ ביטול', callback_data='bc_cancel', style=enums.ButtonStyle.DANGER),
         InlineKeyboardButton('✅ שדר עכשיו', callback_data='bc2_send', style=enums.ButtonStyle.SUCCESS)],
    ])


def _composer_text(state):
    text = "📢 <b>עריכת שידור</b>\n\nהגדר את כל השדות ולחץ 'שדר עכשיו' כשסיימת."
    if state.get('buttons') and state['mode'] == 'forward':
        text += "\n\n⚠️ במצב Forward לא ניתן לצרף כפתורים - הם לא יישלחו."
    return text


async def _render_composer(message, state):
    await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=_composer_text(state)), reply_markup=_composer_markup(state))


async def _refresh_composer(client, state):
    await client.edit_message_caption(
        state['panel_chat'], state['panel_msg'], caption=_composer_text(state), reply_markup=_composer_markup(state)
    )


async def _clear_stash(client, state):
    if state.get('src_msg'):
        try:
            await client.delete_messages(state['src_chat'], state['src_msg'])
        except Exception:
            pass


@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_command(client, message):
    sent = await message.reply_photo(PHOTO_URL, caption="⏳", quote=True)
    state = _new_state(sent.chat.id, sent.id)
    BC_STATE[message.from_user.id] = state
    await _render_composer(sent, state)


def _is_awaiting_input(_, __, message):
    admin_id = message.from_user.id if message.from_user else None
    return admin_id in BC_STATE and BC_STATE[admin_id].get('step') in ('await_content', 'await_buttons')


@Client.on_message(filters.user(ADMINS) & filters.create(_is_awaiting_input))
async def broadcast_input(client, message):
    admin_id = message.from_user.id
    state = BC_STATE[admin_id]

    if state['step'] == 'await_content':
        old_chat, old_msg = state.get('src_chat'), state.get('src_msg')
        try:
            stored = await message.copy(state['panel_chat'])
        except Exception:
            stored = None
        try:
            await message.delete()
        except Exception:
            pass
        if old_msg:
            try:
                await client.delete_messages(old_chat, old_msg)
            except Exception:
                pass
        if stored:
            state['src_chat'] = stored.chat.id
            state['src_msg'] = stored.id
        state['step'] = None
        return await _refresh_composer(client, state)

    if state['step'] == 'await_buttons':
        buttons = _parse_buttons(message.text or "")
        try:
            await message.delete()
        except Exception:
            pass
        if buttons:
            state['buttons'] = buttons
        state['step'] = None
        return await _refresh_composer(client, state)


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
        rows.append([InlineKeyboardButton(label, url=url)])
    return rows or None


@Client.on_callback_query(filters.regex(r"^bc"))
async def broadcast_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if data == "bc_menu":
        old = BC_STATE.get(admin_id)
        if old:
            await _clear_stash(client, old)
        state = _new_state(query.message.chat.id, query.message.id)
        BC_STATE[admin_id] = state
        return await _render_composer(query.message, state)

    if data == "bc_cancel":
        state = BC_STATE.pop(admin_id, None)
        if state:
            await _clear_stash(client, state)
        from .admin import send_admin_panel
        return await send_admin_panel(query.message, is_edit=True)

    state = BC_STATE.get(admin_id)
    if not state:
        return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)

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

    if data == "bc2_content":
        state['step'] = 'await_content'
        text = "📨 <b>שלח עכשיו את ההודעה לשידור</b> (טקסט / תמונה / וידאו / קובץ).\nאפשר גם להעביר (Forward) הודעה קיימת אליי."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('🔙 חזרה לעריכה', callback_data='bc2_back')]])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "bc2_view_content":
        if state['src_msg']:
            try:
                await client.copy_message(state['panel_chat'], state['src_chat'], state['src_msg'])
            except Exception:
                pass
        return await query.answer()

    if data == "bc2_buttons":
        state['step'] = 'await_buttons'
        text = "⌨️ <b>שלח את הכפתורים</b>\n\nשורה אחת לכל כפתור, בפורמט:\n<code>טקסט - קישור</code>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('🔙 חזרה לעריכה', callback_data='bc2_back')]])
        return await query.message.edit_caption(text, reply_markup=markup)

    if data == "bc2_view_buttons":
        if state.get('buttons'):
            listing = "\n".join(f"{row[0].text} → {row[0].url}" for row in state['buttons'])
            return await query.answer(listing[:200], show_alert=True)
        return await query.answer()

    if data == "bc2_toggle_pin":
        state['pin'] = not state['pin']
        return await _refresh_composer(client, state)

    if data == "bc2_toggle_mode":
        state['mode'] = 'forward' if state['mode'] == 'copy' else 'copy'
        return await _refresh_composer(client, state)

    if data == "bc2_full_preview":
        if not state['src_msg']:
            return await query.answer("❌ יש להגדיר הודעה קודם.", show_alert=True)
        markup = InlineKeyboardMarkup(state['buttons']) if state.get('buttons') and state['mode'] == 'copy' else None
        try:
            if state['mode'] == 'forward':
                await client.forward_messages(state['panel_chat'], state['src_chat'], state['src_msg'])
            else:
                await client.copy_message(state['panel_chat'], state['src_chat'], state['src_msg'], reply_markup=markup)
            return await query.answer("✅ תצוגה מקדימה נשלחה למעלה.")
        except Exception as e:
            return await query.answer(f"❌ שגיאה: {e}", show_alert=True)

    if data == "bc2_send":
        if not state['audience']:
            return await query.answer("❌ יש לבחור יעד קודם.", show_alert=True)
        if not state['src_msg']:
            return await query.answer("❌ יש להגדיר הודעה קודם.", show_alert=True)
        await query.answer()
        return await _run_broadcast(client, admin_id, state)


async def _run_broadcast(client, admin_id, state):
    panel_chat, panel_msg = state['panel_chat'], state['panel_msg']
    buttons_markup = InlineKeyboardMarkup(state['buttons']) if state.get('buttons') and state['mode'] == 'copy' else None

    targets = []
    if state['audience'] in ('users', 'all'):
        async for u in await db.get_all_users():
            targets.append(u['_id'])
    if state['audience'] in ('groups', 'all'):
        async for g in await db.get_all_groups():
            targets.append(g['_id'])

    count = 0
    failed = 0
    last_update = time.time()

    await client.edit_message_caption(panel_chat, panel_msg, caption="🚀 **מתחיל שידור...**", reply_markup=None)

    for target_id in targets:
        try:
            if state['mode'] == 'forward':
                sent = await client.forward_messages(target_id, state['src_chat'], state['src_msg'])
            else:
                sent = await client.copy_message(target_id, state['src_chat'], state['src_msg'], reply_markup=buttons_markup)

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

        if time.time() - last_update >= 5:
            try:
                await client.edit_message_caption(
                    panel_chat, panel_msg, caption=f"⏳ **משדר...**\n✅ נשלח: {count}\n🚫 נכשל: {failed}"
                )
                last_update = time.time()
            except Exception:
                pass

    await _clear_stash(client, state)
    BC_STATE.pop(admin_id, None)

    text = f"✅ **השידור הסתיים.**\n\n📫 נשלח ל: `{count}`\n🚫 נכשל/נחסם: `{failed}`"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('חזרה לפאנל ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)]])
    await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)
