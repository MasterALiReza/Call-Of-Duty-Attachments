from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from web.backend.app.schemas.common import ApiResponse
from web.backend.app.schemas.cms_schema import (
    ChannelItem,
    ChannelCreate,
    ChannelUpdate,
    GuideItem,
    GuideCreate,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/cms", tags=["CMS & Required Channels"])


# ─────────────────────────────────────────────────────────────
# Required Channels Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/channels", response_model=ApiResponse[List[ChannelItem]])
async def list_channels(admin=Depends(get_current_admin)):
    """List required channels with priority ordering"""
    db = get_database_adapter()
    query = """
        SELECT channel_id, title, url, priority, is_active, created_at::text
        FROM required_channels
        ORDER BY priority ASC, created_at ASC
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [ChannelItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/channels", response_model=ApiResponse[ChannelItem])
async def create_channel(
    payload: ChannelCreate,
    admin=Depends(require_permission("manage_settings")),
):
    """Add a new required channel for forced subscription"""
    db = get_database_adapter()
    query = """
        INSERT INTO required_channels (channel_id, title, url, priority, is_active)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING channel_id, title, url, priority, is_active, created_at::text
    """
    try:
        row = await db.execute_query(
            query,
            (payload.channel_id.strip(), payload.title.strip(), payload.url.strip(), payload.priority, payload.is_active),
            fetch_one=True,
        )
        return ApiResponse(success=True, message="کانال با موفقیت اضافه شد", data=ChannelItem(**row))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در ایجاد کانال: ممکن است این شناسه قبلاً ثبت شده باشد ({e})")


@router.put("/channels/{channel_id}", response_model=ApiResponse[ChannelItem])
async def update_channel(
    channel_id: str,
    payload: ChannelUpdate,
    admin=Depends(require_permission("manage_settings")),
):
    """Update existing required channel"""
    db = get_database_adapter()
    updates = []
    params = []
    if payload.title is not None:
        updates.append("title = %s")
        params.append(payload.title.strip())
    if payload.url is not None:
        updates.append("url = %s")
        params.append(payload.url.strip())
    if payload.priority is not None:
        updates.append("priority = %s")
        params.append(payload.priority)
    if payload.is_active is not None:
        updates.append("is_active = %s")
        params.append(payload.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای ویرایش ارسال نشده است")

    params.append(channel_id)
    query = f"""
        UPDATE required_channels
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE channel_id = %s
        RETURNING channel_id, title, url, priority, is_active, created_at::text
    """
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="کانال یافت نشد")
    return ApiResponse(success=True, message="کانال با موفقیت به‌روزرسانی شد", data=ChannelItem(**row))


@router.post("/channels/{channel_id}/toggle", response_model=ApiResponse[ChannelItem])
async def toggle_channel(
    channel_id: str,
    admin=Depends(require_permission("manage_settings")),
):
    """Toggle a required channel's active state"""
    db = get_database_adapter()
    query = """
        UPDATE required_channels
        SET is_active = NOT is_active, updated_at = NOW()
        WHERE channel_id = %s
        RETURNING channel_id, title, url, priority, is_active, created_at::text
    """
    row = await db.execute_query(query, (channel_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="کانال یافت نشد")
    return ApiResponse(
        success=True,
        message=f"وضعیت کانال با موفقیت تغییر یافت",
        data=ChannelItem(**row),
    )


@router.delete("/channels/{channel_id}", response_model=ApiResponse[dict])
async def delete_channel(
    channel_id: str,
    admin=Depends(require_permission("manage_settings")),
):
    """Delete a required channel"""
    db = get_database_adapter()
    query = "DELETE FROM required_channels WHERE channel_id = %s RETURNING channel_id"
    row = await db.execute_query(query, (channel_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="کانال یافت نشد")
    return ApiResponse(success=True, message="کانال با موفقیت حذف شد")


# ─────────────────────────────────────────────────────────────
# Guides Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/guides", response_model=ApiResponse[List[GuideItem]])
async def list_guides(admin=Depends(get_current_admin)):
    """List game guides, HUD, and sensitivity settings"""
    db = get_database_adapter()
    query = """
        SELECT id, key, mode, name, code, description, is_active
        FROM guides
        ORDER BY id ASC
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [GuideItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/guides", response_model=ApiResponse[GuideItem])
async def create_guide(
    payload: GuideCreate,
    admin=Depends(require_permission("manage_texts")),
):
    """Create a new guide"""
    db = get_database_adapter()
    query = """
        INSERT INTO guides (key, mode, name, code, description, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, key, mode, name, code, description, is_active
    """
    try:
        row = await db.execute_query(
            query,
            (payload.key.strip(), payload.mode, payload.name, payload.code, payload.description, payload.is_active),
            fetch_one=True,
        )
        return ApiResponse(success=True, message="راهنما با موفقیت ثبت شد", data=GuideItem(**row))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در ایجاد راهنما: {e}")
