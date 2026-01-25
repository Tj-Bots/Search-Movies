import motor.motor_asyncio
import re
from config import MONGO_URI, DB_NAME

class Database:
    def __init__(self):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.db = None
        self.files = None
        self.users = None
        self.groups = None
        self.settings = None
        self.watched = None
        self.banned = None
        self.banned_chats = None
        self.set_db_name(DB_NAME)

    def set_db_name(self, name):
        self.db = self._client[name]
        self.files = self.db.files
        self.users = self.db.users
        self.groups = self.db.groups
        self.settings = self.db.settings
        self.watched = self.db.watched
        self.banned = self.db.banned
        self.banned_chats = self.db.banned_chats
        print(f"✅ Database switched to: {name}")

    async def add_user(self, user_id, first_name):
        if self.users is None: return False
        user = await self.users.find_one({'_id': user_id})
        if not user:
            await self.users.insert_one({'_id': user_id, 'first_name': first_name})
            return True
        return False

    async def add_group(self, chat_id, title):
        if self.groups is None: return False
        group = await self.groups.find_one({'_id': chat_id})
        if not group:
            await self.groups.insert_one({'_id': chat_id, 'title': title})
            return True
        return False

    async def get_all_users(self):
        return self.users.find({})

    async def get_all_groups(self):
        return self.groups.find({})

    async def save_file(self, file_data):
        if self.files is None: return "error"
        exist = await self.files.find_one({'file_unique_id': file_data['file_unique_id']})
        if exist:
            return "duplicate"
        await self.files.insert_one(file_data)
        return "saved"

    async def get_file(self, _id):
        from bson.objectid import ObjectId
        try:
            return await self.files.find_one({'_id': ObjectId(_id)})
        except:
            return None

    async def search_files(self, query):
        clean_query = re.sub(r'[._\-]', ' ', query)
        words = clean_query.split()
        
        regex_list = []
        for word in words:
            escaped_word = re.escape(word)
            regex_list.append(re.compile(escaped_word, re.IGNORECASE))
        
        cursor = self.files.find({"file_name": {"$all": regex_list}})
        results = await cursor.to_list(length=100)
        
        def sort_key(item):
            name = item.get('file_name', '')
            s = re.search(r'(?:עונה|season|s)\s*(\d+)', name, re.I)
            e = re.search(r'(?:פרק|episode|e)\s*(\d+)', name, re.I)
            season = int(s.group(1)) if s else 0
            episode = int(e.group(1)) if e else 0
            return (season, episode)

        results.sort(key=sort_key)
        return results

    async def get_settings(self, chat_id):
        settings = await self.settings.find_one({'_id': chat_id})
        if not settings:
            return {'results_per_page': 10, 'display_mode': 'inline', 'search_trigger': 'all', 'show_image': True}
        return settings

    async def update_settings(self, chat_id, key, value):
        await self.settings.update_one({'_id': chat_id}, {'$set': {key: value}}, upsert=True)

    async def add_watched_channel(self, chat_id):
        await self.watched.update_one({'_id': chat_id}, {'$set': {'_id': chat_id}}, upsert=True)

    async def remove_watched_channel(self, chat_id):
        await self.watched.delete_one({'_id': chat_id})

    async def get_watched_channels(self):
        channels = await self.watched.find({}).to_list(length=1000)
        return [c['_id'] for c in channels]

    async def delete_all_files(self):
        result = await self.files.delete_many({})
        return result.deleted_count

    async def delete_all_users(self):
        result = await self.users.delete_many({})
        return result.deleted_count

    async def delete_all_groups(self):
        result = await self.groups.delete_many({})
        return result.deleted_count

    async def delete_file_by_unique_id(self, unique_id):
        await self.files.delete_one({'file_unique_id': unique_id})

    async def delete_files_by_chat_id(self, chat_id):
        result = await self.files.delete_many({'chat_id': chat_id})
        return result.deleted_count

    async def ban_user(self, user_id, reason="לא צוינה סיבה"):
        await self.banned.update_one(
            {'_id': user_id}, 
            {'$set': {'_id': user_id, 'reason': reason}}, 
            upsert=True
        )

    async def unban_user(self, user_id):
        await self.banned.delete_one({'_id': user_id})

    async def get_ban_status(self, user_id):
        if self.banned is None: return None
        return await self.banned.find_one({'_id': user_id})

    async def ban_chat(self, chat_id, reason="לא צוינה סיבה"):
        await self.banned_chats.update_one(
            {'_id': chat_id}, 
            {'$set': {'_id': chat_id, 'reason': reason}}, 
            upsert=True
        )

    async def unban_chat(self, chat_id):
        await self.banned_chats.delete_one({'_id': chat_id})

    async def get_chat_ban_status(self, chat_id):
        if self.banned_chats is None: return None
        return await self.banned_chats.find_one({'_id': chat_id})

db = Database()
