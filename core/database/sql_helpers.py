"""
SQL Helper Functions - PostgreSQL Only
Helper functions for PostgreSQL database operations (PG-only)
"""

import os
from typing import Optional, Union
from datetime import datetime, timedelta




def get_date_interval(days_ago: int) -> str:
    """
    تولید query برای محاسبه تاریخ N روز قبل
    
    Args:
        days_ago: تعداد روزهای قبل
    
    Returns:
        Query string
    """
    return f"CURRENT_DATE - INTERVAL '{days_ago} days'"


def get_datetime_interval(days_ago: int) -> str:
    """
    تولید query برای محاسبه datetime N روز قبل
    
    Args:
        days_ago: تعداد روزهای قبل
    
    Returns:
        Query string
    """
    return f"CURRENT_TIMESTAMP - INTERVAL '{days_ago} days'"


def get_current_date() -> str:
    """
    تولید query برای تاریخ امروز
    
    Returns:
        Query string سازگار با backend
    """
    # PostgreSQL only
    return "CURRENT_DATE"


def get_current_timestamp() -> str:
    """
    تولید query برای timestamp فعلی
    
    Returns:
        Query string سازگار با backend
    """
    # PostgreSQL only
    return "CURRENT_TIMESTAMP"


def build_upsert_query(
    table: str,
    columns: list,
    conflict_columns: list,
    update_columns: Optional[list] = None
) -> str:
    """
    ساخت query UPSERT سازگار با PostgreSQL
    
    Args:
        table: نام جدول
        columns: لیست ستون‌های INSERT
        conflict_columns: ستون‌هایی که conflict دارند
        update_columns: ستون‌هایی که باید UPDATE شوند (اگر None باشد همه به‌جز conflict)
    
    Returns:
        Query string کامل با placeholders
    """
    placeholder = '%s'
    placeholders = ', '.join([placeholder] * len(columns))
    columns_str = ', '.join(columns)
    conflict_str = ', '.join(conflict_columns)
    if update_columns is None:
        update_columns = [col for col in columns if col not in conflict_columns]
    if update_columns:
        update_str = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
        return f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}"
    else:
        return f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT ({conflict_str}) DO NOTHING"


def build_insert_ignore_query(
    table: str,
    columns: list
) -> str:
    """
    ساخت query INSERT IGNORE سازگار
    
    Args:
        table: نام جدول
        columns: لیست ستون‌ها
    
    Returns:
        Query string کامل
    """
    # PostgreSQL only
    placeholder = '%s'
    placeholders = ', '.join([placeholder] * len(columns))
    columns_str = ', '.join(columns)
    return f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"


def get_returning_clause(column: str = 'id') -> str:
    """
    تولید RETURNING clause برای دریافت ID بعد از INSERT
    
    Args:
        column: نام ستونی که باید برگردانده شود
    
    Returns:
        RETURNING clause مخصوص PostgreSQL
    """
    # PostgreSQL only
    return f" RETURNING {column}"


def adapt_placeholder(query: str) -> str:
    """
    تبدیل placeholders در query
    
    Args:
        query: Query با placeholder
    
    Returns:
        Query با placeholder صحیح
    """
    # PostgreSQL only - convert $ placeholders to %s if present
    parts = []
    in_string = False
    quote_char = None
    i = 0
    while i < len(query):
        char = query[i]
        if char in ('"', "'") and (i == 0 or query[i-1] != '\\'):
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None
        if char == '$' and not in_string:
            parts.append('%s')
        else:
            parts.append(char)
        i += 1
    return ''.join(parts)


# کلاس wrapper برای queries سازگار
class SQLQuery:
    """کلاس کمکی برای ساخت queries (مخصوص PostgreSQL)"""
    
    def __init__(self):
        pass
    
    def placeholder(self) -> str:
        """دریافت placeholder مناسب (PostgreSQL)"""
        return '%s'
    
    def date_interval(self, days_ago: int) -> str:
        """محاسبه تاریخ N روز قبل"""
        return get_date_interval(days_ago)
    
    def datetime_interval(self, days_ago: int) -> str:
        """محاسبه datetime N روز قبل"""
        return get_datetime_interval(days_ago)
    
    def current_date(self) -> str:
        """تاریخ امروز"""
        return get_current_date()
    
    def current_timestamp(self) -> str:
        """timestamp فعلی"""
        return get_current_timestamp()
    
    def upsert(self, table: str, columns: list, conflict_columns: list, 
               update_columns: Optional[list] = None) -> str:
        """ساخت upsert query مخصوص PostgreSQL"""
        return build_upsert_query(table, columns, conflict_columns, update_columns)
    
    def insert_ignore(self, table: str, columns: list) -> str:
        """ساخت insert ignore query مخصوص PostgreSQL"""
        return build_insert_ignore_query(table, columns)
    
    def returning(self, column: str = 'id') -> str:
        """RETURNING clause (PostgreSQL)"""
        return get_returning_clause(column)


# ========== Full-Text Search Helpers ==========

def build_fts_where_clause(
    query: str,
    search_columns: list
) -> str:
    """
    ساخت WHERE clause برای Full-Text Search
    
    Args:
        query: متن جستجو
        search_columns: لیست ستون‌های جستجو (مثل ['name', 'code'])
    
    Returns:
        WHERE clause string
    """
    conditions = " OR ".join([f"{col} %% %s" for col in search_columns])
    return conditions


def build_fts_order_clause(
    query: str,
    primary_column: str
) -> str:
    """
    ساخت ORDER BY clause برای Full-Text Search
    
    Args:
        query: متن جستجو
        primary_column: ستون اصلی برای مرتب‌سازی
    
    Returns:
        ORDER BY clause string
    """
    # PostgreSQL only - pg_trgm similarity ordering
    return f"similarity({primary_column}, %s) DESC"


def get_fts_params(
    query: str,
    search_columns: list
) -> tuple:
    """
    دریافت پارامترهای مورد نیاز برای FTS query
    
    Args:
        query: متن جستجو
        search_columns: لیست ستون‌های جستجو
    
    Returns:
        Tuple از پارامترها برای query
    """
    # PostgreSQL only - one per WHERE column plus one for ORDER BY
    num_columns = len(search_columns)
    return tuple([query] * (num_columns + 1))


def build_fts_query(
    query: str,
    search_columns: list,
    primary_column: str = None
) -> tuple:
    """
    ساخت کامل FTS query (WHERE + ORDER + params)
    
    Args:
        query: متن جستجو
        search_columns: لیست ستون‌های جستجو
        primary_column: ستون اصلی برای ordering (default: اولین ستون)
    
    Returns:
        (where_clause, order_clause, params)
    """
    if primary_column is None:
        primary_column = search_columns[0]
    
    where_clause = build_fts_where_clause(query, search_columns)
    order_clause = build_fts_order_clause(query, primary_column)
    params = get_fts_params(query, search_columns)
    
    return (where_clause, order_clause, params)


def get_fts_similarity_threshold() -> float:
    """
    دریافت similarity threshold برای FTS
    
    Returns:
        Threshold value (0.0 - 1.0)
    """
    # PostgreSQL only
    threshold = os.getenv('PG_TRGM_THRESHOLD', '0.3')
    return float(threshold)
