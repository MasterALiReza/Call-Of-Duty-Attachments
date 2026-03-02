import os
from enum import Enum
import threading
from typing import Optional

from .database_pg import DatabasePostgres

class DatabaseBackend(Enum):
    """Supported database backends"""
    POSTGRES = 'postgres'

# Type alias for the adapter interface
DatabaseAdapter = DatabasePostgres

_db_instance: Optional[DatabaseAdapter] = None
_db_lock = threading.Lock()

def get_database_adapter(backend: DatabaseBackend = DatabaseBackend.POSTGRES) -> DatabaseAdapter:
    """
    Factory function to get the database adapter.
    Returns a singleton instance of DatabasePostgres.
    
    Args:
        backend: Database backend to use (default: POSTGRES)
    
    Returns:
        DatabaseAdapter: The database adapter instance
    """
    global _db_instance
    
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                if backend == DatabaseBackend.POSTGRES:
                    _db_instance = DatabasePostgres()
                else:
                    raise ValueError(f"Unsupported database backend: {backend}")
        
    return _db_instance
