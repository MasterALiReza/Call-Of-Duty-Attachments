"""Channel add-flow handlers extracted from management_actions."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler

from core.context import CustomContext
from utils.analytics_pg import AnalyticsPostgres as Analytics
from utils.i18n import t
from utils.language import get_user_lang
from utils.logger import log_exception
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def add_channel_start_impl(
    update: Update, context: CustomContext, add_channel_id_state: str
):
    """Start add-channel flow."""
    query = update.callback_query
    await query.answer()

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    message = (
        t("admin.channels.add.title", lang)
        + "\n\n"
        + t("admin.channels.add.prompt_id", lang)
        + "\n"
        + t("admin.channels.add.example_id", lang)
        + "\n\n"
        + t("admin.channels.add.note_bot_admin", lang)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.cancel", lang), callback_data="channel_menu"
            )
        ]
    ]
    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    return add_channel_id_state


async def add_channel_id_impl(
    update: Update,
    context: CustomContext,
    add_channel_id_state: str,
    add_channel_title_state: str,
):
    """Receive and validate channel id/username."""
    if not update.message or not update.message.text:
        return add_channel_id_state

    channel_id = update.message.text.strip()
    logger.info(
        "[channel] Received channel ID: %s from user=%s",
        channel_id,
        update.effective_user.id,
    )

    if "t.me/" in channel_id:
        clean_id = channel_id.replace("https://", "").replace("http://", "")
        parts = [part for part in clean_id.split("/") if part]
        if parts:
            possible_username = parts[-1]
            if (
                not possible_username.startswith("+")
                and possible_username != "joinchat"
            ):
                channel_id = f"@{possible_username}"
                logger.info("[channel] Extracted username from URL: %s", channel_id)

    from utils.validators import validate_channel_id

    is_valid, error_or_value = validate_channel_id(channel_id)
    if not is_valid:
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
                    t("menu.buttons.cancel", lang), callback_data="channel_menu"
                )
            ]
        ]
        await update.message.reply_text(
            f"❌ {error_or_value}", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return add_channel_id_state

    channel_id = error_or_value
    try:
        chat = await context.bot.get_chat(channel_id)
        channel_title = chat.title
        context.user_data["temp_channel"] = {
            "channel_id": str(chat.id),
            "title": channel_title,
        }
        logger.info(
            "[channel] Successfully verified channel %s (%s)", channel_title, chat.id
        )

        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        message = (
            t("admin.channels.add.found", lang, title=channel_title)
            + "\n\n"
            + t("admin.channels.add.prompt_title", lang)
            + "\n"
            + t("admin.channels.add.default_title_label", lang, title=channel_title)
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    t("admin.channels.use_default_title", lang),
                    callback_data="use_default_title",
                )
            ],
            [
                InlineKeyboardButton(
                    t("menu.buttons.cancel", lang), callback_data="channel_menu"
                )
            ],
        ]
        await update.message.reply_text(
            message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
        return add_channel_title_state
    except Exception as e:
        logger.error("[channel] Error accessing channel %s: %s", channel_id, e)
        log_exception(
            logger,
            e,
            str({"channel_id": channel_id, "user_id": update.effective_user.id}),
        )
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
                    t("menu.buttons.back", lang), callback_data="channel_menu"
                )
            ]
        ]
        await update.message.reply_text(
            t("admin.channels.errors.access_channel", lang, err=str(e)),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return add_channel_id_state


async def use_default_title_impl(
    update: Update, context: CustomContext, add_channel_url_state: str
):
    """Keep Telegram title as display title and move to URL step."""
    query = update.callback_query
    await query.answer()

    temp_channel = context.user_data.get("temp_channel")
    if not temp_channel:
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        await safe_edit_message_text(
            query, t("admin.channels.errors.missing_temp", lang)
        )
        return ConversationHandler.END

    context.user_data["temp_channel"]["display_title"] = temp_channel["title"]
    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    message = (
        t("admin.channels.add.url.title", lang)
        + "\n\n"
        + t("admin.channels.add.url.prompt", lang)
        + "\n"
        + t("admin.channels.add.url.example", lang)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.cancel", lang), callback_data="channel_menu"
            )
        ]
    ]
    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    return add_channel_url_state


async def add_channel_title_impl(
    update: Update,
    context: CustomContext,
    add_channel_title_state: str,
    add_channel_url_state: str,
):
    """Receive custom display title."""
    if not update.message or not update.message.text:
        return add_channel_title_state

    title = update.message.text.strip()
    logger.info(
        "[channel] Received channel title: %s from user=%s",
        title,
        update.effective_user.id,
    )
    if not title:
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
                    t("menu.buttons.cancel", lang), callback_data="channel_menu"
                )
            ]
        ]
        await update.message.reply_text(
            t("admin.channels.errors.empty_title", lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return add_channel_title_state

    context.user_data["temp_channel"]["display_title"] = title

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    message = (
        t("admin.channels.add.url.title", lang)
        + "\n\n"
        + t("admin.channels.add.url.prompt", lang)
        + "\n"
        + t("admin.channels.add.url.example", lang)
    )
    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.cancel", lang), callback_data="channel_menu"
            )
        ]
    ]
    await update.message.reply_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    return add_channel_url_state


async def add_channel_url_impl(
    update: Update,
    context: CustomContext,
    add_channel_url_state: str,
    add_channel_confirm_state: str,
):
    """Receive channel URL and render confirmation."""
    if not update.message or not update.message.text:
        return add_channel_url_state

    url = update.message.text.strip()
    logger.info(
        "[channel] Received channel URL: %s from user=%s", url, update.effective_user.id
    )

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    if not url.startswith("https://t.me/"):
        keyboard = [
            [
                InlineKeyboardButton(
                    t("menu.buttons.cancel", lang), callback_data="channel_menu"
                )
            ]
        ]
        await update.message.reply_text(
            t("admin.channels.errors.invalid_link", lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return add_channel_url_state

    temp_channel = context.user_data.get("temp_channel")
    if not temp_channel:
        await update.message.reply_text(t("admin.channels.errors.missing_temp", lang))
        return ConversationHandler.END

    context.user_data["temp_channel"]["url"] = url
    message = (
        t("admin.channels.add.confirm.title", lang)
        + "\n\n"
        + t(
            "admin.channels.add.confirm.body",
            lang,
            title=temp_channel["display_title"],
            url=url,
            id=temp_channel["channel_id"],
        )
    )
    keyboard = [
        [
            InlineKeyboardButton(
                t("admin.channels.add.confirm.save", lang), callback_data="save_channel"
            )
        ],
        [
            InlineKeyboardButton(
                t("admin.channels.add.confirm.edit", lang), callback_data="add_channel"
            )
        ],
        [
            InlineKeyboardButton(
                t("admin.channels.add.confirm.cancel", lang),
                callback_data="channel_menu",
            )
        ],
    ]
    await update.message.reply_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    return add_channel_confirm_state


async def save_channel_confirm_impl(
    update: Update, context: CustomContext, channel_menu_state: str
):
    """Persist confirmed channel and clear temp state."""
    query = update.callback_query
    await query.answer()

    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    temp_channel = context.user_data.get("temp_channel")
    if not temp_channel or "url" not in temp_channel:
        await safe_edit_message_text(
            query, t("admin.channels.errors.missing_temp", lang)
        )
        return ConversationHandler.END

    db = context.bot_data["database"]
    success = await db.cms.add_required_channel(
        channel_id=temp_channel["channel_id"],
        title=temp_channel["display_title"],
        url=temp_channel["url"],
    )

    if success:
        logger.info(
            "[channel] Successfully added channel %s by user=%s",
            temp_channel["channel_id"],
            update.effective_user.id,
        )
        from managers.channel_manager import invalidate_all_cache

        cleared_count = invalidate_all_cache()
        logger.info(
            "[channel] Cleared membership cache for %s users after adding channel",
            cleared_count,
        )

        try:
            analytics = Analytics()
            await analytics.track_channel_added(
                channel_id=temp_channel["channel_id"],
                title=temp_channel["display_title"],
                url=temp_channel["url"],
                admin_id=update.effective_user.id,
            )
        except Exception as e:
            logger.error("[Analytics] Error tracking channel added: %s", e)
            log_exception(
                logger,
                e,
                str(
                    {
                        "channel_id": temp_channel["channel_id"],
                        "admin_id": update.effective_user.id,
                    }
                ),
            )
        message = t("admin.channels.add.success", lang)
    else:
        logger.error(
            "[channel] Failed to add channel %s - possibly duplicate",
            temp_channel["channel_id"],
        )
        message = t("admin.channels.add.save_error", lang)

    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.back", lang), callback_data="channel_menu"
            )
        ]
    ]
    await safe_edit_message_text(
        query, message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    context.user_data.pop("temp_channel", None)
    return channel_menu_state
