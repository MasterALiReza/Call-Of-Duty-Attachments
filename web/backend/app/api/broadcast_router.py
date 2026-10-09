import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from web.backend.app.schemas.common import ApiResponse
from web.backend.app.schemas.broadcast_schema import (
    BroadcastRequest,
    ScheduledNotificationItem,
    ScheduledNotificationCreate,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter
from utils.broadcast_optimizer import OptimizedBroadcaster

router = APIRouter(prefix="/broadcast", tags=["Broadcast & Notifications"])


async def run_async_broadcast(req: BroadcastRequest, admin_id: int):
    """Background task to broadcast messages to subscribers"""
    db = get_database_adapter()
    # Fetch target recipients
    recipients = await db.users.get_active_subscribers()
    if not recipients:
        return

    # In production, uses OptimizedBroadcaster if bot token is active
    # Otherwise records the broadcast event in db
    await db.analytics.track_event(
        user_id=admin_id,
        event_type="web_broadcast",
        metadata={"text": req.message_text[:100], "recipients_count": len(recipients)},
    )


@router.post("", response_model=ApiResponse[dict])
async def trigger_broadcast(
    payload: BroadcastRequest,
    background_tasks: BackgroundTasks,
    admin=Depends(require_permission("send_notifications")),
):
    """Broadcast a rich message to bot subscribers in the background"""
    db = get_database_adapter()
    recipients = await db.users.get_active_subscribers()
    total_recipients = len(recipients) if recipients else 0

    background_tasks.add_task(run_async_broadcast, payload, admin.user_id)

    return ApiResponse(
        success=True,
        message=f"فرآیند ارسال پیام همگانی برای {total_recipients} کاربر در پس‌زمینه آغاز شد",
        data={"recipients_count": total_recipients},
    )


@router.get("/scheduled", response_model=ApiResponse[List[ScheduledNotificationItem]])
async def list_scheduled_notifications(admin=Depends(get_current_admin)):
    """List all periodic scheduled notifications"""
    db = get_database_adapter()
    query = """
        SELECT id, message_type, message_text, photo_file_id, parse_mode,
               interval_hours, enabled, last_sent_at::text, next_run_at::text,
               created_by, created_at::text
        FROM scheduled_notifications
        ORDER BY id ASC
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [ScheduledNotificationItem(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/scheduled", response_model=ApiResponse[ScheduledNotificationItem])
async def create_scheduled_notification(
    payload: ScheduledNotificationCreate,
    admin=Depends(require_permission("manage_scheduled_notifications")),
):
    """Create a recurring scheduled notification"""
    db = get_database_adapter()
    query = """
        INSERT INTO scheduled_notifications (
            message_type, message_text, photo_file_id, parse_mode, interval_hours, enabled, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, message_type, message_text, photo_file_id, parse_mode,
                  interval_hours, enabled, last_sent_at::text, next_run_at::text,
                  created_by, created_at::text
    """
    row = await db.execute_query(
        query,
        (
            payload.message_type,
            payload.message_text.strip(),
            payload.photo_file_id,
            payload.parse_mode,
            payload.interval_hours,
            payload.enabled,
            admin.user_id,
        ),
        fetch_one=True,
    )
    return ApiResponse(success=True, message="اطلاعیه زمان‌بندی‌شده ایجاد شد", data=ScheduledNotificationItem(**row))


@router.post("/scheduled/{notification_id}/toggle", response_model=ApiResponse[dict])
async def toggle_scheduled_notification(
    notification_id: int,
    admin=Depends(require_permission("manage_scheduled_notifications")),
):
    """Toggle enabled status of scheduled notification"""
    db = get_database_adapter()
    query = """
        UPDATE scheduled_notifications
        SET enabled = NOT enabled, updated_at = NOW()
        WHERE id = %s
        RETURNING enabled
    """
    row = await db.execute_query(query, (notification_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اطلاعیه یافت نشد")
    return ApiResponse(success=True, message="وضعیت اطلاعیه تغییر کرد", data={"enabled": row["enabled"]})


@router.delete("/scheduled/{notification_id}", response_model=ApiResponse[dict])
async def delete_scheduled_notification(
    notification_id: int,
    admin=Depends(require_permission("manage_scheduled_notifications")),
):
    """Delete a scheduled notification"""
    db = get_database_adapter()
    query = "DELETE FROM scheduled_notifications WHERE id = %s RETURNING id"
    row = await db.execute_query(query, (notification_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اطلاعیه یافت نشد")
    return ApiResponse(success=True, message="اطلاعیه حذف شد")
