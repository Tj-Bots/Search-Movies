from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from .utils import get_readable_size, clean_filename
import asyncio

@Client.on_message(filters.text & ~filters.command(["start", "index", "newindex", "settings", "broadcast", "broadcast_groups", "stats", "restart", "clean", "channels", "watch", "font", "share", "tts", "paste"]))
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

    results = await db.search_files(query)
    
    if not results:
        try:
            msg = await message.reply(f"🔍 לא נמצאו תוצאות לחיפוש:\n**{query}**", quote=True)
            await asyncio.sleep(2)
            await msg.delete()
        except:
            pass
        return

    try:
        await send_results_page(client, message, results, 1, query, settings)
    except Exception as e:
        print(f"Error sending results: {e}")

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
    
    bot_username = client.me.username
    if not bot_username:
        try:
            me = await client.get_me()
            bot_username = me.username
        except:
            bot_username = "Bot"

    text = f"**🔍 תוצאות חיפוש 🎬**\n\n"
    text += f"📄 **שאילתה:** `{query}`\n"
    text += f"🔢 **תוצאות:** `{total_results}`\n"
    text += "**✄ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬**\n\n"
    
    keyboard = []
    display_mode = settings.get('display_mode', 'inline')

    if display_mode == 'inline':
        for res in current_batch:
            clean = clean_filename(res['file_name'])
            size = get_readable_size(res['file_size'])
            btn_text = f"[{size}] {clean}"
            file_id = str(res['_id'])
            keyboard.append([InlineKeyboardButton(btn_text, url=f"https://t.me/{bot_username}?start={file_id}")])
    else:
        chars = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט', 'י']
        for i, res in enumerate(current_batch):
            prefix = chars[i] if i < len(chars) else str(i+1)
            clean = clean_filename(res['file_name'])
            file_id = str(res['_id'])
            link = f"https://t.me/{bot_username}?start={file_id}"
            text += f"🎬 {prefix}. [**{clean}**]({link})\n\n"

    nav = []
    if page > 1: nav.append(InlineKeyboardButton('⬅️', callback_data=f"search#{query}#{page-1}"))
    if page < total_pages: nav.append(InlineKeyboardButton('➡️', callback_data=f"search#{query}#{page+1}"))
    if nav: keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton(f"‏ ￶‏ ￶📃 עמוד {page}/{total_pages}", callback_data="noop")])

    markup = InlineKeyboardMarkup(keyboard)
    
    if is_edit:
        await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True, quote=True)
