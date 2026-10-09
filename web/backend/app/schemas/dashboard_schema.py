from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class DashboardStats(BaseModel):
    total_users: int = 0
    new_users_today: int = 0
    active_users_week: int = 0
    total_weapons: int = 0
    total_attachments: int = 0
    pending_submissions: int = 0
    open_tickets: int = 0
    pending_reports: int = 0
    total_views: int = 0
    total_likes: int = 0
    system_health_score: float = 100.0

class CategoryStat(BaseModel):
    category_id: int
    name: str
    display_name: Optional[str] = None
    weapon_count: int = 0
    attachment_count: int = 0

class ModeStat(BaseModel):
    mode: str
    count: int = 0
    percentage: float = 0.0

class SearchTrendItem(BaseModel):
    query: str
    search_count: int
    last_searched: Optional[str] = None

class SystemHealthInfo(BaseModel):
    status: str = "healthy"
    database_connected: bool = True
    pool_size: int = 0
    pool_available: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    uptime_seconds: float = 0.0
