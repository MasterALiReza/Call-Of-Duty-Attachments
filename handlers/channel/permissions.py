"""Permission helpers for channel management."""

from __future__ import annotations

from typing import cast

from core.context import CustomContext
from core.database.database_pg import DatabasePostgres
from core.security.role_manager import RoleManager


async def check_channel_management_permission_impl(user_id: int, context: CustomContext) -> bool:
    """Check if a user can manage channels using RBAC with safe fallbacks."""
    from core.security.role_manager import Permission

    role_manager = context.bot_data.get("role_manager")
    if not role_manager:
        db = context.bot_data.get("database")
        if db:
            return bool(await cast(DatabasePostgres, db).users.is_admin(user_id))

        from config import SUPER_ADMIN_ID

        return user_id == int(SUPER_ADMIN_ID)

    typed_role_manager = cast(RoleManager, role_manager)

    if bool(await typed_role_manager.is_super_admin(user_id)):
        return True

    return bool(await typed_role_manager.has_permission(user_id, Permission.MANAGE_SETTINGS))
