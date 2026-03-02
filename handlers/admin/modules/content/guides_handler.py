from core.context import CustomContext
"""
ماژول مدیریت راهنماهای بازی (Guides)
مسئول: تنظیمات HUD, Basic, Sensitivity برای BR/MP
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.admin.modules.base_handler import BaseAdminHandler
from handlers.admin.admin_states import (
    ADMIN_MENU,
    GUIDE_RENAME,
    GUIDE_PHOTO,
    GUIDE_VIDEO,
    GUIDE_CODE,
    GUIDE_FINAL_CONFIRM
)
from core.security.role_manager import require_permission, Permission
from utils.logger import get_logger
from utils.i18n import t
from utils.language import get_user_lang

logger = get_logger('guides', 'admin.log')


class GuidesHandler(BaseAdminHandler):
    """
    مدیریت راهنماهای بازی
    
    Features:
    - مدیریت 3 بخش: HUD, Basic, Sensitivity
    - پشتیبانی BR/MP mode
    - مدیریت رسانه (عکس/ویدیو)
    - تنظیم کد (Sens/HUD)
    - RBAC Integration
    """
    
    def __init__(self, db):
        """مقداردهی اولیه"""
        super().__init__(db)
        logger.info("GuidesHandler initialized")
    
    def set_role_manager(self, role_manager):
        """تنظیم role manager"""
        self.role_manager = role_manager
    
    # ==================== Main Menu ====================
    
    @require_permission(Permission.MANAGE_SETTINGS)
    async def guides_menu(self, update: Update, context: CustomContext):
        """
        منوی تنظیمات بازی - انتخاب mode
        
        Flow:
        1. بررسی دسترسی کاربر (BR/MP)
        2. نمایش مودهای مجاز
        3. انتخاب mode توسط ادمین
        """
        query = update.callback_query
        if query:
            try:
                await query.answer()
            except Exception:
                pass
        
        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or 'fa'
        
        # دریافت مودهای مجاز
        if self.role_manager:
            allowed_modes = await self.role_manager.get_guide_mode_permissions(user_id)
        else:
            allowed_modes = ['br', 'mp']  # پیش‌فرض
        
        if not allowed_modes:
            error_text = t('error.unauthorized', lang)
            if query:
                await query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
            return ADMIN_MENU
        
        text = f"{t('admin.guides.title', lang)}\n\n"
        text += t('admin.guides.desc', lang) + "\n\n"
        text += f"🎯 {t('guides.choose_mode', lang)}"
        
        # ساخت کیبورد
        mode_buttons = []
        if 'br' in allowed_modes:
            mode_buttons.append(InlineKeyboardButton(t('mode.br', lang), callback_data="gmode_br"))
        if 'mp' in allowed_modes:
            mode_buttons.append(InlineKeyboardButton(t('mode.mp', lang), callback_data="gmode_mp"))
        
        kb = []
        if mode_buttons:
            if len(mode_buttons) == 2:
                kb.append(mode_buttons)
            else:
                kb.append([mode_buttons[0]])
        
        kb.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="admin_back")])
        
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
        logger.info(f"Guides menu shown to user {user_id}, modes: {allowed_modes}")
        return ADMIN_MENU
    
    async def guides_mode_selected(self, update: Update, context: CustomContext):
        """
        بعد از انتخاب mode، نمایش بخش‌ها
        
        Callback data: gmode_{mode}
        
        Sections:
        - HUD (📱)
        - Basic (⚙️)
        - Sensitivity (🎯)
        """
        query = update.callback_query
        await query.answer()
        
        mode = query.data.replace("gmode_", "")
        context.user_data['guide_mode'] = mode
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_display = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        # دریافت راهنماها برای شمارش مدیا
        guides = await self.db.get_guides(mode=mode)
        
        # ساخت دکمه‌ها با ایموجی و تعداد مدیا
        def make_button_text(emoji: str, name_key: str, guide_key: str) -> str:
            guide = guides.get(guide_key, {})
            photos = guide.get("photos", []) or []
            videos = guide.get("videos", []) or []
            total_media = len(photos) + len(videos)
            
            name = t(name_key, lang)
            if total_media > 0:
                return f"{emoji} {name} ({total_media})"
            return f"{emoji} {name}"
        
        hud_text = make_button_text("🖼️", "guides.hud_short", "hud")
        basic_text = make_button_text("⚙️", "guides.basic_short", "basic")
        sens_text = make_button_text("🎯", "guides.sens_short", "sens")
        
        text = f"{t('admin.guides.title', lang)} - {mode_display}\n\n"
        text += t('guides.choose_section', lang)
        
        kb = [
            [
                InlineKeyboardButton(hud_text, callback_data=f"gsel_hud_{mode}"),
                InlineKeyboardButton(basic_text, callback_data=f"gsel_basic_{mode}")
            ],
            [InlineKeyboardButton(sens_text, callback_data=f"gsel_sens_{mode}")],
            [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="admin_guides")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        logger.info(f"Mode {mode} selected")
        return ADMIN_MENU
    
    # ==================== Section Menu ====================
    
    async def guide_section_menu(self, update: Update, context: CustomContext, send_new: bool = False):
        """
        منوی عملیات برای یک بخش
        
        Callback data: gsel_{key}_{mode}
        
        Operations:
        - تغییر عنوان
        - افزودن عکس/ویدیو
        - پاک‌سازی رسانه
        - تنظیم کد (sens/hud)
        """
        query = update.callback_query
        
        # استخراج key و mode
        if send_new:
            key = context.user_data.get('guide_key')
            mode = context.user_data.get('guide_mode', 'br')
            if not key:
                lang = await get_user_lang(update, context, self.db) or 'fa'
                await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
                return await self.guides_menu(update, context)
        elif query:
            try:
                await query.answer()
            except Exception:
                pass
            data = query.data.replace("gsel_", "")
            try:
                key, mode = data.rsplit("_", 1)
            except ValueError:
                key = data
                mode = context.user_data.get('guide_mode', 'br')
            
            context.user_data['guide_key'] = key
            context.user_data['guide_mode'] = mode
        else:
            key = context.user_data.get('guide_key')
            mode = context.user_data.get('guide_mode', 'br')
            if not key:
                lang = await get_user_lang(update, context, self.db) or 'fa'
                await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
                return await self.guides_menu(update, context)
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_display = f"{t('mode.label', lang)}: {t(f'mode.{mode}_short', lang)}"
        
        g = await self.db.get_guide(key, mode=mode)
        p = len(g.get("photos", []) or [])
        v = len(g.get("videos", []) or [])
        
        labels = {
            "basic": f"⚙️ {t('guides.basic_short', lang)}",
            "sens": f"🎯 {t('guides.sens_short', lang)}",
            "hud": f"🖼️ {t('guides.hud_short', lang)}"
        }
        section_label = labels.get(key, key)
        
        text = f"{section_label} - {mode_display}\n\n"
        text += t('admin.guides.media.count', lang, photos=p, videos=v)
        
        kb = [
            [InlineKeyboardButton(t('admin.guides.buttons.rename', lang), callback_data=f"gop_rename_{key}_{mode}")],
            [InlineKeyboardButton(t('admin.guides.buttons.add_photo', lang), callback_data=f"gop_addphoto_{key}_{mode}"),
             InlineKeyboardButton(t('admin.guides.buttons.add_video', lang), callback_data=f"gop_addvideo_{key}_{mode}")],
            [InlineKeyboardButton(t('admin.guides.buttons.clear_media', lang), callback_data=f"gop_clearmedia_{key}_{mode}")],
        ]
        
        # برای Sens و HUD قابلیت کد
        if key in ["sens", "hud"]:
            code = (g.get("code") or "").strip()
            code_label = t('guides.sens_short', lang) if key == "sens" else t('guides.hud_short', lang)
            text += f"\n\n{t('admin.guides.code.label', lang, section=code_label, code=(code or t('common.none', lang)))}"
            
            kb.append([InlineKeyboardButton(t('admin.guides.buttons.set_code', lang, section=code_label), callback_data=f"gop_setcode_{key}_{mode}")])
            if code:
                kb.append([InlineKeyboardButton(t('admin.guides.buttons.clear_code', lang, section=code_label), callback_data=f"gop_clearcode_{key}_{mode}")])
        
        kb.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"gmode_{mode}")])
        
        if send_new or not query:
            if query and query.message:
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        else:
            try:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
            except Exception as e:
                logger.warning(f"Failed to edit guides section menu message: {e}")
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        
        logger.info(f"Section menu shown: {key} ({mode})")
        return ADMIN_MENU
    
    # ==================== Operation Router ====================
    
    def _extract_key_mode(self, data: str, prefix: str) -> tuple:
        """استخراج key و mode از callback data"""
        remaining = data.replace(prefix, "")
        try:
            key, mode = remaining.rsplit("_", 1)
            if mode in ['br', 'mp']:
                return key, mode
        except ValueError:
            # در صورت فرمت نامعتبر، به صورت پیش‌فرض mode را br در نظر می‌گیریم
            logger.warning(f"Invalid guide key/mode format in callback data: {data}")
        return remaining, 'br'
    
    async def guide_op_router(self, update: Update, context: CustomContext):
        """
        روت کردن عملیات روی بخش راهنما
        
        Operations:
        - rename: تغییر عنوان
        - addphoto: افزودن عکس
        - addvideo: افزودن ویدیو
        - clearmedia: پاک‌سازی رسانه
        - setcode: تنظیم کد
        - clearcode: حذف کد
        """
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or 'fa'
        data = query.data
        
        if data.startswith("gop_rename_"):
            key, mode = self._extract_key_mode(data, "gop_rename_")
            context.user_data['guide_key'] = key
            context.user_data['guide_mode'] = mode
            
            g = await self.db.get_guide(key, mode=mode)
            current_name = g.get("name", key)
            labels = {"basic": t('guides.basic_short', lang), "sens": t('guides.sens_short', lang), "hud": t('guides.hud_short', lang)}
            section = labels.get(key, key)
            
            msg = (
                f"{t('admin.guides.rename.title', lang, section=section)}\n\n"
                f"{t('admin.guides.rename.current', lang, current=current_name)}\n\n"
                f"{t('admin.guides.rename.prompt', lang)}\n"
                f"{t('admin.guides.rename.tip', lang)}"
            )
            
            await query.edit_message_text(msg)
            logger.info(f"Rename started for {key} ({mode})")
            return GUIDE_RENAME
        
        elif data.startswith("gop_addphoto_"):
            key, mode = self._extract_key_mode(data, "gop_addphoto_")
            context.user_data['guide_key'] = key
            context.user_data['guide_mode'] = mode
            context.user_data['guide_temp_photos'] = []
            context.user_data['guide_temp_videos'] = []
            
            kb = [
                [InlineKeyboardButton(t('admin.guides.buttons.confirm_and_continue', lang), callback_data=f"gop_confirm_media_{key}_{mode}")],
                [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"gsel_{key}_{mode}")]
            ]
            await query.edit_message_text(
                t('admin.guides.photo.prompt', lang),
                reply_markup=InlineKeyboardMarkup(kb)
            )
            logger.info(f"Add photo started for {key} ({mode})")
            return GUIDE_PHOTO
        
        elif data.startswith("gop_addvideo_"):
            key, mode = self._extract_key_mode(data, "gop_addvideo_")
            context.user_data['guide_key'] = key
            context.user_data['guide_mode'] = mode
            context.user_data['guide_temp_videos'] = []
            
            kb = [
                [InlineKeyboardButton(t('admin.guides.buttons.confirm_and_continue', lang), callback_data=f"gop_confirm_media_{key}_{mode}")],
                [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"gsel_{key}_{mode}")]
            ]
            await query.edit_message_text(
                t('admin.guides.video.prompt', lang),
                reply_markup=InlineKeyboardMarkup(kb)
            )
            logger.info(f"Add video started for {key} ({mode})")
            return GUIDE_VIDEO
        
        elif data.startswith("gop_confirm_media_"):
            key, mode = self._extract_key_mode(data, "gop_confirm_media_")
            return await self.guide_media_confirmed(update, context, key)
        
        elif data.startswith("gop_clearmedia_confirm_"):
            key, mode = self._extract_key_mode(data, "gop_clearmedia_confirm_")
            await query.answer(t('feedback.wait', lang))
            
            if await self.db.clear_guide_media(key, mode=mode):
                await query.message.reply_text(t('admin.guides.clearmedia.success', lang), parse_mode='HTML')
                logger.info(f"Media cleared for {key} ({mode})")
            else:
                await query.message.reply_text(t('admin.guides.clearmedia.error', lang))
                logger.error(f"Failed to clear media for {key} ({mode})")
            
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete guides clearmedia confirmation message: {e}")
            
            return await self.guide_section_menu(update, context, send_new=True)
        
        elif data.startswith("gop_clearmedia_"):
            key, mode = self._extract_key_mode(data, "gop_clearmedia_")
            kb = [
                [InlineKeyboardButton(t('admin.guides.buttons.confirm_clear', lang), callback_data=f"gop_clearmedia_confirm_{key}_{mode}")],
                [InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data=f"gsel_{key}_{mode}")]
            ]
            await query.edit_message_text(
                t('admin.guides.clearmedia.confirm_text', lang),
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return ADMIN_MENU
        
        elif data.startswith("gop_setcode_"):
            key, mode = self._extract_key_mode(data, "gop_setcode_")
            context.user_data['guide_key'] = key
            context.user_data['guide_mode'] = mode
            
            cur = (await self.db.get_guide_code(key, mode=mode) or "").strip()
            code_label = t('guides.sens_short', lang) if key == "sens" else t('guides.hud_short', lang)
            
            msg = (
                f"{t('admin.guides.setcode.title', lang, section=code_label)}\n\n"
                f"{t('admin.guides.setcode.current', lang, current=(cur or t('common.none', lang)))}\n\n"
                f"{t('admin.guides.setcode.prompt', lang)}\n"
                f"{t('admin.guides.setcode.tip', lang)}"
            )
            
            await query.edit_message_text(msg)
            logger.info(f"Set code started for {key} ({mode})")
            return GUIDE_CODE
        
        elif data.startswith("gop_clearcode_"):
            key, mode = self._extract_key_mode(data, "gop_clearcode_")
            await query.answer(t('feedback.wait', lang))
            
            if await self.db.clear_guide_code(key, mode=mode):
                await query.message.reply_text(t('admin.guides.clearcode.success', lang), parse_mode='HTML')
                logger.info(f"Code cleared for {key} ({mode})")
            else:
                await query.message.reply_text(t('admin.guides.clearcode.error', lang))
                logger.error(f"Failed to clear code for {key} ({mode})")
            
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete guides clearcode confirmation message: {e}")
            
            return await self.guide_section_menu(update, context, send_new=True)
        
        return ADMIN_MENU
    
    # ==================== Data Handlers ====================
    
    async def guide_rename_received(self, update: Update, context: CustomContext):
        """دریافت نام جدید برای بخش"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        name = (update.message.text or "").strip()
        key = context.user_data.get('guide_key')
        mode = context.user_data.get('guide_mode', 'br')
        
        if not key:
            await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
            return ADMIN_MENU
        
        if await self.db.set_guide_name(key, name, mode=mode):
            name_esc = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            msg = t('admin.guides.rename.saved', lang, name=name_esc)
            
            await update.message.reply_text(msg, parse_mode='HTML')
            logger.info(f"Guide renamed: {key} ({mode}) -> {name}")
        else:
            await update.message.reply_text(t('admin.guides.rename.error', lang))
            logger.error(f"Failed to rename guide: {key} ({mode})")
        
        return await self.guide_section_menu(update, context, send_new=True)
    
    async def guide_photo_received(self, update: Update, context: CustomContext):
        """دریافت عکس"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        key = context.user_data.get('guide_key')
        if not key:
            await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
            return ADMIN_MENU
        
        if update.message.photo:
            photo = update.message.photo[-1]
            
            from utils.validators_enhanced import AttachmentValidator
            result = AttachmentValidator.validate_image(file_size=getattr(photo, 'file_size', 0))
            if not result.is_valid:
                error_msg = t(result.error_key, lang, **(result.error_details or {}))
                await update.message.reply_text(error_msg)
                return GUIDE_PHOTO
                
            fid = photo.file_id
            if 'guide_temp_photos' not in context.user_data:
                context.user_data['guide_temp_photos'] = []
            context.user_data['guide_temp_photos'].append(fid)
            count = len(context.user_data['guide_temp_photos'])
            await update.message.reply_text(t('admin.guides.photo.saved', lang, count=count))
            logger.info(f"Photo received for {key}, total: {count}")
        else:
            await update.message.reply_text(t('admin.guides.photo.required', lang))
        
        return GUIDE_PHOTO
    
    async def guide_video_received(self, update: Update, context: CustomContext):
        """دریافت ویدیو"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        key = context.user_data.get('guide_key')
        if not key:
            await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
            return ADMIN_MENU
        
        if update.message.video:
            fid = update.message.video.file_id
            if 'guide_temp_videos' not in context.user_data:
                context.user_data['guide_temp_videos'] = []
            context.user_data['guide_temp_videos'].append(fid)
            count = len(context.user_data['guide_temp_videos'])
            await update.message.reply_text(t('admin.guides.video.saved', lang, count=count))
            logger.info(f"Video received for {key}, total: {count}")
        else:
            await update.message.reply_text(t('admin.guides.video.required', lang))
        
        return GUIDE_VIDEO
    
    async def guide_media_confirmed(self, update: Update, context: CustomContext, key: str):
        """تایید و ذخیره رسانه‌ها"""
        query = update.callback_query
        lang = await get_user_lang(update, context, self.db) or 'fa'
        await query.answer(t('feedback.wait', lang))
        
        photos = context.user_data.get('guide_temp_photos', [])
        videos = context.user_data.get('guide_temp_videos', [])
        mode = context.user_data.get('guide_mode', 'br')
        
        if not photos and not videos:
            await query.message.reply_text(t('admin.guides.media.none', lang))
            return await self.guide_section_menu(update, context)
        
        # ذخیره رسانه‌ها
        for photo_id in photos:
            await self.db.add_guide_photo(key, photo_id, mode=mode)
        for video_id in videos:
            await self.db.add_guide_video(key, video_id, mode=mode)
        
        # پاکسازی
        context.user_data.pop('guide_temp_photos', None)
        context.user_data.pop('guide_temp_videos', None)
        
        text = t('admin.guides.media.saved', lang, photos=len(photos), videos=len(videos))
        
        await query.message.reply_text(text, parse_mode='HTML')
        logger.info(f"Media saved for {key} ({mode}): {len(photos)} photos, {len(videos)} videos")
        
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete guides media saved message: {e}")
        
        return await self.guide_section_menu(update, context, send_new=True)
    
    async def guide_code_received(self, update: Update, context: CustomContext):
        """دریافت و ذخیره کد"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        key = context.user_data.get('guide_key')
        mode = context.user_data.get('guide_mode', 'br')
        code = (update.message.text or "").strip()
        
        if not key:
            await update.message.reply_text(t('admin.guides.error.key_not_found', lang))
            return ADMIN_MENU
        
        if await self.db.set_guide_code(key, code, mode=mode):
            code_esc = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            await update.message.reply_text(
                t('admin.guides.code.saved', lang, code=code_esc),
                parse_mode='HTML'
            )
            logger.info(f"Code saved for {key} ({mode})")
        else:
            await update.message.reply_text(t('admin.guides.code.error', lang))
            logger.error(f"Failed to save code for {key} ({mode})")
        
        return await self.guide_section_menu(update, context, send_new=True)
