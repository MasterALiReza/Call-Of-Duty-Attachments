from core.context import CustomContext
"""
ماژول حذف اتچمنت (REFACTORED)
مسئول: حذف اتچمنت با انتخاب از لیست، پشتیبانی از ID-based selection

ترتیب جدید: Mode → Category → Weapon → Select
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from config.config import WEAPON_CATEGORIES, GAME_MODES
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import (
    DELETE_ATTACHMENT_MODE, DELETE_ATTACHMENT_CATEGORY,
    DELETE_ATTACHMENT_WEAPON, DELETE_ATTACHMENT_CODE
)
from utils.logger import log_admin_action
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text


class DeleteAttachmentHandler(BaseAdminHandler):
    """Handler برای حذف اتچمنت - Mode First Flow"""
    
    @log_admin_action("delete_attachment_start")
    async def delete_attachment_start(self, update: Update, context: CustomContext):
        """شروع فرآیند حذف اتچمنت - انتخاب Mode"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # پاک کردن navigation stack
        self._clear_navigation(context)
        
        # فیلتر کردن modeها بر اساس دسترسی کاربر
        user_id = update.effective_user.id
        allowed_modes = await self.role_manager.get_mode_permissions(user_id)
        
        # اگر هیچ دسترسی ندارد
        if not allowed_modes:
            await safe_edit_message_text(query, t("common.no_permission", lang))
            return await self.admin_menu_return(update, context)
        
        # انتخاب Mode (BR/MP) - فقط modeهای مجاز
        keyboard = self._make_mode_selection_keyboard("dmode_", lang, allowed_modes)
        
        keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(query, t("admin.delete.mode.prompt", lang), reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                try:
                    await query.answer()
                except Exception:
                    pass
            else:
                raise
        
        return DELETE_ATTACHMENT_MODE
    
    @log_admin_action("delete_attachment_mode_selected")
    async def delete_attachment_mode_selected(self, update: Update, context: CustomContext):
        """انتخاب Mode (BR/MP) برای حذف - سپس نمایش Categories"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست modeها
            return await self.delete_attachment_start(update, context)
        
        mode = query.data.replace("dmode_", "")  # br یا mp
        
        # بررسی دسترسی به mode انتخاب شده
        user_id = update.effective_user.id
        allowed_modes = await self.role_manager.get_mode_permissions(user_id)
        
        if mode not in allowed_modes:
            await query.answer(t("common.no_permission", lang), show_alert=True)
            return DELETE_ATTACHMENT_MODE
        
        # ذخیره state فعلی
        self._push_navigation(context, DELETE_ATTACHMENT_MODE, {})
        
        context.user_data['del_att_mode'] = mode
        mode_name = GAME_MODES.get(mode, mode)
        
        # فیلتر کردن دسته‌های فعال برای mode انتخاب شده
        from config.config import build_category_keyboard, is_category_enabled
        active_categories = {}
        for k, v in WEAPON_CATEGORIES.items():
            if await is_category_enabled(k, mode, self.db):
                active_categories[k] = v
        
        if not active_categories:
            await safe_edit_message_text(
                query,
                t("admin.weapons.header.mode", lang, mode=mode_name) + "\n\n" + t("admin.attach.category.none_active", lang) + "\n" + t("admin.attach.category.enable_hint", lang)
            )
            return DELETE_ATTACHMENT_MODE
        
        # ساخت کیبورد 2 ستونی برای Categories فعال
        keyboard = await build_category_keyboard(callback_prefix="dcat_", active_ids=list(active_categories.keys()), lang=lang)
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(
                query,
                t("admin.weapons.header.mode", lang, mode=mode_name) + "\n\n" + t("admin.weapons.choose_category", lang),
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
        
        return DELETE_ATTACHMENT_CATEGORY
    
    @log_admin_action("delete_attachment_category_selected")
    async def delete_attachment_category_selected(self, update: Update, context: CustomContext):
        """انتخاب دسته برای حذف اتچمنت - سپس نمایش Weapons"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست modeها
            context.user_data.pop('del_att_category', None)
            return await self.delete_attachment_start(update, context)
        
        # ذخیره state فعلی
        self._push_navigation(context, DELETE_ATTACHMENT_CATEGORY, {
            'del_att_mode': context.user_data.get('del_att_mode')
        })
        
        category = query.data.replace("dcat_", "")
        context.user_data['del_att_category'] = category
        
        weapons = await self.db.get_weapons_in_category(category)
        mode = context.user_data.get('del_att_mode', 'br')
        mode_name = GAME_MODES.get(mode, mode)
        
        if not weapons:
            try:
                await safe_edit_message_text(
                    query,
                    t("admin.weapons.path", lang, mode=mode_name, category=t(f"category.{category}", 'en')) + "\n\n" + t("admin.weapons.none_in_category", lang)
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
            return await self.admin_menu_return(update, context)
        
        # ساخت keyboard با تعداد ستون‌های متغیر برای سلاح‌ها
        keyboard = self._make_weapon_keyboard(weapons, "dwpn_", category)
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await safe_edit_message_text(
                query,
                t("admin.weapons.path", lang, mode=mode_name, category=t(f"category.{category}", 'en')) + "\n\n" + t("weapon.choose", lang),
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
        
        return DELETE_ATTACHMENT_WEAPON
    
    @log_admin_action("delete_attachment_weapon_selected")
    async def delete_attachment_weapon_selected(self, update: Update, context: CustomContext):
        """انتخاب سلاح برای حذف - مستقیم نمایش لیست Attachments"""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            # بازگشت به لیست دسته‌ها
            context.user_data.pop('del_att_weapon', None)
            mode = context.user_data.get('del_att_mode', 'br')
            mode_name = GAME_MODES.get(mode, mode)
            
            from config.config import build_category_keyboard, is_category_enabled
            active_categories = {}
            for k, v in WEAPON_CATEGORIES.items():
                if await is_category_enabled(k, mode, self.db):
                    active_categories[k] = v
            keyboard = await build_category_keyboard(callback_prefix="dcat_", active_ids=list(active_categories.keys()))
            self._add_back_cancel_buttons(keyboard, show_back=True)
            
            try:
                await safe_edit_message_text(
                    query,
                    t("admin.weapons.header.mode", lang, mode=mode_name) + "\n\n" + t("admin.weapons.choose_category", lang),
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
            return DELETE_ATTACHMENT_CATEGORY
        
        # ذخیره state فعلی
        self._push_navigation(context, DELETE_ATTACHMENT_WEAPON, {
            'del_att_mode': context.user_data.get('del_att_mode'),
            'del_att_category': context.user_data.get('del_att_category')
        })
        
        weapon = query.data.replace("dwpn_", "")
        context.user_data['del_att_weapon'] = weapon
        
        # دریافت اطلاعات برای نمایش
        category = context.user_data['del_att_category']
        mode = context.user_data.get('del_att_mode', 'br')
        mode_name = GAME_MODES.get(mode, mode)
        
        # مستقیماً لیست اتچمنت‌ها را برای حذف نمایش بده
        attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
        
        if not attachments:
            # ساخت کیبورد با دکمه بازگشت به لیست سلاح‌ها
            keyboard = [
                [InlineKeyboardButton(t("admin.delete.buttons.back_to_weapons", lang), callback_data=f"dcat_{category}")],
                [InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await safe_edit_message_text(
                    query,
                    t("admin.weapons.path_weapon", lang, mode=mode_name, category=t(f"category.{category}", 'en'), weapon=weapon) + "\n\n" + t("attachment.none", lang),
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
            # باقی ماندن در همین state تا دکمه بازگشت زده شود
            return DELETE_ATTACHMENT_CATEGORY
        
        keyboard = []
        for att in attachments:
            # استفاده از ID به جای code در callback_data - فقط name نمایش داده میشه
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {att['name']}", 
                callback_data=f"delatt_{att['id']}"
            )])
        self._add_back_cancel_buttons(keyboard, show_back=True)
        
        try:
            await safe_edit_message_text(
                query,
                t("admin.weapons.path_weapon", lang, mode=mode_name, category=t(f"category.{category}", 'en'), weapon=weapon) + "\n\n" + t("admin.delete.choose_attachment", lang),
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
        return DELETE_ATTACHMENT_CODE
    
    @log_admin_action("delete_attachment_code_selected")
    async def delete_attachment_code_selected(self, update: Update, context: CustomContext):
        """حذف با انتخاب از لیست (با ID)"""
        query = update.callback_query
        # نکته: اینجا answer() را صدا نمی‌زنیم تا بتوانیم در صورت موفقیت alert نشان دهیم
        # await query.answer()
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        if query.data == "admin_cancel":
            await query.answer()
            return await self.admin_menu_return(update, context)
        
        if query.data == "nav_back":
            await query.answer()
            return await self.handle_navigation_back(update, context)
        
        # دریافت ID از callback_data
        att_id = int(query.data.replace("delatt_", ""))
        category = context.user_data['del_att_category']
        weapon = context.user_data['del_att_weapon']
        mode = context.user_data.get('del_att_mode', 'br')
        mode_name = GAME_MODES.get(mode, mode)
        
        # پیدا کردن اتچمنت با ID برای گرفتن نام و کد
        att_to_delete = None
        try:
            for att in await self.db.get_all_attachments(category, weapon, mode=mode):
                if att.get('id') == att_id:
                    att_to_delete = att
                    break
        except Exception:
            pass
        
        if not att_to_delete:
            await query.answer()
            try:
                await safe_edit_message_text(query, t("attachment.not_found", lang))
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    pass
                else:
                    raise
            return await self.admin_menu_return(update, context)
        
        code = att_to_delete['code']
        name = att_to_delete['name']
        
        if await self.db.delete_attachment(category=category, weapon_name=weapon, code=code, mode=mode):
            # Show success message as popup alert
            await query.answer(t("admin.delete.success_alert", lang, name=name), show_alert=True)
            
            # invalidate related caches
            try:
                from core.cache.cache_manager import invalidate_attachment_caches
                await invalidate_attachment_caches(category, weapon)
            except Exception:
                pass
            
            # ارسال نوتیفیکیشن
            await self._auto_notify(context, 'delete_attachment', {
                'category': category, 'weapon': weapon, 'code': code, 'name': name, 'mode': mode
            })
            
            # ✅ DB Audit Logging
            await self.audit.log_action(
                admin_id=update.effective_user.id,
                action="DELETE_ATTACHMENT",
                target_id=str(att_id),
                details={
                    "target_type": "attachment",
                    "name": name,
                    "code": code,
                    "weapon": weapon,
                    "category": category,
                    "mode": mode
                }
            )
            
            # رفرش کردن لیست - همان منطقی که در delete_attachment_weapon_selected داریم
            attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
            
            if not attachments:
                # اگر آیتمی نمانده، پیام "خالی" را نشان بده
                keyboard = [
                    [InlineKeyboardButton(t("admin.delete.buttons.back_to_weapons", lang), callback_data=f"dcat_{category}")],
                    [InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await safe_edit_message_text(
                        query,
                        t("admin.weapons.path_weapon", lang, mode=mode_name, category=t(f"category.{category}", 'en'), weapon=weapon) + "\n\n" + t("attachment.none", lang),
                        reply_markup=reply_markup
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        pass
                    else:
                        raise
                return DELETE_ATTACHMENT_CATEGORY
            
            else:
                # اگر هنوز آیتم هست، لیست جدید را رندر کن
                keyboard = []
                for att in attachments:
                    keyboard.append([InlineKeyboardButton(
                        f"🗑️ {att['name']}", 
                        callback_data=f"delatt_{att['id']}"
                    )])
                self._add_back_cancel_buttons(keyboard, show_back=True)
                
                try:
                    await safe_edit_message_text(
                        query,
                        t("admin.weapons.path_weapon", lang, mode=mode_name, category=t(f"category.{category}", 'en'), weapon=weapon) + "\n\n" + t("admin.delete.choose_attachment", lang),
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        pass
                    else:
                        raise
                return DELETE_ATTACHMENT_CODE
                
        else:
            await query.answer(t("admin.delete.error", lang), show_alert=True)
            return DELETE_ATTACHMENT_CODE
    
    async def _rebuild_state_screen(self, update: Update, context: CustomContext, state: int):
        """بازسازی صفحه برای هر state"""
        query = update.callback_query
        
        if state == DELETE_ATTACHMENT_MODE:
            # بازگشت به لیست modeها
            user_id = update.effective_user.id
            allowed_modes = await self.role_manager.get_mode_permissions(user_id)
            lang = await get_user_lang(update, context, self.db) or 'fa'
            
            keyboard = self._make_mode_selection_keyboard("dmode_", lang, allowed_modes)
            keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="admin_cancel")])
            
            try:
                await safe_edit_message_text(query, t("admin.delete.mode.prompt", lang), reply_markup=InlineKeyboardMarkup(keyboard))
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    try:
                        await query.answer()
                    except Exception:
                        pass
                else:
                    raise
        
        elif state == DELETE_ATTACHMENT_CATEGORY:
            # بازگشت به لیست دسته‌ها
            mode = context.user_data.get('del_att_mode', 'br')
            mode_name = GAME_MODES.get(mode, mode)
            lang = await get_user_lang(update, context, self.db) or 'fa'
            
            from config.config import build_category_keyboard, is_category_enabled
            active_categories = {}
            for k, v in WEAPON_CATEGORIES.items():
                if await is_category_enabled(k, mode, self.db):
                    active_categories[k] = v
            keyboard = await build_category_keyboard(callback_prefix="dcat_", active_ids=list(active_categories.keys()))
            self._add_back_cancel_buttons(keyboard, show_back=True)
            
            await safe_edit_message_text(
                query,
                t("admin.weapons.header.mode", lang, mode=mode_name) + "\n\n" + t("admin.weapons.choose_category", lang),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif state == DELETE_ATTACHMENT_WEAPON:
            # بازگشت به لیست سلاح‌ها
            mode = context.user_data.get('del_att_mode', 'br')
            category = context.user_data.get('del_att_category')
            mode_name = GAME_MODES.get(mode, mode)
            lang = await get_user_lang(update, context, self.db) or 'fa'
            
            if category:
                weapons = await self.db.get_weapons_in_category(category)
                keyboard = self._make_weapon_keyboard(weapons, "dwpn_", category)
                self._add_back_cancel_buttons(keyboard, show_back=True)
                try:
                    await safe_edit_message_text(
                        query,
                        t("admin.weapons.path", lang, mode=mode_name, category=t(f"category.{category}", 'en')) + "\n\n" + t("weapon.choose", lang),
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
        
        elif state == DELETE_ATTACHMENT_CODE:
            # بازگشت به لیست اتچمنت‌ها
            category = context.user_data.get('del_att_category')
            weapon = context.user_data.get('del_att_weapon')
            mode = context.user_data.get('del_att_mode', 'br')
            mode_name = GAME_MODES.get(mode, mode)
            lang = await get_user_lang(update, context, self.db) or 'fa'
            
            attachments = await self.db.get_all_attachments(category, weapon, mode=mode)
            keyboard = []
            for att in attachments:
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ {att['name']}", 
                    callback_data=f"delatt_{att['id']}"
                )])
            self._add_back_cancel_buttons(keyboard, show_back=True)
            
            try:
                await safe_edit_message_text(
                    query,
                    t("admin.weapons.path_weapon", lang, mode=mode_name, category=t(f"category.{category}", 'en'), weapon=weapon) + "\n\n" + t("admin.delete.choose_attachment", lang),
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
    
    async def _auto_notify(self, context: CustomContext, event: str, payload: dict):
        """ارسال اعلان خودکار"""
        try:
            from managers.notification_manager import NotificationManager
            notif_manager = NotificationManager(self.db, None)
            await notif_manager.send_notification(context, event, payload)
        except Exception:
            pass
