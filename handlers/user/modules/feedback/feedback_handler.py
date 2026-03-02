from core.context import CustomContext
from core.container import get_container
"""
Feedback Handler - مدیریت بازخورد اتچمنت‌ها (لایک/دیس‌لایک/نظرات)
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from managers.channel_manager import require_channel_membership
from utils.logger import log_user_action, get_logger
from handlers.user.base_user_handler import BaseUserHandler
from utils.i18n import t
from utils.language import get_user_lang
from utils.telegram_safety import safe_edit_message_text
from utils.validators_enhanced import TextValidator
import time
import re

logger = get_logger('user', 'user.log')

# State برای ConversationHandler
FEEDBACK_TEXT = 1


class FeedbackHandler(BaseUserHandler):
    """مدیریت بازخورد اتچمنت‌ها"""
    
    # Rate limiter: 1 vote per second per user
    _vote_cooldown = {}
    VOTE_COOLDOWN_SECONDS = 1
    
    @require_channel_membership
    @log_user_action("vote_like")
    async def handle_vote_like(self, update: Update, context: CustomContext):
        """مدیریت لایک اتچمنت"""
        query = update.callback_query
        user_id = query.from_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Rate limiting
        if not self._check_rate_limit(user_id):
            await query.answer(t("feedback.wait", lang), show_alert=True)
            return
        
        # استخراج attachment_id از callback_data: att_like_{id}
        try:
            attachment_id = int(query.data.replace("att_like_", ""))
        except ValueError:
            await query.answer(t("feedback.error", lang), show_alert=True)
            return
        
        # ثبت رأی
        result = await self.db.vote_attachment(user_id, attachment_id, vote=1)
        
        if not result.get('success'):
            await query.answer(t("feedback.error", lang), show_alert=True)
            return
        
        # پیام مناسب بر اساس action
        action = result.get('action')
        if action == 'added':
            message = t("feedback.like.added", lang)
        elif action == 'removed':
            message = t("feedback.like.removed", lang)
        elif action == 'changed':
            message = t("feedback.like.changed", lang)
        else:
            message = t("feedback.saved", lang)
        
        await query.answer(message, show_alert=False)
        
        # به‌روزرسانی دکمه‌ها با شمارنده‌های جدید
        await self._update_feedback_buttons(query, attachment_id, result, lang)
    
    @require_channel_membership
    @log_user_action("vote_dislike")
    async def handle_vote_dislike(self, update: Update, context: CustomContext):
        """مدیریت دیس‌لایک اتچمنت"""
        query = update.callback_query
        user_id = query.from_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # Rate limiting
        if not self._check_rate_limit(user_id):
            await query.answer(t("feedback.wait", lang), show_alert=True)
            return
        
        # استخراج attachment_id
        try:
            attachment_id = int(query.data.replace("att_dislike_", ""))
        except ValueError:
            await query.answer(t("feedback.error", lang), show_alert=True)
            return
        
        # ثبت رأی
        result = await self.db.vote_attachment(user_id, attachment_id, vote=-1)
        
        if not result.get('success'):
            await query.answer(t("feedback.error", lang), show_alert=True)
            return
        
        # پیام مناسب
        action = result.get('action')
        if action == 'added':
            message = t("feedback.dislike.added", lang)
        elif action == 'removed':
            message = t("feedback.dislike.removed", lang)
        elif action == 'changed':
            message = t("feedback.dislike.changed", lang)
        else:
            message = t("feedback.saved", lang)
        
        await query.answer(message, show_alert=False)
        
        # به‌روزرسانی دکمه‌ها
        await self._update_feedback_buttons(query, attachment_id, result, lang)
    
    @require_channel_membership
    @log_user_action("feedback_request")
    async def handle_feedback_request(self, update: Update, context: CustomContext):
        """درخواست بازخورد متنی"""
        query = update.callback_query
        await query.answer()
        
        # استخراج attachment_id: att_fb_{id}
        try:
            attachment_id = int(query.data.replace("att_fb_", ""))
        except ValueError:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t("feedback.error", lang), show_alert=True)
            return
        
        # ذخیره attachment_id در context
        context.user_data['feedback_attachment_id'] = attachment_id
        # ذخیره متن/کپشن و کیبورد قبلی برای بازگردانی در لغو
        try:
            prev_caption = query.message.caption or ""
        except Exception:
            prev_caption = ""
        try:
            prev_text = query.message.text or ""
        except Exception:
            prev_text = ""
        context.user_data['feedback_prev_caption'] = prev_caption
        context.user_data['feedback_prev_text'] = prev_text
        context.user_data['feedback_prev_is_text'] = bool(prev_text and not prev_caption)
        try:
            context.user_data['feedback_prev_markup'] = query.message.reply_markup
        except Exception:
            context.user_data['feedback_prev_markup'] = None
        
        # درخواست متن بازخورد
        lang = await get_user_lang(update, context, self.db) or 'fa'
        prompt_suffix = "\n\n" + t('feedback.prompt.write', lang)
        is_text_msg = context.user_data['feedback_prev_is_text']
        try:
            if is_text_msg:
                base_text = (context.user_data.get('feedback_prev_text') or "")
                await safe_edit_message_text(
                    query,
                    text=(base_text + prompt_suffix),
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data=f"att_fb_cancel_{attachment_id}")]])
                )
            else:
                base_caption = (context.user_data.get('feedback_prev_caption') or "")
                await query.edit_message_caption(
                    caption=(base_caption + prompt_suffix),
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data=f"att_fb_cancel_{attachment_id}")]])
                )
        except Exception:
            # اگر یکی شکست خورد، روش دیگر را امتحان کن
            try:
                base_caption = (context.user_data.get('feedback_prev_caption') or "")
                await query.edit_message_caption(
                    caption=(base_caption + prompt_suffix),
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data=f"att_fb_cancel_{attachment_id}")]])
                )
            except Exception:
                base_text = (context.user_data.get('feedback_prev_text') or "")
                await safe_edit_message_text(
                    query,
                    text=(base_text + prompt_suffix),
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data=f"att_fb_cancel_{attachment_id}")]])
                )
        
        return FEEDBACK_TEXT
    
    @log_user_action("feedback_text_received")
    async def handle_feedback_text(self, update: Update, context: CustomContext):
        """
        دریافت متن بازخورد
        
        Uses: TextValidator.validate_comment() for feedback validation
        """
        user_id = update.effective_user.id
        feedback_text = update.message.text.strip()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # ✅ استفاده از validator مشترک با i18n
        result = TextValidator.validate_comment(feedback_text)
        if not result.is_valid:
            error_msg = t(result.error_key, lang, **(result.error_details or {}))
            await update.message.reply_text(error_msg)
            return FEEDBACK_TEXT
        
        # دریافت attachment_id از context
        attachment_id = context.user_data.get('feedback_attachment_id')
        if not attachment_id:
            await update.message.reply_text(t('feedback.error', lang))
            return ConversationHandler.END
        
        # ثبت بازخورد
        success = await self.db.submit_attachment_feedback(user_id, attachment_id, feedback_text)
        
        if success:
            await update.message.reply_text(t('feedback.submit.success', lang))
            logger.info(f"Feedback received: user={user_id}, att={attachment_id}, len={len(feedback_text)}")
        else:
            await update.message.reply_text(t('feedback.submit.error', lang))
        
        # پاک کردن context
        context.user_data.pop('feedback_attachment_id', None)
        
        return ConversationHandler.END
    
    @log_user_action("feedback_cancel")
    async def handle_feedback_cancel(self, update: Update, context: CustomContext):
        """لغو ثبت بازخورد"""
        query = update.callback_query
        if query:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t('common.cancelled', lang))
            # بازیابی caption و کیبورد قبلی؛ در صورت نبود، fallback به بازسازی دکمه‌ها
            prev_caption = context.user_data.pop('feedback_prev_caption', None)
            prev_text = context.user_data.pop('feedback_prev_text', None)
            prev_is_text = context.user_data.pop('feedback_prev_is_text', None)
            prev_markup = context.user_data.pop('feedback_prev_markup', None)
            # استخراج attachment_id برای fallback ساخت کیبورد
            try:
                attachment_id = int(query.data.replace("att_fb_cancel_", ""))
            except Exception:
                attachment_id = context.user_data.get('feedback_attachment_id')

            base_caption = (query.message.caption or "").split("\n\n💬")[0]
            base_text = (query.message.text or "").split("\n\n💬")[0]
            caption_to_set = prev_caption if prev_caption is not None else base_caption
            text_to_set = prev_text if prev_text is not None else base_text
            if prev_markup is None and attachment_id:
                prev_markup = InlineKeyboardMarkup(self.build_feedback_buttons(attachment_id, lang=lang))
            try:
                if prev_is_text:
                    await safe_edit_message_text(
                        query,
                        text=text_to_set,
                        parse_mode='Markdown',
                        reply_markup=prev_markup
                    )
                else:
                    await query.edit_message_caption(
                        caption=caption_to_set,
                        parse_mode='Markdown',
                        reply_markup=prev_markup
                    )
            except Exception:
                # fallback به هر دو حالت
                try:
                    await query.edit_message_caption(
                        caption=caption_to_set,
                        parse_mode='Markdown',
                        reply_markup=prev_markup
                    )
                except Exception:
                    await safe_edit_message_text(
                        query,
                        text=text_to_set,
                        parse_mode='Markdown',
                        reply_markup=prev_markup
                    )
        else:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await update.message.reply_text(t('common.cancelled', lang))
        
        # پاک کردن context
        context.user_data.pop('feedback_attachment_id', None)
        
        return ConversationHandler.END
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """بررسی محدودیت نرخ رأی‌دهی"""
        now = time.time()
        last_vote = self._vote_cooldown.get(user_id, 0)
        
        if now - last_vote < self.VOTE_COOLDOWN_SECONDS:
            return False
        
        self._vote_cooldown[user_id] = now
        return True
    
    async def _update_feedback_buttons(self, query, attachment_id: int, vote_result: dict, lang: str):
        """به‌روزرسانی کیبورد بازخورد.
        - اگر پیام یک «عکس اینلاین در گروه» باشد: فقط لایک/دیس‌لایک + ارسال در پی‌وی + ارسال عکس در گروه
        - در سایر حالات: کیبورد کامل (کپی کد + ثبت نظر نیز)
        """
        try:
            like_count = vote_result.get('like_count', 0)
            dislike_count = vote_result.get('dislike_count', 0)
            # دریافت اطلاعات اتچمنت برای تعیین mode و ساخت دکمه‌های لینک‌دار
            att = await self.db.get_attachment_by_id(attachment_id) or {}
            mode = (att.get('mode') or 'br').lower()
            # تعیین bot username
            try:
                bot_username = query.bot.username
            except Exception:
                import os
                bot_username = os.getenv('BOT_USERNAME', '')
            # تشخیص نوع پیام
            chat_type = None
            is_group = False
            is_photo = False
            is_inline = False
            is_via_inline_message = False
            try:
                chat_type = query.message.chat.type if query.message and query.message.chat else None
                is_group = chat_type in ("group", "supergroup")
                is_photo = bool(getattr(query.message, 'photo', None))
                is_inline = bool(getattr(query, 'inline_message_id', None)) and not bool(query.message)
                # پیام‌هایی که از طریق اینلاین ارسال شده‌اند: message.via_bot پر است
                is_via_inline_message = bool(getattr(query.message, 'via_bot', None)) if query.message else False
            except Exception:
                pass

            # ساخت ردیف‌ها بر اساس نوع پیام
            # هر پیام در چت خصوصی → کیبورد کامل
            # در گروه/سوپرگروه یا پیام‌های اینلاین بدون message → کیبورد مینیمال
            use_full_keyboard = (chat_type == "private")
            
            if not use_full_keyboard:
                rows = self.build_attachment_keyboard(
                    attachment_id, 
                    like_count=like_count, 
                    dislike_count=dislike_count, 
                    lang=lang,
                    is_group=True,
                    bot_username=bot_username,
                    mode=mode
                )
            else:
                # PM معمولی: کل کیبورد را با نسخه جدید و کامل جایگزین می‌کنیم تا استایل حفظ شود
                rows = self.build_attachment_keyboard(
                    attachment_id, 
                    like_count=like_count, 
                    dislike_count=dislike_count, 
                    lang=lang,
                    is_group=False
                )

            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(rows))
        except Exception as e:
            logger.error(f"Error updating feedback buttons: {e}")
    
    @require_channel_membership
    @log_user_action("copy_code")
    async def handle_copy_code(self, update: Update, context: CustomContext):
        """ثبت کلیک روی دکمه «📋 کپی کد» برای یک اتچمنت"""
        query = update.callback_query
        await query.answer()
        try:
            attachment_id = int(query.data.replace("att_copy_", ""))
        except ValueError:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t('feedback.error', lang), show_alert=True)
            return
        user_id = query.from_user.id
        try:
            await get_container().analytics.track_attachment_copy(
                user_id=user_id,
                attachment_id=attachment_id
            )
            # ابتدا از DB کد دقیق را می‌گیریم؛ اگر در دسترس نبود به متن پیام fallback
            code = None
            try:
                if hasattr(self.db, 'get_attachment_code_by_id'):
                    code = await self.db.get_attachment_code_by_id(attachment_id)
            except Exception:
                code = None
            if not code:
                try:
                    src_text = (query.message.caption or query.message.text or "")
                except Exception:
                    src_text = ""
                # الگوهای رایج: کد: `CODE` یا Code: `CODE`
                m = re.search(r"(?:کد|Code)\s*:\s*`([^`]+)`", src_text)
                if m:
                    code = m.group(1).strip()
            # پاسخ کاربر: اگر امکان Reply نیست (inline msg)، کد را در Alert نشان بده
            if code:
                sent = False
                try:
                    await query.message.reply_text(t('attachment.code_copy_message', await get_user_lang(update, context, self.db) or 'fa', code=code), parse_mode='Markdown')
                    sent = True
                except Exception:
                    sent = False
                if not sent:
                    # نمایش در alert (حداکثر ~200 کاراکتر)
                    await query.answer(t('attachment.copy_inline_alert', await get_user_lang(update, context, self.db) or 'fa', code=code), show_alert=True)
                else:
                    await query.answer(t('attachment.copy_ready', await get_user_lang(update, context, self.db) or 'fa'), show_alert=False)
            else:
                await query.answer(t('attachment.copy.inline_hint', await get_user_lang(update, context, self.db) or 'fa'), show_alert=True)
        except Exception as e:
            from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)
    
    def build_attachment_keyboard(self, attachment_id: int, like_count: int = 0, dislike_count: int = 0, lang: str = 'fa', is_group: bool = False, bot_username: str = None, mode: str = 'br') -> list:
        """
        ساخت کیبورد استاندارد شامل لایک، کپی کد و ثبت نظر
        """
        rows = [
            [
                InlineKeyboardButton(f"👍 {like_count}", callback_data=f"att_like_{attachment_id}"),
                InlineKeyboardButton(f"👎 {dislike_count}", callback_data=f"att_dislike_{attachment_id}")
            ]
        ]
        
        if is_group:
            # در گروه‌ها: دکمه ارسال در پی‌وی و اشتراک‌گذاری
            if bot_username:
                rows.append([InlineKeyboardButton(t('share.send_pm', lang), url=f"https://t.me/{bot_username}?start=att-{attachment_id}-{mode or 'br'}")])
            rows.append([InlineKeyboardButton(t('share.send_image_group', lang), switch_inline_query_current_chat=f"att:{attachment_id}-{mode or 'br'}")])
        else:
            # در پی‌وی: کپی کد و ثبت نظر
            rows.append([InlineKeyboardButton(t('attachment.copy_code', lang), callback_data=f"att_copy_{attachment_id}")])
            rows.append([InlineKeyboardButton(t('attachment.feedback', lang), callback_data=f"att_fb_{attachment_id}")] )
            
        return rows

    def build_feedback_buttons(self, attachment_id: int, like_count: int = 0, dislike_count: int = 0, lang: str = 'fa') -> list:
        """نسخه قدیمی - جهت حفظ سازگاری (استفاده از نسخه جدید توصیه می‌شود)"""
        return self.build_attachment_keyboard(attachment_id, like_count, dislike_count, lang, is_group=False)
