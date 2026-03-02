from core.context import CustomContext
"""
Base class برای تمام User Handlers
توابع مشترک و utilities
⚠️ این کد عیناً از user_handlers.py کپی شده - خط 22-89
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from utils.subscribers_pg import SubscribersPostgres as Subscribers
from utils.logger import get_logger
from utils.i18n import t
logger = get_logger('user', 'user.log')

class BaseUserHandler:
    """کلاس پایه برای تمام user handlers"""

    def __init__(self, db):
        """
        Args:
            db: DatabaseAdapter instance
        """
        self.db = db
        self.subs = Subscribers(db_adapter=db)

    async def _track_user_info(self, update: Update):
        """
        ذخیره/به\u200cروزرسانی اطلاعات کاربر در دیتابیس
        Safe to call multiple times - idempotent
        """
        try:
            user = update.effective_user
            await self.db.upsert_user(user_id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)
        except Exception as e:
            logger.debug(f'Could not track user info for {user.id}: {e}')

    def _weapon_reply_keyboard(self, top_count: int, all_count: int, lang: str='fa') -> ReplyKeyboardMarkup:
        """ساخت کیبورد پایینی برای عملیات سلاح (i18n)"""
        top_text = f"{t('weapon.menu.top', lang)} ({top_count})"
        all_text = f"{t('weapon.menu.all', lang)} ({all_count})"
        keyboard = [[top_text, all_text], [t('menu.buttons.search', lang), t('menu.buttons.back', lang)]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def _make_two_column_keyboard(self, items, callback_prefix, add_back_button=True, back_callback='categories', lang: str='fa'):
        """ساخت keyboard 2 ستونی از لیست آیتم\u200cها
        
        Args:
            items: لیست آیتم\u200cها (str یا tuple)
            callback_prefix: prefix برای callback_data
            add_back_button: اضافه کردن دکمه بازگشت
            back_callback: callback_data برای دکمه بازگشت
        """
        keyboard = []
        for i in range(0, len(items), 2):
            row = []
            item1 = items[i]
            if isinstance(item1, tuple):
                text1, data1 = item1
            else:
                text1, data1 = (item1, f'{callback_prefix}{item1}')
            row.append(InlineKeyboardButton(text1, callback_data=data1))
            if i + 1 < len(items):
                item2 = items[i + 1]
                if isinstance(item2, tuple):
                    text2, data2 = item2
                else:
                    text2, data2 = (item2, f'{callback_prefix}{item2}')
                row.append(InlineKeyboardButton(text2, callback_data=data2))
            keyboard.append(row)
        if add_back_button:
            keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=back_callback)])
        return keyboard

    def _make_mode_selection_keyboard(self, callback_prefix: str, lang: str):
        """ساخت کیبورد استاندارد انتخاب مود (عمودی با ایموجی)"""
        keyboard = [
            [InlineKeyboardButton(t("mode.br_btn", lang), callback_data=f"{callback_prefix}br")],
            [InlineKeyboardButton(t("mode.mp_btn", lang), callback_data=f"{callback_prefix}mp")]
        ]
        return keyboard

    async def handle_invalid_input(self, update: Update, context: CustomContext):
        """هندلر برای ورودی\u200cهای نامعتبر (فال\u200cبک)"""
        if not update.message:
            return None
        lang = t('menu.default_lang', 'fa')
        try:
            from utils.language import get_user_lang
            lang = await get_user_lang(update, context, self.db) or 'fa'
        except ImportError:
            pass
        await update.message.reply_text(t('admin.texts.error.text_only', lang))
        return None