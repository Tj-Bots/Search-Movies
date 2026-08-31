import uuid
from pyrogram import Client, filters
from pyrogram.types import (
    InlineQuery, 
    InlineQueryResultCachedVideo, 
    InlineQueryResultCachedDocument,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from database import db
from config import PHOTO_URL, ADMINS
from .pay import check_quota, consume_search, denial_text

@Client.on_inline_query()
async def inline_search(client: Client, query: InlineQuery):
    results = []
    string = query.query.strip()
    
    if not string:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🔍 חפש סרטים וסדרות",
                description="הקלד שם של סרט או סדרה כדי לחפש",
                input_message_content=InputTextMessageContent(
                    "**כדי להשתמש בחיפוש האינליין, פשוט לחץ על הכפתור וכתוב את שם הסרט/סדרה שאתה רוצה.**"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔎 לחץ כאן לחיפוש", switch_inline_query_current_chat="")]
                ]),
                thumb_url=PHOTO_URL
            )
        )
        await query.answer(results, cache_time=0)
        return

    is_admin_user = query.from_user.id in ADMINS

    if not is_admin_user:
        if await db.get_config('bot_locked', False):
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="🔒 הבוט במצב תחזוקה",
                    description="נסה שוב בקרוב",
                    input_message_content=InputTextMessageContent("🔒 **הבוט נמצא כרגע במצב תחזוקה.** נסה שוב בקרוב."),
                    thumb_url=PHOTO_URL
                )
            )
            await query.answer(results, cache_time=0)
            return

        blocked_words = await db.get_blocked_words()
        lowered = string.lower()
        if any(w in lowered for w in blocked_words):
            await db.increment_blocked_attempt(query.from_user.id)
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="🚫 חיפוש לא מורשה",
                    description="החיפוש הזה אינו מורשה",
                    input_message_content=InputTextMessageContent("🚫 **החיפוש הזה אינו מורשה.**"),
                    thumb_url=PHOTO_URL
                )
            )
            await query.answer(results, cache_time=0)
            return

    if not await check_quota(query.from_user.id):
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🚫 נגמרו הקבצים",
                description="ניתן לרכוש קבצים נוספים בכוכבים",
                input_message_content=InputTextMessageContent(denial_text()),
                thumb_url=PHOTO_URL
            )
        )
        await query.answer(results, cache_time=0, switch_pm_text="🔎 קניית קבצים", switch_pm_parameter="buy")
        return

    await db.log_search_query(string)
    files = await db.search_files(string)
    
    if not files:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="לא נמצאו תוצאות",
                description=f"לא נמצאו קבצים עבור: {string}",
                input_message_content=InputTextMessageContent(f"**לא נמצאו תוצאות עבור: {string}**"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔎 נסה חיפוש אחר", switch_inline_query_current_chat="")]
                ]),
                thumb_url="https://cdn-icons-png.flaticon.com/512/2748/2748614.png"
            )
        )
    else:
        await consume_search(query.from_user.id)
        await db.log_user_search(query.from_user.id, string)
        for file in files[:50]:
            f_name = file['file_name']
            file_id = file['file_id']
            file_type = file.get('file_type', 'document')
            
            f_size = file.get('file_size', 0)
            if f_size > 1024 * 1024 * 1024:
                size_text = f"{f_size / (1024 * 1024 * 1024):.2f} GB"
            else:
                size_text = f"{f_size / (1024 * 1024):.2f} MB"

            caption = f"**{f_name}**\n💾 **גודל:** {size_text}"
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔎 חפש שוב", switch_inline_query_current_chat=string)]
            ])

            if file_type == 'video':
                results.append(
                    InlineQueryResultCachedVideo(
                        id=str(uuid.uuid4()),
                        video_file_id=file_id,
                        title=f"🎬 {f_name}",
                        description=f"💾 גודל: {size_text}",
                        caption=caption,
                        reply_markup=reply_markup
                    )
                )
            else:
                results.append(
                    InlineQueryResultCachedDocument(
                        id=str(uuid.uuid4()),
                        document_file_id=file_id,
                        title=f"📁 {f_name}",
                        description=f"💾 גודל: {size_text}",
                        caption=caption,
                        reply_markup=reply_markup
                    )
                )

    await query.answer(results, cache_time=1)

