"""Channel detail/toggle handlers extracted from channel_handlers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from core.context import CustomContext
from utils.i18n import t
from utils.language import get_user_lang
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def view_channel_details_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    channel_menu_state: str,
    channel_id: str | None = None,
):
    """Render full details for one required channel."""
    query = update.callback_query
    await query.answer()

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"

    if not channel_id:
        channel_id = query.data.split("_")[2]
    db = context.bot_data["database"]
    channel = await db.cms.get_channel_by_id(channel_id)
    if not channel:
        await query.answer(t("admin.channels.not_found", lang), show_alert=True)
        return await channel_management_menu(update, context)

    is_active = channel.get("is_active", True)
    status_emoji = "✅" if is_active else "❌"
    status_text = (
        t("admin.channels.status.active", lang)
        if is_active
        else t("admin.channels.status.inactive", lang)
    )
    message = (
        t("admin.channels.details.title", lang)
        + "\n\n"
        + t("admin.channels.details.name", lang, title=channel["title"])
        + "\n"
        + t("admin.channels.details.id", lang, id=channel["channel_id"])
        + "\n"
        + t("admin.channels.details.url", lang, url=channel["url"])
        + "\n"
        + t(
            "admin.channels.details.status",
            lang,
            emoji=status_emoji,
            status=status_text,
        )
        + "\n"
    )

    toggle_emoji = "🔴" if is_active else "🟢"
    toggle_text = (
        t("admin.channels.buttons.toggle_deactivate", lang)
        if is_active
        else t("admin.channels.buttons.toggle_activate", lang)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                f"{toggle_emoji} {toggle_text}",
                callback_data=f"toggle_channel_{channel_id}",
            )
        ],
        [
            InlineKeyboardButton(
                t("admin.channels.buttons.stats", lang),
                callback_data=f"channel_stat_{channel_id}",
            ),
            InlineKeyboardButton(
                t("admin.channels.buttons.test", lang),
                callback_data=f"test_channel_{channel_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                t("menu.buttons.back", lang), callback_data="channel_menu"
            )
        ],
    ]
    await safe_edit_message_text(
        query, message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    return channel_menu_state


async def toggle_channel_status_impl(
    update: Update,
    context: CustomContext,
    view_channel_details: Callable[..., Awaitable[Any]],
    channel_menu_state: str,
):
    """Toggle channel active status and refresh channel details."""
    query = update.callback_query
    await query.answer()

    channel_id = "_".join(query.data.split("_")[2:])
    db = context.bot_data["database"]

    if await db.cms.toggle_channel_status(channel_id):
        from managers.channel_manager import invalidate_all_cache

        cleared_count = invalidate_all_cache()
        logger.info(
            "[channel] Cleared membership cache for %s users after toggling channel status",
            cleared_count,
        )
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.toggled", lang), show_alert=True)
        return await view_channel_details(update, context, channel_id=channel_id)

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    await query.answer(t("admin.channels.toggle_error", lang), show_alert=True)
    return channel_menu_state
