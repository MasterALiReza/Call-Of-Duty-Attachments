from core.context import CustomContext
"""
مدیریت راهنماها و تنظیمات بازی
⚠️ این کد عیناً از user_handlers.py خط 143-354 کپی شده
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.logger import log_user_action, get_logger
from utils.language import get_user_lang
from utils.i18n import t
from handlers.user.base_user_handler import BaseUserHandler
from utils.telegram_safety import safe_edit_message_text

logger = get_logger('user', 'user.log')


class GuidesHandler(BaseUserHandler):
    """مدیریت راهنماها و تنظیمات بازی"""
    
    async def _send_guide(self, update: Update, key: str, mode: str = "br", context: CustomContext = None):
        """ارسال محتوای یک بخش راهنما (basic/sens/hud) با پشتیبانی از mode."""
        lang = (await get_user_lang(update, context, self.db) or 'fa') if context else 'fa'
        guide = await self.db.get_guide(key, mode=mode)
        # استفاده از translation key به جای name از دیتابیس
        name = t(f"guides.{key}_short", lang)
        photos = guide.get("photos", []) or []
        videos = guide.get("videos", []) or []
        mode_name = t(f"mode.{mode}_short", lang)
        code = (guide.get("code") or "").strip() if key in ["sens", "hud"] else ""
        
        # چک کردن اینکه محتوا داره یا نه
        has_content = False
        if photos or videos:
            has_content = True
        elif key == "sens" and code:
            has_content = True
        
        # اگر محتوا نداره
        if not has_content:
            header = f"📚 {name}\n🎮 {t('mode.label', lang)}: {mode_name}\n\n"
            header += t("attachment.none", lang)
            await update.message.reply_text(header)
            return
        
        # اگر محتوا داره، ارسال کن
        header = f"📚 {name}\n🎮 {t('mode.label', lang)}: {mode_name}"
        if code:
            header += f"\n🔤 {t('attachment.code', lang)}: `{code}`"
        await update.message.reply_text(header, parse_mode='Markdown')
        
        # ارسال عکس‌ها
        for fid in photos:
            try:
                await update.message.reply_photo(photo=fid)
            except Exception as e:
                logger.warning(f"Error sending image {fid}: {e}")
        # ارسال ویدیوها
        for fid in videos:
            try:
                await update.message.reply_video(video=fid)
            except Exception as e:
                logger.warning(f"Error sending video {fid}: {e}")
        
        # پیام تایید نهایی
        await update.message.reply_text(t("success.generic", lang))

    async def guide_basic_msg(self, update: Update, context: CustomContext):
        return await self._send_guide(update, "basic", context=context)

    async def guide_sens_msg(self, update: Update, context: CustomContext):
        return await self._send_guide(update, "sens", context=context)

    async def guide_hud_msg(self, update: Update, context: CustomContext):
        return await self._send_guide(update, "hud", context=context)

    async def guide_dynamic_msg(self, update: Update, context: CustomContext):
        """روتر داینامیک: اگر متن پیام برابر یکی از عناوین Basic/Sens/Hud باشد، همان بخش را ارسال کن."""
        # ✅ Fixed: Check if update.message exists (could be callback_query)
        if not update.message or not update.message.text:
            return
        
        text = update.message.text.strip()
        if not text:
            return
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode = context.user_data.get('game_settings_mode', 'br')
        
        # ساخت mapping بر اساس translation keys (هر دو زبان)
        mapping = {
            t("guides.basic_short", "fa"): "basic",
            t("guides.basic_short", "en"): "basic",
            t("guides.sens_short", "fa"): "sens",
            t("guides.sens_short", "en"): "sens",
            t("guides.hud_short", "fa"): "hud",
            t("guides.hud_short", "en"): "hud",
        }
        
        key = mapping.get(text)
        if key:
            return await self._send_guide(update, key, mode=mode, context=context)
    
    @log_user_action("game_settings_menu")

    async def game_settings_menu(self, update: Update, context: CustomContext):
        """منوی تنظیمات کالاف - انتخاب mode (BR/MP)"""
        lang = await get_user_lang(update, context, self.db) or 'fa'
        keyboard = [
            [InlineKeyboardButton(t("mode.br_btn", lang), callback_data="game_settings_br"),
             InlineKeyboardButton(t("mode.mp_btn", lang), callback_data="game_settings_mp")],
            [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = t("guides.title", lang) + "\n\n"
        text += t("guides.hud_desc", lang, mode="BR/MP") + "\n\n"
        text += t("guides.choose_mode", lang)
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await safe_edit_message_text(
                query,
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    @log_user_action("game_settings_mode_selected")

    async def game_settings_mode_selected(self, update: Update, context: CustomContext):
        """پس از انتخاب mode، منوی انتخاب بخش (Basic/Sens/HUD) را نمایش بده"""
        query = update.callback_query
        await query.answer()
        
        mode = query.data.replace("game_settings_", "")
        context.user_data['game_settings_mode'] = mode
        
        lang = await get_user_lang(update, context, self.db) or 'fa'
        mode_name = t(f"mode.{mode}_btn", lang)
        
        # دریافت راهنماها
        guides = await self.db.get_guides(mode=mode)
        
        # ساخت دکمه‌ها با ایموجی و تعداد مدیا
        def make_button_text(emoji: str, name: str, guide_key: str) -> str:
            guide = guides.get(guide_key, {})
            photos = guide.get("photos", []) or []
            videos = guide.get("videos", []) or []
            total_media = len(photos) + len(videos)
            
            if total_media > 0:
                return f"{emoji} {name} ({total_media})"
            return f"{emoji} {name}"
        
        hud_text = make_button_text("🖼️", t("guides.hud_short", lang), "hud")
        basic_text = make_button_text("⚙️", t("guides.basic_short", lang), "basic")
        sens_text = make_button_text("🎯", t("guides.sens_short", lang), "sens")
        keyboard = [
            [InlineKeyboardButton(hud_text, callback_data=f"show_guide_hud_{mode}"),
             InlineKeyboardButton(basic_text, callback_data=f"show_guide_basic_{mode}")],
            [InlineKeyboardButton(sens_text, callback_data=f"show_guide_sens_{mode}")],
            [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="game_settings_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = t("guides.title", lang) + f" - {mode_name}\n\n"
        text += t("guides.choose_section", lang)
        
        await safe_edit_message_text(
            query,
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @log_user_action("show_guide_inline")

    async def show_guide_inline(self, update: Update, context: CustomContext):
        """نمایش یک guide از طریق inline - show_guide_{key}_{mode}"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.replace("show_guide_", "")
        try:
            key, mode = data.rsplit("_", 1)
        except ValueError:
            return
        
        context.user_data['game_settings_mode'] = mode
        guide = await self.db.get_guide(key, mode=mode)
        # استفاده از translation key به جای name از دیتابیس
        lang = await get_user_lang(update, context, self.db) or 'fa'
        name = t(f"guides.{key}_short", lang)
        photos = guide.get("photos", []) or []
        videos = guide.get("videos", []) or []
        mode_name = t(f"mode.{mode}_short", lang)
        code = (guide.get("code") or "").strip() if key in ["sens", "hud"] else ""
        
        # چک کردن محتوا
        has_content = False
        if photos or videos:
            has_content = True
        elif key == "sens" and code:
            has_content = True
        
        # دکمه بازگشت
        back_button = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("menu.buttons.back", lang), callback_data=f"game_settings_{mode}")
        ]])
        
        # اگر محتوا نداره
        if not has_content:
            header = f"📚 {name}\n🎮 {t('mode.label', lang)}: {mode_name}\n\n"
            header += t("attachment.none", lang)
            await query.message.reply_text(header, reply_markup=back_button)
            return
        
        # اگر محتوا داره، ارسال کن
        header = f"📚 {name}\n🎮 {t('mode.label', lang)}: {mode_name}"
        if code:
            header += f"\n🔤 {t('attachment.code', lang)}: `{code}`"
        await query.message.reply_text(header, parse_mode='Markdown')
        
        # ارسال عکس‌ها
        for fid in photos:
            try:
                await query.message.reply_photo(photo=fid)
            except Exception as e:
                logger.warning(f"Error sending image {fid}: {e}")
        # ارسال ویدیوها
        for fid in videos:
            try:
                await query.message.reply_video(video=fid)
            except Exception as e:
                logger.warning(f"Error sending video {fid}: {e}")
        
        # پیام تایید
        await query.message.reply_text(t("success.generic", lang), reply_markup=back_button)
