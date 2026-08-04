"""Channel menu handlers extracted from channel_handlers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from core.context import CustomContext
from handlers.channel.menu_helpers import build_channel_menu_view

logger = logging.getLogger(__name__)


async def channel_management_menu_impl(
    update: Update,
    context: CustomContext,
    page: int,
    check_permission: Callable[[int, CustomContext], Awaitable[bool]],
    audit_permission_denied: Callable[[int], Awaitable[None]],
    get_lang: Callable[[Update, CustomContext, Any], Awaitable[str | None]],
    translate: Callable[..., str],
    safe_edit: Callable[..., Awaitable[Any]],
    channels_per_page: int,
    channel_menu_state: str,
):
    """Render top-level channel management menu with pagination."""
    try:
        lang = await get_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"

    if not await check_permission(update.effective_user.id, context):
        try:
            await audit_permission_denied(update.effective_user.id)
        except Exception:
            logger.exception(
                "[channel] Failed to record permission deny for user=%s",
                update.effective_user.id,
            )
        query = update.callback_query
        if query:
            await query.answer(
                translate("admin.channels.permission_denied", lang), show_alert=True
            )
        else:
            try:
                await update.message.reply_text(
                    translate("admin.channels.permission_denied", lang)
                )
            except Exception:
                pass
        return ConversationHandler.END

    logger.info(
        "[channel] Open menu by user=%s, page=%d", update.effective_user.id, page
    )
    query = update.callback_query
    if query:
        await query.answer()

    db = context.bot_data["database"]
    try:
        lang = await get_lang(update, context, db) or lang
    except Exception:
        pass
    all_channels = await db.cms.get_required_channels()

    keyboard, message = build_channel_menu_view(
        all_channels=all_channels,
        page=page,
        per_page=channels_per_page,
        lang=lang,
        translate=translate,
    )

    if query:
        await safe_edit(
            query,
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    return channel_menu_state
