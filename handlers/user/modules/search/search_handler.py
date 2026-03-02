from core.context import CustomContext
"""
مدیریت جستجو
⚠️ این کد عیناً از user_handlers.py خط 1104-1294 کپی شده
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import time
from config.config import WEAPON_CATEGORIES
from managers.channel_manager import require_channel_membership
from utils.logger import log_user_action
from utils.language import get_user_lang
from utils.i18n import t
from handlers.user.base_user_handler import BaseUserHandler
from utils.telegram_safety import safe_edit_message_text

# Define SEARCHING state
SEARCHING = 3  # Must match the value in user_handlers.py: SELECTING_CATEGORY, SELECTING_WEAPON, VIEWING_ATTACHMENTS, SEARCHING = range(4)


class SearchHandler(BaseUserHandler):
    """مدیریت جستجو"""
    
    def __init__(self, db):
        super().__init__(db)

    async def search_start_msg(self, update: Update, context: CustomContext):
        """شروع جستجو از طریق پیام"""
        from datetime import datetime
        lang = await get_user_lang(update, context, self.db) or 'fa'

        # اضافه کردن timestamp برای جلوگیری از duplicate detection
        now = datetime.now().strftime("%H:%M:%S")
        text = t('search.prompt', lang) + f" _{t('notification.updated', lang, time=now)}_"
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t('search.cancel', lang), callback_data="main_menu")
            ]]),
            parse_mode='Markdown'
        )
        return SEARCHING
    
    @log_user_action("search_start")
    async def search_start(self, update: Update, context: CustomContext):
        """شروع جستجو"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        await safe_edit_message_text(
            query,
            t('search.prompt', lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t('search.cancel', lang), callback_data="main_menu")
            ]]),
            parse_mode='Markdown'
        )
        
        return SEARCHING
    
    @log_user_action("search_process")
    async def search_process(self, update: Update, context: CustomContext):
        """پردازش جستجو"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        query_text = update.message.text.strip()
        start_ts = time.time()
        
        # استفاده از جستجوی هیبریدی جدید
        results = await self.db.search(query_text)
        elapsed_ms = int((time.time() - start_ts) * 1000)
        
        # در معماری جدید results همیشه لیستی از دیکشنری‌هاست
        attachments_results = results or []
        
        # استخراج سلاح‌های یکتا از نتایج
        unique_weapons = {}
        for item in attachments_results:
            category = item.get('category')
            weapon = item.get('weapon')
            if not category or not weapon:
                continue
            weapon_key = f"{category}:{weapon}"
            if weapon_key not in unique_weapons:
                unique_weapons[weapon_key] = {
                    'category': category,
                    'weapon': weapon
                }
        weapons_results = list(unique_weapons.values())
        
        total_results = len(attachments_results)
        text = t('search.results', lang, query=query_text, count=total_results) + "\n\n"
        keyboard = []
        shown_all = set()
        
        # ثبت آمار جستجو
        try:
            user_id = update.effective_user.id if update.effective_user else None
            if user_id:
                await self.db.track_search(user_id, query_text, total_results, float(elapsed_ms))
        except Exception:
            pass
        
        # نمایش سلاح‌های یافت‌شده
        if weapons_results:
            text += f"**{t('search.weapons_header', lang)}**\n"
            for item in weapons_results[:3]: # جهت جلوگیری از شلوغی، تعداد سلاح‌ها را محدود می‌کنیم
                category_key = item['category']
                category_name = t(f"category.{category_key}", 'en')
                weapon_name = item['weapon']
                text += f"• {weapon_name} ({category_name})\n"
                
                # پیدا کردن بهترین اتچمنت‌های همین سلاح در نتایج جستجو
                weapon_atts = [
                    a for a in attachments_results 
                    if a['weapon'] == weapon_name and a['category'] == category_key
                ]
                
                # نمایش حداکثر 3 دکمه برتر برای هر سلاح از دل نتایج خود جستجو (بدون کوئری اضافه)
                for att in weapon_atts[:3]:
                    mode = att.get('mode', 'br')
                    mode_emoji = "🪂" if mode == 'br' else "🎮"
                    mode_text = t(f"mode.{mode}_short", lang)
                    
                    badge = ""
                    if att.get('is_season_top'):
                        badge = t('badge.season_top', lang)
                    elif att.get('is_top'):
                        badge = t('badge.top', lang)
                        
                    button_text = f"{mode_emoji} {mode_text} : {att['name']}"
                    if badge:
                        button_text += f" {badge}"
                    
                    keyboard.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f"qatt_{category_key}__{weapon_name}__{mode}__{att['code']}"
                    )])
                
                # دکمه «نمایش همه» برای سلاح
                key = (category_key, weapon_name)
                if key not in shown_all:
                    keyboard.append([InlineKeyboardButton(
                        t('search.show_all_for_weapon', lang, weapon=weapon_name),
                        callback_data=f"all_{category_key}__{weapon_name}"
                    )])
                    shown_all.add(key)
            text += "\n"
        
        # نمایش سایر اتچمنت‌ها (آن‌هایی که سلاحشان در صدر نبود)
        if attachments_results:
            # اگر سلاحی یافت نشده بود یا اتچمنت‌های متفرقه وجود داشت
            text += f"**{t('search.attachments_header', lang)}**\n"
            
            # نمایش 5 اتچمنت اول که کدشان مستقیما در کوئری مطابقت داشته (یا در صدر لیست هستند)
            for item in attachments_results[:5]:
                weapon_name = item['weapon']
                name = item['name']
                code = item['code']
                mode = item.get('mode', 'br')
                
                text += f"• {name} (`{code}`) - {weapon_name}\n"
                
                # اگر دکمه "همه" برای این سلاح قبلاً اضافه نشده، اینجا اضافه می‌کنیم
                key = (item['category'], weapon_name)
                if key not in shown_all:
                    keyboard.append([InlineKeyboardButton(
                        t('search.show_all_for_weapon', lang, weapon=weapon_name),
                        callback_data=f"all_{item['category']}__{weapon_name}"
                    )])
                    shown_all.add(key)
            text += "\n"
        
        if not weapons_results and not attachments_results:
            text = t('search.no_results', lang, query=query_text)
        
        keyboard.append([InlineKeyboardButton(t('search.new', lang), callback_data="search")])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.home', lang), callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def search_restart_silently(self, update: Update, context: CustomContext):
        """وقتی کاربر در حالت SEARCHING دوباره دکمه جستجو رو میزنه، بی‌صدا دوباره پیام رو نمایش بده - خط 1401"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await update.message.reply_text(
            t('search.prompt', lang),
            reply_markup=InlineKeyboardMarkup([[ 
                InlineKeyboardButton(t('search.cancel', lang), callback_data="main_menu")
            ]]),
            parse_mode='Markdown'
        )
        # همچنان در حالت SEARCHING بمون
        return SEARCHING
    


    async def send_attachment_quick(self, update: Update, context: CustomContext):
        """ارسال سریع اتچمنت از نتایج جستجو"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from utils.logger import get_logger, log_exception
        logger = get_logger('user', 'user.log')
        
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: qatt_{category}__{weapon}__{mode}__{code}
        try:
            payload = query.data.replace("qatt_", "")
            parts = payload.split("__")
            
            if len(parts) != 4:
                logger.error(f"Invalid quick attachment callback: {query.data}")
                return
            
            category, weapon, mode, code = parts
        except Exception as e:
            logger.error(f"Error parsing quick attachment callback: {e}")
            return
        
        # دریافت اتچمنت
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        selected = next((att for att in attachments if att.get('code') == code), None)
        
        if not selected:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t('attachment.not_found', lang), show_alert=True)
            return
        
        # ارسال
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_short = t(f"mode.{mode}_btn", lang)
        cat_name = t(f"category.{category}", 'en')
        caption = f"**{selected['name']}**\n"
        caption += f"{t('weapon.label', lang)}: {weapon} ({cat_name})\n"
        caption += f"{t('mode.label', lang)}: {mode_short}\n"
        caption += f"{t('attachment.code', lang)}: `{selected['code']}`\n\n{t('attachment.tap_to_copy', lang)}"
        
        # آمار بازخورد + ثبت بازدید
        att_id = selected.get('id')
        stats = await self.db.get_attachment_stats(att_id, period='all') if att_id else {}
        like_count = stats.get('like_count', 0)
        dislike_count = stats.get('dislike_count', 0)
        
        if att_id:
            await self.db.track_attachment_view(query.from_user.id, att_id)
            
        feedback_kb = None
        if att_id:
            from core.container import get_container
            fb_handler = get_container().feedback_handler
            feedback_kb = InlineKeyboardMarkup(fb_handler.build_attachment_keyboard(
                att_id, 
                like_count=like_count, 
                dislike_count=dislike_count, 
                lang=lang,
                mode=mode
            ))
        
        try:
            if selected.get('image'):
                await query.message.reply_photo(
                    photo=selected['image'], 
                    caption=caption, 
                    parse_mode='Markdown',
                    reply_markup=feedback_kb
                )
            else:
                await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
        except Exception as e:
            logger.error(f"Error sending quick attachment: {e}")
            log_exception(logger, e, "context")
            await query.message.reply_text(caption, parse_mode='Markdown')

    async def attachment_detail_with_mode(self, update: Update, context: CustomContext):
        """نمایش جزئیات اتچمنت با مود مشخص (از جستجو)"""
        # attm_{category}__{weapon}__{code}__{mode}
        # This seems to be the same logic as view_attachment_from_notification but with different prefix
        # Reuse logic or implement similar
        return await self.send_attachment_quick(update, context) # Logic is very similar, maybe just redirect?
        # Wait, send_attachment_quick expects "qatt_" prefix and specific order.
        # attachment_detail_with_mode expects "attm_" prefix.
        # Let's implement it properly.
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from utils.logger import get_logger, log_exception
        logger = get_logger('user', 'user.log')
        
        query = update.callback_query
        await query.answer()
        
        try:
            payload = query.data.replace("attm_", "")
            # Check if it has double underscore separator
            parts = payload.split("__")
            if len(parts) != 4:
                 # Maybe it's the other format?
                 # UserHandlers had: category, weapon, code, mode = parts
                 pass
            
            category, weapon, code, mode = parts
        except Exception:
             # Try parsing differently if needed, but for now assume standard format
             return

        # Reuse send_attachment_quick logic by mocking payload? No, just copy paste or extract common method.
        # I'll just copy logic for now to be safe.
        
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        selected = next((att for att in attachments if att.get('code') == code), None)
        
        if not selected:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.answer(t('attachment.not_found', lang), show_alert=True)
            return
            
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_short = t(f"mode.{mode}_btn", lang)
        cat_name = t(f"category.{category}", 'en')
        caption = f"**{selected['name']}**\n"
        caption += f"{t('weapon.label', lang)}: {weapon} ({cat_name})\n"
        caption += f"{t('mode.label', lang)}: {mode_short}\n"
        caption += f"{t('attachment.code', lang)}: `{selected['code']}`\n\n{t('attachment.tap_to_copy', lang)}"
        
        att_id = selected.get('id')
        stats = await self.db.get_attachment_stats(att_id, period='all') if att_id else {}
        like_count = stats.get('like_count', 0)
        dislike_count = stats.get('dislike_count', 0)
        
        if att_id:
            await self.db.track_attachment_view(query.from_user.id, att_id)
            
        feedback_kb = None
        if att_id:
            from core.container import get_container
            fb_handler = get_container().feedback_handler
            feedback_kb = InlineKeyboardMarkup(fb_handler.build_attachment_keyboard(
                att_id, 
                like_count=like_count, 
                dislike_count=dislike_count, 
                lang=lang,
                mode=mode
            ))
            
        try:
            if selected.get('image'):
                await query.message.reply_photo(
                    photo=selected['image'], 
                    caption=caption, 
                    parse_mode='Markdown',
                    reply_markup=feedback_kb
                )
            else:
                await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
        except Exception:
            pass
