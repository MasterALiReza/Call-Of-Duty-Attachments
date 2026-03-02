from core.context import CustomContext
"""
سیستم مدیریت نقش\u200cها و دسترسی\u200cها (RBAC - Role-Based Access Control)
این سیستم امکان تعریف نقش\u200cهای مختلف برای ادمین\u200cها و محدودسازی دسترسی آن\u200cها را فراهم می\u200cکند.
"""
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging
from core.cache.cache_manager import get_cache
logger = logging.getLogger(__name__)
_role_manager_instance = None

def get_role_manager(db=None):
    """دریافت singleton instance از RoleManager"""
    global _role_manager_instance
    if _role_manager_instance is None and db is not None:
        _role_manager_instance = RoleManager(db)
    return _role_manager_instance

class Permission(str, Enum):
    """دسترسی‌های مختلف سیستم"""
    # ─── محتوا و اتچمنت ───
    MANAGE_ATTACHMENTS_BR = 'manage_attachments_br'
    MANAGE_ATTACHMENTS_MP = 'manage_attachments_mp'
    MANAGE_SUGGESTED_ATTACHMENTS = 'manage_suggested_attachments'
    MANAGE_USER_ATTACHMENTS = 'manage_user_attachments'
    MANAGE_CATEGORIES = 'manage_categories'
    MANAGE_TEXTS = 'manage_texts'
    # ─── کاربران و ادمین‌ها ───
    MANAGE_ADMINS = 'manage_admins'
    MANAGE_USERS = 'manage_users'
    # ─── آمار و تحلیل ───
    VIEW_ANALYTICS = 'view_analytics'
    VIEW_FEEDBACK = 'view_feedback'
    # ─── اطلاعیه‌ها ───
    SEND_NOTIFICATIONS = 'send_notifications'
    MANAGE_NOTIFICATION_SETTINGS = 'manage_notification_settings'
    MANAGE_SCHEDULED_NOTIFICATIONS = 'manage_scheduled_notifications'
    # ─── پشتیبانی ───
    MANAGE_TICKETS = 'manage_tickets'
    MANAGE_FAQS = 'manage_faqs'
    # ─── داده و سیستم ───
    BACKUP_DATA = 'backup_data'
    IMPORT_EXPORT = 'import_export'
    MANAGE_SETTINGS = 'manage_settings'

@dataclass
class Role:
    """تعریف یک نقش با دسترسی\u200cهای مشخص"""
    name: str
    display_name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    icon: str = '👤'

    def has_permission(self, permission: Permission) -> bool:
        """بررسی وجود دسترسی"""
        return permission in self.permissions

    def add_permission(self, permission: Permission):
        """اضافه کردن دسترسی"""
        self.permissions.add(permission)

    def remove_permission(self, permission: Permission):
        """حذف دسترسی"""
        self.permissions.discard(permission)

