"""Shared RBAC helpers for user-attachments admin modules."""

from typing import Any, cast

from core.database.database_pg import DatabasePostgres

from core.audit import AuditLogger
from core.security.role_manager import Permission, RoleManager


async def has_manage_user_attachments_permission(
    user_id: int,
    *,
    db: Any,
    role_manager: RoleManager,
    audit_logger: AuditLogger | None = None,
    route: str = "user_attachments_admin",
    source: str = "user_attachments_admin",
) -> bool:
    """Allow SuperAdmin or users with MANAGE_USER_ATTACHMENTS permission."""
    try:
        if await role_manager.is_super_admin(user_id):
            return True
        allowed = bool(await role_manager.has_permission(user_id, Permission.MANAGE_USER_ATTACHMENTS))
        if not allowed and audit_logger is not None:
            await audit_logger.log_permission_decision(
                actor_id=user_id,
                permission=Permission.MANAGE_USER_ATTACHMENTS.name,
                allowed=False,
                route=route,
                reason="permission_denied",
                details={"source": source},
            )
        return bool(allowed)
    except Exception:
        # Legacy fallback while older admin checks still exist.
        allowed = bool(await cast(DatabasePostgres, db).users.is_admin(user_id))
        if not allowed and audit_logger is not None:
            await audit_logger.log_permission_decision(
                actor_id=user_id,
                permission=Permission.MANAGE_USER_ATTACHMENTS.name,
                allowed=False,
                route=route,
                reason="permission_fallback_denied",
                details={"source": source},
            )
        return bool(allowed)
