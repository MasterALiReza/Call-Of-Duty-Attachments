"""
Database mixin for Content Management System (CMS), including Channels and Guides.
"""

import logging
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.cms_mixin')


class CMSDatabaseMixin:
    """
    Mixin containing channel and guide management database operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    # ==========================================================================
    # Channel Management
    # ==========================================================================
    
    def get_required_channels(self) -> List[Dict]:
        """دریافت کانال‌های اجباری فعال (بر اساس priority)"""
        try:
            query = """
                SELECT channel_id, title, url, priority
                FROM required_channels
                WHERE is_active = TRUE
                ORDER BY priority ASC, channel_id ASC
            """
            results = self.execute_query(query, fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, "get_required_channels")
            return []
    
    def add_required_channel(self, channel_id: str, title: str, url: str) -> bool:
        """اضافه کردن کانال اجباری"""
        try:
            query = """
                INSERT INTO required_channels (channel_id, title, url)
                VALUES (%s, %s, %s)
                ON CONFLICT (channel_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    url = EXCLUDED.url,
                    is_active = TRUE
            """
            self.execute_query(query, (channel_id, title, url))
            logger.info(f"✅ Required channel added: {channel_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_required_channel({channel_id})")
            return False
    
    def remove_required_channel(self, channel_id: str) -> bool:
        """حذف کانال اجباری (soft delete)"""
        try:
            query = """
                UPDATE required_channels 
                SET is_active = FALSE 
                WHERE channel_id = %s
            """
            self.execute_query(query, (channel_id,))
            logger.info(f"✅ Required channel removed: {channel_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"remove_required_channel({channel_id})")
            return False
    
    def update_required_channel(self, channel_id: str, new_title: str = None,
                               new_url: str = None) -> bool:
        """ویرایش کانال اجباری"""
        try:
            updates = []
            params = []
            
            if new_title is not None:
                updates.append("title = %s")
                params.append(new_title)
            
            if new_url is not None:
                updates.append("url = %s")
                params.append(new_url)
            
            if not updates:
                return True
            
            params.append(channel_id)
            query = f"""
                UPDATE required_channels 
                SET {', '.join(updates)}
                WHERE channel_id = %s
            """
            
            self.execute_query(query, tuple(params))
            logger.info(f"✅ Required channel updated: {channel_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_required_channel({channel_id})")
            return False
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Dict]:
        """دریافت اطلاعات یک کانال (حتی اگر غیرفعال باشد)"""
        try:
            query = """
                SELECT channel_id, title, url, priority, is_active
                FROM required_channels
                WHERE channel_id = %s
            """
            return self.execute_query(query, (channel_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f"get_channel_by_id({channel_id})")
            return None

    def toggle_channel_status(self, channel_id: str) -> bool:
        """تغییر وضعیت فعال/غیرفعال بودن کانال"""
        try:
            query = """
                UPDATE required_channels
                SET is_active = NOT is_active
                WHERE channel_id = %s
            """
            self.execute_query(query, (channel_id,))
            logger.info(f"✅ Channel status toggled: {channel_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"toggle_channel_status({channel_id})")
            return False

    def clear_required_channels(self) -> bool:
        """غیرفعال کردن تمام کانال‌های اجباری"""
        try:
            query = "UPDATE required_channels SET is_active = FALSE"
            self.execute_query(query)
            logger.info("✅ All required channels cleared (set inactive)")
            return True
        except Exception as e:
            log_exception(logger, e, "clear_required_channels")
            return False
    
    # ==========================================================================
    # Channel Priority
    # ==========================================================================
    
    def update_channel_priority(self, channel_id: str, new_priority: int) -> bool:
        """تغییر اولویت کانال"""
        try:
            query = """
                UPDATE required_channels 
                SET priority = %s
                WHERE channel_id = %s
            """
            self.execute_query(query, (new_priority, channel_id))
            logger.info(f"✅ Channel priority updated: {channel_id} -> {new_priority}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_channel_priority({channel_id})")
            return False
    
    def move_channel_up(self, channel_id: str) -> bool:
        """جابجایی کانال به بالا (کاهش priority)"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT priority FROM required_channels WHERE channel_id = %s
                """, (channel_id,))
                current = cursor.fetchone()
                
                if not current:
                    cursor.close()
                    return False
                
                current_priority = current['priority']
                
                cursor.execute("""
                    SELECT channel_id, priority 
                    FROM required_channels 
                    WHERE priority < %s AND is_active = TRUE
                    ORDER BY priority DESC 
                    LIMIT 1
                """, (current_priority,))
                previous = cursor.fetchone()
                
                if not previous:
                    cursor.close()
                    return False
                
                prev_channel_id = previous['channel_id']
                prev_priority = previous['priority']
                
                cursor.execute("""
                    UPDATE required_channels SET priority = %s WHERE channel_id = %s
                """, (prev_priority, channel_id))
                
                cursor.execute("""
                    UPDATE required_channels SET priority = %s WHERE channel_id = %s
                """, (current_priority, prev_channel_id))
                
                cursor.close()
                logger.info(f"✅ Channel moved up: {channel_id}")
                return True
        except Exception as e:
            log_exception(logger, e, f"move_channel_up({channel_id})")
            return False
    
    def move_channel_down(self, channel_id: str) -> bool:
        """جابجایی کانال به پایین (افزایش priority)"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT priority FROM required_channels WHERE channel_id = %s
                """, (channel_id,))
                current = cursor.fetchone()
                
                if not current:
                    cursor.close()
                    return False
                
                current_priority = current['priority']
                
                cursor.execute("""
                    SELECT channel_id, priority 
                    FROM required_channels 
                    WHERE priority > %s AND is_active = TRUE
                    ORDER BY priority ASC 
                    LIMIT 1
                """, (current_priority,))
                next_ch = cursor.fetchone()
                
                if not next_ch:
                    cursor.close()
                    return False
                
                next_channel_id = next_ch['channel_id']
                next_priority = next_ch['priority']
                
                cursor.execute("""
                    UPDATE required_channels SET priority = %s WHERE channel_id = %s
                """, (next_priority, channel_id))
                
                cursor.execute("""
                    UPDATE required_channels SET priority = %s WHERE channel_id = %s
                """, (current_priority, next_channel_id))
                
                cursor.close()
                logger.info(f"✅ Channel moved down: {channel_id}")
                return True
        except Exception as e:
            log_exception(logger, e, f"move_channel_down({channel_id})")
            return False

    # ==========================================================================
    # Guide Management
    # ==========================================================================
    
    def get_guides(self, mode: str = "br") -> Dict[str, Dict]:
        """دریافت راهنماها"""
        try:
            guides = {}
            query_guides = """
                SELECT id, key, name, code
                FROM guides
                WHERE mode = %s
            """
            result = self.execute_query(query_guides, (mode,), fetch_all=True)
            
            for guide in result:
                guide_dict = {
                    'name': guide['name'],
                    'code': guide['code'] or '',
                    'photos': [],
                    'videos': []
                }
                
                query_media = """
                    SELECT media_type, file_id
                    FROM guide_media
                    WHERE guide_id = %s
                    ORDER BY order_index, id
                """
                media = self.execute_query(query_media, (guide['id'],), fetch_all=True)
                
                for m in media:
                    if m['media_type'] == 'photo':
                        guide_dict['photos'].append(m['file_id'])
                    else:
                        guide_dict['videos'].append(m['file_id'])
                
                guides[guide['key']] = guide_dict
            
            # Default guides
            default_guides = ['basic', 'sens', 'hud']
            for key in default_guides:
                if key not in guides:
                    guides[key] = {
                        'name': key.title(),
                        'code': '',
                        'photos': [],
                        'videos': []
                    }
            
            return guides
        except Exception as e:
            log_exception(logger, e, f"get_guides({mode})")
            return {}
    
    def get_guide(self, key: str, mode: str = "br") -> Dict:
        """دریافت یک راهنمای خاص"""
        try:
            query_guide = """
                SELECT id, key, name, code
                FROM guides
                WHERE key = %s AND mode = %s
            """
            guide = self.execute_query(query_guide, (key, mode), fetch_one=True)
            
            guide_dict = {
                'name': key,
                'code': '',
                'photos': [],
                'videos': []
            }
            
            if guide:
                guide_dict['name'] = guide['name']
                guide_dict['code'] = guide['code'] or ''
                
                query_media = """
                    SELECT media_type, file_id
                    FROM guide_media
                    WHERE guide_id = %s
                    ORDER BY order_index, id
                """
                media = self.execute_query(query_media, (guide['id'],), fetch_all=True)
                
                for m in media:
                    if m['media_type'] == 'photo':
                        guide_dict['photos'].append(m['file_id'])
                    else:
                        guide_dict['videos'].append(m['file_id'])
            
            return guide_dict
        except Exception as e:
            log_exception(logger, e, f"get_guide({key}, {mode})")
            return {'name': key, 'code': '', 'photos': [], 'videos': []}
    
    def set_guide_name(self, key: str, name: str, mode: str = "br") -> bool:
        """تنظیم نام راهنما"""
        try:
            query = """
                INSERT INTO guides (key, mode, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (key, mode) DO UPDATE SET
                    name = EXCLUDED.name
            """
            self.execute_query(query, (key, mode, name))
            logger.info(f"✅ Guide name set: {key} -> {name}")
            return True
        except Exception as e:
            log_exception(logger, e, f"set_guide_name({key})")
            return False

    def set_guide_code(self, key: str, code: str, mode: str = "br") -> bool:
        """تنظیم کد راهنما (Sens/HUD)"""
        try:
            query = """
                INSERT INTO guides (key, mode, name, code)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key, mode) DO UPDATE SET
                    code = EXCLUDED.code
            """
            self.execute_query(query, (key, mode, key.title(), code))
            logger.info(f"✅ Guide code set: {key} ({mode})")
            return True
        except Exception as e:
            log_exception(logger, e, f"set_guide_code({key})")
            return False

    def get_guide_code(self, key: str, mode: str = "br") -> str:
        """دریافت کد راهنما"""
        try:
            query = "SELECT code FROM guides WHERE key = %s AND mode = %s"
            result = self.execute_query(query, (key, mode), fetch_one=True)
            return (result.get('code') if result else '') or ''
        except Exception as e:
            log_exception(logger, e, f"get_guide_code({key})")
            return ''

    def clear_guide_code(self, key: str, mode: str = "br") -> bool:
        """حذف کد راهنما (تنظیم به NULL)"""
        try:
            query = "UPDATE guides SET code = NULL WHERE key = %s AND mode = %s"
            self.execute_query(query, (key, mode))
            logger.info(f"✅ Guide code cleared: {key} ({mode})")
            return True
        except Exception as e:
            log_exception(logger, e, f"clear_guide_code({key})")
            return False
    
    def clear_guide_media(self, key: str, mode: str = "br") -> bool:
        """پاک‌سازی تمام رسانه‌های یک راهنما"""
        try:
            query_guide = "SELECT id FROM guides WHERE key = %s AND mode = %s"
            guide = self.execute_query(query_guide, (key, mode), fetch_one=True)
            
            if not guide:
                return True
            
            guide_id = guide['id']
            query_delete = "DELETE FROM guide_media WHERE guide_id = %s"
            self.execute_query(query_delete, (guide_id,))
            
            logger.info(f"✅ Guide media cleared: {key} ({mode})")
            return True
        except Exception as e:
            log_exception(logger, e, f"clear_guide_media({key}, {mode})")
            return False
    
    def add_guide_photo(self, key: str, file_id: str, mode: str = "br") -> bool:
        """افزودن عکس به راهنما"""
        return self._add_guide_media(key, file_id, 'photo', mode)
    
    def add_guide_video(self, key: str, file_id: str, mode: str = "br") -> bool:
        """افزودن ویدیو به راهنما"""
        return self._add_guide_media(key, file_id, 'video', mode)
    
    def _add_guide_media(self, key: str, file_id: str, media_type: str, mode: str) -> bool:
        """افزودن رسانه به راهنما"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id FROM guides WHERE key = %s AND mode = %s
                """, (key, mode))
                result = cursor.fetchone()
                
                if result:
                    guide_id = result['id']
                else:
                    cursor.execute("""
                        INSERT INTO guides (key, mode, name)
                        VALUES (%s, %s, %s)
                        RETURNING id
                    """, (key, mode, key.title()))
                    result = cursor.fetchone()
                    guide_id = result['id']
                
                cursor.execute("""
                    SELECT COALESCE(MAX(order_index), -1) as max_order
                    FROM guide_media
                    WHERE guide_id = %s
                """, (guide_id,))
                result = cursor.fetchone()
                max_order = result['max_order']
                
                cursor.execute("""
                    INSERT INTO guide_media (guide_id, media_type, file_id, order_index)
                    VALUES (%s, %s, %s, %s)
                """, (guide_id, media_type, file_id, max_order + 1))
                
                cursor.close()
                logger.info(f"✅ Guide media added: {key} ({media_type})")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"_add_guide_media({key}, {media_type})")
            return False