class RoleManager:
    """مدیریت نقش\u200cها و دسترسی\u200cها"""
    _initialized = False
    PREDEFINED_ROLES = {
        'super_admin': Role(
            name='super_admin',
            display_name='👑 ادمین کل',
            description='دسترسی کامل به تمام بخش‌ها',
            icon='👑',
            permissions={
                Permission.MANAGE_ATTACHMENTS_BR, Permission.MANAGE_ATTACHMENTS_MP,
                Permission.MANAGE_SUGGESTED_ATTACHMENTS, Permission.MANAGE_USER_ATTACHMENTS,
                Permission.MANAGE_CATEGORIES, Permission.MANAGE_TEXTS,
                Permission.MANAGE_ADMINS, Permission.MANAGE_USERS,
                Permission.VIEW_ANALYTICS, Permission.VIEW_FEEDBACK,
                Permission.SEND_NOTIFICATIONS, Permission.MANAGE_NOTIFICATION_SETTINGS,
                Permission.MANAGE_SCHEDULED_NOTIFICATIONS,
                Permission.MANAGE_TICKETS, Permission.MANAGE_FAQS,
                Permission.BACKUP_DATA, Permission.IMPORT_EXPORT,
                Permission.MANAGE_SETTINGS,
            }
        ),
        'content_admin': Role(
            name='content_admin',
            display_name='📎 ادمین محتوا',
            description='مدیریت اتچمنت‌ها، پیشنهادی‌ها، متون و اطلاعیه‌ها',
            icon='📎',
            permissions={
                Permission.MANAGE_ATTACHMENTS_BR, Permission.MANAGE_ATTACHMENTS_MP,
                Permission.MANAGE_SUGGESTED_ATTACHMENTS, Permission.MANAGE_USER_ATTACHMENTS,
                Permission.MANAGE_CATEGORIES, Permission.MANAGE_TEXTS,
                Permission.SEND_NOTIFICATIONS, Permission.MANAGE_SCHEDULED_NOTIFICATIONS,
                Permission.MANAGE_NOTIFICATION_SETTINGS,
            }
        ),
        'ua_moderator': Role(
            name='ua_moderator',
            display_name='🎮 ادمین اتچمنت کاربران',
            description='بررسی، تایید و رد اتچمنت‌های ارسالی کاربران',
            icon='🎮',
            permissions={
                Permission.MANAGE_USER_ATTACHMENTS,
            }
        ),
        'support_admin': Role(
            name='support_admin',
            display_name='🎧 ادمین پشتیبانی',
            description='مدیریت تیکت‌ها، FAQ، بازخوردها و کاربران',
            icon='🎧',
            permissions={
                Permission.MANAGE_TICKETS, Permission.MANAGE_FAQS,
                Permission.VIEW_FEEDBACK, Permission.MANAGE_USERS,
            }
        ),
        'data_admin': Role(
            name='data_admin',
            display_name='💾 ادمین داده',
            description='بکاپ‌گیری، Import/Export و مشاهده آمار',
            icon='💾',
            permissions={
                Permission.BACKUP_DATA, Permission.IMPORT_EXPORT,
                Permission.VIEW_ANALYTICS,
            }
        ),
    }

    def __init__(self, db):
        """
        Args:
            db: شیء DatabaseSQL برای مدیریت دیتابیس
        """
        self.db = db
        self._roles_cache = None
        self.cache = get_cache()

    async def initialize(self):
        """Must be called to load roles and initialize admin"""
        if not RoleManager._initialized:
            await self._init_predefined_roles()
            RoleManager._initialized = True
            logger.info('✅ RoleManager initialized (first time only)')

    async def _init_predefined_roles(self):
        """ایجاد/به‌روزرسانی نقش‌های پیش‌فرض در دیتابیس و حذف نقش‌های منسوخ"""
        # ─── 1. upsert همه نقش‌های جدید (با permissions به‌روز) ───
        for role_name, role in self.PREDEFINED_ROLES.items():
            await self.db.create_role_if_not_exists(
                role_name=role.name,
                display_name=role.display_name,
                description=role.description,
                icon=role.icon,
                permissions=[p.value for p in role.permissions]
            )

        # ─── 2. حذف نقش‌های قدیمی که دیگه در سیستم نیستند ───
        ALLOWED_ROLE_NAMES = set(self.PREDEFINED_ROLES.keys())
        try:
            # ابتدا لیست نقش‌های موجود در DB رو بگیر
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT id, name FROM roles")
                    all_db_roles = await cursor.fetchall()

            obsolete_roles = [row for row in all_db_roles if row.get('name') not in ALLOWED_ROLE_NAMES]

            if obsolete_roles:
                logger.info(f'🧹 Found {len(obsolete_roles)} obsolete roles to purge: {[r["name"] for r in obsolete_roles]}')
                for row in obsolete_roles:
                    r_name = row.get('name')
                    r_id = row.get('id')
                    try:
                        # استفاده از transaction() که auto-commit دارد
                        async with self.db.transaction() as conn:
                            async with conn.cursor() as cursor:
                                await cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (r_id,))
                                await cursor.execute("DELETE FROM admin_roles WHERE role_id = %s", (r_id,))
                                await cursor.execute("DELETE FROM roles WHERE id = %s", (r_id,))
                        logger.info(f'🗑️ Removed obsolete role from DB: {r_name}')
                    except Exception as e:
                        logger.warning(f'⚠️ Could not remove role "{r_name}": {e}')

                # Invalidate cache so get_all_roles() re-fetches from DB
                self._roles_cache = None
                logger.info('✅ Roles cache invalidated after cleanup')
            else:
                logger.info('✅ No obsolete roles found in DB')
        except Exception as e:
            logger.warning(f'⚠️ Could not clean up old roles: {e}')

        # ─── 3. مطمئن شدن از super_admin اصلی ───
        from config.config import SUPER_ADMIN_ID
        if SUPER_ADMIN_ID:
            await self.db.assign_role_to_admin(user_id=SUPER_ADMIN_ID, role_name='super_admin', display_name='Super Admin', added_by=SUPER_ADMIN_ID)
            logger.info(f'✅ Ensured SUPER_ADMIN_ID ({SUPER_ADMIN_ID}) has super_admin role.')

    async def get_role(self, role_name: str) -> Optional[Role]:
        """دریافت اطلاعات یک نقش"""
        if self._roles_cache is None:
            _ = await self.get_all_roles()
        if self._roles_cache:
            for r in self._roles_cache:
                if r.name == role_name:
                    return r
        role_data = await self.db.get_role(role_name)
        if not role_data:
            return None
        return Role(name=role_data['name'], display_name=role_data['display_name'], description=role_data['description'], icon=role_data.get('icon') or '👤', permissions={
            Permission(p) for p in role_data['permissions']
            if p in Permission._value2member_map_
        })

    async def get_all_roles(self) -> List[Role]:
        """
        دریافت تمام نقش\u200cها (با cache)
        
        Performance: Role definitions تقریباً هیچوقت تغییر نمی\u200cکنند،
        پس یکبار load می\u200cکنیم و cache می\u200cکنیم.
        """
        if self._roles_cache is None:
            roles_data = await self.db.get_all_roles()
            def _safe_perms(perms):
                valid = []
                for p in perms:
                    try:
                        valid.append(Permission(p))
                    except ValueError:
                        logger.warning(f'⚠️ Skipping unknown permission in DB: "{p}"')
                return set(valid)
            self._roles_cache = [Role(
                name=r['name'],
                display_name=r['display_name'],
                description=r['description'],
                icon=r.get('icon') or '👤',
                permissions=_safe_perms(r['permissions'])
            ) for r in roles_data]
            logger.info(f'📦 Loaded {len(self._roles_cache)} role definitions into cache')
        return self._roles_cache

    async def assign_role(self, user_id: int, role_name: str) -> bool:
        """اختصاص نقش به کاربر"""
        role = await self.get_role(role_name)
        if not role:
            logger.error(f'نقش {role_name} یافت نشد')
            return False
        return await self.db.assign_role_to_admin(user_id, role_name)

    async def remove_role(self, user_id: int) -> bool:
        """حذف نقش کاربر"""
        return await self.db.remove_admin(user_id)

    async def get_user_role(self, user_id: int) -> Optional[Role]:
        """دریافت اولین نقش کاربر (backward compatibility)"""
        admin_data = await self.db.get_admin(user_id)
        if not admin_data:
            return None
        return await self.get_role(admin_data['role_name'])

    async def get_user_roles(self, user_id: int) -> List[Role]:
        """دریافت تمام نقش\u200cهای کاربر (با cache کوتاه\u200cمدت)"""
        cache_key = f'user_roles_{user_id}'
        cached_roles = await self.cache.get(cache_key)
        if cached_roles is not None:
            return cached_roles
        try:
            role_names = await self.db.get_admin_roles(user_id)
        except Exception as e:
            logger.error(f'Error loading roles for user {user_id}: {e}')
            role_names = []
        if not role_names:
            roles: List[Role] = []
            await self.cache.set(cache_key, roles, ttl=120)
            return roles
        roles: List[Role] = []
        for role_name in role_names:
            role = await self.get_role(role_name)
            if role:
                roles.append(role)
        await self.cache.set(cache_key, roles, ttl=120)
        return roles

    async def has_permission(self, user_id: int, permission: Permission) -> bool:
        """بررسی دسترسی کاربر (از تمام نقش\u200cها)"""
        roles = await self.get_user_roles(user_id)
        if not roles:
            return False
        return any((role.has_permission(permission) for role in roles))

    async def get_user_permissions(self, user_id: int) -> Set[Permission]:
        """دریافت تمام دسترسی\u200cهای کاربر (ترکیب از تمام نقش\u200cها) با cache کوتاه\u200cمدت"""
        cache_key = f'user_perms_{user_id}'
        cached_perms = await self.cache.get(cache_key)
        if cached_perms is not None:
            return cached_perms
        roles = await self.get_user_roles(user_id)
        if not roles:
            perms: Set[Permission] = set()
            await self.cache.set(cache_key, perms, ttl=120)
            return perms
        all_permissions: Set[Permission] = set()
        for role in roles:
            all_permissions.update(role.permissions)
        await self.cache.set(cache_key, all_permissions, ttl=120)
        return all_permissions

    async def clear_user_cache(self, user_id: int):
        """پاک کردن cache دسترسی‌های یک کاربر"""
        await self.cache.delete(f'user_roles_{user_id}')
        await self.cache.delete(f'user_perms_{user_id}')
        logger.info(f'🧹 Cache cleared for user {user_id}')

    async def get_role_permissions(self, role_name: str) -> Set[Permission]:
        """
        دریافت دسترسی\u200cهای یک نقش (برای backward compatibility)
        
        Args:
            role_name: نام نقش (مثلاً 'super_admin', 'br_admin')
            
        Returns:
            Set of permissions for the role
        """
        role = await self.get_role(role_name)
        if role:
            return role.permissions
        return set()

    async def is_admin(self, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر ادمین است یا نه"""
        return await self.db.is_admin(user_id)

    async def is_super_admin(self, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر super admin است یا نه"""
        roles = await self.get_user_roles(user_id)
        return any(r.name == 'super_admin' for r in roles)

    async def get_admin_list(self) -> List[Dict]:
        """دریافت لیست تمام ادمین\u200cها"""
        return await self.db.get_all_admins()

    async def get_mode_permissions(self, user_id: int) -> List[str]:
        """
        دریافت لیست مودهایی که کاربر به آن\u200cها دسترسی دارد
        Returns: ['br', 'mp'] یا ['br'] یا ['mp'] یا []
        """
        permissions = await self.get_user_permissions(user_id)
        modes = []
        if Permission.MANAGE_ATTACHMENTS_BR in permissions:
            modes.append('br')
        if Permission.MANAGE_ATTACHMENTS_MP in permissions:
            modes.append('mp')
        return modes

def require_admin(func):
    """Decorator برای محدود کردن دسترسی به ادمین\u200cها"""

    @wraps(func)
    async def wrapper(self, update: Update, context: CustomContext, *args, **kwargs):
        user_id = update.effective_user.id
        if not hasattr(self, 'role_manager'):
            logger.error('role_manager not found in handler class')
            if update.callback_query:
                await update.callback_query.answer('❌ خطای سیستم', show_alert=True)
            else:
                await update.message.reply_text('❌ خطای سیستم')
            return None
        if not await self.role_manager.is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer('❌ شما دسترسی ادمین ندارید.', show_alert=True)
            else:
                await update.message.reply_text('❌ شما دسترسی ادمین ندارید.')
            return None
        return await func(self, update, context, *args, **kwargs)
    return wrapper

def require_permission(*required_permissions: Permission):
    """
    Decorator برای محدود کردن دسترسی به کاربران با دسترسی\u200cهای خاص
    
    Usage:
        @require_permission(Permission.MANAGE_ATTACHMENTS_BR)
        async def some_handler(self, update, context):
            ...
    """

    def decorator(func):

        @wraps(func)
        async def wrapper(self, update: Update, context: CustomContext, *args, **kwargs):
            user_id = update.effective_user.id
            if not hasattr(self, 'role_manager'):
                logger.error('role_manager not found in handler class')
                if update.callback_query:
                    await update.callback_query.answer('❌ خطای سیستم', show_alert=True)
                else:
                    await update.message.reply_text('❌ خطای سیستم')
                return None
            if not await self.role_manager.is_admin(user_id):
                if update.callback_query:
                    await update.callback_query.answer('❌ شما دسترسی ادمین ندارید.', show_alert=True)
                else:
                    await update.message.reply_text('❌ شما دسترسی ادمین ندارید.')
                return None
            user_permissions = await self.role_manager.get_user_permissions(user_id)
            if await self.role_manager.is_super_admin(user_id):
                return await func(self, update, context, *args, **kwargs)
            has_permission = any((perm in user_permissions for perm in required_permissions))
            if not has_permission:
                permission_names = [p.value for p in required_permissions]
                logger.warning(f'User {user_id} tried to access {func.__name__} without permission: {permission_names}')
                if update.callback_query:
                    await update.callback_query.answer('❌ شما دسترسی به این بخش را ندارید.', show_alert=True)
                else:
                    await update.message.reply_text('❌ شما دسترسی به این بخش را ندارید.')
                return None
            return await func(self, update, context, *args, **kwargs)
        return wrapper
    return decorator

def require_super_admin(func):
    """Decorator برای محدود کردن دسترسی به super admin فقط"""

    @wraps(func)
    async def wrapper(self, update: Update, context: CustomContext, *args, **kwargs):
        user_id = update.effective_user.id
        if not hasattr(self, 'role_manager'):
            logger.error('role_manager not found in handler class')
            if update.callback_query:
                await update.callback_query.answer('❌ خطای سیستم', show_alert=True)
            else:
                await update.message.reply_text('❌ خطای سیستم')
            return None
        if not await self.role_manager.is_super_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer('❌ فقط ادمین کل به این بخش دسترسی دارد.', show_alert=True)
            else:
                await update.message.reply_text('❌ فقط ادمین کل به این بخش دسترسی دارد.')
            return None
        return await func(self, update, context, *args, **kwargs)
    return wrapper

def get_permission_display_name(permission: Permission) -> str:
    """دریافت نام فارسی دسترسی"""
    names = {
        Permission.MANAGE_ATTACHMENTS_BR:        '🪂 مدیریت اتچمنت BR',
        Permission.MANAGE_ATTACHMENTS_MP:        '🎮 مدیریت اتچمنت MP',
        Permission.MANAGE_SUGGESTED_ATTACHMENTS: '💡 مدیریت پیشنهادی‌ها',
        Permission.MANAGE_USER_ATTACHMENTS:      '📬 مدیریت اتچمنت کاربران',
        Permission.MANAGE_CATEGORIES:            '🗂 مدیریت دسته‌بندی‌ها',
        Permission.MANAGE_TEXTS:                 '📝 مدیریت متون',
        Permission.MANAGE_ADMINS:                '👥 مدیریت ادمین‌ها',
        Permission.MANAGE_USERS:                 '👤 مدیریت کاربران',
        Permission.VIEW_ANALYTICS:               '📊 مشاهده آمار',
        Permission.VIEW_FEEDBACK:                '💬 مشاهده بازخوردها',
        Permission.SEND_NOTIFICATIONS:           '📣 ارسال اطلاعیه',
        Permission.MANAGE_NOTIFICATION_SETTINGS:'🔧 تنظیمات اعلان‌ها',
        Permission.MANAGE_SCHEDULED_NOTIFICATIONS:'⏱ اعلان‌های زمان‌بندی‌شده',
        Permission.MANAGE_TICKETS:               '🎟️ مدیریت تیکت‌ها',
        Permission.MANAGE_FAQS:                  '❓ مدیریت FAQ',
        Permission.BACKUP_DATA:                  '💾 بکاپ‌گیری',
        Permission.IMPORT_EXPORT:                '📥📤 Import/Export',
        Permission.MANAGE_SETTINGS:              '⚙️ مدیریت تنظیمات کلی',
    }
    if permission in names:
        return names[permission]
    return permission.value.replace('_', '\\_')

def format_permissions_list(permissions: Set[Permission]) -> str:
    """فرمت کردن لیست دسترسی\u200cها برای نمایش"""
    if not permissions:
        return 'هیچ دسترسی'
    return '\n'.join([f'  • {get_permission_display_name(p)}' for p in sorted(permissions, key=lambda x: x.value)])