"""
Database mixin for User and Role management.
"""

import logging
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.user_mixin')


class UserDatabaseMixin:
    """
    Mixin containing user and role related database operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    def get_user(self, user_id: int) -> Optional[Dict]:
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
            return self.execute_query(query, (user_id,), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f"get_user({user_id})")
            return None

    def get_user_language(self, user_id: int) -> Optional[str]:
        """
        دریافت زبان کاربر از جدول users
        Returns: 'fa' | 'en' | None
        """
        try:
            query = "SELECT language FROM users WHERE user_id = %s"
            result = self.execute_query(query, (user_id,), fetch_one=True)
            if result:
                return result.get('language')
            return None
        except Exception as e:
            log_exception(logger, e, f"get_user_language({user_id})")
            return None

    def set_user_language(self, user_id: int, lang: str) -> bool:
        """
        تنظیم زبان کاربر در جدول users (fa/en)
        اگر کاربر وجود نداشت، ساخته می‌شود.
        """
        if lang not in ('fa', 'en'):
            logger.error(f"Invalid language: {lang}")
            return False
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO users (user_id, language)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET language = EXCLUDED.language
                    """,
                    (user_id, lang)
                )
                cursor.close()
                logger.info(f"✅ Language set: user={user_id}, lang={lang}")
                return True
        except Exception as e:
            log_exception(logger, e, f"set_user_language({user_id}, {lang})")
            return False

    def unban_user_from_attachments(self, user_id: int) -> bool:
        """
        رفع محرومیت کاربر از ارسال اتچمنت‌ها
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE user_submission_stats
                    SET is_banned = FALSE, updated_at = NOW()
                    WHERE user_id = %s AND is_banned = TRUE
                    """,
                    (user_id,),
                )
                affected = getattr(cursor, 'rowcount', None)
                cursor.close()
                if affected is not None and affected == 0:
                    logger.warning(f"No banned record found to unban for user_id={user_id}")
                    return False
            logger.info(f"✅ User unbanned from attachments: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"unban_user_from_attachments({user_id})")
            return False

    def create_role_if_not_exists(self, role_name: str, display_name: str, 
                                   description: str = '', icon: str = '', 
                                   permissions: List[str] = None) -> bool:
        """ایجاد role اگر وجود نداشته باشد"""
        permissions = permissions or []
        
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                # بررسی وجود role
                query_check = "SELECT id FROM roles WHERE name = %s"
                cursor.execute(query_check, (role_name,))
                result = cursor.fetchone()
                
                if result:
                    role_id = result['id']
                    # Update existing role
                    query_update = """
                        UPDATE roles 
                        SET display_name = %s, description = %s, icon = %s
                        WHERE id = %s
                    """
                    cursor.execute(query_update, (display_name, description, icon, role_id))
                else:
                    # Insert new role
                    query_insert = """
                        INSERT INTO roles (name, display_name, description, icon, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        RETURNING id
                    """
                    cursor.execute(query_insert, (role_name, display_name, description, icon))
                    result = cursor.fetchone()
                    role_id = result['id']
                
                # حذف permissions قدیمی
                query_delete = "DELETE FROM role_permissions WHERE role_id = %s"
                cursor.execute(query_delete, (role_id,))
                # اضافه کردن permissions جدید
                for perm in permissions:
                    query_perm = """
                        INSERT INTO role_permissions (role_id, permission)
                        VALUES (%s, %s)
                    """
                    cursor.execute(query_perm, (role_id, perm))
                
                cursor.close()
                logger.info(f"✅ Role created/updated: {role_name}")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"create_role_if_not_exists({role_name})")
            return False

    def get_all_users(self) -> List[int]:
        """دریافت لیست همه کاربران"""
        try:
            query = "SELECT user_id FROM users WHERE is_subscriber = TRUE"
            results = self.execute_query(query, fetch_all=True)
            return [row['user_id'] for row in results]
        except Exception as e:
            log_exception(logger, e, "get_all_users")
            return []
    
    def get_all_admins(self) -> List[Dict]:
        """دریافت لیست همه ادمین‌ها"""
        try:
            # Pre-check schema for created_at column to avoid exception logs
            exists_row = self.execute_query(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='admins' AND column_name='created_at') AS has_created",
                fetch_one=True,
            )
            has_created = exists_row.get('has_created') if exists_row else False

            if has_created:
                query = """
                    SELECT 
                      a.user_id,
                      COALESCE(a.added_at, a.created_at) AS added_at,
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
                    ORDER BY COALESCE(a.added_at, a.created_at) DESC
                """
            else:
                query = """
                    SELECT 
                      a.user_id,
                      a.added_at AS added_at,
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
                    ORDER BY a.added_at DESC
                """

            rows = self.execute_query(query, fetch_all=True) or []
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
    
    def get_admins_count(self) -> int:
        """تعداد ادمین‌ها"""
        try:
            query = "SELECT COUNT(*) as count FROM admins"
            result = self.execute_query(query, fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            log_exception(logger, e, "get_admins_count")
            return 0

    def remove_admin(self, user_id: int) -> bool:
        """حذف کامل ادمین (تمام نقش‌هایش)"""
        try:
            query = "DELETE FROM admins WHERE user_id = %s"
            self.execute_query(query, (user_id,))
            logger.info(f"✅ Admin {user_id} and all roles removed (PostgreSQL)")
            return True
        except Exception as e:
            log_exception(logger, e, f"remove_admin({user_id})")
            return False
    
    def assign_role_to_admin(self, user_id: int, role_name: str,
                            username: str = None, first_name: str = None,
                            display_name: str = None, added_by: int = None) -> bool:
        """اختصاص نقش به ادمین"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                from psycopg.errors import UniqueViolation
                
                # دریافت role_id
                cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                role = cursor.fetchone()
                
                if not role:
                    cursor.close()
                    logger.error(f"❌ Role {role_name} not found")
                    return False
                
                role_id = role.get('id')
                
                # اضافه کردن ادمین اگر وجود ندارد
                cursor.execute("""
                    INSERT INTO admins (user_id, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id, display_name))
                
                if display_name:
                    cursor.execute("""
                        UPDATE admins 
                        SET display_name = %s
                        WHERE user_id = %s
                    """, (display_name, user_id))
                
                try:
                    cursor.execute(
                        """
                        INSERT INTO admin_roles (user_id, role_id)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id, role_id) DO NOTHING
                        """,
                        (user_id, role_id),
                    )
                except UniqueViolation:
                    cursor.execute(
                        "SELECT 1 FROM admin_roles WHERE user_id = %s AND role_id = %s",
                        (user_id, role_id),
                    )
                    if cursor.fetchone() is None:
                        try:
                            cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name='admin_roles' AND column_name='id'")
                            if cursor.fetchone():
                                try: cursor.execute("ALTER TABLE admin_roles DROP CONSTRAINT IF EXISTS admin_roles_pkey")
                                except Exception: pass
                                try: cursor.execute("ALTER TABLE admin_roles DROP COLUMN IF EXISTS id")
                                except Exception: pass
                                try: cursor.execute("ALTER TABLE admin_roles ADD PRIMARY KEY (user_id, role_id)")
                                except Exception: pass
                                try:
                                    cursor.execute(
                                        """
                                        INSERT INTO admin_roles (user_id, role_id)
                                        VALUES (%s, %s)
                                        ON CONFLICT (user_id, role_id) DO NOTHING
                                        """,
                                        (user_id, role_id),
                                    )
                                except Exception: pass
                        except Exception: pass
                
                cursor.close()
                logger.info(f"✅ Admin {user_id} assigned role {role_name} (PostgreSQL)")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"assign_role_to_admin({user_id}, {role_name})")
            return False
    
    def remove_role_from_admin(self, user_id: int, role_name: str) -> bool:
        """حذف یک نقش خاص از ادمین"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
                role = cursor.fetchone()
                
                if not role:
                    cursor.close()
                    logger.error(f"❌ Role {role_name} not found")
                    return False
                
                role_id = role.get('id')
                
                cursor.execute("""
                    DELETE FROM admin_roles 
                    WHERE user_id = %s AND role_id = %s
                """, (user_id, role_id))
                
                cursor.close()
                logger.info(f"✅ Role {role_name} removed from admin {user_id} (PostgreSQL)")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"remove_role_from_admin({user_id}, {role_name})")
            return False
    
    def get_admin_roles(self, user_id: int) -> List[str]:
        """دریافت لیست نام نقش‌های یک ادمین"""
        try:
            query = """
                SELECT r.name
                FROM admin_roles ar
                JOIN roles r ON ar.role_id = r.id
                WHERE ar.user_id = %s
                ORDER BY r.name
            """
            results = self.execute_query(query, (user_id,), fetch_all=True)
            return [row['name'] for row in results]
        except Exception as e:
            log_exception(logger, e, f"get_admin_roles({user_id})")
            return []

    def get_all_roles(self) -> List[Dict]:
        """دریافت تمام نقش‌ها با permissions"""
        try:
            query_roles = """
                SELECT id, name, display_name, description, icon
                FROM roles
                ORDER BY name
            """
            roles = self.execute_query(query_roles, fetch_all=True)
            
            result = []
            for role in roles:
                query_perms = """
                    SELECT permission
                    FROM role_permissions
                    WHERE role_id = %s
                """
                permissions = self.execute_query(query_perms, (role['id'],), fetch_all=True)
                
                result.append({
                    'name': role['name'],
                    'display_name': role['display_name'],
                    'description': role['description'],
                    'icon': role['icon'],
                    'permissions': [p['permission'] for p in permissions]
                })
            
            return result
            
        except Exception as e:
            log_exception(logger, e, "get_all_roles")
            return []
    
    def get_role(self, role_name: str) -> Optional[Dict]:
        """دریافت اطلاعات یک نقش"""
        try:
            query_role = """
                SELECT id, name, display_name, description, icon
                FROM roles
                WHERE name = %s
            """
            role = self.execute_query(query_role, (role_name,), fetch_one=True)
            
            if not role:
                return None
            
            query_perms = """
                SELECT permission
                FROM role_permissions
                WHERE role_id = %s
            """
            permissions = self.execute_query(query_perms, (role['id'],), fetch_all=True)
            
            return {
                'name': role['name'],
                'display_name': role['display_name'],
                'description': role['description'],
                'icon': role['icon'],
                'permissions': [p['permission'] for p in permissions]
            }
            
        except Exception as e:
            log_exception(logger, e, f"get_role({role_name})")
            return None
    
    def ban_user_from_submissions(self, user_id: int, reason: str, 
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
            self.execute_query(query, (reason, user_id))
            logger.warning(f"⚠️ User {user_id} banned from submissions: {reason}")
            return True
        except Exception as e:
            log_exception(logger, e, f"ban_user_from_submissions({user_id})")
            return False
    
    def unban_user_from_submissions(self, user_id: int) -> bool:
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
            self.execute_query(query, (user_id,))
            logger.info(f"✅ User {user_id} unbanned from submissions")
            return True
        except Exception as e:
            log_exception(logger, e, f"unban_user_from_submissions({user_id})")
            return False

    def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر - CRITICAL"""
        try:
            query = "SELECT 1 FROM admins WHERE user_id = %s LIMIT 1"
            result = self.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            log_exception(logger, e, f"is_admin({user_id})")
            return False
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
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
            self.execute_query(query, (user_id, username, first_name))
            logger.debug(f"✅ User added: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"add_user({user_id})")
            return False
    
    def upsert_user(self, user_id: int, username: str = None,
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
            self.execute_query(query, (user_id, username, first_name))
            logger.debug(f"✅ User upserted: {user_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"upsert_user({user_id})")
            return False
    
    def get_admin(self, user_id: int) -> Optional[Dict]:
        """دریافت اطلاعات ادمین"""
        try:
            query = """
                SELECT a.*, u.username, u.first_name
                FROM admins a
                LEFT JOIN users u ON a.user_id = u.user_id
                WHERE a.user_id = %s
            """
            result = self.execute_query(query, (user_id,), fetch_one=True)
            
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
            roles = self.execute_query(q_roles, (user_id,), fetch_all=True) or []
            admin['roles'] = roles
            return admin
        except Exception as e:
            log_exception(logger, e, f"get_admin({user_id})")
            return None
    
    def get_user_display_name(self, user_id: int) -> str:
        """دریافت نام نمایشی کاربر"""
        try:
            query = """
                SELECT username, first_name
                FROM users
                WHERE user_id = %s
            """
            result = self.execute_query(query, (user_id,), fetch_one=True)
            
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
    
    def add_user_attachment(self, user_id: int, weapon_id: int = None, mode: str = None,
                           category: str = None, custom_weapon_name: str = None,
                           attachment_name: str = None, image_file_id: str = None,
                           description: str = None) -> Optional[int]:
        """افزودن اتچمنت کاربر"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO user_attachments (
                        user_id, weapon_id, mode, category, custom_weapon_name,
                        attachment_name, image_file_id, description, status, submitted_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                    RETURNING id
                """, (user_id, weapon_id, mode, category, custom_weapon_name,
                      attachment_name, image_file_id, description))
                
                result = cursor.fetchone()
                attachment_id = result['id']
                cursor.close()
                
                logger.info(f"✅ User attachment added: ID={attachment_id}")
                return attachment_id
        except Exception as e:
            log_exception(logger, e, "add_user_attachment")
            return None
    
    def get_user_attachment(self, attachment_id: int) -> Optional[Dict]:
        """دریافت اتچمنت کاربر"""
        try:
            query = """
                SELECT ua.*, u.username, u.first_name
                FROM user_attachments ua
                LEFT JOIN users u ON ua.user_id = u.user_id
                WHERE ua.id = %s
            """
            result = self.execute_query(query, (attachment_id,), fetch_one=True)
            
            if result:
                data = dict(result)
                data['weapon_name'] = data.get('custom_weapon_name', 'نامشخص')
                data['category_name'] = data.get('category', 'نامشخص')
                return data
            return None
        except Exception as e:
            log_exception(logger, e, f"get_user_attachment({attachment_id})")
            return None
    
    def get_user_attachments_by_status(self, status: str = 'pending',
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
            results = self.execute_query(query, (status, limit, offset), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, f"get_user_attachments_by_status({status})")
            return []
    
    def approve_user_attachment(self, attachment_id: int, admin_id: int) -> bool:
        """تایید اتچمنت کاربر"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT user_id FROM user_attachments WHERE id = %s
                """, (attachment_id,))
                
                row = cursor.fetchone()
                if not row:
                    cursor.close()
                    return False
                
                user_id = row['user_id']
                
                cursor.execute("""
                    UPDATE user_attachments
                    SET status = 'approved',
                        approved_at = NOW(),
                        approved_by = %s
                    WHERE id = %s
                """, (admin_id, attachment_id))
                
                cursor.execute("""
                    UPDATE user_submission_stats
                    SET approved_count = approved_count + 1
                    WHERE user_id = %s
                """, (user_id,))
                
                cursor.close()
                logger.info(f"✅ User attachment {attachment_id} approved")
                return True
        except Exception as e:
            log_exception(logger, e, f"approve_user_attachment({attachment_id})")
            return False
    
    def reject_user_attachment(self, attachment_id: int, admin_id: int, reason: str) -> bool:
        """رد اتچمنت کاربر"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT user_id FROM user_attachments WHERE id = %s
                """, (attachment_id,))
                
                row = cursor.fetchone()
                if not row:
                    cursor.close()
                    return False
                
                user_id = row['user_id']
                
                cursor.execute("""
                    UPDATE user_attachments
                    SET status = 'rejected',
                        rejected_at = NOW(),
                        rejected_by = %s,
                        rejection_reason = %s
                    WHERE id = %s
                """, (admin_id, reason, attachment_id))
                
                cursor.execute("""
                    UPDATE user_submission_stats
                    SET rejected_count = rejected_count + 1
                    WHERE user_id = %s
                """, (user_id,))
                
                cursor.close()
                logger.info(f"✅ User attachment {attachment_id} rejected")
                return True
        except Exception as e:
            log_exception(logger, e, f"reject_user_attachment({attachment_id})")
            return False

    def delete_user_attachment(self, attachment_id: int, deleted_by: int = None) -> bool:
        """حذف اتچمنت کاربر (Soft Delete)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, status FROM user_attachments WHERE id = %s", (attachment_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                user_id = result['user_id']
                status = result['status']
                
                if status == 'deleted':
                    return True
                
                cursor.execute("""
                    UPDATE user_attachments
                    SET status = 'deleted',
                        deleted_at = NOW(),
                        deleted_by = %s
                    WHERE id = %s
                """, (deleted_by, attachment_id))
                
                if status == 'approved':
                    cursor.execute("""
                        UPDATE user_submission_stats
                        SET approved_count = GREATEST(0, approved_count - 1),
                            deleted_count = deleted_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                elif status == 'rejected':
                    cursor.execute("""
                        UPDATE user_submission_stats
                        SET rejected_count = GREATEST(0, rejected_count - 1),
                            deleted_count = deleted_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                elif status == 'pending':
                    cursor.execute("""
                        UPDATE user_submission_stats
                        SET pending_count = GREATEST(0, pending_count - 1),
                            deleted_count = deleted_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE user_submission_stats
                        SET deleted_count = deleted_count + 1
                        WHERE user_id = %s
                    """, (user_id,))
                
                conn.commit()
                logger.info(f"✅ User attachment {attachment_id} soft-deleted (Status: {status})")
                return True
        except Exception as e:
            logger.error(f"Error soft-deleting user attachment: {e}")
            return False

    def restore_user_attachment(self, attachment_id: int) -> bool:
        """بازگردانی اتچمنت به وضعیت pending"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, status FROM user_attachments WHERE id = %s", (attachment_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                user_id = result['user_id']
                status = result['status']
                
                if status == 'pending':
                    return True
                
                cursor.execute("""
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
                    cursor.execute("UPDATE user_submission_stats SET approved_count = GREATEST(0, approved_count - 1) WHERE user_id = %s", (user_id,))
                elif status == 'rejected':
                    cursor.execute("UPDATE user_submission_stats SET rejected_count = GREATEST(0, rejected_count - 1) WHERE user_id = %s", (user_id,))
                elif status == 'deleted':
                    cursor.execute("UPDATE user_submission_stats SET deleted_count = GREATEST(0, deleted_count - 1) WHERE user_id = %s", (user_id,))
                
                cursor.execute("UPDATE user_submission_stats SET pending_count = pending_count + 1 WHERE user_id = %s", (user_id,))
                
                conn.commit()
                logger.info(f"✅ User attachment {attachment_id} restored to pending")
                return True
        except Exception as e:
            logger.error(f"Error restoring user attachment: {e}")
            return False

    def get_attachments_by_status(self, status: str, page: int = 1, limit: int = 10) -> tuple[list[dict], int]:
        """دریافت لیست اتچمنت‌ها بر اساس وضعیت با صفحه‌بندی"""
        offset = (page - 1) * limit
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) as count FROM user_attachments WHERE status = %s", (status,))
                result = cursor.fetchone()
                total_count = result['count'] if result else 0
                
                cursor.execute("""
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
                
                rows = cursor.fetchall()
                attachments = [dict(row) for row in rows]
                
                return attachments, total_count
        except Exception as e:
            logger.error(f"Error getting attachments by status {status}: {e}")
            return [], 0
