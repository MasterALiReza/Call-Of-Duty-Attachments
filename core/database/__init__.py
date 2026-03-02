"""Database modules for CODM Attachments Bot - PostgreSQL Only"""

from .database_adapter import get_database_adapter, DatabaseAdapter
from .database_pg import DatabasePostgres

__all__ = ['get_database_adapter', 'DatabaseAdapter', 
           'DatabasePostgres']
