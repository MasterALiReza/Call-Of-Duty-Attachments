from core.context import CustomContext

"""
Search module handlers.
"""

import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler

from utils.logger import log_user_action, get_logger, log_exception
from utils.language import get_user_lang
from utils.i18n import t
from handlers.user.base_user_handler import BaseUserHandler
from utils.telegram_safety import safe_edit_message_text

# Must match the value used in handlers/user/__init__.py
SEARCHING = 3
logger = get_logger("user", "user.log")


class SearchHandler(BaseUserHandler):
    """User search flow."""

    def __init__(self, db):
        super().__init__(db)

    async def search_start_msg(self, update: Update, context: CustomContext):
        """Start search from a text message."""
        from datetime import datetime

        lang = await get_user_lang(update, context, self.db) or "fa"
        now = datetime.now().strftime("%H:%M:%S")
        text = (
            t("search.prompt", lang) + f" _{t('notification.updated', lang, time=now)}_"
        )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t("search.cancel", lang), callback_data="main_menu"
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )
        return SEARCHING

    @log_user_action("search_start")
    async def search_start(self, update: Update, context: CustomContext):
        """Start search from callback."""
        query = update.callback_query
        await query.answer()
        lang = await get_user_lang(update, context, self.db) or "fa"

        await safe_edit_message_text(
            query,
            t("search.prompt", lang),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t("search.cancel", lang), callback_data="main_menu"
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )

        return SEARCHING

    @log_user_action("search_process")
    async def search_process(self, update: Update, context: CustomContext):
        """Process free-text search query."""
        lang = await get_user_lang(update, context, self.db) or "fa"
        query_text = update.message.text.strip()
        start_ts = time.time()

        results = await self.db.attachments.search(query_text)
        elapsed_ms = int((time.time() - start_ts) * 1000)
        attachments_results = results or []

        unique_weapons = {}
        for item in attachments_results:
            category = item.get("category")
            weapon = item.get("weapon")
            if not category or not weapon:
                continue
            weapon_key = f"{category}:{weapon}"
            if weapon_key not in unique_weapons:
                unique_weapons[weapon_key] = {
                    "category": category,
                    "weapon": weapon,
                }
        weapons_results = list(unique_weapons.values())

        total_results = len(attachments_results)
        text = t("search.results", lang, query=query_text, count=total_results) + "\n\n"
        keyboard = []
        shown_all = set()

        try:
            user_id = update.effective_user.id if update.effective_user else None
            if user_id:
                await self.db.analytics.track_search(
                    user_id, query_text, total_results, float(elapsed_ms)
                )
        except Exception:
            pass

        if weapons_results:
            text += f"**{t('search.weapons_header', lang)}**\n"
            for item in weapons_results[:3]:
                category_key = item["category"]
                category_name = t(f"category.{category_key}", "en")
                weapon_name = item["weapon"]
                text += f"• {weapon_name} ({category_name})\n"

                weapon_atts = [
                    a
                    for a in attachments_results
                    if a["weapon"] == weapon_name and a["category"] == category_key
                ]

                for att in weapon_atts[:3]:
                    mode = att.get("mode", "br")
                    mode_emoji = "🪂" if mode == "br" else "🎮"
                    mode_text = t(f"mode.{mode}_short", lang)

                    badge = ""
                    if att.get("is_season_top"):
                        badge = t("badge.season_top", lang)
                    elif att.get("is_top"):
                        badge = t("badge.top", lang)

                    button_text = f"{mode_emoji} {mode_text} : {att['name']}"
                    if badge:
                        button_text += f" {badge}"

                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                button_text,
                                callback_data=f"qatt_{category_key}__{weapon_name}__{mode}__{att['code']}",
                            )
                        ]
                    )

                key = (category_key, weapon_name)
                if key not in shown_all:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                t(
                                    "search.show_all_for_weapon",
                                    lang,
                                    weapon=weapon_name,
                                ),
                                callback_data=f"all_{category_key}__{weapon_name}",
                            )
                        ]
                    )
                    shown_all.add(key)
            text += "\n"

        if attachments_results:
            text += f"**{t('search.attachments_header', lang)}**\n"
            for item in attachments_results[:5]:
                weapon_name = item["weapon"]
                name = item["name"]
                code = item["code"]

                text += f"• {name} (`{code}`) - {weapon_name}\n"

                key = (item["category"], weapon_name)
                if key not in shown_all:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                t(
                                    "search.show_all_for_weapon",
                                    lang,
                                    weapon=weapon_name,
                                ),
                                callback_data=f"all_{item['category']}__{weapon_name}",
                            )
                        ]
                    )
                    shown_all.add(key)
            text += "\n"

        if not weapons_results and not attachments_results:
            text = t("search.no_results", lang, query=query_text)

        keyboard.append(
            [InlineKeyboardButton(t("search.new", lang), callback_data="search")]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    t("menu.buttons.home", lang), callback_data="main_menu"
                )
            ]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode="Markdown"
        )
        return ConversationHandler.END

    async def search_restart_silently(self, update: Update, context: CustomContext):
        """When already in SEARCHING state and user presses search again."""
        lang = await get_user_lang(update, context, self.db) or "fa"
        await update.message.reply_text(
            t("search.prompt", lang),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            t("search.cancel", lang), callback_data="main_menu"
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )
        return SEARCHING

    async def send_attachment_quick(self, update: Update, context: CustomContext):
        """Handle quick attachment callback from search results.

        Callback format: qatt_{category}__{weapon}__{mode}__{code}
        """
        query = update.callback_query
        await query.answer()

        parts = query.data.replace("qatt_", "", 1).split("__")
        if len(parts) != 4:
            logger.error(f"Invalid quick attachment callback: {query.data}")
            return

        category, weapon, mode, code = parts
        await self._send_attachment_by_identity(
            update, context, category, weapon, mode, code
        )

    async def attachment_detail_with_mode(self, update: Update, context: CustomContext):
        """Backward-compatible attm callback handler.

        Callback format: attm_{category}__{weapon}__{code}__{mode}
        """
        query = update.callback_query
        await query.answer()

        parts = query.data.replace("attm_", "", 1).split("__")
        if len(parts) != 4:
            logger.error(f"Invalid attm callback: {query.data}")
            return

        category, weapon, code, mode = parts
        await self._send_attachment_by_identity(
            update, context, category, weapon, mode, code
        )

    async def _send_attachment_by_identity(
        self,
        update: Update,
        context: CustomContext,
        category: str,
        weapon: str,
        mode: str,
        code: str,
    ) -> None:
        """Load and send a single attachment by identity fields."""
        query = update.callback_query

        attachments = await self.db.attachments.get_all_attachments(
            category, weapon, mode=mode
        )
        selected = next((att for att in attachments if att.get("code") == code), None)

        lang = await get_user_lang(update, context, self.db) or "fa"
        if not selected:
            await query.answer(t("attachment.not_found", lang), show_alert=True)
            return

        mode_short = t(f"mode.{mode}_btn", lang)
        cat_name = t(f"category.{category}", "en")
        caption = f"**{selected['name']}**\n"
        caption += f"{t('weapon.label', lang)}: {weapon} ({cat_name})\n"
        caption += f"{t('mode.label', lang)}: {mode_short}\n"
        caption += f"{t('attachment.code', lang)}: `{selected['code']}`\n\n{t('attachment.tap_to_copy', lang)}"

        att_id = selected.get("id")
        stats = (
            await self.db.analytics.get_attachment_stats(att_id, period="all")
            if att_id
            else {}
        )
        like_count = stats.get("like_count", 0)
        dislike_count = stats.get("dislike_count", 0)

        if att_id:
            await self.db.analytics.track_attachment_view(query.from_user.id, att_id)

        feedback_kb = None
        if att_id:
            from core.container import get_container

            fb_handler = get_container().feedback_handler
            feedback_kb = InlineKeyboardMarkup(
                fb_handler.build_attachment_keyboard(
                    att_id,
                    like_count=like_count,
                    dislike_count=dislike_count,
                    lang=lang,
                    mode=mode,
                )
            )

        try:
            if selected.get("image"):
                await query.message.reply_photo(
                    photo=selected["image"],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=feedback_kb,
                )
            else:
                await query.message.reply_text(
                    caption, parse_mode="Markdown", reply_markup=feedback_kb
                )
        except Exception as e:
            logger.error(f"Error sending quick attachment: {e}")
            log_exception(logger, e, "context")
            await query.message.reply_text(caption, parse_mode="Markdown")
