from core.context import CustomContext

"""
مدیریت منوی اصلی و navigation
⚠️ این کد عیناً از user_handlers.py خط 91-141 کپی شده
"""

import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler
from core.events import event_bus, EventTypes
from managers.channel_manager import require_channel_membership
from handlers.user.base_user_handler import BaseUserHandler
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t, kb
from managers.admin_notifier import AdminNotifier
from utils.validation import parse_attachment_deep_link, parse_all_weapons_deep_link
from utils.telegram_safety import safe_edit_message_text

logger = get_logger("user", "user.log")


class MainMenuHandler(BaseUserHandler):
    """مدیریت منوی اصلی ربات با طراحی اینلاین ۵ دکمه‌ای مدرن"""

    async def build_main_inline_keyboard(
        self, user_id: int, lang: str
    ) -> InlineKeyboardMarkup:
        """ساخت منوی اصلی شیشه‌ای ۵ دکمه‌ای مدرن و بهینه"""
        keyboard = [
            # ردیف ۱: برترهای فصل و متا (چپ) + دریافت اتچمنت (راست)
            [
                InlineKeyboardButton(
                    t("menu.buttons.meta_hub", lang), callback_data="nav_meta_hub"
                ),
                InlineKeyboardButton(
                    t("menu.buttons.get", lang), callback_data="categories"
                ),
            ],
            # ردیف ۲: تنظیمات کالاف HUD/Sens (تمام‌عرض)
            [
                InlineKeyboardButton(
                    t("menu.buttons.game_settings", lang),
                    callback_data="game_settings_menu",
                )
            ],
            # ردیف ۳: جستجوی سلاح (چپ) + لوداوت‌های کاربران (راست)
            [
                InlineKeyboardButton(
                    t("menu.buttons.search", lang), callback_data="search"
                ),
                InlineKeyboardButton(
                    t("menu.buttons.ua", lang), callback_data="ua_menu"
                ),
            ],
            # ردیف ۴: پشتیبانی و تنظیمات (تمام‌عرض)
            [
                InlineKeyboardButton(
                    t("menu.buttons.settings_hub", lang),
                    callback_data="nav_settings_hub",
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def build_group_inline_keyboard(
        self, bot_username: str, lang: str
    ) -> InlineKeyboardMarkup:
        """ساخت منوی گروه با ساختار و چیدمان یکسان با منوی اصلی به همراه دکمه ورود به پی‌وی"""
        keyboard = [
            # ردیف ۱: برترهای فصل و متا (چپ) + دریافت اتچمنت (راست)
            [
                InlineKeyboardButton(
                    t("menu.buttons.meta_hub", lang), callback_data="nav_meta_hub"
                ),
                InlineKeyboardButton(
                    t("menu.buttons.get", lang), callback_data="categories"
                ),
            ],
            # ردیف ۲: تنظیمات کالاف HUD/Sens (تمام‌عرض)
            [
                InlineKeyboardButton(
                    t("menu.buttons.game_settings", lang),
                    callback_data="game_settings_menu",
                )
            ],
            # ردیف ۳: جستجوی سلاح (چپ) + لوداوت‌های کاربران (راست)
            [
                InlineKeyboardButton(
                    t("menu.buttons.search", lang), callback_data="search"
                ),
                InlineKeyboardButton(
                    t("menu.buttons.ua", lang), callback_data="ua_menu"
                ),
            ],
            # ردیف ۴: پشتیبانی و تنظیمات (تمام‌عرض)
            [
                InlineKeyboardButton(
                    t("menu.buttons.settings_hub", lang),
                    callback_data="nav_settings_hub",
                )
            ],
        ]
        if bot_username:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "💬 ورود به پی‌وی ربات (امکانات کامل) ↗️",
                        url=f"https://t.me/{bot_username}?start=from_group",
                    )
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    async def build_admin_reply_keyboard(
        self, user_id: int, lang: str
    ) -> ReplyKeyboardMarkup | None:
        """ساخت دکمه ریپلای کیبورد اختصاصی مدیریت برای ادمین‌ها در پایین چت"""
        try:
            if await self.db.users.is_admin(user_id):
                return ReplyKeyboardMarkup(
                    [[kb("menu.buttons.admin", lang)]],
                    resize_keyboard=True,
                    is_persistent=True,
                )
        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
        return None

    @require_channel_membership
    async def start(self, update: Update, context: CustomContext):
        """دستور شروع و نمایش منوی اصلی"""
        user_id = update.effective_user.id
        if context.args and len(context.args) > 0:
            context.user_data["start_param"] = context.args[0]

        # Deep-link actions (فقط یک‌بار مصرف تا در دستورات بعدی /start تکرار نشود)
        param = context.user_data.pop("start_param", None)
        if param and update.message:
            # /start att-{id}-{mode}
            if param.startswith("att-"):
                att_id, mode = parse_attachment_deep_link(param)
                if att_id:
                    att = await self.db.attachments.get_attachment_by_id(att_id)
                    if att:
                        lang = await get_user_lang(update, context, self.db) or "fa"
                        mode_name = t(f"mode.{mode}_btn", lang)
                        weapon = att.get("weapon") or att.get("weapon_name") or ""
                        caption = f"**{att.get('name', '')}**\n{t('attachment.code', lang)}: `{att.get('code', '')}`\n{weapon} | {mode_name}"
                        # دکمه‌های بازخورد
                        feedback_kb = None
                        a_id = att.get("id")
                        if a_id:
                            try:
                                stats = (
                                    await self.db.analytics.get_attachment_stats(
                                        a_id, period="all"
                                    )
                                    or {}
                                )
                                like_count = stats.get("like_count", 0)
                                dislike_count = stats.get("dislike_count", 0)
                            except Exception:
                                like_count = dislike_count = 0

                            from core.container import get_container

                            fb_handler = get_container().feedback_handler
                            feedback_kb = InlineKeyboardMarkup(
                                fb_handler.build_attachment_keyboard(
                                    a_id,
                                    like_count=like_count,
                                    dislike_count=dislike_count,
                                    lang=lang,
                                    mode=mode,
                                )
                            )
                        try:
                            if att.get("image"):
                                await update.message.reply_photo(
                                    photo=att["image"],
                                    caption=caption,
                                    parse_mode="Markdown",
                                    reply_markup=feedback_kb,
                                )
                            else:
                                await update.message.reply_text(
                                    caption,
                                    parse_mode="Markdown",
                                    reply_markup=feedback_kb,
                                )
                                return
                            return
                        except Exception as e:
                            logger.error(
                                f"Error sending attachment photo/message (att_id {a_id}): {e}"
                            )
                            await update.message.reply_text(
                                caption, parse_mode="Markdown", reply_markup=feedback_kb
                            )
                            return
            # /start allw-{category}__{weapon}__{mode}
            if param.startswith("allw-"):
                category, weapon, mode = parse_all_weapons_deep_link(param)
                if category and weapon:
                    items = (
                        await self.db.attachments.get_all_attachments(
                            category, weapon, mode=mode
                        )
                        or []
                    )
                    lang = await get_user_lang(update, context, self.db) or "fa"
                    mode_name = t(f"mode.{mode}_btn", lang)
                    if not items:
                        await update.message.reply_text(t("attachment.none", lang))
                        return
                    header = t(
                        "attachment.all.title", lang, weapon=weapon, mode=mode_name
                    )
                    lines = [header]
                    for i, att in enumerate(items[:20], start=1):
                        lines.append(
                            f"{i}. {att.get('name', '?')} — `{att.get('code', '')}`"
                        )
                    await update.message.reply_text(
                        "\n".join(lines), parse_mode="Markdown"
                    )
                    return

        # بررسی کاربر جدید قبل از ثبت
        admin_notifier = AdminNotifier(self.db)
        is_new_user = not await admin_notifier.is_existing_user(user_id)

        # Track user info in database
        await self._track_user_info(update)

        # ثبت خودکار کاربر به عنوان مشترک برای دریافت نوتیفیکیشن‌ها
        try:
            await self.subs.add(user_id)
        except Exception as e:
            logger.warning(f"Error registering user {user_id} for notifications: {e}")

        # Emit async event for user registered/started
        asyncio.create_task(
            event_bus.emit(
                EventTypes.USER_REGISTERED,
                user_id=user_id,
                user=update.effective_user,
                is_new_user=is_new_user,
                context=context,
            )
        )

        lang = await get_user_lang(update, context, self.db) or "fa"

        # تفکیک محیط سوپرگروه/گروه از پی‌وی (عدم ارسال Reply Keyboard در گروه)
        chat_type = update.effective_chat.type if update.effective_chat else "private"
        if chat_type in ("group", "supergroup"):
            bot_username = context.bot.username or ""
            if not bot_username:
                try:
                    me = await context.bot.get_me()
                    bot_username = me.username or ""
                except Exception:
                    pass
            group_markup = await self.build_group_inline_keyboard(bot_username, lang)

            import html as py_html

            if update.message and getattr(update.message, "sender_chat", None):
                sender_name = py_html.escape(
                    update.message.sender_chat.title or "کانال"
                )
                user_mention = f"<b>{sender_name}</b>"
            elif update.effective_user:
                user_mention = update.effective_user.mention_html()
            else:
                user_mention = "<b>کاربر</b>"

            group_text = (
                f"🎮 <b>{t('app.name', lang)}</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"سلام {user_mention} عزیز! خوش آمدید.\n"
                "برای دریافت سریع اتچمنت‌ها یا جستجوی سلاح از گزینه‌های زیر استفاده کنید:"
            )
            if update.message:
                await update.message.reply_html(
                    group_text,
                    reply_markup=group_markup,
                    reply_to_message_id=update.message.message_id,
                )
            return

        inline_markup = await self.build_main_inline_keyboard(user_id, lang)
        admin_markup = await self.build_admin_reply_keyboard(user_id, lang)
        welcome_text = t("welcome", lang, app_name=t("app.name", lang))

        if update.message:
            # ارسال کیبورد اختصاصی ادمین در پایین چت (در صورت ادمین بودن)
            if admin_markup:
                await update.message.reply_text(
                    welcome_text,
                    reply_markup=inline_markup,
                    parse_mode="Markdown",
                )
                # ارسال ریپلای کیبورد پایینی برای ادمین
                try:
                    await update.message.reply_text(
                        "👑", reply_markup=admin_markup
                    )
                except Exception:
                    pass
            else:
                await update.message.reply_text(
                    welcome_text,
                    reply_markup=inline_markup,
                    parse_mode="Markdown",
                )

    async def nav_meta_hub(self, update: Update, context: CustomContext):
        """نمایش زیرمنوی برترهای فصل، متای بازی و پیشنهادی‌ها"""
        query = update.callback_query
        await query.answer()

        lang = await get_user_lang(update, context, self.db) or "fa"
        keyboard = [
            [
                InlineKeyboardButton(
                    t("menu.buttons.season_top", lang), callback_data="season_top"
                ),
                InlineKeyboardButton(
                    t("menu.buttons.season_list", lang), callback_data="season_top_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("menu.buttons.suggested", lang),
                    callback_data="suggested_attachments",
                ),
                InlineKeyboardButton(
                    t("menu.buttons.leaderboard", lang), callback_data="leaderboard"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("menu.buttons.back_to_main", lang), callback_data="main_menu"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = t("menu.meta_hub.title", lang)
        await safe_edit_message_text(
            query, text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def nav_settings_hub(self, update: Update, context: CustomContext):
        """نمایش زیرمنوی تنظیمات، زبان، اعلان‌ها، پشتیبانی و راهنما"""
        query = update.callback_query
        await query.answer()

        lang = await get_user_lang(update, context, self.db) or "fa"
        keyboard = [
            [
                InlineKeyboardButton(
                    t("menu.buttons.game_settings", lang),
                    callback_data="game_settings_menu",
                ),
                InlineKeyboardButton(
                    t("menu.buttons.notify", lang), callback_data="user_notif_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("settings.user.language", lang),
                    callback_data="user_settings_language",
                ),
                InlineKeyboardButton(
                    t("menu.buttons.contact", lang), callback_data="contact"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("menu.buttons.help", lang), callback_data="help"
                ),
            ],
        ]

        # بررسی فعال بودن CMS
        try:
            cms_enabled = (
                str(await self.db.settings.get_setting("cms_enabled", "false")).lower()
                == "true"
            )
        except Exception:
            cms_enabled = False

        if cms_enabled:
            keyboard[2].insert(
                0,
                InlineKeyboardButton(
                    t("menu.buttons.cms", lang), callback_data="cms"
                ),
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    t("menu.buttons.back_to_main", lang), callback_data="main_menu"
                )
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = t("menu.settings_hub.title", lang)
        await safe_edit_message_text(
            query, text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def _build_main_menu_keyboard(
        self, user_id: int, lang: str
    ) -> ReplyKeyboardMarkup:
        """ساخت منوی ریپلای قدیمی جهت پشتیبانی رو به عقب (Backwards Compatibility)"""
        keyboard = [
            [kb("menu.buttons.game_settings", lang), kb("menu.buttons.get", lang)]
        ]
        ua_system_enabled = (
            await self.db.settings.get_ua_setting("system_enabled") or "1"
        )
        if ua_system_enabled in ("1", "true", "True"):
            keyboard.append(
                [kb("menu.buttons.ua", lang), kb("menu.buttons.suggested", lang)]
            )
        else:
            keyboard.append([kb("menu.buttons.suggested", lang)])

        keyboard.extend(
            [
                [
                    kb("menu.buttons.season_list", lang),
                    kb("menu.buttons.season_top", lang),
                ],
                [kb("menu.buttons.notify", lang), kb("menu.buttons.search", lang)],
                [kb("menu.buttons.contact", lang), kb("menu.buttons.help", lang)],
            ]
        )
        if await self.db.users.is_admin(user_id):
            keyboard.append([kb("menu.buttons.admin", lang)])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def back_msg(self, update: Update, context: CustomContext):
        """بازگشت به منوی اصلی از طریق پیام"""
        chat = update.effective_chat
        chat_type = chat.type if chat else "private"
        if chat_type in ("group", "supergroup") and update.message:
            from telegram import ReplyKeyboardRemove

            try:
                # حذف کیبورد ریپلای از پایین صفحه چت گروه
                await update.message.reply_text(
                    "🔄",
                    reply_markup=ReplyKeyboardRemove(selective=True),
                    reply_to_message_id=update.message.message_id,
                )
            except Exception:
                pass
        return await self.start(update, context)

    async def main_menu(self, update: Update, context: CustomContext):
        """بازگشت به منوی اصلی با ویرایش نرم پیام شیشه‌ای (بدون اسپم چت)"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        lang = await get_user_lang(update, context, self.db) or "fa"

        chat = update.effective_chat
        chat_type = chat.type if chat else "private"

        if chat_type in ("group", "supergroup"):
            bot_username = context.bot.username or ""
            if not bot_username:
                try:
                    me = await context.bot.get_me()
                    bot_username = me.username or ""
                except Exception:
                    pass
            inline_markup = await self.build_group_inline_keyboard(bot_username, lang)
            welcome_text = (
                f"🎮 *{t('app.name', lang)}* | نسخه گروه\n\n"
                "برای دریافت اتچمنت‌ها، جستجو یا تنظیمات از گزینه‌های زیر استفاده کنید:"
            )
        else:
            inline_markup = await self.build_main_inline_keyboard(user_id, lang)
            welcome_text = t("welcome", lang, app_name=t("app.name", lang))

        try:
            await safe_edit_message_text(
                query, welcome_text, reply_markup=inline_markup, parse_mode="Markdown"
            )
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await query.message.chat.send_message(
                welcome_text, reply_markup=inline_markup, parse_mode="Markdown"
            )

        return ConversationHandler.END

    async def show_user_id(self, update: Update, context: CustomContext):
        """نمایش شناسه کاربری"""
        await update.message.reply_text(
            f"Your User ID: `{update.effective_user.id}`", parse_mode="Markdown"
        )
