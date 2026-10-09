from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from web.backend.app.schemas.common import ApiResponse, PaginatedData, PaginationMeta
from web.backend.app.schemas.weapons_schema import (
    AttachmentResponse,
    AttachmentCreate,
    AttachmentUpdate,
    SuggestedAttachmentCreate,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/attachments", tags=["Attachments CMS"])


@router.get("", response_model=ApiResponse[PaginatedData[AttachmentResponse]])
async def list_attachments(
    weapon_id: Optional[int] = None,
    category_id: Optional[int] = None,
    mode: Optional[str] = Query(None, pattern="^(br|mp)$"),
    is_top: Optional[bool] = None,
    is_season_top: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
):
    """List attachments with filtering, search and pagination"""
    db = get_database_adapter()
    where_clauses = []
    params = []

    if weapon_id:
        where_clauses.append("a.weapon_id = %s")
        params.append(weapon_id)
    if category_id:
        where_clauses.append("w.category_id = %s")
        params.append(category_id)
    if mode:
        where_clauses.append("a.mode = %s")
        params.append(mode)
    if is_top is not None:
        where_clauses.append("a.is_top = %s")
        params.append(is_top)
    if is_season_top is not None:
        where_clauses.append("a.is_season_top = %s")
        params.append(is_season_top)
    if search:
        where_clauses.append("(a.name ILIKE %s OR a.code ILIKE %s OR w.name ILIKE %s)")
        search_pattern = f"%{search.strip()}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Count total items
    count_query = f"""
        SELECT COUNT(*) as total
        FROM attachments a
        JOIN weapons w ON a.weapon_id = w.id
        JOIN weapon_categories c ON w.category_id = c.id
        {where_sql}
    """
    count_res = await db.execute_query(count_query, tuple(params), fetch_one=True)
    total_items = count_res["total"] if count_res else 0
    total_pages = (total_items + page_size - 1) // page_size or 1

    # Fetch page
    offset = (page - 1) * page_size
    query = f"""
        SELECT 
            a.id, a.weapon_id, a.mode, a.code, a.name, a.image_file_id,
            a.is_top, a.is_season_top, a.order_index, a.views_count, a.shares_count,
            w.name as weapon_name,
            c.name as category_name,
            COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) as likes_count,
            COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) as dislikes_count
        FROM attachments a
        JOIN weapons w ON a.weapon_id = w.id
        JOIN weapon_categories c ON w.category_id = c.id
        LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id
        {where_sql}
        GROUP BY a.id, a.weapon_id, a.mode, a.code, a.name, a.image_file_id,
                 a.is_top, a.is_season_top, a.order_index, a.views_count, a.shares_count,
                 w.name, c.name, c.sort_order
        ORDER BY a.is_season_top DESC, a.is_top DESC, a.order_index ASC NULLS LAST, a.id DESC
        LIMIT %s OFFSET %s
    """
    paginated_params = params + [page_size, offset]
    rows = await db.execute_query(query, tuple(paginated_params), fetch_all=True)
    items = [AttachmentResponse(**r) for r in rows]

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


@router.get("/{attachment_id}", response_model=ApiResponse[AttachmentResponse])
async def get_attachment(attachment_id: int, admin=Depends(get_current_admin)):
    """Fetch single attachment by ID"""
    db = get_database_adapter()
    query = """
        SELECT 
            a.id, a.weapon_id, a.mode, a.code, a.name, a.image_file_id,
            a.is_top, a.is_season_top, a.order_index, a.views_count, a.shares_count,
            w.name as weapon_name,
            c.name as category_name,
            COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) as likes_count,
            COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) as dislikes_count
        FROM attachments a
        JOIN weapons w ON a.weapon_id = w.id
        JOIN weapon_categories c ON w.category_id = c.id
        LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id
        WHERE a.id = %s
        GROUP BY a.id, a.weapon_id, a.mode, a.code, a.name, a.image_file_id,
                 a.is_top, a.is_season_top, a.order_index, a.views_count, a.shares_count,
                 w.name, c.name
    """
    row = await db.execute_query(query, (attachment_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اتچمنت یافت نشد")
    return ApiResponse(success=True, data=AttachmentResponse(**row))


@router.post("", response_model=ApiResponse[AttachmentResponse])
async def create_attachment(
    payload: AttachmentCreate,
    admin=Depends(require_permission("manage_attachments_br")),
):
    """Create a new official attachment"""
    db = get_database_adapter()
    query = """
        INSERT INTO attachments (
            weapon_id, mode, code, name, image_file_id, is_top, is_season_top, order_index
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, weapon_id, mode, code, name, image_file_id, is_top, is_season_top, order_index, views_count, shares_count
    """
    try:
        row = await db.execute_query(
            query,
            (
                payload.weapon_id,
                payload.mode.lower(),
                payload.code.strip().upper(),
                payload.name.strip(),
                payload.image_file_id,
                payload.is_top,
                payload.is_season_top,
                payload.order_index,
            ),
            fetch_one=True,
        )
        return ApiResponse(
            success=True,
            message="اتچمنت با موفقیت ذخیره شد",
            data=AttachmentResponse(**row),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطا در ایجاد اتچمنت: ممکن است این کد در این سلاح و مود قبلاً ثبت شده باشد ({e})",
        )


@router.put("/{attachment_id}", response_model=ApiResponse[AttachmentResponse])
async def update_attachment(
    attachment_id: int,
    payload: AttachmentUpdate,
    admin=Depends(require_permission("manage_attachments_br")),
):
    """Update existing attachment"""
    db = get_database_adapter()
    updates = []
    params = []

    if payload.weapon_id is not None:
        updates.append("weapon_id = %s")
        params.append(payload.weapon_id)
    if payload.mode is not None:
        updates.append("mode = %s")
        params.append(payload.mode.lower())
    if payload.code is not None:
        updates.append("code = %s")
        params.append(payload.code.strip().upper())
    if payload.name is not None:
        updates.append("name = %s")
        params.append(payload.name.strip())
    if payload.image_file_id is not None:
        updates.append("image_file_id = %s")
        params.append(payload.image_file_id)
    if payload.is_top is not None:
        updates.append("is_top = %s")
        params.append(payload.is_top)
    if payload.is_season_top is not None:
        updates.append("is_season_top = %s")
        params.append(payload.is_season_top)
    if payload.order_index is not None:
        updates.append("order_index = %s")
        params.append(payload.order_index)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای ویرایش ارسال نشده است")

    params.append(attachment_id)
    query = f"""
        UPDATE attachments
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, weapon_id, mode, code, name, image_file_id, is_top, is_season_top, order_index, views_count, shares_count
    """
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اتچمنت یافت نشد")

    return ApiResponse(
        success=True,
        message="اتچمنت با موفقیت به‌روزرسانی شد",
        data=AttachmentResponse(**row),
    )


@router.delete("/{attachment_id}", response_model=ApiResponse[dict])
async def delete_attachment(
    attachment_id: int,
    admin=Depends(require_permission("manage_attachments_br")),
):
    """Delete an attachment"""
    db = get_database_adapter()
    query = "DELETE FROM attachments WHERE id = %s RETURNING id"
    row = await db.execute_query(query, (attachment_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اتچمنت یافت نشد")
    return ApiResponse(success=True, message="اتچمنت با موفقیت حذف شد")


@router.post("/{attachment_id}/toggle-top", response_model=ApiResponse[dict])
async def toggle_top(
    attachment_id: int,
    admin=Depends(require_permission("manage_attachments_br")),
):
    """Toggle is_top status"""
    db = get_database_adapter()
    query = """
        UPDATE attachments
        SET is_top = NOT is_top, updated_at = NOW()
        WHERE id = %s
        RETURNING is_top
    """
    row = await db.execute_query(query, (attachment_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اتچمنت یافت نشد")
    return ApiResponse(
        success=True,
        message="وضعیت اتچمنت برتر به‌روز شد",
        data={"is_top": row["is_top"]},
    )


@router.post("/{attachment_id}/toggle-season-top", response_model=ApiResponse[dict])
async def toggle_season_top(
    attachment_id: int,
    admin=Depends(require_permission("manage_attachments_br")),
):
    """Toggle is_season_top status"""
    db = get_database_adapter()
    query = """
        UPDATE attachments
        SET is_season_top = NOT is_season_top, updated_at = NOW()
        WHERE id = %s
        RETURNING is_season_top
    """
    row = await db.execute_query(query, (attachment_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="اتچمنت یافت نشد")
    return ApiResponse(
        success=True,
        message="وضعیت متای فصل به‌روز شد",
        data={"is_season_top": row["is_season_top"]},
    )
