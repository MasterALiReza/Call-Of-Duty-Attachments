"""Admin entry/exit flow helpers extracted from admin_handlers_modular."""

from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from core.context import CustomContext
from utils.i18n import t
from utils.language import get_user_lang
from utils.logger import get_logger

logger = get_logger("admin_modular", "admin.log")


def _clear_admin_entry_context(handler: Any, context: CustomContext) -> None:
    handler._clear_navigation(context)
    handler._clear_temp_data(context)

    keys_to_clear = [
        key
        for key in list(context.user_data.keys())
        if key.startswith(
            (
                "admin_",
                "edit_",
                "add_",
                "del_",
                "set_",
                "notif_",
                "guide_",
                "text_",
                "tmpl_",
                "faq_",
                "ticket_",
                "cms_",
                "cat_",
                "weapon_",
                "suggested_",
                "health_",
                "import_",
                "export_",
                "ua_",
                "nav_",
                "search_",
            )
        )
    ]
    for key in keys_to_clear:
        context.user_data.pop(key, None)
    context.user_data.pop("admin_entry_handled", None)


async def run_admin_start(handler: Any, update: Update, context: CustomContext):
    user_id = update.effective_user.id
    if not await handler.is_admin(user_id):
        await handler.audit_permission_denied(
            user_id,
            route="admin_start",
            permission="ADMIN_ACCESS",
            source="admin_start",
        )
        lang = await get_user_lang(update, context, handler.db) or "fa"
        if update.callback_query:
            await update.callback_query.answer(t("admin.not_admin", lang))
            await update.callback_query.edit_message_text(t("admin.not_admin", lang))
        else:
            await update.message.reply_text(t("admin.not_admin", lang))
        return ConversationHandler.END

    _clear_admin_entry_context(handler, context)

    lang = await get_user_lang(update, context, handler.db) or "fa"
    keyboard = await handler._get_admin_main_keyboard(user_id, lang)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            t("admin.panel.welcome", lang),
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            t("admin.panel.welcome", lang),
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    from handlers.admin.admin_states import ADMIN_MENU

    return ADMIN_MENU


async def run_admin_start_msg(handler: Any, update: Update, context: CustomContext):
    user_id = update.effective_user.id
    if not await handler.is_admin(user_id):
        await handler.audit_permission_denied(
            user_id,
            route="admin_start_msg",
            permission="ADMIN_ACCESS",
            source="admin_start_msg",
        )
        lang = await get_user_lang(update, context, handler.db) or "fa"
        await update.message.reply_text(t("admin.not_admin", lang))
        return ConversationHandler.END

    handler._clear_navigation(context)

    lang = await get_user_lang(update, context, handler.db) or "fa"
    keyboard = await handler._get_admin_main_keyboard(user_id, lang)
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        t("admin.panel.welcome", lang),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    from handlers.admin.admin_states import ADMIN_MENU

    return ADMIN_MENU


async def run_admin_cancel(handler: Any, update: Update, context: CustomContext):
    query = update.callback_query
    if query:
        await query.answer()
    return await handler.admin_menu_return(update, context)


async def run_search_cancel_and_admin(handler: Any, update: Update, context: CustomContext):
    user_id = update.effective_user.id
    if await handler.is_admin(user_id):
        await handler.admin_start_msg(update, context)
    else:
        lang = await get_user_lang(update, context, handler.db) or "fa"
        await update.message.reply_text(t("admin.not_admin", lang))
    return ConversationHandler.END


async def run_admin_exit_silent(handler: Any, update: Update, context: CustomContext):
    logger.info("[ADMIN_EXIT_SILENT] User %s exiting admin", update.effective_user.id)
    handler._clear_navigation(context)
    handler._clear_temp_data(context)
    return ConversationHandler.END
