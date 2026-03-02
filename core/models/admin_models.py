from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class AttachmentBase(BaseModel):
    """Base model for attachment data validation."""
    name: str = Field(..., min_length=2, max_length=150, description="Attachment name")
    weapon_id: int = Field(..., gt=0, description="ID of the weapon")
    code: str = Field(..., min_length=3, max_length=50, description="Attachment loadout code")
    mode: str = Field(..., pattern="^(br|mp)$", description="Game mode (br or mp)")
    is_top: bool = Field(False, description="Whether it's a top attachment")
    is_season_top: bool = Field(False, description="Whether it's a season top attachment")

class AttachmentCreate(AttachmentBase):
    """Model for creating a new attachment."""
    image_file_id: Optional[str] = None

class AttachmentUpdate(AttachmentBase):
    """Model for updating an existing attachment."""
    id: int = Field(..., gt=0)
    image_file_id: Optional[str] = None

class UserModerationRequest(BaseModel):
    """Model for user moderation actions (ban/unban/role)."""
    user_id: int = Field(..., description="Telegram user ID")
    action: str = Field(..., pattern="^(ban|unban|role)$")
    reason: Optional[str] = Field(None, max_length=500)
    banned_until: Optional[datetime] = None

    @field_validator('banned_until')
    @classmethod
    def check_future_date(cls, v):
        if v and v < datetime.now():
            raise ValueError('Banned until date must be in the future')
        return v

class AdminNotificationRequest(BaseModel):
    """Model for broadcast notification requests."""
    message_type: str = Field(..., pattern="^(text|photo|broadcast)$")
    message_text: str = Field(..., min_length=1, max_length=4000)
    photo_file_id: Optional[str] = None
    parse_mode: str = Field("Markdown", pattern="^(Markdown|HTML|MarkdownV2)$")
    target_group: str = Field("all", pattern="^(all|active|inactive)$")
