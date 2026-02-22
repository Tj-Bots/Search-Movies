import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = "TjBotDB"

# מנהלים: ניתן להוסיף כמה מנהלים מופרדים ברווח או פסיק
ADMINS = [int(x) for x in os.environ.get("ADMINS", "").replace(",", " ").split()]

LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))
UPDATE_CHANNEL = "searchgram_bots"
REQUEST_GROUP = "https://t.me/searchgram_group

PHOTO_URL = "https://i.ibb.co/BK2j0c7p/x.jpg"

AUTH_CHANNEL_FORCE = os.environ.get("AUTH_CHANNEL_FORCE", "False").lower() == "true"
