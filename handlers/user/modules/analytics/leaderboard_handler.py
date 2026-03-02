from core.context import CustomContext
from core.container import get_container
"""
Leaderboard Handler - Displays top contributors
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.user.base_user_handler import BaseUserHandler
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text
from html import escape

logger = get_logger('leaderboard', 'user.log')

class LeaderboardHandler(BaseUserHandler):
    """مدیریت بخش برترین کاربران (Leaderboard)"""
    
    async def show_leaderboard(self, update: Update, context: CustomContext):
        """نمایش لیست برترین کاربران بر اساس فعالیت"""
        query = update.callback_query
        if query:
            await query.answer()
            
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # دریافت لیست از ریپازیتوری (10 نفر برتر 30 روز اخیر)
        leaderboard = await get_container().analytics.get_user_leaderboard(days=30, limit=10)
        
        if not leaderboard:
            text = t("leaderboard.empty", lang)
        else:
            # هدر لیست
            title = escape(t("leaderboard.title", lang))
            period = escape(t("leaderboard.period_30d", lang))
            text = f"🏆 <b>{title}</b>\n"
            text += f"📅 {period}\n\n"
            
            medals = ["🥇", "🥈", "🥉", "🏅"]
            for i, entry in enumerate(leaderboard):
                rank = i + 1
                icon = medals[i] if i < 3 else medals[3]
                user_id = entry.get('user_id')
                username = entry.get('username')
                first_name = entry.get('first_name')
                score = int(entry.get('score', 0))
                
                # تعیین نام نمایشی
                if username:
                    display_name = f"@{escape(username)}"
                elif first_name:
                    display_name = escape(first_name)
                else:
                    display_name = f"User_{str(user_id)[-4:]}"
                
                # امتیازدهی: بازدید، کپی، رأی
                text += f"{icon} {rank}. <b>{display_name}</b> — <code>{score}</code> {escape(t('leaderboard.points', lang))}\n"
            
            text += f"\n💡 {escape(t('leaderboard.footer_hint', lang))}"
        
        keyboard = [
            [InlineKeyboardButton(t("common.retry", lang), callback_data="leaderboard")],
            [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await safe_edit_message_text(query, text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
