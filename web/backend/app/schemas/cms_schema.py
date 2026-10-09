from typing import Optional, List
from pydantic import BaseModel, Field

class ChannelItem(BaseModel):
    channel_id: str
    title: str
    url: str
    priority: int = 999
    is_active: bool = True
    member_count: Optional[int] = 0
    created_at: Optional[str] = None

class ChannelCreate(BaseModel):
    channel_id: str = Field(..., description="@channel_username or -100xxxx id")
    title: str
    url: str
    priority: int = 999
    is_active: bool = True

class ChannelUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class GuideMediaItem(BaseModel):
    id: Optional[int] = None
    media_type: str = Field(..., pattern="^(photo|video)$")
    file_id: str
    caption: Optional[str] = None
    order_index: int = 0

class GuideItem(BaseModel):
    id: int
    key: str
    mode: str
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    media: Optional[List[GuideMediaItem]] = []

class GuideCreate(BaseModel):
    key: str
    mode: str = Field("br", pattern="^(br|mp)$")
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
