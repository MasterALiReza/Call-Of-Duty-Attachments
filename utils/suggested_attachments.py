from core.context import CustomContext
"""
سیستم مدیریت اتچمنت\u200cهای پیشنهادی
"""
from typing import List, Dict, Tuple, Optional
from core.database.database_adapter import DatabaseAdapter
from config.config import GAME_MODES, CATEGORIES
from utils.logger import get_logger, log_user_action, log_admin_action
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, Update
from telegram.ext import ContextTypes
import math
ITEMS_PER_PAGE = 10
MAX_PRIORITY = 999
DEFAULT_PRIORITY = 500
logger = get_logger('suggested_attachments')

class SuggestedAttachmentsManager:
    """مدیریت اتچمنت\u200cهای پیشنهادی"""

    def __init__(self, db: DatabaseAdapter):
        self.db = db
        logger.info('SuggestedAttachmentsManager initialized')

    @log_admin_action('add_to_suggested')
    async def add_to_suggested(self, attachment_id: int, mode: str, priority: int=DEFAULT_PRIORITY, reason: str=None, admin_id: int=None) -> bool:
        """افزودن اتچمنت به لیست پیشنهادی
        
        Args:
            attachment_id: شناسه اتچمنت
            mode: 'br' یا 'mp'
            priority: اولویت نمایش (1-999)
            reason: دلیل پیشنهاد
            admin_id: شناسه ادمین
        """
        try:
            if not 1 <= priority <= MAX_PRIORITY:
                logger.warning(f'Invalid priority {priority}, using default {DEFAULT_PRIORITY}')
                priority = DEFAULT_PRIORITY
            success = await self.db.add_suggested_attachment(attachment_id=attachment_id, mode=mode, priority=priority, reason=reason, added_by=admin_id)
            if success:
                logger.info(f'Attachment {attachment_id} added to suggested list for {mode} by admin {admin_id}')
            else:
                logger.error(f'Failed to add attachment {attachment_id} to suggested list')
            return success
        except Exception as e:
            logger.error(f'Error in add_to_suggested: {e}')
            return False

    @log_admin_action('remove_from_suggested')
    async def remove_from_suggested(self, attachment_id: int, mode: str) -> bool:
        """حذف اتچمنت از لیست پیشنهادی
        
        Args:
            attachment_id: شناسه اتچمنت
            mode: 'br' یا 'mp'
        """
        try:
            success = await self.db.remove_suggested_attachment(attachment_id, mode)
            if success:
                logger.info(f'Attachment {attachment_id} removed from suggested list for {mode}')
            else:
                logger.error(f'Failed to remove attachment {attachment_id} from suggested list')
            return success
        except Exception as e:
            logger.error(f'Error in remove_from_suggested: {e}')
            return False

    @log_admin_action('clear_all_suggested')
    async def clear_all_suggested(self, mode: str=None) -> bool:
        """پاک کردن همه اتچمنت\u200cهای پیشنهادی
        
        Args:
            mode: 'br', 'mp' یا None برای پاک کردن همه
        """
        try:
            count_before = await self.db.get_suggested_count(mode)
            success = await self.db.clear_suggested_attachments(mode)
            if success:
                logger.info(f"Cleared {count_before} suggested attachments for mode: {mode or 'all'}")
            return success
        except Exception as e:
            logger.error(f'Error in clear_all_suggested: {e}')
            return False

    async def is_suggested(self, attachment_id: int, mode: str) -> bool:
        """بررسی اینکه آیا اتچمنت در لیست پیشنهادی هست"""
        try:
            return await self.db.is_attachment_suggested(attachment_id, mode)
        except Exception as e:
            logger.error(f'Error checking if attachment is suggested: {e}')
            return False

    async def get_suggested_count(self, mode: str=None) -> int:
        """دریافت تعداد اتچمنت\u200cهای پیشنهادی"""
        try:
            return await self.db.get_suggested_count(mode)
        except Exception as e:
            logger.error(f'Error getting suggested count: {e}')
            return 0

    @log_user_action('view_suggested')
    async def get_suggested_for_display(self, mode: str) -> List[Dict]:
        """دریافت اتچمنت\u200cهای پیشنهادی برای نمایش به کاربر
        
        Args:
            mode: 'br' یا 'mp'
            
        Returns:
            لیست تاپل\u200cها: (category, weapon_name, mode, attachment_dict)
        """
        try:
            items = await self.db.get_suggested_attachments(mode)
            logger.info(f'Retrieved {len(items)} suggested attachments for mode {mode}')
            return items
        except Exception as e:
            logger.error(f'Error getting suggested attachments for display: {e}')
            return []

    def format_suggested_list_text(self, items: List[Dict], mode: str, page: int=1) -> str:
        """فرمت کردن متن لیست پیشنهادی\u200cها
        
        Args:
            items: لیست اتچمنت\u200cها
            mode: 'br' یا 'mp'
            page: شماره صفحه
        """
        if not items:
            return f'❌ هیچ اتچمنت پیشنهادی برای {GAME_MODES.get(mode, mode)} وجود ندارد.'
        mode_name = GAME_MODES.get(mode, mode)
        total_items = len(items)
        total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        page_items = items[start_idx:end_idx]
        text_lines = [f'💡 **اتچمنت\u200cهای پیشنهادی {mode_name}**', f'📊 صفحه {page} از {total_pages} | نمایش {start_idx + 1}-{end_idx} از {total_items}', '➖➖➖➖➖➖➖➖➖➖➖➖\n']
        for idx, item in enumerate(page_items, start=start_idx + 1):
            from config.config import WEAPON_CATEGORIES
            category = (item or {}).get('category')
            weapon = (item or {}).get('weapon')
            attachment = (item or {}).get('attachment', {})
            cat_name = WEAPON_CATEGORIES.get(category, category)
            priority_emoji = self._get_priority_emoji(attachment.get('priority', DEFAULT_PRIORITY))
            text_lines.append(f'{idx}. {priority_emoji} **{weapon}** ({cat_name})')
            text_lines.append(f"   📎 {attachment.get('name')}")
            text_lines.append(f"   🔤 کد: `{attachment.get('code')}`")
            reason = attachment.get('reason')
            if reason:
                text_lines.append(f'   💭 دلیل: {reason}')
            text_lines.append('')
        return '\n'.join(text_lines)

    def _get_priority_emoji(self, priority: int) -> str:
        """دریافت emoji مناسب برای اولویت"""
        if priority <= 100:
            return '🔥'
        elif priority <= 300:
            return '⭐'
        elif priority <= 500:
            return '💫'
        else:
            return '✨'

    async def send_suggested_gallery(self, update: Update, context: CustomContext, mode: str) -> None:
        """ارسال گالری تصاویر اتچمنت\u200cهای پیشنهادی
        
        Args:
            update: آپدیت تلگرام
            context: کانتکست
            mode: 'br' یا 'mp'
        """
        try:
            items = await self.get_suggested_for_display(mode)
            mode_name = GAME_MODES.get(mode, mode)
            if not items:
                keyboard = [[InlineKeyboardButton('⬅️ بازگشت', callback_data='suggested_attachments')], [InlineKeyboardButton('🏠 منوی اصلی', callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                if update.callback_query:
                    await update.callback_query.edit_message_text(f'❌ هیچ اتچمنت پیشنهادی برای {mode_name} ثبت نشده است.', reply_markup=reply_markup)
                else:
                    await update.message.reply_text(f'❌ هیچ اتچمنت پیشنهادی برای {mode_name} ثبت نشده است.', reply_markup=reply_markup)
                return
            start_message = f'🎯 در حال ارسال {len(items)} اتچمنت پیشنهادی {mode_name}...'
            if update.callback_query:
                query = update.callback_query
                await query.answer()
                msg = await query.message.reply_text(start_message)
            else:
                msg = await update.message.reply_text(start_message)
            media_groups = []
            current_group = []
            for item in items:
                attachment = (item or {}).get('attachment', {})
                if attachment.get('image'):
                    from config.config import WEAPON_CATEGORIES
                    category = (item or {}).get('category')
                    weapon = (item or {}).get('weapon')
                    cat_name = WEAPON_CATEGORIES.get(category, category)
                    caption = f"🔫 **{weapon}** ({cat_name})\n📎 {attachment.get('name')}\n🔤 کد: {attachment.get('code')}"
                    reason = attachment.get('reason')
                    if reason:
                        caption += f'\n💭 {reason}'
                    media = InputMediaPhoto(media=attachment.get('image'), caption=caption[:1024])
                    current_group.append(media)
                    if len(current_group) == 10:
                        media_groups.append(current_group)
                        current_group = []
            if current_group:
                media_groups.append(current_group)
            for group in media_groups:
                try:
                    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=group)
                except Exception as e:
                    logger.error(f'Error sending media group: {e}')
            try:
                await msg.delete()
            except Exception as e:
                logger.warning(f'Failed to delete suggested start message: {e}')
            keyboard = [[InlineKeyboardButton('📋 نمایش لیست', callback_data=f'suggested_list_mode_{mode}')], [InlineKeyboardButton('⬅️ بازگشت', callback_data='suggested_attachments')], [InlineKeyboardButton('🏠 منوی اصلی', callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f'✅ پایان فهرست اتچمنت\u200cهای پیشنهادی {mode_name}', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f'Error sending suggested gallery: {e}')
            await update.effective_message.reply_text('❌ خطا در ارسال اتچمنت\u200cهای پیشنهادی. لطفاً دوباره تلاش کنید.')

    def build_suggested_keyboard(self, items: List[Dict], page: int, mode: str) -> InlineKeyboardMarkup:
        """ساخت کیبورد برای لیست پیشنهادی\u200cها
        
        Args:
            items: لیست اتچمنت\u200cها
            page: شماره صفحه فعلی
            mode: 'br' یا 'mp'
        """
        keyboard = []
        total_items = len(items)
        total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton('◀️ قبلی', callback_data=f'sugglist_page_{page - 1}'))
            nav_buttons.append(InlineKeyboardButton(f'📄 {page}/{total_pages}', callback_data='noop'))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton('▶️ بعدی', callback_data=f'sugglist_page_{page + 1}'))
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton('⬅️ بازگشت', callback_data='suggested_attachments')])
        keyboard.append([InlineKeyboardButton('🏠 منوی اصلی', callback_data='main_menu')])
        return InlineKeyboardMarkup(keyboard)