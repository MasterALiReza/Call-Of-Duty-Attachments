"""Channel edit-flow handlers extracted from management_actions."""

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


async def edit_channel_start_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    edit_select_state: str,
):
    """Start edit flow by listing channels."""
    query = update.callback_query
    await query.answer()

    db = context.bot_data["database"]
    channels = await db.cms.get_required_channels()
    if not channels:
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.edit.none", lang), show_alert=True)
        return await channel_management_menu(update, context)

    keyboard = []
    for channel in channels:
        keyboard.append([
            InlineKeyboardButton(f"📢 {channel['title']}", callback_data=f"edit_select_{channel['channel_id']}")
        ])

    try:
        lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="channel_menu")])

    await safe_edit_message_text(
        query,
        t("admin.channels.edit.title", lang) + "\n\n" + t("admin.channels.edit.prompt", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return edit_select_state


async def edit_channel_select_impl(update: Update, context: CustomContext, edit_field_state: str):
    """Select editable field for chosen channel."""
    query = update.callback_query
    await query.answer()

    channel_id = query.data.split("_")[2]
    context.user_data["editing_channel_id"] = channel_id

    try:
        lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"
    keyboard = [
        [InlineKeyboardButton(t("admin.channels.buttons.edit_title", lang), callback_data="edit_field_title")],
        [InlineKeyboardButton(t("admin.channels.buttons.edit_url", lang), callback_data="edit_field_url")],
        [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="edit_channel")],
    ]

    await safe_edit_message_text(
        query,
        t("admin.channels.edit.choose_field", lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return edit_field_state


async def edit_channel_field_impl(update: Update, context: CustomContext, edit_value_state: str):
    """Prompt for updated field value."""
    query = update.callback_query
    await query.answer()

    field = query.data.split("_")[2]
    context.user_data["editing_field"] = field

    try:
        lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"
    message = t("admin.channels.edit.prompt_title", lang) if field == "title" else t("admin.channels.edit.prompt_url", lang)
    keyboard = [[InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="channel_menu")]]
    await safe_edit_message_text(query, message, reply_markup=InlineKeyboardMarkup(keyboard))
    return edit_value_state


async def edit_channel_value_impl(
    update: Update,
    context: CustomContext,
    edit_value_state: str,
    channel_menu_state: str,
):
    """Persist edited title/url and return to menu."""
    if not update.message or not update.message.text:
        return edit_value_state

    value = update.message.text.strip()
    channel_id = context.user_data.get("editing_channel_id")
    field = context.user_data.get("editing_field")

    if not channel_id or not field:
        try:
            lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
        except Exception:
            lang = "fa"
        await update.message.reply_text(t("admin.channels.errors.missing_edit", lang))
        return ConversationHandler.END

    db = context.bot_data["database"]
    if field == "title":
        success = await db.cms.update_required_channel(channel_id, title=value)
        if success:
            try:
                analytics = Analytics()
                await analytics.track_channel_updated(channel_id=channel_id, admin_id=update.effective_user.id, title=value)
            except Exception as e:
                logger.error("[Analytics] Error tracking channel update: %s", e)
                log_exception(logger, e, str({"channel_id": channel_id, "admin_id": update.effective_user.id}))
    else:
        if not value.startswith("https://t.me/"):
            try:
                lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
            except Exception:
                lang = "fa"
            await update.message.reply_text(t("admin.channels.errors.invalid_link", lang))
            return edit_value_state
        success = await db.cms.update_required_channel(channel_id, url=value)
        if success:
            try:
                analytics = Analytics()
                await analytics.track_channel_updated(channel_id=channel_id, admin_id=update.effective_user.id, url=value)
            except Exception as e:
                logger.error("[Analytics] Error tracking channel update: %s", e)
                log_exception(logger, e, str({"channel_id": channel_id, "admin_id": update.effective_user.id}))

    try:
        lang = await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"
    message = t("admin.channels.edit.success", lang) if success else t("admin.channels.edit.error", lang)
    keyboard = [[InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="channel_menu")]]
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

    context.user_data.pop("editing_channel_id", None)
    context.user_data.pop("editing_field", None)
    return channel_menu_state
