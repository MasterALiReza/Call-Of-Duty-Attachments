"""Navigation-related channel handlers extracted from channel_handlers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from core.context import CustomContext

logger = logging.getLogger(__name__)


async def cancel_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    get_lang: Callable[[Update, CustomContext, Any], Awaitable[str | None]],
    translate: Callable[..., str],
):
    """Return to channel menu from any intermediate state."""
    try:
        lang = await get_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception:
        lang = "fa"

    query = getattr(update, "callback_query", None)
    if query:
        try:
            await query.answer()
        except Exception:
            pass
        return await channel_management_menu(update, context)

    message = getattr(update, "message", None)
    if message:
        try:
            await message.reply_text(translate("menu.buttons.back", lang))
        except Exception:
            pass
        return await channel_management_menu(update, context)

    return ConversationHandler.END


async def return_to_admin_menu_impl(
    update: Update,
    context: CustomContext,
    admin_handlers_cls: type,
    get_lang: Callable[[Update, CustomContext, Any], Awaitable[str | None]],
    translate: Callable[..., str],
):
    """Leave channel conversation and return to main admin panel."""
    logger.info(
        "[channel] Return to admin clicked by user=%s", update.effective_user.id
    )
    query = update.callback_query
    await query.answer()

    context.user_data.pop("temp_channel", None)
    context.user_data.pop("editing_channel_id", None)
    context.user_data.pop("editing_field", None)
    context.user_data.pop("deleting_channel_id", None)
    context.user_data.pop("return_to_admin", None)

    db = context.bot_data["database"]
    admin_handler = admin_handlers_cls(db)
    lang = await get_lang(update, context, db) or "fa"
    keyboard = await admin_handler._get_admin_main_keyboard(
        update.effective_user.id, lang
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        translate("admin.panel.welcome", lang),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return ConversationHandler.END
