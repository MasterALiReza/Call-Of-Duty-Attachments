from typing import Optional, List
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(..., description="Admin username or Telegram User ID")
    password: str = Field(..., description="Password")

class TelegramOtpLoginRequest(BaseModel):
    user_id: int = Field(..., description="Telegram User ID")
    otp_code: str = Field(..., description="One-time confirmation code")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "AdminUserResponse"

class AdminUserResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    is_super_admin: bool = False

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="رمز عبور فعلی")
    new_password: str = Field(..., min_length=6, description="رمز عبور جدید")

class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, description="نام نمایشی ادمین")

class AuditLogItem(BaseModel):
    id: str
    action: str
    details: str
    ip_address: str
    timestamp: str
    status: str

class AdminProfileResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    is_super_admin: bool = False
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    active_sessions_count: int = 1
