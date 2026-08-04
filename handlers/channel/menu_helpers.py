"""Shared helpers for channel management menu flows."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, Update

from core.context import CustomContext


def paginate_list(items: list, page: int, per_page: int) -> tuple:
    """Paginate items and return view metadata."""
    total_items = len(items)
    total_pages = (total_items + per_page - 1) // per_page

    page = max(1, min(page, total_pages if total_pages > 0 else 1))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    items_in_page = items[start_idx:end_idx]
    has_prev = page > 1
    has_next = page < total_pages
    return items_in_page, total_pages, has_prev, has_next


async def noop_cb_impl(update: Update, context: CustomContext):
    """Answer no-op callback buttons to prevent client timeout."""
    del context
    try:
        await update.callback_query.answer()
    except Exception:
        pass


async def handle_page_navigation_impl(
    update: Update,
    context: CustomContext,
    channel_management_menu: Callable[[Update, CustomContext, int], Awaitable[Any]],
):
    """Extract page from callback payload and render target page."""
    query = update.callback_query
    page = int(query.data.split("_")[2])
    return await channel_management_menu(update, context, page)


def build_channel_menu_view(
    all_channels: list[dict[str, Any]],
    page: int,
    per_page: int,
    lang: str,
    translate: Callable[..., str],
) -> tuple[list[list[InlineKeyboardButton]], str]:
    """Build channel menu keyboard and text for a given page."""
    keyboard: list[list[InlineKeyboardButton]] = []
    channels: list[dict[str, Any]] = []
    total_pages = 0

    if all_channels:
        channels, total_pages, has_prev, has_next = paginate_list(
            all_channels, page, per_page
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    translate(
                        "admin.channels.pagination.header",
                        lang,
                        page=page,
                        total=total_pages,
                    ),
                    callback_data="noop",
                )
            ]
        )

        for channel in channels:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📢 {channel['title']}",
                        callback_data=f"view_channel_{channel['channel_id']}",
                    )
                ]
            )

        if total_pages > 1:
            nav_buttons: list[InlineKeyboardButton] = []
            if has_prev:
                nav_buttons.append(
                    InlineKeyboardButton(
                        translate("nav.prev", lang),
                        callback_data=f"ch_page_{page - 1}",
                    )
                )

            nav_buttons.append(
                InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop")
            )

            if has_next:
                nav_buttons.append(
                    InlineKeyboardButton(
                        translate("nav.next", lang),
                        callback_data=f"ch_page_{page + 1}",
                    )
                )
            keyboard.append(nav_buttons)

    keyboard.append(
        [
            InlineKeyboardButton(
                translate("admin.channels.buttons.add", lang),
                callback_data="add_channel",
            )
        ]
    )

    if channels:
        keyboard.append(
            [
                InlineKeyboardButton(
                    translate("admin.channels.buttons.edit", lang),
                    callback_data="edit_channel",
                ),
                InlineKeyboardButton(
                    translate("admin.channels.buttons.delete", lang),
                    callback_data="delete_channel",
                ),
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    translate("admin.channels.buttons.reorder", lang),
                    callback_data="reorder_channels",
                ),
                InlineKeyboardButton(
                    translate("admin.channels.buttons.clear_all", lang),
                    callback_data="clear_channels",
                ),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                translate("menu.buttons.back", lang), callback_data="ch_admin_return"
            )
        ]
    )

    message = translate("admin.channels.menu.title", lang) + "\n\n"
    if all_channels:
        message += (
            translate("admin.channels.menu.total", lang, n=len(all_channels)) + "\n"
        )

        if total_pages > 1:
            start_num = (page - 1) * per_page + 1
            end_num = min(page * per_page, len(all_channels))
            message += (
                translate(
                    "pagination.showing_range",
                    lang,
                    start=start_num,
                    end=end_num,
                    total=len(all_channels),
                )
                + "\n"
            )

        message += "\n" + translate("admin.channels.menu.hint_click", lang) + "\n"
        message += translate("admin.channels.menu.hint_membership", lang)
    else:
        message += translate("admin.channels.menu.empty", lang) + "\n\n"
        message += translate("admin.channels.menu.empty_hint", lang)

    return keyboard, message
