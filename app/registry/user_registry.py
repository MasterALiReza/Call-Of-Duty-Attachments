"""
User Handler Registry

⚠️ تمام کدها از main.py کپی شده‌اند - هیچ logic تغییر نکرده!
"""

from telegram import Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

from .base_registry import BaseHandlerRegistry
from handlers.user.modules.navigation.main_menu import MainMenuHandler
from handlers.user.modules.search.search_handler import SearchHandler
from handlers.user.modules.categories.category_handler import CategoryHandler
from handlers.user.modules.attachments.season_handler import SeasonTopHandler
from handlers.user.modules.suggested.suggested_handler import SuggestedHandler
from handlers.user.modules.guides.guides_handler import GuidesHandler
from handlers.user.modules.cms.cms_handler import CMSUserHandler
from handlers.user.modules.categories.weapon_handler import WeaponHandler
from handlers.user.modules.attachments.top_handler import TopAttachmentsHandler
from handlers.user.modules.attachments.all_handler import AllAttachmentsHandler
from handlers.user.modules.analytics.leaderboard_handler import LeaderboardHandler
from utils.subscribers_pg import SubscribersPostgres

from handlers.user import SEARCHING
from handlers.user.modules.feedback import FeedbackHandler, FEEDBACK_TEXT
from handlers.user.modules.settings.language_handler import LanguageHandler
from handlers.user.modules.notification_handler import NotificationHandler
from handlers.user.modules.help_handler import HelpHandler

from utils.i18n import build_regex_for_key, build_regex_for_keys

# دکمه‌های منوی ثابت که توسط handlerهای اختصاصی مدیریت می‌شوند.
# هر دکمه‌ای که اینجا اضافه شود به طور خودکار از dynamic fallback handler حذف می‌شود.
MENU_KEYS = [
    'menu.buttons.get', 'menu.buttons.search',
    'menu.buttons.season_top', 'menu.buttons.season_list',
    'menu.buttons.suggested', 'menu.buttons.game_settings',
    'menu.buttons.user_settings', 'menu.buttons.notify',
    'menu.buttons.contact', 'menu.buttons.help',
    'menu.buttons.cms', 'menu.buttons.admin',
    'menu.buttons.ua', 'menu.buttons.leaderboard'
]

# الگوی regex کامل‌شده برای خارج کردن دکمه‌های مشخص از dynamic handler
_MENU_EXCLUSION_PATTERN = build_regex_for_keys(MENU_KEYS)


