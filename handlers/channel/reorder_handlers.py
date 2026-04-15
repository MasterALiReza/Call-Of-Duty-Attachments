"""Channel reorder handlers extracted from channel_handlers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from core.context import CustomContext
from utils.i18n import t
from utils.language import get_user_lang

logger = logging.getLogger(__name__)


async def reorder_channels_menu_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    reorder_state: str,
):
    """Render channel reorder UI with up/down controls."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["database"]
    channels = await db.cms.get_required_channels()

    try:
        lang = await get_user_lang(update, context, db) or "fa"
    except Exception:
        lang = "fa"
    if not channels:
        await query.answer(t("admin.channels.reorder.none", lang), show_alert=True)
        return await channel_management_menu(update, context)

    keyboard = []
    keyboard.append([InlineKeyboardButton(t("admin.channels.reorder.title", lang), callback_data="noop")])

    for idx, channel in enumerate(channels):
        row = []
        if idx > 0:
            row.append(InlineKeyboardButton("⬆️", callback_data=f"move_up_{channel['channel_id']}"))
        else:
            row.append(InlineKeyboardButton("  ", callback_data="noop"))

        row.append(InlineKeyboardButton(f"{idx + 1}. {channel['title']}", callback_data="noop"))

        if idx < len(channels) - 1:
            row.append(InlineKeyboardButton("⬇️", callback_data=f"move_down_{channel['channel_id']}"))
        else:
            row.append(InlineKeyboardButton("  ", callback_data="noop"))

        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(t("admin.channels.reorder.confirm", lang), callback_data="channel_menu")])

    await query.edit_message_text(
        t("admin.channels.reorder.title", lang) + "\n\n" + t("admin.channels.reorder.instructions", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return reorder_state


async def handle_move_channel_impl(
    update: Update,
    context: CustomContext,
    reorder_channels_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    reorder_state: str,
):
    """Move channel priority up or down and refresh reorder UI."""
    query = update.callback_query
    parts = query.data.split("_")
    if len(parts) < 3:
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.reorder.invalid_operation", lang), show_alert=True)
        return reorder_state

    action = "_".join(parts[:2])
    channel_id = "_".join(parts[2:])
    db = context.bot_data["database"]

    if action == "move_up":
        success = await db.cms.move_channel_up(channel_id)
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        message = t("admin.channels.reorder.moved_up", lang) if success else t("admin.channels.reorder.move_up_failed", lang)
    elif action == "move_down":
        success = await db.cms.move_channel_down(channel_id)
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        message = t("admin.channels.reorder.moved_down", lang) if success else t("admin.channels.reorder.move_down_failed", lang)
    else:
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.reorder.invalid_operation", lang), show_alert=True)
        return reorder_state

    await query.answer(message)
    if success:
        from managers.channel_manager import invalidate_all_cache

        cleared_count = invalidate_all_cache()
        logger.info("[channel] Cleared membership cache for %s users after reordering", cleared_count)

    return await reorder_channels_menu(update, context)
