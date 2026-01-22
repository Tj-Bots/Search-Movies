from pyrogram import Client, filters

@Client.on_message(filters.command("stickerid"))
async def stickerid(bot, message):
    if message.reply_to_message and message.reply_to_message.sticker:
        sticker = message.reply_to_message.sticker
        await message.reply_text(
            f"**מזהה סטיקר:**\n`{sticker.file_id}`\n\n**מזהה ייחודי:**\n`{sticker.file_unique_id}`",
            quote=True
        )
    else:
        await message.reply_text("❌ אנא הגב על סטיקר עם הפקודה הזו.", quote=True)
