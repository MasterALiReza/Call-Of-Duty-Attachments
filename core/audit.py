import logging
from typing import Optional, Dict, Any
from core.database.database_adapter import get_database_adapter
from utils.logger import log_exception

logger = logging.getLogger('audit')

class AuditLogger:
    """Manages the creation and insertion of administrative audit logs."""
    
    def __init__(self):
        self.db = get_database_adapter()

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
            await self.db.execute_query(query)
            logger.info("Audit logs table verified/created.")
        except Exception as e:
            log_exception(logger, e, "create_audit_table")

    async def log_action(self, admin_id: int, action: str, target_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
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
            await self.db.execute_query(query, (admin_id, action, target_id, details_json))
            logger.debug(f"[Audit] Recorded block: Admin {admin_id} did {action} -> {target_id}")
        except Exception as e:
            log_exception(logger, e, f"log_audit_action({admin_id}, {action})")
