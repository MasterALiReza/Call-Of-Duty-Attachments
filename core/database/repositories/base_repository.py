from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import os
from contextlib import asynccontextmanager

if TYPE_CHECKING:
    from core.database.database_pg import DatabasePostgres
from utils.logger import get_logger, log_exception

logger = get_logger('database.repository', 'database.log')

class BaseRepository:
    """
    Base Repository class providing consistent database access.
    """
    def __init__(self, db: 'DatabasePostgres'):
        self._db = db

    async def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, 
                     fetch_all: bool = False, as_dict: bool = True) -> Any:
        return await self._db.execute_query(query, params, fetch_one, fetch_all, as_dict)

    @asynccontextmanager
    async def transaction(self):
        async with self._db.transaction() as conn:
            yield conn
            
    @asynccontextmanager
    async def get_connection(self):
        async with self._db.get_connection() as conn:
            yield conn
