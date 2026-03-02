from core.context import CustomContext
"""
مدیریت نمایش تمام اتچمنت‌ها با pagination
⚠️ این کد عیناً از user_handlers.py خط 655-962 کپی شده
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.config import ITEMS_PER_PAGE
from managers.channel_manager import require_channel_membership
from utils.logger import log_user_action, get_logger
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text
from handlers.user.base_user_handler import BaseUserHandler
from core.container import get_container
import math

logger = get_logger('user', 'user.log')


class AllAttachmentsHandler(BaseUserHandler):
    """مدیریت نمایش تمام اتچمنت‌ها با pagination"""
    
    @require_channel_membership
    @log_user_action("show_all_attachments")

    async def show_all_attachments(self, update: Update, context: CustomContext):
        """نمایش همه اتچمنت‌ها - اگر از search بیاد هر دو mode، اگر از منو بیاد فقط همون mode"""
        query = update.callback_query
        await query.answer()
        
        # اگر پیام قبلی یک عکس است، حذف کن و پیام جدید بفرست
        should_send_new = query.message.photo is not None
        chat_id = query.message.chat_id
        
        # اگر از جستجو وارد شده باشد: all_{category}__{weapon}
        from_search = False
        if query.data.startswith("all_") and "__" in query.data and not query.data.startswith("all_page_"):
            from_search = True
            payload = query.data.replace("all_", "")
            try:
                category, weapon_name = payload.split("__", 1)
                context.user_data['current_category'] = category
                context.user_data['current_weapon'] = weapon_name
            except ValueError as e:
                logger.warning(f"Invalid callback data format: {query.data}")
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        category = context.user_data.get('current_category')
        weapon_name = context.user_data.get('current_weapon')
        
        # اگر از search آمده، هر دو mode را نمایش بده
        if from_search:
            br_atts = await self.db.get_all_attachments(category, weapon_name, mode="br")
            mp_atts = await self.db.get_all_attachments(category, weapon_name, mode="mp")
            
            if not br_atts and not mp_atts:
                if should_send_new:
                    await query.message.delete()
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=t('attachment.none', lang),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="search_weapon")
                        ]])
                    )
                else:
                    await safe_edit_message_text(
                        query,
                        t('attachment.none', lang),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="search_weapon")
                        ]])
                    )
                return
            
            # ساخت متن و دکمه‌ها برای هر دو mode
            text = t('attachment.all.header', lang, weapon=weapon_name) + "\n\n"
            
            # تعداد ردیف‌ها = بیشترین تعداد بین BR و MP
            max_items = max(len(br_atts), len(mp_atts))
            
            # ساخت متن دو ستونی
            if br_atts:
                text += f"**{t('mode.label', lang)}: {t('mode.br_short', lang)} {t('attachment.count_label', lang, count=len(br_atts))}**\n"
                for i, att in enumerate(br_atts, 1):
                    text += f"{i}. {att['name']}\n"
                text += "\n"
            
            if mp_atts:
                text += f"**{t('mode.label', lang)}: {t('mode.mp_short', lang)} {t('attachment.count_label', lang, count=len(mp_atts))}**\n"
                for i, att in enumerate(mp_atts, 1):
                    text += f"{i}. {att['name']}\n"
                text += "\n"
            
            # ساخت دکمه‌های دو ستونی
            keyboard = []
            for i in range(max_items):
                row = []
                # ستون BR (چپ)
                if i < len(br_atts):
                    att = br_atts[i]
                    row.append(InlineKeyboardButton(
                        f"🪂 {att['name'][:18]}", 
                        callback_data=f"attm_br_{att['code']}"
                    ))
                # ستون MP (راست)
                if i < len(mp_atts):
                    att = mp_atts[i]
                    row.append(InlineKeyboardButton(
                        f"🎮 {att['name'][:18]}", 
                        callback_data=f"attm_mp_{att['code']}"
                    ))
                
                if row:
                    keyboard.append(row)
            
            # دکمه دریافت همه در آخر
            download_buttons = []
            if br_atts:
                download_buttons.append(InlineKeyboardButton(
                    t('attachment.download_all', lang, mode=t('mode.br_btn', lang), count=len(br_atts)),
                    callback_data=f"download_all_br_{category}__{weapon_name}"
                ))
            if mp_atts:
                download_buttons.append(InlineKeyboardButton(
                    t('attachment.download_all', lang, mode=t('mode.mp_btn', lang), count=len(mp_atts)),
                    callback_data=f"download_all_mp_{category}__{weapon_name}"
                ))
            if download_buttons:
                keyboard.append(download_buttons)
            
            keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="search_weapon")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            if should_send_new:
                await query.message.delete()
                await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await safe_edit_message_text(query, text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # اگر از منوی عادی آمده (با mode مشخص)
        mode = context.user_data.get('current_mode', 'br')
        all_attachments = await self.db.get_all_attachments(category, weapon_name, mode=mode)
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        if not all_attachments:
            if should_send_new:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=t('attachment.none', lang),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"mode_{mode}_{weapon_name}")
                    ]])
                )
            else:
                await safe_edit_message_text(
                    query,
                    t('attachment.none', lang),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"mode_{mode}_{weapon_name}")
                    ]])
                )
            return
        
        # محاسبه صفحه‌بندی
        page = 1
        if query.data.startswith("all_page_"):
            page = int(query.data.replace("all_page_", ""))
        
        total_items = len(all_attachments)
        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        
        context.user_data['all_page'] = page
        
        # ساخت متن
        text = t('attachment.all.title', lang, weapon=weapon_name, mode=mode_name) + "\n"
        text += t('pagination.page_of', lang, page=page, total=total_pages) + "\n\n"
        
        for i, att in enumerate(all_attachments[start_idx:end_idx], start_idx + 1):
            text += f"**{i}.** {att['name']}\n"
            text += f"   {t('attachment.code', lang)}: `{att['code']}`\n\n"
        
        # ساخت دکمه‌ها
        keyboard = []
        for i, att in enumerate(all_attachments[start_idx:end_idx], start_idx + 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {att['name']}", callback_data=f"att_{att['code']}")])
        
        # دکمه‌های صفحه‌بندی
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(t('nav.prev', lang), callback_data=f"all_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(t('nav.next', lang), callback_data=f"all_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"mode_{mode}_{weapon_name}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        if should_send_new:
            await query.message.delete()
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await safe_edit_message_text(query, text, reply_markup=reply_markup, parse_mode='Markdown')
    
    @require_channel_membership
    @log_user_action("show_all_attachments_msg")

    async def show_all_attachments_msg(self, update: Update, context: CustomContext):
        """نمایش همه اتچمنت‌ها از طریق پیام (کیبورد پایین) با پشتیبانی از mode"""
        from datetime import datetime
        
        category = context.user_data.get('current_category')
        weapon_name = context.user_data.get('current_weapon')
        mode = context.user_data.get('current_mode', 'br')
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if not category or not weapon_name:
            await update.message.reply_text(t('weapon.select_first', lang))
            return
        
        all_attachments = await self.db.get_all_attachments(category, weapon_name, mode=mode)
        if not all_attachments:
            await update.message.reply_text(t('attachment.none', lang))
            return
        
        # صفحه اول را نمایش بده و ناوبری را با اینلاین نگه دار
        page = 1
        total_items = len(all_attachments)
        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        context.user_data['all_page'] = page
        
        # اضافه کردن timestamp برای جلوگیری از duplicate detection
        now = datetime.now().strftime("%H:%M:%S")
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_btn', lang)}"
        text = t('attachment.all.title', lang, weapon=weapon_name, mode=mode_name) + f" _{t('notification.updated', lang, time=now)}_\n"
        text += t('pagination.page_of', lang, page=page, total=total_pages) + "\n\n"
        for i, att in enumerate(all_attachments[start_idx:end_idx], start_idx + 1):
            stats = await self.db.get_attachment_stats(att['id'], period='all')
            likes = stats.get('like_count', 0)
            text += f"**{i}.** {att['name']}"
            if likes > 0:
                text += f" 👍{likes}"
            text += f"\n   {t('attachment.code', lang)}: `{att['code']}`\n\n"
        
        # دکمه انتخاب اتچمنت‌ها
        keyboard = []
        for i, att in enumerate(all_attachments[start_idx:end_idx], start_idx + 1):
            stats = await self.db.get_attachment_stats(att['id'], period='all')
            likes = stats.get('like_count', 0)
            button_text = f"{i}. {att['name']}"
            if likes > 0:
                button_text += f" 👍{likes}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"att_{att['code']}")])
        # دکمه‌های صفحه‌بندی با چپ/راست
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(t('nav.prev', lang), callback_data=f"all_page_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(t('nav.next', lang), callback_data=f"all_page_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"mode_{mode}_{weapon_name}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    @require_channel_membership
    async def attachment_detail_with_mode(self, update: Update, context: CustomContext):
        """نمایش جزئیات اتچمنت با mode در callback: attm_{mode}_{code}"""
        query = update.callback_query
        await query.answer()
        
        payload = query.data.replace("attm_", "")
        try:
            mode, code = payload.split("_", 1)
        except ValueError:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            logger.warning(f"Invalid attachment detail payload: {query.data}")
            await safe_edit_message_text(query, t('error.generic', lang))
            return
        
        category = context.user_data.get('current_category')
        weapon_name = context.user_data.get('current_weapon')
        
        if not category or not weapon_name:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await safe_edit_message_text(query, t('weapon.select_first', lang))
            return
        
        # ست کردن mode
        context.user_data['current_mode'] = mode
        
        attachments = await self.db.get_all_attachments(category, weapon_name, mode=mode)
        selected = next((att for att in attachments if att.get('code') == code), None)
        if not selected:
            await safe_edit_message_text(query, t('attachment.not_found', lang))
            return
        
        mode_short = t(f"mode.{mode}_short", lang)
        mode_name = f"{t('mode.label', lang)}: {mode_short}"
        caption = f"**{selected['name']}**\n{t('attachment.code', lang)}: `{selected['code']}`\n{mode_name}"
        
        # دریافت آمار بازخورد
        att_id = selected.get('id')
        stats = await self.db.get_attachment_stats(att_id, period='all') if att_id else {}
        like_count = stats.get('like_count', 0)
        dislike_count = stats.get('dislike_count', 0)
        
        # Track view و copy
        if att_id:
            await get_container().analytics.track_attachment_view(
                user_id=query.from_user.id,
                attachment_id=att_id
            )
        
        # ساخت keyboard با دکمه‌های بازخورد
        keyboard = []
        if att_id:
            from core.container import get_container
            fb_handler = get_container().feedback_handler
            keyboard.extend(fb_handler.build_attachment_keyboard(
                att_id, 
                like_count=like_count, 
                dislike_count=dislike_count, 
                lang=lang,
                mode=mode
            ))
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"all_{category}__{weapon_name}")])
        
        try:
            if selected.get('image'):
                await query.message.reply_photo(
                    photo=selected['image'], 
                    caption=caption, 
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.message.reply_text(
                    caption, 
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception:
            await query.message.reply_text(
                caption, 
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # پیام تأیید
        await safe_edit_message_text(query, t('success.generic', lang))
    
    @require_channel_membership
    async def attachment_detail(self, update: Update, context: CustomContext):
        """نمایش جزئیات یک اتچمنت و ارسال عکس + کد"""
        query = update.callback_query
        await query.answer()
        
        code = query.data.replace("att_", "")
        category = context.user_data.get('current_category')
        weapon_name = context.user_data.get('current_weapon')
        mode = context.user_data.get('current_mode', 'br')  # دریافت mode از context
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if not category or not weapon_name:
            await safe_edit_message_text(query, t('weapon.select_first', lang))
            return
        
        attachments = await self.db.get_all_attachments(category, weapon_name, mode=mode)  # اضافه کردن mode
        selected = next((att for att in attachments if att.get('code') == code), None)
        if not selected:
            await safe_edit_message_text(query, t('attachment.not_found', lang))
            return
        
        caption = f"**{selected['name']}**\n{t('attachment.code', lang)}: `{selected['code']}`"
        
        # دریافت آمار بازخورد
        att_id = selected.get('id')
        stats = await self.db.get_attachment_stats(att_id, period='all') if att_id else {}
        like_count = stats.get('like_count', 0)
        dislike_count = stats.get('dislike_count', 0)
        
        # Track view
        if att_id:
            await get_container().analytics.track_attachment_view(
                user_id=query.from_user.id,
                attachment_id=att_id
            )
        
        # ساخت keyboard با دکمه‌های بازخورد
        keyboard = []
        if att_id:
            from core.container import get_container
            fb_handler = get_container().feedback_handler
            keyboard.extend(fb_handler.build_attachment_keyboard(
                att_id, 
                like_count=like_count, 
                dislike_count=dislike_count, 
                lang=lang,
                mode=mode
            ))
        
        # دکمه بازگشت به لیست همان صفحه
        page = context.user_data.get('all_page', 1)
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"all_page_{page}")])
        
        try:
            if selected.get('image'):
                await query.message.reply_photo(
                    photo=selected['image'], 
                    caption=caption, 
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.message.reply_text(
                    caption, 
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception:
            await query.message.reply_text(
                caption, 
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        # پیام تأیید
        await safe_edit_message_text(query, t('success.generic', lang))
