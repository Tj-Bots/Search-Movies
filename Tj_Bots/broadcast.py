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


def _cancel_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton('❌ ביטול', callback_data='bc_cancel')]])


async def send_broadcast_menu(message, is_edit=False):
    text = "📢 <b>שידור הודעות</b>\n\nלמי לשדר?"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(AUDIENCE_LABELS["users"], callback_data="bc_aud_users")],
        [InlineKeyboardButton(AUDIENCE_LABELS["groups"], callback_data="bc_aud_groups")],
        [InlineKeyboardButton(AUDIENCE_LABELS["all"], callback_data="bc_aud_all")],
        [InlineKeyboardButton('חזרה ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)],
    ])
    if is_edit:
        await message.edit_media(InputMediaPhoto(PHOTO_URL, caption=text), reply_markup=markup)
    else:
        await message.reply_photo(PHOTO_URL, caption=text, reply_markup=markup, quote=True)


@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_command(client, message):
    await send_broadcast_menu(message)


def _is_awaiting_input(_, __, message):
    admin_id = message.from_user.id if message.from_user else None
    return admin_id in BC_STATE and BC_STATE[admin_id]['step'] in ('await_content', 'await_buttons')


@Client.on_message(filters.user(ADMINS) & filters.create(_is_awaiting_input))
async def broadcast_input(client, message):
    admin_id = message.from_user.id
    state = BC_STATE[admin_id]

    if state['step'] == 'await_content':
        state['src_chat'] = message.chat.id
        state['src_msg'] = message.id
        state['step'] = 'await_mode'
        try:
            await message.delete()
        except Exception:
            pass

        text = "📨 <b>ההודעה נקלטה.</b>\n\nלשדר עם תיוג מקור (Forward) או בהעתקה נקייה (Copy)?"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('🔁 עם תיוג מקור (Forward)', callback_data='bc_mode_forward')],
            [InlineKeyboardButton('📋 העתקה נקייה (Copy)', callback_data='bc_mode_copy')],
            [InlineKeyboardButton('❌ ביטול', callback_data='bc_cancel')],
        ])
        await client.edit_message_caption(
            state['panel_chat'], state['panel_msg'], caption=text, reply_markup=markup
        )
        return

    if state['step'] == 'await_buttons':
        buttons = _parse_buttons(message.text or "")
        try:
            await message.delete()
        except Exception:
            pass

        if not buttons:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton('❌ ביטול', callback_data='bc_cancel')],
            ])
            await client.edit_message_caption(
                state['panel_chat'], state['panel_msg'],
                caption="❌ <b>לא זוהו כפתורים תקינים.</b>\n\nשלח שוב בפורמט: <code>טקסט - קישור</code> (שורה לכל כפתור).",
                reply_markup=markup
            )
            return

        state['buttons'] = buttons
        await _show_preview(client, admin_id)


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


async def _show_preview(client, admin_id):
    state = BC_STATE[admin_id]
    buttons_markup = InlineKeyboardMarkup(state['buttons']) if state.get('buttons') else None

    try:
        if state['mode'] == 'forward':
            await client.forward_messages(admin_id, state['src_chat'], state['src_msg'])
        else:
            await client.copy_message(admin_id, state['src_chat'], state['src_msg'], reply_markup=buttons_markup)
    except Exception as e:
        await client.edit_message_caption(
            state['panel_chat'], state['panel_msg'],
            caption=f"❌ <b>לא ניתן היה להציג תצוגה מקדימה.</b>\n<code>{e}</code>",
            reply_markup=_cancel_btn()
        )
        return

    mode_label = "🔁 Forward" if state['mode'] == 'forward' else "📋 Copy"
    btns_label = "כן" if state.get('buttons') else "לא"
    text = (
        "🔍 <b>תצוגה מקדימה למעלה 👆</b>\n\n"
        f"<blockquote>👥 קהל: <b>{AUDIENCE_LABELS[state['audience']]}</b>\n"
        f"⚙️ מצב: <b>{mode_label}</b>\n"
        f"🔘 כפתורים: <b>{btns_label}</b></blockquote>\n\n"
        "לשדר?"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('✅ שדר עכשיו', callback_data='bc_confirm'),
         InlineKeyboardButton('❌ ביטול', callback_data='bc_cancel')],
    ])
    await client.edit_message_caption(state['panel_chat'], state['panel_msg'], caption=text, reply_markup=markup)


