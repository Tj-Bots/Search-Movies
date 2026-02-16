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
UPDATE_CHANNEL = "amoviesnww1o"
REQUEST_GROUP = "https://t.me/+t0Bi1P95xps1Mzk0"

PHOTO_URL = "https://telegra.ph/file/3fa89085f20e4e7e6e38b-c522eb8a573d3961e6.jpg"
