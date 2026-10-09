from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class BroadcastRequest(BaseModel):
    message_text: str = Field(..., min_length=1, max_length=4000)
    parse_mode: str = Field("HTML", pattern="^(HTML|Markdown|MarkdownV2|plain)$")
    photo_file_id: Optional[str] = None
    target_modes: Optional[List[str]] = None  # ['br', 'mp']
    target_language: Optional[str] = None     # 'fa', 'en', or None for all
    buttons: Optional[List[Dict[str, str]]] = None  # [{"text": "...", "url": "..."}]
    safe_speed_delay: float = 0.05            # seconds between messages

class ScheduledNotificationItem(BaseModel):
    id: int
    message_type: str
    message_text: str
    photo_file_id: Optional[str] = None
    parse_mode: Optional[str] = "HTML"
    interval_hours: int
    enabled: bool
    last_sent_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[str] = None

class ScheduledNotificationCreate(BaseModel):
    message_type: str = Field("text", pattern="^(text|photo)$")
    message_text: str = Field(..., min_length=1)
    photo_file_id: Optional[str] = None
    parse_mode: str = "HTML"
    interval_hours: int = Field(24, ge=1, le=720)
    enabled: bool = True
