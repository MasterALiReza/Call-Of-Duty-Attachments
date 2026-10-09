from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from web.backend.app.schemas.common import ApiResponse
from web.backend.app.schemas.weapons_schema import (
    CategoryResponse,
    CategoryCreate,
    CategoryUpdate,
    WeaponResponse,
    WeaponCreate,
    WeaponUpdate,
)
from web.backend.app.auth import get_current_admin, require_permission
from core.database.database_adapter import get_database_adapter

router = APIRouter(prefix="/weapons", tags=["Weapons & Categories"])


# ─────────────────────────────────────────────────────────────
# Categories Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/categories", response_model=ApiResponse[List[CategoryResponse]])
async def list_categories(admin=Depends(get_current_admin)):
    """List all weapon categories with weapon and attachment counts"""
    db = get_database_adapter()
    query = """
        SELECT 
            c.id, c.name, c.display_name, c.icon, c.sort_order, c.is_active,
            COUNT(DISTINCT w.id) as weapon_count,
            COUNT(a.id) as attachment_count
        FROM weapon_categories c
        LEFT JOIN weapons w ON c.id = w.category_id
        LEFT JOIN attachments a ON w.id = a.weapon_id
        GROUP BY c.id, c.name, c.display_name, c.icon, c.sort_order, c.is_active
        ORDER BY c.sort_order ASC, c.id ASC
    """
    rows = await db.execute_query(query, fetch_all=True)
    items = [CategoryResponse(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("/categories", response_model=ApiResponse[CategoryResponse])
async def create_category(
    payload: CategoryCreate,
    admin=Depends(require_permission("manage_categories")),
):
    """Create a new weapon category"""
    db = get_database_adapter()
    query = """
        INSERT INTO weapon_categories (name, display_name, icon, sort_order, is_active)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, name, display_name, icon, sort_order, is_active
    """
    try:
        row = await db.execute_query(
            query,
            (
                payload.name.strip().lower(),
                payload.display_name or payload.name,
                payload.icon or "🔫",
                payload.sort_order,
                payload.is_active,
            ),
            fetch_one=True,
        )
        return ApiResponse(
            success=True,
            message="دسته‌بندی با موفقیت ایجاد شد",
            data=CategoryResponse(**row, weapon_count=0, attachment_count=0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطا در ایجاد دسته‌بندی: ممکن است نام تکراری باشد ({e})",
        )


@router.put("/categories/{category_id}", response_model=ApiResponse[CategoryResponse])
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    admin=Depends(require_permission("manage_categories")),
):
    """Update an existing weapon category"""
    db = get_database_adapter()
    updates = []
    params = []
    if payload.display_name is not None:
        updates.append("display_name = %s")
        params.append(payload.display_name)
    if payload.icon is not None:
        updates.append("icon = %s")
        params.append(payload.icon)
    if payload.sort_order is not None:
        updates.append("sort_order = %s")
        params.append(payload.sort_order)
    if payload.is_active is not None:
        updates.append("is_active = %s")
        params.append(payload.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای به‌روزرسانی ارسال نشده است")

    params.append(category_id)
    query = f"""
        UPDATE weapon_categories
        SET {', '.join(updates)}
        WHERE id = %s
        RETURNING id, name, display_name, icon, sort_order, is_active
    """
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد")

    return ApiResponse(
        success=True,
        message="دسته‌بندی با موفقیت به‌روزرسانی شد",
        data=CategoryResponse(**row),
    )


@router.delete("/categories/{category_id}", response_model=ApiResponse[dict])
async def delete_category(
    category_id: int,
    admin=Depends(require_permission("manage_categories")),
):
    """Delete a weapon category"""
    db = get_database_adapter()
    query = "DELETE FROM weapon_categories WHERE id = %s RETURNING id"
    row = await db.execute_query(query, (category_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد")
    return ApiResponse(success=True, message="دسته‌بندی با موفقیت حذف شد")


# ─────────────────────────────────────────────────────────────
# Weapons Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[List[WeaponResponse]])
async def list_weapons(
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = False,
    admin=Depends(get_current_admin),
):
    """List weapons with optional category and search filters"""
    db = get_database_adapter()
    where_clauses = []
    params = []

    if category_id:
        where_clauses.append("w.category_id = %s")
        params.append(category_id)
    if category_name:
        where_clauses.append("c.name = %s")
        params.append(category_name)
    if search:
        where_clauses.append("(w.name ILIKE %s OR w.display_name ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if active_only:
        where_clauses.append("w.is_active = TRUE")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT 
            w.id, w.category_id, w.name, w.display_name, w.is_active,
            c.name as category_name,
            COUNT(a.id) FILTER (WHERE a.mode = 'br') as attachment_count_br,
            COUNT(a.id) FILTER (WHERE a.mode = 'mp') as attachment_count_mp
        FROM weapons w
        JOIN weapon_categories c ON w.category_id = c.id
        LEFT JOIN attachments a ON w.id = a.weapon_id
        {where_sql}
        GROUP BY w.id, w.category_id, w.name, w.display_name, w.is_active, c.name, c.sort_order
        ORDER BY c.sort_order ASC, w.name ASC
    """
    rows = await db.execute_query(query, tuple(params), fetch_all=True)
    items = [WeaponResponse(**r) for r in rows]
    return ApiResponse(success=True, data=items)


@router.post("", response_model=ApiResponse[WeaponResponse])
async def create_weapon(
    payload: WeaponCreate,
    admin=Depends(require_permission("manage_categories")),
):
    """Create a new weapon"""
    db = get_database_adapter()
    query = """
        INSERT INTO weapons (category_id, name, display_name, is_active)
        VALUES (%s, %s, %s, %s)
        RETURNING id, category_id, name, display_name, is_active
    """
    try:
        row = await db.execute_query(
            query,
            (
                payload.category_id,
                payload.name.strip().upper(),
                payload.display_name or payload.name.strip(),
                payload.is_active,
            ),
            fetch_one=True,
        )
        return ApiResponse(
            success=True,
            message="سلاح با موفقیت ثبت شد",
            data=WeaponResponse(**row),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"خطا در افزودن سلاح: ممکن است نام سلاح در این دسته تکراری باشد ({e})",
        )


@router.put("/{weapon_id}", response_model=ApiResponse[WeaponResponse])
async def update_weapon(
    weapon_id: int,
    payload: WeaponUpdate,
    admin=Depends(require_permission("manage_categories")),
):
    """Update weapon metadata or category"""
    db = get_database_adapter()
    updates = []
    params = []

    if payload.category_id is not None:
        updates.append("category_id = %s")
        params.append(payload.category_id)
    if payload.name is not None:
        updates.append("name = %s")
        params.append(payload.name.strip().upper())
    if payload.display_name is not None:
        updates.append("display_name = %s")
        params.append(payload.display_name.strip())
    if payload.is_active is not None:
        updates.append("is_active = %s")
        params.append(payload.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="هیچ فیلدی برای به‌روزرسانی ارسال نشده است")

    params.append(weapon_id)
    query = f"""
        UPDATE weapons
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE id = %s
        RETURNING id, category_id, name, display_name, is_active
    """
    row = await db.execute_query(query, tuple(params), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="سلاح یافت نشد")
    return ApiResponse(
        success=True,
        message="سلاح با موفقیت به‌روزرسانی شد",
        data=WeaponResponse(**row),
    )


@router.delete("/{weapon_id}", response_model=ApiResponse[dict])
async def delete_weapon(
    weapon_id: int,
    admin=Depends(require_permission("manage_categories")),
):
    """Delete a weapon and its attachments"""
    db = get_database_adapter()
    query = "DELETE FROM weapons WHERE id = %s RETURNING id"
    row = await db.execute_query(query, (weapon_id,), fetch_one=True)
    if not row:
        raise HTTPException(status_code=404, detail="سلاح یافت نشد")
    return ApiResponse(success=True, message="سلاح با موفقیت حذف شد")
