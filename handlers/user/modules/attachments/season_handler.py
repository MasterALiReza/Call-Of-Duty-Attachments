from core.context import CustomContext
"""
مدیریت برترهای فصل
⚠️ این کد عیناً از user_handlers.py خط 1418-1740 کپی شده
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.config import ITEMS_PER_PAGE
from managers.channel_manager import require_channel_membership
from utils.logger import log_user_action
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text
from handlers.user.base_user_handler import BaseUserHandler
from typing import Tuple
import math

class SeasonTopHandler(BaseUserHandler):
    """مدیریت برترهای فصل"""

    @require_channel_membership
    @log_user_action('season_top_select_mode_msg')
    async def season_top_select_mode_msg(self, update: Update, context: CustomContext):
        """انتخاب mode برای برترهای فصل (از طریق پیام)"""
        from datetime import datetime
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [[InlineKeyboardButton(t('mode.br_btn', lang), callback_data='season_top_mode_br'), InlineKeyboardButton(t('mode.mp_btn', lang), callback_data='season_top_mode_mp')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        now = datetime.now().strftime('%H:%M:%S')
        text = t('menu.buttons.season_top', lang) + f" _{t('notification.updated', lang, time=now)}_\n\n"
        text += t('season.choose_mode', lang)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_select_mode')
    async def season_top_select_mode(self, update: Update, context: CustomContext):
        """انتخاب mode برای برترهای فصل (از طریق inline)"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [[InlineKeyboardButton(t('mode.br_btn', lang), callback_data='season_top_mode_br'), InlineKeyboardButton(t('mode.mp_btn', lang), callback_data='season_top_mode_mp')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = t('menu.buttons.season_top', lang) + '\n\n'
        text += t('season.choose_mode', lang)
        await safe_edit_message_text(query, text, reply_markup=reply_markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_media_msg')
    async def season_top_media_msg(self, update: Update, context: CustomContext):
        """ارسال اتچمنت\u200cهای برتر فصل به صورت گالری (از طریق پیام)
        این تابع قدیمی برای backward compatibility - اکنون از season_top_select_mode_msg استفاده کنید
        """
        return await self.season_top_select_mode_msg(update, context)

    @require_channel_membership
    @log_user_action('season_top_media_with_mode')
    async def season_top_media_with_mode(self, update: Update, context: CustomContext):
        """ارسال اتچمنت\u200cهای برتر فصل با mode مشخص شده (از طریق پیام)"""
        query = update.callback_query
        await query.answer()
        mode = query.data.replace('season_top_mode_', '')
        context.user_data['season_top_mode'] = mode
        lang = await get_user_lang(update, context, self.db) or 'fa'
        items = await self.db.get_season_top_attachments(mode=mode)
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        if not items:
            await query.message.reply_text(t('attachment.none', lang))
            return
        await safe_edit_message_text(query, t('season.title', lang, mode=mode_name))
        for i, raw_item in enumerate(items, 1):
            item = raw_item
            att = item['attachment']
            weapon = item['weapon']
            cat_name = t(f"category.{item['category']}", 'en')
            caption = f"**#{i} - {att['name']}**\n{t('attachment.code', lang)}: `{att['code']}`\n{t('weapon.label', lang)}: {weapon} ({cat_name})\n{mode_name}\n\n{t('attachment.tap_to_copy', lang)}"
            att_id = att.get('id')
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
                if att.get('image'):
                    await query.message.reply_photo(photo=att['image'], caption=caption, parse_mode='Markdown', reply_markup=feedback_kb)
                else:
                    await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
            except Exception:
                await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='season_top')], [InlineKeyboardButton(t('menu.buttons.home', lang), callback_data='main_menu')]])
        await query.message.reply_text(t('success.generic', lang), reply_markup=back_markup)

    @require_channel_membership
    @log_user_action('season_top_media')
    async def season_top_media(self, update: Update, context: CustomContext):
        """ارسال اتچمنت\u200cهای برتر فصل به صورت گالری (از طریق اینلاین منو)
        Redirect به انتخاب mode
        """
        return await self.season_top_select_mode(update, context)

    async def _season_top_cache(self, context: CustomContext, mode: str=None) -> list:
        """ذخیره اتچمنت\u200cهای برتر فصل با mode مشخص در cache"""
        items = await self.db.get_season_top_attachments(mode=mode)
        context.user_data['season_top_cache'] = items
        return items

    def _season_top_build_page(self, items: list, page: int, mode: str=None, lang: str='fa') -> Tuple[str, InlineKeyboardMarkup, int]:
        """ساخت صفحه لیست برترهای فصل"""
        total_items = len(items)
        total_pages = max(1, math.ceil(total_items / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}" if mode else f"{t('mode.label', lang)}: {t('mode.all', lang)}"
        text = t('season.list_title', lang, mode=mode_name) + '\n' + t('pagination.page_of', lang, page=page, total=total_pages) + '\n\n'
        keyboard = []
        for i, raw_item in enumerate(items[start_idx:end_idx], start_idx + 1):
            item = raw_item
            att = item['attachment']
            weapon = item['weapon']
            text += f"**{i}.** {att['name']} — {weapon}\n{t('attachment.code', lang)}: `{att['code']}`\n\n"
            keyboard.append([InlineKeyboardButton(f"{i}. {att['name']} ({weapon})", callback_data=f'satt_{i}')])
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(t('nav.prev', lang), callback_data=f'slist_page_{page - 1}'))
        nav.append(InlineKeyboardButton(f'{page}/{total_pages}', callback_data='noop'))
        if page < total_pages:
            nav.append(InlineKeyboardButton(t('nav.next', lang), callback_data=f'slist_page_{page + 1}'))
        if nav:
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='season_top_list')])
        keyboard.append([InlineKeyboardButton(t('menu.buttons.home', lang), callback_data='main_menu')])
        return (text, InlineKeyboardMarkup(keyboard), page)

    @require_channel_membership
    @log_user_action('season_top_list_select_mode_msg')
    async def season_top_list_select_mode_msg(self, update: Update, context: CustomContext):
        """انتخاب mode برای لیست برترهای فصل (از طریق پیام)"""
        from datetime import datetime
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [[InlineKeyboardButton(t('mode.br_btn', lang), callback_data='season_list_mode_br'), InlineKeyboardButton(t('mode.mp_btn', lang), callback_data='season_list_mode_mp')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        now = datetime.now().strftime('%H:%M:%S')
        text = t('menu.buttons.season_list', lang) + f" _{t('notification.updated', lang, time=now)}_\n\n" + t('season.choose_mode', lang)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_list_select_mode')
    async def season_top_list_select_mode(self, update: Update, context: CustomContext):
        """انتخاب mode برای لیست برترهای فصل (از طریق inline)"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [[InlineKeyboardButton(t('mode.br_btn', lang), callback_data='season_list_mode_br'), InlineKeyboardButton(t('mode.mp_btn', lang), callback_data='season_list_mode_mp')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = t('menu.buttons.season_list', lang) + '\n\n' + t('season.choose_mode', lang)
        await safe_edit_message_text(query, text, reply_markup=reply_markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_list_msg')
    async def season_top_list_msg(self, update: Update, context: CustomContext):
        """نمایش لیست برترهای فصل به صورت لیستی (از طریق پیام)
        Redirect به انتخاب mode
        """
        return await self.season_top_list_select_mode_msg(update, context)

    @require_channel_membership
    @log_user_action('season_top_list_with_mode')
    async def season_top_list_with_mode(self, update: Update, context: CustomContext):
        """نمایش لیست برترهای فصل با mode مشخص شده"""
        query = update.callback_query
        await query.answer()
        mode = query.data.replace('season_list_mode_', '')
        context.user_data['season_top_list_mode'] = mode
        lang = await get_user_lang(update, context, self.db) or 'fa'
        items = await self._season_top_cache(context, mode=mode)
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        if not items:
            await safe_edit_message_text(query, t('attachment.none', lang), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='season_top_list')], [InlineKeyboardButton(t('menu.buttons.home', lang), callback_data='main_menu')]]))
            return
        text, markup, page = self._season_top_build_page(items, 1, mode, lang)
        context.user_data['season_top_page'] = page
        await safe_edit_message_text(query, text, reply_markup=markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_list')
    async def season_top_list(self, update: Update, context: CustomContext):
        """نمایش لیست برترهای فصل به صورت لیستی (از طریق اینلاین)
        Redirect به انتخاب mode
        """
        return await self.season_top_list_select_mode(update, context)

    @require_channel_membership
    @log_user_action('season_top_list_page_navigation')
    async def season_top_list_page_navigation(self, update: Update, context: CustomContext):
        """مدیریت navigation بین صفحات لیست برترهای فصل"""
        query = update.callback_query
        await query.answer()
        items = context.user_data.get('season_top_cache')
        mode = context.user_data.get('season_top_list_mode')
        if not items:
            items = await self._season_top_cache(context, mode=mode)
        page = 1
        if query.data.startswith('slist_page_'):
            try:
                page = int(query.data.replace('slist_page_', ''))
            except ValueError:
                page = 1
        lang = await get_user_lang(update, context, self.db) or 'fa'
        text, markup, page = self._season_top_build_page(items, page, mode, lang)
        context.user_data['season_top_page'] = page
        await safe_edit_message_text(query, text, reply_markup=markup, parse_mode='Markdown')

    @require_channel_membership
    @log_user_action('season_top_item_detail')
    async def season_top_item_detail(self, update: Update, context: CustomContext):
        """نمایش جزئیات یک آیتم از لیست برترهای فصل بر اساس ایندکس"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        items = context.user_data.get('season_top_cache') or self._season_top_cache(context)
        try:
            idx = int(query.data.replace('satt_', ''))
        except Exception:
            await query.answer()
            return
        if idx < 1 or idx > len(items):
            await query.answer(t('attachment.not_found', lang))
            return
        raw_item = items[idx - 1]
        item = raw_item
        att = item['attachment']
        weapon = item['weapon']
        cat_name = t(f"category.{item['category']}", 'en')
        mode_short = t(f"mode.{item['mode']}_short", lang)
        mode_name = f"{t('mode.label', lang)}: {mode_short}"
        caption = f"**{att['name']}**\n{t('attachment.code', lang)}: `{att['code']}`\n{t('weapon.label', lang)}: {weapon} ({cat_name})\n{mode_name}"
        att_id = att.get('id')
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
                mode=item.get('mode', 'br')
            ))
        try:
            if att.get('image'):
                await query.message.reply_photo(photo=att['image'], caption=caption, parse_mode='Markdown', reply_markup=feedback_kb)
            else:
                await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
        except Exception:
            await query.message.reply_text(caption, parse_mode='Markdown', reply_markup=feedback_kb)
        page = context.user_data.get('season_top_page', 1)
        back_markup = InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f'slist_page_{page}')]])
        await query.message.reply_text(t('success.generic', lang), reply_markup=back_markup)