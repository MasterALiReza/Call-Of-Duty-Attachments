from core.context import CustomContext
"""
ماژول تنظیم اتچمنت‌های برتر (REFACTORED)
مسئول: تنظیم 5 اتچمنت برتر برای هر سلاح

ترتیب جدید: Mode → Category → Weapon → Select → Confirm
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from config.config import WEAPON_CATEGORIES, GAME_MODES
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import (
    SET_TOP_MODE, SET_TOP_CATEGORY, SET_TOP_WEAPON,
    SET_TOP_ATTACHMENT, SET_TOP_CONFIRM
)
from utils.logger import log_admin_action
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text


class TopAttachmentsHandler(BaseAdminHandler):
    """Handler برای تنظیم اتچمنت‌های برتر - Mode First Flow"""
    
    @log_admin_action("set_top_start")
    async def set_top_start(self, update: Update, context: CustomContext):
        """شروع فرآیند تنظیم اتچمنت‌های برتر - انتخاب Mode"""
        query = update.callback_query
        
        # پاک کردن navigation stack
        self._clear_navigation(context)
        
        # فیلتر کردن modeها بر اساس دسترسی کاربر
        user_id = update.effective_user.id
        allowed_modes = await self.role_manager.get_mode_permissions(user_id)
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # اگر هیچ دسترسی ندارد
        if not allowed_modes:
            await safe_edit_message_text(query, t("common.no_permission", lang))
            return await self.admin_menu_return(update, context)
        
        # انتخاب Mode (BR/MP) - فقط modeهای مجاز
        keyboard = self._make_mode_selection_keyboard("tmode_", lang, allowed_modes)
        
        keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(
                query,
                t("admin.top.choose_mode", lang),
                reply_markup=reply_markup
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                try:
                    await query.answer()
                except Exception:
                    pass
            else:
                raise
        
        return SET_TOP_MODE
    
    @log_admin_action("set_top_mode_selected")
    async def set_top_mode_selected(self, update: Update, context: CustomContext):
        """انتخاب Mode (BR/MP) برای تنظیم Top - سپس نمایش Categories"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست modeها
            return await self.set_top_start(update, context)
        
        mode = query.data.replace("tmode_", "")  # br یا mp
        
        # بررسی دسترسی به mode انتخاب شده
        user_id = update.effective_user.id
        allowed_modes = await self.role_manager.get_mode_permissions(user_id)
        
        if mode not in allowed_modes:
            await query.answer(t("common.no_permission", lang), show_alert=True)
            return SET_TOP_MODE
        
        # ذخیره state فعلی
        self._push_navigation(context, SET_TOP_MODE, {})
        
        context.user_data['set_top_mode'] = mode
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        # فیلتر کردن دسته‌های فعال برای mode انتخاب شده
        from config.config import build_category_keyboard, is_category_enabled
        active_categories = {}
        for k, v in WEAPON_CATEGORIES.items():
            if await is_category_enabled(k, mode, self.db):
                active_categories[k] = v
        
        if not active_categories:
            await safe_edit_message_text(
                query,
                f"📍 {mode_name}\n\n" + t('admin.suggested.no_active_categories_hint', lang)
            )
            return SET_TOP_MODE
        
        # ساخت کیبورد 2 ستونی برای Categories فعال
        keyboard = await build_category_keyboard(callback_prefix="tcat_", active_ids=list(active_categories.keys()), lang=lang)
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(
                query,
                f"📍 {mode_name}\n\n" + t("category.choose", 'en'),
                reply_markup=reply_markup
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                try:
                    await query.answer()
                except Exception:
                    pass
            else:
                raise
        
        return SET_TOP_CATEGORY
    
    @log_admin_action("set_top_category_selected")
    async def set_top_category_selected(self, update: Update, context: CustomContext):
        """انتخاب دسته برای تنظیم اتچمنت‌های برتر - سپس نمایش Weapons"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست modeها
            context.user_data.pop('set_top_category', None)
            return await self.set_top_start(update, context)
        
        # ذخیره state فعلی
        self._push_navigation(context, SET_TOP_CATEGORY, {
            'set_top_mode': context.user_data.get('set_top_mode')
        })
        
        category = query.data.replace("tcat_", "")
        context.user_data['set_top_category'] = category
        
        weapons = await self.db.get_weapons_in_category(category)
        mode = context.user_data.get('set_top_mode', 'br')
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        if not weapons:
            await safe_edit_message_text(
                query,
                f"📍 {mode_name} > {t(f'category.{category}', 'en')}\n\n" + t('admin.no_weapons_in_category', lang)
            )
            return await self.admin_menu_return(update, context)
        
        # ساخت keyboard با تعداد ستون‌های متغیر برای سلاح‌ها
        keyboard = self._make_weapon_keyboard(weapons, "twpn_", category)
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(
                query,
                f"📍 {mode_name} > {t(f'category.{category}', 'en')}\n\n" + t("weapon.choose", lang),
                reply_markup=reply_markup
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                try:
                    await query.answer()
                except Exception:
                    pass
            else:
                raise
        
        return SET_TOP_WEAPON
    
    @log_admin_action("set_top_weapon_selected")
    async def set_top_weapon_selected(self, update: Update, context: CustomContext):
        """انتخاب سلاح برای تنظیم اتچمنت‌های برتر - مستقیم نمایش لیست"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست دسته‌ها
            context.user_data.pop('set_top_weapon', None)
            mode = context.user_data.get('set_top_mode', 'br')
            mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
            
            from config.config import build_category_keyboard
            keyboard = await build_category_keyboard(callback_prefix="tcat_", active_ids=list(WEAPON_CATEGORIES.keys()), lang=lang)
            self._add_back_cancel_buttons(keyboard, show_back=True)
            
            try:
                await safe_edit_message_text(
                    query,
                    f"📍 {mode_name}\n\n" + t("category.choose", 'en'),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
            return SET_TOP_CATEGORY
        
        # ذخیره state فعلی
        self._push_navigation(context, SET_TOP_WEAPON, {
            'set_top_mode': context.user_data.get('set_top_mode'),
            'set_top_category': context.user_data.get('set_top_category')
        })
        
        weapon = query.data.replace("twpn_", "")
        context.user_data['set_top_weapon'] = weapon
        
        # Initialize selected tops list
        context.user_data['selected_tops'] = []
        
        category = context.user_data['set_top_category']
        mode = context.user_data.get('set_top_mode', 'br')
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        
        if not attachments:
            await safe_edit_message_text(
                query,
                f"📍 {mode_name} > {t(f'category.{category}', 'en')} > {weapon}\n\n" + t('attachment.none', lang)
            )
            return await self.admin_menu_return(update, context)
        
        # نمایش لیست اتچمنت‌ها به صورت دکمه
        selected_tops = context.user_data.get('selected_tops', [])
        text = f"📍 {mode_name} > {t(f'category.{category}', 'en')} > {weapon}\n\n"
        text += t("admin.top.set_title", lang) + "\n\n"
        text += t("admin.top.selected_count", lang, n=len(selected_tops), max=5) + "\n\n"
        
        if selected_tops:
            text += t("admin.top.selected_list_header", lang) + "\n"
            for i, att_id in enumerate(selected_tops, 1):
                att = next((a for a in attachments if a['id'] == att_id), None)
                if att:
                    text += f"{i}. {att['name']}\n"
            text += "\n"
        
        text += t("admin.top.select_attachment", lang)
        
        # ساخت کیبورد از اتچمنت‌ها
        keyboard = []
        for att in attachments:
            # نمایش ✅ برای اتچمنت‌های انتخاب شده
            prefix = "✅ " if att['id'] in selected_tops else ""
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{att['name']}",
                callback_data=f"tatt_{att['id']}"
            )])
        
        # دکمه تایید نهایی (فقط اگر حداقل 1 انتخاب شده)
        if selected_tops:
            keyboard.append([InlineKeyboardButton(t("admin.top.confirm_save", lang), callback_data="top_save_")])
        
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        try:
            await safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                try:
                    await query.answer()
                except Exception:
                    pass
            else:
                raise
        
        return SET_TOP_ATTACHMENT
    
    @log_admin_action("set_top_attachment_selected")
    async def set_top_attachment_selected(self, update: Update, context: CustomContext):
        """انتخاب یک اتچمنت برای افزودن/حذف از لیست برترها"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            return await self.handle_navigation_back(update, context)
        
        # تایید نهایی
        if query.data == "top_save_":
            return await self.set_top_confirm_save(update, context)
        
        # انتخاب اتچمنت
        att_id = int(query.data.replace("tatt_", ""))
        
        category = context.user_data['set_top_category']
        weapon = context.user_data['set_top_weapon']
        mode = context.user_data.get('set_top_mode', 'br')
        
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        selected_att = next((a for a in attachments if a['id'] == att_id), None)
        
        if not selected_att:
            await query.answer(t('attachment.not_found', lang), show_alert=True)
            return SET_TOP_ATTACHMENT
        
        # ذخیره state فعلی برای navigation back
        self._push_navigation(context, SET_TOP_ATTACHMENT, {
            'set_top_mode': context.user_data.get('set_top_mode'),
            'set_top_category': context.user_data.get('set_top_category'),
            'set_top_weapon': context.user_data.get('set_top_weapon'),
            'selected_tops': context.user_data.get('selected_tops', [])
        })
        
        # ذخیره اتچمنت برای تایید
        context.user_data['pending_top_att'] = att_id
        
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        # سوال: برتر هست یا نه؟
        keyboard = self._create_confirmation_keyboard(
            confirm_callback="top_ans_yes",
            cancel_callback="top_ans_no",
            confirm_text=t('admin.top.confirm_yes', lang),
            cancel_text=t('admin.top.confirm_no', lang),
            show_back=False  # دکمه بازگشت جداگانه اضافه می‌شود
        )
        # اضافه کردن دکمه بازگشت سفارشی
        keyboard.insert(-1, [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="top_ans_back")])
        
        text = f"📍 {mode_name} > {t(f'category.{category}', 'en')} > {weapon}\n\n"
        text += t('admin.top.selected_attachment_label', lang) + "\n\n"
        text += f"🔹 {selected_att['name']}\n\n"
        text += t('admin.top.confirm_question', lang)
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        return SET_TOP_CONFIRM
    
    @log_admin_action("set_top_confirm_answer")
    async def set_top_confirm_answer(self, update: Update, context: CustomContext):
        """پاسخ به سوال: برتر است یا نه؟"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # بررسی دکمه‌های خاص
        if query.data == "admin_cancel":
            context.user_data.pop('pending_top_att', None)
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            context.user_data.pop('pending_top_att', None)
            return await self.handle_navigation_back(update, context)
        
        if query.data == "top_ans_back":
            # بازگشت به لیست اتچمنت‌ها با استفاده از navigation stack
            context.user_data.pop('pending_top_att', None)
            return await self.handle_navigation_back(update, context)
        
        att_id = context.user_data.get('pending_top_att')
        if not att_id:
            return await self.set_top_weapon_selected(update, context)
        
        selected_tops = context.user_data.get('selected_tops', [])
        
        if query.data == "top_ans_yes":
            # اضافه کردن به لیست برترها
            if att_id not in selected_tops:
                if len(selected_tops) >= 5:
                    await query.answer(t('admin.top.limit_reached', lang, max=5), show_alert=True)
                else:
                    selected_tops.append(att_id)
                    context.user_data['selected_tops'] = selected_tops
                    await query.answer(t('admin.top.added_to_top', lang), show_alert=False)
            else:
                await query.answer(t('admin.top.already_selected', lang), show_alert=False)
        
        elif query.data == "top_ans_no":
            # حذف از لیست برترها (اگر وجود داشت)
            if att_id in selected_tops:
                selected_tops.remove(att_id)
                context.user_data['selected_tops'] = selected_tops
                await query.answer(t('admin.top.removed_from_top', lang), show_alert=False)
            else:
                await query.answer(t('admin.top.not_top', lang), show_alert=False)
        
        # پاک کردن pending
        context.user_data.pop('pending_top_att', None)
        
        # بازگشت به لیست اتچمنت‌ها
        return await self.set_top_weapon_selected(update, context)
    
    @log_admin_action("set_top_confirm_save")
    async def set_top_confirm_save(self, update: Update, context: CustomContext):
        """ذخیره نهایی اتچمنت‌های برتر"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        selected_tops = context.user_data.get('selected_tops', [])
        
        if not selected_tops:
            await query.answer(t('admin.top.none_selected', lang), show_alert=True)
            return SET_TOP_ATTACHMENT
        
        category = context.user_data['set_top_category']
        weapon = context.user_data['set_top_weapon']
        mode = context.user_data.get('set_top_mode', 'br')
        mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        # دریافت اتچمنت‌ها برای استخراج کدها و نام‌ها
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        codes = []
        names = []
        for att_id in selected_tops:
            att = next((a for a in attachments if a['id'] == att_id), None)
            if att:
                codes.append(att['code'])
                names.append(att['name'])
        
        if await self.db.set_top_attachments(category, weapon, codes, mode=mode):
            try:
                await safe_edit_message_text(
                    query,
                    t('admin.top.save.success_title', lang) + "\n\n"
                    f"📍 {mode_name} > {t(f'category.{category}', 'en')} > {weapon}\n"
                    + t('admin.top.save.count', lang, n=len(names)) + "\n\n"
                    + t('admin.top.save.list_header', lang) + "\n" + "\n".join([f"{i}. {name}" for i, name in enumerate(names, 1)])
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
            # اعلان خودکار تنظیم برترین‌ها
            await self._auto_notify(context, 'top_set', {
                'category': category, 'weapon': weapon, 'mode': mode
            })
        else:
            try:
                await safe_edit_message_text(
                    query,
                    t('error.generic', lang)
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
        
        # پاکسازی
        context.user_data.pop('selected_tops', None)
        context.user_data.pop('pending_top_att', None)
        
        return await self.admin_menu_return(update, context)
    
    async def _rebuild_state_screen(self, update: Update, context: CustomContext, state: int):
        """بازسازی صفحه برای هر state"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if state == SET_TOP_MODE:
            # بازگشت به لیست modeها
            user_id = update.effective_user.id
            allowed_modes = await self.role_manager.get_mode_permissions(user_id)
            
            keyboard = self._make_mode_selection_keyboard("tmode_", lang, allowed_modes)
            keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")])
            
            try:
                await safe_edit_message_text(
                    query,
                    t("admin.top.choose_mode", lang),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
        
        elif state == SET_TOP_CATEGORY:
            # بازگشت به لیست دسته‌ها
            mode = context.user_data.get('set_top_mode', 'br')
            mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
            
            from config.config import build_category_keyboard
            keyboard = await build_category_keyboard(callback_prefix="tcat_", active_ids=list(WEAPON_CATEGORIES.keys()), lang=lang)
            self._add_back_cancel_buttons(keyboard, show_back=True)
            
            await safe_edit_message_text(
                query,
                f"📍 {mode_name}\n\n" + t("category.choose", 'en'),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif state == SET_TOP_WEAPON:
            # بازگشت به لیست سلاح‌ها
            mode = context.user_data.get('set_top_mode', 'br')
            category = context.user_data.get('set_top_category')
            mode_name = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
            
            if category:
                weapons = await self.db.get_weapons_in_category(category)
                keyboard = self._make_weapon_keyboard(weapons, "twpn_", category)
                self._add_back_cancel_buttons(keyboard, show_back=True)
                try:
                    await safe_edit_message_text(
                        query,
                        f"📍 {mode_name} > {t(f'category.{category}', 'en')}\n\n" + t("weapon.choose", lang),
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        try:
                            await query.answer()
                        except Exception:
                            pass
                    else:
                        raise
        
        elif state == SET_TOP_ATTACHMENT:
            # بازگشت به لیست اتچمنت‌ها
            await self.set_top_weapon_selected(update, context)
    
    async def _auto_notify(self, context: CustomContext, event: str, payload: dict):
        """ارسال اعلان خودکار"""
        try:
            from managers.notification_manager import NotificationManager
            notif_manager = NotificationManager(self.db, None)
            await notif_manager.send_notification(context, event, payload)
        except Exception:
            pass
