from core.context import CustomContext
"""
Data Health Report Handler - Simple Version
Admin interface for viewing and managing data health checks
بدون استفاده از ConversationHandler برای سادگی
"""

import os
import json
import html
import re
import subprocess
import shutil
import tempfile
from shutil import which
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import ADMIN_MENU, AWAITING_BACKUP_FILE
from utils.data_health_check import DataHealthChecker
from utils.logger import get_logger
from core.security.role_manager import Permission
from utils.i18n import t
from utils.language import get_user_lang
from utils.telegram_safety import safe_edit_message_text

logger = get_logger('data_health_report', 'admin.log')

class DataHealthReportHandler(BaseAdminHandler):
    """Handler for data health reports in admin panel"""
    
    def __init__(self, db, role_manager=None):
        super().__init__(db)
        self.health_checker = DataHealthChecker(self.db)
    async def data_health_menu(self, update: Update, context: CustomContext) -> None:
        """Show data health main menu"""
        query = update.callback_query
        if query:
            await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
            
        # Check permissions
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
            
        # Init message
        message = t('admin.health.menu.title', lang) + "\n\n"

        # Get latest health check results (safe try/with)
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    # Latest metrics
                    await cursor.execute(
                        """
                        SELECT 
                            created_at,
                            total_weapons,
                            total_attachments,
                            health_score
                        FROM data_quality_metrics
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    )
                    latest_metrics = await cursor.fetchone()

                    # Active issues by severity
                    await cursor.execute(
                        """
                        SELECT 
                            severity,
                            COUNT(*) as count
                        FROM data_health_checks
                        GROUP BY severity
                        """
                    )
                    rows = await cursor.fetchall()
                    issue_counts = {}
                    if rows:
                        for row in rows:
                            issue_counts[row.get('severity')] = row.get('count')
        except Exception as e:
            logger.error(f"Error loading data health menu: {e}")
            latest_metrics = None
            issue_counts = {}

        # Build message
        if latest_metrics:
            created_at = latest_metrics.get('created_at')
            total_weapons = latest_metrics.get('total_weapons')
            total_attachments = latest_metrics.get('total_attachments')
            health_score = latest_metrics.get('health_score')
            # Ensure numeric type for comparisons/formatting
            try:
                health_score = float(health_score)
            except (TypeError, ValueError):
                health_score = 0.0
            score_emoji = "\U0001F7E2" if health_score >= 80 else "\U0001F7E1" if health_score >= 60 else "\U0001F534"
            message += t('admin.health.menu.last_check', lang, date=str(created_at)) + "\n"
            message += t('admin.health.menu.score', lang, emoji=score_emoji, score=f"{health_score:.1f}") + "\n\n"
            message += t('admin.health.menu.stats.header', lang) + "\n"
            message += t('admin.health.menu.stats.weapons', lang, n=total_weapons) + "\n"
            message += t('admin.health.menu.stats.attachments', lang, n=total_attachments) + "\n\n"
            
            if issue_counts:
                message += t('admin.health.menu.issues.header', lang) + "\n"
                if 'CRITICAL' in issue_counts:
                    message += t('admin.health.menu.issues.critical', lang, n=issue_counts['CRITICAL']) + "\n"
                if 'WARNING' in issue_counts:
                    message += t('admin.health.menu.issues.warning', lang, n=issue_counts['WARNING']) + "\n"
                if 'INFO' in issue_counts or 'TECHNICAL' in issue_counts:
                    total_info = int(issue_counts.get('INFO', 0)) + int(issue_counts.get('TECHNICAL', 0))
                    message += t('admin.health.menu.issues.info', lang, n=total_info) + "\n"
        else:
            message += t('admin.health.menu.no_report', lang) + "\n"
            
        # Build keyboard
        keyboard = []
        
        # Run check button (requires RUN_HEALTH_CHECKS permission)
        can_run = await self.check_permission(user_id, Permission.MANAGE_SETTINGS)
        if can_run:
            keyboard.append([
                InlineKeyboardButton(t('admin.health.buttons.run_check', lang), callback_data="health_run_check")
            ])
            
        # View reports buttons
        keyboard.extend([
            [
                InlineKeyboardButton(t('admin.health.buttons.view_full', lang), callback_data="health_view_full_report"),
                InlineKeyboardButton(t('admin.health.buttons.critical', lang), callback_data="health_view_critical")
            ],
            [
                InlineKeyboardButton(t('admin.health.buttons.warnings', lang), callback_data="health_view_warnings"),
                InlineKeyboardButton(t('admin.health.buttons.detailed', lang), callback_data="health_view_detailed_stats")
            ]
        ])
        
        # Fix issues button (requires FIX_DATA_ISSUES permission)
        can_fix = await self.check_permission(user_id, Permission.MANAGE_SETTINGS)
        if can_fix:
            keyboard.append([
                InlineKeyboardButton(t('admin.health.buttons.fix_issues', lang), callback_data="health_fix_issues_menu")
            ])
            
        # History and back buttons
        keyboard.extend([
            [InlineKeyboardButton(t('admin.health.buttons.history', lang), callback_data="health_view_check_history")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="admin_menu_return")]
        ])
        
        if query:
            await safe_edit_message_text(
                query,
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        # No return needed for simple handler
        
    async def run_health_check(self, update: Update, context: CustomContext) -> None:
        """Run a new health check"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.health.run.start', lang))
        
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
            
        # Show progress message
        await safe_edit_message_text(
            query,
            t('admin.health.run.progress', lang),
            parse_mode=ParseMode.HTML
        )
        
        try:
            # Run health check
            results = await self.health_checker.run_full_check(save_to_db=True)
            
            # Build result message
            score = results['health_score']
            score_emoji = "\U0001F7E2" if score >= 80 else "\U0001F7E1" if score >= 60 else "\U0001F534"
            
            message = t('admin.health.run.completed.title', lang) + "\n\n"
            message += t('admin.health.run.completed.score', lang, emoji=score_emoji, score=f"{score:.1f}") + "\n\n"
            if results['critical_count'] > 0:
                message += t('admin.health.run.completed.critical', lang, n=results['critical_count']) + "\n"
            if results['warning_count'] > 0:
                message += t('admin.health.run.completed.warnings', lang, n=results['warning_count']) + "\n"
            if results['info_count'] > 0:
                message += t('admin.health.run.completed.info', lang, n=results['info_count']) + "\n"
            
            report_filename = html.escape(os.path.basename(results['report_path'])) if results.get('report_path') else "N/A"
            message += "\n" + t('admin.health.run.completed.saved', lang, file=report_filename)
            
            # Send report file
            if os.path.exists(results['report_path']):
                with open(results['report_path'], 'rb') as f:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename=os.path.basename(results['report_path']),
                        caption=t('admin.health.run.report_caption', lang)
                    )
                    
        except Exception as e:
            message = t('admin.health.run.error', lang, err=html.escape(str(e)))
            logger.error(f"Health check error: {e}")
            
        # Update message with back button
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]]
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def view_critical(self, update: Update, context: CustomContext) -> None:
        """View critical issues"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                    SELECT 
                        check_type,
                        issue_count,
                        details,
                        created_at
                    FROM data_health_checks
                    WHERE severity = 'CRITICAL'
                    ORDER BY created_at DESC
                    LIMIT 10
                    """)
                    
                    critical_issues = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error loading critical issues: {e}")
            critical_issues = []
            
        message = t('admin.health.critical.title', lang) + "\n\n"
        
        if critical_issues:
            for issue in critical_issues:
                check_type = issue.get('check_type')
                count = issue.get('issue_count')
                details_json = issue.get('details')
                created_at = issue.get('created_at')
                details = json.loads(details_json) if isinstance(details_json, str) and details_json else {}
                
                if check_type == 'missing_images':
                    message += f"\U0001F5BC\uFE0F **{t('admin.health.type.missing_images', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'duplicate_codes':
                    message += f"\U0001F50D **{t('admin.health.type.duplicate_codes', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'orphaned_attachments':
                    message += f"\U0001F9E9 **{t('admin.health.type.orphaned_attachments', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'missing_columns':
                    message += f"\U0001F4D1 **{t('admin.health.type.missing_columns', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                
                date_str = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else (str(created_at)[:10] if created_at else '-')
                message += t('admin.health.date', lang, date=date_str) + "\n\n"
        else:
            message += t('admin.health.critical.none', lang)
            
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def view_warnings(self, update: Update, context: CustomContext) -> None:
        """View warning issues"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                    SELECT 
                        check_type,
                        issue_count,
                        details,
                        created_at
                    FROM data_health_checks
                    WHERE severity = 'WARNING'
                    ORDER BY created_at DESC
                    LIMIT 10
                    """)
                    
                    warnings = await cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error loading warnings: {e}")
            warnings = []
            
        message = t('admin.health.warnings.title', lang) + "\n\n"
        
        if warnings:
            for warning in warnings:
                check_type = warning.get('check_type')
                count = warning.get('issue_count')
                details_json = warning.get('details')
                created_at = warning.get('created_at')
                
                if check_type == 'empty_weapons':
                    message += f"\U0001F5E1\uFE0F **{t('admin.health.type.empty_weapons', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'sparse_weapons':
                    message += f"\U0001F7E8 **{t('admin.health.type.sparse_weapons', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'missing_indexes':
                    message += f"\U0001F5D2\uFE0F **{t('admin.health.type.missing_indexes', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'sequence_desync':
                    message += f"\U0001F522 **{t('admin.health.type.sequence_desync', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'sequence_missing':
                    message += f"\U0001F522 **{t('admin.health.type.sequence_missing', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                elif check_type == 'invalid_images':
                    message += f"\u26A0\uFE0F **{t('admin.health.type.invalid_images', lang)}**: {count} {t('admin.health.issue.unit', lang)}\n"
                
                date_str = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else (str(created_at)[:10] if created_at else '-')
                message += t('admin.health.date', lang, date=date_str) + "\n\n"
        else:
            message += t('admin.health.warnings.none', lang)
            
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def view_full_report(self, update: Update, context: CustomContext) -> None:
        """View full report with all issues"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    # Get latest metrics
                    await cursor.execute("""
                    SELECT 
                        created_at,
                        health_score,
                        total_weapons,
                        total_attachments,
                        attachments_with_images,
                        attachments_without_images
                    FROM data_quality_metrics
                    ORDER BY created_at DESC
                    LIMIT 1
                    """)
                    latest = await cursor.fetchone()
                    
                    # Get all issues
                    await cursor.execute("""
                    SELECT 
                        severity,
                        check_type,
                        issue_count
                    FROM data_health_checks
                    ORDER BY 
                        CASE severity 
                            WHEN 'CRITICAL' THEN 1
                            WHEN 'WARNING' THEN 2
                            ELSE 3
                        END,
                        created_at DESC
                    """)
                    issues = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error loading full report: {e}")
            latest = None
            issues = []
            
        message = t('admin.health.full.title', lang) + "\n\n"
        
        if latest:
            date = latest.get('created_at')
            score = latest.get('health_score')
            weapons = latest.get('total_weapons')
            attachments = latest.get('total_attachments')
            with_img = latest.get('attachments_with_images')
            without_img = latest.get('attachments_without_images')
            # Ensure numeric type for comparisons/formatting
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = 0.0
            score_emoji = "\U0001F7E2" if score >= 80 else "\U0001F7E1" if score >= 60 else "\U0001F534"
            
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else (str(date)[:10] if date else '-')
            message += t('admin.health.date', lang, date=date_str) + "\n"
            message += t('admin.health.run.completed.score', lang, emoji=score_emoji, score=f"{score:.1f}") + "\n\n"
            
            message += t('admin.health.menu.stats.header', lang) + "\n"
            message += t('admin.health.menu.stats.weapons', lang, n=weapons) + "\n"
            message += t('admin.health.menu.stats.attachments', lang, n=attachments) + "\n"
            message += t('admin.health.stats.with_images', lang, n=with_img) + "\n"
            message += t('admin.health.stats.without_images', lang, n=without_img) + "\n\n"
            
            if issues:
                message += t('admin.health.open_issues.header', lang) + "\n"
                for row in issues:
                    severity = row.get('severity')
                    check_type = row.get('check_type')
                    count = row.get('issue_count')
                    emoji = "\u274C" if severity == "CRITICAL" else "\u26A0\uFE0F" if severity == "WARNING" else "\u2139\uFE0F"
                    type_title = {
                        'missing_images': t('admin.health.type.missing_images', lang),
                        'duplicate_codes': t('admin.health.type.duplicate_codes', lang),
                        'empty_weapons': t('admin.health.type.empty_weapons', lang),
                        'sparse_weapons': t('admin.health.type.sparse_weapons', lang),
                        'orphaned_attachments': t('admin.health.type.orphaned_attachments', lang),
                        'missing_indexes': t('admin.health.type.missing_indexes', lang),
                        'sequence_desync': t('admin.health.type.sequence_desync', lang),
                        'sequence_missing': t('admin.health.type.sequence_missing', lang),
                        'missing_columns': t('admin.health.type.missing_columns', lang),
                        'invalid_images': t('admin.health.type.invalid_images', lang),
                        'slow_searches': t('admin.health.type.slow_searches', lang)
                    }.get(check_type, check_type)
                    message += f"{emoji} {type_title}: {count} {t('admin.health.issue.unit', lang)}\n"
            else:
                message += t('admin.health.full.no_issues', lang)
        else:
            message += t('admin.health.full.no_checks', lang)
            
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def view_detailed_stats(self, update: Update, context: CustomContext) -> None:
        """View detailed statistics"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Calculate fresh metrics
        await self.health_checker.calculate_metrics()
        metrics = self.health_checker.metrics
        
        message = t('admin.health.detailed.title', lang) + "\n\n"
        message += t('admin.health.detailed.total.header', lang) + "\n"
        message += t('admin.health.detailed.total.categories', lang, n=metrics.get('total_categories', 0)) + "\n"
        message += t('admin.health.menu.stats.weapons', lang, n=metrics.get('total_weapons', 0)) + "\n"
        message += t('admin.health.menu.stats.attachments', lang, n=metrics.get('total_attachments', 0)) + "\n\n"
        
        message += t('admin.health.detailed.special.header', lang) + "\n"
        message += t('admin.health.detailed.special.top', lang, n=metrics.get('top_attachments', 0)) + "\n"
        message += t('admin.health.detailed.special.season', lang, n=metrics.get('season_attachments', 0)) + "\n\n"
        
        message += t('admin.health.detailed.images.header', lang) + "\n"
        message += t('admin.health.detailed.images.line', lang, pct=f"{metrics.get('image_coverage', 0):.1f}") + "\n\n"
        
        if metrics.get('category_distribution'):
            message += t('admin.health.detailed.catdist.header', lang) + "\n"
            for cat in metrics['category_distribution']:
                # Escape markdown characters in category name
                safe_category = cat['category'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
                message += t('admin.health.detailed.catdist.line', lang, category=safe_category, weapons=cat['weapons'], attachments=cat['attachments']) + "\n"
                
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def view_check_history(self, update: Update, context: CustomContext) -> None:
        """View history of health checks"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                    SELECT 
                        created_at,
                        health_score,
                        total_weapons,
                        total_attachments,
                        attachments_with_images,
                        attachments_without_images
                    FROM data_quality_metrics
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                    
                    history = await cursor.fetchall()
        finally:
            pass  # Connection auto-closed by context manager
            
        message = t('admin.health.history.title', lang) + "\n\n"
        
        if history:
            for record in history:
                date = record.get('created_at')
                score = record.get('health_score')
                weapons = record.get('total_weapons')
                attachments = record.get('total_attachments')
                with_img = record.get('attachments_with_images')
                without_img = record.get('attachments_without_images')
                # Ensure numeric type for comparisons/formatting
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = 0.0
                score_emoji = "\U0001F7E2" if score >= 80 else "\U0001F7E1" if score >= 60 else "\U0001F534"
                
                date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else (str(date)[:10] if date else '-')
                message += f"\U0001F4C5 **{date_str}**\n"
                message += f"{t('admin.health.run.completed.score', lang, emoji=score_emoji, score=f'{score:.1f}')}\n"
                message += f"\u2022 {t('admin.health.menu.stats.weapons', lang, n=weapons)} | {t('admin.health.menu.stats.attachments', lang, n=attachments)}\n"
                message += f"\u2022 {t('admin.health.stats.with_images', lang, n=with_img)} | {t('admin.health.stats.without_images', lang, n=without_img)}\n\n"
        else:
            message += t('admin.health.history.none', lang)
            
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed for simple handler
        
    async def fix_issues_menu(self, update: Update, context: CustomContext) -> None:
        """Show menu for fixing issues"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
            
        message = t('admin.health.fix.menu.title', lang) + "\n\n" + t('admin.health.fix.menu.note', lang) + "\n\n" + t('admin.health.fix.menu.prompt', lang)
        
        keyboard = [
            [InlineKeyboardButton(t('admin.health.fix.buttons.missing_images', lang), callback_data="health_fix_missing_images")],
            [InlineKeyboardButton(t('admin.health.fix.buttons.duplicate_codes', lang), callback_data="health_fix_duplicate_codes")],
            [InlineKeyboardButton(t('admin.health.fix.buttons.orphaned', lang), callback_data="health_fix_orphaned")],
            [InlineKeyboardButton(t('admin.health.fix.buttons.technical_fix', lang), callback_data="health_fix_technical")],
            [
                InlineKeyboardButton(t('admin.health.fix.buttons.create_backup', lang), callback_data="health_create_backup"),
                InlineKeyboardButton(t('admin.health.fix.buttons.restore_backup', lang), callback_data="health_restore_backup")
            ],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_data_health")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # No return needed
        
    async def fix_missing_images(self, update: Update, context: CustomContext) -> None:
        """Show list of attachments without images"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.health.loading.missing_images', lang))
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
        
        # Get all attachments without images
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                    SELECT 
                        a.id,
                        a.name,
                        a.code,
                        wc.name as category,
                        w.name as weapon,
                        a.mode
                    FROM attachments a
                    JOIN weapons w ON a.weapon_id = w.id
                    JOIN weapon_categories wc ON w.category_id = wc.id
                    WHERE a.image_file_id IS NULL OR a.image_file_id = ''
                    ORDER BY wc.name, w.name
                    LIMIT 20
                """)
                    
                    missing_images = await cursor.fetchall()
                    total = len(missing_images)
        finally:
            pass  # Connection auto-closed by context manager
            
        message = t('admin.health.missing_images.title', lang) + "\n\n"
        
        if missing_images:
            message += t('admin.health.list.total', lang, n=total) + "\n"
            message += t('admin.health.list.showing', lang, n=min(20, total)) + "\n\n"
            
            current_category = None
            for row in missing_images:
                att_id = row.get('id')
                name = row.get('name')
                code = row.get('code')
                category = row.get('category')
                weapon = row.get('weapon')
                mode = row.get('mode')
                if category != current_category:
                    current_category = category
                    message += f"\n**{category}:**\n"
                    
                mode_emoji = "🪂" if mode == "br" else "🎮"
                safe_weapon = html.escape(weapon)
                safe_name = html.escape(name)
                message += f"{mode_emoji} {safe_weapon} - {safe_name} (<code>{html.escape(code)}</code>)\n"
                
            message += "\n" + t('admin.health.missing_images.hint.title', lang) + "\n"
            message += t('admin.health.missing_images.hint.edit', lang) + "\n"
            message += t('admin.health.missing_images.hint.check', lang) + "\n"
            message += t('admin.health.missing_images.hint.quality', lang) + "\n"
        else:
            message += t('admin.health.missing_images.none', lang)
        
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def fix_duplicate_codes(self, update: Update, context: CustomContext) -> None:
        """Show and fix duplicate attachment codes"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.health.loading.duplicates', lang))
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
        
        # Find duplicate codes
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                    SELECT 
                        LOWER(a.code) as code,
                        COUNT(*) as count,
                        STRING_AGG(a.name || ' (' || w.name || ')', ', ') as attachments
                    FROM attachments a
                    JOIN weapons w ON a.weapon_id = w.id
                    GROUP BY LOWER(a.code)
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                    LIMIT 10
                """)
                    
                    duplicates = await cursor.fetchall()
        finally:
            pass  # Connection auto-closed by context manager
            
        message = t('admin.health.duplicates.title', lang) + "\n\n"
        
        if duplicates:
            message += t('admin.health.list.total', lang, n=len(duplicates)) + "\n\n"
            
            for row in duplicates:
                code = html.escape(row.get('code', ''))
                count = row.get('count')
                attachments = html.escape(row.get('attachments', ''))

                message += f"• <code>{code}</code> - {count} {t('admin.health.issue.unit', lang)}\n"
                att_list = attachments.split(',')
                for att in att_list[:3]:  # نمایش 3 مورد اول
                    message += f"  \u2022 {att.strip()}\n"
                if len(att_list) > 3:
                    message += f"  \u2022 {t('common.items_other_count', lang, n=len(att_list) - 3)}\n"
                message += "\n"
                
            message += t('admin.health.duplicates.note', lang) + "\n\n"
            message += t('admin.health.duplicates.hint.title', lang) + "\n"
            message += t('admin.health.duplicates.hint.fix', lang) + "\n"
            message += t('admin.health.duplicates.hint.remove', lang) + "\n"
        else:
            message += t('admin.health.duplicates.none', lang)
            
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def fix_orphaned(self, update: Update, context: CustomContext) -> None:
        """Find and optionally remove orphaned attachments"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.health.loading.orphaned', lang))
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
        
        # Find orphaned attachments (attachments with deleted weapon_id)
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    # Find attachments with non-existent weapon_id
                    await cursor.execute("""
                    SELECT 
                        a.id,
                        a.name,
                        a.code,
                        a.weapon_id
                    FROM attachments a
                    LEFT JOIN weapons w ON a.weapon_id = w.id
                    WHERE w.id IS NULL
                    LIMIT 20
                """)
                    
                    orphaned = await cursor.fetchall()
        finally:
            pass  # Connection auto-closed by context manager
            
        message = t('admin.health.orphaned.title', lang) + "\n\n"
        message += t('admin.health.orphaned.desc', lang) + "\n\n"
        
        if orphaned:
            message += t('admin.health.list.total', lang, n=len(orphaned)) + "\n\n"
            
            for row in orphaned:
                att_id = row.get('id')
                name = html.escape(row.get('name', ''))
                code = html.escape(row.get('code', ''))
                weapon_id = row.get('weapon_id')
                message += f"• {name} (<code>{code}</code>)\n"
                message += t('admin.health.orphaned.weapon_id', lang, id=weapon_id) + "\n\n"
                
            message += t('admin.health.orphaned.note', lang) + "\n\n"
            
            message += t('admin.health.orphaned.hint.title', lang) + "\n"
            message += t('admin.health.orphaned.hint.restore', lang) + "\n"
            message += t('admin.health.orphaned.hint.cleanup', lang) + "\n"
        else:
            message += t('admin.health.orphaned.none', lang)
        
        keyboard = [
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]
        ]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    def get_pg_tool_path(self, tool_name: str) -> str:
        """Find path to pg_dump or psql on common OS locations"""
        # First check if it's already in PATH
        path = which(tool_name)
        if path:
            return path
            
        # Common Windows locations for PostgreSQL
        if os.name == 'nt':
            # Priority to version 18 since we saw it
            versions = ['18', '17', '16', '15', '14', '13']
            for v in versions:
                full_path = f"C:\\Program Files\\PostgreSQL\\{v}\\bin\\{tool_name}.exe"
                if os.path.exists(full_path):
                    return full_path
                    
        return tool_name # Fallback to name and hope for the best

    async def create_backup(self, update: Update, context: CustomContext) -> None:
        """Create database backup and send to admin"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('admin.health.backup.start', lang))
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            
            # Check for PostgreSQL using different possible ways
            is_postgres = False
            if hasattr(self.db, 'is_postgres'):
                is_postgres = await self.db.is_postgres()
            
            if is_postgres:
                # Use centralized backup manager for PostgreSQL
                backup_path = await self.db.backup_manager.create_full_backup()
                if not backup_path:
                    raise Exception("Failed to create PostgreSQL backup via BackupManager.")
                backup_filename = os.path.basename(backup_path)
            else:
                # SQLite Logic - Only if NOT postgres
                db_path = getattr(self.health_checker, 'db_path', None)
                if not db_path or ':' in db_path:
                    # If db_path looks like a connection string, we shouldn't use it as a file path
                    raise Exception("SQLite database path not found or invalid for backup.")
                
                backup_filename = f"codm_backup_{timestamp}.db"
                backup_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), backup_filename)
                shutil.copy2(db_path, backup_path)
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            size_mb = file_size / (1024 * 1024)
            
            # Send backup file to admin
            with open(backup_path, 'rb') as backup_file:
                caption = t('admin.health.backup.caption.title', lang) + "\n\n"
                caption += t('admin.health.backup.caption.date', lang, date=timestamp[:8]) + "\n"
                caption += t('admin.health.backup.caption.time', lang, time=timestamp[9:]) + "\n"
                caption += t('admin.health.backup.caption.size', lang, size=f"{size_mb:.2f}") + "\n\n"
                caption += t('admin.health.backup.caption.note', lang)
                
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=backup_file,
                    filename=backup_filename,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            
            # Cleanup temp file if PostgreSQL
            if hasattr(self.db, 'is_postgres') and await self.db.is_postgres():
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            
            message = t('admin.health.backup.success.title', lang) + "\n\n"
            message += t('admin.health.backup.success.sent', lang) + "\n"
            if backup_filename.endswith('.zip'):
                message += "📦 <b>Format:</b> ZIP (Contains Database Dump)\n"
            message += t('admin.health.backup.caption.size', lang, size=f"{size_mb:.2f}") + "\n\n"
            message += t('admin.health.backup.success.tip_restore', lang)
            
        except Exception as e:
            message = t('admin.health.backup.error', lang, err=html.escape(str(e)))
            logger.error(f"Backup error: {e}")
            
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    async def restore_backup_start(self, update: Update, context: CustomContext) -> int:
        """Start backup restoration process"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU
        
        message = (
            t('admin.health.restore.start.title', lang) + "\n\n" +
            t('admin.health.restore.start.steps_header', lang) + "\n" +
            t('admin.health.restore.start.step1', lang) + "\n" +
            t('admin.health.restore.start.step2', lang) + "\n\n" +
            t('admin.health.restore.start.prompt', lang) + "\n" +
            t('admin.health.restore.start.cancel', lang)
        )
        
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return AWAITING_BACKUP_FILE
        
    async def restore_backup_file(self, update: Update, context: CustomContext) -> int:
        """Handle received backup file and restore it"""
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Check permission
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await self.send_permission_denied(update, context)
            return ADMIN_MENU
        
        # Check if document exists
        if not update.message.document:
            await update.message.reply_text(
                t('admin.health.restore.file_required', lang) + "\n" + t('admin.health.restore.start.cancel', lang)
            )
            return AWAITING_BACKUP_FILE
        
        document = update.message.document
        
        # Check file extension
        is_postgres = hasattr(self.db, 'is_postgres') and await self.db.is_postgres()
        valid_exts = ('.sql', '.zip', '.dump') if is_postgres else ('.db',)
        
        if not any(document.file_name.lower().endswith(ext) for ext in valid_exts):
            await update.message.reply_text(
                t('admin.health.restore.invalid_format', lang) + "\n" + t('admin.health.restore.start.cancel', lang)
            )
            return AWAITING_BACKUP_FILE
        
        try:
            # Download file
            logger.info(f"💾 Starting backup restore from file_id: {document.file_id}")
            logger.info("📡 Requesting file path from Telegram...")
            
            try:
                file = await context.bot.get_file(document.file_id)
            except Exception as e:
                logger.error(f"❌ Failed to get file path: {e}")
                if "ConnectError" in str(e) or "ConnectTimeout" in str(e):
                    raise Exception("Network Error: Could not connect to Telegram API. Check your proxy/VPN.") from e
                raise
                
            logger.info(f"📥 File path retrieved: {file.file_path}")
            
            ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_ext = os.path.splitext(document.file_name)[1].lower()
            temp_path = os.path.join(tempfile.gettempdir(), f"restore_{ts_str}{file_ext}")
            
            logger.info(f"💾 Downloading file to: {temp_path}")
            try:
                await file.download_to_drive(temp_path)
            except Exception as e:
                logger.error(f"❌ Download failed: {e}")
                if "ConnectError" in str(e):
                     raise Exception("Network Error: Connection failed during download. This is likely a proxy/VPN issue.") from e
                raise
                
            logger.info("✅ File downloaded successfully. Starting database restore...")
            
            restore_file = temp_path
            temp_dir = None
            
            # ZIP Handling
            if file_ext == '.zip':
                import zipfile
                temp_dir = os.path.join(tempfile.gettempdir(), f"extract_{ts_str}")
                os.makedirs(temp_dir, exist_ok=True)
                
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Look for .dump or .sql inside ZIP
                found = False
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f.lower().endswith(('.dump', '.sql')):
                            restore_file = os.path.join(root, f)
                            found = True
                            break
                    if found: break
                
                if not found:
                    raise Exception("Valid backup file (.sql or .dump) not found inside ZIP.")
                
                logger.info(f"📦 Extracted and found backup file: {os.path.basename(restore_file)}")

            if is_postgres:
                # PostgreSQL Restore
                pg_host = os.environ.get('POSTGRES_HOST')
                pg_user = os.environ.get('POSTGRES_USER')
                pg_db = os.environ.get('POSTGRES_DB')
                pg_pass = os.environ.get('POSTGRES_PASSWORD')
                
                # Fetch settings if env vars are missing
                if not all([pg_host, pg_user, pg_db]):
                    db_url = os.environ.get('DATABASE_URL', '')
                    if db_url.startswith('postgresql://'):
                        try:
                            import re
                            pattern = r'postgresql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)'
                            match = re.match(pattern, db_url)
                            if match:
                                u, p, h, pt, d = match.groups()
                                pg_user = pg_user or u
                                pg_pass = pg_pass or p
                                pg_host = pg_host or h
                                pg_db = pg_db or d
                        except Exception: pass

                pg_host = pg_host or 'localhost'
                pg_user = pg_user or 'postgres'
                pg_db = pg_db or 'postgres'
                
                env = os.environ.copy()
                env['PGPASSWORD'] = pg_pass or ''
                
                # Decide between psql and pg_restore
                is_dump = restore_file.lower().endswith('.dump')
                
                if is_dump:
                    logger.info("🛠 Using pg_restore for binary dump...")
                    restore_path = self.get_pg_tool_path('pg_restore')
                    # --clean: drop objects before recreating, --no-owner: skip restoration of object ownership
                    args = [restore_path, '-h', pg_host, '-U', pg_user, '-d', pg_db, '--clean', '--no-owner', restore_file]
                else:
                    logger.info("🛠 Using psql for SQL script...")
                    restore_path = self.get_pg_tool_path('psql')
                    args = [restore_path, '-h', pg_host, '-U', pg_user, '-d', pg_db, '-f', restore_file]
                
                result = subprocess.run(args, env=env, capture_output=True, text=True)
                
                # Cleanup
                try:
                    if os.path.exists(temp_path): os.remove(temp_path)
                    if temp_dir and os.path.exists(temp_dir): shutil.rmtree(temp_dir)
                except Exception: pass

                if result.returncode != 0:
                    logger.error(f"❌ Restore failed: {result.stderr}")
                    # Some data existing errors are expected if not using --clean, but we want to know
                    if "already exists" in result.stderr:
                        await update.message.reply_text(t('admin.health.restore.partial_success', lang))
                        return ADMIN_MENU
                    raise Exception(result.stderr)
                
                await update.message.reply_text(t('admin.health.restore.success', lang))
                return ADMIN_MENU
            
            else:
                # SQLite Restore
                db_path = getattr(self.health_checker, 'db_path', None)
                if not db_path or ':' in db_path:
                    raise Exception("SQLite database path not found or invalid for restore.")
                
                # Sanitize safety backup name for Windows (ensure no colons)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                safety_backup = f"{db_path}.before_restore_{ts}.bak"
                shutil.copy2(db_path, safety_backup)
                shutil.copy2(temp_path, db_path)
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            message = t('admin.health.restore.success.title', lang) + "\n\n"
            message += t('admin.health.restore.success.safety_backup', lang, file=os.path.basename(safety_backup)) + "\n\n"
            message += t('admin.health.restore.success.restart', lang, cmd="sudo systemctl restart codm-bot")
            
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="fix_issues_menu")]]
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Database restored by admin {user_id}")
            
        except Exception as e:
            message = t('admin.health.restore.error', lang, err=html.escape(str(e)))
            
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="fix_issues_menu")]]
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            logger.error(f"Restore error: {e}")
        
        return ADMIN_MENU

    async def fix_technical(self, update: Update, context: CustomContext) -> None:
        """Execute technical fixes (indexes, sequences)"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Check permission
        user_id = update.effective_user.id
        if not await self.check_permission(user_id, Permission.MANAGE_SETTINGS):
            await query.answer(t('errors.no_permission', lang), show_alert=True)
            return

        await query.answer(t('admin.health.fix.technical.start', lang))
        
        try:
            # Execute fix
            success = await self.health_checker.fix_technical_issues()
            
            if success:
                message = t('admin.health.fix.technical.success', lang)
            else:
                message = t('admin.health.fix.technical.error', lang, err="Internal Error")
                
        except Exception as e:
            logger.error(f"Error in fix_technical: {e}")
            message = t('admin.health.fix.technical.error', lang, err=str(e))
            
        keyboard = [[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="health_fix_issues_menu")]]
        
        await safe_edit_message_text(
            query,
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
