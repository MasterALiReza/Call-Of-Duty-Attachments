"""
Analytics Database Helper
Helper برای استفاده آسان از database در analytics modules
"""
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

class AnalyticsDBHelper:
    """Helper class برای analytics با PostgreSQL support"""

    def __init__(self, db_adapter):
        self.db = db_adapter

    @contextmanager
    async def _get_connection(self):
        """Get PostgreSQL database connection"""
        async with self.db.get_connection() as conn:
            yield conn

    async def execute_query(self, query: str, params: tuple=(), fetch_all: bool=False, fetch_one: bool=False):
        """Execute PostgreSQL query"""
        query = query.replace('?', '%s')
        if hasattr(self.db, 'execute_query'):
            return await self.db.execute_query(query, params, fetch_all=fetch_all, fetch_one=fetch_one)
        async with self._get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if fetch_one:
                    return await cur.fetchone()
                if fetch_all:
                    return await cur.fetchall()
                # conn.commit() is handled by context manager if it's a transaction,
                # but if it's a simple connection we might need to commit if not in autocommit mode.
                # However, get_connection() usually returns a connection that auto-commits or is handled.
                return None

    async def get_stats(self, days: int=30) -> Dict:
        """Get analytics stats for last N days"""
        try:
            days = int(days)
        except Exception:
            days = 30
        days = max(1, min(days, 365))
        date_filter = 'created_at >= NOW() - make_interval(days => %s)'
        params = (days,)
        query = f'\n            SELECT COUNT(*) as total\n            FROM analytics_events  \n            WHERE {date_filter}\n        '
        result = await self.execute_query(query, params, fetch_one=True)
        return result or {'total': 0}