from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class SystemSettingItem(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = "general"
    data_type: str = "string"
    updated_at: Optional[str] = None

class SystemSettingUpdate(BaseModel):
    value: str
    description: Optional[str] = None
    category: Optional[str] = None

class BlacklistWordItem(BaseModel):
    word: str
    category: str = "general"
    severity: int = 1
    created_at: Optional[str] = None

class BlacklistWordCreate(BaseModel):
    word: str
    category: str = "general"
    severity: int = 1

class HealthIssueItem(BaseModel):
    check_type: str
    severity: str
    category: Optional[str] = None
    issue_count: int
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

class BackupFileItem(BaseModel):
    filename: str
    size_bytes: int
    size_mb: float
    created_at: str
