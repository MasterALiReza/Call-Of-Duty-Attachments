"""Navigation routing helpers for modular admin handlers."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from telegram import Update

from core.context import CustomContext


async def handle_admin_navigation_back(
    handler: Any,
    update: Update,
    context: CustomContext,
    fallback: Callable[[Update, CustomContext], Awaitable[Any]],
):
    """Route nav_back to the active sub-flow handler based on context flags."""
    if "cat_mgmt_mode" in context.user_data:
        return await handler.category_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["add_att_mode", "add_att_category", "add_att_weapon"]):
        return await handler.add_attachment_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["del_att_mode", "del_att_category", "del_att_weapon"]):
        return await handler.delete_attachment_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["edit_att_mode", "edit_att_category", "edit_att_weapon"]):
        return await handler.edit_attachment_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["set_top_mode", "set_top_category", "set_top_weapon"]):
        return await handler.top_attachments_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["weapon_mgmt_mode", "weapon_mgmt_category", "weapon_mgmt_weapon"]):
        return await handler.weapon_handler.handle_navigation_back(update, context)

    if any(key in context.user_data for key in ["suggested_mode", "suggested_category", "suggested_weapon"]):
        return await handler.suggested_attachments_handler.handle_navigation_back(update, context)

    return await fallback(update, context)
