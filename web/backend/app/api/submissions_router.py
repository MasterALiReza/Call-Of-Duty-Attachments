from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from web.backend.app.schemas.common import ApiResponse, PaginatedData, PaginationMeta
from web.backend.app.schemas.submissions_schema import (
    SubmissionResponse,
    SubmissionReviewRequest,
    ReportResponse,
    ReportResolveRequest,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/submissions", tags=["User Submissions & Moderation"])


@router.get("", response_model=ApiResponse[PaginatedData[SubmissionResponse]])
async def list_submissions(
    status_filter: Optional[str] = Query("pending", pattern="^(pending|approved|rejected|deleted|all)$"),
    mode: Optional[str] = Query(None, pattern="^(br|mp)$"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
):
    """List user attachments submissions with status and search filtering"""
    db = get_database_adapter()
    where_clauses = []
    params = []

    if status_filter and status_filter != "all":
        where_clauses.append("ua.status = %s")
        params.append(status_filter)
    if mode:
        where_clauses.append("ua.mode = %s")
        params.append(mode)
    if search:
        where_clauses.append("(ua.attachment_name ILIKE %s OR ua.description ILIKE %s OR u.username ILIKE %s)")
        search_pattern = f"%{search.strip()}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_query = f"""
        SELECT COUNT(*) as total
        FROM user_attachments ua
        LEFT JOIN users u ON ua.user_id = u.user_id
        {where_sql}
    """
    count_res = await db.execute_query(count_query, tuple(params), fetch_one=True)
    total_items = count_res["total"] if count_res else 0
    total_pages = (total_items + page_size - 1) // page_size or 1

    offset = (page - 1) * page_size
    query = f"""
        SELECT 
            ua.id, ua.user_id, ua.weapon_id, ua.mode, ua.category, ua.custom_weapon_name,
            ua.attachment_name, ua.description, ua.image_file_id, ua.status,
            ua.submitted_at::text, ua.approved_at::text, ua.approved_by,
            ua.rejected_at::text, ua.rejected_by, ua.rejection_reason,
            ua.like_count, ua.report_count, ua.view_count,
            w.name as weapon_name,
            u.username, u.first_name
        FROM user_attachments ua
        LEFT JOIN weapons w ON ua.weapon_id = w.id
        LEFT JOIN users u ON ua.user_id = u.user_id
        {where_sql}
        ORDER BY ua.submitted_at DESC
        LIMIT %s OFFSET %s
    """
    paginated_params = params + [page_size, offset]
    rows = await db.execute_query(query, tuple(paginated_params), fetch_all=True)
    items = [SubmissionResponse(**r) for r in rows]

    return ApiResponse(
        success=True,
        data=PaginatedData(
            items=items,
            meta=PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        ),
    )


@router.post("/{submission_id}/review", response_model=ApiResponse[dict])
async def review_submission(
    submission_id: int,
    payload: SubmissionReviewRequest,
    admin=Depends(require_permission("manage_user_attachments")),
):
    """Approve or reject a user submission"""
    db = get_database_adapter()

    if payload.action == "approve":
        success = await db.users.approve_user_attachment(
            attachment_id=submission_id,
            admin_id=admin.user_id,
        )
        if not success:
            raise HTTPException(status_code=400, detail="خطا در تایید اتچمنت کاربر")
        return ApiResponse(success=True, message="اتچمنت با موفقیت تایید شد")

    elif payload.action == "reject":
        reason = payload.rejection_reason or "عدم تطابق با قوانین ربات"
        success = await db.users.reject_user_attachment(
            attachment_id=submission_id,
            admin_id=admin.user_id,
            reason=reason,
        )
        if not success:
            raise HTTPException(status_code=400, detail="خطا در رد اتچمنت کاربر")
        return ApiResponse(success=True, message="اتچمنت رد شد و پیام به کاربر ارسال خواهد شد")


# ─────────────────────────────────────────────────────────────
# Reports Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/reports", response_model=ApiResponse[List[ReportResponse]])
async def list_reports(
    status_filter: str = Query("pending", pattern="^(pending|reviewed|resolved|dismissed|all)$"),
    admin=Depends(get_current_admin),
):
    """List reports on user attachments"""
    db = get_database_adapter()
    where_sql = "" if status_filter == "all" else "WHERE uar.status = %s"
    params = () if status_filter == "all" else (status_filter,)

    query = f"""
        SELECT 
            uar.id, uar.attachment_id, uar.reporter_id, uar.reason, uar.status,
            uar.reported_at::text, uar.resolved_by, uar.resolved_at::text, uar.resolution_notes,
            ua.attachment_name, ua.user_id as author_id,
            u.username as reporter_username
        FROM user_attachment_reports uar
        JOIN user_attachments ua ON uar.attachment_id = ua.id
        LEFT JOIN users u ON uar.reporter_id = u.user_id
        {where_sql}
        ORDER BY uar.reported_at DESC
        LIMIT 100
    """
    rows = await db.execute_query(query, params, fetch_all=True)
    items = [ReportResponse(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/reports/{report_id}/resolve", response_model=ApiResponse[dict])
async def resolve_report(
    report_id: int,
    payload: ReportResolveRequest,
    admin=Depends(require_permission("manage_user_attachments")),
):
    """Resolve, dismiss, or delete reported attachment"""
    db = get_database_adapter()
    query = """
        UPDATE user_attachment_reports
        SET status = %s, resolved_by = %s, resolved_at = NOW(), resolution_notes = %s
        WHERE id = %s
        RETURNING attachment_id
    """
    report_status = "dismissed" if payload.action == "dismiss" else "resolved"
    row = await db.execute_query(
        query,
        (report_status, admin.user_id, payload.resolution_notes or payload.action, report_id),
        fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="گزارش یافت نشد")

    if payload.action in ("resolve_delete", "resolve_ban"):
        # Delete user attachment
        await db.execute_query(
            "UPDATE user_attachments SET status = 'deleted', deleted_at = NOW(), deleted_by = %s WHERE id = %s",
            (admin.user_id, row["attachment_id"]),
        )

    return ApiResponse(success=True, message="گزارش با موفقیت رسیدگی شد")
