import logging
from typing import Optional, Dict, Any
from core.database.database_adapter import get_database_adapter
from utils.logger import log_exception

logger = logging.getLogger("audit")

_audit_logger_instance = None


def get_audit_logger():
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


class AuditLogger:
    """Manages the creation and insertion of administrative audit logs."""

    def __init__(self):
        self.db = get_database_adapter()

    async def _execute(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> None:
        """Run audit SQL without relying on deprecated direct adapter query helpers."""
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params or ())
                await conn.commit()

    async def create_table_if_not_exists(self):
        """Creates the audit_logs table during initialization."""
        query = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            action VARCHAR(100) NOT NULL,
            target_id VARCHAR(100),
            details JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_audit_admin_id ON audit_logs(admin_id);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
        """
        try:
            await self._execute(query)
            logger.info("Audit logs table verified/created.")
        except Exception as e:
            log_exception(logger, e, "create_audit_table")

    async def log_action(
        self,
        admin_id: int,
        action: str,
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Records an action taken by an admin.

        Args:
            admin_id: Telegram ID of the administrator
            action: Action string identifier (e.g., 'ADD_WEAPON', 'BAN_USER')
            target_id: The ID of the item manipulated, if applicable
            details: JSON-serializable dictionary of additional context
        """
        import json

        query = """
            INSERT INTO audit_logs (admin_id, action, target_id, details)
            VALUES (%s, %s, %s, %s)
        """
        details_json = json.dumps(details, ensure_ascii=False) if details else None

        try:
            await self._execute(query, (admin_id, action, target_id, details_json))
            logger.debug(
                f"[Audit] Recorded block: Admin {admin_id} did {action} -> {target_id}"
            )
        except Exception as e:
            log_exception(logger, e, f"log_audit_action({admin_id}, {action})")

    async def log_permission_decision(
        self,
        actor_id: int,
        permission: str,
        allowed: bool,
        route: str,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an allow/deny permission decision with a stable action name."""
        payload: Dict[str, Any] = {
            "permission": permission,
            "allowed": allowed,
            "route": route,
        }
        if reason:
            payload["reason"] = reason
        if details:
            payload.update(details)

        await self.log_action(
            actor_id,
            "PERMISSION_DENIED" if not allowed else "PERMISSION_ALLOWED",
            target_id=route,
            details=payload,
        )
