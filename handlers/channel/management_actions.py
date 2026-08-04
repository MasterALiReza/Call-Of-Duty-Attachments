"""Shared channel management actions that are not flow-specific."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from core.context import CustomContext
from utils.i18n import t
from utils.language import get_user_lang
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def clear_channels_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    channel_menu_state: str,
):
    """Clear all required channels with confirmation step."""
    query = update.callback_query
    await query.answer()

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"

    db = context.bot_data["database"]
    if query.data == "clear_channels":
        keyboard = [
            [
                InlineKeyboardButton(
                    t("admin.channels.delete.confirm_yes", lang),
                    callback_data="clear_yes",
                ),
                InlineKeyboardButton(
                    t("menu.buttons.cancel", lang), callback_data="channel_menu"
                ),
            ]
        ]
        await safe_edit_message_text(
            query,
            t("admin.channels.clear.confirm", lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return channel_menu_state

    channels = await db.cms.get_required_channels()
    success_all = True
    for channel in channels:
        try:
            ok = await db.cms.remove_required_channel(channel["channel_id"])
            success_all = success_all and ok
        except Exception:
            success_all = False

    if success_all:
        try:
            from managers.channel_manager import invalidate_all_cache

            cleared_count = invalidate_all_cache()
            logger.info(
                "[channel] Cleared all channels; invalidated cache for %s users",
                cleared_count,
            )
        except Exception as e:
            logger.error("[channel] Error invalidating cache after clear: %s", e)

    message = (
        t("admin.channels.clear.success", lang)
        if success_all
        else t("admin.channels.clear.error", lang)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.back", lang), callback_data="channel_menu"
            )
        ]
    ]
    await safe_edit_message_text(
        query, message, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return channel_menu_state
