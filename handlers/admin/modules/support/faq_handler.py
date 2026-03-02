from core.context import CustomContext
"""
ماژول مدیریت FAQ (سوالات متداول)
مسئول: مدیریت سوالات و پاسخ\u200cهای متداول
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import ADMIN_MENU, ADD_FAQ_QUESTION, ADD_FAQ_ANSWER, ADD_FAQ_CATEGORY, EDIT_FAQ_SELECT, EDIT_FAQ_QUESTION, EDIT_FAQ_ANSWER
from utils.logger import log_admin_action
from utils.language import get_user_lang
from utils.i18n import t

class FAQHandler(BaseAdminHandler):
    """Handler برای مدیریت FAQ"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._faq_cache_by_lang = {}
        self._stats_cache = None
        self._cache_time = 0
        self._cache_ttl = 30

    async def _get_cached_faqs(self, lang):
        """دریافت FAQها با cache (بر اساس زبان)"""
        import time
        current_time = time.time()
        cached_list = self._faq_cache_by_lang.get(lang)
        if cached_list is None or current_time - self._cache_time > self._cache_ttl:
            faqs = await self.db.get_faqs(lang=lang)
            self._faq_cache_by_lang[lang] = faqs
            self._stats_cache = await self.db.get_feedback_stats()
            self._cache_time = current_time
        return (self._faq_cache_by_lang.get(lang, []), self._stats_cache)

    def _invalidate_cache(self):
        """حذف cache بعد از تغییرات"""
        self._faq_cache_by_lang = {}
        self._stats_cache = None
        self._cache_time = 0

    def _get_faq_lang_label(self, ui_lang: str, faq_lang: str) -> str:
        return t('admin.faq.lang.fa', ui_lang) if faq_lang == 'fa' else t('admin.faq.lang.en', ui_lang)

    @log_admin_action('admin_faqs_menu')
    async def admin_faqs_menu(self, update: Update, context: CustomContext):
        """منوی مدیریت FAQ"""
        query = update.callback_query
        await query.answer()
        from core.security.role_manager import Permission
        user_id = update.effective_user.id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        if not await self.role_manager.has_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', ui_lang))
            return ADMIN_MENU
        faqs, feedback_stats = await self._get_cached_faqs(faq_lang)
        text = t('admin.faq.menu.title', ui_lang) + '\n\n'
        text += t('admin.faq.menu.count', ui_lang, count=len(faqs)) + '\n'
        text += t('admin.faq.menu.avg_rating', ui_lang, rating=f"{feedback_stats.get('average_rating', 0):.1f}") + '\n'
        text += t('admin.faq.menu.feedback_count', ui_lang, count=feedback_stats.get('total', 0)) + '\n'
        lang_label = self._get_faq_lang_label(ui_lang, faq_lang)
        text += t('admin.faq.menu.lang_current', ui_lang, current_lang=lang_label) + '\n'
        keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.add', ui_lang), callback_data='adm_faq_add'), InlineKeyboardButton(t('admin.faq.buttons.list', ui_lang), callback_data='adm_faq_list')], [InlineKeyboardButton(t('admin.faq.buttons.stats', ui_lang), callback_data='adm_faq_stats'), InlineKeyboardButton(t('admin.faq.buttons.feedback', ui_lang), callback_data='adm_feedback')], [InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_back')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    async def admin_faq_list(self, update: Update, context: CustomContext):
        """نمایش لیست FAQ ها"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        from core.security.role_manager import Permission
        if not await self.check_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', ui_lang))
            return ADMIN_MENU

        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        faqs, _ = await self._get_cached_faqs(faq_lang)
        if not faqs:
            text = t('admin.faq.list.empty_lang', ui_lang, faq_lang_name=faq_lang)
            keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.add', ui_lang), callback_data='adm_faq_add')], [InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')]]
        else:
            text = t('admin.faq.list.title', ui_lang, count=len(faqs)) + '\n\n'
            text += t('admin.faq.list.prompt', ui_lang) + '\n\n'
            keyboard = []
            for faq in faqs[:20]:
                short_q = faq['question'][:50] + '...' if len(faq['question']) > 50 else faq['question']
                views = faq.get('views', 0)
                keyboard.append([InlineKeyboardButton(t('admin.faq.list.item', ui_lang, q=short_q, views=views), callback_data=f"adm_faq_view_{faq['id']}")])
            keyboard.append([InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')])
            keyboard.append([InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    async def admin_faq_view(self, update: Update, context: CustomContext):
        """نمایش جزئیات یک FAQ"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        from core.security.role_manager import Permission
        if not await self.check_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', ui_lang))
            return ADMIN_MENU

        faq_id = int(query.data.split('_')[-1])
        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        faqs, _ = await self._get_cached_faqs(faq_lang)
        faq = next((f for f in faqs if f['id'] == faq_id), None)
        if not faq:
            await query.edit_message_text(t('common.not_found', ui_lang))
            return ADMIN_MENU
        text = t('admin.faq.view.title', ui_lang, id=faq_id) + '\n\n'
        text += t('admin.faq.view.question_label', ui_lang) + '\n' + faq['question'] + '\n\n'
        text += t('admin.faq.view.answer_label', ui_lang) + '\n' + faq['answer'] + '\n\n'
        text += t('admin.faq.view.category', ui_lang, category=faq.get('category', 'general')) + '\n'
        text += t('admin.faq.view.views', ui_lang, views=faq.get('views', 0)) + '\n'
        keyboard = [[InlineKeyboardButton(t('common.edit', ui_lang), callback_data=f'adm_faq_edit_{faq_id}'), InlineKeyboardButton(t('common.delete', ui_lang), callback_data=f'adm_faq_del_{faq_id}')], [InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='adm_faq_list')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    async def admin_faq_stats(self, update: Update, context: CustomContext):
        """نمایش آمار بازدید FAQ ها"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        from core.security.role_manager import Permission
        if not await self.role_manager.has_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', ui_lang))
            return ADMIN_MENU

        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        faqs, _ = await self._get_cached_faqs(faq_lang)
        sorted_faqs = sorted(faqs, key=lambda x: x.get('views', 0), reverse=True)
        text = t('admin.faq.stats.title', ui_lang) + '\n\n'
        text += t('admin.faq.stats.total_count', ui_lang, count=len(faqs)) + '\n'
        total_views = sum((f.get('views', 0) for f in faqs))
        text += t('admin.faq.stats.total_views', ui_lang, views=total_views) + '\n\n'
        text += t('admin.faq.stats.top_header', ui_lang) + '\n'
        for i, faq in enumerate(sorted_faqs[:5], 1):
            short_q = faq['question'][:35] + '...' if len(faq['question']) > 35 else faq['question']
            views = faq.get('views', 0)
            text += f"{i}. {short_q}\n   └─ 👁️ {views} {t('ua.view.views_label', ui_lang)}\n\n"
        keyboard = [[InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    @log_admin_action('admin_feedback_stats')
    async def admin_feedback_stats(self, update: Update, context: CustomContext):
        """نمایش آمار بازخوردها"""
        query = update.callback_query
        await query.answer()
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        _, stats = await self._get_cached_faqs(faq_lang)
        text = t('admin.faq.feedback.title', ui_lang) + '\n\n'
        text += t('admin.faq.feedback.avg', ui_lang, rating=f"{stats.get('average_rating', 0):.2f}") + '\n'
        text += t('admin.faq.feedback.total', ui_lang, total=stats.get('total', 0)) + '\n\n'
        text += t('admin.faq.feedback.dist_header', ui_lang) + '\n'
        distribution = stats.get('rating_distribution', {})
        for rating in [5, 4, 3, 2, 1]:
            count = distribution.get(str(rating), 0)
            stars = '⭐' * rating
            bar = '█' * (count // max(1, stats.get('total', 1) // 10))
            text += f'{stars} ({rating}): {count} {bar}\n'
        keyboard = [[InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    async def admin_faq_add_start(self, update: Update, context: CustomContext):
        """شروع افزودن FAQ جدید"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        from core.security.role_manager import Permission
        if not await self.check_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', ui_lang))
            return ADMIN_MENU

        text = t('admin.faq.add.title', ui_lang) + '\n\n' + t('admin.faq.add.prompt_q', ui_lang)
        keyboard = [[InlineKeyboardButton(t('menu.buttons.cancel', ui_lang), callback_data='admin_faqs')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADD_FAQ_CATEGORY

    @log_admin_action('admin_faq_category_selected')
    async def admin_faq_category_selected(self, update: Update, context: CustomContext):
        """انتخاب دسته\u200cبندی برای FAQ"""
        query = update.callback_query
        await query.answer()
        category = query.data.replace('adm_faq_cat_', '')
        context.user_data['faq_category'] = category
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.edit_message_text(t('admin.faq.add.prompt_q', ui_lang))
        return ADD_FAQ_QUESTION

    @log_admin_action('admin_faq_question_received')
    async def admin_faq_question_received(self, update: Update, context: CustomContext):
        """دریافت سوال FAQ"""
        question = update.message.text.strip()
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        if len(question) < 5:
            await update.message.reply_text(t('admin.faq.validation.question_short', ui_lang))
            return ADD_FAQ_QUESTION
        context.user_data['faq_question'] = question
        await update.message.reply_text(t('admin.faq.add.question_saved', ui_lang))
        return ADD_FAQ_ANSWER

    @log_admin_action('admin_faq_answer_received')
    async def admin_faq_answer_received(self, update: Update, context: CustomContext):
        """دریافت پاسخ FAQ و ذخیره"""
        answer = update.message.text.strip()
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        if len(answer) < 10:
            await update.message.reply_text(t('admin.faq.validation.answer_short', ui_lang))
            return ADD_FAQ_ANSWER
        question = context.user_data.get('faq_question', '')
        category = context.user_data.get('faq_category', 'general')
        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        success = await self.db.add_faq(question, answer, category, faq_lang)
        context.user_data.pop('faq_question', None)
        if success:
            self._invalidate_cache()
            faqs, feedback_stats = await self._get_cached_faqs(faq_lang)
            text = t('admin.faq.add.success.title', ui_lang) + '\n\n'
            text += t('admin.faq.menu.title', ui_lang) + '\n\n'
            text += t('admin.faq.menu.count', ui_lang, count=len(faqs)) + '\n'
            text += t('admin.faq.menu.avg_rating', ui_lang, rating=f"{feedback_stats.get('average_rating', 0):.1f}") + '\n'
            text += t('admin.faq.menu.feedback_count', ui_lang, count=feedback_stats.get('total', 0)) + '\n'
            lang_label = self._get_faq_lang_label(ui_lang, faq_lang)
            text += t('admin.faq.menu.lang_current', ui_lang, current_lang=lang_label) + '\n'
            keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.add', ui_lang), callback_data='adm_faq_add'), InlineKeyboardButton(t('admin.faq.buttons.list', ui_lang), callback_data='adm_faq_list')], [InlineKeyboardButton(t('admin.faq.buttons.stats', ui_lang), callback_data='adm_faq_stats'), InlineKeyboardButton(t('admin.faq.buttons.feedback', ui_lang), callback_data='adm_feedback')], [InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_back')]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text(t('admin.faq.error.save', ui_lang))
        return ADMIN_MENU

    @log_admin_action('admin_faq_edit')
    async def admin_faq_edit(self, update: Update, context: CustomContext):
        """ویرایش FAQ - انتخاب بخش مورد نظر"""
        query = update.callback_query
        await query.answer()
        faq_id = int(query.data.split('_')[-1])
        context.user_data['edit_faq_id'] = faq_id
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        faq_lang = context.user_data.get('faq_admin_lang') or ui_lang
        faqs, _ = await self._get_cached_faqs(faq_lang)
        faq = next((f for f in faqs if f['id'] == faq_id), None)
        if not faq:
            await query.edit_message_text(t('common.not_found', ui_lang))
            return ADMIN_MENU
        context.user_data['edit_faq_data'] = {'question': faq['question'], 'answer': faq['answer'], 'category': faq.get('category', 'general')}
        text = t('admin.faq.edit.title', ui_lang) + '\n\n'
        text += t('admin.faq.edit.current_question', ui_lang) + '\n' + faq['question'] + '\n\n'
        text += t('admin.faq.edit.current_answer_preview', ui_lang) + '\n' + faq['answer'][:100] + '...\n\n'
        text += t('admin.faq.edit.choose_field', ui_lang)
        keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.edit_q', ui_lang), callback_data='edit_faq_q'), InlineKeyboardButton(t('admin.faq.buttons.edit_a', ui_lang), callback_data='edit_faq_a')], [InlineKeyboardButton(t('admin.faq.lang.fa', ui_lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', ui_lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data=f'adm_faq_view_{faq_id}')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return EDIT_FAQ_SELECT

    @log_admin_action('admin_faq_edit_field_select')
    async def admin_faq_edit_field_select(self, update: Update, context: CustomContext):
        """انتخاب فیلد برای ویرایش"""
        query = update.callback_query
        await query.answer()
        field = query.data
        lang = await get_user_lang(update, context, self.db) or 'fa'
        if field == 'edit_faq_q':
            text = t('admin.faq.edit_q.prompt', lang)
            next_state = EDIT_FAQ_QUESTION
        else:
            text = t('admin.faq.edit_a.prompt', lang)
            next_state = EDIT_FAQ_ANSWER
        faq_id = context.user_data.get('edit_faq_id')
        keyboard = [[InlineKeyboardButton(t('admin.faq.lang.fa', lang), callback_data='adm_faq_lang_fa'), InlineKeyboardButton(t('admin.faq.lang.en', lang), callback_data='adm_faq_lang_en')], [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f'adm_faq_edit_{faq_id}'), InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data='admin_cancel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return next_state

    @log_admin_action('admin_faq_edit_question_received')
    async def admin_faq_edit_question_received(self, update: Update, context: CustomContext):
        """دریافت سوال جدید برای ویرایش"""
        new_question = update.message.text.strip()
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        if len(new_question) < 5:
            await update.message.reply_text(t('admin.faq.validation.question_short', ui_lang))
            return EDIT_FAQ_QUESTION
        faq_id = context.user_data.get('edit_faq_id')
        if not faq_id:
            await update.message.reply_text(t('common.not_found', ui_lang))
            return ADMIN_MENU
        success = await self.db.update_faq(faq_id, question=new_question)
        if success:
            self._invalidate_cache()
        context.user_data.pop('edit_faq_id', None)
        context.user_data.pop('edit_faq_data', None)
        if success:
            text = t('admin.faq.edit_q.success', ui_lang) + '\n\n'
            keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.view', ui_lang), callback_data=f'adm_faq_view_{faq_id}')], [InlineKeyboardButton(t('admin.faq.buttons.back_to_list', ui_lang), callback_data='adm_faq_list')]]
        else:
            text = t('admin.faq.error.update', ui_lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    @log_admin_action('admin_faq_edit_answer_received')
    async def admin_faq_edit_answer_received(self, update: Update, context: CustomContext):
        """دریافت پاسخ جدید برای ویرایش"""
        new_answer = update.message.text.strip()
        ui_lang = await get_user_lang(update, context, self.db) or 'fa'
        if len(new_answer) < 10:
            await update.message.reply_text(t('admin.faq.validation.answer_short', ui_lang))
            return EDIT_FAQ_ANSWER
        faq_id = context.user_data.get('edit_faq_id')
        if not faq_id:
            await update.message.reply_text(t('common.not_found', ui_lang))
            return ADMIN_MENU
        success = await self.db.update_faq(faq_id, answer=new_answer)
        if success:
            self._invalidate_cache()
        context.user_data.pop('edit_faq_id', None)
        context.user_data.pop('edit_faq_data', None)
        if success:
            text = t('admin.faq.edit_a.success', ui_lang) + '\n\n'
            keyboard = [[InlineKeyboardButton(t('admin.faq.buttons.view', ui_lang), callback_data=f'adm_faq_view_{faq_id}')], [InlineKeyboardButton(t('admin.faq.buttons.back_to_list', ui_lang), callback_data='adm_faq_list')]]
        else:
            text = t('admin.faq.error.update', ui_lang)
            keyboard = [[InlineKeyboardButton(t('menu.buttons.back', ui_lang), callback_data='admin_faqs')]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ADMIN_MENU

    async def admin_faq_delete(self, update: Update, context: CustomContext):
        """حذف FAQ"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        from core.security.role_manager import Permission
        if not await self.check_permission(user_id, Permission.MANAGE_FAQS):
            await query.edit_message_text(t('common.no_permission', lang))
            return ADMIN_MENU

        faq_id = int(query.data.split('_')[-1])
        success = await self.db.delete_faq(faq_id)
        if success:
            self._invalidate_cache()
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.edit_message_text(t('admin.faq.delete.success', lang), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t('menu.buttons.back', lang), callback_data='adm_faq_list')]]))
        else:
            lang = await get_user_lang(update, context, self.db) or 'fa'
            await query.edit_message_text(t('admin.faq.error.delete', lang))
        return ADMIN_MENU

    @log_admin_action('admin_faq_set_lang')
    async def admin_faq_set_lang(self, update: Update, context: CustomContext):
        """تنظیم زبان محتوای FAQ (fa/en) و بازسازی منو"""
        query = update.callback_query
        await query.answer()
        data = (query.data or '').strip()
        if data.endswith('_fa'):
            context.user_data['faq_admin_lang'] = 'fa'
        elif data.endswith('_en'):
            context.user_data['faq_admin_lang'] = 'en'
        else:
            ui_lang = await get_user_lang(update, context, self.db) or 'fa'
            context.user_data['faq_admin_lang'] = ui_lang
        return await self.admin_faqs_menu(update, context)