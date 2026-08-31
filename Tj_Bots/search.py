
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from config import UPDATE_CHANNEL, ADMINS
from .utils import get_readable_size, clean_filename
from .pay import check_quota, consume_search, out_of_quota_markup, denial_text
import asyncio

@Client.on_message(filters.text & ~filters.command(["start", "index", "newindex", "settings", "broadcast", "stats", "restart", "clean", "channels", "watch", "font", "share", "tts", "paste", "buy", "status", "admin"]))
async def search_handler(client, message):
    query = message.text
    if query.startswith("/"): return
    chat_id = message.chat.id

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(chat_id, message.chat.title)
        settings = await db.get_settings(chat_id)
        if settings.get('search_trigger') == 'bang' and not query.startswith('!'): return
        if query.startswith('!'): query = query[1:].strip()
    else:
        settings = await db.get_settings(chat_id)

    if len(query) < 2: return

    is_admin_user = bool(message.from_user) and message.from_user.id in ADMINS

    if not is_admin_user:
        if await db.get_config('bot_locked', False):
            return await message.reply("🔒 **הבוט נמצא כרגע במצב תחזוקה.** נסה שוב בקרוב.", quote=True)

        blocked_words = await db.get_blocked_words()
        lowered = query.lower()
        if any(w in lowered for w in blocked_words):
            return await message.reply("🚫 **החיפוש הזה אינו מורשה.**", quote=True)

    if message.from_user and not await check_quota(message.from_user.id):
        return await message.reply(
            denial_text(),
            reply_markup=out_of_quota_markup(client.me.username),
            quote=True
        )

    await db.log_search_query(query)
    results = await db.search_files(query)

    if not results:
        try:
            msg = await message.reply(f"**לא נמצאו תוצאות לחיפוש: `{query}`** <tg-emoji emoji-id='5924497670721769339'>🙅‍♂️</tg-emoji>", quote=True)
            await asyncio.sleep(2)
            await msg.delete()
        except:
            pass
        return

    if message.from_user:
        await consume_search(message.from_user.id)

    try:
        await send_results_page(client, message, results, 1, query, settings)
    except Exception as e:
        print(f"Error sending results: {e}")

@Client.on_callback_query(filters.regex(r"^dl_"))
async def handle_search_click(client, query: CallbackQuery):
    file_id = query.data.split("_")[1]
    bot_username = client.me.username
    await query.answer(url=f"https://t.me/{bot_username}?start={file_id}")

@Client.on_callback_query(filters.regex(r"^search#"))
async def search_pagination(client, query):
    try:
        _, q_str, page_str = query.data.split("#")
        page = int(page_str)
        settings = await db.get_settings(query.message.chat.id)
        results = await db.search_files(q_str)
        
        if not results:
            return await query.answer("החיפוש פג תוקף.", show_alert=True)
            
        await send_results_page(client, query.message, results, page, q_str, settings, is_edit=True)
    except Exception as e:
        print(f"Error in pagination: {e}")

async def send_results_page(client, message, results, page, query, settings, is_edit=False):
    per_page = settings.get('results_per_page', 10)
    total_results = len(results)
    total_pages = (total_results + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    current_batch = results[start_idx : start_idx + per_page]
    
    bot_username = client.me.username or "Bot"

    text = f"<b><tg-emoji emoji-id='5319230516929502602'>🔍</tg-emoji></b> <b><i><u>תוצאות חיפוש</u></i></b> <tg-emoji emoji-id='5452069934089641166'>❓</tg-emoji>\n\n"
    text += f"<blockquote><b><tg-emoji emoji-id='5397782960512444700'>📌</tg-emoji></b>   <b>שאילתה:</b> <code>{query}</code></blockquote>\n"
    text += f"<blockquote><b><tg-emoji emoji-id='5282843764451195532'>🖥</tg-emoji></b>   <b>תוצאות:</b> <code>{total_results}</code></blockquote>\n"
    text += "\n**<tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji><tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji>**\n\n"
    
    keyboard = []
    display_mode = settings.get('display_mode', 'inline')

    if display_mode == 'inline':
        for res in current_batch:
            clean = clean_filename(res['file_name'])
            size = get_readable_size(res['file_size'])
            btn_text = f"[{size}] {clean}"
            file_id = str(res['_id'])
            
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"dl_{file_id}", style=enums.ButtonStyle.PRIMARY)])
            
    else:
        chars = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט', 'י']
        for i, res in enumerate(current_batch):
            prefix = chars[i] if i < len(chars) else str(i+1)
            clean = clean_filename(res['file_name'])
            file_id = str(res['_id'])
            link = f"https://t.me/{bot_username}?start={file_id}"
            text += f"🎬 **{prefix}. [{clean}]({link})**\n\n"

    nav = []
    if page > 1: nav.append(InlineKeyboardButton('⬅️', callback_data=f"search#{query}#{page-1}", style=enums.ButtonStyle.SUCCESS))
    if page < total_pages: nav.append(InlineKeyboardButton('➡️', callback_data=f"search#{query}#{page+1}", style=enums.ButtonStyle.SUCCESS))
    if nav: keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton(f"‏ ￶‏ ￶📃 עמוד {page}/{total_pages}", callback_data="noop", style=enums.ButtonStyle.DANGER)])

    markup = InlineKeyboardMarkup(keyboard)
    
    if is_edit:
        await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True, quote=True)
