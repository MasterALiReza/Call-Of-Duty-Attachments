"""Channel delete-flow handlers extracted from management_actions."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from core.context import CustomContext
from utils.analytics_pg import AnalyticsPostgres as Analytics
from utils.i18n import t
from utils.language import get_user_lang
from utils.logger import log_exception
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def delete_channel_start_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    delete_state: str,
):
    """Start delete-channel flow with channel picker."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["database"]
    channels = await db.cms.get_required_channels()
    if not channels:
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.delete.none", lang), show_alert=True)
        return await channel_management_menu(update, context)

    keyboard = []
    for channel in channels:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🗑 {channel['title']}",
                    callback_data=f"del_confirm_{channel['channel_id']}",
                )
            ]
        )
    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    keyboard.append(
        [
            InlineKeyboardButton(
                t("menu.buttons.back", lang), callback_data="channel_menu"
            )
        ]
    )

    await safe_edit_message_text(
        query,
        t("admin.channels.delete.title", lang)
        + "\n\n"
        + t("admin.channels.delete.prompt", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return delete_state


async def delete_channel_confirm_impl(
    update: Update, context: CustomContext, delete_state: str
):
    """Confirm delete intent for selected channel."""
    query = update.callback_query
    await query.answer()

    channel_id = query.data.split("_")[2]
    context.user_data["deleting_channel_id"] = channel_id

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    keyboard = [
        [
            InlineKeyboardButton(
                t("admin.channels.delete.confirm_yes", lang), callback_data="del_yes"
            ),
            InlineKeyboardButton(
                t("menu.buttons.cancel", lang), callback_data="channel_menu"
            ),
        ]
    ]
    await safe_edit_message_text(
        query,
        t("admin.channels.delete.confirm", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return delete_state


async def delete_channel_execute_impl(
    update: Update, context: CustomContext, channel_menu_state: str
):
    """Execute channel deletion after confirmation."""
    query = update.callback_query
    await query.answer()

    channel_id = context.user_data.get("deleting_channel_id")
    if not channel_id:
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        await query.answer(
            t("admin.channels.errors.missing_temp", lang), show_alert=True
        )
        return ConversationHandler.END

    db = context.bot_data["database"]
    success = await db.cms.remove_required_channel(channel_id)

    if success:
        from managers.channel_manager import invalidate_all_cache

        cleared_count = invalidate_all_cache()
        logger.info(
            "[channel] Cleared membership cache for %s users after removing channel",
            cleared_count,
        )

        try:
            analytics = Analytics()
            await analytics.track_channel_removed(
                channel_id=channel_id, admin_id=update.effective_user.id
            )
        except Exception as e:
            logger.error("[Analytics] Error tracking channel removed: %s", e)
            log_exception(
                logger,
                e,
                str({"channel_id": channel_id, "admin_id": update.effective_user.id}),
            )

        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        message = t("admin.channels.delete.success", lang)
    else:
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        message = t("admin.channels.delete.error", lang)

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

    context.user_data.pop("deleting_channel_id", None)
    return channel_menu_state
