from core.context import CustomContext
from core.container import get_container
"""
Admin Feedback Dashboard - مدیریت و گزارش\u200cهای بازخورد اتچمنت\u200cها

✨ Updated: 2025-01-17
- Added sql_helpers for cross-database date queries
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.config import CATEGORIES, WEAPON_CATEGORIES, GAME_MODES
from utils.logger import log_user_action, get_logger
from utils.i18n import t
from utils.language import get_user_lang
from handlers.admin.modules.base_handler import BaseAdminHandler
from datetime import datetime, timedelta
from core.database.sql_helpers import get_date_interval, get_datetime_interval
import io
import urllib.parse
from utils.chart_gen import ChartGenerator
logger = get_logger('admin', 'admin.log')

class FeedbackAdminHandler(BaseAdminHandler):
    """مدیریت گزارش\u200cهای بازخورد برای ادمین\u200cها"""

    @log_user_action('feedback_dashboard')
    async def show_feedback_dashboard(self, update: Update, context: CustomContext):
        """نمایش منوی اصلی داشبورد بازخورد"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        suggested_only = context.user_data.get('fb_suggested_only', False)
        
        # استفاده از متد جدید ریپازیتوری
        stats = await self.db.analytics.get_attachment_feedback_stats(suggested_only=suggested_only, days=30)
        
        # Calculate engagement metrics
        total_votes = stats['total_votes']
        total_views = stats['total_views']
        engagement_rate = (total_votes / total_views * 100) if total_views > 0 else 0
        like_rate = (stats['total_likes'] / total_votes * 100) if total_votes > 0 else 0
        
        # Create a visual status summary
        def get_bar(percentage):
            filled = min(10, int(percentage / 10))
            return "🟩" * filled + "⬜" * (10 - filled)

        text = t('admin.feedback.dashboard.title', lang) + '\n\n'
        text += f"📊 **Overview (Global)**\n"
        text += f"👥 Active Users: `{stats['active_users']}`\n"
        text += f"👁 Total Views: `{total_views:,}`\n"
        text += f"🗳 Total Votes: `{total_votes:,}`\n"
        text += f"💬 Comments: `{stats['total_feedbacks']}`\n\n"
        
        text += f"📈 **Engagement: {engagement_rate:.1f}%**\n"
        text += f"{get_bar(engagement_rate * 5)} (Relative to 20% max)\n\n" # Scaled for visibility
        
        text += f"👍 **Approval: {like_rate:.1f}%**\n"
        text += f"{get_bar(like_rate)}\n\n"
        
        text += t('admin.feedback.dashboard.period.label', lang, days=30) + '\n\n' + t('admin.feedback.dashboard.choose_report', lang)
        
        status_word = t('common.enabled_word', lang) if suggested_only else t('common.disabled_word', lang)
        toggle_text = t('admin.feedback.dashboard.toggle', lang, status=status_word)
        keyboard = [
            [InlineKeyboardButton(toggle_text, callback_data='fb_toggle_suggested')],
            [InlineKeyboardButton(t('admin.feedback.buttons.period', lang), callback_data='fb_change_period')],
            [InlineKeyboardButton(t('admin.feedback.buttons.top', lang), callback_data='fb_top'), 
             InlineKeyboardButton(t('admin.feedback.buttons.bottom', lang), callback_data='fb_bottom')],
            [InlineKeyboardButton(t('admin.feedback.buttons.comments', lang), callback_data='fb_comments'), 
             InlineKeyboardButton(t('admin.feedback.buttons.trend', lang, default='📈 Weekly Trend'), callback_data='fb_trend')],
            [InlineKeyboardButton(t('admin.feedback.buttons.search', lang), callback_data='fb_search'), 
             InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='admin_menu_return')]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    @log_user_action('feedback_top_attachments')
    async def show_top_attachments(self, update: Update, context: CustomContext):
        """نمایش محبوب‌ترین اتچمنت‌ها"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        period = context.user_data.get('fb_period', 30)
        mode = context.user_data.get('fb_mode')
        category = context.user_data.get('fb_category')
        suggested_only = context.user_data.get('fb_suggested_only', False)
        popular = await self.db.get_popular_attachments(limit=10, days=period, mode=mode, category=category, suggested_only=suggested_only)
        if not popular:
            text = t('admin.feedback.top.empty', lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        else:
            text = t('admin.feedback.top.title', lang, days=period) + '\n\n'
            for idx, item in enumerate(popular, 1):
                likes = item.get('likes', 0) or 0
                dislikes = item.get('dislikes', 0) or 0
                views = item.get('views', 0) or 0
                net_score = likes - dislikes
                total_votes = likes + dislikes
                like_ratio = likes / total_votes * 100 if total_votes > 0 else 0
                text += f"**{idx}. {item['name']}**\n"
                text += f"   🔤 کد: `{item['code']}`\n"
                text += f"   🔫 سلاح: {item['weapon']} ({CATEGORIES.get(item['category'], item['category'])})\n"
                text += f'   👍 {likes} | 👎 {dislikes} (نمره: {net_score:+d})\n'
                text += f'   📊 نسبت: {like_ratio:.1f}% | 👁 {views:,} بازدید\n\n'
            filters = []
            if mode:
                filters.append('🎮 ' + t(f'mode.{mode}_short', lang))
            if category:
                filters.append('📂 ' + t(f'category.{category}', lang))
            if filters:
                text += f"\n🔍 **فیلتر فعال**: {' | '.join(filters)}\n"
            keyboard = [[InlineKeyboardButton(t('admin.feedback.buttons.change_period', lang), callback_data='fb_change_period')], [InlineKeyboardButton(t('admin.feedback.buttons.filter_mode', lang), callback_data='fb_filter_mode')], [InlineKeyboardButton(t('admin.feedback.buttons.filter_category', lang), callback_data='fb_filter_category')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        await query.edit_message_text(text[:4096], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    @log_user_action('feedback_bottom_attachments')
    async def show_bottom_attachments(self, update: Update, context: CustomContext):
        """نمایش کم‌بازدیدترین یا منفی‌ترین اتچمنت‌ها"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        period = context.user_data.get('fb_period', 30)
        mode = context.user_data.get('fb_mode')
        category = context.user_data.get('fb_category')
        suggested_only = context.user_data.get('fb_suggested_only', False)
        popular = await self.db.get_popular_attachments(limit=100, days=period, mode=mode, category=category, suggested_only=suggested_only)
        negative = [item for item in popular if item['likes'] - item['dislikes'] < 0]
        negative.sort(key=lambda x: x['likes'] - x['dislikes'])
        if not negative:
            text = t('admin.feedback.bottom.none', lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        else:
            text = t('admin.feedback.bottom.title', lang, days=period) + '\n\n'
            text += t('admin.feedback.bottom.note', lang) + '\n\n'
            for idx, item in enumerate(negative[:10], 1):
                net_score = item['likes'] - item['dislikes']
                text += f"**{idx}. {item['name']}**\n"
                text += f"   🔤 کد: `{item['code']}`\n"
                text += f"   🔫 سلاح: {item['weapon']}\n"
                text += f"   👍 {item['likes']} | 👎 {item['dislikes']} (نمره: {net_score:+d})\n"
                text += f"   👁 {item['views']:,} بازدید\n\n"
            text += '\n💡 **پیشنهاد**: این اتچمنت‌ها ممکن است نیاز به بازبینی داشته باشند.\n'
            keyboard = [[InlineKeyboardButton(t('admin.feedback.buttons.change_period', lang), callback_data='fb_change_period')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        await query.edit_message_text(text[:4096], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    @log_user_action('feedback_search_menu')
    async def show_search_menu(self, update: Update, context: CustomContext):
        """نمایش منوی جستجو: محبوب‌ترین جستجوها + ابزار فیلتر"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        try:
            popular = await self.db.get_popular_searches(limit=10)
        except Exception:
            popular = []
        text = t('admin.feedback.search.menu.title', lang) + '\n\n' + t('admin.feedback.search.menu.desc', lang) + '\n\n'
        keyboard = []
        if popular:
            for q in popular:
                enc = urllib.parse.quote_plus(q)
                label = q if len(q) <= 25 else q[:25] + '…'
                keyboard.append([InlineKeyboardButton(t('admin.feedback.search.buttons.popular', lang, q=label), callback_data=f'fb_search_q_{enc}')])
        else:
            text += t('admin.feedback.search.menu.no_popular', lang) + '\n\n'
        keyboard.append([InlineKeyboardButton(t('admin.feedback.buttons.filter_mode', lang), callback_data='fb_filter_mode')])
        keyboard.append([InlineKeyboardButton(t('admin.feedback.buttons.filter_category', lang), callback_data='fb_filter_category')])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    @log_user_action('feedback_search_exec')
    async def execute_search_query(self, update: Update, context: CustomContext):
        """اجرای جستجو و نمایش نتایج (تا 10 مورد)"""
        query = update.callback_query
        await query.answer()
        raw = query.data.replace('fb_search_q_', '')
        qtext = urllib.parse.unquote_plus(raw)
        lang = await get_user_lang(update, context, self.db) or 'fa'
        results = []
        try:
            results = await self.db.search_attachments(qtext)
        except Exception as e:
            logger.error(f'Error searching attachments: {e}')
            results = []
        if not results:
            text = t('admin.feedback.search.results.none', lang, query=qtext)
        else:
            text = t('admin.feedback.search.results.title', lang, query=qtext) + '\n\n'
            for category, weapon, mode, att in results[:10]:
                name = att.get('name')
                code = att.get('code')
                mode_disp = t(f'mode.{mode}_short', lang)
                cat_disp = t(f'category.{category}', lang)
                text += f'• {name} — `{code}`\n   🔫 {weapon} | 📂 {cat_disp} | 🎮 {mode_disp}\n\n'
        keyboard = [[InlineKeyboardButton(t('admin.feedback.search.buttons.popular_back', lang), callback_data='fb_search')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        await query.edit_message_text(text[:4096], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def filter_mode_menu(self, update: Update, context: CustomContext):
        """نمایش منوی فیلتر مود (BR/MP/همه)"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [[InlineKeyboardButton(t('mode.br_short', lang), callback_data='fb_mode_br'), InlineKeyboardButton(t('mode.mp_short', lang), callback_data='fb_mode_mp')], [InlineKeyboardButton(t('mode.all', lang), callback_data='fb_mode_all')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_top')]]
        await query.edit_message_text(t('mode.choose', lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def set_mode_filter(self, update: Update, context: CustomContext):
        """تنظیم فیلتر مود و بازگشت به گزارش محبوب‌ترین"""
        query = update.callback_query
        await query.answer()
        mode = query.data.replace('fb_mode_', '')
        if mode == 'all':
            context.user_data.pop('fb_mode', None)
        else:
            context.user_data['fb_mode'] = mode
        await self.show_top_attachments(update, context)

    async def filter_category_menu(self, update: Update, context: CustomContext):
        """نمایش منوی فیلتر دسته‌ها"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = []
        for key, _ in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(t(f'category.{key}', 'en'), callback_data=f'fb_cat_{key}')])
        keyboard.append([InlineKeyboardButton(t('admin.feedback.filter.category.clear', lang), callback_data='fb_cat_clear')])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_top')])
        await query.edit_message_text(t('category.choose', lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def set_category_filter(self, update: Update, context: CustomContext):
        """تنظیم فیلتر دسته و بازگشت به گزارش محبوب‌ترین"""
        query = update.callback_query
        await query.answer()
        data = query.data.replace('fb_cat_', '')
        if data == 'clear':
            context.user_data.pop('fb_category', None)
        else:
            context.user_data['fb_category'] = data
        await self.show_top_attachments(update, context)

    @log_user_action('feedback_comments')
    async def show_user_comments(self, update: Update, context: CustomContext):
        """نمایش نظرات متنی کاربران"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data and query.data.startswith('fb_comments_page_'):
            try:
                page = int(query.data.replace('fb_comments_page_', ''))
                context.user_data['fb_comments_page'] = page
            except Exception:
                page = context.user_data.get('fb_comments_page', 1)
        else:
            page = context.user_data.get('fb_comments_page', 1)
            
        per_page = 5
        suggested_only = context.user_data.get('fb_suggested_only', False)
        
        # استفاده از متد جدید ریپازیتوری
        feedbacks = await self.db.analytics.get_attachment_feedback_list(page=page, per_page=per_page, suggested_only=suggested_only)
        
        if not feedbacks['items']:
            text = t('admin.feedback.comments.empty', lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        else:
            text = t('admin.feedback.comments.title', lang, page=page, total_pages=feedbacks['total_pages']) + '\n\n'
            for item in feedbacks['items']:
                fb_text = item['feedback'] or ''
                feedback_preview = fb_text[:150] + '...' if len(fb_text) > 150 else fb_text
                
                if item.get('username'):
                    display = f"@{item['username']}"
                    user_link = f"[{display}](https://t.me/{item['username']})"
                else:
                    display = f"User {item['user_id']}"
                    user_link = f"[{display}](tg://user?id={item['user_id']})"
                
                # تحلیل معنایی با متد بهبود یافته
                sentiment = await self.db.support.analyze_sentiment(fb_text)
                sentiment_emoji = {'positive': '🟢', 'negative': '🔴', 'neutral': '⚪'}.get(sentiment, '⚪')
                
                # فرمت تاریخ
                date_str = item['last_view_date'].strftime('%Y-%m-%d') if isinstance(item['last_view_date'], datetime) else str(item['last_view_date'])[:10]
                
                text += f'👤 {user_link} {sentiment_emoji}\n'
                text += f"📎 {item['attachment_name']} — `{item['code']}`\n"
                text += f'💬 {feedback_preview}\n'
                text += f"📅 {date_str}\n"
                text += '➖➖➖➖➖\n\n'
                
            keyboard = []
            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton(t('nav.prev', lang), callback_data=f'fb_comments_page_{page - 1}'))
            nav_row.append(InlineKeyboardButton(t('pagination.page_of', lang, page=page, total=feedbacks['total_pages']), callback_data='noop'))
            if page < feedbacks['total_pages']:
                nav_row.append(InlineKeyboardButton(t('nav.next', lang), callback_data=f'fb_comments_page_{page + 1}'))
            if nav_row:
                keyboard.append(nav_row)
            keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')])
            
        await query.edit_message_text(text[:4096], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

    @log_user_action('feedback_weekly_trend')
    async def show_weekly_trend(self, update: Update, context: CustomContext):
        """نمایش روند هفتگی و آمار تفصیلی"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        suggested_only = context.user_data.get('fb_suggested_only', False)
        
        # استفاده از متدهای ریپازیتوری
        stats_by_category = await self.db.analytics.get_attachment_stats_by_category(suggested_only=suggested_only)
        stats_by_mode = await self.db.analytics.get_attachment_stats_by_mode(suggested_only=suggested_only)
        weekly = await self.db.analytics.get_attachment_weekly_trend(suggested_only=suggested_only)
        
        text = t('admin.feedback.detailed.title', lang) + '\n\n'
        
        text += t('admin.feedback.detailed.modes.title', lang) + '\n'
        for data in stats_by_mode:
            mode_name = t(f"mode.{data['mode']}_btn", lang)
            text += t('admin.feedback.detailed.modes.line', lang, mode=mode_name, votes=data['votes'], likes=data['likes'], dislikes=data['dislikes']) + '\n'
            
        text += '\n' + t('admin.feedback.detailed.categories.title', lang) + '\n'
        for data in stats_by_category:
            cat_name = data['category']
            attachments = data['attachments'] or 0
            avg_score = (data['likes'] - data['dislikes']) / max(attachments, 1)
            text += t('admin.feedback.detailed.categories.line', lang, category=cat_name, attachments=attachments, avg=f'{avg_score:+.1f}') + '\n'
            
        text += '\n📅 **روند هفتگی:**\n'
        
        # Generate Visual Chart
        chart_gen = ChartGenerator(title="Weekly Engagement Trend")
        chart_data = [(w['week_label'], float(w['votes'])) for w in weekly[-8:]] # Last 8 weeks
        chart_buf = chart_gen.generate_bar_chart(chart_data, title=t('admin.feedback.detailed.trend_chart', lang, default='Weekly Voting Trend'))
        
        caption = text[:1024]
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_dashboard')]]
        
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart_buf,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    @log_user_action('feedback_change_period')
    async def change_period(self, update: Update, context: CustomContext):
        """تغییر بازه زمانی گزارش‌ها"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        text = t('admin.feedback.period.title', lang)
        keyboard = [[InlineKeyboardButton(t('admin.feedback.period.7', lang), callback_data='fb_period_7')], [InlineKeyboardButton(t('admin.feedback.period.30', lang), callback_data='fb_period_30')], [InlineKeyboardButton(t('admin.feedback.period.90', lang), callback_data='fb_period_90')], [InlineKeyboardButton(t('admin.feedback.period.all', lang), callback_data='fb_period_all')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='fb_top')]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def set_period(self, update: Update, context: CustomContext):
        """ذخیره بازه زمانی انتخابی"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        period_str = query.data.replace('fb_period_', '')
        if period_str == 'all':
            period = 36500
            context.user_data['fb_period'] = period
            await query.answer(t('admin.feedback.period.set_all', lang))
        else:
            period = int(period_str)
            context.user_data['fb_period'] = period
            await query.answer(t('admin.feedback.period.set_days', lang, days=period))
        await self.show_top_attachments(update, context)

    @log_user_action('feedback_toggle_suggested')
    async def toggle_suggested_only(self, update: Update, context: CustomContext):
        """روشن/خاموش کردن فیلتر «فقط پیشنهادی‌ها»"""
        query = update.callback_query
        await query.answer()
        current = context.user_data.get('fb_suggested_only', False)
        context.user_data['fb_suggested_only'] = not current
        await self.show_feedback_dashboard(update, context)