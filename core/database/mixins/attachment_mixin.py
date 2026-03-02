"""
Database mixin for Category, Weapon, and Attachment operations.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from core.cache.cache_manager import cached
from psycopg.errors import UniqueViolation
from utils.logger import log_exception

logger = logging.getLogger('database.attachment_mixin')


class AttachmentDatabaseMixin:
    """
    Mixin containing weapon, category, and attachment operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    # ==========================================================================
    # Categories & Weapons
    # ==========================================================================
    def get_weapons_in_category(self, category: str, include_inactive: bool = False) -> List[str]:
        """دریافت لیست سلاح‌های یک دسته"""
        try:
            active_filter = "" if include_inactive else "AND w.is_active = TRUE"
            query = f"""
                SELECT w.name
                FROM weapons w
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s {active_filter}
                ORDER BY w.name
            """
            
            results = self.execute_query(query, (category,), fetch_all=True)
            return [row['name'] for row in results]
        except Exception as e:
            log_exception(logger, e, f"get_weapons_in_category({category})")
            return []

    def add_weapon(self, category: str, weapon_name: str) -> bool:
        """افزودن سلاح جدید"""
        try:
            query1 = "SELECT id FROM weapon_categories WHERE name = %s"
            result = self.execute_query(query1, (category,), fetch_one=True)
            if not result:
                logger.error(f"Category '{category}' not found")
                return False
            category_id = result['id']
            query2 = """
                INSERT INTO weapons (category_id, name, created_at)
                VALUES (%s, %s, NOW())
            """
            self.execute_query(query2, (category_id, weapon_name))
            logger.info(f"✅ Weapon added: {weapon_name} in {category}")
            return True
        except UniqueViolation:
            logger.info(f"Weapon already exists, skipping: {weapon_name} in {category}")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_weapon({category}, {weapon_name})")
            return False

    @cached(ttl=1800)
    def get_all_category_counts(self) -> Dict[str, int]:
        """دریافت تعداد سلاح‌های همه دسته‌ها"""
        try:
            query = """
                SELECT c.name, COUNT(w.id) as count
                FROM weapon_categories c
                LEFT JOIN weapons w ON c.id = w.category_id
                GROUP BY c.name
            """
            results = self.execute_query(query, fetch_all=True)
            return {row['name']: row['count'] for row in results}
        except Exception as e:
            log_exception(logger, e, "get_all_category_counts")
            return {}

    # ==========================================================================
    # Search & Fetch Attachments
    # ==========================================================================
    def get_weapon_attachments(self, category: str, weapon_name: str, mode: str) -> List[Dict]:
        """دریافت اتچمنت‌های یک سلاح برای یک mode خاص"""
        try:
            query = """
                SELECT 
                    a.id, a.code, a.name, a.mode,
                    a.image_file_id as image,
                    a.is_top as top, 
                    a.is_season_top as season_top
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s AND w.name = %s AND a.mode = %s
                ORDER BY a.is_top DESC, a.is_season_top DESC, a.order_index NULLS LAST, a.id
            """
            results = self.execute_query(query, (category, weapon_name, mode), fetch_all=True)
            if not results:
                logger.debug(f"No attachments found for {weapon_name} ({mode})")
            return results
        except Exception as e:
            log_exception(logger, e, f"get_weapon_attachments({category}, {weapon_name})")
            return []

    def get_top_attachments(self, category: str, weapon_name: str, mode: str = "br") -> List[Dict]:
        """دریافت 5 اتچمنت برتر"""
        try:
            query = """
                SELECT 
                    a.id, a.code, a.name, 
                    a.image_file_id as image,
                    a.is_top, a.is_season_top as season_top
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s 
                  AND w.name = %s 
                  AND a.mode = %s 
                  AND a.is_top = TRUE
                ORDER BY a.order_index NULLS LAST, a.id
                LIMIT 5
            """
            results = self.execute_query(query, (category, weapon_name, mode), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"get_top_attachments({category}, {weapon_name})")
            return []

    def get_all_attachments(self, category: str, weapon_name: str, mode: str = "br") -> List[Dict]:
        """دریافت تمام اتچمنت‌های یک سلاح"""
        return self.get_weapon_attachments(category, weapon_name, mode)

    def search(self, query_text: str) -> List[Dict]:
        """جستجوی اتچمنت‌ها بر اساس نام، کد یا نام سلاح"""
        try:
            query = """
                SELECT 
                    a.id, a.code, a.name, a.mode,
                    a.image_file_id as image,
                    w.name AS weapon,
                    c.name AS category
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE a.code ILIKE %s 
                   OR a.name ILIKE %s 
                   OR w.name ILIKE %s
                ORDER BY w.name, a.mode, a.is_top DESC
                LIMIT 10
            """
            search_param = f"%{query_text}%"
            results = self.execute_query(query, (search_param, search_param, search_param), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"search({query_text})")
            return []

    # ==========================================================================
    # Modify Attachments
    # ==========================================================================
    def set_top_attachments(self, category: str, weapon_name: str,
                            attachment_codes: List[str], mode: str = "br") -> bool:
        """تنظیم اتچمنت‌های برتر برای یک سلاح/مود"""
        try:
            codes = list(dict.fromkeys(attachment_codes))[:5]
            if not codes:
                return True
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT w.id FROM weapons w
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE c.name = %s AND w.name = %s
                    """,
                    (category, weapon_name),
                )
                res = cursor.fetchone()
                if not res:
                    cursor.close()
                    return False
                weapon_id = res["id"]
                
                cursor.execute(
                    """
                    UPDATE attachments
                    SET is_top = FALSE, updated_at = NOW()
                    WHERE weapon_id = %s AND mode = %s
                    """,
                    (weapon_id, mode),
                )
                
                case_parts = []
                params = []
                for idx, code in enumerate(codes, start=1):
                    case_parts.append("WHEN code = %s THEN %s")
                    params.extend([code, idx])
                case_sql = " ".join(case_parts)
                in_placeholders = ", ".join(["%s"] * len(codes))
                params.extend([weapon_id, mode, *codes])
                
                update_sql = f"""
                    UPDATE attachments
                    SET is_top = TRUE,
                        order_index = CASE {case_sql} ELSE order_index END,
                        updated_at = NOW()
                    WHERE weapon_id = %s AND mode = %s AND code IN ({in_placeholders})
                """
                cursor.execute(update_sql, tuple(params))
                cursor.close()
                return True
        except Exception as e:
            log_exception(logger, e, f"set_top_attachments({category}, {weapon_name})")
            return False

    def add_attachment(self, category: str, weapon_name: str, code: str,
                      name: str, image: str = None, is_top: bool = False,
                      is_season_top: bool = False, mode: str = "br") -> bool:
        """افزودن اتچمنت جدید"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                query_weapon = """
                    SELECT w.id FROM weapons w
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE c.name = %s AND w.name = %s
                """
                cursor.execute(query_weapon, (category, weapon_name))
                result = cursor.fetchone()
                if not result:
                    cursor.close()
                    if not self.add_weapon(category, weapon_name):
                        return False
                    cursor = conn.cursor()
                    cursor.execute(query_weapon, (category, weapon_name))
                    result = cursor.fetchone()
                    if not result:
                        cursor.close()
                        return False
                
                weapon_id = result['id']
                query_insert = """
                    INSERT INTO attachments (
                        weapon_id, mode, code, name, image_file_id,
                        is_top, is_season_top, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (weapon_id, mode, code)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        image_file_id = EXCLUDED.image_file_id,
                        is_top = EXCLUDED.is_top,
                        is_season_top = EXCLUDED.is_season_top,
                        updated_at = NOW()
                """
                cursor.execute(
                    query_insert,
                    (weapon_id, mode, code, name, image, is_top, is_season_top)
                )
                cursor.close()
                return True
        except Exception as e:
            log_exception(logger, e, f"add_attachment({category}, {weapon_name}, {code})")
            return False

    def update_attachment(self, attachment_id: int = None, category: str = None,
                         weapon_name: str = None, mode: str = None, code: str = None,
                         name: str = None, image: str = None, 
                         is_top: bool = None, is_season_top: bool = None) -> bool:
        """ویرایش اتچمنت"""
        try:
            updates = []
            params = []
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if image is not None:
                updates.append("image_file_id = %s")
                params.append(image)
            if is_top is not None:
                updates.append("is_top = %s")
                params.append(is_top)
            if is_season_top is not None:
                updates.append("is_season_top = %s")
                params.append(is_season_top)
                
            if not updates:
                return False
                
            updates.append("updated_at = NOW()")
            
            if attachment_id is not None:
                where_clause = "id = %s"
                params.append(attachment_id)
            elif all([category, weapon_name, mode, code]):
                where_clause = """
                    weapon_id = (
                        SELECT w.id FROM weapons w
                        JOIN weapon_categories c ON w.category_id = c.id
                        WHERE c.name = %s AND w.name = %s
                    ) AND mode = %s AND code = %s
                """
                params.extend([category, weapon_name, mode, code])
            else:
                return False
                
            query = f"""
                UPDATE attachments
                SET {', '.join(updates)}
                WHERE {where_clause}
            """
            self.execute_query(query, tuple(params))
            return True
        except Exception as e:
            log_exception(logger, e, f"update_attachment")
            return False

    def delete_attachment(self, attachment_id: int = None, category: str = None,
                         weapon_name: str = None, mode: str = None, code: str = None) -> bool:
        """حذف اتچمنت"""
        try:
            if attachment_id is not None:
                query = "DELETE FROM attachments WHERE id = %s"
                params = (attachment_id,)
            elif all([category, weapon_name, mode, code]):
                query = """
                    DELETE FROM attachments
                    WHERE weapon_id = (
                        SELECT w.id FROM weapons w
                        JOIN weapon_categories c ON w.category_id = c.id
                        WHERE c.name = %s AND w.name = %s
                    ) AND mode = %s AND code = %s
                """
                params = (category, weapon_name, mode, code)
            else:
                return False
            self.execute_query(query, params)
            return True
        except Exception as e:
            log_exception(logger, e, f"delete_attachment")
            return False

    def update_attachment_code(self, category: str, weapon_name: str, old_code: str, 
                               new_code: str, mode: str = "br") -> bool:
        """به‌روزرسانی کد اتچمنت"""
        try:
            query = """
                UPDATE attachments 
                SET code = %s
                WHERE weapon_id = (
                    SELECT w.id FROM weapons w
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE c.name = %s AND w.name = %s
                )
                AND code = %s AND mode = %s
            """
            result = self.execute_query(query, (new_code, category, weapon_name, old_code, mode))
            if result and hasattr(result, 'rowcount'):
                return result.rowcount > 0
            return True
        except Exception as e:
            log_exception(logger, e, f"update_attachment_code({category}, {weapon_name}, {old_code}, {new_code})")
            return False

    def edit_attachment(
        self,
        category: str,
        weapon_name: str,
        code: str,
        new_name: str = None,
        new_image: str = None,
        new_code: str = None,
        mode: str = "br",
    ) -> bool:
        """ویرایش اتچمنت (wrapper سازگار با نسخه‌های قدیمی)"""
        try:
            success = True
            if new_name is not None or new_image is not None:
                ok = self.update_attachment(
                    category=category,
                    weapon_name=weapon_name,
                    mode=mode,
                    code=code,
                    name=new_name,
                    image=new_image,
                )
                success = success and ok
            if new_code:
                ok = self.update_attachment_code(
                    category=category,
                    weapon_name=weapon_name,
                    old_code=code,
                    new_code=new_code,
                    mode=mode,
                )
                success = success and ok
            return success
        except Exception as e:
            log_exception(logger, e, f"edit_attachment({category}, {weapon_name}, {code})")
            return False

    # ==========================================================================
    # Specific ID and Season Fetches
    # ==========================================================================
    def get_attachment_by_id(self, attachment_id: int) -> Optional[Dict]:
        """دریافت اطلاعات کامل یک اتچمنت با ID"""
        try:
            query = """
                SELECT 
                    a.id, a.code, a.name, a.mode,
                    a.image_file_id as image,
                    w.name AS weapon,
                    c.name AS category
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE a.id = %s
            """
            return self.execute_query(query, (attachment_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f"get_attachment_by_id({attachment_id})")
            return None

    def get_attachment_code_by_id(self, attachment_id: int) -> Optional[str]:
        """دریافت فقط کد اتچمنت با ID"""
        try:
            query = "SELECT code FROM attachments WHERE id = %s"
            result = self.execute_query(query, (attachment_id,), fetch_one=True)
            return result['code'] if result else None
        except Exception as e:
            log_exception(logger, e, f"get_attachment_code_by_id({attachment_id})")
            return None

    def get_season_top_attachments_for_weapon(self, category: str, weapon_name: str, 
                                             mode: str = "br") -> List[Dict]:
        """دریافت برترین‌های فصل برای یک سلاح خاص"""
        try:
            query = """
                SELECT 
                    a.code, a.name, 
                    a.image_file_id as image
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s 
                  AND w.name = %s 
                  AND a.mode = %s 
                  AND a.is_season_top = TRUE
                ORDER BY a.id
            """
            results = self.execute_query(query, (category, weapon_name, mode), fetch_all=True)
            for row in results:
                row['season_top'] = True
            return results
        except Exception as e:
            log_exception(logger, e, f"get_season_top_attachments_for_weapon")
            return []

    def get_season_top_attachments(self, mode: str = None) -> List[Dict]:
        """دریافت همه برترین‌های فصل"""
        try:
            if mode:
                query = """
                    SELECT 
                        c.name as category, w.name as weapon, a.mode,
                        a.id, a.code, a.name as att_name, a.image_file_id as image
                    FROM attachments a
                    JOIN weapons w ON a.weapon_id = w.id
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE a.is_season_top = TRUE AND a.mode = %s
                    ORDER BY c.id, w.name
                """
                results = self.execute_query(query, (mode,), fetch_all=True)
            else:
                query = """
                    SELECT 
                        c.name as category, w.name as weapon, a.mode,
                        a.id, a.code, a.name as att_name, a.image_file_id as image
                    FROM attachments a
                    JOIN weapons w ON a.weapon_id = w.id
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE a.is_season_top = TRUE
                    ORDER BY c.id, w.name, a.mode
                """
                results = self.execute_query(query, fetch_all=True)
            
            items = []
            for row in results:
                items.append({
                    'category': row['category'],
                    'weapon': row['weapon'],
                    'mode': row['mode'],
                    'attachment': {
                        'id': row['id'],
                        'code': row['code'],
                        'name': row['att_name'],
                        'image': row['image']
                    }
                })
            return items
        except Exception as e:
            log_exception(logger, e, "get_season_top_attachments")
            return []

    # ==========================================================================
    # Phase 3: Weapon Management - Day 2
    # ==========================================================================
    
    def get_weapon_by_name(self, category: str, weapon_name: str) -> dict:
        """دریافت اطلاعات سلاح بر اساس نام و دسته"""
        try:
            query = """
                SELECT w.* 
                FROM weapons w
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s AND w.name = %s
            """
            result = self.execute_query(query, (category, weapon_name), fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            log_exception(logger, e, f"get_weapon_by_name({category}, {weapon_name})")
            return None
    
    def get_weapon_info(self, category: str, weapon_name: str) -> dict:
        """دریافت اطلاعات کامل یک سلاح"""
        try:
            query_weapon = """
                SELECT w.id, w.is_active 
                FROM weapons w
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE c.name = %s AND w.name = %s
            """
            result = self.execute_query(query_weapon, (category, weapon_name), fetch_one=True)
            
            if not result:
                return {'br': {'attachment_count': 0, 'top_count': 0}, 
                        'mp': {'attachment_count': 0, 'top_count': 0},
                        'is_active': True}
            
            weapon_id = result['id']
            is_active = result.get('is_active', True)
            info = {'is_active': is_active}
            
            for mode in ['br', 'mp']:
                query_counts = """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN is_top = TRUE THEN 1 ELSE 0 END) as top_count
                    FROM attachments
                    WHERE weapon_id = %s AND mode = %s
                """
                counts = self.execute_query(query_counts, (weapon_id, mode), fetch_one=True)
                
                info[mode] = {
                    'attachment_count': counts['total'] or 0,
                    'top_count': counts['top_count'] or 0
                }
            
            return info
            
        except Exception as e:
            log_exception(logger, e, f"get_weapon_info({category}, {weapon_name})")
            return {'br': {'attachment_count': 0, 'top_count': 0}, 
                    'mp': {'attachment_count': 0, 'top_count': 0},
                    'is_active': True}
    
    def delete_weapon(self, category: str, weapon_name: str, mode: str = None) -> bool:
        """حذف سلاح یا اتچمنت‌های یک mode خاص"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT w.id 
                    FROM weapons w
                    JOIN weapon_categories c ON w.category_id = c.id
                    WHERE c.name = %s AND w.name = %s
                """, (category, weapon_name))
                result = cursor.fetchone()
                
                if not result:
                    cursor.close()
                    return False
                
                weapon_id = result['id']
                
                if mode is None:
                    cursor.close()
                    logger.warning(f"⚠️ Weapon deletion attempted but blocked: {category}/{weapon_name}")
                    return False
                
                cursor.execute("""
                    DELETE FROM attachments 
                    WHERE weapon_id = %s AND mode = %s
                """, (weapon_id, mode))
                
                cursor.close()
                logger.info(f"✅ Weapon attachments deleted: {category}/{weapon_name} ({mode})")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"delete_weapon({category}, {weapon_name})")
            return False

    def toggle_weapon_status(self, category: str, weapon_name: str) -> bool:
        """تغییر وضعیت فعال/غیرفعال بودن سلاح"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE weapons w
                    SET is_active = NOT COALESCE(w.is_active, TRUE), updated_at = NOW()
                    FROM weapon_categories c
                    WHERE w.category_id = c.id AND c.name = %s AND w.name = %s
                    RETURNING w.is_active
                """, (category, weapon_name))
                result = cursor.fetchone()
                cursor.close()
                if result:
                    new_status = result['is_active']
                    logger.info(f"✅ Weapon status toggled: {category}/{weapon_name} -> {'Active' if new_status else 'Inactive'}")
                    return True
                return False
        except Exception as e:
            log_exception(logger, e, f"toggle_weapon_status({category}, {weapon_name})")
            return False

    # ==========================================================================
    # Suggested Attachments - Day 3
    # ==========================================================================
    
    def add_suggested_attachment(self, attachment_id: int, mode: str, priority: int = 999, 
                                reason: str = None, added_by: int = None) -> bool:
        """اضافه کردن اتچمنت به لیست پیشنهادی"""
        try:
            query = """
                INSERT INTO suggested_attachments 
                (attachment_id, mode, priority, reason, added_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (attachment_id, mode) DO UPDATE SET
                    priority = EXCLUDED.priority,
                    reason = EXCLUDED.reason,
                    added_by = EXCLUDED.added_by
            """
            self.execute_query(query, (attachment_id, mode, priority, reason, added_by))
            logger.info(f"✅ Attachment {attachment_id} added to suggested list ({mode})")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_suggested_attachment({attachment_id}, {mode})")
            return False
    
    def remove_suggested_attachment(self, attachment_id: int, mode: str) -> bool:
        """حذف اتچمنت از لیست پیشنهادی"""
        try:
            query = """
                DELETE FROM suggested_attachments 
                WHERE attachment_id = %s AND mode = %s
            """
            self.execute_query(query, (attachment_id, mode))
            logger.info(f"✅ Attachment {attachment_id} removed from suggested list ({mode})")
            return True
        except Exception as e:
            log_exception(logger, e, f"remove_suggested_attachment({attachment_id}, {mode})")
            return False
    
    def get_suggested_attachments(self, mode: str) -> List[Dict]:
        """دریافت لیست اتچمنت‌های پیشنهادی"""
        try:
            query = """
                SELECT c.name as category, w.name as weapon, a.mode,
                       a.id, a.code, a.name as att_name, a.image_file_id as image,
                       sa.priority, sa.reason, sa.added_at
                FROM suggested_attachments sa
                JOIN attachments a ON sa.attachment_id = a.id
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE sa.mode = %s
                ORDER BY sa.priority, c.id, w.name
            """
            result = self.execute_query(query, (mode,), fetch_all=True)
            
            items = []
            for row in result:
                items.append({
                    'category': row['category'],
                    'weapon': row['weapon'],
                    'mode': row['mode'],
                    'attachment': {
                        'id': row['id'],
                        'code': row['code'],
                        'name': row['att_name'],
                        'image': row['image'],
                        'priority': row['priority'],
                        'reason': row['reason']
                    }
                })
            
            return items
        except Exception as e:
            log_exception(logger, e, f"get_suggested_attachments({mode})")
            return []
    
    def is_attachment_suggested(self, attachment_id: int, mode: str) -> bool:
        """بررسی اینکه آیا اتچمنت در لیست پیشنهادی هست یا نه"""
        try:
            query = """
                SELECT COUNT(*) as count
                FROM suggested_attachments
                WHERE attachment_id = %s AND mode = %s
            """
            result = self.execute_query(query, (attachment_id, mode), fetch_one=True)
            return result['count'] > 0
        except Exception as e:
            log_exception(logger, e, f"is_attachment_suggested({attachment_id})")
            return False
    
    def clear_suggested_attachments(self, mode: str = None) -> bool:
        """پاک کردن همه اتچمنت‌های پیشنهادی"""
        try:
            if mode:
                query = "DELETE FROM suggested_attachments WHERE mode = %s"
                self.execute_query(query, (mode,))
                logger.info(f"✅ Cleared all suggested attachments for mode {mode}")
            else:
                query = "DELETE FROM suggested_attachments"
                self.execute_query(query)
                logger.info("✅ Cleared all suggested attachments")
            return True
        except Exception as e:
            log_exception(logger, e, "clear_suggested_attachments")
            return False
    
    def get_suggested_count(self, mode: str = None) -> int:
        """دریافت تعداد اتچمنت‌های پیشنهادی"""
        try:
            if mode:
                query = """
                    SELECT COUNT(*) as count
                    FROM suggested_attachments
                    WHERE mode = %s
                """
                result = self.execute_query(query, (mode,), fetch_one=True)
            else:
                query = """
                    SELECT COUNT(*) as count
                    FROM suggested_attachments
                """
                result = self.execute_query(query, fetch_one=True)
            
            return result['count']
        except Exception as e:
            log_exception(logger, e, "get_suggested_count")
            return 0
    
    def get_suggested_ranked(self, mode: str, category: str = None, weapon: str = None) -> List[Dict]:
        """دریافت اتچمنت‌های پیشنهادی با رتبه‌بندی هوشمند (dict-only)"""
        try:
            # ساخت شرط‌های WHERE
            where_clauses = ["sa.mode = %s"]
            params = [mode]
            
            if category:
                where_clauses.append("wc.name = %s")
                params.append(category)
            
            if weapon:
                where_clauses.append("w.name = %s")
                params.append(weapon)
            
            where_sql = " AND ".join(where_clauses)
            
            # کوئری با محاسبه PopScore
            query = f"""
                SELECT 
                    wc.name as category,
                    w.name as weapon,
                    sa.mode,
                    a.id,
                    a.name,
                    a.code,
                    a.image_file_id as image,
                    sa.priority,
                    sa.reason,
                    COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) as likes,
                    COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) as dislikes,
                    COALESCE(SUM(uae.total_views), 0) as views,
                    -- محاسبه PopScore
                    (1000 - sa.priority) + 
                    (COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) * 10) - 
                    (COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) * 5) +
                    (COALESCE(SUM(uae.total_views), 0) / 10.0) as pop_score
                FROM suggested_attachments sa
                JOIN attachments a ON sa.attachment_id = a.id
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories wc ON w.category_id = wc.id
                LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id
                WHERE {where_sql}
                GROUP BY a.id, wc.name, w.name, sa.mode, sa.priority, sa.reason
                ORDER BY pop_score DESC, sa.priority ASC, likes DESC
            """
            
            results = self.execute_query(query, tuple(params), fetch_all=True)
            
            # تبدیل به فرمت dict-only
            ranked_list = []
            for row in results:
                att_dict = {
                    'id': row['id'],
                    'name': row['name'],
                    'code': row['code'],
                    'image': row['image'],
                    'priority': row['priority'],
                    'reason': row['reason'],
                    'likes': row['likes'],
                    'dislikes': row['dislikes'],
                    'views': row['views'],
                    'pop_score': round(float(row['pop_score']), 2)
                }
                ranked_list.append({
                    'category': row['category'],
                    'weapon': row['weapon'],
                    'mode': row['mode'],
                    'attachment': att_dict
                })
            
            logger.info(f"Ranked suggestions: mode={mode}, count={len(ranked_list)}")
            return ranked_list
            
        except Exception as e:
            log_exception(logger, e, f"get_suggested_ranked({mode})")
            return []
