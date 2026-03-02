"""
Database mixin for Content Management System (CMS), including Channels and Guides.
"""
import logging
from .base_repository import BaseRepository
from typing import Optional, Dict, List, Any
from utils.logger import log_exception
logger = logging.getLogger('database.cms_mixin')

class CMSRepository(BaseRepository):
    """
    Mixin containing channel and guide management database operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    async def get_required_channels(self) -> List[Dict]:
        """دریافت کانال‌های اجباری فعال (بر اساس priority)"""
        try:
            query = '\n                SELECT channel_id, title, url, priority\n                FROM required_channels\n                WHERE is_active = TRUE\n                ORDER BY priority ASC, channel_id ASC\n            '
            results = await self.execute_query(query, fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, 'get_required_channels')
            return []

    async def add_required_channel(self, channel_id: str, title: str, url: str) -> bool:
        """اضافه کردن کانال اجباری"""
        try:
            query = '\n                INSERT INTO required_channels (channel_id, title, url)\n                VALUES (%s, %s, %s)\n                ON CONFLICT (channel_id) DO UPDATE SET\n                    title = EXCLUDED.title,\n                    url = EXCLUDED.url,\n                    is_active = TRUE\n            '
            await self.execute_query(query, (channel_id, title, url))
            logger.info(f'✅ Required channel added: {channel_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'add_required_channel({channel_id})')
            return False

    async def remove_required_channel(self, channel_id: str) -> bool:
        """حذف کانال اجباری (soft delete)"""
        try:
            query = '\n                UPDATE required_channels \n                SET is_active = FALSE \n                WHERE channel_id = %s\n            '
            await self.execute_query(query, (channel_id,))
            logger.info(f'✅ Required channel removed: {channel_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'remove_required_channel({channel_id})')
            return False

    async def update_required_channel(self, channel_id: str, new_title: str=None, new_url: str=None) -> bool:
        """ویرایش کانال اجباری"""
        try:
            updates = []
            params = []
            if new_title is not None:
                updates.append('title = %s')
                params.append(new_title)
            if new_url is not None:
                updates.append('url = %s')
                params.append(new_url)
            if not updates:
                return True
            params.append(channel_id)
            query = f"\n                UPDATE required_channels \n                SET {', '.join(updates)}\n                WHERE channel_id = %s\n            "
            await self.execute_query(query, tuple(params))
            logger.info(f'✅ Required channel updated: {channel_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'update_required_channel({channel_id})')
            return False

    async def get_channel_by_id(self, channel_id: str) -> Optional[Dict]:
        """دریافت اطلاعات یک کانال (حتی اگر غیرفعال باشد)"""
        try:
            query = '\n                SELECT channel_id, title, url, priority, is_active\n                FROM required_channels\n                WHERE channel_id = %s\n            '
            return await self.execute_query(query, (channel_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f'get_channel_by_id({channel_id})')
            return None

    async def toggle_channel_status(self, channel_id: str) -> bool:
        """تغییر وضعیت فعال/غیرفعال بودن کانال"""
        try:
            query = '\n                UPDATE required_channels\n                SET is_active = NOT is_active\n                WHERE channel_id = %s\n            '
            await self.execute_query(query, (channel_id,))
            logger.info(f'✅ Channel status toggled: {channel_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'toggle_channel_status({channel_id})')
            return False

    async def clear_required_channels(self) -> bool:
        """غیرفعال کردن تمام کانال‌های اجباری"""
        try:
            query = 'UPDATE required_channels SET is_active = FALSE'
            await self.execute_query(query)
            logger.info('✅ All required channels cleared (set inactive)')
            return True
        except Exception as e:
            log_exception(logger, e, 'clear_required_channels')
            return False

    async def update_channel_priority(self, channel_id: str, new_priority: int) -> bool:
        """تغییر اولویت کانال"""
        try:
            query = '\n                UPDATE required_channels \n                SET priority = %s\n                WHERE channel_id = %s\n            '
            await self.execute_query(query, (new_priority, channel_id))
            logger.info(f'✅ Channel priority updated: {channel_id} -> {new_priority}')
            return True
        except Exception as e:
            log_exception(logger, e, f'update_channel_priority({channel_id})')
            return False

    async def move_channel_up(self, channel_id: str) -> bool:
        """جابجایی کانال به بالا (کاهش priority)"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT priority FROM required_channels WHERE channel_id = %s
                    """, (channel_id,))
                    current = await cursor.fetchone()
                    if not current:
                        return False
                    current_priority = current['priority']
                    await cursor.execute("""
                        SELECT channel_id, priority 
                        FROM required_channels 
                        WHERE priority < %s AND is_active = TRUE
                        ORDER BY priority DESC 
                        LIMIT 1
                    """, (current_priority,))
                    previous = await cursor.fetchone()
                    if not previous:
                        return False
                    prev_channel_id = previous['channel_id']
                    prev_priority = previous['priority']
                    await cursor.execute("""
                        UPDATE required_channels SET priority = %s WHERE channel_id = %s
                    """, (prev_priority, channel_id))
                    await cursor.execute("""
                        UPDATE required_channels SET priority = %s WHERE channel_id = %s
                    """, (current_priority, prev_channel_id))
                logger.info(f'✅ Channel moved up: {channel_id}')
                return True
        except Exception as e:
            log_exception(logger, e, f'move_channel_up({channel_id})')
            return False

    async def move_channel_down(self, channel_id: str) -> bool:
        """جابجایی کانال به پایین (افزایش priority)"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT priority FROM required_channels WHERE channel_id = %s
                    """, (channel_id,))
                    current = await cursor.fetchone()
                    if not current:
                        return False
                    current_priority = current['priority']
                    await cursor.execute("""
                        SELECT channel_id, priority 
                        FROM required_channels 
                        WHERE priority > %s AND is_active = TRUE
                        ORDER BY priority ASC 
                        LIMIT 1
                    """, (current_priority,))
                    next_ch = await cursor.fetchone()
                    if not next_ch:
                        return False
                    next_channel_id = next_ch['channel_id']
                    next_priority = next_ch['priority']
                    await cursor.execute("""
                        UPDATE required_channels SET priority = %s WHERE channel_id = %s
                    """, (next_priority, channel_id))
                    await cursor.execute("""
                        UPDATE required_channels SET priority = %s WHERE channel_id = %s
                    """, (current_priority, next_channel_id))
                logger.info(f'✅ Channel moved down: {channel_id}')
                return True
        except Exception as e:
            log_exception(logger, e, f'move_channel_down({channel_id})')
            return False

    async def get_guides(self, mode: str='br') -> Dict[str, Dict]:
        """دریافت راهنماها"""
        try:
            guides = {}
            query_guides = """
                SELECT id, key, name, code
                FROM guides
                WHERE mode = %s
            """
            result = await self.execute_query(query_guides, (mode,), fetch_all=True)
            for guide in result:
                guide_id = guide['id']
                guide_dict = {
                    'name': guide['name'],
                    'code': guide['code'] or '',
                    'photos': [],
                    'videos': []
                }
                
                # Fetch photos
                query_photos = "SELECT file_id FROM guide_photos WHERE guide_id = %s ORDER BY sort_order ASC"
                photos = await self.execute_query(query_photos, (guide_id,), fetch_all=True)
                guide_dict['photos'] = [p['file_id'] for p in photos]
                
                # Fetch videos
                query_videos = "SELECT file_id FROM guide_videos WHERE guide_id = %s ORDER BY sort_order ASC"
                videos = await self.execute_query(query_videos, (guide_id,), fetch_all=True)
                guide_dict['videos'] = [v['file_id'] for v in videos]
                
                guides[guide['key']] = guide_dict
            default_guides = ['basic', 'sens', 'hud']
            for key in default_guides:
                if key not in guides:
                    guides[key] = {'name': key.title(), 'code': '', 'photos': [], 'videos': []}
            return guides
        except Exception as e:
            log_exception(logger, e, f'get_guides({mode})')
            return {}

    async def get_guide(self, key: str, mode: str='br') -> Dict:
        """دریافت یک راهنمای خاص"""
        try:
            query_guide = """
                SELECT id, key, name, code
                FROM guides
                WHERE key = %s AND mode = %s
            """
            guide = await self.execute_query(query_guide, (key, mode), fetch_one=True)
            guide_dict = {'name': key, 'code': '', 'photos': [], 'videos': []}
            if guide:
                guide_id = guide['id']
                guide_dict['name'] = guide['name']
                guide_dict['code'] = guide['code'] or ''
                
                # Fetch photos
                query_photos = "SELECT file_id FROM guide_photos WHERE guide_id = %s ORDER BY sort_order ASC"
                photos = await self.execute_query(query_photos, (guide_id,), fetch_all=True)
                guide_dict['photos'] = [p['file_id'] for p in photos]
                
                # Fetch videos
                query_videos = "SELECT file_id FROM guide_videos WHERE guide_id = %s ORDER BY sort_order ASC"
                videos = await self.execute_query(query_videos, (guide_id,), fetch_all=True)
                guide_dict['videos'] = [v['file_id'] for v in videos]
            return guide_dict
        except Exception as e:
            log_exception(logger, e, f'get_guide({key}, {mode})')
            return {'name': key, 'code': '', 'photos': [], 'videos': []}

    async def set_guide_name(self, key: str, name: str, mode: str='br') -> bool:
        """تنظیم نام راهنما"""
        try:
            query = '\n                INSERT INTO guides (key, mode, name)\n                VALUES (%s, %s, %s)\n                ON CONFLICT (key, mode) DO UPDATE SET\n                    name = EXCLUDED.name\n            '
            await self.execute_query(query, (key, mode, name))
            logger.info(f'✅ Guide name set: {key} -> {name}')
            return True
        except Exception as e:
            log_exception(logger, e, f'set_guide_name({key})')
            return False

    async def set_guide_code(self, key: str, code: str, mode: str='br') -> bool:
        """تنظیم کد راهنما (Sens/HUD)"""
        try:
            query = '\n                INSERT INTO guides (key, mode, name, code)\n                VALUES (%s, %s, %s, %s)\n                ON CONFLICT (key, mode) DO UPDATE SET\n                    code = EXCLUDED.code\n            '
            await self.execute_query(query, (key, mode, key.title(), code))
            logger.info(f'✅ Guide code set: {key} ({mode})')
            return True
        except Exception as e:
            log_exception(logger, e, f'set_guide_code({key})')
            return False

    async def get_guide_code(self, key: str, mode: str='br') -> str:
        """دریافت کد راهنما"""
        try:
            query = 'SELECT code FROM guides WHERE key = %s AND mode = %s'
            result = await self.execute_query(query, (key, mode), fetch_one=True)
            return (result.get('code') if result else '') or ''
        except Exception as e:
            log_exception(logger, e, f'get_guide_code({key})')
            return ''

    async def clear_guide_code(self, key: str, mode: str='br') -> bool:
        """حذف کد راهنما (تنظیم به NULL)"""
        try:
            query = 'UPDATE guides SET code = NULL WHERE key = %s AND mode = %s'
            await self.execute_query(query, (key, mode))
            logger.info(f'✅ Guide code cleared: {key} ({mode})')
            return True
        except Exception as e:
            log_exception(logger, e, f'clear_guide_code({key})')
            return False

    async def clear_guide_media(self, key: str, mode: str='br') -> bool:
        """پاک‌سازی تمام رسانه‌های یک راهنما"""
        try:
            query_guide = 'SELECT id FROM guides WHERE key = %s AND mode = %s'
            guide = await self.execute_query(query_guide, (key, mode), fetch_one=True)
            if not guide:
                return True
            guide_id = guide['id']
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('DELETE FROM guide_photos WHERE guide_id = %s', (guide_id,))
                    await cursor.execute('DELETE FROM guide_videos WHERE guide_id = %s', (guide_id,))
            logger.info(f'✅ Guide media (photos & videos) cleared: {key} ({mode})')
            return True
        except Exception as e:
            log_exception(logger, e, f'clear_guide_media({key}, {mode})')
            return False

    async def add_guide_photo(self, key: str, file_id: str, mode: str='br') -> bool:
        """افزودن عکس به راهنما"""
        return await self._add_guide_media(key, file_id, 'photo', mode)

    async def add_guide_video(self, key: str, file_id: str, mode: str='br') -> bool:
        """افزودن ویدیو به راهنما"""
        return await self._add_guide_media(key, file_id, 'video', mode)

    async def _add_guide_media(self, key: str, file_id: str, media_type: str, mode: str) -> bool:
        """افزودن رسانه به راهنما"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id FROM guides WHERE key = %s AND mode = %s
                    """, (key, mode))
                    result = await cursor.fetchone()
                    if result:
                        guide_id = result['id']
                    else:
                        # Fallback for set_guide methods being global
                        await cursor.execute("""
                            INSERT INTO guides (key, mode, name)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (key) DO UPDATE SET
                                mode = EXCLUDED.mode
                            RETURNING id
                        """, (key, mode, key.title()))
                        result = await cursor.fetchone()
                        guide_id = result['id']
                    
                    table_name = "guide_photos" if media_type == "photo" else "guide_videos"
                    
                    await cursor.execute(f"""
                        SELECT COALESCE(MAX(sort_order), -1) as max_order
                        FROM {table_name}
                        WHERE guide_id = %s
                    """, (guide_id,))
                    result = await cursor.fetchone()
                    max_order = result['max_order']
                    
                    await cursor.execute(f"""
                        INSERT INTO {table_name} (guide_id, file_id, sort_order)
                        VALUES (%s, %s, %s)
                    """, (guide_id, file_id, max_order + 1))
                    
                logger.info(f'✅ Guide media added to {table_name}: {key}')
                return True
        except Exception as e:
            log_exception(logger, e, f'_add_guide_media({key}, {media_type})')
            return False

    # ==========================================================================
    # Scheduled Notifications Methods
    # ==========================================================================
    async def create_scheduled_notification(
        self,
        message_type: str,
        message_text: str = None,
        photo_file_id: str = None,
        parse_mode: str = 'Markdown',
        interval_hours: int = 24,
        next_run_at = None,
        enabled: bool = True,
        created_by: int = None,
    ) -> Optional[int]:
        """ایجاد یک اعلان زمان‌بندی شده جدید و برگرداندن id"""
        try:
            query = (
                """
                INSERT INTO scheduled_notifications (
                  message_type, message_text, photo_file_id, parse_mode,
                  interval_hours, enabled, last_sent_at, next_run_at,
                  created_by, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW(), NOW())
                RETURNING id
                """
            )
            row = await self.execute_query(
                query,
                (
                    message_type, message_text, photo_file_id, parse_mode,
                    interval_hours, enabled, None, next_run_at,
                    created_by,
                ),
                fetch_one=True,
            )
            return row['id'] if row else None
        except Exception as e:
            log_exception(logger, e, "create_scheduled_notification")
            return None

    async def update_scheduled_notification(
        self,
        schedule_id: int,
        message_type: Optional[str] = None,
        message_text: Optional[str] = None,
        photo_file_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        interval_hours: Optional[int] = None,
        next_run_at: Optional[Any] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        """به‌روزرسانی فیلدهای زمان‌بندی اعلان."""
        try:
            sets = []
            params: list[Any] = []

            if message_type is not None:
                sets.append("message_type = %s")
                params.append(message_type)
            if message_text is not None:
                sets.append("message_text = %s")
                params.append(message_text)
            if photo_file_id is not None:
                sets.append("photo_file_id = %s")
                params.append(photo_file_id)
            if parse_mode is not None:
                sets.append("parse_mode = %s")
                params.append(parse_mode)
            if interval_hours is not None:
                sets.append("interval_hours = %s")
                params.append(interval_hours)
            if next_run_at is not None:
                sets.append("next_run_at = %s")
                params.append(next_run_at)
            if enabled is not None:
                sets.append("enabled = %s")
                params.append(enabled)

            if not sets:
                logger.warning("update_scheduled_notification called with no fields to update")
                return False

            sets.append("updated_at = NOW()")
            query = f"""
                UPDATE scheduled_notifications
                SET {', '.join(sets)}
                WHERE id = %s
            """
            params.append(schedule_id)

            await self.execute_query(query, tuple(params))
            logger.info(f"✅ Scheduled notification updated: id={schedule_id}")
            return True
        except Exception as e:
            log_exception(logger, e, "update_scheduled_notification")
            return False

    async def list_scheduled_notifications(self) -> List[Dict]:
        """دریافت لیست اعلان‌های زمان‌بندی شده"""
        try:
            query = (
                """
                SELECT id, message_type, message_text, photo_file_id, parse_mode,
                       interval_hours, enabled, last_sent_at, next_run_at,
                       created_by, created_at, updated_at
                FROM scheduled_notifications
                ORDER BY enabled DESC, next_run_at NULLS LAST, id DESC
                """
            )
            return await self.execute_query(query, fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "list_scheduled_notifications")
            return []

    async def delete_scheduled_notification(self, schedule_id: int) -> bool:
        """حذف یک اعلان زمان‌بندی شده"""
        try:
            await self.execute_query("DELETE FROM scheduled_notifications WHERE id = %s", (schedule_id,))
            return True
        except Exception as e:
            log_exception(logger, e, "delete_scheduled_notification")
            return False

    async def get_due_scheduled_notifications(self, now_ts) -> List[Dict]:
        """
        دریافت اعلان‌های سررسید شده (enabled و next_run_at <= now)
        Args:
            now_ts: datetime with tzinfo (UTC)
        """
        try:
            query = (
                """
                SELECT id, message_type, message_text, photo_file_id, parse_mode,
                       interval_hours, enabled, last_sent_at, next_run_at
                FROM scheduled_notifications
                WHERE enabled = TRUE AND next_run_at IS NOT NULL AND next_run_at <= %s
                ORDER BY next_run_at ASC
                LIMIT 50
                """
            )
            return await self.execute_query(query, (now_ts,), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_due_scheduled_notifications")
            return []

    async def mark_schedule_sent(self, schedule_id: int, last_sent_at, next_run_at) -> bool:
        """به‌روزرسانی زمان‌های ارسال برای یک اعلان زمان‌بندی شده"""
        try:
            query = (
                """
                UPDATE scheduled_notifications
                SET last_sent_at = %s,
                    next_run_at = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            )
            await self.execute_query(query, (last_sent_at, next_run_at, schedule_id))
            return True
        except Exception as e:
            log_exception(logger, e, "mark_schedule_sent")
            return False

    async def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> bool:
        """فعال/غیرفعال کردن یک زمان‌بندی"""
        try:
            query = (
                """
                UPDATE scheduled_notifications
                SET enabled = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
            )
            await self.execute_query(query, (enabled, schedule_id))
            return True
        except Exception as e:
            log_exception(logger, e, "set_schedule_enabled")
            return False

    async def get_scheduled_notification_by_id(self, schedule_id: int) -> Optional[Dict]:
        """دریافت یک زمان‌بندی بر اساس id"""
        try:
            query = (
                """
                SELECT id, message_type, message_text, photo_file_id, parse_mode,
                       interval_hours, enabled, last_sent_at, next_run_at,
                       created_by, created_at, updated_at
                FROM scheduled_notifications
                WHERE id = %s
            """
            )
            return await self.execute_query(query, (schedule_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, "get_scheduled_notification_by_id")
            return None