@Client.on_callback_query(filters.regex(r"^bc_"))
async def broadcast_callback(client, query):
    data = query.data
    admin_id = query.from_user.id

    if data == "bc_menu":
        return await send_broadcast_menu(query.message, is_edit=True)

    if data.startswith("bc_aud_"):
        audience = data[len("bc_aud_"):]
        BC_STATE[admin_id] = {
            'step': 'await_content', 'audience': audience,
            'panel_chat': query.message.chat.id, 'panel_msg': query.message.id,
        }
        text = (
            f"📨 <b>שידור ל{AUDIENCE_LABELS[audience]}</b>\n\n"
            "שלח עכשיו את ההודעה לשידור (טקסט / תמונה / וידאו / קובץ).\n"
            "אפשר גם להעביר (Forward) הודעה קיימת אליי."
        )
        await query.message.edit_caption(text, reply_markup=_cancel_btn())
        return

    state = BC_STATE.get(admin_id)

    if data == "bc_cancel":
        BC_STATE.pop(admin_id, None)
        from .admin import send_admin_panel
        return await send_admin_panel(query.message, is_edit=True)

    if not state:
        return await query.answer("הפעולה פגה, התחל מחדש.", show_alert=True)

    if data in ("bc_mode_forward", "bc_mode_copy"):
        state['mode'] = 'forward' if data == 'bc_mode_forward' else 'copy'

        if state['mode'] == 'forward':
            state['buttons'] = None
            return await _show_preview(client, admin_id)

        state['step'] = 'await_buttons_choice'
        text = "🔘 <b>להוסיף כפתורים להודעה?</b>"
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ כן', callback_data='bc_btns_yes'),
             InlineKeyboardButton('➡️ לא, המשך', callback_data='bc_btns_no')],
            [InlineKeyboardButton('❌ ביטול', callback_data='bc_cancel')],
        ])
        await query.message.edit_caption(text, reply_markup=markup)
        return

    if data == "bc_btns_no":
        state['buttons'] = None
        return await _show_preview(client, admin_id)

    if data == "bc_btns_yes":
        state['step'] = 'await_buttons'
        text = (
            "🔘 <b>שלח את הכפתורים</b>\n\n"
            "שורה אחת לכל כפתור, בפורמט:\n"
            "<code>טקסט - קישור</code>"
        )
        await query.message.edit_caption(text, reply_markup=_cancel_btn())
        return

    if data == "bc_confirm":
        await query.answer()
        await _run_broadcast(client, admin_id)
        return


async def _run_broadcast(client, admin_id):
    state = BC_STATE[admin_id]
    panel_chat, panel_msg = state['panel_chat'], state['panel_msg']
    buttons_markup = InlineKeyboardMarkup(state['buttons']) if state.get('buttons') else None

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
                await client.forward_messages(target_id, state['src_chat'], state['src_msg'])
            else:
                await client.copy_message(target_id, state['src_chat'], state['src_msg'], reply_markup=buttons_markup)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

        if time.time() - last_update >= 5:
            try:
                await client.edit_message_caption(
                    panel_chat, panel_msg,
                    caption=f"⏳ **משדר...**\n✅ נשלח: {count}\n🚫 נכשל: {failed}"
                )
                last_update = time.time()
            except Exception:
                pass

    BC_STATE.pop(admin_id, None)
    text = f"✅ **השידור הסתיים.**\n\n📫 נשלח ל: `{count}`\n🚫 נכשל/נחסם: `{failed}`"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('חזרה לפאנל ⋟', callback_data='adm_home', style=enums.ButtonStyle.PRIMARY)]])
    await client.edit_message_caption(panel_chat, panel_msg, caption=text, reply_markup=markup)
