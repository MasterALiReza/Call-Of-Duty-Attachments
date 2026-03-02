"""
Contact Handler Registry

⚠️ تمام کدها از main.py کپی شده‌اند - هیچ logic تغییر نکرده!
"""

from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

from .base_registry import BaseHandlerRegistry
from handlers.user.modules.navigation.main_menu import MainMenuHandler

from handlers.contact.contact_handlers import (
    CONTACT_MENU, TICKET_CATEGORY, TICKET_SUBJECT, TICKET_DESCRIPTION,
    TICKET_ATTACHMENT, FAQ_SEARCH, FEEDBACK_RATING, FEEDBACK_MESSAGE
)


from utils.i18n import build_regex_for_key, build_regex_for_keys

# دکمه‌های منوی اصلی برای مستثنی کردن از ورودی‌های متنی (Keyboard Capture Fix)
MENU_KEYS = [
    'menu.buttons.get', 'menu.buttons.search',
    'menu.buttons.season_top', 'menu.buttons.season_list',
    'menu.buttons.suggested', 'menu.buttons.game_settings',
    'menu.buttons.user_settings', 'menu.buttons.notify',
    'menu.buttons.contact', 'menu.buttons.help',
    'menu.buttons.cms', 'menu.buttons.admin',
    'menu.buttons.ua', 'menu.buttons.leaderboard'
]
_MENU_EXCLUSION_PATTERN = build_regex_for_keys(MENU_KEYS)

class ContactHandlerRegistry(BaseHandlerRegistry):
    """ثبت handlers مربوط به تماس با ما"""
    
    def __init__(self, application, db):
        """
        Args:
            application: Telegram Application
            db: Database adapter
        """
        super().__init__(application, db)
        from core.container import get_container
        self.contact_handlers = get_container().contact
        # Create MainMenuHandler for fallback handlers
        self.main_menu_handler = MainMenuHandler(db)
    
    def register(self):
        """ثبت ConversationHandler تماس - کپی دقیق از main.py خط 678-729"""
        contact_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact$"),
                MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.contact')), self.contact_handlers.contact_menu),
                # Add entry points for inner buttons to handle restarts/cross-conversation
                CallbackQueryHandler(self.contact_handlers.new_ticket_start, pattern="^contact_new_ticket$"),
                CallbackQueryHandler(self.contact_handlers.my_tickets, pattern="^contact_my_tickets$"),
                CallbackQueryHandler(self.contact_handlers.faq_menu, pattern="^contact_faq$"),
                CallbackQueryHandler(self.contact_handlers.feedback_start, pattern="^contact_feedback$")
            ],
            states={
                CONTACT_MENU: [
                    # اجازه بازگشت به منوی تماس با keyboard
                    MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.contact')), self.contact_handlers.contact_menu),
                    CallbackQueryHandler(self.contact_handlers.new_ticket_start, pattern="^contact_new_ticket$"),
                    CallbackQueryHandler(self.contact_handlers.my_tickets, pattern="^contact_my_tickets$"),
                    CallbackQueryHandler(self.contact_handlers.faq_menu, pattern="^contact_faq$"),
                    CallbackQueryHandler(self.contact_handlers.feedback_start, pattern="^contact_feedback$"),
                    CallbackQueryHandler(self.contact_handlers.view_ticket, pattern="^ticket_view_"),
                    CallbackQueryHandler(self.contact_handlers.faq_view, pattern="^faq_view_"),
                    # ثبت بازخورد روی FAQ (مفید/نامفید)
                    CallbackQueryHandler(self.contact_handlers.faq_mark_helpful, pattern=r"^faq_helpful_\d+$"),
                    CallbackQueryHandler(self.contact_handlers.faq_mark_not_helpful, pattern=r"^faq_not_helpful_\d+$"),
                    CallbackQueryHandler(self.main_menu_handler.main_menu, pattern="^main_menu$"),
                ],
                TICKET_CATEGORY: [
                    CallbackQueryHandler(self.contact_handlers.ticket_category_selected, pattern="^tc_"),
                    CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact_menu$"),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ],
                TICKET_SUBJECT: [
                    # استثنا کردن دکمه‌های منوی اصلی (Keyboard Capture Fix)
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_MENU_EXCLUSION_PATTERN), self.contact_handlers.ticket_subject_received),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ],
                TICKET_DESCRIPTION: [
                    # استثنا کردن دکمه‌های منوی اصلی
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_MENU_EXCLUSION_PATTERN), self.contact_handlers.ticket_description_received),
                    CallbackQueryHandler(self.contact_handlers.ticket_continue, pattern="^ticket_continue$"),
                    CallbackQueryHandler(self.contact_handlers.faq_view, pattern="^faq_view_"),
                    CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact_menu$"),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ],
                TICKET_ATTACHMENT: [
                    CallbackQueryHandler(self.contact_handlers.ticket_add_image_request, pattern="^ticket_add_image$"),
                    CallbackQueryHandler(self.contact_handlers.ticket_submit, pattern="^ticket_submit$"),
                    MessageHandler(filters.PHOTO, self.contact_handlers.ticket_image_received),
                    CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact_menu$"),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ],
                FEEDBACK_RATING: [
                    CallbackQueryHandler(self.contact_handlers.feedback_rating_selected, pattern="^feedback_rate_"),
                    CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact_menu$"),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ],
                FEEDBACK_MESSAGE: [
                    # استثنا کردن دکمه‌های منوی اصلی
                    MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_MENU_EXCLUSION_PATTERN), self.contact_handlers.feedback_message_received),
                    CallbackQueryHandler(self.contact_handlers.feedback_submit_no_comment, pattern="^feedback_submit_no_comment$"),
                    MessageHandler(filters.ALL, self.contact_handlers.handle_invalid_input)
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.contact_handlers.contact_menu, pattern="^contact_menu$"),
                CommandHandler("start", self.main_menu_handler.start)
            ],
            per_message=True
        )
        self.application.add_handler(contact_conv)
