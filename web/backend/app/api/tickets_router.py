from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from web.backend.app.schemas.common import ApiResponse, PaginatedData, PaginationMeta
from web.backend.app.schemas.tickets_schema import (
    TicketResponse,
    TicketReplyItem,
    TicketReplyCreateRequest,
    TicketStatusUpdateRequest,
    FAQResponse,
    FAQCreate,
    FAQUpdate,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/support", tags=["Tickets & FAQs Support Desk"])


# ─────────────────────────────────────────────────────────────
# Tickets Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/tickets", response_model=ApiResponse[PaginatedData[TicketResponse]])
async def list_tickets(
    status_filter: Optional[str] = Query(None, pattern="^(open|in_progress|waiting_user|resolved|closed|all)$"),
    priority: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
):
    """List support tickets with filtering and pagination"""
    db = get_database_adapter()
    where_clauses = []
    params = []

    if status_filter and status_filter != "all":
        where_clauses.append("t.status = %s")
        params.append(status_filter)
    if priority:
        where_clauses.append("t.priority = %s")
        params.append(priority)
    if search:
        where_clauses.append("(t.subject ILIKE %s OR t.description ILIKE %s OR u.username ILIKE %s)")
        search_pattern = f"%{search.strip()}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_query = f"""
        SELECT COUNT(*) as total
        FROM tickets t
        LEFT JOIN users u ON t.user_id = u.user_id
        {where_sql}
    """
    count_res = await db.execute_query(count_query, tuple(params), fetch_one=True)
    total_items = count_res["total"] if count_res else 0
    total_pages = (total_items + page_size - 1) // page_size or 1

    offset = (page - 1) * page_size
    query = f"""
        SELECT 
            t.id, t.user_id, t.category, t.subject, t.description, t.status, t.priority,
            t.assigned_to, t.created_at::text, t.updated_at::text, t.closed_at::text,
            u.username, u.first_name,
            adm.display_name as assigned_name,
            (SELECT COUNT(*) FROM ticket_replies tr WHERE tr.ticket_id = t.id) as replies_count
        FROM tickets t
        LEFT JOIN users u ON t.user_id = u.user_id
        LEFT JOIN admins adm ON t.assigned_to = adm.user_id
        {where_sql}
        ORDER BY 
            CASE t.priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                ELSE 4 
            END,
            t.created_at DESC
        LIMIT %s OFFSET %s
    """
    paginated_params = params + [page_size, offset]
    rows = await db.execute_query(query, tuple(paginated_params), fetch_all=True)
    items = [TicketResponse(**r) for r in rows]

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


@router.get("/tickets/{ticket_id}", response_model=ApiResponse[TicketResponse])
async def get_ticket_details(ticket_id: int, admin=Depends(get_current_admin)):
    """Fetch ticket details and full reply conversation thread"""
    db = get_database_adapter()
    query = """
        SELECT 
            t.id, t.user_id, t.category, t.subject, t.description, t.status, t.priority,
            t.assigned_to, t.created_at::text, t.updated_at::text, t.closed_at::text,
            u.username, u.first_name,
            adm.display_name as assigned_name
        FROM tickets t
        LEFT JOIN users u ON t.user_id = u.user_id
        LEFT JOIN admins adm ON t.assigned_to = adm.user_id
        WHERE t.id = %s
    """
    row = await db.execute_query(query, (ticket_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")

    # Fetch replies
    replies_query = """
        SELECT 
            tr.id, tr.ticket_id, tr.user_id, tr.message, tr.is_admin, tr.attachments,
            tr.created_at::text,
            u.username, u.first_name
        FROM ticket_replies tr
        LEFT JOIN users u ON tr.user_id = u.user_id
        WHERE tr.ticket_id = %s
        ORDER BY tr.created_at ASC
    """
    replies_rows = await db.execute_query(replies_query, (ticket_id,), fetch_all=True)
    replies = [TicketReplyItem(**r) for r in replies_rows]

    ticket_data = TicketResponse(**row, replies_count=len(replies), replies=replies)
    return ApiResponse(success=True, data=ticket_data)


@router.post("/tickets/{ticket_id}/reply", response_model=ApiResponse[dict])
async def reply_to_ticket(
    ticket_id: int,
    payload: TicketReplyCreateRequest,
    admin=Depends(require_permission("manage_tickets")),
):
    """Admin reply to ticket and optionally close it"""
    db = get_database_adapter()

    # Verify ticket exists
    ticket = await db.execute_query("SELECT user_id, status FROM tickets WHERE id = %s", (ticket_id,), fetch_one=True)
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")

    # Insert reply
    insert_reply = """
        INSERT INTO ticket_replies (ticket_id, user_id, message, is_admin, created_at)
        VALUES (%s, %s, %s, TRUE, NOW())
        RETURNING id
    """
    await db.execute_query(insert_reply, (ticket_id, admin.user_id, payload.message))

    # Update ticket status
    new_status = "closed" if payload.close_ticket else "in_progress"
    update_ticket = """
        UPDATE tickets
        SET status = %s, updated_at = NOW(), assigned_to = COALESCE(assigned_to, %s)
        WHERE id = %s
    """
    await db.execute_query(update_ticket, (new_status, admin.user_id, ticket_id))

    return ApiResponse(success=True, message="پاسخ با موفقیت ثبت شد")


@router.patch("/tickets/{ticket_id}/status", response_model=ApiResponse[dict])
async def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdateRequest,
    admin=Depends(require_permission("manage_tickets")),
):
    """Update ticket priority, status or assignment"""
    db = get_database_adapter()
    updates = []
    params = []

    if payload.status:
        updates.append("status = %s")
        params.append(payload.status)
        if payload.status == "closed":
            updates.append("closed_at = NOW()")
    if payload.priority:
        updates.append("priority = %s")
        params.append(payload.priority)
    if payload.assigned_to is not None:
        updates.append("assigned_to = %s")
        params.append(payload.assigned_to)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای به‌روزرسانی ارسال نشده است")

    params.append(ticket_id)
    query = f"UPDATE tickets SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s RETURNING id"
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")

    return ApiResponse(success=True, message="وضعیت تیکت به‌روزرسانی شد")


# ─────────────────────────────────────────────────────────────
# FAQ Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/faqs", response_model=ApiResponse[List[FAQResponse]])
async def list_faqs(
    category: Optional[str] = None,
    language: Optional[str] = None,
    admin=Depends(get_current_admin),
):
    """List frequently asked questions"""
    db = get_database_adapter()
    where = []
    params = []
    if category:
        where.append("category = %s")
        params.append(category)
    if language:
        where.append("language = %s")
        params.append(language)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    query = f"""
        SELECT 
            id, question, answer, category, language, views,
            helpful_count, not_helpful_count, is_active, created_at::text
        FROM faqs
        {where_sql}
        ORDER BY id ASC
    """
    rows = await db.execute_query(query, tuple(params), fetch_all=True)
    items = [FAQResponse(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/faqs", response_model=ApiResponse[FAQResponse])
async def create_faq(
    payload: FAQCreate,
    admin=Depends(require_permission("manage_texts")),
):
    """Create a new FAQ entry"""
    db = get_database_adapter()
    query = """
        INSERT INTO faqs (question, answer, category, language, is_active)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, question, answer, category, language, views, helpful_count, not_helpful_count, is_active, created_at::text
    """
    try:
        row = await db.execute_query(
            query,
            (payload.question.strip(), payload.answer.strip(), payload.category, payload.language, payload.is_active),
            fetch_one=True,
        )
        return ApiResponse(success=True, message="سوال با موفقیت افزوده شد", data=FAQResponse(**row))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در ثبت FAQ: {e}")


@router.put("/faqs/{faq_id}", response_model=ApiResponse[FAQResponse])
async def update_faq(
    faq_id: int,
    payload: FAQUpdate,
    admin=Depends(require_permission("manage_texts")),
):
    """Update existing FAQ entry"""
    db = get_database_adapter()
    updates = []
    params = []
    if payload.question is not None:
        updates.append("question = %s")
        params.append(payload.question.strip())
    if payload.answer is not None:
        updates.append("answer = %s")
        params.append(payload.answer.strip())
    if payload.category is not None:
        updates.append("category = %s")
        params.append(payload.category)
    if payload.language is not None:
        updates.append("language = %s")
        params.append(payload.language)
    if payload.is_active is not None:
        updates.append("is_active = %s")
        params.append(payload.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای ویرایش ارسال نشده است")

    params.append(faq_id)
    query = f"""
        UPDATE faqs
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, question, answer, category, language, views, helpful_count, not_helpful_count, is_active, created_at::text
    """
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="سوال یافت نشد")
    return ApiResponse(success=True, message="سوال با موفقیت ویرایش شد", data=FAQResponse(**row))


@router.delete("/faqs/{faq_id}", response_model=ApiResponse[dict])
async def delete_faq(
    faq_id: int,
    admin=Depends(require_permission("manage_texts")),
):
    """Delete an FAQ entry"""
    db = get_database_adapter()
    query = "DELETE FROM faqs WHERE id = %s RETURNING id"
    row = await db.execute_query(query, (faq_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="سوال یافت نشد")
    return ApiResponse(success=True, message="سوال با موفقیت حذف شد")
