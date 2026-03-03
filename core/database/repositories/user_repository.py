"""
Database mixin for User and Role management.
"""

import logging
from .base_repository import BaseRepository
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.user_mixin')


class UserRepository(BaseRepository):
    """
    Mixin containing user and role related database operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """
        دریافت اطلاعات کاربر از جدول users
        Returns: dict یا None
        """
        try:
            query = """
                SELECT user_id, username, first_name
                FROM users
                WHERE user_id = %s
            """
            return await self.execute_query(query, (user_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f"get_user({user_id})")
            return None

    async def get_user_language(self, user_id: int) -> Optional[str]:
        """
        دریافت زبان کاربر از جدول users
        Returns: 'fa' | 'en' | None
        """
        try:
            query = "SELECT language FROM users WHERE user_id = %s"
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            if result:
                return result.get('language')
            return None
        except Exception as e:
            log_exception(logger, e, f"get_user_language({user_id})")
            return None

    async def set_user_language(self, user_id: int, lang: str) -> bool:
        """
        تنظیم زبان کاربر در جدول users (fa/en)
        اگر کاربر وجود نداشت، ساخته می‌شود.
        """
        if lang not in ('fa', 'en'):
            logger.error(f"Invalid language: {lang}")
            return False
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO users (user_id, language)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id)
                        DO UPDATE SET language = EXCLUDED.language
                        """,
                        (user_id, lang)
                    )
                logger.info(f"✅ Language set: user={user_id}, lang={lang}")
                return True
        except Exception as e:
            log_exception(logger, e, f"set_user_language({user_id}, {lang})")
            return False

    async def unban_user_from_attachments(self, user_id: int) -> bool:
        """
        رفع محرومیت کاربر از ارسال اتچمنت‌ها
        """
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE user_submission_stats
                        SET is_banned = FALSE, updated_at = NOW()
                        WHERE user_id = %s AND is_banned = TRUE
                        """,
                        (user_id,),
                    )
                    affected = cursor.rowcount
                if affected == 0:
                    logger.warning(f"No banned record found to unban for user_id={user_id}")
                    return False
            logger.info(f"✅ User unbanned from attachments: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"unban_user_from_attachments({user_id})")
            return False

    async def create_role_if_not_exists(self, role_name: str, display_name: str, 
                                   description: str = '', icon: str = '', 
                                   permissions: List[str] = None) -> bool:
        """ایجاد role اگر وجود نداشته باشد"""
        permissions = permissions or []
        
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    
                    # بررسی وجود role
                    query_check = "SELECT id FROM roles WHERE name = %s"
                    await cursor.execute(query_check, (role_name,))
                    result = await cursor.fetchone()
                    
                    if result:
                        role_id = result['id']
                        # Update existing role
                        query_update = """
                            UPDATE roles 
                            SET display_name = %s, description = %s, icon = %s
                            WHERE id = %s
                        """
                        await cursor.execute(query_update, (display_name, description, icon, role_id))
                    else:
                        # Insert new role
                        query_insert = """
                            INSERT INTO roles (name, display_name, description, icon, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                            RETURNING id
                        """
                        await cursor.execute(query_insert, (role_name, display_name, description, icon))
                        result = await cursor.fetchone()
                        role_id = result['id']
                    
                    # حذف permissions قدیمی
                    query_delete = "DELETE FROM role_permissions WHERE role_id = %s"
                    await cursor.execute(query_delete, (role_id,))
                    # اضافه کردن permissions جدید
                    for perm in permissions:
                        query_perm = """
                            INSERT INTO role_permissions (role_id, permission)
                            VALUES (%s, %s)
                        """
                        await cursor.execute(query_perm, (role_id, perm))
                
                logger.info(f"✅ Role created/updated: {role_name}")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"create_role_if_not_exists({role_name})")
            return False

    async def get_all_users(self) -> List[int]:
        """دریافت لیست همه کاربران فعال (مشترکین)"""
        try:
            # Source of truth for active subscribers is the 'subscribers' table
            query = "SELECT user_id FROM subscribers WHERE is_active = TRUE"
            results = await self.execute_query(query, fetch_all=True)
            return [row['user_id'] for row in results]
        except Exception as e:
            log_exception(logger, e, "get_all_users")
            return []
    
    async def get_all_admins(self) -> List[Dict]:
        """دریافت لیست همه ادمین‌ها"""
        try:
            query = """
                SELECT 
                  a.user_id,
                  a.created_at,
                  a.display_name,
                  u.username,
                  u.first_name,
                  COALESCE(
                    (
                      SELECT json_agg(json_build_object('name', r.name, 'display_name', r.display_name, 'icon', r.icon))
                      FROM admin_roles ar 
                      JOIN roles r ON ar.role_id = r.id
                      WHERE ar.user_id = a.user_id
                    ), '[]'::json
                  ) AS roles
                FROM admins a
                LEFT JOIN users u ON a.user_id = u.user_id
                ORDER BY a.created_at DESC
            """

            rows = await self.execute_query(query, fetch_all=True) or []
            admins: List[Dict] = []
            import json as _json
            for row in rows:
                item = dict(row)
                # Normalize roles to list[dict]
                roles = item.get('roles')
                if isinstance(roles, str):
                    try:
                        roles = _json.loads(roles)
                    except Exception:
                        roles = []
                item['roles'] = roles or []
                admins.append(item)
            return admins
        except Exception as e:
            log_exception(logger, e, "get_all_admins")
            return []
    
    async def get_admins_count(self) -> int:
        """تعداد ادمین‌ها"""
        try:
            query = "SELECT COUNT(*) as count FROM admins"
            result = await self.execute_query(query, fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            log_exception(logger, e, "get_admins_count")
            return 0

    async def remove_admin(self, user_id: int) -> bool:
        """حذف کامل ادمین (تمام نقش‌هایش)"""
        try:
            query = "DELETE FROM admins WHERE user_id = %s"
            await self.execute_query(query, (user_id,))
            logger.info(f"✅ Admin {user_id} and all roles removed (PostgreSQL)")
            return True
        except Exception as e:
            log_exception(logger, e, f"remove_admin({user_id})")
            return False
    
    async def assign_role_to_admin(self, user_id: int, role_name: str,
                            display_name: str = None, added_by: int = None) -> bool:
        """اختصاص نقش به ادمین"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    # دریافت role_id
                    await cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                    role = await cursor.fetchone()
                    
                    if not role:
                        logger.error(f"❌ Role {role_name} not found")
                        return False
                    
                    role_id = role.get('id')
                    
                    # ✅ Ensure user exists in 'users' table (Foreign Key requirement)
                    # This allows adding admins who haven't started the bot yet.
                    await cursor.execute("""
                        INSERT INTO users (user_id, last_seen)
                        VALUES (%s, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET last_seen = NOW()
                    """, (user_id,))
                    
                    # اضافه کردن ادمین اگر وجود ندارد
                    await cursor.execute("""
                        INSERT INTO admins (user_id, display_name)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                            display_name = COALESCE(EXCLUDED.display_name, admins.display_name),
                            updated_at = NOW()
                    """, (user_id, display_name))
                    
                    # اختصاص نقش
                    await cursor.execute("""
                        INSERT INTO admin_roles (user_id, role_id, assigned_by)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, role_id) DO NOTHING
                    """, (user_id, role_id, added_by))
                
                logger.info(f"✅ Admin {user_id} assigned role {role_name}")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"assign_role_to_admin({user_id}, {role_name})")
            return False
    
    async def remove_role_from_admin(self, user_id: int, role_name: str) -> bool:
        """حذف یک نقش خاص از ادمین"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    
                    await cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                    role = await cursor.fetchone()
                    
                    if not role:
                        logger.error(f"❌ Role {role_name} not found")
                        return False
                    
                    role_id = role.get('id')
                    
                    await cursor.execute("""
                        DELETE FROM admin_roles 
                        WHERE user_id = %s AND role_id = %s
                    """, (user_id, role_id))
                    
                logger.info(f"✅ Role {role_name} removed from admin {user_id} (PostgreSQL)")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"remove_role_from_admin({user_id}, {role_name})")
            return False
    
    async def get_admin_roles(self, user_id: int) -> List[str]:
        """دریافت لیست نام نقش‌های یک ادمین"""
        try:
            query = """
                SELECT r.name
                FROM admin_roles ar
                JOIN roles r ON ar.role_id = r.id
                WHERE ar.user_id = %s
                ORDER BY r.name
            """
            results = await self.execute_query(query, (user_id,), fetch_all=True)
            return [row['name'] for row in results]
        except Exception as e:
            log_exception(logger, e, f"get_admin_roles({user_id})")
            return []

    async def get_all_roles(self) -> List[Dict]:
        """دریافت تمام نقش‌ها با permissions - بهینه‌شده با JOIN"""
        try:
            # استفاده از json_agg برای دریافت همه permissions در یک query
            query = """
                SELECT 
                    r.id, r.name, r.display_name, r.description, r.icon,
                    COALESCE(
                        json_agg(rp.permission) FILTER (WHERE rp.permission IS NOT NULL),
                        '[]'::json
                    ) as permissions
                FROM roles r
                LEFT JOIN role_permissions rp ON r.id = rp.role_id
                GROUP BY r.id, r.name, r.display_name, r.description, r.icon
                ORDER BY r.name
            """
            results = await self.execute_query(query, fetch_all=True)
            
            # تبدیل permissions از JSON به لیست
            result = []
            for row in results:
                perms = row.get('permissions', [])
                if isinstance(perms, str):
                    import json
                    perms = json.loads(perms)
                result.append({
                    'name': row['name'],
                    'display_name': row['display_name'],
                    'description': row['description'],
                    'icon': row['icon'],
                    'permissions': perms
                })
            
            return result
            
        except Exception as e:
            log_exception(logger, e, "get_all_roles")
            return []
    
    async def get_role(self, role_name: str) -> Optional[Dict]:
        """دریافت اطلاعات یک نقش - بهینه‌شده با JOIN"""
        try:
            query = """
                SELECT 
                    r.id, r.name, r.display_name, r.description, r.icon,
                    COALESCE(
                        json_agg(rp.permission) FILTER (WHERE rp.permission IS NOT NULL),
                        '[]'::json
                    ) as permissions
                FROM roles r
                LEFT JOIN role_permissions rp ON r.id = rp.role_id
                WHERE r.name = %s
                GROUP BY r.id, r.name, r.display_name, r.description, r.icon
            """
            row = await self.execute_query(query, (role_name,), fetch_one=True)
            
            if not row:
                return None
            
            perms = row.get('permissions', [])
            if isinstance(perms, str):
                import json
                perms = json.loads(perms)
            
            return {
                'name': row['name'],
                'display_name': row['display_name'],
                'description': row['description'],
                'icon': row['icon'],
                'permissions': perms
            }
            
        except Exception as e:
            log_exception(logger, e, f"get_role({role_name})")
            return None
    
    async def ban_user_from_submissions(self, user_id: int, reason: str, 
                                  banned_by: int = None) -> bool:
        """محروم کردن کاربر از ارسال اتچمنت"""
        try:
            query = """
                UPDATE user_submission_stats
                SET is_banned = TRUE,
                    banned_at = NOW(),
                    banned_reason = %s
                WHERE user_id = %s
            """
            await self.execute_query(query, (reason, user_id))
            logger.warning(f"⚠️ User {user_id} banned from submissions: {reason}")
            return True
        except Exception as e:
            log_exception(logger, e, f"ban_user_from_submissions({user_id})")
            return False
    
    async def unban_user_from_submissions(self, user_id: int) -> bool:
        """رفع محرومیت کاربر"""
        try:
            query = """
                UPDATE user_submission_stats
                SET is_banned = FALSE,
                    banned_at = NULL,
                    banned_until = NULL,
                    banned_reason = NULL,
                    strike_count = 0
                WHERE user_id = %s
            """
            await self.execute_query(query, (user_id,))
            logger.info(f"✅ User {user_id} unbanned from submissions")
            return True
        except Exception as e:
            log_exception(logger, e, f"unban_user_from_submissions({user_id})")
            return False

    async def get_user_role(self, user_id: int) -> Optional[str]:
        """دریافت نام نقش کاربر از جدول ادمین‌ها"""
        try:
            query = "SELECT role FROM admins WHERE user_id = %s LIMIT 1"
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            if result:
                return result.get('role')
            return 'user' # پیش‌فرض برای کاربران عادی
        except Exception as e:
            log_exception(logger, e, f"get_user_role({user_id})")
            return 'user'

    async def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر - CRITICAL"""
        try:
            query = "SELECT 1 FROM admins WHERE user_id = %s LIMIT 1"
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            log_exception(logger, e, f"is_admin({user_id})")
            return False
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """افزودن کاربر جدید"""
        try:
            query = """
                INSERT INTO users (user_id, username, first_name, last_seen)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, users.username),
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_seen = NOW()
            """
            await self.execute_query(query, (user_id, username, first_name))
            logger.debug(f"✅ User added: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_user({user_id})")
            return False
    
    async def upsert_user(self, user_id: int, username: str = None,
                   first_name: str = None, last_name: str = None) -> bool:
        """Insert or Update user (idempotent)"""
        try:
            query = """
                INSERT INTO users (user_id, username, first_name, last_seen)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, users.username),
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_seen = NOW()
            """
            await self.execute_query(query, (user_id, username, first_name))
            logger.debug(f"✅ User upserted: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"upsert_user({user_id})")
            return False
    
    async def get_admin(self, user_id: int) -> Optional[Dict]:
        """دریافت اطلاعات ادمین"""
        try:
            query = """
                SELECT a.*, u.username, u.first_name
                FROM admins a
                LEFT JOIN users u ON a.user_id = u.user_id
                WHERE a.user_id = %s
            """
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            
            if not result:
                return None
            
            admin = result
            q_roles = """
                SELECT r.name, r.display_name, r.icon
                FROM admin_roles ar
                JOIN roles r ON ar.role_id = r.id
                WHERE ar.user_id = %s
                ORDER BY r.name
            """
            roles = await self.execute_query(q_roles, (user_id,), fetch_all=True) or []
            admin['roles'] = roles
            return admin
        except Exception as e:
            log_exception(logger, e, f"get_admin({user_id})")
            return None
    
    async def get_user_display_name(self, user_id: int) -> str:
        """دریافت نام نمایشی کاربر"""
        try:
            query = """
                SELECT username, first_name
                FROM users
                WHERE user_id = %s
            """
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            
            if result:
                username = result.get('username')
                first_name = result.get('first_name')
                
                if username:
                    return f"@{username}"
                elif first_name:
                    return first_name
            
            return f"User_{user_id}"
        except Exception as e:
            logger.debug(f"Could not get display name for {user_id}: {e}")
            return f"User_{user_id}"
    
    async def add_user_attachment(self, user_id: int, weapon_id: int = None, mode: str = None,
                           category: str = None, custom_weapon_name: str = None,
                           attachment_name: str = None, image_file_id: str = None,
                           description: str = None) -> Optional[int]:
        """افزودن اتچمنت کاربر"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    
                    await cursor.execute("""
                        INSERT INTO user_attachments (
                            user_id, weapon_id, mode, category, custom_weapon_name,
                            attachment_name, image_file_id, description, status, submitted_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                        RETURNING id
                    """, (user_id, weapon_id, mode, category, custom_weapon_name,
                          attachment_name, image_file_id, description))
                    
                    result = await cursor.fetchone()
                    attachment_id = result['id']
                
                logger.info(f"✅ User attachment added: ID={attachment_id}")
                return attachment_id
        except Exception as e:
            log_exception(logger, e, "add_user_attachment")
            return None
    
    async def get_user_attachment(self, attachment_id: int) -> Optional[Dict]:
        """دریافت اتچمنت کاربر"""
        try:
            query = """
                SELECT ua.*, u.username, u.first_name
                FROM user_attachments ua
                LEFT JOIN users u ON ua.user_id = u.user_id
                WHERE ua.id = %s
            """
            result = await self.execute_query(query, (attachment_id,), fetch_one=True)
            
            if result:
                data = dict(result)
                data['weapon_name'] = data.get('custom_weapon_name', 'نامشخص')
                data['category_name'] = data.get('category', 'نامشخص')
                return data
            return None
        except Exception as e:
            log_exception(logger, e, f"get_user_attachment({attachment_id})")
            return None
    
    async def get_user_attachments_paginated(self, user_id: int, status: str = None, 
                                          limit: int = 5, offset: int = 0) -> List[Dict]:
        """دریافت اتچمنت‌های یک کاربر خاص با صفحه‌بندی"""
        # Validate status to prevent injection (whitelist approach)
        ALLOWED_STATUSES = {'pending', 'approved', 'rejected', 'deleted'}
        
        try:
            conditions = ["ua.user_id = %s"]
            params = [user_id]
            
            if status and status in ALLOWED_STATUSES:
                conditions.append("ua.status = %s")
                params.append(status)
            
            params.extend([limit, offset])
            where_clause = " AND ".join(conditions)
            
            query = f"""
                SELECT ua.*, w.name as weapon_name, w.display_name as weapon_display
                FROM user_attachments ua
                LEFT JOIN weapons w ON ua.weapon_id = w.id
                WHERE {where_clause}
                ORDER BY ua.submitted_at DESC
                LIMIT %s OFFSET %s
            """
            results = await self.execute_query(query, tuple(params), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"get_user_attachments_paginated({user_id})")
            return []

    async def get_user_attachments_count(self, user_id: int, status: str = None) -> int:
        """تعداد کل اتچمنت‌های یک کاربر برای مدیریت صفحه‌بندی"""
        # Validate status to prevent injection (whitelist approach)
        ALLOWED_STATUSES = {'pending', 'approved', 'rejected', 'deleted'}
        
        try:
            conditions = ["user_id = %s"]
            params = [user_id]
            
            if status and status in ALLOWED_STATUSES:
                conditions.append("status = %s")
                params.append(status)
            
            where_clause = " AND ".join(conditions)
            query = f"SELECT COUNT(*) as count FROM user_attachments WHERE {where_clause}"
            result = await self.execute_query(query, tuple(params), fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            log_exception(logger, e, f"get_user_attachments_count({user_id})")
            return 0

    async def get_approved_user_attachments_paginated(self, mode: str, category: str = None, 
                                                   limit: int = 5, offset: int = 0) -> List[Dict]:
        """دریافت اتچمنت‌های تایید شده برای نمایش عمومی با صفحه‌بندی"""
        # Validate mode (whitelist approach)
        ALLOWED_MODES = {'br', 'mp', 'zombies'}
        if mode not in ALLOWED_MODES:
            return []
            
        try:
            conditions = ["ua.mode = %s", "ua.status = 'approved'"]
            params = [mode]
            
            if category and category != 'all':
                conditions.append("ua.category = %s")
                params.append(category)
            
            params.extend([limit, offset])
            where_clause = " AND ".join(conditions)
            
            query = f"""
                SELECT ua.*, u.username, u.first_name, w.display_name as weapon_display
                FROM user_attachments ua
                LEFT JOIN users u ON ua.user_id = u.user_id
                LEFT JOIN weapons w ON ua.weapon_id = w.id
                WHERE {where_clause}
                ORDER BY ua.like_count DESC, ua.approved_at DESC
                LIMIT %s OFFSET %s
            """
            results = await self.execute_query(query, tuple(params), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"get_approved_user_attachments_paginated({mode})")
            return []

    async def get_approved_user_attachments_count(self, mode: str, category: str = None) -> int:
        """تعداد اتچمنت‌های تایید شده برای مدیریت صفحه‌بندی Browse"""
        # Validate mode (whitelist approach)
        ALLOWED_MODES = {'br', 'mp', 'zombies'}
        if mode not in ALLOWED_MODES:
            return 0
            
        try:
            conditions = ["mode = %s", "status = 'approved'"]
            params = [mode]
            
            if category and category != 'all':
                conditions.append("category = %s")
                params.append(category)
            
            where_clause = " AND ".join(conditions)
            query = f"SELECT COUNT(*) as count FROM user_attachments WHERE {where_clause}"
            result = await self.execute_query(query, tuple(params), fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            log_exception(logger, e, f"get_approved_user_attachments_count({mode})")
            return 0

    async def get_user_attachments_by_status(self, status: str = 'pending',
                                      limit: int = 50, offset: int = 0) -> List[Dict]:
        """دریافت اتچمنت‌های کاربر بر اساس وضعیت"""
        try:
            query = """
                SELECT ua.*, u.username, u.first_name
                FROM user_attachments ua
                LEFT JOIN users u ON ua.user_id = u.user_id
                WHERE ua.status = %s
                ORDER BY ua.submitted_at DESC
                LIMIT %s OFFSET %s
            """
            results = await self.execute_query(query, (status, limit, offset), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"get_user_attachments_by_status({status})")
            return []
    
    async def approve_user_attachment(self, attachment_id: int, admin_id: int) -> bool:
        """تایید اتچمنت کاربر"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    
                    await cursor.execute("""
                        SELECT user_id FROM user_attachments WHERE id = %s
                    """, (attachment_id,))
                    
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    
                    user_id = row['user_id']
                    
                    await cursor.execute("""
                        UPDATE user_attachments
                        SET status = 'approved',
                            approved_at = NOW(),
                            approved_by = %s
                        WHERE id = %s
                    """, (admin_id, attachment_id))
                    
                    await cursor.execute("""
                        UPDATE user_submission_stats
                        SET approved_count = approved_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                
                logger.info(f"✅ User attachment {attachment_id} approved")
                return True
        except Exception as e:
            log_exception(logger, e, f"approve_user_attachment({attachment_id})")
            return False
    
    async def reject_user_attachment(self, attachment_id: int, admin_id: int, reason: str) -> bool:
        """رد اتچمنت کاربر"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    
                    await cursor.execute("""
                        SELECT user_id FROM user_attachments WHERE id = %s
                    """, (attachment_id,))
                    
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    
                    user_id = row['user_id']
                    
                    await cursor.execute("""
                        UPDATE user_attachments
                        SET status = 'rejected',
                            rejected_at = NOW(),
                            rejected_by = %s,
                            rejection_reason = %s
                        WHERE id = %s
                    """, (admin_id, reason, attachment_id))
                    
                    await cursor.execute("""
                        UPDATE user_submission_stats
                        SET rejected_count = rejected_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                
                logger.info(f"✅ User attachment {attachment_id} rejected")
                return True
        except Exception as e:
            log_exception(logger, e, f"reject_user_attachment({attachment_id})")
            return False

    async def delete_user_attachment(self, attachment_id: int, deleted_by: int = None) -> bool:
        """حذف اتچمنت کاربر (Soft Delete)"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT user_id, status FROM user_attachments WHERE id = %s", (attachment_id,))
                    result = await cursor.fetchone()
                    if not result:
                        return False
                    
                    user_id = result['user_id']
                    status = result['status']
                    
                    if status == 'deleted':
                        return True
                    
                    await cursor.execute("""
                        UPDATE user_attachments
                        SET status = 'deleted',
                            deleted_at = NOW(),
                            deleted_by = %s
                        WHERE id = %s
                    """, (deleted_by, attachment_id))
                    
                    if status == 'approved':
                        await cursor.execute("""
                            UPDATE user_submission_stats
                            SET approved_count = GREATEST(0, approved_count - 1),
                                deleted_count = deleted_count + 1
                            WHERE user_id = %s
                        """, (user_id,))
                    elif status == 'rejected':
                        await cursor.execute("""
                            UPDATE user_submission_stats
                            SET rejected_count = GREATEST(0, rejected_count - 1),
                                deleted_count = deleted_count + 1
                            WHERE user_id = %s
                        """, (user_id,))
                    elif status == 'pending':
                        await cursor.execute("""
                            UPDATE user_submission_stats
                            SET pending_count = GREATEST(0, pending_count - 1),
                                deleted_count = deleted_count + 1
                            WHERE user_id = %s
                        """, (user_id,))
                    else:
                        await cursor.execute("""
                            UPDATE user_submission_stats
                            SET deleted_count = deleted_count + 1
                            WHERE user_id = %s
                        """, (user_id,))
                
                logger.info(f"✅ User attachment {attachment_id} soft-deleted (Status: {status})")
                return True
        except Exception as e:
            logger.error(f"Error soft-deleting user attachment: {e}")
            return False

    async def restore_user_attachment(self, attachment_id: int) -> bool:
        """بازگردانی اتچمنت به وضعیت pending"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT user_id, status FROM user_attachments WHERE id = %s", (attachment_id,))
                    result = await cursor.fetchone()
                    if not result:
                        return False
                    
                    user_id = result['user_id']
                    status = result['status']
                    
                    if status == 'pending':
                        return True
                    
                    await cursor.execute("""
                        UPDATE user_attachments
                        SET status = 'pending',
                            deleted_at = NULL,
                            deleted_by = NULL,
                            rejection_reason = NULL,
                            rejected_at = NULL,
                            rejected_by = NULL,
                            approved_at = NULL,
                            approved_by = NULL
                        WHERE id = %s
                    """, (attachment_id,))
                    
                    if status == 'approved':
                        await cursor.execute("UPDATE user_submission_stats SET approved_count = GREATEST(0, approved_count - 1) WHERE user_id = %s", (user_id,))
                    elif status == 'rejected':
                        await cursor.execute("UPDATE user_submission_stats SET rejected_count = GREATEST(0, rejected_count - 1) WHERE user_id = %s", (user_id,))
                    elif status == 'deleted':
                        await cursor.execute("UPDATE user_submission_stats SET deleted_count = GREATEST(0, deleted_count - 1) WHERE user_id = %s", (user_id,))
                    
                    await cursor.execute("UPDATE user_submission_stats SET pending_count = pending_count + 1 WHERE user_id = %s", (user_id,))
                    
                logger.info(f"✅ User attachment {attachment_id} restored to pending")
                return True
        except Exception as e:
            logger.error(f"Error restoring user attachment: {e}")
            return False

    async def get_attachments_by_status(self, status: str, page: int = 1, limit: int = 10) -> tuple[list[dict], int]:
        """دریافت لیست اتچمنت‌ها بر اساس وضعیت با صفحه‌بندی"""
        offset = (page - 1) * limit
        try:
            async with self.get_connection() as conn:
                async with conn.cursor() as cursor:
                    
                    await cursor.execute("SELECT COUNT(*) as count FROM user_attachments WHERE status = %s", (status,))
                    result = await cursor.fetchone()
                    total_count = result['count'] if result else 0
                    
                    await cursor.execute("""
                        SELECT 
                            ua.*,
                            u.username, u.first_name,
                            CASE 
                                WHEN ua.status = 'approved' THEN ua.approved_at
                                WHEN ua.status = 'rejected' THEN ua.rejected_at
                                WHEN ua.status = 'deleted' THEN ua.deleted_at
                                ELSE ua.submitted_at 
                            END as action_date
                        FROM user_attachments ua
                        LEFT JOIN users u ON ua.user_id = u.user_id
                        WHERE ua.status = %s
                        ORDER BY action_date DESC, ua.id DESC
                        LIMIT %s OFFSET %s
                    """, (status, limit, offset))
                    
                    rows = await cursor.fetchall()
                    attachments = [dict(row) for row in rows]
                    
                    return attachments, total_count
        except Exception as e:
            logger.error(f"Error getting attachments by status {status}: {e}")
            return [], 0

    async def get_users_for_notification(self, event_types: list, mode: str) -> set:
        """
        دریافت کاربران فعال برای نوتیفیکیشن بر اساس تنظیمات (Optimized SQL)
        
        Args:
            event_types: لیست انواع رویدادها (مثلا add_attachment, edit_name)
            mode: مود بازی (br/mp)
            
        Returns:
            مجموعه‌ای از user_id ها
        """
        query = """
            SELECT s.user_id
            FROM subscribers s
            LEFT JOIN user_notification_preferences up ON s.user_id = up.user_id
            WHERE 
                s.is_active = TRUE
                AND (
                    -- 1. کاربر تنظیمات خاصی ندارد (پیش‌فرض فعال)
                    up.user_id IS NULL
                    OR
                    (
                        -- 2. کلید کلی فعال بودن
                        up.enabled = true
                        AND
                        -- 3. چک کردن مود بازی در JSONB
                        up.modes @> to_jsonb(%s::text)
                        AND
                        -- 4. چک کردن رویدادها
                        (
                            -- اگر آبجکت رویدادها خالی است، همه فعال در نظر گرفته می‌شوند
                            up.events IS NULL OR up.events = '{}'::jsonb
                            OR
                            EXISTS (
                                SELECT 1
                                FROM jsonb_each_text(up.events)
                                WHERE key = ANY(%s) AND value::boolean = true
                            )
                            OR
                            -- رویدادهایی که در آبجکت نیستند هم پیش‌فرض فعال در نظر گرفته می‌شوند
                            EXISTS (
                                SELECT 1
                                FROM unnest(%s::text[]) as req_event
                                WHERE NOT (up.events ? req_event)
                            )
                        )
                    )
                )
        """
        try:
            results = await self.execute_query(query, (mode, event_types, event_types), fetch_all=True)
            return {row['user_id'] for row in results}
        except Exception as e:
            logger.error(f'Error fetching notification users: {e}')
            return set()

    # ========== User Management Methods ==========

    async def get_users_paginated(self, page: int = 1, limit: int = 10,
                                   search: str = None, sort_by: str = 'created_at',
                                   is_banned: bool = None) -> List[Dict]:
        """دریافت لیست کاربران با صفحه‌بندی، جستجو و فیلتر"""
        offset = (page - 1) * limit
        ALLOWED_SORTS = {'created_at', 'last_seen', 'username', 'user_id'}
        if sort_by not in ALLOWED_SORTS:
            sort_by = 'created_at'

        try:
            conditions = []
            params = []

            if search:
                conditions.append(
                    "(CAST(u.user_id AS TEXT) LIKE %s OR u.username ILIKE %s OR u.first_name ILIKE %s)"
                )
                like = f"%{search}%"
                params.extend([like, like, like])

            if is_banned is True:
                conditions.append("u.is_banned = TRUE")
            elif is_banned is False:
                conditions.append("(u.is_banned = FALSE OR u.is_banned IS NULL)")

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params.extend([limit, offset])

            query = f"""
                SELECT u.user_id, u.username, u.first_name, u.last_name,
                       u.language, u.is_banned, u.ban_reason,
                       u.last_seen, u.created_at
                FROM users u
                {where}
                ORDER BY u.{sort_by} DESC NULLS LAST
                LIMIT %s OFFSET %s
            """
            results = await self.execute_query(query, tuple(params), fetch_all=True)
            return [dict(r) for r in results] if results else []
        except Exception as e:
            log_exception(logger, e, "get_users_paginated")
            return []

    async def get_users_count(self, search: str = None, is_banned: bool = None) -> int:
        """تعداد کل کاربران با فیلتر"""
        try:
            conditions = []
            params = []

            if search:
                conditions.append(
                    "(CAST(user_id AS TEXT) LIKE %s OR username ILIKE %s OR first_name ILIKE %s)"
                )
                like = f"%{search}%"
                params.extend([like, like, like])

            if is_banned is True:
                conditions.append("is_banned = TRUE")
            elif is_banned is False:
                conditions.append("(is_banned = FALSE OR is_banned IS NULL)")

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            query = f"SELECT COUNT(*) as count FROM users {where}"
            result = await self.execute_query(query, tuple(params), fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            log_exception(logger, e, "get_users_count")
            return 0

    async def get_user_detailed(self, user_id: int) -> Optional[Dict]:
        """دریافت اطلاعات کامل یک کاربر"""
        try:
            query = """
                SELECT u.user_id, u.username, u.first_name, u.last_name,
                       u.language, u.is_banned, u.ban_reason, u.banned_until,
                       u.last_seen, u.created_at, u.updated_at,
                       COALESCE(uss.total_submissions, 0) as total_submissions,
                       COALESCE(uss.approved_count, 0) as approved_count,
                       COALESCE(uss.rejected_count, 0) as rejected_count,
                       COALESCE(uss.pending_count, 0) as pending_count,
                       COALESCE(uss.is_banned, FALSE) as submission_banned,
                       (SELECT COUNT(*) FROM subscribers s WHERE s.user_id = u.user_id AND s.is_active = TRUE) as is_subscribed
                FROM users u
                LEFT JOIN user_submission_stats uss ON u.user_id = uss.user_id
                WHERE u.user_id = %s
            """
            result = await self.execute_query(query, (user_id,), fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            log_exception(logger, e, f"get_user_detailed({user_id})")
            return None

    async def ban_user(self, user_id: int, reason: str = None) -> bool:
        """بن کردن کاربر از ربات"""
        try:
            query = """
                UPDATE users
                SET is_banned = TRUE, ban_reason = %s, updated_at = NOW()
                WHERE user_id = %s
            """
            await self.execute_query(query, (reason, user_id))
            logger.warning(f"⚠️ User {user_id} banned: {reason}")
            return True
        except Exception as e:
            log_exception(logger, e, f"ban_user({user_id})")
            return False

    async def unban_user(self, user_id: int) -> bool:
        """آنبن کردن کاربر"""
        try:
            query = """
                UPDATE users
                SET is_banned = FALSE, ban_reason = NULL, banned_until = NULL, updated_at = NOW()
                WHERE user_id = %s
            """
            await self.execute_query(query, (user_id,))
            logger.info(f"✅ User {user_id} unbanned")
            return True
        except Exception as e:
            log_exception(logger, e, f"unban_user({user_id})")
            return False

    async def get_users_stats(self) -> Dict:
        """آمار کلی کاربران"""
        try:
            query = """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as new_today,
                    COUNT(*) FILTER (WHERE last_seen >= NOW() - INTERVAL '7 days') as active_week,
                    COUNT(*) FILTER (WHERE last_seen >= NOW() - INTERVAL '24 hours') as active_today,
                    COUNT(*) FILTER (WHERE is_banned = TRUE) as banned
                FROM users
            """
            result = await self.execute_query(query, fetch_one=True)
            if result:
                return dict(result)
            return {'total': 0, 'new_today': 0, 'active_week': 0, 'active_today': 0, 'banned': 0}
        except Exception as e:
            log_exception(logger, e, "get_users_stats")
            return {'total': 0, 'new_today': 0, 'active_week': 0, 'active_today': 0, 'banned': 0}
