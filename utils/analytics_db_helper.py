"""
Analytics Database Helper
Helper برای استفاده آسان از database در analytics modules
"""
from typing import Dict

class AnalyticsDBHelper:
    """Helper class برای analytics با PostgreSQL support"""

    def __init__(self, db_adapter):
        self.db = db_adapter

    async def execute_query(self, query: str, params: tuple=(), fetch_all: bool=False, fetch_one: bool=False):
        """Execute PostgreSQL query"""
        query = query.replace('?', '%s')
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if fetch_one:
                    return await cur.fetchone()
                if fetch_all:
                    return await cur.fetchall()
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
