from core.context import CustomContext
from core.container import get_container
"""
Attachment Analytics Dashboard
Admin interface for viewing attachment performance analytics

✨ Updated: 2025-01-17
- Added sql_helpers for cross-database date queries
- Ready for PostgreSQL migration
"""

import os
import io
import csv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import ADMIN_MENU
from core.security.role_manager import Permission
from core.database.database_adapter import DatabaseAdapter
from utils.logger import get_logger
from core.database.sql_helpers import get_date_interval, get_current_date
from utils.i18n import t
from config.config import WEAPON_CATEGORIES
from utils.language import get_user_lang

logger = get_logger('attachments_dashboard', 'admin.log')

ANALYTICS_MENU, VIEW_TRENDING, VIEW_WEAPON_STATS, VIEW_UNDERPERFORMING, SEARCH_ATTACH = range(5)

class AttachmentsDashboardHandler(BaseAdminHandler):
    """Handler for attachment analytics dashboard"""
    
    def __init__(self, db: DatabaseAdapter):
        """Initialize handler"""
        super().__init__(db)
        # role_manager is already created in BaseAdminHandler
        # ✨ Updated: Pass DatabaseAdapter instead of db_path
    
    def _escape_markdown(self, text: str) -> str:
        """
        Escape markdown special characters in text (for Markdown parse mode)
        Only escapes the most problematic characters
        """
        if not text:
            return text
        # Escape only essential markdown characters
        escape_chars = ['_', '*', '[', ']', '`']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def _safe_edit_message(self, query, message: str, keyboard, parse_mode=ParseMode.MARKDOWN):
        """
        Safely edit message with error handling for "Message is not modified"
        """
        try:
            await query.edit_message_text(
                message,
                parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            # Ignore "Message is not modified" error
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing message: {e}")
        
    async def analytics_menu(self, update: Update, context: CustomContext) -> int:
        """Show main analytics menu"""
        query = update.callback_query
        if query:
            await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
            
        # Check permissions
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            await self.send_permission_denied(update, context)
            return ConversationHandler.END
            
        # ✅ DB Audit Logging - Dashboard Access
        await self.audit.log_action(
            admin_id=update.effective_user.id,
            action="VIEW_ANALYTICS_DASHBOARD",
            target_id="analytics",
            details={"target_type": "system"}
        )

        # Get overview statistics
        stats = await get_container().analytics.get_overview_stats(days=30)
        
        # Build message
        message = t('admin.analytics.menu.title', lang) + "\n\n"
        message += t('admin.analytics.menu.overview.header', lang, days=30) + "\n"
        message += t('admin.analytics.menu.overview.views', lang, n=stats.get('total_views', 0)) + "\n"
        message += t('admin.analytics.menu.overview.clicks', lang, n=stats.get('total_clicks', 0)) + "\n"
        message += t('admin.analytics.menu.overview.shares', lang, n=stats.get('total_shares', 0)) + "\n"
        message += t('admin.analytics.menu.overview.users', lang, n=stats.get('unique_users', 0)) + "\n"
        message += t('admin.analytics.menu.overview.engagement', lang, rate=f"{stats.get('engagement_rate', 0):.1f}") + "\n\n"
        
        message += t('admin.analytics.menu.top.header', lang) + "\n"
        if stats.get('top_performer'):
            safe_name = self._escape_markdown(stats['top_performer']['name'])
            message += t('admin.analytics.menu.top.most_viewed', lang, name=safe_name, views=stats['top_performer']['views']) + "\n"
        if stats.get('most_engaging'):
            safe_name = self._escape_markdown(stats['most_engaging']['name'])
            message += t('admin.analytics.menu.top.most_engaging', lang, name=safe_name, rate=f"{stats['most_engaging']['rate']:.1f}") + "\n"
        if stats.get('highest_rated'):
            safe_name = self._escape_markdown(stats['highest_rated']['name'])
            message += t('admin.analytics.menu.top.highest_rated', lang, name=safe_name, rating=f"{stats['highest_rated']['rating']:.1f}") + "\n"
            
        # Build keyboard (implemented handlers)
        context.user_data.pop('analytics_search_mode', None)
        keyboard = [
            [
                InlineKeyboardButton(t('admin.analytics.buttons.trending', lang), callback_data="analytics_view_trending"),
                InlineKeyboardButton(t('admin.analytics.buttons.underperforming', lang), callback_data="analytics_view_underperforming")
            ],
            [
                InlineKeyboardButton(t('admin.analytics.buttons.weapon_stats', lang), callback_data="analytics_view_weapon_stats"),
                InlineKeyboardButton(t('admin.analytics.buttons.search_attachment', lang), callback_data="analytics_search_attachment")
            ],
            [
                InlineKeyboardButton(t('admin.analytics.buttons.daily_report', lang), callback_data="analytics_daily_report"),
                InlineKeyboardButton(t('admin.analytics.buttons.download_report', lang), callback_data="analytics_download_report")
            ],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="admin_menu_return")]
        ]
        
        if query:
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        return ADMIN_MENU
        
    def _get_db_connection(self):
        """Helper method to get database connection"""
        if hasattr(self.db, 'get_connection'):
            # Via DatabaseAdapter forwarding to PostgreSQL pool
            return self.db.get_connection()
        else:
            raise RuntimeError("Database connection not available")
    
    async def analytics_cohort_analysis(self, update: Update, context: CustomContext) -> int:
        """Show cohort retention analysis"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()

        cohorts = await get_container().analytics.get_cohort_retention(weeks=4)
        
        message = "📊 *Cohort Retention Analysis*\n"
        message += "_Tracking user activity by their first seen week_\n\n"
        
        if not cohorts:
            message += "No cohort data available yet."
        else:
            message += "```\n"
            message += "Cohort | Size | W1  | W2  | W3  | W4\n"
            message += "-------|------|-----|-----|-----|-----\n"
            for c in cohorts:
                w1 = f"{c['week_1']}%" if c['week_1'] else "-"
                w2 = f"{c['week_2']}%" if c['week_2'] else "-"
                w3 = f"{c['week_3']}%" if c['week_3'] else "-"
                w4 = f"{c['week_4']}%" if c['week_4'] else "-"
                message += f"{c['cohort']:<6} | {c['size']:<4} | {w1:<3} | {w2:<3} | {w3:<3} | {w4:<3}\n"
            message += "```"
            
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

        
    async def view_trending(self, update: Update, context: CustomContext) -> int:
        """ترندینگ - Real-Time با منطق ساده"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.analytics.loading', lang))

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            await self.send_permission_denied(update, context)
            return ConversationHandler.END
        
        # Add timestamp to prevent "Message is not modified" error
        now = datetime.now().strftime('%H:%M:%S')
        
        message = t('admin.analytics.trending.title', lang) + "\n"
        message += t('admin.analytics.trending.subtitle', lang) + "\n"
        message += t('admin.analytics.trending.updated', lang, time=now) + "\n\n"
        results = []
        try:
            # Use unified repository method directly
            results = await get_container().analytics.get_trending_growth_stats(limit=10)
            
            if results:
                # Display trending results with growth
                for i, result in enumerate(results, 1):
                    name = result['name']
                    weapon = result['weapon']
                    views = result['views']
                    growth = result['growth_rate']
                    
                    medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
                    if growth >= 100:
                        icon = "🔥"
                    elif growth >= 50:
                        icon = "📈"
                    else:
                        icon = "📊"
                    safe_name = self._escape_markdown(name)
                    safe_weapon = self._escape_markdown(weapon)
                    message += f"{medal} *{safe_name}*\n"
                    message += t('admin.analytics.lines.weapon', lang, weapon=safe_weapon) + "\n"
                    message += t('admin.analytics.lines.growth', lang, icon=icon, value=f"{growth:+.0f}") + "\n"
                    message += t('admin.analytics.lines.views', lang, value=f"{views:,}") + "\n\n"
            else:
                message += t('admin.analytics.fallback.no_data', lang) + "\n"
        except Exception as e:
            logger.error(f"Error in view_trending: {e}")
            message = t('admin.analytics.trending.error.title', lang) + "\n\n" + t('admin.analytics.trending.error.body', lang)

        keyboard = []
        if results:
            for i, r in enumerate(results, 1):
                try:
                    att_id = r['id']
                    title = f"{i}. {r['name']}"
                    keyboard.append([InlineKeyboardButton(title, callback_data=f"weapon_details_{att_id}")])
                except Exception:
                    continue
        keyboard.append([InlineKeyboardButton(t('menu.buttons.refresh', lang), callback_data="refresh_trending")])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")])
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    def _map_category_name_to_label(self, db_name: str) -> str:
        """Map DB category name to English+emoji label from WEAPON_CATEGORIES.
        Falls back to the original DB name if no match is found."""
        try:
            nm = (db_name or '').strip().lower()
            # try exact/contains match against emoji-stripped values
            for key, val in WEAPON_CATEGORIES.items():
                v = (val or '').strip()
                # remove leading emoji and whitespace if present
                parts = v.split(' ', 1)
                no_emoji = parts[1].strip() if len(parts) > 1 else v
                ve = no_emoji.lower()
                if nm == ve or nm in ve or ve in nm:
                    return v
        except Exception:
            pass
        return db_name
    
    async def weapon_stats_select_mode(self, update: Update, context: CustomContext) -> int:
        """Alias برای سازگاری با AdminHandlers: انتخاب مود"""
        return await self.ws_choose_mode(update, context)

    async def weapon_stats_show_results(self, update: Update, context: CustomContext) -> int:
        """Alias برای سازگاری با AdminHandlers: نمایش نتایج دسته انتخاب‌شده"""
        return await self.ws_choose_category(update, context)

    async def search_attachment_stats(self, update: Update, context: CustomContext) -> int:
        """نمایش UI جستجوی آمار اتچمنت و ورود به حالت دریافت متن"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            if query: await query.answer()
            await self.send_permission_denied(update, context)
            return ConversationHandler.END

        if query:
            await query.answer()
            message = t('admin.analytics.search.title', lang) + "\n\n"
            message += t('admin.analytics.search.help.header', lang) + "\n"
            message += t('admin.analytics.search.help.body', lang) + "\n\n"
            message += t('admin.analytics.search.prompt', lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
            await self._safe_edit_message(query, message, keyboard)
        # علامت‌گذاری برای حالت جستجو
        context.user_data['analytics_search_mode'] = True
        return ADMIN_MENU

    async def handle_search_text(self, update: Update, context: CustomContext) -> int:
        """دریافت متن جستجو و نمایش نتایج (ساده و امن)"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if not update.message:
            return ADMIN_MENU
        if not context.user_data.get('analytics_search_mode'):
            return ADMIN_MENU
        q = (update.message.text or '').strip()
        if not q:
            await update.message.reply_text(t('admin.analytics.search.prompt', lang))
            return ADMIN_MENU
        try:
            # نمایش وضعیت جستجو
            await update.message.reply_text(t('admin.analytics.search.searching', lang, query=q))
            
            rows = await get_container().analytics.get_attachment_search_results(q, limit=10)
            
            if not rows:
                await update.message.reply_text(
                    t('admin.analytics.search.no_results.title', lang) + "\n\n" + t('admin.analytics.search.no_results.tips', lang)
                )
                context.user_data.pop('analytics_search_mode', None)
                return ADMIN_MENU
            
            # ساخت پیام نتایج
            header = t('admin.analytics.search.results.header', lang, query=q)
            count = t('admin.analytics.search.results.count', lang, n=len(rows))
            lines = [header, count, ""]
            for r in rows:
                att = self._escape_markdown(r['attachment'])
                wpn = self._escape_markdown(r['weapon'])
                cat = self._escape_markdown(r['category'])
                views = f"{int(r['views']):,}"
                clicks = f"{int(r['clicks']):,}"
                lines.append(f"• *{att}*")
                lines.append(t('admin.analytics.search.lines.meta', lang, weapon=wpn, category=cat))
                lines.append(t('admin.analytics.search.lines.stats', lang, views=views, clicks=clicks))
                lines.append("")
            
            # کیبورد دکمه‌های جزئیات برای هر نتیجه
            keyboard = []
            for r in rows:
                try:
                    att_id = r['att_id']
                    title = f"ℹ {r['attachment']}"
                    keyboard.append([InlineKeyboardButton(title, callback_data=f"weapon_details_{att_id}")])
                except Exception:
                    continue
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
        except Exception as e:
            logger.error(f"Error in handle_search_text: {e}")
            await update.message.reply_text(
                t('admin.analytics.search.error.title', lang) + "\n\n" + t('admin.analytics.search.error.body', lang)
            )
        context.user_data.pop('analytics_search_mode', None)
        return ADMIN_MENU

    async def download_report(self, update: Update, context: CustomContext) -> int:
        """دانلود گزارش CSV 7 روز اخیر برای آمار اتچمنت‌ها"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            if query: await query.answer()
            await self.send_permission_denied(update, context)
            return ConversationHandler.END

        if not query:
            return ADMIN_MENU
        await query.answer()
        try:
            rows = await get_container().analytics.get_csv_report_data(days=7, limit=200)
            
            # ساخت CSV در حافظه
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Attachment','Weapon','Category','Views','Clicks','Users'])
            for r in rows:
                writer.writerow([
                    r['attachment'], r['weapon'], r['category'],
                    int(r['views'] or 0), int(r['clicks'] or 0), int(r['users'] or 0)
                ])
            data = io.BytesIO(output.getvalue().encode('utf-8'))
            output.close()
            filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(InputFile(data, filename=filename),
                                               caption=t('admin.analytics.weekly.title', lang))
        except Exception as e:
            logger.error(f"Error in download_report: {e}")
            await query.message.reply_text(t('admin.analytics.weekly.error.body', lang))
        return ADMIN_MENU

    async def daily_chart(self, update: Update, context: CustomContext) -> int:
        """نمایش نمودار متنی ۷ روز اخیر (Views/Clicks)"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            if query: await query.answer()
            await self.send_permission_denied(update, context)
            return ConversationHandler.END

        if not query:
            return ADMIN_MENU
        await query.answer()
        try:
            rows = await get_container().analytics.get_daily_breakdown(days=7)
            
            # تبدیل به دیکشنری برای پر کردن روزهای خالی
            from datetime import date as _date
            today = datetime.utcnow().date()
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            data_map = {str(r['date']): {'views': int(r['views'] or 0), 'clicks': int(r['clicks'] or 0)} for r in rows}
            series = []
            max_val = 0
            for d in days:
                key = str(d)
                v = data_map.get(key, {'views': 0, 'clicks': 0})
                series.append((key, v['views'], v['clicks']))
                max_val = max(max_val, v['views'])

            # رسم نمودار ساده ASCII
            chart = f"📊 *{t('admin.analytics.daily_chart.header', lang)}*\n\n"
            for date_str, views, clicks in series:
                day_label = date_str[5:] # MM-DD
                bar_len = int(views / max_val * 10) if max_val > 0 else 0
                bar = "▇" * bar_len + "░" * (10 - bar_len)
                chart += f"`{day_label}` {bar}  👁`{views}`  🖱`{clicks}`\n"
            
            chart += f"\n_{t('admin.analytics.daily_chart.footer', lang)}_"
            
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
            await self._safe_edit_message(query, chart, keyboard)
        except Exception as e:
            logger.error(f"Error in daily_chart: {e}")
            await query.message.reply_text(t('admin.analytics.daily.error.body', lang))
        return ADMIN_MENU

    async def download_daily_csv(self, update: Update, context: CustomContext) -> int:
        """دانلود CSV تجمیعی روزانه برای ۷ روز اخیر"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if not query:
            return ADMIN_MENU
        await query.answer()
        try:
            rows = await get_container().analytics.get_daily_breakdown(days=7)
            # کامل‌سازی روزهای خالی و ساخت CSV
            today = datetime.utcnow().date()
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            data_map = {str(r['date']): (int(r['views'] or 0), int(r['clicks'] or 0), int(r['users'] or 0)) for r in rows}
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date','Views','Clicks','Users'])
            for d in days:
                v, c, u = data_map.get(str(d), (0,0,0))
                writer.writerow([str(d), v, c, u])
            data = io.BytesIO(output.getvalue().encode('utf-8'))
            output.close()
            filename = f"daily_breakdown_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(InputFile(data, filename=filename),
                                               caption=t('admin.analytics.weekly.title', lang))
        except Exception as e:
            from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)
        return ADMIN_MENU

    async def weapon_details(self, update: Update, context: CustomContext) -> int:
        """نمایش جزئیات یک اتچمنت بر اساس شناسه در callback_data: weapon_details_<id>"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            if query: await query.answer()
            await self.send_permission_denied(update, context)
            return ConversationHandler.END

        if not query:
            return ADMIN_MENU
        await query.answer()
        data = query.data or ""
        att_id = None
        if data.startswith("weapon_details_"):
            try:
                att_id = int(data.split("_")[-1])
            except Exception:
                att_id = None
        if not att_id:
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
            await self._safe_edit_message(query, t('admin.analytics.weapon_stats.no_data.title', lang), keyboard)
            return ADMIN_MENU

        try:
            stats = await get_container().analytics.get_attachment_detailed_stats(att_id)
            if not stats:
                await query.answer(t('error.generic', lang), show_alert=True)
                return ADMIN_MENU
            
            meta = stats['attachment']
            summary_30 = stats['summary_30d']
            daily_rows = stats['daily_7d']
            
            views = summary_30['views']
            clicks = summary_30['clicks']
            users = summary_30['users']
            rate = (float(clicks)/float(views)*100) if views > 0 else 0.0

            # Compose message
            safe_att = self._escape_markdown(meta.get('name') or 'Unknown')
            safe_weapon = self._escape_markdown(meta.get('weapon_name') or 'Unknown')
            code = meta.get('code') or '-'
            mode_val = meta.get('mode') or ''
            mode_title = t('admin.analytics.weapon_stats.buttons.br', lang) if mode_val == 'br' else t('admin.analytics.weapon_stats.buttons.mp', lang) if mode_val == 'mp' else t('admin.analytics.weapon_stats.buttons.all', lang)

            message = f"🔫 *{safe_att}*\n"
            message += t('admin.analytics.lines.weapon', lang, weapon=safe_weapon) + "\n"
            message += t('admin.analytics.lines.code', lang, code=code) + "\n"
            message += t('admin.analytics.weapon_stats.mode', lang, mode=mode_title) + "\n\n"

            message += t('admin.analytics.weekly.summary.header', lang) + "\n"
            message += t('admin.analytics.weekly.summary.views', lang, n=f"{views:,}") + "\n"
            message += t('admin.analytics.weekly.summary.clicks', lang, n=f"{clicks:,}") + "\n"
            message += t('admin.analytics.weekly.summary.users', lang, n=f"{users:,}") + "\n"
            message += t('admin.analytics.weekly.summary.engagement', lang, rate=f"{rate:.1f}") + "\n\n"

            # 7d ASCII chart
            today = datetime.utcnow().date()
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            data_map = {str(r['date']): (int(r['views'] or 0), int(r['clicks'] or 0)) for r in daily_rows}
            max_val = max([v for (v, _) in data_map.values()], default=0)
            width = 24
            chart_lines = ["```"]
            for d in days:
                v, c = data_map.get(str(d), (0,0))
                bar_len = int((v / max_val) * width) if max_val > 0 else 0
                bar = '█' * bar_len
                chart_lines.append(f"{str(d)} | {bar:<{width}} {v:>5} / {c:>5}")
            chart_lines.append("```")
            message += "\n".join(chart_lines)
        except Exception as e:
            logger.error(f"Error in weapon_details: {e}")
            message = t('error.generic', lang)

        keyboard = [
            [InlineKeyboardButton(t('admin.analytics.buttons.daily_chart', lang), callback_data=f"att_daily_chart_{att_id}")],
            [InlineKeyboardButton(t('admin.analytics.buttons.download_csv', lang), callback_data=f"att_download_csv_{att_id}")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def att_daily_chart(self, update: Update, context: CustomContext) -> int:
        """نمودار متنی ۷ روز اخیر برای یک اتچمنت خاص: att_daily_chart_<id>"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if not query:
            return ADMIN_MENU
        await query.answer()
        data = query.data or ""
        att_id = None
        if data.startswith("att_daily_chart_"):
            try:
                att_id = int(data.split("_")[-1])
            except Exception:
                att_id = None
        if not att_id:
            await query.answer(t('error.generic', lang), show_alert=True)
            return ADMIN_MENU
        try:
            stats = await get_container().analytics.get_attachment_detailed_stats(att_id)
            if not stats:
                await query.answer(t('error.generic', lang), show_alert=True)
                return ADMIN_MENU
            
            att_name = self._escape_markdown(stats['attachment'].get('name') or 'Unknown')
            rows = stats['daily_7d']
            
            today = datetime.utcnow().date()
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            data_map = {str(r['date']): (int(r['views'] or 0), int(r['clicks'] or 0)) for r in rows}
            max_val = max([v for (v, _) in data_map.values()], default=0)
            width = 28
            lines = [t('admin.analytics.daily.title', lang) + f" — *{att_name}*", "", "```"]
            for d in days:
                v, c = data_map.get(str(d), (0,0))
                bar_len = int((v / max_val) * width) if max_val > 0 else 0
                bar = '█' * bar_len
                lines.append(f"{str(d)} | {bar:<{width}} {v:>5} / {c:>5}")
            lines.append("```")
            await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)
        return ADMIN_MENU

    async def att_download_csv(self, update: Update, context: CustomContext) -> int:
        """دانلود CSV روزانه ۷ روز اخیر برای یک اتچمنت خاص: att_download_csv_<id>"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if not query:
            return ADMIN_MENU
        await query.answer()
        data = query.data or ""
        att_id = None
        if data.startswith("att_download_csv_"):
            try:
                att_id = int(data.split("_")[-1])
            except Exception:
                att_id = None
        if not att_id:
            await query.answer(t('error.generic', lang), show_alert=True)
            return ADMIN_MENU
        try:
            stats = await get_container().analytics.get_attachment_detailed_stats(att_id)
            if not stats:
                await query.answer(t('error.generic', lang), show_alert=True)
                return ADMIN_MENU
            
            rows = stats['daily_7d']
            
            today = datetime.utcnow().date()
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            data_map = {str(r['date']): (int(r['views'] or 0), int(r['clicks'] or 0), int(r.get('users', 0))) for r in rows}
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date','Views','Clicks','Users'])
            for d in days:
                v, c, u = data_map.get(str(d), (0,0,0))
                writer.writerow([str(d), v, c, u])
            data_buf = io.BytesIO(output.getvalue().encode('utf-8'))
            output.close()
            filename = f"attachment_{att_id}_daily_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(InputFile(data_buf, filename=filename),
                                               caption=t('admin.analytics.daily.title', lang))
        except Exception as e:
            from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)
        return ADMIN_MENU
    
    async def view_user_behavior(self, update: Update, context: CustomContext) -> int:
        """آنالیز رفتار کاربران (خلاصه + هایلایت‌ها)"""
        query = update.callback_query
    async def view_user_behavior(self, update: Update, context: CustomContext) -> int:
        """آنالیز رفتار کاربران (خلاصه + هایلایت‌ها)"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            if query: await query.answer()
            await self.send_permission_denied(update, context)
            return ConversationHandler.END

        await query.answer(t('admin.analytics.user.loading', lang))
        
        message = t('admin.analytics.user.title', lang) + "\n\n"
        try:
            stats = await get_container().analytics.get_user_behavior_analytics(days=7)
            summary = stats['summary']
            
            total_users = summary['total_users_all_time']
            active_users = summary['active_users']
            views = summary['total_views']
            clicks = summary['total_clicks']

            avg_views = (float(views)/float(active_users)) if active_users > 0 else 0.0
            engagement_rate = (float(clicks)/float(views)*100) if views > 0 else 0.0

            # Summary lines
            message += t('admin.analytics.user.summary.header', lang) + "\n"
            message += t('admin.analytics.user.summary.total_users', lang, n=f"{total_users:,}") + "\n"
            message += t('admin.analytics.user.summary.active_7d', lang, n=f"{active_users:,}") + "\n"
            message += t('admin.analytics.user.summary.avg_views', lang, n=f"{avg_views:.1f}") + "\n"
            message += t('admin.analytics.user.summary.engagement', lang, rate=f"{engagement_rate:.1f}") + "\n\n"

            # Per-user stats (7d)
            per_user = stats.get('per_user_stats', [])
            very_active = [u for u in per_user if (int(u['views']) >= 50 or int(u['clicks']) >= 10)]
            active = [u for u in per_user if (10 <= int(u['views']) < 50 or 3 <= int(u['clicks']) < 10)]
            moderate_count = len([u for u in per_user if (int(u['views']) < 10 and int(u['clicks']) < 3)])

            if per_user:
                if very_active:
                    message += t('admin.analytics.user.group.very_active.header', lang) + "\n"
                    for item in very_active[:3]:
                        name = self._escape_markdown(f"#{item['user_id']}")
                        eng = (float(item['clicks'])/float(item['views'])*100) if int(item['views']) > 0 else 0.0
                        message += f"\n🥇 *{name}*\n"
                        message += t('admin.analytics.user.line.views', lang, n=f"{item['views']:,}") + "\n"
                        message += t('admin.analytics.user.line.clicks', lang, n=f"{item['clicks']:,}") + "\n"
                        message += t('admin.analytics.user.line.engagement', lang, rate=f"{eng:.0f}") + "\n"
                    message += "\n"

                if active:
                    message += t('admin.analytics.user.group.active.header', lang) + "\n"
                    for item in active[:2]:
                        name = self._escape_markdown(f"#{item['user_id']}")
                        message += t('admin.analytics.user.line.item', lang, name=name, views=f"{item['views']:,}", atts='-') + "\n"
                    message += "\n"

                if moderate_count > 0:
                    message += t('admin.analytics.user.group.moderate.count', lang, n=moderate_count) + "\n"
            else:
                message += t('admin.analytics.user.no_data.title', lang) + "\n\n" + t('admin.analytics.user.no_data.body', lang)
        except Exception as e:
            logger.error(f"Error in view_user_behavior: {e}")
            message = t('admin.analytics.user.error.title', lang) + "\n\n" + t('admin.analytics.user.error.body', lang)

        keyboard = [
            [InlineKeyboardButton(t('admin.analytics.buttons.more_details', lang), callback_data="user_behavior_details")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def user_behavior_details(self, update: Update, context: CustomContext) -> int:
        """جزئیات رفتار کاربران (توزیع و برترین‌ها)"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()

        message = t('admin.analytics.user_details.title', lang) + "\n\n"
        try:
            stats = await get_container().analytics.get_user_behavior_analytics(days=7)
            per_user = stats.get('per_user_stats', [])
            
            very = 0
            act = 0
            mod = 1 # avoid division by zero or empty list issues
            if per_user:
                mod = 0
                for r in per_user:
                    v = int(r['views'] or 0)
                    c = int(r['clicks'] or 0)
                    if v >= 50 or c >= 10:
                        very += 1
                    elif v >= 10 or c >= 3:
                        act += 1
                    else:
                        mod += 1

            total = very + act + mod
            if total > 0:
                message += t('admin.analytics.user_details.dist.header', lang) + "\n"
                def pct(x):
                    return f"{(x*100.0/total):.0f}"
                message += t('admin.analytics.user_details.dist.line', lang, icon='🔥', cat=t('admin.analytics.user_details.dist.cat.very_active', lang), count=very, pct=pct(very)) + "\n"
                message += t('admin.analytics.user_details.dist.line', lang, icon='⚡', cat=t('admin.analytics.user_details.dist.cat.active', lang), count=act, pct=pct(act)) + "\n"
                message += t('admin.analytics.user_details.dist.line', lang, icon='📊', cat=t('admin.analytics.user_details.dist.cat.moderate', lang), count=mod, pct=pct(mod)) + "\n\n"

            # Top attachments reach
            reach = stats.get('top_attachments_reach', [])
            if reach:
                message += t('admin.analytics.user_details.top.header', lang) + "\n"
                for i, row in enumerate(reach, 1):
                    medal = "🥇" if i==1 else "🥈" if i==2 else "🥉"
                    safe_name = self._escape_markdown(row['name'])
                    message += f"{medal} {safe_name} — {int(row['unique_users'])}\n"
                message += "\n"

            # Weekly active users
            weekly = stats['summary']['active_users']
            message += t('admin.analytics.user.summary.active_7d', lang, n=f"{weekly:,}") + "\n"
            
        except Exception as e:
            logger.error(f"Error in user_behavior_details: {e}")
            message = t('error.generic', lang)

        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU
    
    async def ws_back_to_categories(self, update: Update, context: CustomContext) -> int:
        """بازگشت به فهرست دسته‌ها برای مود انتخاب‌شده"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()
        
        data = context.user_data.get('ws_mode', 'ws_mode_all')
        mode_map = {
            'ws_mode_br': t('admin.analytics.weapon_stats.buttons.br', lang),
            'ws_mode_mp': t('admin.analytics.weapon_stats.buttons.mp', lang),
            'ws_mode_all': t('admin.analytics.weapon_stats.buttons.all', lang),
        }
        mode_title = mode_map.get(data, '')
        
        message = t('admin.analytics.weapon_stats.title', lang) + "\n"
        message += t('admin.analytics.weapon_stats.mode', lang, mode=mode_title) + "\n\n"
        message += t('admin.analytics.weapon_stats.choose_category', lang)
        
        try:
            cats = await get_container().analytics.get_weapon_categories()
        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            message = t('admin.analytics.weapon_stats.error.categories', lang)
            cats = []
        
        keyboard = []
        row = []
        for c in cats or []:
            _db_name = (c.get('name') or '').strip()
            title = self._escape_markdown(self._map_category_name_to_label(_db_name))
            row.append(InlineKeyboardButton(title, callback_data=f"ws_cat_{c['id']}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(t('admin.analytics.buttons.back_to_mode_selection', lang), callback_data="ws_back_to_mode")])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")])
        
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU
    
    async def view_weapon_stats(self, update: Update, context: CustomContext) -> int:
        """نمایش انتخاب مود برای آمار سلاح‌ها"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()

        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.VIEW_ANALYTICS):
            await self.send_permission_denied(update, context)
            return ConversationHandler.END
        
        message = t('admin.analytics.weapon_stats.title', lang) + "\n\n"
        message += t('admin.analytics.weapon_stats.choose_mode', lang)
        
        keyboard = [
            [
                InlineKeyboardButton(t('admin.analytics.weapon_stats.buttons.br', lang), callback_data="analytics_ws_mode_br"),
                InlineKeyboardButton(t('admin.analytics.weapon_stats.buttons.mp', lang), callback_data="analytics_ws_mode_mp")
            ],
            [InlineKeyboardButton(t('admin.analytics.weapon_stats.buttons.all', lang), callback_data="analytics_ws_mode_all")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def ws_choose_mode(self, update: Update, context: CustomContext) -> int:
        """پس از انتخاب مود، نمایش لیست دسته‌های سلاح"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_map = {
            'analytics_ws_mode_br': t('admin.analytics.weapon_stats.buttons.br', lang),
            'analytics_ws_mode_mp': t('admin.analytics.weapon_stats.buttons.mp', lang),
            'analytics_ws_mode_all': t('admin.analytics.weapon_stats.buttons.all', lang),
        }
        context.user_data['ws_mode'] = data
        mode_title = mode_map.get(data, 'All')
        
        message = t('admin.analytics.weapon_stats.title', lang) + "\n"
        message += t('admin.analytics.weapon_stats.mode', lang, mode=mode_title) + "\n\n"
        message += t('admin.analytics.weapon_stats.choose_category', lang)
        
        try:
            cats = await get_container().analytics.get_weapon_categories()
        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            message = t('admin.analytics.weapon_stats.error.categories', lang)
            cats = []
        
        keyboard = []
        row = []
        for c in cats or []:
            _db_name = (c.get('name') or '').strip()
            title = self._escape_markdown(self._map_category_name_to_label(_db_name))
            row.append(InlineKeyboardButton(title, callback_data=f"ws_cat_{c['id']}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(t('admin.analytics.buttons.back_to_mode_selection', lang), callback_data="ws_back_to_mode")])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")])
        
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def ws_choose_category(self, update: Update, context: CustomContext) -> int:
        """نمایش آمار کلی برای دسته انتخاب‌شده"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()
        
        cat_id = int(query.data.replace('ws_cat_', ''))
        mode_key = context.user_data.get('ws_mode', 'ws_mode_all')
        mode_map = {
            'ws_mode_br': t('admin.analytics.weapon_stats.buttons.br', lang),
            'ws_mode_mp': t('admin.analytics.weapon_stats.buttons.mp', lang),
            'ws_mode_all': t('admin.analytics.weapon_stats.buttons.all', lang),
        }
        mode_title = mode_map.get(mode_key, '')
        
        # اعمال فیلتر مود در صورت انتخاب BR/MP
        mode_value = None
        if mode_key == 'ws_mode_br':
            mode_value = 'br'
        elif mode_key == 'ws_mode_mp':
            mode_value = 'mp'

        try:
            agg = await get_container().analytics.get_weapon_category_stats(cat_id, mode_value)
        except Exception as e:
            logger.error(f"Error loading weapon stats: {e}")
            agg = None
        
        if agg and agg.get('category_name'):
            category_name = self._escape_markdown(agg['category_name'])
            message = t('admin.analytics.weapon_stats.title', lang) + "\n"
            message += t('admin.analytics.weapon_stats.mode', lang, mode=mode_title) + "\n\n"
            message += f"📂 {category_name}\n\n"
            message += t('admin.analytics.weapon_stats.lines.attach_count', lang, n=agg['attachment_count']) + "\n"
            message += t('admin.analytics.weapon_stats.lines.views', lang, views=f"{int(agg['total_views']):,}") + "\n"
            message += t('admin.analytics.weapon_stats.lines.avg_max', lang, avg=f"{float(agg['average_views']):.1f}", max=f"{int(agg['max_views']):,}") + "\n"
        else:
            message = t('admin.analytics.weapon_stats.no_data.title', lang) + "\n" + t('admin.analytics.weapon_stats.no_data.suggestion', lang)
        
        keyboard = [
            [InlineKeyboardButton(t('admin.analytics.buttons.change_category', lang), callback_data="analytics_ws_back_to_categories")],
            [InlineKeyboardButton(t('admin.analytics.buttons.back_to_mode_selection', lang), callback_data="analytics_ws_back_to_mode")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU
    
    async def refresh_trending(self, update: Update, context: CustomContext) -> int:
        """Refresh trending by delegating to view_trending"""
        return await self.view_trending(update, context)
    
    async def view_underperforming(self, update: Update, context: CustomContext) -> int:
        """نمایش آیتم‌های کم‌عملکرد بر اساس بازدید و نرخ تعامل"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.analytics.loading_under', lang))
        
        message = t('admin.analytics.under.title', lang) + "\n"
        message += t('admin.analytics.under.subtitle', lang) + "\n\n"
        
        try:
            items = await get_container().analytics.get_underperforming_stats(limit=20)
            
            if items:
                count = 0
                for it in items:
                    name = it['name']
                    weapon = it['weapon']
                    views = it['views'] or 0
                    clicks = it['clicks'] or 0
                    rate = (float(clicks) / float(views) * 100) if views > 0 else 0.0
                    
                    issues = []
                    if views < 20:
                        issues.append(t('admin.analytics.issue.low_views', lang))
                    if rate < 5.0:
                        issues.append(t('admin.analytics.issue.low_engagement', lang))
                    
                    safe_name = self._escape_markdown(name)
                    safe_weapon = self._escape_markdown(weapon)
                    
                    message += f"• *{safe_name}*\n"
                    if issues:
                        message += "   " + " • ".join(issues) + "\n"
                    message += t('admin.analytics.lines.weapon', lang, weapon=safe_weapon) + "\n"
                    message += t('admin.analytics.search.lines.stats', lang, views=f"{views:,}", clicks=f"{clicks:,}") + "\n\n"
                    count += 1
                message += t('admin.analytics.under.total', lang, n=count) + "\n"
            else:
                message += t('admin.analytics.under.all_good', lang) + "\n"
        except Exception as e:
            logger.error(f"Error in view_underperforming: {e}")
            message = t('admin.analytics.under.title', lang) + "\n\n" + t('admin.analytics.daily.error.body', lang)
        
        keyboard = []
        if items:
            added = 0
            for it in items:
                try:
                    att_id = it['id']
                    title = f"ℹ {it['name']}"
                    keyboard.append([InlineKeyboardButton(title, callback_data=f"weapon_details_{att_id}")])
                    added += 1
                    if added >= 10:
                        break
                except Exception:
                    continue
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")])
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def daily_report(self, update: Update, context: CustomContext) -> int:
        """گزارش روزانه ساده بر اساس آمار امروز"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.analytics.loading', lang))
        
        message = t('admin.analytics.daily.title', lang) + "\n\n"
        
        try:
            stats = await get_container().analytics.get_report_summary(days=1)
            views = stats['views']
            clicks = stats['clicks']
            users = stats['users']
            rate = (float(clicks)/float(views)*100) if views > 0 else 0.0
            
            message += t('admin.analytics.daily.stats.header', lang) + "\n"
            message += t('admin.analytics.daily.stats.views', lang, n=views) + "\n"
            message += t('admin.analytics.daily.stats.clicks', lang, n=clicks) + "\n"
            message += t('admin.analytics.daily.stats.users', lang, n=users) + "\n"
            message += t('admin.analytics.daily.stats.engagement', lang, rate=f"{rate:.1f}") + "\n\n"
            
            # Top today
            top = await get_container().analytics.get_top_attachments(days=1, limit=3)
            if top:
                message += t('admin.analytics.daily.top.header', lang) + "\n"
                for i, row in enumerate(top, 1):
                    medal = "🥇" if i==1 else "🥈" if i==2 else "🥉"
                    safe_name = self._escape_markdown(row['name'])
                    safe_weapon = self._escape_markdown(row['weapon'])
                    message += f"{medal} *{safe_name}*\n"
                    message += t('admin.analytics.lines.weapon', lang, weapon=safe_weapon) + "\n"
                    message += t('admin.analytics.fallback.lines.views', lang, value=f"{row['views']:,}") + "\n\n"
            else:
                message += t('admin.analytics.daily.no_data.title', lang) + "\n\n" + t('admin.analytics.daily.no_data.body', lang)
        except Exception as e:
            logger.error(f"Error in daily_report: {e}")
            message = t('admin.analytics.daily.error.title', lang) + "\n\n" + t('admin.analytics.daily.error.body', lang)
        
        keyboard = [
            [
                InlineKeyboardButton(t('admin.analytics.buttons.daily_chart', lang), callback_data="daily_chart"),
                InlineKeyboardButton(t('admin.analytics.buttons.download_csv', lang), callback_data="download_daily_csv")
            ],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    async def weekly_report(self, update: Update, context: CustomContext) -> int:
        """گزارش هفتگی ساده بر اساس آمار ۷ روز اخیر"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.analytics.loading', lang))
        
        message = t('admin.analytics.weekly.title', lang) + "\n\n"
        
        try:
            stats = await get_container().analytics.get_report_summary(days=7)
            views = stats['views']
            clicks = stats['clicks']
            users = stats['users']
            rate = (float(clicks)/float(views)*100) if views > 0 else 0.0
            
            message += t('admin.analytics.weekly.summary.header', lang) + "\n"
            message += t('admin.analytics.weekly.summary.views', lang, n=views) + "\n"
            message += t('admin.analytics.weekly.summary.clicks', lang, n=clicks) + "\n"
            message += t('admin.analytics.weekly.summary.users', lang, n=users) + "\n"
            message += t('admin.analytics.weekly.summary.engagement', lang, rate=f"{rate:.1f}") + "\n\n"
            
            # Top weekly
            top = await get_container().analytics.get_top_attachments(days=7, limit=3)
            if top:
                message += t('admin.analytics.weekly.top.header', lang) + "\n"
                for i, row in enumerate(top, 1):
                    medal = "🥇" if i==1 else "🥈" if i==2 else "🥉"
                    safe_name = self._escape_markdown(row['name'])
                    safe_weapon = self._escape_markdown(row['weapon'])
                    message += f"{medal} *{safe_name}*\n"
                    message += t('admin.analytics.lines.weapon_simple', lang, weapon=safe_weapon) + "\n"
                    message += t('admin.analytics.fallback.lines.views', lang, value=f"{row['views']:,}") + "\n\n"
            else:
                message += t('admin.analytics.weekly.no_data.title', lang) + "\n\n" + t('admin.analytics.weekly.no_data.body', lang)
        except Exception as e:
            logger.error(f"Error in weekly_report: {e}")
            message = t('admin.analytics.weekly.error.title', lang) + "\n\n" + t('admin.analytics.weekly.error.body', lang)
        
        keyboard = [
            [
                InlineKeyboardButton(t('admin.analytics.buttons.daily_chart', lang), callback_data="daily_chart"),
                InlineKeyboardButton(t('admin.analytics.buttons.download_csv', lang), callback_data="download_daily_csv")
            ],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]
        ]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU
    

    async def analytics_funnel_analysis(self, update: Update, context: CustomContext) -> int:
        """نمایش آنالیز قیف (مسیر کاربر)"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer()
        
        message = "🎯 *User Journey Funnel*\n\n"
        message += "این بخش مسیر تبدیل کاربر از مشاهده تا کپی کد را آنالیز می‌کند. (در حال پیاده‌سازی)"
        
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="analytics_menu")]]
        await self._safe_edit_message(query, message, keyboard)
        return ADMIN_MENU

    def get_conversation_handler(self) -> ConversationHandler:
        """Get conversation handler for analytics dashboard"""
        return ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.analytics_menu, pattern="^analytics_menu$"),
                CallbackQueryHandler(self.analytics_menu, pattern="^attachment_analytics$")
            ],
            states={
                ANALYTICS_MENU: [
                    # Legacy callbacks
                    CallbackQueryHandler(self.view_trending, pattern="^view_trending$"),
                    CallbackQueryHandler(self.view_underperforming, pattern="^view_underperforming$"),
                    CallbackQueryHandler(self.view_weapon_stats, pattern="^view_weapon_stats$"),
                    CallbackQueryHandler(self.view_user_behavior, pattern="^view_user_behavior$"),
                    CallbackQueryHandler(self.daily_report, pattern="^daily_report$"),
                    CallbackQueryHandler(self.weekly_report, pattern="^weekly_report$"),
                    # New analytics_* callbacks to match registry
                    CallbackQueryHandler(self.view_trending, pattern="^analytics_view_trending$"),
                    CallbackQueryHandler(self.view_underperforming, pattern="^analytics_view_underperforming$"),
                    CallbackQueryHandler(self.view_weapon_stats, pattern="^analytics_view_weapon_stats$"),
                    CallbackQueryHandler(self.view_user_behavior, pattern="^analytics_view_user_behavior$"),
                    CallbackQueryHandler(self.daily_report, pattern="^analytics_daily_report$"),
                    CallbackQueryHandler(self.weekly_report, pattern="^analytics_weekly_report$"),
                    # Common
                    CallbackQueryHandler(self.daily_chart, pattern="^daily_chart$"),
                    CallbackQueryHandler(self.download_daily_csv, pattern="^download_daily_csv$"),
                    CallbackQueryHandler(self.att_daily_chart, pattern="^att_daily_chart_\\d+$"),
                    CallbackQueryHandler(self.att_download_csv, pattern="^att_download_csv_\\d+$"),
                    CallbackQueryHandler(self.search_attachment_stats, pattern="^analytics_search_attachment$"),
                    CallbackQueryHandler(self.download_report, pattern="^analytics_download_report$"),
                    CallbackQueryHandler(self.weapon_details, pattern="^weapon_details_\\d+$"),
                    CallbackQueryHandler(self.ws_choose_mode, pattern="^analytics_ws_mode_(br|mp|all)$"),
                    CallbackQueryHandler(self.view_weapon_stats, pattern="^analytics_ws_back_to_mode$"),
                    CallbackQueryHandler(self.ws_choose_category, pattern="^analytics_ws_cat_\\d+$"),
                    CallbackQueryHandler(self.ws_choose_mode, pattern="^analytics_ws_back_to_categories$"),
                    CallbackQueryHandler(self.admin_cancel, pattern="^admin_menu_return$")
                ],
                VIEW_TRENDING: [
                    CallbackQueryHandler(self.refresh_trending, pattern="^refresh_trending$"),
                    CallbackQueryHandler(self.analytics_menu, pattern="^analytics_menu$"),
                    CallbackQueryHandler(self.weapon_details, pattern="^weapon_details_\\d+$")
                ],
                VIEW_UNDERPERFORMING: [
                    CallbackQueryHandler(self.analytics_menu, pattern="^analytics_menu$")
                ],
                VIEW_WEAPON_STATS: [
                    CallbackQueryHandler(self.analytics_menu, pattern="^analytics_menu$")
                ],
                SEARCH_ATTACH: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_search_text),
                    CallbackQueryHandler(self.analytics_menu, pattern="^analytics_menu$")
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.admin_cancel, pattern="^admin_cancel$"),
                MessageHandler(filters.Regex("^/cancel$"), self.admin_cancel)
            ]
        )






