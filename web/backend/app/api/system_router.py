import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import FileResponse
from web.backend.app.schemas.common import ApiResponse
from web.backend.app.schemas.system_schema import (
    SystemSettingItem,
    SystemSettingUpdate,
    BlacklistWordItem,
    BlacklistWordCreate,
    HealthIssueItem,
    BackupFileItem,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter
from utils.data_health_check import DataHealthChecker

router = APIRouter(prefix="/system", tags=["System, Settings & Backups"])
BACKUPS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Settings Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/settings", response_model=ApiResponse[List[SystemSettingItem]])
async def list_settings(admin=Depends(get_current_admin)):
    """List system settings"""
    db = get_database_adapter()
    query = "SELECT key, value, description, category, data_type, updated_at::text FROM settings ORDER BY key ASC"
    rows = await db.execute_query(query, fetch_all=True)
    items = [SystemSettingItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.put("/settings", response_model=ApiResponse[dict])
async def update_settings_bulk(
    payload: Dict[str, Any],
    admin=Depends(require_permission("manage_settings")),
):
    """Bulk update system settings"""
    db = get_database_adapter()
    settings_dict = payload.get("settings", {})
    for key, value in settings_dict.items():
        query = """
            INSERT INTO settings (key, value, updated_by, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
        """
        await db.execute_query(query, (key, str(value), admin.user_id))
    return ApiResponse(success=True, message="تمام تنظیمات با موفقیت ذخیره شدند")


@router.put("/settings/{key}", response_model=ApiResponse[dict])
async def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    admin=Depends(require_permission("manage_settings")),
):
    """Update a system setting key-value"""
    db = get_database_adapter()
    query = """
        INSERT INTO settings (key, value, description, category, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            description = COALESCE(EXCLUDED.description, settings.description),
            category = COALESCE(EXCLUDED.category, settings.category),
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
    """
    await db.execute_query(query, (key, payload.value, payload.description, payload.category or "general", admin.user_id))
    return ApiResponse(success=True, message=f"تنظیمات {key} با موفقیت ذخیره شد")


# ─────────────────────────────────────────────────────────────
# Blacklist Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/blacklist", response_model=ApiResponse[List[BlacklistWordItem]])
async def list_blacklist(admin=Depends(get_current_admin)):
    """List prohibited words"""
    db = get_database_adapter()
    query = "SELECT word, category, severity, created_at::text FROM blacklisted_words ORDER BY created_at DESC"
    rows = await db.execute_query(query, fetch_all=True)
    items = [BlacklistWordItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/blacklist", response_model=ApiResponse[BlacklistWordItem])
async def add_blacklist_word(
    payload: BlacklistWordCreate,
    admin=Depends(require_permission("manage_texts")),
):
    """Add word to blacklist"""
    db = get_database_adapter()
    query = """
        INSERT INTO blacklisted_words (word, category, severity)
        VALUES (%s, %s, %s)
        ON CONFLICT (word) DO UPDATE SET category = EXCLUDED.category, severity = EXCLUDED.severity
        RETURNING word, category, severity, created_at::text
    """
    row = await db.execute_query(query, (payload.word.strip().lower(), payload.category, payload.severity), fetch_one=True)
    return ApiResponse(success=True, message="کلمه به لیست مسدودشده‌ها افزوده شد", data=BlacklistWordItem(**row))


@router.delete("/blacklist/{word}", response_model=ApiResponse[dict])
async def delete_blacklist_word(
    word: str,
    admin=Depends(require_permission("manage_texts")),
):
    """Remove word from blacklist"""
    db = get_database_adapter()
    query = "DELETE FROM blacklisted_words WHERE word = %s RETURNING word"
    row = await db.execute_query(query, (word.strip().lower(),), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="کلمه یافت نشد")
    return ApiResponse(success=True, message="کلمه از لیست مسدودشده‌ها حذف شد")


# ─────────────────────────────────────────────────────────────
# Data Health Check Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/health-issues", response_model=ApiResponse[List[HealthIssueItem]])
async def get_health_issues(admin=Depends(get_current_admin)):
    """Fetch latest data integrity health check issues"""
    db = get_database_adapter()
    query = """
        SELECT check_type, severity, category, issue_count, details, created_at::text
        FROM data_health_checks
        ORDER BY created_at DESC
        LIMIT 50
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [HealthIssueItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/health-check/run", response_model=ApiResponse[dict])
async def run_health_check(admin=Depends(require_permission("all"))):
    """Run real-time automated data health and schema audit"""
    db = get_database_adapter()
    checker = DataHealthChecker(db)
    results = await checker.run_all_checks()
    return ApiResponse(success=True, message="بررسی سلامت داده‌ها با موفقیت انجام شد", data=results)


# ─────────────────────────────────────────────────────────────
# Backups Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/backups", response_model=ApiResponse[List[BackupFileItem]])
async def list_backups(admin=Depends(require_permission("all"))):
    """List available PostgreSQL backup files"""
    items = []
    if BACKUPS_DIR.exists():
        for f in BACKUPS_DIR.glob("*.*"):
            if f.is_file() and f.suffix in [".sql", ".dump", ".zip"]:
                stat = f.stat()
                items.append(
                    BackupFileItem(
                        filename=f.name,
                        size_bytes=stat.st_size,
                        size_mb=round(stat.st_size / (1024 * 1024), 2),
                        created_at=str(stat.st_mtime),
                    )
                )
    items.sort(key=lambda x: x.created_at, reverse=True)
    return ApiResponse(success=True, data=items)


@router.post("/backups", response_model=ApiResponse[dict])
async def create_backup(admin=Depends(require_permission("all"))):
    """Trigger manual PostgreSQL database backup"""
    db = get_database_adapter()
    backup_file = await db.settings.backup_database()
    if not backup_file:
        raise HTTPException(status_code=500, detail="خطا در ایجاد نسخه پشتیبان دیتابیس")
    return ApiResponse(success=True, message="نسخه پشتیبان با موفقیت ایجاد شد", data={"file": backup_file})


@router.get("/backups/{filename}/download")
async def download_backup(filename: str, admin=Depends(require_permission("all"))):
    """Download database backup file"""
    file_path = BACKUPS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="فایل پشتیبان یافت نشد")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")
