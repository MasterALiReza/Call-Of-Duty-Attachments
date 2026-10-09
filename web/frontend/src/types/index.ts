export interface AdminUser {
  user_id: number;
  username?: string;
  display_name?: string;
  roles: string[];
  permissions: string[];
  is_super_admin: boolean;
}

export interface AdminProfile extends AdminUser {
  created_at?: string;
  last_login?: string;
  active_sessions_count: number;
}

export interface AuditLog {
  id: string;
  action: string;
  details: string;
  ip_address: string;
  timestamp: string;
  status: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AdminUser;
}

export interface DashboardStats {
  total_users: number;
  new_users_today: number;
  active_users_week: number;
  total_weapons: number;
  total_attachments: number;
  pending_submissions: number;
  open_tickets: number;
  pending_reports: number;
  total_views: number;
  total_likes: number;
  system_health_score: number;
}

export interface CategoryStat {
  category_id: number;
  name: string;
  display_name: string;
  weapon_count: number;
  attachment_count: number;
}

export interface ModeStat {
  mode: string;
  count: number;
  percentage: number;
}

export interface SearchTrendItem {
  query: string;
  search_count: number;
  last_searched?: string;
}

export interface SystemHealthInfo {
  status: string;
  database_connected: boolean;
  pool_size: number;
  pool_available: number;
  cpu_percent: number;
  memory_percent: number;
  uptime_seconds: number;
}

export interface CategoryItem {
  id: number;
  name: string;
  display_name: string;
  icon?: string;
  sort_order: number;
  is_active: boolean;
  weapon_count?: number;
  attachment_count?: number;
}

export interface WeaponItem {
  id: number;
  category_id: number;
  name: string;
  display_name?: string;
  is_active: boolean;
  category_name?: string;
  attachment_count_br?: number;
  attachment_count_mp?: number;
}

export interface AttachmentItem {
  id: number;
  weapon_id: number;
  mode: 'br' | 'mp';
  code: string;
  name: string;
  image_file_id?: string;
  is_top: boolean;
  is_season_top: boolean;
  order_index?: number;
  views_count: number;
  shares_count: number;
  weapon_name?: string;
  category_name?: string;
  likes_count?: number;
  dislikes_count?: number;
}

export interface SubmissionItem {
  id: number;
  user_id: number;
  username?: string;
  first_name?: string;
  weapon_id?: number;
  weapon_name?: string;
  category?: string;
  custom_weapon_name?: string;
  mode: 'br' | 'mp';
  attachment_name: string;
  description?: string;
  image_file_id?: string;
  status: 'pending' | 'approved' | 'rejected' | 'deleted';
  submitted_at?: string;
  approved_at?: string;
  approved_by?: number;
  rejected_at?: string;
  rejected_by?: number;
  rejection_reason?: string;
  like_count: number;
  report_count: number;
  view_count: number;
}

export interface ReportItem {
  id: number;
  attachment_id: number;
  attachment_name?: string;
  author_id?: number;
  reporter_id: number;
  reporter_username?: string;
  reason?: string;
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  reported_at?: string;
  resolved_by?: number;
  resolved_at?: string;
  resolution_notes?: string;
}

export interface TicketReplyItem {
  id: number;
  ticket_id: number;
  user_id: number;
  username?: string;
  first_name?: string;
  message: string;
  is_admin: boolean;
  attachments?: string[];
  created_at?: string;
}

export interface TicketItem {
  id: number;
  user_id: number;
  username?: string;
  first_name?: string;
  category?: string;
  subject: string;
  description?: string;
  status: 'open' | 'in_progress' | 'waiting_user' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  assigned_to?: number;
  assigned_name?: string;
  created_at?: string;
  updated_at?: string;
  closed_at?: string;
  replies_count: number;
  replies?: TicketReplyItem[];
}

export interface FAQItem {
  id: number;
  question: string;
  answer: string;
  category?: string;
  language: 'fa' | 'en';
  views: number;
  helpful_count: number;
  not_helpful_count: number;
  is_active: boolean;
  created_at?: string;
}

export interface ChannelItem {
  channel_id: string;
  title: string;
  url: string;
  priority: number;
  is_active: boolean;
  created_at?: string;
}

export interface ScheduledNotificationItem {
  id: number;
  message_type: 'text' | 'photo';
  message_text: string;
  photo_file_id?: string;
  parse_mode?: string;
  interval_hours: number;
  enabled: boolean;
  last_sent_at?: string;
  next_run_at?: string;
  created_by?: number;
  created_at?: string;
}

export interface SystemSettingItem {
  key: string;
  value?: string;
  description?: string;
  category?: string;
  data_type: string;
  updated_at?: string;
}

export interface BlacklistWordItem {
  word: string;
  category: string;
  severity: number;
  created_at?: string;
}

export interface BackupFileItem {
  filename: string;
  size_bytes: number;
  size_mb: number;
  created_at: string;
}

export interface HealthIssueItem {
  check_type: string;
  severity: string;
  category?: string;
  issue_count: number;
  details?: Record<string, any>;
  created_at?: string;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}
