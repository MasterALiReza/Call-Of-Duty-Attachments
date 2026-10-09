from typing import Optional, List
from pydantic import BaseModel, Field

class CategoryBase(BaseModel):
    name: str = Field(..., description="Unique category slug (e.g. assault_rifle)")
    display_name: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    display_name: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class CategoryResponse(CategoryBase):
    id: int
    weapon_count: Optional[int] = 0
    attachment_count: Optional[int] = 0

class WeaponBase(BaseModel):
    category_id: int
    name: str = Field(..., description="Weapon name, e.g. AK47, M4")
    display_name: Optional[str] = None
    is_active: bool = True

class WeaponCreate(WeaponBase):
    pass

class WeaponUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None

class WeaponResponse(WeaponBase):
    id: int
    category_name: Optional[str] = None
    attachment_count_br: Optional[int] = 0
    attachment_count_mp: Optional[int] = 0

class AttachmentBase(BaseModel):
    weapon_id: int
    mode: str = Field("br", pattern="^(br|mp)$")
    code: str = Field(..., description="Loadout code")
    name: str = Field(..., description="Attachment title/build name")
    image_file_id: Optional[str] = None
    is_top: bool = False
    is_season_top: bool = False
    order_index: Optional[int] = None

class AttachmentCreate(AttachmentBase):
    pass

class AttachmentUpdate(BaseModel):
    weapon_id: Optional[int] = None
    mode: Optional[str] = Field(None, pattern="^(br|mp)$")
    code: Optional[str] = None
    name: Optional[str] = None
    image_file_id: Optional[str] = None
    is_top: Optional[bool] = None
    is_season_top: Optional[bool] = None
    order_index: Optional[int] = None

class AttachmentResponse(AttachmentBase):
    id: int
    weapon_name: Optional[str] = None
    category_name: Optional[str] = None
    views_count: int = 0
    shares_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    pop_score: Optional[float] = 0.0

class SuggestedAttachmentCreate(BaseModel):
    attachment_id: int
    mode: str = Field("br", pattern="^(br|mp)$")
    priority: int = 999
    reason: Optional[str] = None
    is_active: bool = True
