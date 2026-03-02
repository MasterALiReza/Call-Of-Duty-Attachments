from core.context import CustomContext
"""
کلاس جامع AdminHandlers که تمام ماژول‌ها را ترکیب می‌کند
این فایل جایگزین admin_handlers.py قدیمی می‌شود
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.subscribers_pg import SubscribersPostgres as Subscribers
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.modules.attachments import (
    AddAttachmentHandler, 
    DeleteAttachmentHandler,
    EditAttachmentHandler,
    TopAttachmentsHandler,
    SuggestedAttachmentsHandler,
    AttachmentManagementHandler
)
from handlers.admin.modules.analytics import AttachmentsDashboardHandler
from handlers.admin.modules.reports import DataHealthReportHandler
from handlers.admin.modules.system import (
    NotificationHandler,
    # StatsBackupHandler,  # Replaced by DataManagementHandler
    ImportExportHandler,
    AdminManagementHandler,
    DataManagementHandler # Added
)
from handlers.admin.modules.support import (
    FAQHandler,
    TicketHandler,
    DirectContactHandler,
)
from handlers.admin.modules.content import (
    GuidesHandler,
    CategoryHandler,
    WeaponHandler,
    TextHandler,
)
from utils.logger import get_logger, log_admin_action
from utils.language import get_user_lang
from utils.i18n import t

logger = get_logger('admin_modular', 'admin.log')


class AdminHandlers(BaseAdminHandler):
    """
    کلاس اصلی مدیریت پنل ادمین
    ترکیب تمام ماژول‌های مختلف
    """
    
    def __init__(self, db):
        """
        Args:
            db: DatabaseAdapter instance
        """
        super().__init__(db)
        self.subs = Subscribers(db_adapter=db)
        
        # ایجاد notification manager
        from managers.notification_manager import NotificationManager
        self.notif_manager = NotificationManager(db, self.subs)
        
        # ایجاد handler های ماژولار
        self._init_attachment_handlers()
        self._init_system_handlers()
        self._init_support_handlers()
        self._init_content_handlers()
        self._init_new_feature_handlers()  # Initialize new features
    
    def _init_attachment_handlers(self):
        """مقداردهی اولیه handlers مربوط به اتچمنت‌ها"""
        # Attachment handlers
        self.add_attachment_handler = AddAttachmentHandler(self.db)
        self.delete_attachment_handler = DeleteAttachmentHandler(self.db)
        self.edit_attachment_handler = EditAttachmentHandler(self.db)
        self.top_attachments_handler = TopAttachmentsHandler(self.db)
        self.top_attachments_handler = TopAttachmentsHandler(self.db)
        self.suggested_attachments_handler = SuggestedAttachmentsHandler(self.db)
        self.attachment_mgmt_handler = AttachmentManagementHandler(self.db)
        
        self._sub_handlers.extend([
            self.add_attachment_handler,
            self.delete_attachment_handler,
            self.edit_attachment_handler,
            self.top_attachments_handler,
            self.suggested_attachments_handler,
            self.attachment_mgmt_handler
        ])
        
        # کپی کردن توابع از handlers به این کلاس
        from handlers.admin.modules.feedback.feedback_admin_handler import FeedbackAdminHandler
        self.feedback_admin = FeedbackAdminHandler(self.db)
        
        # Mapping for modular access
        # Main Attachment Menu
        self.attachment_management_menu = self.attachment_mgmt_handler.attachment_management_menu
        # Add Attachment
        self.add_attachment_start = self.add_attachment_handler.add_attachment_start
        self.add_attachment_category_selected = self.add_attachment_handler.add_attachment_category_selected
        self.add_attachment_weapon_selected = self.add_attachment_handler.add_attachment_weapon_selected
        self.add_attachment_mode_selected = self.add_attachment_handler.add_attachment_mode_selected
        self.add_attachment_new_weapon_name_received = self.add_attachment_handler.add_attachment_new_weapon_name_received
        self.add_attachment_code_received = self.add_attachment_handler.add_attachment_code_received
        self.add_attachment_name_received = self.add_attachment_handler.add_attachment_name_received
        self.add_attachment_image_received = self.add_attachment_handler.add_attachment_image_received
        self.add_attachment_top_selected = self.add_attachment_handler.add_attachment_top_selected
        self.add_attachment_season_selected = self.add_attachment_handler.add_attachment_season_selected
        # Ignore stray text during callback-only steps (Top/Season questions)
        self.add_attachment_top_ignore_text = self.add_attachment_handler.add_attachment_top_ignore_text
        self.add_attachment_season_ignore_text = self.add_attachment_handler.add_attachment_season_ignore_text
        
        # Delete Attachment
        self.delete_attachment_start = self.delete_attachment_handler.delete_attachment_start
        self.delete_attachment_category_selected = self.delete_attachment_handler.delete_attachment_category_selected
        self.delete_attachment_weapon_selected = self.delete_attachment_handler.delete_attachment_weapon_selected
        self.delete_attachment_mode_selected = self.delete_attachment_handler.delete_attachment_mode_selected
        self.delete_attachment_code_selected = self.delete_attachment_handler.delete_attachment_code_selected
        
        # Edit Attachment
        self.edit_attachment_start = self.edit_attachment_handler.edit_attachment_start
        self.edit_attachment_category_selected = self.edit_attachment_handler.edit_attachment_category_selected
        self.edit_attachment_weapon_selected = self.edit_attachment_handler.edit_attachment_weapon_selected
        self.edit_attachment_mode_selected = self.edit_attachment_handler.edit_attachment_mode_selected
        self.edit_attachment_selected = self.edit_attachment_handler.edit_attachment_selected
        self.edit_attachment_action_menu = self.edit_attachment_handler.edit_attachment_action_menu
        self.edit_attachment_action_selected = self.edit_attachment_handler.edit_attachment_action_selected
        self.edit_attachment_name_received = self.edit_attachment_handler.edit_attachment_name_received
        self.edit_attachment_image_received = self.edit_attachment_handler.edit_attachment_image_received
        self.edit_attachment_code_received = self.edit_attachment_handler.edit_attachment_code_received
        
        # Top Attachments
        self.set_top_start = self.top_attachments_handler.set_top_start
        self.set_top_category_selected = self.top_attachments_handler.set_top_category_selected
        self.set_top_weapon_selected = self.top_attachments_handler.set_top_weapon_selected
        self.set_top_mode_selected = self.top_attachments_handler.set_top_mode_selected
        self.set_top_attachment_selected = self.top_attachments_handler.set_top_attachment_selected
        self.set_top_confirm_answer = self.top_attachments_handler.set_top_confirm_answer
        self.set_top_confirm_save = self.top_attachments_handler.set_top_confirm_save
        
        # Suggested Attachments
        self.manage_suggested_menu = self.suggested_attachments_handler.manage_suggested_menu
        self.suggested_add_start = self.suggested_attachments_handler.suggested_add_start
        self.suggested_mode_selected = self.suggested_attachments_handler.suggested_mode_selected
        self.suggested_category_selected = self.suggested_attachments_handler.suggested_category_selected
        self.suggested_weapon_selected = self.suggested_attachments_handler.suggested_weapon_selected
        self.suggested_attachment_selected = self.suggested_attachments_handler.suggested_attachment_selected
        self.suggested_remove_start = self.suggested_attachments_handler.suggested_remove_start
        self.suggested_remove_mode_selected = self.suggested_attachments_handler.suggested_remove_mode_selected
        self.suggested_delete_confirmed = self.suggested_attachments_handler.suggested_delete_confirmed
        self.suggested_view_list = self.suggested_attachments_handler.suggested_view_list
        # Suggested Analytics
        self.suggested_analytics_menu = self.suggested_attachments_handler.suggested_analytics_menu
        self.analytics_sugg_trending = self.suggested_attachments_handler.analytics_sugg_trending
        self.analytics_sugg_underperforming = self.suggested_attachments_handler.analytics_sugg_underperforming
        self.analytics_sugg_weapon_stats = self.suggested_attachments_handler.analytics_sugg_weapon_stats
    
    def _init_system_handlers(self):
        """مقداردهی اولیه handlers مربوط به سیستم"""
        self.category_handler = CategoryHandler(self.db)
        self.weapon_handler = WeaponHandler(self.db)
        self.admin_mgmt_handler = AdminManagementHandler(self.db)
        self.admin_mgmt_handler.set_role_manager(self.role_manager)
        self.import_export_handler = ImportExportHandler(self.db)
        
        # Notification handler
        from handlers.admin.modules.system import NotificationHandler, DataManagementHandler
        self.notification_handler = NotificationHandler(self.db)
        self.data_mgmt_handler = DataManagementHandler(self.db)

        # User Management handler
        from handlers.admin.modules.system.user_management import UserManagementHandler
        self.user_mgmt_handler = UserManagementHandler(self.db)

        self._sub_handlers.extend([
            self.category_handler,
            self.weapon_handler,
            self.admin_mgmt_handler,
            self.import_export_handler,
            self.notification_handler,
            self.data_mgmt_handler,
            self.user_mgmt_handler
        ])
    
        # Mapping for NotificationHandler
        self.notify_start = self.notification_handler.notify_start
        self.notify_home_menu = self.notification_handler.notify_home_menu
        self.notify_compose_start = self.notification_handler.notify_compose_start
        self.notify_compose_received = self.notification_handler.notify_compose_received
        self.notify_settings_menu = self.notification_handler.notify_settings_menu
        self.notify_toggle = self.notification_handler.notify_toggle
        self.notify_auto_toggle = self.notification_handler.notify_auto_toggle
        self.template_list_menu = self.notification_handler.template_list_menu
        self.notif_toggle_event = self.notification_handler.notif_toggle_event
        self.template_edit_start = self.notification_handler.template_edit_start
        self.schedule_delete = self.notification_handler.schedule_delete
        self.schedule_toggle = self.notification_handler.schedule_toggle
        self.schedule_edit_open = self.notification_handler.schedule_edit_open
        self.schedule_edit_text_start = self.notification_handler.schedule_edit_text_start
        self.schedule_edit_text_received = self.notification_handler.schedule_edit_text_received
        self.notify_confirm_selected = self.notification_handler.notify_confirm_selected
        self.notify_schedule_menu = self.notification_handler.notify_schedule_menu
        self.notify_schedule_preset_selected = self.notification_handler.notify_schedule_preset_selected
        self.notif_toggle_global = self.notification_handler.notif_toggle_global
        self.schedules_menu = self.notification_handler.schedules_menu
    
        self.edit_admin_role_start = self.admin_mgmt_handler.edit_admin_role_start
        self.edit_admin_role_select = self.admin_mgmt_handler.edit_admin_role_select
        self.add_role_to_admin = self.admin_mgmt_handler.add_role_to_admin
        self.add_role_confirm = self.admin_mgmt_handler.add_role_confirm
        self.delete_role_from_admin = self.admin_mgmt_handler.delete_role_from_admin
        self.delete_role_confirm = self.admin_mgmt_handler.delete_role_confirm
        self.remove_admin_start = self.admin_mgmt_handler.remove_admin_start
        self.remove_admin_confirmed = self.admin_mgmt_handler.remove_admin_confirmed
        # Handlers جدید برای UX بهتر
        self.view_all_admins = self.admin_mgmt_handler.view_all_admins
        self.role_stats = self.admin_mgmt_handler.role_stats
        self.data_management_menu = self.data_mgmt_handler.data_management_menu

        # User Management mapping
        self.user_mgmt_menu = self.user_mgmt_handler.user_mgmt_menu
        self.user_list = self.user_mgmt_handler.user_list
        self.user_search_start = self.user_mgmt_handler.user_search_start
        self.user_search_received = self.user_mgmt_handler.user_search_received
        self.user_detail = self.user_mgmt_handler.user_detail
        self.user_ban_start = self.user_mgmt_handler.user_ban_start
        self.user_ban_confirm = self.user_mgmt_handler.user_ban_confirm
        self.user_unban = self.user_mgmt_handler.user_unban
        self.user_filter_banned = self.user_mgmt_handler.user_filter_banned
    
    def _init_support_handlers(self):
        """مقداردهی اولیه handlers مربوط به پشتیبانی"""
        self.admin_faq_handler = FAQHandler(self.db)
        self.admin_ticket_handler = TicketHandler(self.db)
        self.direct_contact_handler = DirectContactHandler(self.db)

        self._sub_handlers.extend([
            self.admin_faq_handler,
            self.admin_ticket_handler,
            self.direct_contact_handler
        ])
    
    def _init_content_handlers(self):
        """مقداردهی اولیه handlers مربوط به محتوا"""
        # Content handlers
        self.guides_handler = GuidesHandler(self.db)
        self.guides_handler.set_role_manager(self.role_manager)
        self.category_handler = CategoryHandler(self.db)
        self.weapon_handler = WeaponHandler(self.db)
        self.text_handler = TextHandler(self.db)
        # CMS
        try:
            from handlers.admin.modules.content import CMSHandler
            self.cms_handler = CMSHandler(self.db)
        except Exception as _e:
            self.cms_handler = None
        
        # کپی کردن توابع از handlers به این کلاس
        # Guides
        self.guides_menu = self.guides_handler.guides_menu
        self.guides_mode_selected = self.guides_handler.guides_mode_selected
        self.guide_section_menu = self.guides_handler.guide_section_menu
        self.guide_op_router = self.guides_handler.guide_op_router
        self.guide_rename_received = self.guides_handler.guide_rename_received
        self.guide_photo_received = self.guides_handler.guide_photo_received
        self.guide_video_received = self.guides_handler.guide_video_received
        self.guide_media_confirmed = self.guides_handler.guide_media_confirmed
        self.guide_code_received = self.guides_handler.guide_code_received
        
        # Category (Mode-First)
        self.category_handler.set_role_manager(self.role_manager)
        self.category_mgmt_menu = self.category_handler.category_mgmt_menu
        self.category_mode_selected = self.category_handler.category_mode_selected
        self.category_toggle_selected = self.category_handler.category_toggle_selected
        self.category_clear_prompt = self.category_handler.category_clear_prompt
        self.category_clear_confirm = self.category_handler.category_clear_confirm
        self.category_clear_cancel = self.category_handler.category_clear_cancel
        # Note: handle_navigation_back از BaseAdminHandler استفاده می‌شود
        
        # Weapon
        self.weapon_mgmt_menu = self.weapon_handler.weapon_mgmt_menu
        self.weapon_mode_selected = self.weapon_handler.weapon_mode_selected
        self.weapon_select_category_menu = self.weapon_handler.weapon_select_category_menu
        self.weapon_select_weapon_menu = self.weapon_handler.weapon_select_weapon_menu
        self.weapon_action_selected = self.weapon_handler.weapon_action_selected
        self.weapon_delete_confirmed = self.weapon_handler.weapon_delete_confirmed
        
        # Text
        self.texts_menu = self.text_handler.texts_menu
        self.text_edit_start = self.text_handler.text_edit_start
        self.text_edit_received = self.text_handler.text_edit_received
        # CMS
        if self.cms_handler:
            self.cms_menu = self.cms_handler.cms_menu
            self.cms_add_start = self.cms_handler.cms_add_start
            self.cms_type_selected = self.cms_handler.cms_type_selected
            self.cms_title_received = self.cms_handler.cms_title_received
            self.cms_body_received = self.cms_handler.cms_body_received
            self.cms_list_menu = self.cms_handler.cms_list_menu
            self.cms_publish = self.cms_handler.cms_publish
            self.cms_delete = self.cms_handler.cms_delete
            self.cms_search_start = self.cms_handler.cms_search_start
            self.cms_search_received = self.cms_handler.cms_search_received
            self._sub_handlers.append(self.cms_handler)
        
        self._sub_handlers.extend([
            self.guides_handler,
            self.text_handler
        ])
    
    def _init_new_feature_handlers(self):
        """Initialize new feature handlers (Data Health, Loadouts, Analytics)"""
        from core.security.role_manager import RoleManager
        
        # Initialize Role Manager for new handlers
        role_manager = RoleManager(self.db)
        
        # Analytics Dashboard
        self.analytics_handler = AttachmentsDashboardHandler(self.db)
        self.analytics_menu = self.analytics_handler.analytics_menu
        self.view_trending = self.analytics_handler.view_trending
        self.view_underperforming = self.analytics_handler.view_underperforming
        self.view_weapon_stats = self.analytics_handler.view_weapon_stats
        self.weapon_stats_select_mode = self.analytics_handler.weapon_stats_select_mode
        self.weapon_stats_show_results = self.analytics_handler.weapon_stats_show_results
        self.view_user_behavior = self.analytics_handler.view_user_behavior
        self.user_behavior_details = self.analytics_handler.user_behavior_details
        self.daily_report = self.analytics_handler.daily_report
        self.weekly_report = self.analytics_handler.weekly_report
        self.search_attachment_stats = self.analytics_handler.search_attachment_stats
        self.handle_search_text = self.analytics_handler.handle_search_text  # NEW
        self.download_report = self.analytics_handler.download_report
        self.refresh_trending = self.analytics_handler.refresh_trending
        self.daily_chart = self.analytics_handler.daily_chart
        self.download_daily_csv = self.analytics_handler.download_daily_csv
        self.weapon_details = self.analytics_handler.weapon_details
        self.att_daily_chart = self.analytics_handler.att_daily_chart
        self.att_download_csv = self.analytics_handler.att_download_csv
        
        self._sub_handlers.append(self.analytics_handler)
        
        # Data Health Report
        self.health_handler = DataHealthReportHandler(self.db, role_manager)
        self.data_health_menu = self.health_handler.data_health_menu
        self.run_health_check = self.health_handler.run_health_check
        self.view_full_report = self.health_handler.view_full_report
        self.view_critical = self.health_handler.view_critical
        self.view_warnings = self.health_handler.view_warnings
        self.view_detailed_stats = self.health_handler.view_detailed_stats
        self.view_check_history = self.health_handler.view_check_history
        self.fix_issues_menu = self.health_handler.fix_issues_menu
        self.fix_missing_images = self.health_handler.fix_missing_images
        self.fix_duplicate_codes = self.health_handler.fix_duplicate_codes
        self.fix_orphaned = self.health_handler.fix_orphaned
        self.fix_technical = self.health_handler.fix_technical
        
        # Route restore flow correctly to DataHealthReportHandler
        self.restore_backup_start = self.health_handler.restore_backup_start
        self.restore_backup_file = self.health_handler.restore_backup_file
        
        # Keep StatsBackupHandler.create_backup as the main backup entrypoint (PostgreSQL-safe)
        self.create_backup_health = self.health_handler.create_backup
        
        self._sub_handlers.append(self.health_handler)
    
    def __getattr__(self, name):
        # Proxy to sub-handlers, eliminating the need to manually assign hundreds of methods
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        for handler in self._sub_handlers:
            if hasattr(handler, name):
                return getattr(handler, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def admin_start(self, update: Update, context: CustomContext):
        """شروع پنل ادمین از طریق دستور یا callback"""
        from telegram import InlineKeyboardMarkup
        
        user_id = update.effective_user.id
        
        if not await self.is_admin(user_id):
            # Handle both message and callback query
            lang = await get_user_lang(update, context, self.db) or 'fa'
            if update.callback_query:
                await update.callback_query.answer(t("admin.not_admin", lang))
                await update.callback_query.edit_message_text(t("admin.not_admin", lang))
            else:
                await update.message.reply_text(t("admin.not_admin", lang))
            return ConversationHandler.END
        
        # ======== FULL RESET: Clear ALL admin-related context data ========
        # This ensures a fresh start every time admin panel is opened
        self._clear_navigation(context)
        self._clear_temp_data(context)
        
        # Clear any additional stuck state keys
        keys_to_clear = [k for k in list(context.user_data.keys()) 
                         if k.startswith(('admin_', 'edit_', 'add_', 'del_', 'set_', 
                                         'notif_', 'guide_', 'text_', 'tmpl_', 
                                         'faq_', 'ticket_', 'cms_', 'cat_', 'weapon_',
                                         'suggested_', 'health_', 'import_', 'export_',
                                         'ua_', 'nav_', 'search_'))]
        for key in keys_to_clear:
            context.user_data.pop(key, None)
        context.user_data.pop('admin_entry_handled', None)
        
        # استفاده از متد مشترک برای ساخت کیبورد با فیلتر دسترسی
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = await self._get_admin_main_keyboard(user_id, lang)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                t("admin.panel.welcome", lang),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                t("admin.panel.welcome", lang),
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        from handlers.admin.admin_states import ADMIN_MENU
        return ADMIN_MENU
    
    @log_admin_action("admin_start_msg")
    async def admin_start_msg(self, update: Update, context: CustomContext):
        """شروع پنل ادمین از طریق دکمه کیبورد"""
        from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
        
        user_id = update.effective_user.id
        
        if not await self.is_admin(user_id):
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await update.message.reply_text(t("admin.not_admin", lang))
            return ConversationHandler.END
        
        # پاک کردن navigation stack
        self._clear_navigation(context)
        
        # کیبورد اصلی با فیلتر دسترسی
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = await self._get_admin_main_keyboard(user_id, lang)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            t("admin.panel.welcome", lang),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        from handlers.admin.admin_states import ADMIN_MENU
        return ADMIN_MENU
    
    @log_admin_action("admin_menu")
    async def admin_menu(self, update: Update, context: CustomContext):
        """مدیریت منوی ادمین - مسیریابی به ماژول‌های مختلف"""
        
        query = update.callback_query
        logger.info(f"⚠️ admin_menu called with callback: {query.data}")
        # حذف answer() - هر handler خودش answer می‌کند
        
        user_id = query.from_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if not await self.is_admin(user_id):
            await query.answer()  # فقط در صورت خطا
            await query.edit_message_text(t("admin.not_admin", lang))
            return ConversationHandler.END
        
        # اگر از entry_points فراخوانی شده، stack را پاک کن
        if 'admin_entry_handled' not in context.user_data:
            self._clear_navigation(context)
            context.user_data['admin_entry_handled'] = True
        
        action = query.data
        
        # مسیریابی به handlers مختلف
        if action in ("admin_menu_return", "admin_back", "admin_return"):
            # بازگشت به منوی اصلی ادمین
            return await self.admin_menu_return(update, context)
        elif action == "admin_main":
            return await self.admin_menu_return(update, context)
        elif action == "admin_cms" and self.cms_handler:
            return await self.cms_menu(update, context)
        elif action == "cms_add" and self.cms_handler:
            return await self.cms_add_start(update, context)
        elif action == "cms_list" and self.cms_handler:
            return await self.cms_list_menu(update, context)
        elif action == "cms_search" and self.cms_handler:
            return await self.cms_search_start(update, context)
        elif action.startswith("cms_type_") and self.cms_handler:
            return await self.cms_type_selected(update, context)
        elif action.startswith("cms_pub_") and self.cms_handler:
            return await self.cms_publish(update, context)
        elif action.startswith("cms_del_") and self.cms_handler:
            return await self.cms_delete(update, context)
        elif action == "manage_admins":
            # همیشه منوی مدیریت ادمین‌ها را رندر کن (خود handler خطای Message is not modified را هندل می‌کند)
            return await self.manage_admins_menu(update, context)
        elif action == "admin_manage_attachments":
             return await self.attachment_management_menu(update, context)
        elif action == "admin_add_attachment":
            return await self.add_attachment_start(update, context)
        elif action == "admin_delete_attachment":
            return await self.delete_attachment_start(update, context)
        elif action == "admin_edit_attachment":
            return await self.edit_attachment_start(update, context)
        elif action == "admin_set_top":
            return await self.set_top_start(update, context)
        elif action == "admin_manage_suggested":
            return await self.manage_suggested_menu(update, context)
        elif action == "admin_notify":
            return await self.notify_start(update, context)
        elif action == "admin_notify_settings":
            return await self.notify_settings_menu(update, context)
        elif (action.startswith("notif_") or action.startswith("tmpl_") or 
              action.startswith("sched_") or action.startswith("notify_") or
              action.startswith("nconf_")):
            # مسیریابی تمام کالبک‌های مربوط به پیام‌رسانی و اعلان‌ها
            if action == "notify_compose":
                return await self.notify_compose_start(update, context)
            elif action == "admin_sched_notifications":
                return await self.schedules_menu(update, context)
            elif action == "notify_home":
                return await self.notify_home_menu(update, context)
            elif action == "notif_toggle":
                return await self.notify_toggle(update, context)
            elif action == "notif_auto_toggle":
                return await self.notify_auto_toggle(update, context)
            elif action == "notif_templates":
                return await self.template_list_menu(update, context)
            elif action.startswith("notif_event_"):
                return await self.notif_toggle_event(update, context)
            elif action.startswith("tmpl_edit_"):
                return await self.template_edit_start(update, context)
            elif action.startswith("sched_delete_"):
                return await self.schedule_delete(update, context)
            elif action.startswith("sched_toggle_"):
                return await self.schedule_toggle(update, context)
            elif action.startswith("sched_edit_text_"):
                return await self.schedule_edit_text_start(update, context)
            elif action.startswith("sched_edit_"):
                return await self.schedule_edit_open(update, context)
            elif action == "notify_confirm" or action.startswith("nconf_"):
                return await self.notify_confirm_selected(update, context)
            elif action == "notify_schedule":
                return await self.notify_schedule_menu(update, context)
            elif action.startswith("notif_sched_"):
                return await self.notify_schedule_preset_selected(update, context)
            elif action == "notif_toggle_global":
                return await self.notif_toggle_global(update, context)
            elif action == "notif_schedules":
                return await self.schedules_menu(update, context)
            
            # پیش‌فرض برای بخش تنظیمات (اگر کالبک خاصی هندل نشد)
            return await self.notify_settings_menu(update, context)
        
        elif action == "admin_stats":
            # Legacy: feature removed — return to main menu
            return await self.admin_menu_return(update, context)
        elif action == "admin_data_management":
            return await self.data_management_menu(update, context)
        elif action == "admin_backup" or action == "admin_create_backup":
            return await self.create_backup(update, context)
        elif action == "admin_auto_backup_menu":
            return await self.auto_backup_menu(update, context)
        elif action == "toggle_auto_backup":
            return await self.toggle_auto_backup(update, context)
        elif action.startswith("set_ab_interval_"):
            return await self.set_auto_backup_interval(update, context)
        elif action == "restore_backup":
            return await self.health_handler.restore_backup_start(update, context)
        elif action == "admin_import":
            return await self.import_start(update, context)
        elif action == "admin_export":
            return await self.export_start(update, context)
        elif action == "admin_faqs":
            return await self.admin_faqs_menu(update, context)
        elif action == "adm_faq_add":
            return await self.admin_faq_add_start(update, context)
        elif action.startswith("adm_faq_cat_"):
            return await self.admin_faq_category_selected(update, context)
        elif action == "adm_faq_list":
            return await self.admin_faq_list(update, context)
        elif action == "admin_tickets":
            return await self.admin_tickets_menu(update, context)
        elif action == "adm_direct_contact":
            return await self.admin_direct_contact_menu(update, context)
        elif action == "admin_guides":
            return await self.guides_menu(update, context)
        elif action.startswith("gmode_"):
            return await self.guides_mode_selected(update, context)
        elif action.startswith("gsel_"):
            return await self.guide_section_menu(update, context)
        elif action.startswith("gop_"):
            return await self.guide_op_router(update, context)
        elif action == "admin_category_mgmt":
            return await self.category_handler.category_mgmt_menu(update, context)
        elif action.startswith("cmm_"):
            return await self.category_handler.category_mode_selected(update, context)
        elif action.startswith("adm_cat_toggle_"):
            return await self.category_handler.category_toggle_selected(update, context)
        elif action.startswith("adm_cat_clear_"):
            return await self.category_handler.category_clear_prompt(update, context)
        elif action == "admin_weapon_mgmt":
            return await self.weapon_handler.weapon_mgmt_menu(update, context)
        elif action.startswith("wmm_"):
            return await self.weapon_handler.weapon_mode_selected(update, context)
        elif action.startswith("wmcat_"):
            return await self.weapon_select_category_menu(update, context)
        elif action.startswith("wmwpn_"):
            return await self.weapon_select_weapon_menu(update, context)
        elif action.startswith("wmact_"):
            return await self.weapon_action_selected(update, context)
        elif action.startswith("wmconf_"):
            return await self.weapon_delete_confirmed(update, context)
        elif action == "cat_clear_confirm":
            return await self.category_clear_confirm(update, context)
        elif action == "cat_clear_cancel":
            return await self.category_clear_cancel(update, context)
        elif action == "nav_back":
            # Determine which sub-handler should handle it
            if any(k.startswith('weapon_') for k in context.user_data.keys()):
                 return await self.weapon_handler.handle_navigation_back(update, context)
            if any(k.startswith('cat_') for k in context.user_data.keys()):
                 return await self.category_handler.handle_navigation_back(update, context)
            return await self.admin_menu_return(update, context)
        elif action == "admin_texts" or action.startswith("text_edit_"):
            return await self.text_edit_start(update, context) if action.startswith("text_edit_") else await self.texts_menu(update, context)
        elif action == "add_new_admin":
            return await self.add_admin_start(update, context)
        elif action == "view_all_admins":
            return await self.view_all_admins(update, context)
        elif action == "role_stats":
            return await self.role_stats(update, context)
        # New feature menu items
        elif action.startswith("analytics_") or action == "attachment_analytics":
            # Delegate to specialized handlers based on prefix
            if action == "analytics_view_trending":
                return await self.analytics_handler.view_trending(update, context)
            elif action == "analytics_view_underperforming":
                return await self.analytics_handler.view_underperforming(update, context)
            elif action == "analytics_view_weapon_stats":
                return await self.analytics_handler.view_weapon_stats(update, context)
            elif action == "analytics_search_attachment":
                return await self.analytics_handler.search_attachment_stats(update, context)
            elif action == "analytics_cohort_analysis":
                return await self.analytics_handler.analytics_cohort_analysis(update, context)
            elif action == "analytics_funnel_analysis":
                return await self.analytics_handler.analytics_funnel_analysis(update, context)
            elif action == "analytics_daily_report":
                return await self.analytics_handler.daily_report(update, context)
            elif action == "analytics_download_report":
                return await self.analytics_handler.download_report(update, context)
            # Default to main analytics menu
            return await self.analytics_menu(update, context)
            
        elif action.startswith("health_") or action == "data_health":
            # Delegate to health handler
            if action == "health_run_check":
                return await self.health_handler.run_health_check(update, context)
            elif action == "health_view_full_report":
                return await self.health_handler.view_full_report(update, context)
            elif action == "health_view_critical":
                return await self.health_handler.view_critical(update, context)
            elif action == "health_view_warnings":
                return await self.health_handler.view_warnings(update, context)
            elif action == "health_view_detailed_stats":
                return await self.health_handler.view_detailed_stats(update, context)
            elif action == "health_view_check_history":
                return await self.health_handler.view_check_history(update, context)
            elif action == "health_fix_missing_images":
                return await self.health_handler.fix_missing_images(update, context)
            elif action == "health_fix_duplicate_codes":
                return await self.health_handler.fix_duplicate_codes(update, context)
            elif action == "health_fix_orphaned":
                return await self.health_handler.fix_orphaned(update, context)
            elif action == "health_fix_technical":
                return await self.health_handler.fix_technical(update, context)
            elif action in ["health_restore_backup", "admin_restore_backup", "restore_backup"]:
                return await self.health_handler.restore_backup_start(update, context)
            elif action in ["admin_create_backup", "health_create_backup"]:
                return await self.health_handler.create_backup(update, context)
            elif action in ["health_fix_issues_menu", "fix_issues_menu"]:
                return await self.health_handler.fix_issues_menu(update, context)
            
            # Default to main health menu
            return await self.data_health_menu(update, context)
            
        elif action.startswith("fb_"):
            # Delegate feedback-related callbacks
            if action == "fb_dashboard":
                return await self.feedback_admin.show_feedback_dashboard(update, context)
            elif action == "fb_change_period":
                return await self.feedback_admin.change_period(update, context)
            elif action.startswith("fb_period_"):
                return await self.feedback_admin.set_period(update, context)
            elif action == "fb_toggle_suggested":
                return await self.feedback_admin.toggle_suggested_only(update, context)
            elif action == "fb_top":
                return await self.feedback_admin.show_top_attachments(update, context)
            elif action == "fb_bottom":
                return await self.feedback_admin.show_bottom_attachments(update, context)
            elif action == "fb_comments" or action.startswith("fb_comments_page_"):
                return await self.feedback_admin.show_user_comments(update, context)
            elif action == "fb_trend":
                return await self.feedback_admin.show_weekly_trend(update, context)
            elif action == "fb_search":
                return await self.feedback_admin.show_search_menu(update, context)
            elif action.startswith("fb_search_q_"):
                return await self.feedback_admin.execute_search_query(update, context)
            elif action == "fb_filter_mode":
                return await self.feedback_admin.filter_mode_menu(update, context)
            elif action.startswith("fb_mode_"):
                return await self.feedback_admin.set_mode_filter(update, context)
            elif action == "fb_filter_category":
                return await self.feedback_admin.filter_category_menu(update, context)
            elif action.startswith("fb_cat_"):
                return await self.feedback_admin.set_category_filter(update, context)
            
            # Default fallback for other fb_ prefixes
            return await self.feedback_admin.show_feedback_dashboard(update, context)

        elif action.startswith("selrole_"):
            return await self.add_admin_role_selected(update, context)
        elif action == "edit_admin_role":
            return await self.edit_admin_role_start(update, context)
        elif action == "view_roles":
            return await self.view_roles_menu(update, context)
        elif action == "remove_admin":
            return await self.remove_admin_start(update, context)
        elif action.startswith("editadm_"):
            return await self.edit_admin_role_select(update, context)
        elif action.startswith("addrole_"):
            return await self.add_role_to_admin(update, context)
        elif action.startswith("newrole_"):
            return await self.add_role_confirm(update, context)
        elif action.startswith("delrole_"):
            return await self.delete_role_from_admin(update, context)
        elif action.startswith("delconfirm_"):
            return await self.delete_role_confirm(update, context)
        elif action.startswith("remove_") or action.startswith("remove_confirm_"):
            return await self.remove_admin_confirmed(update, context)
        # ─── User Management ───
        elif action == "admin_users":
            return await self.user_mgmt_menu(update, context)
        elif action == "um_list":
            return await self.user_list(update, context)
        elif action.startswith("um_page_"):
            return await self.user_list(update, context)
        elif action == "um_search":
            return await self.user_search_start(update, context)
        elif action == "um_filter_banned":
            return await self.user_filter_banned(update, context)
        elif action.startswith("um_detail_"):
            return await self.user_detail(update, context)
        elif action.startswith("um_ban_"):
            return await self.user_ban_start(update, context)
        elif action.startswith("um_unban_"):
            return await self.user_unban(update, context)
        elif action == "um_noop":
            await query.answer()
            return ADMIN_MENU
        elif action == "admin_exit":
            await query.edit_message_text(t("admin.exit.done", lang))
            return ConversationHandler.END
        
        # سایر actions باید در ماژول‌های دیگر پیاده‌سازی شوند
        logger.warning(f"Unhandled action in admin_menu: {action}")
        
        from handlers.admin.admin_states import ADMIN_MENU
        return ADMIN_MENU
    
    async def admin_cancel(self, update: Update, context: CustomContext):
        """لغو و بازگشت به منوی اصلی"""
        query = update.callback_query
        if query:
            await query.answer()
        return await self.admin_menu_return(update, context)
    
    async def search_cancel_and_admin(self, update: Update, context: CustomContext):
        """لغو بی‌صدا جستجو و نمایش پنل ادمین"""
        user_id = update.effective_user.id
        
        if self.is_admin(user_id):
            await self.admin_start_msg(update, context)
        else:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await update.message.reply_text(t("admin.not_admin", lang))
        
        return ConversationHandler.END
    
    async def admin_exit_silent(self, update: Update, context: CustomContext):
        """خروج ساکت از conversation ادمین"""
        from utils.logger import get_logger
        logger = get_logger('admin_modular', 'admin.log')
        logger.info(f"[ADMIN_EXIT_SILENT] User {update.effective_user.id} exiting admin")
        
        # پاک کردن navigation stack و داده‌های موقت
        self._clear_navigation(context)
        self._clear_temp_data(context)
        
        return ConversationHandler.END
    
    async def handle_navigation_back(self, update: Update, context: CustomContext):
        """
        Override handle_navigation_back برای delegate کردن به handler مناسب
        بر اساس context فعلی
        
        Note: query.answer() را اینجا نمی‌زنیم چون به handler مشخص delegate می‌کنیم
        که خودش یا تابع نهایی (مثل category_mgmt_menu) answer را handle می‌کند
        """
        # بررسی اینکه در کدام flow هستیم
        if 'cat_mgmt_mode' in context.user_data:
            # در flow مدیریت دسته‌ها هستیم - delegate به category_handler
            return await self.category_handler.handle_navigation_back(update, context)
            
        # بررسی flow افزودن اتچمنت
        if any(key in context.user_data for key in ['add_att_mode', 'add_att_category', 'add_att_weapon']):
            return await self.add_attachment_handler.handle_navigation_back(update, context)

        # بررسی flow حذف اتچمنت
        if any(key in context.user_data for key in ['del_att_mode', 'del_att_category', 'del_att_weapon']):
            return await self.delete_attachment_handler.handle_navigation_back(update, context)

        # بررسی flow ویرایش اتچمنت
        if any(key in context.user_data for key in ['edit_att_mode', 'edit_att_category', 'edit_att_weapon']):
            return await self.edit_attachment_handler.handle_navigation_back(update, context)

        # بررسی flow اتچمنت‌های برتر
        if any(key in context.user_data for key in ['set_top_mode', 'set_top_category', 'set_top_weapon']):
            return await self.top_attachments_handler.handle_navigation_back(update, context)

        # بررسی flow مدیریت سلاح‌ها
        if any(key in context.user_data for key in ['weapon_mgmt_mode', 'weapon_mgmt_category', 'weapon_mgmt_weapon']):
            return await self.weapon_handler.handle_navigation_back(update, context)
        
        # بررسی flow اتچمنت‌های پیشنهادی
        if any(key in context.user_data for key in ['suggested_mode', 'suggested_category', 'suggested_weapon']):
            # در flow suggested attachments هستیم - delegate به suggested_handler
            return await self.suggested_attachments_handler.handle_navigation_back(update, context)
        
        # پیش‌فرض: استفاده از BaseAdminHandler
        return await super().handle_navigation_back(update, context)
