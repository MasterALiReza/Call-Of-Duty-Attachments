"""
ماژول مدیریت کاربران (User Management)
مسئول: نمایش، جستجو، بن/آنبن کاربران در پنل ادمین

Features:
- آمار کلی کاربران
- لیست کاربران با صفحه‌بندی
- جستجوی کاربر (username / ID / نام)
- جزئیات کامل کاربر
- بن / آنبن کردن کاربر
- فیلتر (فعال / بن‌شده / همه)
"""

from core.context import CustomContext

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import (
    ADMIN_MENU, USER_MGMT_MENU, USER_MGMT_LIST,
    USER_MGMT_SEARCH, USER_MGMT_DETAIL, USER_MGMT_BAN
)
from utils.logger import get_logger, log_admin_action
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text
from core.security.role_manager import Permission
import math

logger = get_logger('user_mgmt', 'admin.log')

PAGE_SIZE = 10


class UserManagementHandler(BaseAdminHandler):
    """
    مدیریت کاربران در پنل ادمین

    Features:
    - آمار کلی (کل، امروز، فعال، بن‌شده)
    - لیست کاربران با صفحه‌بندی
    - جستجو بر اساس username / ID / نام
    - جزئیات کامل کاربر
    - بن / آنبن کردن
    - فیلتر (همه / بن‌شده)
    """

    def __init__(self, db):
        super().__init__(db)
        logger.info("UserManagementHandler initialized")

    # ========== Helper ==========

    def _fa_digits(self, n, lang: str = 'fa') -> str:
        """تبدیل عدد به فارسی در صورت نیاز"""
        if lang == 'fa':
            return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        return str(n)

    def _format_datetime(self, dt, lang: str = 'fa') -> str:
        """فرمت تاریخ/زمان"""
        if dt is None:
            return t('admin.user_mgmt.never', lang)
        try:
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(dt)[:16]

    def _escape(self, text: str) -> str:
        """آماده‌سازی متن برای مارک‌داون (Legacy Markdown)"""
        if not text:
            return ""
        # در مارک‌داون معمولی تلگرام، کاراکترهای _ و * و [ و ` باید با دقت مدیریت شوند
        return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

    # ========== منوی اصلی مدیریت کاربران ==========

    async def user_mgmt_menu(self, update: Update, context: CustomContext):
        """منوی اصلی مدیریت کاربران با آمار"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        has_perm = await self.check_permission(user_id, Permission.MANAGE_USERS)
        is_super = await self.role_manager.is_super_admin(user_id)
        if not has_perm and not is_super:
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        # پاک کردن داده‌های قبلی
        context.user_data.pop('um_search', None)
        context.user_data.pop('um_filter', None)
        context.user_data.pop('um_page', None)

        # دریافت آمار
        stats = await self.db.get_users_stats()
        _n = lambda n: self._fa_digits(n, lang)

        text = "━━━━━━━━━━━━━━━━━━━━\n"
        text += t('admin.user_mgmt.title', lang) + "\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        text += t('admin.user_mgmt.stats.header', lang) + "\n"
        text += t('admin.user_mgmt.stats.total', lang, n=_n(stats['total'])) + "\n"
        text += t('admin.user_mgmt.stats.new_today', lang, n=_n(stats['new_today'])) + "\n"
        text += t('admin.user_mgmt.stats.active_today', lang, n=_n(stats['active_today'])) + "\n"
        text += t('admin.user_mgmt.stats.active_week', lang, n=_n(stats['active_week'])) + "\n"
        text += t('admin.user_mgmt.stats.banned', lang, n=_n(stats['banned'])) + "\n"

        keyboard = [
            [
                InlineKeyboardButton(t("admin.user_mgmt.buttons.list_all", lang), callback_data="um_list"),
                InlineKeyboardButton(t("admin.user_mgmt.buttons.search", lang), callback_data="um_search"),
            ],
            [
                InlineKeyboardButton(t("admin.user_mgmt.buttons.banned_only", lang), callback_data="um_filter_banned"),
            ],
            [
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_main"),
            ],
        ]

        await safe_edit_message_text(
            query, text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return USER_MGMT_MENU

    # ========== لیست کاربران ==========

    async def user_list(self, update: Update, context: CustomContext):
        """لیست کاربران با صفحه‌بندی"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        # تشخیص صفحه
        data = query.data
        if data.startswith("um_page_"):
            page = int(data.replace("um_page_", ""))
        else:
            page = 1

        context.user_data['um_page'] = page

        search = context.user_data.get('um_search')
        is_banned = context.user_data.get('um_filter')

        # دریافت کاربران
        users = await self.db.get_users_paginated(page=page, limit=PAGE_SIZE, search=search, is_banned=is_banned)
        total = await self.db.get_users_count(search=search, is_banned=is_banned)
        total_pages = max(1, math.ceil(total / PAGE_SIZE))

        _n = lambda n: self._fa_digits(n, lang)

        text = t('admin.user_mgmt.list.title', lang) + "\n"
        if search:
            text += t('admin.user_mgmt.list.search_for', lang, q=self._escape(search)) + "\n"
        if is_banned is True:
            text += t('admin.user_mgmt.list.filter_banned', lang) + "\n"
        text += t('admin.user_mgmt.list.page_info', lang, page=_n(page), total=_n(total_pages), count=_n(total)) + "\n"
        text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

        if not users:
            text += "\n" + t('admin.user_mgmt.list.empty', lang)
        else:
            for idx, user in enumerate(users, (page - 1) * PAGE_SIZE + 1):
                uid = user['user_id']
                uname = user.get('username')
                fname = user.get('first_name') or ''
                banned = user.get('is_banned', False)

                status_icon = "🚫" if banned else "👤"
                name_display = f"@{uname}" if uname else fname or f"User_{uid}"
                safe_name = self._escape(name_display)
                text += f"{_n(idx)}) {status_icon} *{safe_name}* (`{uid}`)\n"

        # ساخت keyboard
        keyboard = []

        # دکمه‌های کاربران (هر کدام قابل کلیک)
        if users:
            user_buttons = []
            for user in users:
                uid = user['user_id']
                uname = user.get('username')
                fname = user.get('first_name') or ''
                label = f"@{uname}" if uname else fname[:15] or str(uid)
                user_buttons.append(InlineKeyboardButton(label, callback_data=f"um_detail_{uid}"))
                if len(user_buttons) == 2:
                    keyboard.append(user_buttons)
                    user_buttons = []
            if user_buttons:
                keyboard.append(user_buttons)

        # دکمه‌های صفحه‌بندی
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("◀️", callback_data=f"um_page_{page - 1}"))
        nav_row.append(InlineKeyboardButton(f"{_n(page)}/{_n(total_pages)}", callback_data="um_noop"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("▶️", callback_data=f"um_page_{page + 1}"))
        keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_users")])

        await safe_edit_message_text(
            query, text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return USER_MGMT_LIST

    # ========== جستجوی کاربر ==========

    async def user_search_start(self, update: Update, context: CustomContext):
        """شروع جستجوی کاربر"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        text = t('admin.user_mgmt.search.prompt', lang)
        keyboard = [[InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_users")]]
        await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return USER_MGMT_SEARCH

    async def user_search_received(self, update: Update, context: CustomContext):
        """دریافت عبارت جستجو و نمایش نتایج"""
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await update.message.reply_text(t('common.no_permission', lang))
            return ADMIN_MENU

        search_text = update.message.text.strip()

        if not search_text or len(search_text) < 2:
            await update.message.reply_text(t('admin.user_mgmt.search.too_short', lang))
            return USER_MGMT_SEARCH

        context.user_data['um_search'] = search_text
        context.user_data['um_page'] = 1
        context.user_data.pop('um_filter', None)

        # دریافت نتایج
        users = await self.db.get_users_paginated(page=1, limit=PAGE_SIZE, search=search_text)
        total = await self.db.get_users_count(search=search_text)
        _n = lambda n: self._fa_digits(n, lang)

        text = t('admin.user_mgmt.search.results', lang, q=self._escape(search_text), n=_n(total)) + "\n"
        text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

        if not users:
            text += "\n" + t('admin.user_mgmt.list.empty', lang)
        else:
            for idx, user in enumerate(users, 1):
                uid = user['user_id']
                uname = user.get('username')
                fname = user.get('first_name') or ''
                banned = user.get('is_banned', False)
                status_icon = "🚫" if banned else "👤"
                name_display = f"@{uname}" if uname else fname or f"User_{uid}"
                safe_name = self._escape(name_display)
                text += f"{_n(idx)}) {status_icon} *{safe_name}* (`{uid}`)\n"

        keyboard = []
        if users:
            user_buttons = []
            for user in users:
                uid = user['user_id']
                uname = user.get('username')
                fname = user.get('first_name') or ''
                label = f"@{uname}" if uname else fname[:15] or str(uid)
                user_buttons.append(InlineKeyboardButton(label, callback_data=f"um_detail_{uid}"))
                if len(user_buttons) == 2:
                    keyboard.append(user_buttons)
                    user_buttons = []
            if user_buttons:
                keyboard.append(user_buttons)

        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        if total_pages > 1:
            keyboard.append([
                InlineKeyboardButton(f"1/{_n(total_pages)}", callback_data="um_noop"),
                InlineKeyboardButton("▶️", callback_data="um_page_2"),
            ])

        keyboard.append([
            InlineKeyboardButton(t("admin.user_mgmt.buttons.search", lang), callback_data="um_search"),
            InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_users"),
        ])

        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return USER_MGMT_LIST

    # ========== فیلتر بن‌شده‌ها ==========

    async def user_filter_banned(self, update: Update, context: CustomContext):
        """فیلتر فقط کاربران بن‌شده"""
        query = update.callback_query
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        context.user_data['um_filter'] = True
        context.user_data['um_page'] = 1
        context.user_data.pop('um_search', None)
        return await self.user_list(update, context)
        return await self.user_list(update, context)

    # ========== جزئیات کاربر ==========

    async def user_detail(self, update: Update, context: CustomContext):
        """نمایش جزئیات کامل یک کاربر"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        target_user_id = int(query.data.replace("um_detail_", ""))
        user_data = await self.db.get_user_detailed(target_user_id)

        if not user_data:
            await safe_edit_message_text(query, t('admin.user_mgmt.detail.not_found', lang))
            return USER_MGMT_MENU

        _n = lambda n: self._fa_digits(n, lang)

        # ساخت متن جزئیات
        uname = user_data.get('username')
        fname = user_data.get('first_name') or ''
        lname = user_data.get('last_name') or ''
        is_banned = user_data.get('is_banned', False)
        ban_reason = user_data.get('ban_reason') or ''
        language = user_data.get('language', 'fa')
        created = self._format_datetime(user_data.get('created_at'), lang)
        last_seen = self._format_datetime(user_data.get('last_seen'), lang)
        is_sub = user_data.get('is_subscribed', 0) > 0

        text = "━━━━━━━━━━━━━━━━━━━━\n"
        text += t('admin.user_mgmt.detail.title', lang) + "\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"

        text += f"🆔 **ID:** `{target_user_id}`\n"
        if uname:
            text += f"👤 **Username:** @{self._escape(uname)}\n"
        text += f"📛 **{t('admin.user_mgmt.detail.name', lang)}:** {self._escape(fname)} {self._escape(lname)}\n"
        text += f"🌐 **{t('admin.user_mgmt.detail.lang', lang)}:** {language.upper()}\n"
        text += f"📅 **{t('admin.user_mgmt.detail.joined', lang)}:** {created}\n"
        text += f"🕐 **{t('admin.user_mgmt.detail.last_seen', lang)}:** {last_seen}\n"
        text += f"📢 **{t('admin.user_mgmt.detail.subscribed', lang)}:** {'✅' if is_sub else '❌'}\n"

        if is_banned:
            text += f"\n🚫 **{t('admin.user_mgmt.detail.banned', lang)}**\n"
            if ban_reason:
                text += f"📝 {t('admin.user_mgmt.detail.ban_reason', lang)}: {ban_reason}\n"

        # آمار ارسال‌ها
        total_sub = user_data.get('total_submissions', 0)
        if total_sub > 0:
            text += f"\n📊 **{t('admin.user_mgmt.detail.submissions', lang)}:**\n"
            text += f"   📤 {t('admin.user_mgmt.detail.total', lang)}: {_n(total_sub)}\n"
            text += f"   ✅ {t('admin.user_mgmt.detail.approved', lang)}: {_n(user_data.get('approved_count', 0))}\n"
            text += f"   ❌ {t('admin.user_mgmt.detail.rejected', lang)}: {_n(user_data.get('rejected_count', 0))}\n"
            text += f"   ⏳ {t('admin.user_mgmt.detail.pending', lang)}: {_n(user_data.get('pending_count', 0))}\n"

        # دکمه‌ها
        keyboard = []
        if is_banned:
            keyboard.append([InlineKeyboardButton(
                t("admin.user_mgmt.buttons.unban", lang),
                callback_data=f"um_unban_{target_user_id}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                t("admin.user_mgmt.buttons.ban", lang),
                callback_data=f"um_ban_{target_user_id}"
            )])

        keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="um_list")])

        await safe_edit_message_text(
            query, text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return USER_MGMT_DETAIL

    # ========== بن کاربر ==========

    async def user_ban_start(self, update: Update, context: CustomContext):
        """شروع بن کردن کاربر — درخواست دلیل"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        target_user_id = int(query.data.replace("um_ban_", ""))
        context.user_data['um_ban_target'] = target_user_id

        text = t('admin.user_mgmt.ban.prompt', lang, uid=target_user_id)
        keyboard = [[InlineKeyboardButton(t("menu.buttons.back", lang), callback_data=f"um_detail_{target_user_id}")]]
        await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return USER_MGMT_BAN

    async def user_ban_confirm(self, update: Update, context: CustomContext):
        """تایید بن کردن کاربر"""
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await update.message.reply_text(t('common.no_permission', lang))
            return ADMIN_MENU

        reason = update.message.text.strip()
        target_user_id = context.user_data.get('um_ban_target')

        if not target_user_id:
            await update.message.reply_text(t('admin.user_mgmt.ban.error', lang))
            return await self._return_to_menu(update, context)

        success = await self.db.ban_user(target_user_id, reason)

        # Audit log
        await self.audit.log_action(
            admin_id=update.effective_user.id,
            action="BAN_USER",
            target_id=str(target_user_id),
            details={"reason": reason}
        )

        if success:
            await update.message.reply_text(t('admin.user_mgmt.ban.success', lang, uid=target_user_id))
        else:
            await update.message.reply_text(t('admin.user_mgmt.ban.error', lang))

        context.user_data.pop('um_ban_target', None)
        return await self._return_to_menu(update, context)

    # ========== آنبن کاربر ==========

    async def user_unban(self, update: Update, context: CustomContext):
        """آنبن کردن کاربر"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # بررسی دسترسی
        if not await self.check_permission(user_id, Permission.MANAGE_USERS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU

        target_user_id = int(query.data.replace("um_unban_", ""))

        success = await self.db.unban_user(target_user_id)

        # Audit log
        await self.audit.log_action(
            admin_id=update.effective_user.id,
            action="UNBAN_USER",
            target_id=str(target_user_id),
            details={}
        )

        if success:
            await query.answer(t('admin.user_mgmt.unban.success', lang), show_alert=True)
        else:
            await query.answer(t('admin.user_mgmt.unban.error', lang), show_alert=True)

        # برگشت به جزئیات کاربر
        # fake callback data to re-render detail
        query.data = f"um_detail_{target_user_id}"
        return await self.user_detail(update, context)

    # ========== Helper: بازگشت به منو ==========

    async def _return_to_menu(self, update: Update, context: CustomContext):
        """بازگشت به منوی مدیریت کاربران"""
        lang = await get_user_lang(update, context, self.db) or 'fa'

        stats = await self.db.get_users_stats()
        _n = lambda n: self._fa_digits(n, lang)

        text = "━━━━━━━━━━━━━━━━━━━━\n"
        text += t('admin.user_mgmt.title', lang) + "\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        text += t('admin.user_mgmt.stats.header', lang) + "\n"
        text += t('admin.user_mgmt.stats.total', lang, n=_n(stats['total'])) + "\n"
        text += t('admin.user_mgmt.stats.new_today', lang, n=_n(stats['new_today'])) + "\n"
        text += t('admin.user_mgmt.stats.active_today', lang, n=_n(stats['active_today'])) + "\n"
        text += t('admin.user_mgmt.stats.active_week', lang, n=_n(stats['active_week'])) + "\n"
        text += t('admin.user_mgmt.stats.banned', lang, n=_n(stats['banned'])) + "\n"

        keyboard = [
            [
                InlineKeyboardButton(t("admin.user_mgmt.buttons.list_all", lang), callback_data="um_list"),
                InlineKeyboardButton(t("admin.user_mgmt.buttons.search", lang), callback_data="um_search"),
            ],
            [
                InlineKeyboardButton(t("admin.user_mgmt.buttons.banned_only", lang), callback_data="um_filter_banned"),
            ],
            [
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_main"),
            ],
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return USER_MGMT_MENU
