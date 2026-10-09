import time
import psutil
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from web.backend.app.schemas.common import ApiResponse
from web.backend.app.schemas.dashboard_schema import (
    DashboardStats,
    CategoryStat,
    ModeStat,
    SearchTrendItem,
    SystemHealthInfo,
)
from web.backend.app.auth import get_current_admin
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])
START_TIME = time.time()


@router.get("/stats", response_model=ApiResponse[DashboardStats])
async def get_dashboard_stats(admin=Depends(get_current_admin)):
    """Fetch high-level KPI dashboard metrics"""
    db = get_database_adapter()

    # 1. User stats
    user_stats = await db.users.get_users_stats()

    # 2. Attachments & Weapons counts
    att_count_res = await db.execute_query(
        "SELECT COUNT(*) as cnt FROM attachments", fetch_one=True
    )
    weapon_count_res = await db.execute_query(
        "SELECT COUNT(*) as cnt FROM weapons WHERE is_active = TRUE", fetch_one=True
    )
    views_likes_res = await db.execute_query(
        """
        SELECT 
            COALESCE(SUM(total_views), 0) as total_views,
            COALESCE(COUNT(*) FILTER (WHERE rating = 1), 0) as total_likes
        FROM user_attachment_engagement
        """,
        fetch_one=True,
    )

    # 3. Pending Submissions & Reports
    pending_sub_res = await db.execute_query(
        "SELECT COUNT(*) as cnt FROM user_attachments WHERE status = 'pending'", fetch_one=True
    )
    pending_rep_res = await db.execute_query(
        "SELECT COUNT(*) as cnt FROM user_attachment_reports WHERE status = 'pending'", fetch_one=True
    )

    # 4. Open Tickets
    open_tickets_res = await db.execute_query(
        "SELECT COUNT(*) as cnt FROM tickets WHERE status IN ('open', 'in_progress', 'waiting_user')",
        fetch_one=True,
    )

    # 5. Quality / Health Score
    health_res = await db.execute_query(
        "SELECT health_score FROM data_quality_metrics ORDER BY created_at DESC LIMIT 1",
        fetch_one=True,
    )
    health_score = float(health_res["health_score"]) if health_res and health_res.get("health_score") is not None else 98.5

    stats = DashboardStats(
        total_users=user_stats.get("total", 0),
        new_users_today=user_stats.get("new_today", 0),
        active_users_week=user_stats.get("active_week", 0),
        total_weapons=weapon_count_res["cnt"] if weapon_count_res else 0,
        total_attachments=att_count_res["cnt"] if att_count_res else 0,
        pending_submissions=pending_sub_res["cnt"] if pending_sub_res else 0,
        open_tickets=open_tickets_res["cnt"] if open_tickets_res else 0,
        pending_reports=pending_rep_res["cnt"] if pending_rep_res else 0,
        total_views=int(views_likes_res["total_views"]) if views_likes_res else 0,
        total_likes=int(views_likes_res["total_likes"]) if views_likes_res else 0,
        system_health_score=health_score,
    )

    return ApiResponse(success=True, data=stats)


@router.get("/categories-breakdown", response_model=ApiResponse[List[CategoryStat]])
async def get_categories_breakdown(admin=Depends(get_current_admin)):
    """Fetch weapon and attachment count breakdown per category"""
    db = get_database_adapter()
    query = """
        SELECT 
            c.id as category_id,
            c.name,
            c.display_name,
            COUNT(DISTINCT w.id) as weapon_count,
            COUNT(a.id) as attachment_count
        FROM weapon_categories c
        LEFT JOIN weapons w ON c.id = w.category_id AND w.is_active = TRUE
        LEFT JOIN attachments a ON w.id = a.weapon_id
        WHERE c.is_active = TRUE
        GROUP BY c.id, c.name, c.display_name
        ORDER BY c.sort_order ASC
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [
        CategoryStat(
            category_id=r["category_id"],
            name=r["name"],
            display_name=r["display_name"] or r["name"],
            weapon_count=r["weapon_count"],
            attachment_count=r["attachment_count"],
        )
        for r in rows
    ]
    return ApiResponse(success=True, data=items)


@router.get("/modes-breakdown", response_model=ApiResponse[List[ModeStat]])
async def get_modes_breakdown(admin=Depends(get_current_admin)):
    """Fetch distribution of Battle Royale vs Multiplayer attachments"""
    db = get_database_adapter()
    query = """
        SELECT mode, COUNT(*) as cnt
        FROM attachments
        GROUP BY mode
    """
    rows = await db.execute_query(query, fetch_all=True)
    total = sum(r["cnt"] for r in rows) or 1
    items = [
        ModeStat(
            mode=r["mode"].upper(),
            count=r["cnt"],
            percentage=round((r["cnt"] / total) * 100, 1),
        )
        for r in rows
    ]
    return ApiResponse(success=True, data=items)


@router.get("/search-trends", response_model=ApiResponse[List[SearchTrendItem]])
async def get_search_trends(limit: int = 10, admin=Depends(get_current_admin)):
    """Fetch most popular weapon and attachment searches"""
    db = get_database_adapter()
    query = """
        SELECT query, search_count, last_searched
        FROM popular_searches
        ORDER BY search_count DESC
        LIMIT %s
    """
    rows = await db.execute_query(query, (limit,), fetch_all=True)
    items = [
        SearchTrendItem(
            query=r["query"],
            search_count=r["search_count"],
            last_searched=str(r["last_searched"]) if r.get("last_searched") else None,
        )
        for r in rows
    ]
    return ApiResponse(success=True, data=items)


@router.get("/system-health", response_model=ApiResponse[SystemHealthInfo])
async def get_system_health(admin=Depends(get_current_admin)):
    """Fetch live server metrics: CPU, RAM, Uptime, DB Pool"""
    db = get_database_adapter()
    pool = db._pool
    pool_size = pool.max_size if pool else 0
    
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    uptime = time.time() - START_TIME

    health = SystemHealthInfo(
        status="healthy",
        database_connected=True,
        pool_size=pool_size,
        pool_available=pool_size,
        cpu_percent=cpu,
        memory_percent=mem,
        uptime_seconds=round(uptime, 1),
    )
    return ApiResponse(success=True, data=health)
