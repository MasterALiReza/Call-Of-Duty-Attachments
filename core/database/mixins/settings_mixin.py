"""
Database mixin for Settings, Notifications, and Submission Statistics.
"""

import logging
import json
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.settings_mixin')


class SettingsDatabaseMixin:
    """
    Mixin containing settings, blacklists, notifications, and submission stats operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    # ==========================================================================
    # Global Settings
    # ==========================================================================
    def get_setting(self, key: str, default: str = None) -> str:
        """دریافت تنظیمات"""
        try:
            query = "SELECT value FROM settings WHERE key = %s"
            result = self.execute_query(query, (key,), fetch_one=True)
            return result['value'] if result else default
        except Exception as e:
            log_exception(logger, e, f"get_setting({key})")
            return default

    def set_setting(self, key: str, value: str, description: str = None,
                   category: str = "general", updated_by: int = None) -> bool:
        """تنظیم/به‌روزرسانی تنظیمات"""
        try:
            query = """
                INSERT INTO settings 
                (key, value, description, category, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    description = COALESCE(EXCLUDED.description, settings.description),
                    category = COALESCE(EXCLUDED.category, settings.category),
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
            """
            self.execute_query(query, (key, value, description, category, updated_by))
            logger.info(f"✅ Setting {key} updated to: {value}")
            return True
        except Exception as e:
            log_exception(logger, e, f"set_setting({key})")
            return False

    def get_all_settings(self, category: str = None) -> List[Dict]:
        """دریافت همه تنظیمات"""
        try:
            if category:
                query = """
                    SELECT * FROM settings WHERE category = %s ORDER BY key
                """
                results = self.execute_query(query, (category,), fetch_all=True)
            else:
                query = "SELECT * FROM settings ORDER BY category, key"
                results = self.execute_query(query, fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, "get_all_settings")
            return []

    # ==========================================================================
    # Blacklisted Words
    # ==========================================================================
    def get_all_blacklisted_words(self) -> List[Dict]:
        """دریافت تمام کلمات ممنوعه"""
        try:
            query = "SELECT word, category, severity FROM blacklisted_words ORDER BY created_at DESC"
            results = self.execute_query(query, fetch_all=True)
            return results if results else []
        except Exception as e:
            log_exception(logger, e, "get_all_blacklisted_words")
            return []

    def add_blacklisted_word(self, word: str, category: str = 'profanity',
                            severity: int = 1, admin_id: int = None) -> bool:
        """افزودن کلمه ممنوعه"""
        try:
            query = """
                INSERT INTO blacklisted_words (word, category, severity, added_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (word) DO NOTHING
            """
            self.execute_query(query, (word.lower(), category, severity, admin_id))
            logger.info(f"✅ Blacklisted word added: '{word}' (severity: {severity})")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_blacklisted_word({word})")
            return False

    def remove_blacklisted_word(self, word_id: int) -> bool:
        """حذف کلمه ممنوعه"""
        try:
            query = "DELETE FROM blacklisted_words WHERE id = %s"
            self.execute_query(query, (word_id,))
            logger.info(f"✅ Blacklisted word removed: ID={word_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"remove_blacklisted_word({word_id})")
            return False

    # ==========================================================================
    # User Preferences
    # ==========================================================================
    def get_user_notification_preferences(self, user_id: int) -> Optional[dict]:
        """دریافت تنظیمات نوتیفیکیشن کاربر"""
        try:
            query = """
                SELECT enabled, modes, events 
                FROM user_notification_preferences 
                WHERE user_id = %s
            """
            result = self.execute_query(query, (user_id,), fetch_one=True)
            if result:
                modes = result['modes']
                events = result['events']
                if isinstance(modes, str):
                    modes = json.loads(modes)
                if isinstance(events, str):
                    events = json.loads(events)
                return {
                    'enabled': bool(result['enabled']),
                    'modes': modes,
                    'events': events
                }
            return None
        except Exception as e:
            log_exception(logger, e, f"get_user_notification_preferences({user_id})")
            return None

    def update_user_notification_preferences(self, user_id: int, preferences: dict) -> bool:
        """به‌روزرسانی تنظیمات نوتیفیکیشن کاربر"""
        try:
            query = """
                INSERT INTO user_notification_preferences (user_id, enabled, modes, events, updated_at)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, NOW())
                ON CONFLICT(user_id) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    modes = EXCLUDED.modes,
                    events = EXCLUDED.events,
                    updated_at = NOW()
            """
            self.execute_query(query, (
                user_id,
                preferences.get('enabled', True),
                json.dumps(preferences.get('modes', ['br', 'mp'])),
                json.dumps(preferences.get('events', {}))
            ))
            logger.info(f"✅ Notification preferences updated: user={user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_user_notification_preferences({user_id})")
            return False

    def set_user_subscription(self, user_id: int, is_subscriber: bool) -> bool:
        """تنظیم وضعیت اشتراک کاربر"""
        try:
            query = """
                UPDATE users 
                SET is_subscriber = %s 
                WHERE user_id = %s
            """
            self.execute_query(query, (is_subscriber, user_id))
            logger.info(f"✅ User subscription updated: {user_id} -> {is_subscriber}")
            return True
        except Exception as e:
            log_exception(logger, e, f"set_user_subscription({user_id})")
            return False

    # ==========================================================================
    # Submission Statistics
    # ==========================================================================
    def get_user_submission_stats(self, user_id: int) -> Optional[Dict]:
        """دریافت آمار ارسال کاربر"""
        try:
            query = """
                SELECT * FROM user_submission_stats WHERE user_id = %s
            """
            row = self.execute_query(query, (user_id,), fetch_one=True)
            defaults = {
                'user_id': user_id,
                'total_submissions': 0,
                'violation_count': 0,
                'strike_count': 0.0,
                'is_banned': False,
                'daily_submissions': 0,
                'daily_reset_date': None,
                'banned_reason': None,
                'banned_at': None,
                'approved_count': 0,
                'rejected_count': 0,
                'pending_count': 0,
                'last_submission_at': None,
            }

            if row:
                data = dict(row)
                merged = {**defaults, **data}
                return merged

            try:
                with self.transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO user_submission_stats (user_id)
                        VALUES (%s)
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING *
                    """, (user_id,))
                    _ = cursor.fetchone()
                    return defaults
            except Exception as e:
                log_exception(logger, e, f"get_user_submission_stats->create_new({user_id})")
                return defaults

        except Exception as e:
            log_exception(logger, e, f"get_user_submission_stats({user_id})")
            return None

    def update_submission_stats(self, user_id: int, increment_total: bool = False,
                               increment_daily: bool = False, add_violation: int = 0,
                               add_strike: float = 0.0) -> bool:
        """به‌روزرسانی آمار ارسال کاربر"""
        try:
            query = """
                INSERT INTO user_submission_stats (
                    user_id, total_submissions, daily_submissions, 
                    violation_count, strike_count, last_submission_at
                ) VALUES (
                    %s, 
                    CASE WHEN %s THEN 1 ELSE 0 END, 
                    CASE WHEN %s THEN 1 ELSE 0 END, 
                    %s, %s, 
                    NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    total_submissions = user_submission_stats.total_submissions + CASE WHEN %s THEN 1 ELSE 0 END,
                    daily_submissions = user_submission_stats.daily_submissions + CASE WHEN %s THEN 1 ELSE 0 END,
                    violation_count = user_submission_stats.violation_count + %s,
                    strike_count = user_submission_stats.strike_count + %s,
                    last_submission_at = NOW(),
                    updated_at = NOW()
            """
            self.execute_query(query, (
                user_id,
                increment_total, increment_daily, add_violation, add_strike,
                increment_total, increment_daily, add_violation, add_strike
            ))
            return True
        except Exception as e:
            log_exception(logger, e, f"update_submission_stats({user_id})")
            return False

    # ==========================================================================
    # Extra Settings & Database Utility Methods
    # ==========================================================================
    
    def delete_setting(self, key: str) -> bool:
        """حذف تنظیمات"""
        try:
            query = "DELETE FROM settings WHERE key = %s"
            self.execute_query(query, (key,))
            logger.info(f"✅ Setting {key} deleted")
            return True
        except Exception as e:
            log_exception(logger, e, f"delete_setting({key})")
            return False
    
    def get_ua_setting(self, key: str) -> Optional[str]:
        """دریافت یک تنظیم user_attachment از جدول واحد settings"""
        try:
            query = """
                SELECT value as setting_value FROM settings 
                WHERE key = %s AND category = 'user_attachments'
            """
            row = self.execute_query(query, (key,), fetch_one=True)
            if row:
                return row['setting_value']
            if key == 'system_enabled':
                return '1'
            return None
        except Exception as e:
            log_exception(logger, e, f"get_ua_setting({key})")
            return None
    
    def get_all_ua_settings(self) -> List[Dict]:
        """دریافت تمام تنظیمات user_attachment از جدول settings"""
        try:
            query = """
                SELECT key as setting_key, value as setting_value, updated_at, updated_by
                FROM settings
                WHERE category = 'user_attachments'
                ORDER BY key
            """
            rows = self.execute_query(query, fetch_all=True)
            return [dict(row) for row in rows]
        except Exception as e:
            log_exception(logger, e, "get_all_ua_settings")
            return []
    
    def get_all_user_attachment_settings(self) -> List[Dict]:
        """Alias for get_all_ua_settings() - used by settings_handler"""
        return self.get_all_ua_settings()
    
    def update_ua_setting(self, key: str, value: str, admin_id: int = None) -> bool:
        """به‌روزرسانی تنظیم user_attachment (UPSERT در جدول settings با category)"""
        try:
            query = """
                INSERT INTO settings (key, value, category, updated_at, updated_by)
                VALUES (%s, %s, 'user_attachments', NOW(), %s)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """
            self.execute_query(query, (key, value, admin_id))
            logger.info(f"✅ UA Setting upserted: {key} = {value}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_ua_setting({key})")
            return False
    
    def set_user_attachment_setting(self, key: str, value: str, admin_id: int = None) -> bool:
        """Alias for update_ua_setting() - used by settings_handler"""
        return self.update_ua_setting(key, value, admin_id)
    
    def backup_database(self, backup_dir: str = 'backups') -> str:
        """ایجاد backup از دیتابیس PostgreSQL"""
        import subprocess
        from datetime import datetime
        import os
        
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'postgres_backup_{timestamp}.sql')
            
            cmd = [
                'pg_dump',
                '-h', os.getenv('POSTGRES_HOST', 'localhost'),
                '-p', os.getenv('POSTGRES_PORT', '5432'),
                '-U', os.getenv('POSTGRES_USER', 'postgres'),
                '-d', os.getenv('POSTGRES_DB', 'codm_bot'),
                '-F', 'c',  # Custom format
                '-f', backup_file
            ]
            
            env = os.environ.copy()
            if os.getenv('POSTGRES_PASSWORD'):
                env['PGPASSWORD'] = os.getenv('POSTGRES_PASSWORD')
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ PostgreSQL backup created: {backup_file}")
                return backup_file
            else:
                logger.error(f"pg_dump failed: {result.stderr}")
                return None
                
        except Exception as e:
            log_exception(logger, e, "backup_database")
            return None
    
    def export_data(self, file_path: str) -> bool:
        """Export دیتا به فایل"""
        try:
            logger.warning("export_data: Not fully implemented for PostgreSQL")
            return False
        except Exception as e:
            log_exception(logger, e, "export_data")
            return False
    
    def import_data(self, file_path: str) -> bool:
        """Import دیتا از فایل"""
        try:
            logger.warning("import_data: Not fully implemented for PostgreSQL")
            return False
        except Exception as e:
            log_exception(logger, e, "import_data")
            return False
