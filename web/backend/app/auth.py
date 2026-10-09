"""
Authentication and Authorization Module
JWT token management and RBAC dependencies for FastAPI
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

# Add project root to sys.path to allow importing core modules
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.backend.app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    PANEL_ADMIN_USERNAME,
    PANEL_ADMIN_PASSWORD,
)
from core.database.database_adapter import get_database_adapter
from core.security.role_manager import RoleManager, get_role_manager
from web.backend.app.schemas.auth_schema import AdminUserResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password.startswith("$2b$") and not hashed_password.startswith("$2a$"):
        # Fallback for plaintext configured in env
        return plain_password == hashed_password
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> AdminUserResponse:
    """Dependency to retrieve and authenticate current admin from Bearer token"""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توکن احراز هویت ارسال نشده است",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توکن نامعتبر یا منقضی شده است",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="شناسه کاربر در توکن یافت نشد",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Super Admin Bootstrap User
    if user_id == 1 and payload.get("username") == PANEL_ADMIN_USERNAME:
        return AdminUserResponse(
            user_id=1,
            username=PANEL_ADMIN_USERNAME,
            display_name="مدیر کل سیستم (Super Admin)",
            roles=["super_admin"],
            permissions=["all"],
            is_super_admin=True,
        )

    # Resolve from DB
    db = get_database_adapter()
    role_mgr = get_role_manager(db)

    is_admin = await role_mgr.is_admin(int(user_id))
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی ادمین برای این کاربر یافت نشد",
        )

    user_roles = await role_mgr.get_user_roles(int(user_id))
    user_perms = await role_mgr.get_user_permissions(int(user_id))
    is_super = await role_mgr.is_super_admin(int(user_id))

    return AdminUserResponse(
        user_id=int(user_id),
        username=payload.get("username"),
        display_name=payload.get("display_name") or f"Admin {user_id}",
        roles=[r.name for r in user_roles],
        permissions=[p.value for p in user_perms],
        is_super_admin=is_super,
    )


def require_permission(permission: str):
    """Dependency factory for checking specific permission"""
    async def permission_checker(admin: AdminUserResponse = Depends(get_current_admin)):
        if admin.is_super_admin or "all" in admin.permissions:
            return admin
        if permission in admin.permissions:
            return admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"شما دسترسی لازم برای این عملیات را ندارید ({permission})",
        )
    return permission_checker
