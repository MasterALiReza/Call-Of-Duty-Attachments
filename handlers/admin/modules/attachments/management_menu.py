from core.context import CustomContext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from handlers.admin.modules.base_handler import BaseAdminHandler
from utils.language import get_user_lang
from utils.i18n import t
from core.security.role_manager import Permission


class AttachmentManagementHandler(BaseAdminHandler):
    """مدیریت منوی اصلی اتچمنت‌ها"""

    async def attachment_management_menu(self, update: Update, context: CustomContext):
        """نمایش منوی مدیریت اتچمنت‌ها"""
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or "fa"
        user_permissions = await self.role_manager.get_user_permissions(user_id)

        # عنوان منو
        message = (
            t("admin.menu.attachments", lang)
            + "\n\n"
            + t("admin.panel.welcome", lang).split("\n")[-1]
        )

        keyboard = []

        # ردیف ۱: افزودن و ویرایش (پرکاربردترین‌ها)
        row1 = []
        if (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
        ):
            row1.append(
                InlineKeyboardButton(
                    t("admin.buttons.add_attachment", lang),
                    callback_data="admin_add_attachment",
                )
            )
            row1.append(
                InlineKeyboardButton(
                    t("admin.buttons.edit_attachment", lang),
                    callback_data="admin_edit_attachment",
                )
            )
        if row1:
            keyboard.append(row1)

        # ردیف ۲: حذف و برترین‌ها
        row2 = []
        if (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
        ):
            row2.append(
                InlineKeyboardButton(
                    t("admin.buttons.delete_attachment", lang),
                    callback_data="admin_delete_attachment",
                )
            )
            row2.append(
                InlineKeyboardButton(
                    t("admin.buttons.set_top", lang), callback_data="admin_set_top"
                )
            )
        if row2:
            keyboard.append(row2)

        # ردیف ۳: مدیریت ساختار (سلاح‌ها و دسته‌ها)
        if Permission.MANAGE_CATEGORIES in user_permissions:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        t("admin.buttons.weapon_mgmt", lang),
                        callback_data="admin_weapon_mgmt",
                    ),
                    InlineKeyboardButton(
                        t("admin.buttons.category_mgmt", lang),
                        callback_data="admin_category_mgmt",
                    ),
                ]
            )

        # ردیف ۴: بخش تعاملی (پیشنهادی و اتچمنت کاربران)
        community_row = []
        if Permission.MANAGE_SUGGESTED_ATTACHMENTS in user_permissions:
            community_row.append(
                InlineKeyboardButton(
                    t("admin.buttons.suggested_attachments", lang),
                    callback_data="admin_manage_suggested",
                )
            )

        if (
            Permission.MANAGE_USER_ATTACHMENTS in user_permissions
            or await self.role_manager.is_super_admin(user_id)
        ):
            community_row.append(
                InlineKeyboardButton(
                    t("admin.buttons.user_attachments", lang),
                    callback_data="ua_admin_menu",
                )
            )

        if community_row:
            keyboard.append(community_row)

        # ردیف ۵: محدودیت گروهی برترهای فصل
        if (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
            or Permission.MANAGE_SETTINGS in user_permissions
            or await self.role_manager.is_super_admin(user_id)
        ):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        t("admin.buttons.season_rate_limit", lang),
                        callback_data="admin_season_rate_limit",
                    )
                ]
            )

        # دکمه بازگشت به منوی اصلی
        keyboard.append(
            [
                InlineKeyboardButton(
                    t("menu.buttons.back", lang), callback_data="admin_menu_return"
                )
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode="Markdown"
        )

        from handlers.admin.admin_states import ADMIN_MENU

        return ADMIN_MENU

    async def season_rate_limit_menu(self, update: Update, context: CustomContext):
        """نمایش منوی تنظیم محدودیت ارسال برترهای فصل در گروه"""
        from core.security.rate_limiter import group_season_top_limiter

        query = update.callback_query
        if query:
            try:
                await query.answer()
            except Exception:
                pass

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or "fa"
        user_permissions = await self.role_manager.get_user_permissions(user_id)

        if not (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
            or Permission.MANAGE_SETTINGS in user_permissions
            or await self.role_manager.is_super_admin(user_id)
        ):
            if query:
                await query.answer(t("common.no_permission", lang), show_alert=True)
            return await self.admin_menu_return(update, context)

        await group_season_top_limiter.ensure_initialized(self.db)

        enabled = group_season_top_limiter.enabled
        current_cooldown = int(group_season_top_limiter.cooldown)

        status_text = (
            t("common.status.enabled", lang)
            if enabled
            else t("common.status.disabled", lang)
        )
        status_emoji = "✅" if enabled else "❌"

        # Cooldown description
        minutes = current_cooldown // 60
        seconds_rem = current_cooldown % 60
        min_unit = t("time.minutes", lang) if lang == "en" else "دقیقه"
        sec_unit = t("time.seconds", lang) if lang == "en" else "ثانیه"
        if minutes > 0 and seconds_rem == 0:
            cd_desc = f"{minutes} {min_unit}"
        elif minutes > 0:
            cd_desc = f"{minutes} {min_unit} {seconds_rem} {sec_unit}"
        else:
            cd_desc = f"{current_cooldown} {sec_unit}"

        title = t("admin.season_rl.title", lang)
        desc = t("admin.season_rl.desc", lang)
        status_line = t(
            "admin.season_rl.status",
            lang,
            emoji=status_emoji,
            status=status_text,
        )
        cooldown_line = t(
            "admin.season_rl.cooldown",
            lang,
            cooldown=cd_desc,
            seconds=current_cooldown,
        )

        text = f"{title}\n\n{status_line}\n{cooldown_line}\n\n{desc}"

        toggle_label = t(
            "admin.season_rl.btn_disable" if enabled else "admin.season_rl.btn_enable",
            lang,
        )

        presets_row1 = [
            (60, "1m", "۱ دقیقه"),
            (120, "2m", "۲ دقیقه"),
            (300, "5m", "۵ دقیقه"),
        ]
        presets_row2 = [
            (600, "10m", "۱۰ دقیقه"),
            (900, "15m", "۱۵ دقیقه"),
            (1800, "30m", "۳۰ دقیقه"),
        ]

        def _make_preset_row(items):
            row = []
            for sec, en_label, fa_label in items:
                label = fa_label if lang == "fa" else en_label
                if sec == current_cooldown:
                    label = f"• {label} •"
                row.append(
                    InlineKeyboardButton(
                        label, callback_data=f"set_season_rl_{sec}"
                    )
                )
            return row

        keyboard = [
            [InlineKeyboardButton(toggle_label, callback_data="toggle_season_rl")],
            _make_preset_row(presets_row1),
            _make_preset_row(presets_row2),
            [
                InlineKeyboardButton(
                    t("menu.buttons.back", lang),
                    callback_data="admin_manage_attachments",
                )
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode="Markdown"
            )

        from handlers.admin.admin_states import ADMIN_MENU

        return ADMIN_MENU

    async def toggle_season_rate_limit(self, update: Update, context: CustomContext):
        """تغییر وضعیت فعال/غیرفعال بودن محدودیت گروهی"""
        from core.security.rate_limiter import group_season_top_limiter

        query = update.callback_query
        if query:
            try:
                await query.answer()
            except Exception:
                pass

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or "fa"
        user_permissions = await self.role_manager.get_user_permissions(user_id)

        if not (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
            or Permission.MANAGE_SETTINGS in user_permissions
            or await self.role_manager.is_super_admin(user_id)
        ):
            if query:
                await query.answer(t("common.no_permission", lang), show_alert=True)
            return await self.admin_menu_return(update, context)

        await group_season_top_limiter.ensure_initialized(self.db)
        new_state = not group_season_top_limiter.enabled
        group_season_top_limiter.set_enabled(new_state)

        await self.db.settings.set_setting(
            "group_season_top_rl_enabled",
            "1" if new_state else "0",
            description="Group Season Top Rate Limit Enabled",
            category="security",
            updated_by=user_id,
        )

        if query:
            try:
                await query.answer(t("admin.season_rl.updated", lang))
            except Exception:
                pass

        return await self.season_rate_limit_menu(update, context)

    async def set_season_rate_limit_seconds(
        self, update: Update, context: CustomContext
    ):
        """تنظیم مدت زمان کول‌داون گروهی بر حسب ثانیه"""
        from core.security.rate_limiter import group_season_top_limiter

        query = update.callback_query
        if query:
            try:
                await query.answer()
            except Exception:
                pass

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or "fa"
        user_permissions = await self.role_manager.get_user_permissions(user_id)

        if not (
            Permission.MANAGE_ATTACHMENTS_BR in user_permissions
            or Permission.MANAGE_ATTACHMENTS_MP in user_permissions
            or Permission.MANAGE_SETTINGS in user_permissions
            or await self.role_manager.is_super_admin(user_id)
        ):
            if query:
                await query.answer(t("common.no_permission", lang), show_alert=True)
            return await self.admin_menu_return(update, context)

        await group_season_top_limiter.ensure_initialized(self.db)
        try:
            val_str = query.data.replace("set_season_rl_", "")
            seconds = int(val_str)
        except Exception:
            seconds = 300

        group_season_top_limiter.set_cooldown(seconds)

        await self.db.settings.set_setting(
            "group_season_top_cooldown",
            str(seconds),
            description="Group Season Top Cooldown in seconds",
            category="security",
            updated_by=user_id,
        )

        if query:
            try:
                await query.answer(t("admin.season_rl.updated", lang))
            except Exception:
                pass

        return await self.season_rate_limit_menu(update, context)
