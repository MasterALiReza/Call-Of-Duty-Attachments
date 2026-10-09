from typing import Optional, List
from pydantic import BaseModel, Field

class SubmissionResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    weapon_id: Optional[int] = None
    weapon_name: Optional[str] = None
    category: Optional[str] = None
    custom_weapon_name: Optional[str] = None
    mode: str
    attachment_name: str
    description: Optional[str] = None
    image_file_id: Optional[str] = None
    status: str
    submitted_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[int] = None
    rejected_at: Optional[str] = None
    rejected_by: Optional[int] = None
    rejection_reason: Optional[str] = None
    like_count: int = 0
    report_count: int = 0
    view_count: int = 0

class SubmissionReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: Optional[str] = None
    override_weapon_id: Optional[int] = None

class ReportResponse(BaseModel):
    id: int
    attachment_id: int
    attachment_name: Optional[str] = None
    author_id: Optional[int] = None
    reporter_id: int
    reporter_username: Optional[str] = None
    reason: Optional[str] = None
    status: str
    reported_at: Optional[str] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None

class ReportResolveRequest(BaseModel):
    action: str = Field(..., pattern="^(dismiss|resolve_delete|resolve_ban)$")
    resolution_notes: Optional[str] = None
    ban_reason: Optional[str] = None
