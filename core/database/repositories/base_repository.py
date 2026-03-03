from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Callable, Tuple
import os
import asyncio
from contextlib import asynccontextmanager
from functools import wraps

if TYPE_CHECKING:
    from core.database.database_pg import DatabasePostgres
from utils.logger import get_logger, log_exception

logger = get_logger('database.repository', 'database.log')


def with_retry(max_retries: int = 3, delay: float = 0.5, 
               exponential_backoff: bool = True,
               exceptions: Tuple = (Exception,)) -> Callable:
    """
    Decorator for retrying database operations
    
    Args:
        max_retries: Maximum retry attempts
        delay: Initial delay between retries (seconds)
        exponential_backoff: Use exponential backoff
        exceptions: Tuple of exception types to catch
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    
                    error_str = str(e).lower()
                    is_retryable = any(keyword in error_str for keyword in [
                        'connection', 'timeout', 'deadlock', 'lock', 
                        'temporary', 'unavailable', 'reset'
                    ])
                    
                    if not is_retryable or attempt == max_retries - 1:
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}"
                    )
                    
                    await asyncio.sleep(current_delay)
                    
                    if exponential_backoff:
                        current_delay *= 2
            
            raise last_error
        
        return wrapper
    return decorator


class BaseRepository:
    """
    Base Repository class providing consistent database access.
    """
    
    DEFAULT_RETRY_COUNT: int = 3
    
    def __init__(self, db: 'DatabasePostgres'):
        self._db = db

    async def execute_query(
        self, 
        query: str, 
        params: tuple = None, 
        fetch_one: bool = False, 
        fetch_all: bool = False, 
        as_dict: bool = True
    ) -> Any:
        """Execute a query through the database adapter."""
        return await self._db.execute_query(
            query, params, fetch_one, fetch_all, as_dict
        )

    @asynccontextmanager
    async def transaction(self):
        async with self._db.transaction() as conn:
            yield conn
            
    @asynccontextmanager
    async def get_connection(self):
        async with self._db.get_connection() as conn:
            yield conn

    @with_retry(max_retries=3, delay=0.5, exponential_backoff=True)
    async def execute_with_retry(
        self,
        query: str,
        params: tuple = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        as_dict: bool = True
    ) -> Any:
        """Execute query with automatic retry on transient errors."""
        return await self.execute_query(
            query, params, fetch_one, fetch_all, as_dict
        )

    async def execute_in_transaction(
        self, 
        operations: List[Tuple[str, tuple]]
    ) -> bool:
        """
        Execute multiple operations in a single transaction.
        
        Args:
            operations: List of (query, params) tuples
            
        Returns:
            True if all operations succeeded
        """
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    for query, params in operations:
                        await cursor.execute(query, params)
            return True
        except Exception as e:
            log_exception(logger, e, "execute_in_transaction")
            return False
