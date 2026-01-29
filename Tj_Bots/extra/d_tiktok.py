import os
import time
import asyncio
import math
import re
import subprocess
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class MyLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        print(msg)

def get_full_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        }
        session = requests.Session()
        response = session.head(url, allow_redirects=True, timeout=10, headers=headers)
        return response.url
    except:
        return url

def extract_url(text):
    regex = r'(https?://(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?://(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,})'
    match = re.search(regex, text)
    if match:
        return match.group(0)
    return None

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def time_formatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2] if tmp else "0s"

async def progress(current, total, message, start_time, action_text, last_update_ref):
    now = time.time()
    if current != total and (now - last_update_ref[0]) < 5:
        return
    last_update_ref[0] = now
    
    diff = now - start_time
    if diff == 0: diff = 0.1
    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff) * 1000
    estimated_total_time = elapsed_time + (round((total - current) / speed) * 1000 if speed > 0 else 0)
    estimated_str = time_formatter(milliseconds=estimated_total_time)

    progress_str = "[{0}{1}] \n**{2}%**".format(
        ''.join(["●" for i in range(math.floor(percentage / 10))]),
        ''.join(["○" for i in range(10 - math.floor(percentage / 10))]),
        round(percentage, 2))

    tmp = f"{action_text}...\n{progress_str}\n{humanbytes(current)} of {humanbytes(total)}\n**Speed:** {humanbytes(speed)}/s\n**ETA:** {estimated_str}"
    try:
        await message.edit(tmp)
    except:
        pass

def generate_thumbnail(video_path, thumb_path):
    try:
        subprocess.call(['ffmpeg', '-i', video_path, '-ss', '00:00:01.000', '-vframes', '1', thumb_path, '-y'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(thumb_path):
            return thumb_path
    except Exception:
        pass
    return None

def download_media_sync(url, unique_id):
    filename_base = f"downloads/{unique_id}"
    
    if "?" in url:
        url = url.split("?")[0]
    
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{filename_base}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'logger': MyLogger(),
        'noplaylist': True, 
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    }

    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url, download=True)
            
            if info_dict is None:
                return None, None, "error", None

            downloaded_file = None
            for file in os.listdir("downloads"):
                if file.startswith(str(unique_id)) and not file.endswith(('_thumb.jpg', '.part')):
                    downloaded_file = os.path.join("downloads", file)
                    break
            
            if downloaded_file:
                ext = info_dict.get('ext', 'mp4')
                if ext not in ['mp4', 'mkv', 'webm', 'mov']:
                    return None, "photo_detected", "photo_mode", None
            
            description = info_dict.get('description') or info_dict.get('title') or "ללא תיאור"
            return downloaded_file, description, info_dict.get('ext'), None

        except Exception as e:
            return None, str(e), "error", None

@Client.on_message(filters.command("d"))
async def download_handler(client, message):
    if not yt_dlp:
        return await message.reply("❌ **שגיאת מערכת:** הספרייה `yt-dlp` חסרה.", quote=True)

    text_to_check = message.text.split(None, 1)[1] if len(message.command) > 1 else (message.reply_to_message.text or message.reply_to_message.caption or "") if message.reply_to_message else ""
    
    if not text_to_check:
        return await message.reply("❌ **שגיאה: חסר קישור.**\nשלח `/d [קישור]` או הגב על הודעה.", quote=True)

    url = extract_url(text_to_check)
    if not url:
        return await message.reply("⚠️ לא נמצא קישור חוקי.", quote=True)

    if "tiktok.com" not in url:
        return await message.reply("⚠️ המערכת תומכת כרגע בהורדות מ-TikTok בלבד.", quote=True)

    full_url = await asyncio.get_event_loop().run_in_executor(None, get_full_url, url)
    if "/photo/" in full_url:
        return await message.reply("⚠️ **נכון לעכשיו, הבוט תומך בהורדת סרטונים בלבד (לא תמונות).**", quote=True)

    status_msg = await message.reply("📥 **מוריד מדיה...**", quote=True)
    if not os.path.exists("downloads"): os.makedirs("downloads")

    unique_id = f"{message.chat.id}_{message.id}_{int(time.time())}"

    try:
        loop = asyncio.get_event_loop()
        file_path, description, ext, _ = await loop.run_in_executor(None, download_media_sync, full_url, unique_id)
        
        if ext == "photo_mode":
             await status_msg.edit("⚠️ **מצטער, הבוט מזהה שזה פוסט תמונות/אודיו ולא וידאו רגיל.**")
             if file_path and os.path.exists(file_path): os.remove(file_path)
             return

        if ext == "error":
            error_msg = str(description) if description else "שגיאה לא ידועה"
            clean_error = "שגיאה לא ידועה"
            if "HTTP Error 530" in error_msg or "rate-limit" in error_msg: clean_error = "TikTok חוסם את הבקשה. נסה שוב מאוחר יותר."
            else: clean_error = error_msg[:200]
            
            await status_msg.edit(f"❌ **ההורדה נכשלה:**\n`{clean_error}`")
            return

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit("❌ ההורדה נכשלה (לא נמצא קובץ וידאו).")
            return

        if not file_path.lower().endswith(('.mp4', '.mkv', '.webm', '.mov')):
             await status_msg.edit("⚠️ **הקובץ שירד אינו וידאו.**")
             if os.path.exists(file_path): os.remove(file_path)
             return

        await status_msg.edit("📤 **מעבד ומעלה...**")
        
        bot_first_name = client.me.first_name
        bot_link = f"https://t.me/{client.me.username}"
        if len(description) > 800: description = description[:797] + "..."
        caption_text = f"**🎥תיאור: [{description}]({url})**\n\n**🤖 הועלה על ידי: [{bot_first_name}]({bot_link})**"
        
        display_filename = f"uploaded_by_{client.me.username}.mp4"
        
        temp_thumb = f"downloads/{unique_id}_thumb.jpg"
        thumb_path = generate_thumbnail(file_path, temp_thumb)

        start_time = time.time()
        last_update_ref = [0]

        await client.send_video(
            message.chat.id, file_path, caption=caption_text, file_name=display_filename,
            thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            progress=progress, progress_args=(status_msg, start_time, "📤 **מעלה וידאו**", last_update_ref),
            reply_to_message_id=message.reply_to_message.id if message.reply_to_message else message.id
        )

        await status_msg.delete()
        
        if os.path.exists(file_path): os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)

    except Exception as e:
        await status_msg.edit(f"❌ שגיאה בקוד: `{str(e)}`")
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            os.remove(file_path)
