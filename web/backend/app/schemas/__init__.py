from .common import ApiResponse, PaginationMeta, PaginatedData
from .auth_schema import LoginRequest, TelegramOtpLoginRequest, TokenResponse, AdminUserResponse
from .dashboard_schema import DashboardStats, CategoryStat, ModeStat, SearchTrendItem, SystemHealthInfo
from .weapons_schema import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    WeaponCreate, WeaponUpdate, WeaponResponse,
    AttachmentCreate, AttachmentUpdate, AttachmentResponse,
    SuggestedAttachmentCreate
)
from .submissions_schema import SubmissionResponse, SubmissionReviewRequest, ReportResponse, ReportResolveRequest
from .tickets_schema import TicketResponse, TicketReplyCreateRequest, TicketStatusUpdateRequest, FAQCreate, FAQUpdate, FAQResponse
from .cms_schema import ChannelItem, ChannelCreate, ChannelUpdate, GuideItem, GuideCreate
from .broadcast_schema import BroadcastRequest, ScheduledNotificationItem, ScheduledNotificationCreate
from .system_schema import SystemSettingItem, SystemSettingUpdate, BlacklistWordItem, BlacklistWordCreate, HealthIssueItem, BackupFileItem
