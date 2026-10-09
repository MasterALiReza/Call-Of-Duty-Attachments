from typing import Optional, List
from pydantic import BaseModel, Field

class TicketReplyItem(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    message: str
    is_admin: bool = False
    attachments: Optional[List[str]] = []
    created_at: Optional[str] = None

class TicketResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    category: Optional[str] = None
    subject: str
    description: Optional[str] = None
    status: str
    priority: str
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    replies_count: int = 0
    replies: Optional[List[TicketReplyItem]] = []

class TicketStatusUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(open|in_progress|waiting_user|resolved|closed)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    assigned_to: Optional[int] = None

class TicketReplyCreateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    close_ticket: bool = False

class FAQBase(BaseModel):
    question: str
    answer: str
    category: Optional[str] = "general"
    language: str = Field("fa", pattern="^(fa|en)$")
    is_active: bool = True

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    is_active: Optional[bool] = None

class FAQResponse(FAQBase):
    id: int
    views: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    created_at: Optional[str] = None
