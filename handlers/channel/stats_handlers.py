"""Channel analytics/statistics handlers extracted from channel_handlers."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from core.context import CustomContext
from core.errors import InfrastructureError
from utils.analytics_pg import AnalyticsPostgres as Analytics
from utils.i18n import t
from utils.language import get_user_lang
from utils.logger import log_exception
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def _resolve_lang(update: Update, context: CustomContext) -> str:
    try:
        return await get_user_lang(update, context, context.bot_data.get("database")) or "fa"
    except Exception as exc:
        logger.warning("[channel] Failed to resolve language: %s", exc)
        return "fa"


def _build_back_markup(label: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=callback_data)]])


def _format_added_at(added_at: object) -> str:
    if isinstance(added_at, datetime):
        return added_at.strftime("%Y/%m/%d - %H:%M")

    try:
        return datetime.fromisoformat(str(added_at)).strftime("%Y/%m/%d - %H:%M")
    except (TypeError, ValueError):
        return str(added_at)[:10]


async def _render_stats_error(
    query,
    *,
    lang: str,
    text: str,
    back_callback: str,
    back_label: str,
) -> None:
    await safe_edit_message_text(
        query,
        text,
        reply_markup=_build_back_markup(back_label, back_callback),
    )


async def show_single_channel_stats_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    channel_menu_state: str,
):
    """Display stats for a single required channel."""
    query = update.callback_query
    await query.answer()

    channel_id = "_".join(query.data.split("_")[2:])

    try:
        analytics = Analytics()
        db = context.bot_data["database"]
        lang = await _resolve_lang(update, context)
        channel = await db.cms.get_channel_by_id(channel_id)

        if not channel:
            await query.answer(t("admin.channels.not_found", lang), show_alert=True)
            return await channel_management_menu(update, context)

        stats = await analytics.get_channel_stats(channel_id)
        message = t("admin.channels.stats.single.title", lang, title=channel["title"]) + "\n\n"

        if not stats:
            message += t("admin.channels.stats.single.no_data", lang)
        else:
            message += t("admin.channels.stats.single.joins", lang, n=stats.get("total_joins", 0)) + "\n"
            message += t("admin.channels.stats.single.attempts", lang, n=stats.get("total_join_attempts", 0)) + "\n"
            message += t("admin.channels.stats.single.conversion", lang, rate=stats.get("conversion_rate", 0)) + "\n\n"

            added_at = stats.get("added_at")
            if added_at:
                message += t("admin.channels.stats.single.added_date", lang, date=_format_added_at(added_at)) + "\n"

            status = stats.get("status", "active")
            status_text = (
                t("admin.channels.status.active", lang)
                if status == "active"
                else t("admin.channels.status.deleted", lang)
            )
            status_emoji = "?" if status == "active" else "?"
            message += t("admin.channels.details.status", lang, emoji=status_emoji, status=status_text) + "\n"

        await safe_edit_message_text(
            query,
            message,
            parse_mode="HTML",
            reply_markup=_build_back_markup(t("menu.buttons.back", lang), f"view_channel_{channel_id}"),
        )
    except Exception as exc:
        logger.error("[channel] Error showing single channel stats: %s", exc)
        log_exception(logger, exc, str({"channel_id": channel_id}))
        lang = await _resolve_lang(update, context)
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.stats.error", lang, err=str(exc)),
            back_callback="channel_menu",
            back_label=t("menu.buttons.back", lang),
        )

    return channel_menu_state


async def show_channel_stats_impl(update: Update, context: CustomContext, channel_menu_state: str):
    """Display aggregated dashboard for all required channels."""
    query = update.callback_query
    await query.answer()

    try:
        analytics = Analytics()
        dashboard_text = await analytics.generate_admin_dashboard()
        lang = await _resolve_lang(update, context)
        keyboard = [
            [InlineKeyboardButton(t("admin.channels.stats.buttons.funnel", lang), callback_data="channel_funnel")],
            [InlineKeyboardButton(t("admin.channels.stats.buttons.period_report", lang), callback_data="channel_period_report")],
            [InlineKeyboardButton(t("admin.channels.stats.buttons.export_csv", lang), callback_data="channel_export_csv")],
            [InlineKeyboardButton(t("admin.channels.stats.buttons.history", lang), callback_data="channel_history")],
            [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="channel_menu")],
        ]

        await safe_edit_message_text(
            query,
            dashboard_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as exc:
        logger.error("[channel] Error showing channel stats: %s", exc)
        log_exception(logger, exc, str({"action": "show_channel_stats"}))
        lang = await _resolve_lang(update, context)
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.stats.error", lang, err=str(exc)),
            back_callback="channel_menu",
            back_label=t("menu.buttons.back", lang),
        )

    return channel_menu_state


async def show_funnel_analysis_impl(update: Update, context: CustomContext, channel_menu_state: str):
    """Display conversion funnel analytics."""
    query = update.callback_query
    await query.answer()

    try:
        analytics = Analytics()
        funnel_text = await analytics.generate_funnel_analysis()
        lang = await _resolve_lang(update, context)
        await safe_edit_message_text(
            query,
            funnel_text,
            parse_mode="HTML",
            reply_markup=_build_back_markup(t("admin.channels.history.back_to_stats", lang), "channel_stats"),
        )
    except Exception as exc:
        logger.error("[channel] Error showing funnel: %s", exc)
        log_exception(logger, exc, str({"action": "show_funnel_analysis"}))
        lang = await _resolve_lang(update, context)
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.funnel.error", lang),
            back_callback="channel_stats",
            back_label=t("admin.channels.history.back_to_stats", lang),
        )

    return channel_menu_state


async def show_period_report_impl(update: Update, context: CustomContext, channel_menu_state: str):
    """Display last-period analytics report."""
    query = update.callback_query
    await query.answer()

    try:
        analytics = Analytics()
        report_text = await analytics.generate_period_report()
        lang = await _resolve_lang(update, context)
        await safe_edit_message_text(
            query,
            report_text,
            parse_mode="HTML",
            reply_markup=_build_back_markup(t("admin.channels.history.back_to_stats", lang), "channel_stats"),
        )
    except Exception as exc:
        logger.error("[channel] Error showing period report: %s", exc)
        log_exception(logger, exc, str({"action": "show_period_report"}))
        lang = await _resolve_lang(update, context)
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.period.error", lang),
            back_callback="channel_stats",
            back_label=t("admin.channels.history.back_to_stats", lang),
        )

    return channel_menu_state


async def export_analytics_csv_impl(update: Update, context: CustomContext, channel_menu_state: str):
    """Export analytics as CSV files and send to admin."""
    query = update.callback_query
    lang = await _resolve_lang(update, context)
    await query.answer(t("admin.channels.export.creating", lang))

    try:
        analytics = Analytics()
        files = await analytics.export_to_csv("all")

        if not files:
            await safe_edit_message_text(
                query,
                t("admin.channels.export.no_files", lang),
                reply_markup=_build_back_markup(t("admin.channels.history.back_to_stats", lang), "channel_stats"),
            )
            return channel_menu_state

        await safe_edit_message_text(query, t("admin.channels.export.sending", lang, count=len(files)))

        for file_path in files:
            try:
                with open(file_path, "rb") as file_obj:
                    await query.message.reply_document(
                        document=file_obj,
                        filename=os.path.basename(file_path),
                        caption=f"CSV {os.path.basename(file_path)}",
                    )
            except OSError as exc:
                raise InfrastructureError(f"Unable to read analytics export file: {file_path}") from exc

        await query.message.reply_text(
            t("admin.channels.export.success", lang),
            reply_markup=_build_back_markup(t("admin.channels.history.back_to_stats", lang), "channel_stats"),
        )
    except Exception as exc:
        logger.error("[channel] Error exporting CSV: %s", exc)
        log_exception(logger, exc, str({"action": "export_analytics_csv"}))
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.export.error", lang),
            back_callback="channel_stats",
            back_label=t("admin.channels.history.back_to_stats", lang),
        )

    return channel_menu_state


async def show_channel_history_impl(update: Update, context: CustomContext, channel_menu_state: str):
    """Display removed-channel history report."""
    query = update.callback_query
    await query.answer()

    try:
        analytics = Analytics()
        history_text = await analytics.generate_channel_history_report()
        lang = await _resolve_lang(update, context)
        await safe_edit_message_text(
            query,
            history_text,
            parse_mode="HTML",
            reply_markup=_build_back_markup(t("admin.channels.history.back_to_stats", lang), "channel_stats"),
        )
    except Exception as exc:
        logger.error("[channel] Error showing channel history: %s", exc)
        log_exception(logger, exc, str({"action": "show_channel_history"}))
        lang = await _resolve_lang(update, context)
        await _render_stats_error(
            query,
            lang=lang,
            text=t("admin.channels.history.error", lang),
            back_callback="channel_stats",
            back_label=t("admin.channels.history.back_to_stats", lang),
        )

    return channel_menu_state
