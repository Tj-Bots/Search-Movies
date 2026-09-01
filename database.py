import motor.motor_asyncio
import re
import time
from config import MONGO_URI, DB_NAME

class Database:
    def __init__(self):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.db = self._client[DB_NAME]
        self.files = None
        self.users = None
        self.groups = None
        self.settings = None
        self.watched = None
        self.banned = None
        self.banned_chats = None
        self.purchases = None
        self.bot_config = None
        self.search_log = None
        self.user_search_log = None
        self.support_threads = None
        self.sub_admins = None

    async def init_database(self, bot):
        me = await bot.get_me()
        prefix = me.username
        self.files = self.db[f"{prefix}_files"]
        self.users = self.db[f"{prefix}_users"]
        self.groups = self.db[f"{prefix}_groups"]
        self.settings = self.db[f"{prefix}_settings"]
        self.watched = self.db[f"{prefix}_watched"]
        self.banned = self.db[f"{prefix}_banned"]
        self.banned_chats = self.db[f"{prefix}_banned_chats"]
        self.purchases = self.db[f"{prefix}_purchases"]
        self.bot_config = self.db[f"{prefix}_bot_config"]
        self.search_log = self.db[f"{prefix}_search_log"]
        self.user_search_log = self.db[f"{prefix}_user_search_log"]
        self.support_threads = self.db[f"{prefix}_support_threads"]
        self.sub_admins = self.db[f"{prefix}_sub_admins"]

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
        results = await cursor.to_list(length=1000)
        
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

    async def get_banned_users_page(self, page, per_page=10):
        skip = (page - 1) * per_page
        cursor = self.banned.find({}).skip(skip).limit(per_page)
        rows = await cursor.to_list(length=per_page)
        total = await self.banned.count_documents({})
        return rows, total

    async def get_banned_chats_page(self, page, per_page=10):
        skip = (page - 1) * per_page
        cursor = self.banned_chats.find({}).skip(skip).limit(per_page)
        rows = await cursor.to_list(length=per_page)
        total = await self.banned_chats.count_documents({})
        return rows, total

    async def get_search_quota(self, user_id):
        user = await self.users.find_one({'_id': user_id}) or {}
        return {
            'free_used': user.get('free_used', 0),
            'free_date': user.get('free_date', ''),
            'search_credits': user.get('search_credits', 0),
            'unlimited_until': user.get('unlimited_until', 0),
            'extra_daily_limit': user.get('extra_daily_limit', 0),
        }

    async def add_referral_bonus(self, user_id, amount=1):
        await self.users.update_one({'_id': user_id}, {'$inc': {'extra_daily_limit': amount}}, upsert=True)

    async def get_referral_count(self, user_id):
        return await self.users.count_documents({'referred_by': user_id})

    async def set_referred_by(self, user_id, referrer_id):
        await self.users.update_one({'_id': user_id}, {'$set': {'referred_by': referrer_id}}, upsert=True)

    async def reset_free_usage(self, user_id, today):
        await self.users.update_one({'_id': user_id}, {'$set': {'free_used': 0, 'free_date': today}}, upsert=True)

    async def reset_all_free_usage(self, today):
        result = await self.users.update_many({}, {'$set': {'free_used': 0, 'free_date': today}})
        return result.modified_count

    async def increment_free_usage(self, user_id):
        await self.users.update_one({'_id': user_id}, {'$inc': {'free_used': 1}}, upsert=True)

    async def use_search_credit(self, user_id):
        result = await self.users.find_one_and_update(
            {'_id': user_id, 'search_credits': {'$gt': 0}},
            {'$inc': {'search_credits': -1}}
        )
        return result is not None

    async def add_search_credits(self, user_id, amount):
        await self.users.update_one({'_id': user_id}, {'$inc': {'search_credits': amount}}, upsert=True)

    async def extend_unlimited(self, user_id, seconds):
        quota = await self.get_search_quota(user_id)
        base = quota['unlimited_until'] if quota['unlimited_until'] > time.time() else time.time()
        until = base + seconds
        await self.users.update_one({'_id': user_id}, {'$set': {'unlimited_until': until}}, upsert=True)
        return until

    async def log_purchase(self, user_id, package_key, kind, stars, value):
        if self.purchases is None: return
        await self.purchases.insert_one({
            'user_id': user_id, 'package_key': package_key, 'kind': kind,
            'stars': stars, 'value': value, 'date': time.time()
        })

    async def get_purchase_stats(self):
        if self.purchases is None: return {'total_stars': 0, 'total_count': 0, 'packages': {}}
        pipeline = [{'$group': {'_id': '$package_key', 'stars': {'$sum': '$stars'}, 'count': {'$sum': 1}}}]
        rows = await self.purchases.aggregate(pipeline).to_list(length=100)
        return {
            'total_stars': sum(r['stars'] for r in rows),
            'total_count': sum(r['count'] for r in rows),
            'packages': {r['_id']: {'stars': r['stars'], 'count': r['count']} for r in rows},
        }

    async def get_config(self, key, default=None):
        if self.bot_config is None: return default
        doc = await self.bot_config.find_one({'_id': 'global'})
        if not doc: return default
        return doc.get(key, default)

    async def set_config(self, key, value):
        await self.bot_config.update_one({'_id': 'global'}, {'$set': {key: value}}, upsert=True)

    async def get_blocked_words(self):
        doc = await self.bot_config.find_one({'_id': 'global'}) or {}
        return doc.get('blocked_words', [])

    async def add_blocked_word(self, word):
        await self.bot_config.update_one({'_id': 'global'}, {'$addToSet': {'blocked_words': word}}, upsert=True)

    async def remove_blocked_word(self, word):
        await self.bot_config.update_one({'_id': 'global'}, {'$pull': {'blocked_words': word}})

    async def log_search_query(self, query, found=True):
        key = query.strip().lower()
        if not key or self.search_log is None: return
        await self.search_log.update_one(
            {'_id': key},
            {'$inc': {'count': 1, 'success_count': 1 if found else 0}, '$set': {'last': time.time()}},
            upsert=True
        )

    async def get_popular_searches(self, limit=10):
        if self.search_log is None: return []
        cursor = self.search_log.find({}).sort('count', -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_search_stats_totals(self):
        if self.search_log is None: return (0, 0)
        pipeline = [{'$group': {'_id': None, 'total': {'$sum': '$count'}, 'success': {'$sum': '$success_count'}}}]
        rows = await self.search_log.aggregate(pipeline).to_list(length=1)
        if not rows: return (0, 0)
        return (rows[0].get('success', 0), rows[0].get('total', 0))

    async def clear_popular_searches(self):
        if self.search_log is None: return
        await self.search_log.delete_many({})

    async def get_users_page(self, page, per_page=10):
        skip = (page - 1) * per_page
        cursor = self.users.find({}).sort('_id', 1).skip(skip).limit(per_page)
        users = await cursor.to_list(length=per_page)
        total = await self.users.count_documents({})
        return users, total

    async def find_user(self, user_id):
        return await self.users.find_one({'_id': user_id})

    async def search_users_by_name(self, name, limit=10):
        regex = re.compile(re.escape(name), re.IGNORECASE)
        cursor = self.users.find({'first_name': regex}).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_groups_page(self, page, per_page=10):
        skip = (page - 1) * per_page
        cursor = self.groups.find({}).sort('_id', 1).skip(skip).limit(per_page)
        groups = await cursor.to_list(length=per_page)
        total = await self.groups.count_documents({})
        return groups, total

    async def find_group(self, chat_id):
        return await self.groups.find_one({'_id': chat_id})

    async def remove_group(self, chat_id):
        await self.groups.delete_one({'_id': chat_id})

    async def search_groups_by_name(self, name, limit=10):
        regex = re.compile(re.escape(name), re.IGNORECASE)
        cursor = self.groups.find({'title': regex}).limit(limit)
        return await cursor.to_list(length=limit)

    async def increment_blocked_attempt(self, user_id):
        await self.users.update_one({'_id': user_id}, {'$inc': {'blocked_attempts': 1}}, upsert=True)

    async def remove_search_credits(self, user_id, amount):
        user = await self.users.find_one({'_id': user_id}) or {}
        new_val = max(user.get('search_credits', 0) - amount, 0)
        await self.users.update_one({'_id': user_id}, {'$set': {'search_credits': new_val}}, upsert=True)
        return new_val

    async def revoke_unlimited(self, user_id):
        await self.users.update_one({'_id': user_id}, {'$set': {'unlimited_until': 0}}, upsert=True)

    async def log_user_search(self, user_id, query):
        if self.user_search_log is None: return
        await self.user_search_log.insert_one({'user_id': user_id, 'query': query, 'ts': time.time()})

    async def get_user_search_history(self, user_id, limit=15):
        if self.user_search_log is None: return []
        cursor = self.user_search_log.find({'user_id': user_id}).sort('ts', -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def save_support_thread(self, admin_chat_id, message_id, user_id):
        await self.support_threads.update_one(
            {'_id': f"{admin_chat_id}:{message_id}"}, {'$set': {'user_id': user_id, 'ts': time.time()}}, upsert=True
        )

    async def get_support_thread(self, admin_chat_id, message_id):
        doc = await self.support_threads.find_one({'_id': f"{admin_chat_id}:{message_id}"})
        return doc['user_id'] if doc else None

    async def save_continue_marker(self, user_id, message_id):
        await self.support_threads.update_one(
            {'_id': f"cont:{user_id}:{message_id}"}, {'$set': {'active': True, 'ts': time.time()}}, upsert=True
        )

    async def is_continue_marker(self, user_id, message_id):
        doc = await self.support_threads.find_one({'_id': f"cont:{user_id}:{message_id}"})
        return doc is not None

    async def add_sub_admin(self, user_id, permissions, expire_at=None, is_permanent=False):
        await self.sub_admins.update_one(
            {'_id': user_id},
            {'$set': {'permissions': permissions, 'expire_at': expire_at, 'is_permanent': is_permanent}},
            upsert=True
        )

    async def remove_sub_admin(self, user_id):
        await self.sub_admins.delete_one({'_id': user_id})

    async def get_sub_admin(self, user_id):
        if self.sub_admins is None: return None
        doc = await self.sub_admins.find_one({'_id': user_id})
        if not doc:
            return None
        if not doc.get('is_permanent') and doc.get('expire_at') and doc['expire_at'] < time.time():
            await self.sub_admins.delete_one({'_id': user_id})
            return None
        return doc

    async def get_all_sub_admins(self):
        if self.sub_admins is None: return []
        return await self.sub_admins.find({}).to_list(length=1000)

db = Database()
