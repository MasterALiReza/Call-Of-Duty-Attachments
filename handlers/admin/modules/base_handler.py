from core.context import CustomContext
"""
Base handler برای تمام admin handlers
شامل توابع مشترک و helper methods
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from typing import Dict, List
from config.config import SUPER_ADMIN_ID
from core.security.role_manager import Permission
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t
from core.audit import AuditLogger

logger = get_logger('admin_base', 'admin.log')


class BaseAdminHandler:
    """کلاس پایه برای تمام admin handlers"""
    
    def __init__(self, db):
        """
        Args:
            db: DatabaseAdapter instance
        """
        self.db = db
        from core.container import get_container
        self.container = get_container()
        
        # ایجاد role manager برای مدیریت نقش‌ها و دسترسی‌ها
        from core.security.role_manager import RoleManager
        self.role_manager = RoleManager(db)
        
        # ایجاد audit logger برای ثبت فعالیت‌ها
        self.audit = AuditLogger()
        self._sub_handlers = []
    
    
    async def is_admin(self, user_id: int) -> bool:
        """بررسی دسترسی ادمین"""
        if hasattr(self, 'role_manager'):
            return await self.role_manager.is_admin(user_id)
        # fallback به سوپراادمین
        return user_id == SUPER_ADMIN_ID
    
    async def check_permission(self, user_id: int, permission) -> bool:
        """بررسی دسترسی کاربر به یک permission خاص"""
        if hasattr(self, 'role_manager'):
            return await self.role_manager.has_permission(user_id, permission)
        # fallback: اگر ادمین است true برگردان
        return self.is_admin(user_id)
    
    async def send_permission_denied(self, update: Update, context: CustomContext):
        """ارسال پیام عدم دسترسی"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        message = t("admin.permission.denied.title", lang) + "\n\n" + t("admin.permission.denied.body", lang)
        
        keyboard = [[InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_menu_return")]]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    async def admin_cancel(self, update: Update, context: CustomContext):
        """لغو عملیات و بازگشت به منوی ادمین"""
        query = update.callback_query
        if query:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t("common.cancelled", lang))
        
        # Clear user data
        context.user_data.clear()
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        message = t("admin.canceled_return", lang)
        
        if query:
            await query.edit_message_text(message)
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                message
            )
            
        return ConversationHandler.END
    
    async def handle_invalid_input(self, update: Update, context: CustomContext):
        """هندلر برای ورودی‌های نامعتبر (فال‌بک)"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        # استفاده از پیام عمومی برای ورودی نامعتبر
        await update.message.reply_text(t("admin.texts.error.text_only", lang))
        return None  # ماندن در وضعیت فعلی
    
    # ========== Navigation Stack Methods ==========
    
    def _push_navigation(self, context: CustomContext, state: int, data: dict = None):
        """اضافه کردن یک مرحله به navigation stack"""
        if 'nav_stack' not in context.user_data:
            context.user_data['nav_stack'] = []
        context.user_data['nav_stack'].append({'state': state, 'data': data or {}})
    
    def _pop_navigation(self, context: CustomContext):
        """برگشت به مرحله قبلی"""
        if 'nav_stack' in context.user_data and context.user_data['nav_stack']:
            return context.user_data['nav_stack'].pop()
        return None
    
    def _clear_navigation(self, context: CustomContext):
        """پاک کردن navigation stack"""
        if 'nav_stack' in context.user_data:
            context.user_data['nav_stack'] = []
    
    def _add_back_cancel_buttons(self, keyboard: list, show_back: bool = True):
        """اضافه کردن دکمه‌های بازگشت و لغو به keyboard"""
        buttons = []
        if show_back:
            buttons.append(InlineKeyboardButton("⬅️", callback_data="nav_back"))
        buttons.append(InlineKeyboardButton("❌", callback_data="admin_cancel"))
        keyboard.append(buttons)
    
    # ========== Helper Methods ==========
    
    def _make_weapon_keyboard(self, weapons: List[str], prefix: str, category: str = None) -> List[List[InlineKeyboardButton]]:
        """
        ساخت keyboard برای لیست سلاح‌ها با تعداد ستون متغیر
        
        Args:
            weapons: لیست نام سلاح‌ها
            prefix: پیشوند برای callback_data
            category: دسته سلاح (اختیاری)
        
        Returns:
            لیست از لیست دکمه‌ها
        """
        keyboard = []
        
        # تعیین تعداد ستون‌ها
        # برای دسته‌های AR و SMG همیشه 3 ستون
        if category:
            category_lower = str(category).lower().strip()
            if category_lower in ['assault_rifle', 'smg', 'ar']:
                columns = 3
            elif len(weapons) > 0:
                # بر اساس طول نام سلاح‌ها
                max_name_length = max([len(w) for w in weapons], default=0)
                
                if max_name_length <= 8:
                    columns = 3
                elif max_name_length <= 15:
                    columns = 2
                else:
                    columns = 1
            else:
                columns = 2
        else:
            # اگر category نداریم، بر اساس طول نام سلاح‌ها
            max_name_length = max([len(w) for w in weapons], default=0)
            
            if max_name_length <= 8:
                columns = 3
            elif max_name_length <= 15:
                columns = 2
            else:
                columns = 1
        
        # ساخت ردیف‌ها
        row = []
        for weapon in weapons:
            callback_data = f"{prefix}{weapon}"
            row.append(InlineKeyboardButton(weapon, callback_data=callback_data))
            
            if len(row) == columns:
                keyboard.append(row)
                row = []
        
        # اضافه کردن ردیف آخر اگر کامل نشده
        if row:
            keyboard.append(row)
        
        return keyboard
    
    def _make_mode_selection_keyboard(self, prefix: str, lang: str = 'fa', allowed_modes: List[str] = None) -> List[List[InlineKeyboardButton]]:
        """
        ساخت کیبورد انتخاب مود به صورت عمودی (استاندارد)
        
        Args:
            prefix: پیشوند برای callback_data (مثلاً edit_att_mode_)
            lang: زبان
            allowed_modes: لیست مودهای مجاز (اختیاری)
            
        Returns:
            لیست دکمه‌ها (هر مود در یک ردیف)
        """
        keyboard = []
        # ترتیب: BR بالاتر، MP پایین‌تر (یا برعکس طبق سلیقه، اینجا عمودی است)
        if allowed_modes is None or 'br' in allowed_modes:
            keyboard.append([InlineKeyboardButton(t("mode.br_btn", lang), callback_data=f"{prefix}br")])
        if allowed_modes is None or 'mp' in allowed_modes:
            keyboard.append([InlineKeyboardButton(t("mode.mp_btn", lang), callback_data=f"{prefix}mp")])
        return keyboard
    
    async def admin_menu_return(self, update: Update, context: CustomContext):
        """بازگشت به منوی اصلی ادمین"""
        query = update.callback_query if update.callback_query else None
        
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = await self._get_admin_main_keyboard(user_id, lang)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            try:
                await query.edit_message_text(
                    t("admin.panel.welcome", lang),
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                if "message is not modified" not in str(e).lower():
                    raise
        else:
            await update.message.reply_text(
                t("admin.panel.welcome", lang),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # پاک کردن داده‌های موقت
        self._clear_temp_data(context)
        
        # Import states from admin_states
        from handlers.admin.admin_states import ADMIN_MENU
        return ADMIN_MENU
    
    def _clear_temp_data(self, context: CustomContext):
        """پاک کردن داده‌های موقت از context"""
        keys_to_remove = [
            'add_att_category', 'add_att_weapon', 'add_att_mode',
            'add_att_code', 'add_att_name', 'add_att_image', 'add_att_is_top',
            'del_att_category', 'del_att_weapon', 'del_att_mode',
            'set_top_category', 'set_top_weapon', 'set_top_mode',
            'edit_att_category', 'edit_att_weapon', 'edit_att_mode', 'edit_att_code',
            'notif_type', 'notif_text', 'notif_photo',
            'guide_key', 'guide_mode', 'text_key', 'tmpl_key',
            'admin_entry_handled', 'faq_question', 'edit_faq_id', 'edit_faq_data',
            'selected_admin_role', 'new_admin_id', 'edit_admin_user_id'
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
    
    async def _get_admin_main_keyboard(self, user_id: int, lang: str = 'fa') -> List[List[InlineKeyboardButton]]:
        """
        ساخت کیبورد منوی اصلی ادمین با فیلتر دسترسی و دسته‌بندی منطقی
        
        Args:
            user_id: شناسه کاربر ادمین
        
        Returns:
            لیست دکمه‌های فیلتر شده
        """
        from core.security.role_manager import Permission
        
        # ─── Super Admin: همه دکمه‌ها بدون فیلتر ───
        is_super = await self.role_manager.is_super_admin(user_id)
        if is_super:
            keyboard = [
                # ─── بخش مدیریت کاربران و دسترسی ───
                [
                    InlineKeyboardButton(t("admin.buttons.manage_users", lang), callback_data="admin_users"),
                    InlineKeyboardButton(t("admin.buttons.manage_admins", lang), callback_data="manage_admins"),
                ],
                # ─── بخش اطلاع‌رسانی ───
                [
                    InlineKeyboardButton(t("admin.buttons.notify_send", lang), callback_data="admin_notify"),
                    InlineKeyboardButton(t("admin.buttons.notify_settings", lang), callback_data="admin_notify_settings"),
                ],
                # ─── بخش پشتیبانی و بازخورد ───
                [
                    InlineKeyboardButton(t("admin.buttons.tickets", lang), callback_data="admin_tickets"),
                    InlineKeyboardButton(t("admin.buttons.feedback_dashboard", lang), callback_data="fb_dashboard"),
                ],
                # ─── بخش محتوا و راهنما ───
                [
                    InlineKeyboardButton(t("admin.buttons.cms", lang), callback_data="admin_cms"),
                    InlineKeyboardButton(t("admin.buttons.faq", lang), callback_data="admin_faqs"),
                ],
                # ─── بخش فنی و سیستم ───
                [
                    InlineKeyboardButton(t("admin.buttons.analytics", lang), callback_data="attachment_analytics"),
                    InlineKeyboardButton(t("admin.buttons.data_health", lang), callback_data="data_health"),
                ],
                # ─── بخش زیرساخت و داده ───
                [
                    InlineKeyboardButton(t("admin.buttons.manage_channels", lang), callback_data="channel_management"),
                    InlineKeyboardButton(t("admin.buttons.data_mgmt", lang), callback_data="admin_data_management"),
                ],
                # ─── تنظیمات ربات ───
                [
                    InlineKeyboardButton(t("admin.buttons.edit_texts", lang), callback_data="admin_texts"),
                    InlineKeyboardButton(t("admin.buttons.game_settings", lang), callback_data="admin_guides"),
                ],
                [InlineKeyboardButton(t("admin.menu.attachments", lang), callback_data="admin_manage_attachments")],
                [InlineKeyboardButton(t("admin.buttons.exit", lang), callback_data="admin_exit")],
            ]
            return keyboard

        # ─── سایر ادمین‌ها: فیلتر بر اساس دسترسی ───
        user_permissions = await self.role_manager.get_user_permissions(user_id)
        keyboard = []

        # 1. مدیریت کاربران و دسترسی
        user_row = []
        if Permission.MANAGE_USERS in user_permissions:
            user_row.append(InlineKeyboardButton(t("admin.buttons.manage_users", lang), callback_data="admin_users"))
        if Permission.MANAGE_ADMINS in user_permissions:
            user_row.append(InlineKeyboardButton(t("admin.buttons.manage_admins", lang), callback_data="manage_admins"))
        if user_row:
            keyboard.append(user_row)

        # 2. اطلاع‌رسانی
        notify_row = []
        if Permission.SEND_NOTIFICATIONS in user_permissions:
            notify_row.append(InlineKeyboardButton(t("admin.buttons.notify_send", lang), callback_data="admin_notify"))
        if Permission.MANAGE_NOTIFICATION_SETTINGS in user_permissions:
            notify_row.append(InlineKeyboardButton(t("admin.buttons.notify_settings", lang), callback_data="admin_notify_settings"))
        if notify_row:
            keyboard.append(notify_row)

        # 3. پشتیبانی و بازخورد
        support_row = []
        if Permission.MANAGE_TICKETS in user_permissions:
            support_row.append(InlineKeyboardButton(t("admin.buttons.tickets", lang), callback_data="admin_tickets"))
        if Permission.VIEW_FEEDBACK in user_permissions:
            support_row.append(InlineKeyboardButton(t("admin.buttons.feedback_dashboard", lang), callback_data="fb_dashboard"))
        if support_row:
            keyboard.append(support_row)

        # 4. محتوا و فایل‌ها
        content_row = []
        if Permission.MANAGE_TEXTS in user_permissions:
            content_row.append(InlineKeyboardButton(t("admin.buttons.cms", lang), callback_data="admin_cms"))
        if Permission.MANAGE_FAQS in user_permissions:
            content_row.append(InlineKeyboardButton(t("admin.buttons.faq", lang), callback_data="admin_faqs"))
        if content_row:
            keyboard.append(content_row)

        # 5. فنی و تحلیل
        analytics_row = []
        if Permission.VIEW_ANALYTICS in user_permissions:
            analytics_row.append(InlineKeyboardButton(t("admin.buttons.analytics", lang), callback_data="attachment_analytics"))
            analytics_row.append(InlineKeyboardButton(t("admin.buttons.data_health", lang), callback_data="data_health"))
        if analytics_row:
            keyboard.append(analytics_row)

        # 6. زیرساخت و داده
        infra_row = []
        # فرض بر این است که مدیریت کانال هم جزئی از تنظیمات یا مدیریت سیستم است
        if Permission.MANAGE_SETTINGS in user_permissions:
            infra_row.append(InlineKeyboardButton(t("admin.buttons.manage_channels", lang), callback_data="channel_management"))
        if Permission.IMPORT_EXPORT in user_permissions or Permission.BACKUP_DATA in user_permissions:
            infra_row.append(InlineKeyboardButton(t("admin.buttons.data_mgmt", lang), callback_data="admin_data_management"))
        if infra_row:
            keyboard.append(infra_row)

        # 7. تنظیمات کلیدی
        settings_row = []
        if Permission.MANAGE_TEXTS in user_permissions:
            settings_row.append(InlineKeyboardButton(t("admin.buttons.edit_texts", lang), callback_data="admin_texts"))
        if Permission.MANAGE_SETTINGS in user_permissions: # تنظیمات بازی/راهنما
            settings_row.append(InlineKeyboardButton(t("admin.buttons.game_settings", lang), callback_data="admin_guides"))
        if settings_row:
            keyboard.append(settings_row)

        # 8. دکمه‌های اصلی و خروجی
        if (Permission.MANAGE_ATTACHMENTS_BR in user_permissions or
            Permission.MANAGE_ATTACHMENTS_MP in user_permissions or
            Permission.MANAGE_USER_ATTACHMENTS in user_permissions or
            Permission.MANAGE_SUGGESTED_ATTACHMENTS in user_permissions or
            Permission.MANAGE_CATEGORIES in user_permissions):
            keyboard.append([InlineKeyboardButton(t("admin.menu.attachments", lang), callback_data="admin_manage_attachments")])

        keyboard.append([InlineKeyboardButton(t("admin.buttons.exit", lang), callback_data="admin_exit")])
        return keyboard
    
    async def data_management_menu(self, update: Update, context: CustomContext):
        """نمایش منوی مدیریت داده و بکاپ"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_permissions = await self.role_manager.get_user_permissions(user_id)
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        message = t("admin.data_mgmt.title", lang) + "\n\n" + t("admin.data_mgmt.body", lang)
        
        keyboard = []
        
        # Import/Export
        if Permission.IMPORT_EXPORT in user_permissions:
            keyboard.append([
                InlineKeyboardButton(t("admin.data_mgmt.import", lang), callback_data="admin_import"),
                InlineKeyboardButton(t("admin.data_mgmt.export", lang), callback_data="admin_export")
            ])
        
        # Backup
        if Permission.BACKUP_DATA in user_permissions:
            keyboard.append([
                InlineKeyboardButton(t("admin.data_mgmt.backup", lang), callback_data="admin_backup")
            ])
        
        # بازگشت
        keyboard.append([
            InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="admin_menu_return")
        ])
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_navigation_back(self, update: Update, context: CustomContext):
        """مدیریت دکمه بازگشت"""
        query = update.callback_query
        # توجه: answer() قبلاً در handler caller صدا زده شده
        
        # بازیابی state قبلی
        prev = self._pop_navigation(context)
        
        if not prev:
            # اگر stack خالی است، به منوی اصلی برگرد
            return await self.admin_menu_return(update, context)
        
        state = prev['state']
        data = prev.get('data', {})
        
        # بازگرداندن داده‌ها
        for key, value in data.items():
            context.user_data[key] = value
        
        # بازسازی صفحه قبلی
        await self._rebuild_state_screen(update, context, state)
        
        return state
    
    async def _rebuild_state_screen(self, update: Update, context: CustomContext, state: int):
        """
        بازسازی و نمایش صفحه مربوط به state قبلی
        این متد باید در هر handler که از navigation استفاده می‌کند override شود
        """
        # این متد در base است، اما هر handler باید آن را override کند
        pass
    
    def _create_confirmation_keyboard(
        self,
        confirm_callback: str = "confirm_yes",
        cancel_callback: str = "confirm_no",
        confirm_text: str = None,
        cancel_text: str = None,
        show_back: bool = False
    ) -> List[List[InlineKeyboardButton]]:
        """
        ساخت کیبورد تایید استاندارد
        
        Args:
            confirm_callback: callback_data برای دکمه تایید
            cancel_callback: callback_data برای دکمه لغو
            confirm_text: متن دکمه تایید
            cancel_text: متن دکمه لغو
            show_back: نمایش دکمه بازگشت
        
        Returns:
            لیست دکمه‌های کیبورد
        """
        if confirm_text is None:
            confirm_text = "✅"
        if cancel_text is None:
            cancel_text = "❌"
        keyboard = [
            [
                InlineKeyboardButton(confirm_text, callback_data=confirm_callback),
                InlineKeyboardButton(cancel_text, callback_data=cancel_callback)
            ]
        ]
        if show_back:
            keyboard.append([InlineKeyboardButton("⬅️", callback_data="nav_back")])
        keyboard.append([InlineKeyboardButton("❌", callback_data="admin_cancel")])
        return keyboard