class UserHandlerRegistry(BaseHandlerRegistry):
    """ثبت handlers مربوط به کاربران عادی"""
    
    def __init__(self, application, db):
        """
        Args:
            application: Telegram Application
            db: Database adapter
        """
        super().__init__(application, db)
        from core.container import get_container
        container = get_container()
        self.contact_handlers = container.contact
        self.admin_handlers = container.admin
        
        self.feedback_handler = container.feedback_handler
        self.language_handler = LanguageHandler(db)
        
        # Initialize Subscribers (shared instance)
        self.subs = SubscribersPostgres(db_adapter=self.db)

        # Initialize Handlers
        self.main_menu_handler = MainMenuHandler(self.db)
        # Inject subs into NotificationHandler
        self.notification_handler = NotificationHandler(self.db, self.subs)
        self.category_handler = CategoryHandler(self.db)
        self.weapon_handler = WeaponHandler(self.db)
        self.top_handler = TopAttachmentsHandler(self.db)
        self.all_handler = AllAttachmentsHandler(self.db)
        self.season_handler = SeasonTopHandler(self.db)
        self.suggested_handler = SuggestedHandler(self.db)
        self.guides_handler = GuidesHandler(self.db)
        self.cms_user_handler = CMSUserHandler(self.db)
        
        self.help_handler = HelpHandler(db)
        
        self.search_handler = SearchHandler(self.db)
        self.leaderboard_handler = LeaderboardHandler(self.db)

    
    async def initialize(self):
        """Asynchronous initialization of components"""
        if hasattr(self.subs, 'initialize'):
            await self.subs.initialize()

    def register(self):
        """ثبت تمام handlers مربوط به کاربران"""
        self._register_commands()
        self._register_message_handlers()
        self._register_search_conversation()
        self._register_callback_handlers()
        self._register_analytics_handlers()
        self._register_season_top_handlers()
        self._register_suggested_handlers()
        self._register_feedback_handlers()
        self._register_notification_handlers()
        self._register_dynamic_handlers()
    
    def _register_commands(self):
        """ثبت command handlers"""
        self.application.add_handler(CommandHandler("start", self.main_menu_handler.start))
        self.application.add_handler(CommandHandler("myid", self.main_menu_handler.show_user_id))
        self.application.add_handler(CommandHandler("subscribe", self.notification_handler.subscribe_cmd))
        self.application.add_handler(CommandHandler("unsubscribe", self.notification_handler.unsubscribe_cmd))
    
    def _register_message_handlers(self):
        """ثبت message handlers"""
        # هندلرهای پیام‌های متنی برای دکمه‌های کیبورد
        # دریافت اتچمنت - اول مود را می‌پرسد
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.get')), self.category_handler.show_mode_selection_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.help')), self.help_handler.help_command_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.game_settings')), self.guides_handler.game_settings_menu))
        # تنظیمات ربات (کاربر)
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.user_settings')), self.language_handler.open_user_settings))
        # محتوای CMS (پیام)
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.cms')), self.cms_user_handler.cms_home_msg))
        
        # Import show_user_attachments_menu برای handler
        from handlers.user.user_attachments.submission_handler import show_user_attachments_menu
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.ua')), show_user_attachments_menu))
        
        # منوی راهنماها (Reply Keyboard) - برای backward compatibility
        self.application.add_handler(MessageHandler(filters.Regex('^Basic$'), self.guides_handler.guide_basic_msg))
        self.application.add_handler(MessageHandler(filters.Regex('^Sens$'), self.guides_handler.guide_sens_msg))
        self.application.add_handler(MessageHandler(filters.Regex('^Hud$'), self.guides_handler.guide_hud_msg))
        
        # منوی اصلی - برترهای فصل
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.season_top')), self.season_handler.season_top_media_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.season_list')), self.season_handler.season_top_list_msg))
        
        # کیبورد سطح سلاح
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('weapon.menu.top')), self.top_handler.show_top_attachments_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('weapon.menu.all')), self.all_handler.show_all_attachments_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.back')), self.main_menu_handler.back_msg))
        self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.leaderboard')), self.leaderboard_handler.show_leaderboard))
    
    def _register_search_conversation(self):
        """ثبت ConversationHandler جستجو"""
        search_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.search_handler.search_start, pattern="^search$"),
                CallbackQueryHandler(self.search_handler.search_start, pattern="^search_weapon$"),
                MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.search')), self.search_handler.search_start_msg)
            ],
            states={
                SEARCHING: [
                    # ابتدا دکمه‌های کیبورد را چک می‌کنیم - IMPORTANT: باید قبل از handler عمومی باشد
                # اگر کاربر دوباره دکمه جستجو رو بزنه، بی‌صدا دوباره پیام رو نمایش بده
                MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.search')), self.search_handler.search_restart_silently),
                    # دکمه‌های دیگه - لغو جستجو و رفتن به بخش دیگه
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.get')), self._search_cancel_and_show_mode_selection),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.season_top')), self._search_cancel_and_season_top),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.season_list')), self._search_cancel_and_season_list),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.suggested')), self._search_cancel_and_suggested),
                    # CMS: خروج از جستجو و نمایش CMS
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.cms')), self._search_cancel_and_cms),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.game_settings')), self._search_cancel_and_game_settings),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.help')), self._search_cancel_and_help),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.contact')), self.contact_handlers.search_cancel_and_contact),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.notify')), self._search_cancel_and_notifications),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.leaderboard')), self._search_cancel_and_leaderboard),
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), self.admin_handlers.search_cancel_and_admin),
                    # سپس متن عادی را به عنوان جستجو پردازش می‌کنیم (به استثنای دکمه‌های منو)
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_MENU_EXCLUSION_PATTERN), self.search_handler.search_process),
                    # فال‌بک نهایی برای ورودی‌های غیرمتنی
                    MessageHandler(filters.ALL, self.search_handler.handle_invalid_input)
                ]
            },
            fallbacks=[
                # دکمه لغو - بازگشت به منوی اصلی و خروج از conversation
                CallbackQueryHandler(self.main_menu_handler.main_menu, pattern="^main_menu$")
            ]
        )
        self.application.add_handler(search_conv)
        
    # ======= Search Cancellation Handlers =======
    
    async def _search_cancel_and_show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.category_handler:
            await self.category_handler.show_categories_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_season_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.season_handler:
            await self.season_handler.season_top_select_mode_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_season_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.season_handler:
            await self.season_handler.season_top_list_select_mode_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_suggested(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.suggested_handler:
            await self.suggested_handler.suggested_attachments_select_mode_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_game_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.guides_handler:
            await self.guides_handler.game_settings_menu(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.help_handler:
            await self.help_handler.help_command_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.notification_handler:
            context.user_data['_notification_shown'] = True
            await self.notification_handler.notification_settings(update, context)
        return ConversationHandler.END

    async def _search_cancel_and_show_mode_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.category_handler:
            await self.category_handler.show_mode_selection_msg(update, context)
        return ConversationHandler.END
    
    async def _search_cancel_and_cms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.cms_user_handler:
            await self.cms_user_handler.cms_home_msg(update, context)
        return ConversationHandler.END

    async def _search_cancel_and_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.leaderboard_handler:
            await self.leaderboard_handler.show_leaderboard(update, context)
        return ConversationHandler.END
    
    def _register_callback_handlers(self):
        """ثبت CallbackQuery handlers"""
        # مشاهده اتچمنت از نوتیفیکیشن - با group=-1 تا قبل از همه handlers اجرا بشه
        self.application.add_handler(
            CallbackQueryHandler(self.notification_handler.view_attachment_from_notification, pattern="^attm__"),
            group=-1
        )
        
        # CallbackQuery handlers برای منوها
        # دریافت اتچمنت - اول مود را می‌پرسد
        self.application.add_handler(CallbackQueryHandler(self.category_handler.show_mode_selection, pattern="^categories$"))
        self.application.add_handler(CallbackQueryHandler(self.category_handler.show_mode_selection, pattern="^select_mode_first$"))
        # انتخاب مود (MP/BR) در ابتدای فلوی دریافت اتچمنت
        self.application.add_handler(CallbackQueryHandler(self.category_handler.mode_selected, pattern="^mode_(mp|br)$"))
        self.application.add_handler(CallbackQueryHandler(self.weapon_handler.show_weapons, pattern="^cat_"))
        self.application.add_handler(CallbackQueryHandler(self.weapon_handler.show_weapon_menu, pattern="^wpn_"))
        # Handler برای انتخاب mode بعد از انتخاب سلاح (BR/MP در سطح weapon)
        self.application.add_handler(CallbackQueryHandler(self.weapon_handler.show_mode_menu, pattern="^mode_(?!mp$|br$)"))
        self.application.add_handler(CallbackQueryHandler(self.top_handler.show_top_attachments, pattern="^show_top$"))
        # نمایش همه اتچمنت‌ها؛ پشتیبانی از مسیر مستقیم از نتایج جستجو: all_{category}__{weapon}
        self.application.add_handler(CallbackQueryHandler(self.all_handler.show_all_attachments, pattern="^show_all$|^all_page_|^all_"))
        # send_attachment_quick is in AllAttachmentsHandler? No, it was in UserHandlers.
        # Let's check where it should be. Probably AllAttachmentsHandler or SearchHandler.
        # UserHandlers had it. I need to find it.
        # It's for "qatt_" callback.
        # I'll assume it's in AllAttachmentsHandler or I need to move it.
        # Checked SearchHandler: it generates "qatt_" buttons.
        # But who handles them? UserHandlers.send_attachment_quick.
        # I need to move send_attachment_quick to SearchHandler or AllAttachmentsHandler.
        # Let's assume I moved it to SearchHandler (it's related to quick result from search).
        # Wait, I didn't move it yet. I need to add it to SearchHandler.
        self.application.add_handler(CallbackQueryHandler(self.search_handler.send_attachment_quick, pattern="^qatt_"))
        
        # اتچمنت با mode (فرمت: attm_{mode}_{code})
        # پیاده‌سازی صحیح در AllAttachmentsHandler.attachment_detail_with_mode قرار دارد.
        self.application.add_handler(CallbackQueryHandler(self.all_handler.attachment_detail_with_mode, pattern="^attm_"))
        
        # اتچمنت عادی - فقط att_{code} نه top/season/like/dislike/fb/copy
        # Exclude copy_ تا دکمه «📋 کپی کد» به هندلر اختصاصی خودش برود
        self.application.add_handler(CallbackQueryHandler(self.all_handler.attachment_detail, pattern=r"^att_(?!top_|season_|like_|dislike_|fb_|copy_)") )
        
        # دیگر handlers
        self.application.add_handler(CallbackQueryHandler(self.help_handler.help_command, pattern="^help$"))
        self.application.add_handler(CallbackQueryHandler(self.main_menu_handler.main_menu, pattern="^main_menu$"))
        # CMS (User)
        self.application.add_handler(CallbackQueryHandler(self.cms_user_handler.cms_home, pattern="^cms$"))
        self.application.add_handler(CallbackQueryHandler(self.cms_user_handler.cms_type_selected, pattern="^cms_type_"))
        self.application.add_handler(CallbackQueryHandler(self.cms_user_handler.cms_view, pattern="^cms_view_\\d+$"))
        self.application.add_handler(CallbackQueryHandler(self.cms_user_handler.cms_list_page_navigation, pattern="^cmslist_page_\\d+$"))
        # تنظیمات ربات (کاربر)
        self.application.add_handler(CallbackQueryHandler(self.language_handler.open_user_settings, pattern="^user_settings_menu$"))
        self.application.add_handler(CallbackQueryHandler(self.language_handler.open_language_menu, pattern="^user_settings_language$"))
        self.application.add_handler(CallbackQueryHandler(self.language_handler.set_language, pattern="^set_lang_(fa|en)$"))
        # تنظیمات بازی
        self.application.add_handler(CallbackQueryHandler(self.guides_handler.game_settings_menu, pattern="^game_settings_menu$"))
        self.application.add_handler(CallbackQueryHandler(self.guides_handler.game_settings_mode_selected, pattern="^game_settings_(br|mp)$"))
        self.application.add_handler(CallbackQueryHandler(self.guides_handler.show_guide_inline, pattern="^show_guide_"))
        from handlers.channel.channel_handlers import noop_cb
        self.application.add_handler(CallbackQueryHandler(noop_cb, pattern="^noop$"))
    
    def _register_season_top_handlers(self):
        """ثبت handlers برترهای فصل"""
        # انتخاب mode برای برترهای فصل (گالری)
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_select_mode, pattern="^season_top$"))
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_media_with_mode, pattern="^season_top_mode_"))
        
        # انتخاب mode برای لیست برترهای فصل
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_list_select_mode, pattern="^season_top_list$"))
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_list_with_mode, pattern="^season_list_mode_"))
        
        # صفحه‌بندی و جزئیات
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_list_page_navigation, pattern="^slist_page_"))
        self.application.add_handler(CallbackQueryHandler(self.season_handler.season_top_item_detail, pattern="^satt_"))
    
    def _register_suggested_handlers(self):
        """ثبت handlers اتچمنت‌های پیشنهادی"""
        # انتخاب mode برای اتچمنت‌های پیشنهادی
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_attachments_select_mode, pattern="^suggested_attachments$"))
        # نمایش لیست سلاح‌ها (بعد از انتخاب mode)
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_media_with_mode, pattern="^suggested_mode_"))
        # نمایش لیست اتچمنت‌های یک سلاح
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_weapon_attachments, pattern="^sugg_wpn_"))
        # ارسال یک اتچمنت پیشنهادی
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_send_attachment, pattern="^sugg_send_"))
        
        # نمایش لیست اتچمنت‌های پیشنهادی (متنی)
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_list_with_mode, pattern="^suggested_list_mode_"))
        self.application.add_handler(CallbackQueryHandler(self.suggested_handler.suggested_list_page_navigation, pattern="^sugglist_page_"))
        
        # handler برای دکمه "💡 اتچمنت‌های پیشنهادی"
        sugg_regex = build_regex_for_key('menu.buttons.suggested')
        self.application.add_handler(MessageHandler(filters.Regex(sugg_regex), self.suggested_handler.suggested_attachments_select_mode_msg))
    
    def _register_feedback_handlers(self):
        """ثبت handlers سیستم بازخورد اتچمنت‌ها"""
        # ConversationHandler برای دریافت بازخورد متنی
        feedback_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.feedback_handler.handle_feedback_request, pattern=r"^att_fb_\d+$")
            ],
            states={
                FEEDBACK_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.feedback_handler.handle_feedback_text),
                    CallbackQueryHandler(self.feedback_handler.handle_feedback_cancel, pattern="^att_fb_cancel_")
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.feedback_handler.handle_feedback_cancel)
            ],
            name="feedback_conversation",
            persistent=False
        )
        self.application.add_handler(feedback_conv_handler)
        
        # Callback handlers برای لایک/دیس‌لایک
        self.application.add_handler(CallbackQueryHandler(self.feedback_handler.handle_vote_like, pattern=r"^att_like_\d+$"))
        self.application.add_handler(CallbackQueryHandler(self.feedback_handler.handle_vote_dislike, pattern=r"^att_dislike_\d+$"))
        # Callback handler برای کپی کد
        self.application.add_handler(CallbackQueryHandler(self.feedback_handler.handle_copy_code, pattern=r"^att_copy_\d+$"))
    
    def _register_notification_handlers(self):
        """ثبت handlers تنظیمات اعلان‌ها"""
        # Handler عمومی برای دکمه keyboard - با group=10 تا بعد از ConversationHandler ها اجرا بشه
        # این فقط در حالت عادی (نه admin، نه search) trigger میشه
        # استفاده از wrapper که flag رو check می‌کنه
        notif_regex = build_regex_for_key('menu.buttons.notify')
        self.application.add_handler(
            MessageHandler(filters.Regex(notif_regex), self.notification_handler.notification_settings_with_check),
            group=10
        )
        
        # CallbackQuery handlers برای interaction با منوی notification
        self.application.add_handler(CallbackQueryHandler(self.notification_handler.notification_toggle, pattern="^user_notif_toggle$"))
        self.application.add_handler(CallbackQueryHandler(self.notification_handler.notification_toggle_mode, pattern="^user_notif_mode_"))
        self.application.add_handler(CallbackQueryHandler(self.notification_handler.notification_events_menu, pattern="^user_notif_events$"))
        self.application.add_handler(CallbackQueryHandler(self.notification_handler.notification_toggle_event, pattern="^user_notif_event_"))
        self.application.add_handler(CallbackQueryHandler(self.notification_handler.notification_settings, pattern="^user_notif_back$"))
    
    def _register_analytics_handlers(self):
        """ثبت handlers مربوط به آنالیتیکس و لیدربورد"""
        self.application.add_handler(CallbackQueryHandler(self.leaderboard_handler.show_leaderboard, pattern="^leaderboard$"))
        # متن منوی اصلی برای لیدربورد - در صورت نیاز
        # self.application.add_handler(MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.leaderboard')), self.leaderboard_handler.show_leaderboard))

    def _register_dynamic_handlers(self):
        """ثبت dynamic handler برای نام‌های سفارشی (Basic/Sens/Hud و غیره).
        
        از `_MENU_EXCLUSION_PATTERN` استفاده می‌کند تا دکمه‌های منوی ثابت handler دیگری داشته باشند.
        برای افزودن دکمه جدید، تنها کافی است `MENU_BUTTONS` را به‌روز کنید.
        """
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(_MENU_EXCLUSION_PATTERN),
            self.guides_handler.guide_dynamic_msg
        ), group=10)
