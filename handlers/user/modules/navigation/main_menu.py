from core.context import CustomContext
"""
مدیریت منوی اصلی و navigation
⚠️ این کد عیناً از user_handlers.py خط 91-141 کپی شده
"""

import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from core.events import event_bus, EventTypes
from config.config import GAME_MODES
from managers.channel_manager import require_channel_membership
from utils.analytics_pg import AnalyticsPostgres as Analytics
from handlers.user.base_user_handler import BaseUserHandler
from utils.logger import get_logger, log_exception
from utils.language import get_user_lang
from utils.i18n import t, kb
from managers.cms_manager import CMSManager
from managers.cms_manager import CMSManager
from managers.admin_notifier import AdminNotifier
from utils.validation import parse_attachment_deep_link, parse_all_weapons_deep_link

logger = get_logger('user', 'user.log')


class MainMenuHandler(BaseUserHandler):
    """مدیریت منوی اصلی ربات"""
    
    @require_channel_membership
    async def start(self, update: Update, context: CustomContext):
        """دستور شروع و نمایش منوی اصلی"""
        user_id = update.effective_user.id
        if context.args and len(context.args) > 0:
            context.user_data['start_param'] = context.args[0]

        # Deep-link actions
        param = context.user_data.get('start_param')
        if param and update.message:
            # /start att-{id}-{mode}
            if param.startswith("att-"):
                att_id, mode = parse_attachment_deep_link(param)
                if att_id:
                    att = await self.db.get_attachment_by_id(att_id)
                    if att:
                        lang = await get_user_lang(update, context, self.db) or 'fa'
                        mode_name = t(f"mode.{mode}_btn", lang)
                        weapon = att.get('weapon') or att.get('weapon_name') or ''
                        caption = f"**{att.get('name','')}**\n{t('attachment.code', lang)}: `{att.get('code','')}`\n{weapon} | {mode_name}"
                        # دکمه‌های بازخورد
                        feedback_kb = None
                        a_id = att.get('id')
                        if a_id:
                            try:
                                stats = await self.db.get_attachment_stats(a_id, period='all') or {}
                                like_count = stats.get('like_count', 0)
                                dislike_count = stats.get('dislike_count', 0)
                            except Exception:
                                like_count = dislike_count = 0
                            
                            from core.container import get_container
                            fb_handler = get_container().feedback_handler
                            feedback_kb = InlineKeyboardMarkup(fb_handler.build_attachment_keyboard(
                                a_id, 
                                like_count=like_count, 
                                dislike_count=dislike_count, 
                                lang=lang,
                                mode=mode
                            ))
                        try:
                            if att.get('image'):
                                await update.message.reply_photo(photo=att['image'], caption=caption, parse_mode='Markdown', reply_markup=feedback_kb)
                            else:
                                await update.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
                                return
                            return
                        except Exception as e:
                            logger.error(f"Error sending attachment photo/message (att_id {a_id}): {e}")
                            await update.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
                            return
            # /start allw-{category}__{weapon}__{mode}
            if param.startswith("allw-"):
                category, weapon, mode = parse_all_weapons_deep_link(param)
                if category and weapon:
                    items = await self.db.get_all_attachments(category, weapon, mode=mode) or []
                    lang = await get_user_lang(update, context, self.db) or 'fa'
                    mode_name = t(f"mode.{mode}_btn", lang)
                    if not items:
                        await update.message.reply_text(t('attachment.none', lang))
                        return
                    header = t('attachment.all.title', lang, weapon=weapon, mode=mode_name)
                    lines = [header]
                    for i, att in enumerate(items[:20], start=1):
                        lines.append(f"{i}. {att.get('name','?')} — `{att.get('code','')}`")
                    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
                    return

        # بررسی کاربر جدید قبل از ثبت
        admin_notifier = AdminNotifier(self.db)
        is_new_user = not await admin_notifier.is_existing_user(user_id)

        # Track user info in database (NEW - for analytics)
        await self._track_user_info(update)

        # ثبت خودکار کاربر به عنوان مشترک برای دریافت نوتیفیکیشن‌ها
        try:
            await self.subs.add(user_id)
        except Exception as e:
            logger.warning(f"Error registering user {user_id} for notifications: {e}")

        # Emit async event for user registered/started
        asyncio.create_task(event_bus.emit(
            EventTypes.USER_REGISTERED,
            user_id=user_id,
            user=update.effective_user,
            is_new_user=is_new_user,
            context=context
        ))

        lang = await get_user_lang(update, context, self.db) or 'fa'

        keyboard = [
            [kb("menu.buttons.game_settings", lang), kb("menu.buttons.get", lang)]
        ]
        
        # ردیف 2: بسته به فعال بودن سیستم اتچمنت کاربران
        ua_system_enabled = await self.db.get_ua_setting('system_enabled') or '1'
        logger.info(f"[DEBUG] UA system_enabled value: {repr(ua_system_enabled)} (type: {type(ua_system_enabled).__name__})")
        if ua_system_enabled in ('1', 'true', 'True'):
            keyboard.append([kb("menu.buttons.ua", lang), kb("menu.buttons.suggested", lang)])
        else:
            keyboard.append([kb("menu.buttons.suggested", lang)])
        
        keyboard.extend([
            [kb("menu.buttons.season_list", lang), kb("menu.buttons.season_top", lang)],
            [kb("menu.buttons.notify", lang), kb("menu.buttons.search", lang)],
            [kb("menu.buttons.contact", lang), kb("menu.buttons.help", lang)]
        ])

        # ردیف CMS (نمایش مشروط به فعال بودن و داشتن محتوا)
        try:
            cms_enabled = str(await self.db.get_setting('cms_enabled', 'false')).lower() == 'true'
        except Exception:
            cms_enabled = False
        if cms_enabled:
            try:
                cms_total = CMSManager(self.db).count_published_content(None)
            except Exception:
                cms_total = 0
            if cms_total > 0:
                keyboard.append([kb("menu.buttons.cms", lang)])

        keyboard.append([kb("menu.buttons.leaderboard", lang), kb("menu.buttons.user_settings", lang)])

        # اگر کاربر ادمین است، دکمه پنل ادمین را اضافه کن (بررسی از دیتابیس RBAC)
        if await self.db.is_admin(user_id):
            keyboard.append([kb("menu.buttons.admin", lang)])

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        welcome_text = t("welcome", lang, app_name=t("app.name", lang))
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def back_msg(self, update: Update, context: CustomContext):
        """بازگشت به منوی اصلی از طریق پیام"""
        return await self.start(update, context)

    async def main_menu(self, update: Update, context: CustomContext):
        """بازگشت به منوی اصلی (Inline) — کیبورد پایین را ری‌لود می‌کند"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # ساخت همان کیبورد reply
        keyboard = [
            [kb("menu.buttons.game_settings", lang), kb("menu.buttons.get", lang)]
        ]

        ua_system_enabled = await self.db.get_ua_setting('system_enabled') or '1'
        if ua_system_enabled in ('1', 'true', 'True'):
            keyboard.append([kb("menu.buttons.ua", lang), kb("menu.buttons.suggested", lang)])
        else:
            keyboard.append([kb("menu.buttons.suggested", lang)])

        keyboard.extend([
            [kb("menu.buttons.season_list", lang), kb("menu.buttons.season_top", lang)],
            [kb("menu.buttons.notify", lang), kb("menu.buttons.search", lang)],
            [kb("menu.buttons.contact", lang), kb("menu.buttons.help", lang)]
        ])

        try:
            cms_enabled = str(await self.db.get_setting('cms_enabled', 'false')).lower() == 'true'
        except Exception:
            cms_enabled = False
        if cms_enabled:
            try:
                cms_total = CMSManager(self.db).count_published_content(None)
            except Exception:
                cms_total = 0
            if cms_total > 0:
                keyboard.append([kb("menu.buttons.cms", lang)])

        keyboard.append([kb("menu.buttons.leaderboard", lang), kb("menu.buttons.user_settings", lang)])

        if await self.db.is_admin(user_id):
            keyboard.append([kb("menu.buttons.admin", lang)])

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        welcome_text = t("welcome", lang, app_name=t("app.name", lang))

        # حذف پیام inline قبلی (اگر ممکن بود)
        try:
            await query.message.delete()
        except Exception:
            pass

        # ارسال پیام جدید با کیبورد reply در پایین چت
        await query.message.chat.send_message(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        return ConversationHandler.END

    async def show_user_id(self, update: Update, context: CustomContext):
        """نمایش شناسه کاربری"""
        await update.message.reply_text(f"Your User ID: `{update.effective_user.id}`", parse_mode='Markdown')
