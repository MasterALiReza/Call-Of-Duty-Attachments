"""
User Attachments Cache Manager
مدیریت Cache برای بهبود Performance سیستم اتچمنت کاربران
"""
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
from utils.logger import get_logger
logger = get_logger('ua_cache', 'cache.log')

class UACache:
    """مدیریت Cache برای User Attachments"""

    def __init__(self, db_adapter, ttl_seconds: int=300):
        """
        Args:
            db_adapter: Database adapter instance
            ttl_seconds: Time to live for cache entries (default: 5 minutes)
        """
        self.db = db_adapter
        self.ttl = ttl_seconds
        self.memory_cache = {}
        self.lock = Lock()

    def _is_cache_valid(self, updated_at: str) -> bool:
        """بررسی اعتبار cache بر اساس زمان"""
        if not updated_at:
            return False
        try:
            cache_time = datetime.fromisoformat(updated_at)
            expiry_time = datetime.now() - timedelta(seconds=self.ttl)
            return cache_time > expiry_time
        except Exception as e:
            logger.error(f'Error checking cache validity: {e}')
            return False

    async def get_stats(self, force_refresh: bool=False) -> Optional[Dict]:
        """دریافت آمار از cache یا محاسبه جدید"""
        if not force_refresh and 'stats' in self.memory_cache:
            cached = self.memory_cache['stats']
            if self._is_cache_valid(cached.get('timestamp')):
                logger.debug('Stats retrieved from memory cache')
                return cached['data']
        try:
            if not hasattr(self.db, 'get_connection'):
                return None
            cache_row = None
            if not force_refresh:
                try:
                    async with self.db.get_connection() as conn:
                        async with conn.cursor() as cursor:
                            try:
                                await cursor.execute("\n                                    SELECT * FROM ua_stats_cache \n                                    WHERE id = 1 \n                                      AND updated_at > (CURRENT_TIMESTAMP - INTERVAL '5 minutes')\n                                    ")
                            except Exception as e:
                                logger.debug(f'Cache table might not have updated_at column or table missing: {e}')
                                await cursor.execute('\n                                    SELECT * FROM ua_stats_cache \n                                    WHERE id = 1\n                                    ')
                            cache_row = await cursor.fetchone()
                except Exception as cache_err:
                    logger.debug(f'Skipping DB cache for stats (will compute fresh): {cache_err}')
                    cache_row = None
                if cache_row:
                    stats = dict(cache_row)
                    with self.lock:
                        self.memory_cache['stats'] = {'data': stats, 'timestamp': datetime.now().isoformat()}
                    logger.debug('Stats retrieved from database cache')
                    return stats
            logger.info('Calculating fresh stats with CTE')
            start_time = time.time()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("\n                        WITH stats AS (\n                            SELECT \n                                COUNT(*) as total_attachments,\n                                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,\n                                COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,\n                                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,\n                                COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted_count,\n                                COUNT(CASE WHEN mode = 'br' AND status = 'approved' THEN 1 END) as br_count,\n                                COUNT(CASE WHEN mode = 'mp' AND status = 'approved' THEN 1 END) as mp_count,\n                                COUNT(DISTINCT user_id) as total_users,\n                                COALESCE(SUM(like_count), 0) as total_likes,\n                                COALESCE(SUM(report_count), 0) as total_reports,\n                                COUNT(CASE WHEN submitted_at >= (CURRENT_TIMESTAMP - INTERVAL '7 days') THEN 1 END) as last_week_submissions,\n                                COUNT(CASE WHEN approved_at >= (CURRENT_TIMESTAMP - INTERVAL '7 days') AND status = 'approved' THEN 1 END) as last_week_approvals\n                            FROM user_attachments\n                        ),\n                        banned AS (\n                            SELECT COUNT(*) as banned_users\n                            FROM user_submission_stats \n                            WHERE is_banned = TRUE\n                        ),\n                        reports AS (\n                            SELECT COUNT(*) as pending_reports\n                            FROM user_attachment_reports\n                            WHERE status = 'pending'\n                        )\n                        SELECT \n                            s.*,\n                            b.banned_users,\n                            r.pending_reports,\n                            s.total_users - b.banned_users as active_users\n                        FROM stats s, banned b, reports r\n                        ")
                    row = await cursor.fetchone()
            elapsed = (time.time() - start_time) * 1000
            logger.info(f'Stats calculated in {elapsed:.2f}ms')
            if row:
                stats = dict(row)
                stats['updated_at'] = datetime.now().isoformat()
                try:
                    async with self.db.transaction() as tconn:
                        async with tconn.cursor() as tcur:
                            await tcur.execute('\n                                INSERT INTO ua_stats_cache (\n                                    id, total_attachments, pending_count, approved_count, rejected_count, deleted_count,\n                                    total_users, active_users, banned_users, br_count, mp_count,\n                                    total_likes, total_reports, pending_reports,\n                                    last_week_submissions, last_week_approvals,\n                                    updated_at\n                                ) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)\n                                ON CONFLICT (id) DO UPDATE SET\n                                    total_attachments = EXCLUDED.total_attachments,\n                                    pending_count = EXCLUDED.pending_count,\n                                    approved_count = EXCLUDED.approved_count,\n                                    rejected_count = EXCLUDED.rejected_count,\n                                    deleted_count = EXCLUDED.deleted_count,\n                                    total_users = EXCLUDED.total_users,\n                                    active_users = EXCLUDED.active_users,\n                                    banned_users = EXCLUDED.banned_users,\n                                    br_count = EXCLUDED.br_count,\n                                    mp_count = EXCLUDED.mp_count,\n                                    total_likes = EXCLUDED.total_likes,\n                                    total_reports = EXCLUDED.total_reports,\n                                    pending_reports = EXCLUDED.pending_reports,\n                                    last_week_submissions = EXCLUDED.last_week_submissions,\n                                    last_week_approvals = EXCLUDED.last_week_approvals,\n                                    updated_at = CURRENT_TIMESTAMP\n                                ', (stats['total_attachments'], stats['pending_count'], stats['approved_count'], stats['rejected_count'], stats.get('deleted_count', 0), stats['total_users'], stats['active_users'], stats['banned_users'], stats['br_count'], stats['mp_count'], stats['total_likes'], stats['total_reports'], stats['pending_reports'], stats['last_week_submissions'], stats['last_week_approvals']))
                except Exception as e:
                    logger.debug(f'Could not update cache table: {e}')
                with self.lock:
                    self.memory_cache['stats'] = {'data': stats, 'timestamp': datetime.now().isoformat()}
                return stats
        except Exception as e:
            logger.error(f'Error getting stats: {e}')
            return None

    async def get_top_weapons(self, limit: int=10, force_refresh: bool=False) -> List[Dict]:
        """دریافت محبوب\u200cترین سلاح\u200cها از cache"""
        try:
            limit = int(limit)
        except Exception:
            limit = 10
        limit = max(1, min(limit, 100))
        cache_key = f'top_weapons_{limit}'
        if not force_refresh and cache_key in self.memory_cache:
            cached = self.memory_cache[cache_key]
            if self._is_cache_valid(cached.get('timestamp')):
                logger.debug(f'Top weapons retrieved from memory cache')
                return cached['data']
        try:
            if not hasattr(self.db, 'get_connection'):
                return []
            if not force_refresh:
                try:
                    async with self.db.get_connection() as conn:
                        async with conn.cursor() as cursor:
                            try:
                                await cursor.execute("\n                                    SELECT weapon_name, attachment_count, mode\n                                    FROM ua_top_weapons_cache\n                                    WHERE updated_at > (CURRENT_TIMESTAMP - INTERVAL '5 minutes')\n                                    ORDER BY attachment_count DESC\n                                    LIMIT %s\n                                    ", (limit,))
                            except Exception:
                                await cursor.execute('\n                                    SELECT weapon_name, attachment_count, mode\n                                    FROM ua_top_weapons_cache\n                                    ORDER BY attachment_count DESC\n                                    LIMIT %s\n                                    ', (limit,))
                            cache_rows = await cursor.fetchall()
                    if cache_rows:
                        weapons = [dict(row) for row in cache_rows]
                        with self.lock:
                            self.memory_cache[cache_key] = {'data': weapons, 'timestamp': datetime.now().isoformat()}
                        logger.debug('Top weapons retrieved from database cache')
                        return weapons
                except Exception as cache_err:
                    logger.debug(f'Skipping DB cache for top weapons: {cache_err}')
            logger.info('Calculating fresh top weapons')
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("\n                        SELECT \n                            COALESCE(custom_weapon_name, 'Unknown') as weapon_name,\n                            COUNT(*) as attachment_count,\n                            mode\n                        FROM user_attachments\n                        WHERE status = 'approved' \n                          AND custom_weapon_name IS NOT NULL\n                        GROUP BY custom_weapon_name, mode\n                        ORDER BY attachment_count DESC\n                        LIMIT %s\n                        ", (limit,))
                    rows = await cursor.fetchall()
            weapons = [dict(row) for row in rows]
            try:
                async with self.db.transaction() as tconn:
                    async with tconn.cursor() as tcur:
                        await tcur.execute('DELETE FROM ua_top_weapons_cache')
                        for weapon in weapons:
                            await tcur.execute('\n                                INSERT INTO ua_top_weapons_cache (weapon_name, attachment_count, mode, updated_at)\n                                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)\n                                ', (weapon['weapon_name'], weapon['attachment_count'], weapon.get('mode', '')))
            except Exception as e:
                logger.debug(f'Could not refresh top weapons cache: {e}')
            with self.lock:
                self.memory_cache[cache_key] = {'data': weapons, 'timestamp': datetime.now().isoformat()}
            return weapons
        except Exception as e:
            logger.error(f'Error getting top weapons: {e}')
            return []

    async def get_top_users(self, limit: int=5, force_refresh: bool=False) -> List[Dict]:
        """دریافت فعال\u200cترین کاربران از cache"""
        try:
            limit = int(limit)
        except Exception:
            limit = 5
        limit = max(1, min(limit, 100))
        cache_key = f'top_users_{limit}'
        if not force_refresh and cache_key in self.memory_cache:
            cached = self.memory_cache[cache_key]
            if self._is_cache_valid(cached.get('timestamp')):
                logger.debug('Top users retrieved from memory cache')
                return cached['data']
        try:
            if not hasattr(self.db, 'get_connection'):
                return []
            if not force_refresh:
                try:
                    async with self.db.get_connection() as conn:
                        async with conn.cursor() as cursor:
                            try:
                                await cursor.execute("\n                                    SELECT user_id, username, approved_count, total_likes\n                                    FROM ua_top_users_cache\n                                    WHERE updated_at > (CURRENT_TIMESTAMP - INTERVAL '5 minutes')\n                                    ORDER BY approved_count DESC\n                                    LIMIT %s\n                                    ", (limit,))
                            except Exception:
                                await cursor.execute('\n                                    SELECT user_id, username, approved_count, total_likes\n                                    FROM ua_top_users_cache\n                                    ORDER BY approved_count DESC\n                                    LIMIT %s\n                                    ', (limit,))
                            cache_rows = await cursor.fetchall()
                    if cache_rows:
                        users = [dict(row) for row in cache_rows]
                        with self.lock:
                            self.memory_cache[cache_key] = {'data': users, 'timestamp': datetime.now().isoformat()}
                        logger.debug('Top users retrieved from database cache')
                        return users
                except Exception as cache_err:
                    logger.debug(f'Skipping DB cache for top users: {cache_err}')
            logger.info('Calculating fresh top users')
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("\n                        SELECT \n                            ua.user_id,\n                            u.username,\n                            COUNT(*) as approved_count,\n                            COALESCE(SUM(ua.like_count), 0) as total_likes\n                        FROM user_attachments ua\n                        LEFT JOIN users u ON ua.user_id = u.user_id\n                        WHERE ua.status = 'approved'\n                        GROUP BY ua.user_id, u.username\n                        ORDER BY approved_count DESC\n                        LIMIT %s\n                        ", (limit,))
                    rows = await cursor.fetchall()
            users = [dict(row) for row in rows]
            try:
                async with self.db.transaction() as tconn:
                    async with tconn.cursor() as tcur:
                        await tcur.execute('DELETE FROM ua_top_users_cache')
                        for user in users:
                            await tcur.execute('\n                                INSERT INTO ua_top_users_cache (user_id, username, approved_count, total_likes, updated_at)\n                                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)\n                                ', (user['user_id'], user.get('username'), user['approved_count'], user['total_likes']))
            except Exception as e:
                logger.debug(f'Could not refresh top users cache: {e}')
            with self.lock:
                self.memory_cache[cache_key] = {'data': users, 'timestamp': datetime.now().isoformat()}
            return users
        except Exception as e:
            logger.error(f'Error getting top users: {e}')
            return []

    async def get_paginated_count(self, status: str='pending') -> int:
        """دریافت تعداد برای pagination با cache"""
        cache_key = f'count_{status}'
        if cache_key in self.memory_cache:
            cached = self.memory_cache[cache_key]
            cache_time = cached.get('timestamp', 0)
            if time.time() - cache_time < 60:
                logger.debug(f'Count for {status} from memory cache')
                return cached['count']
        try:
            if not hasattr(self.db, 'get_connection'):
                return 0
            if status in ['pending', 'approved', 'rejected']:
                stats = await self.get_stats()
                if stats:
                    count = stats.get(f'{status}_count', 0)
                    with self.lock:
                        self.memory_cache[cache_key] = {'count': count, 'timestamp': time.time()}
                    return count
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('SELECT COUNT(*) AS cnt FROM user_attachments WHERE status = %s', (status,))
                    row = await cursor.fetchone()
                count = int((row or {}).get('cnt') or 0)
            with self.lock:
                self.memory_cache[cache_key] = {'count': count, 'timestamp': time.time()}
            return count
        except Exception as e:
            logger.error(f'Error getting count for {status}: {e}')
            return 0

    async def invalidate(self, cache_type: Optional[str]=None):
        """پاک کردن cache"""
        with self.lock:
            if cache_type:
                keys_to_delete = [k for k in self.memory_cache if k.startswith(cache_type)]
                for key in keys_to_delete:
                    del self.memory_cache[key]
                logger.info(f'Invalidated {len(keys_to_delete)} {cache_type} cache entries')
            else:
                self.memory_cache.clear()
                logger.info('All cache entries invalidated')
        try:
            if hasattr(self.db, 'transaction'):
                async with self.db.transaction() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("\n                            UPDATE ua_stats_cache \n                            SET updated_at = (CURRENT_TIMESTAMP - INTERVAL '1 hour')\n                            WHERE id = 1\n                            ")
        except Exception as e:
            logger.error(f'Error invalidating database cache: {e}')

    async def batch_get_users(self, user_ids: List[int]) -> Dict[int, Dict]:
        """دریافت batch اطلاعات کاربران برای جلوگیری از N+1 queries"""
        if not user_ids:
            return {}
        cache_key = f'users_{hash(tuple(sorted(user_ids)))}'
        if cache_key in self.memory_cache:
            cached = self.memory_cache[cache_key]
            if self._is_cache_valid(cached.get('timestamp')):
                logger.debug(f'Batch users retrieved from cache')
                return cached['data']
        try:
            if not hasattr(self.db, 'get_connection'):
                return {}
            placeholders = ','.join(['%s'] * len(user_ids))
            query = f'\n                SELECT user_id, username, first_name\n                FROM users\n                WHERE user_id IN ({placeholders})\n            '
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, tuple(user_ids))
                    rows = await cursor.fetchall()
            users = {row['user_id']: dict(row) for row in rows}
            with self.lock:
                self.memory_cache[cache_key] = {'data': users, 'timestamp': datetime.now().isoformat()}
            return users
        except Exception as e:
            logger.error(f'Error batch getting users: {e}')
            return {}

def cache_result(ttl_seconds: int=300):
    """Decorator برای cache کردن نتایج توابع"""

    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f'{func.__name__}_{str(args)}_{str(kwargs)}'
            if cache_key in cache:
                cached_data, cached_time = cache[cache_key]
                if time.time() - cached_time < ttl_seconds:
                    logger.debug(f'Cache hit for {func.__name__}')
                    return cached_data
            result = func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            logger.debug(f'Cache miss for {func.__name__}, result cached')
            return result

        def clear_cache():
            cache.clear()
            logger.debug(f'Cache cleared for {func.__name__}')
        wrapper.clear_cache = clear_cache
        return wrapper
    return decorator
_cache_instance = None

def get_ua_cache(db_adapter, ttl_seconds: int=300) -> UACache:
    """دریافت singleton instance از cache manager"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = UACache(db_adapter, ttl_seconds)
    return _cache_instance