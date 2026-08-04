"""Channel diagnostics handlers extracted from stats_handlers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from core.context import CustomContext
from utils.i18n import t
from utils.language import get_user_lang
from utils.telegram_safety import safe_edit_message_text

logger = logging.getLogger(__name__)


async def test_channel_access_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext], Awaitable[Any]],
    channel_menu_state: str,
):
    """Run a diagnostic check for bot access to a required channel."""
    query = update.callback_query
    try:
        lang = (
            await get_user_lang(update, context, context.bot_data.get("database"))
            or "fa"
        )
    except Exception:
        lang = "fa"
    await query.answer(t("admin.channels.test.running", lang))

    channel_id = "_".join(query.data.split("_")[2:])
    db = context.bot_data["database"]
    channels = await db.cms.get_required_channels()
    channel = next((ch for ch in channels if ch["channel_id"] == channel_id), None)

    if not channel:
        try:
            lang = (
                await get_user_lang(update, context, context.bot_data.get("database"))
                or "fa"
            )
        except Exception:
            lang = "fa"
        await query.answer(t("admin.channels.not_found", lang), show_alert=True)
        return await channel_management_menu(update, context)

    test_results: list[str] = []
    test_results.append(t("admin.channels.test.header", lang))
    test_results.append(
        t("admin.channels.test.channel_title", lang, title=channel["title"])
    )

    try:
        chat = await context.bot.get_chat(channel_id)
        test_results.append(t("admin.channels.test.step1.channel_found", lang))
        test_results.append(t("admin.channels.test.step1.type", lang, type=chat.type))
        test_results.append(t("admin.channels.test.step1.name", lang, name=chat.title))

        try:
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)

            if bot_member.status in ["administrator", "creator"]:
                test_results.append(t("admin.channels.test.step2.bot_is_admin", lang))
                test_results.append(
                    t("admin.channels.test.step2.role", lang, role=bot_member.status)
                )

                if hasattr(bot_member, "can_post_messages"):
                    if bot_member.can_post_messages:
                        test_results.append(
                            t("admin.channels.test.step2.can_post_true", lang)
                        )
                    else:
                        test_results.append(
                            t("admin.channels.test.step2.can_post_false", lang)
                        )

                if (
                    hasattr(bot_member, "can_invite_users")
                    and bot_member.can_invite_users
                ):
                    test_results.append(
                        t("admin.channels.test.step2.can_invite_true", lang)
                    )
            else:
                test_results.append(
                    t(
                        "admin.channels.test.step2.not_admin",
                        lang,
                        role=bot_member.status,
                    )
                )
                test_results.append(t("admin.channels.test.step2.must_be_admin", lang))

        except Exception as e:
            test_results.append(t("admin.channels.test.step2.error_check", lang))
            test_results.append(t("admin.channels.test.error_detail", lang, err=str(e)))

        test_results.append(t("admin.channels.test.step3.header", lang))
        if channel["url"].startswith("https://t.me/"):
            test_results.append(t("admin.channels.test.step3.link_ok", lang))

            username = channel["url"].replace("https://t.me/", "").split("?")[0]
            if username.startswith("+"):
                test_results.append(t("admin.channels.test.step3.link_private", lang))
            else:
                test_results.append(
                    t(
                        "admin.channels.test.step3.link_public_user",
                        lang,
                        username=username,
                    )
                )
        else:
            test_results.append(t("admin.channels.test.step3.link_invalid", lang))

        try:
            member_count = await context.bot.get_chat_member_count(channel_id)
            test_results.append(
                t(
                    "admin.channels.test.step4.members_count",
                    lang,
                    n=f"{member_count:,}",
                )
            )
        except Exception as e:
            logger.warning(
                "[channel] Failed to get member count for %s: %s", channel_id, e
            )

        test_results.append(t("admin.channels.test.summary.success", lang))

    except Exception as e:
        error_type = type(e).__name__
        test_results.append(t("admin.channels.test.step1.error_access", lang))
        test_results.append(t("admin.channels.test.error_type", lang, type=error_type))
        test_results.append(t("admin.channels.test.error_message", lang, msg=str(e)))
        test_results.append(t("admin.channels.test.suggestions.header", lang))
        test_results.append(t("admin.channels.test.suggestions.check_id", lang))
        test_results.append(t("admin.channels.test.suggestions.bot_admin", lang))
        test_results.append(t("admin.channels.test.suggestions.channel_active", lang))

    keyboard = [
        [
            InlineKeyboardButton(
                t("menu.buttons.back", lang), callback_data=f"view_channel_{channel_id}"
            )
        ]
    ]
    await safe_edit_message_text(
        query,
        "\n".join(test_results),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return channel_menu_state
