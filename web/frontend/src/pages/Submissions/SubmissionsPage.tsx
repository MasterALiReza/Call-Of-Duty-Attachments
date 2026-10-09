import React, { useState, useEffect } from 'react';
import {
  Inbox,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Search,
  Eye,
  ThumbsUp,
  Flag,
  User,
  ShieldCheck,
  Ban,
  MessageSquare,
  Copy,
  Check,
  Sparkles,
  Layers,
  Crosshair,
  ExternalLink,
  Compass,
  Gamepad2,
  PartyPopper,
} from 'lucide-react';
import { api } from '../../services/api';
import { SubmissionItem, ReportItem, PaginatedResponse } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';

export const SubmissionsPage: React.FC = () => {
  const [submissions, setSubmissions] = useState<SubmissionItem[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedCodeId, setCopiedCodeId] = useState<number | null>(null);

  // Tabs & Filters
  const [activeTab, setActiveTab] = useState<'submissions' | 'reports'>('submissions');
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Review Reject Modal
  const [rejectTarget, setRejectTarget] = useState<SubmissionItem | null>(null);
  const [rejectionReason, setRejectionReason] = useState('عدم تطابق تصویر با مشخصات سلاح یا نامعتبر بودن کد لوداوت');

  // Preview Image Lightbox Modal
  const [previewItem, setPreviewItem] = useState<SubmissionItem | null>(null);

  const fetchSubmissions = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ success: boolean; data: PaginatedResponse<SubmissionItem> }>('/submissions', {
        params: {
          status_filter: statusFilter,
          search: searchQuery.trim() || undefined,
          page,
          page_size: 15,
        },
      });
      if (res.data?.data) {
        setSubmissions(res.data.data.items);
        setTotalPages(res.data.data.meta.total_pages);
        setTotalItems(res.data.data.meta.total_items);
      }
    } catch (err) {
      console.error('Failed to load submissions:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchReports = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ success: boolean; data: ReportItem[] }>('/submissions/reports');
      if (res.data?.data) {
        setReports(res.data.data);
      }
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'submissions') {
      fetchSubmissions();
    } else {
      fetchReports();
    }
  }, [activeTab, statusFilter, page]);

  const handleCopyCode = (id: number, code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  const handleApprove = async (sub: SubmissionItem) => {
    try {
      await api.post(`/submissions/${sub.id}/review`, {
        action: 'approve',
      });
      fetchSubmissions();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در تایید اتچمنت');
    }
  };

  const handleRejectConfirm = async () => {
    if (!rejectTarget) return;
    try {
      await api.post(`/submissions/${rejectTarget.id}/review`, {
        action: 'reject',
        rejection_reason: rejectionReason,
      });
      setRejectTarget(null);
      fetchSubmissions();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در رد اتچمنت');
    }
  };

  const handleResolveReport = async (reportId: number, action: 'dismiss' | 'resolve_delete') => {
    try {
      await api.post(`/submissions/reports/${reportId}/resolve`, {
        action,
        resolution_notes: action === 'dismiss' ? 'گزارش بررسی شد و مشکلی نداشت' : 'اتچمنت متخلف حذف شد',
      });
      fetchReports();
    } catch (err) {
      console.error(err);
    }
  };

  const rejectPresets = [
    'عدم تطابق تصویر با مشخصات سلاح یا نامعتبر بودن کد لوداوت',
    'کیفیت تصویر پایین یا ناخوانا بودن بخش‌های اتچمنت',
    'کد لوداوت اشتباه است و در بازی کار نمی‌کند',
    'اسپم یا محتوای نامربوط',
  ];

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER & TABS
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-accent/20 text-accent text-[10px] font-mono font-bold uppercase tracking-wider border border-accent/30">
              MODERATION STUDIO
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              اعتبارسنجی لوداوت‌های کاربران
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>صف بررسی و اعتدال اتچمنت‌های کاربران</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            بررسی کیفی، اعتبارسنجی تصاویر، تایید یا رد بیلدها و مدیریت گزارش‌های تخلف
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="p-1 rounded-2xl bg-card border border-border flex items-center gap-1 relative z-10 shadow-inner">
          <button
            onClick={() => setActiveTab('submissions')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 ${
              activeTab === 'submissions'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            صف سابمیشن‌ها ({statusFilter === 'pending' ? totalItems : ''})
          </button>
          <button
            onClick={() => setActiveTab('reports')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 flex items-center gap-1.5 ${
              activeTab === 'reports'
                ? 'bg-rose-500 text-white shadow-rose-500/20'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>گزارش‌های تخلف ({reports.length})</span>
          </button>
        </div>
      </div>

      {activeTab === 'submissions' ? (
        <>
          {/* ─────────────────────────────────────────────────────────────
              2. SUBMISSIONS FILTER TOOLBAR
             ───────────────────────────────────────────────────────────── */}
          <div className="glass-panel p-4 rounded-2xl border border-border flex flex-wrap items-center justify-between gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-mainText-subtle" />
              <input
                type="text"
                placeholder="جستجوی نام بیلد، توضیحات، سلاح یا نام کاربری ارسال‌کننده..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="w-full pr-10 pl-4 py-2 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary transition-all font-sans"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setStatusFilter('pending');
                  setPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition-all ${
                  statusFilter === 'pending'
                    ? 'bg-accent/20 text-accent border-accent/40 shadow-glow-accent'
                    : 'bg-card text-mainText-muted border-border hover:text-mainText'
                }`}
              >
                در انتظار بررسی
              </button>
              <button
                onClick={() => {
                  setStatusFilter('approved');
                  setPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition-all ${
                  statusFilter === 'approved'
                    ? 'bg-primary/20 text-primary border-primary/40 shadow-glow-primary'
                    : 'bg-card text-mainText-muted border-border hover:text-mainText'
                }`}
              >
                تایید شده‌ها
              </button>
              <button
                onClick={() => {
                  setStatusFilter('rejected');
                  setPage(1);
                }}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition-all ${
                  statusFilter === 'rejected'
                    ? 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-sm'
                    : 'bg-card text-mainText-muted border-border hover:text-mainText'
                }`}
              >
                رد شده‌ها
              </button>
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────
              3. SUBMISSIONS GRID (High-End Inspection Cards)
             ───────────────────────────────────────────────────────────── */}
          {loading ? (
            <div className="py-20 text-center text-mainText-muted">
              <span className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block mb-3" />
              <p className="text-xs">در حال بارگذاری سابمیشن‌های کاربران...</p>
            </div>
          ) : submissions.length === 0 ? (
            <div className="glass-panel p-12 rounded-3xl border border-border text-center space-y-3">
              <PartyPopper className="w-12 h-12 text-primary mx-auto" />
              <h3 className="text-sm font-bold text-mainText">صف بررسی خالی است</h3>
              <p className="text-xs text-mainText-subtle max-w-sm mx-auto">
                هیچ لوداوتی در وضعیت «{statusFilter}» وجود ندارد.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {submissions.map((sub) => (
                <div
                  key={sub.id}
                  className="p-1 rounded-[24px] bg-card border border-border hover:border-primary/50 transition-all duration-300 group shadow-sm hover:shadow-glow-primary"
                >
                  <div className="p-5 rounded-[20px] bg-card-surface/40 border border-border/40 flex flex-col justify-between h-full space-y-4">
                    {/* Header Row: Weapon & Mode & Status */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-lg font-black text-mainText font-mono">
                            {sub.weapon_name}
                          </span>
                          <Badge variant={sub.mode === 'br' ? 'primary' : 'secondary'}>
                            <span className="flex items-center gap-1">
                              {sub.mode === 'br' ? (
                                <Compass className="w-3 h-3 text-primary" />
                              ) : (
                                <Gamepad2 className="w-3 h-3 text-secondary" />
                              )}
                              <span>{sub.mode === 'br' ? 'بتل' : 'مولتی'}</span>
                            </span>
                          </Badge>
                        </div>
                        <p className="text-xs text-mainText-muted font-bold mt-1">
                          {sub.attachment_name}
                        </p>
                      </div>

                      {/* Status Badge */}
                      <Badge
                        variant={
                          sub.status === 'approved'
                            ? 'primary'
                            : sub.status === 'rejected'
                            ? 'danger'
                            : 'warning'
                        }
                      >
                        {sub.status === 'approved'
                          ? 'تایید شده'
                          : sub.status === 'rejected'
                          ? 'رد شده'
                          : 'در انتظار'}
                      </Badge>
                    </div>

                    {/* Middle: Description & Loadout Name */}
                    {sub.description && (
                      <p className="text-[11px] text-mainText-muted bg-card p-2.5 rounded-xl border border-border leading-relaxed">
                        {sub.description}
                      </p>
                    )}

                    {/* Submitter User Info & Date */}
                    <div className="flex items-center justify-between text-[11px] text-mainText-subtle pt-2 border-t border-border">
                      <span className="font-mono flex items-center gap-1">
                        <User className="w-3 h-3 text-mainText-subtle" />
                        <span>@{sub.username || sub.user_id}</span>
                      </span>
                      <span>
                        {sub.submitted_at
                          ? new Date(sub.submitted_at).toLocaleDateString('fa-IR')
                          : '-'}
                      </span>
                    </div>

                    {/* Actions Row */}
                    <div className="pt-3 border-t border-border flex items-center justify-between gap-2">
                      {sub.image_file_id && (
                        <button
                          onClick={() => setPreviewItem(sub)}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-card-surface hover:bg-card-hover text-mainText-muted hover:text-mainText text-xs font-medium transition-colors border border-border"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>تصویر</span>
                        </button>
                      )}

                      {sub.status === 'pending' && (
                        <div className="flex items-center gap-2 mr-auto">
                          <button
                            onClick={() => handleApprove(sub)}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>تایید بیلد</span>
                          </button>
                          <button
                            onClick={() => setRejectTarget(sub)}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-500 border border-rose-500/30 text-xs font-bold transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            <span>رد</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        /* ─────────────────────────────────────────────────────────────
            4. REPORTS TABLE
           ───────────────────────────────────────────────────────────── */
        <div className="glass-panel rounded-3xl border border-border overflow-hidden">
          <table className="w-full text-right text-xs">
            <thead className="bg-card-surface/70 border-b border-border text-mainText-muted font-semibold">
              <tr>
                <th className="px-6 py-4">گزارش‌دهنده</th>
                <th className="px-6 py-4">شناسه اتچمنت</th>
                <th className="px-6 py-4">علت گزارش تخلف</th>
                <th className="px-6 py-4">تاریخ</th>
                <th className="px-6 py-4">وضعیت</th>
                <th className="px-6 py-4 text-center">اقدام اعتدال</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-mainText-muted">
                    هیچ گزارش تخلف بازی وجود ندارد.
                  </td>
                </tr>
              ) : (
                reports.map((rep) => (
                  <tr key={rep.id} className="hover:bg-card-hover transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-mainText">
                      @{rep.reporter_username || rep.reporter_id}
                    </td>
                    <td className="px-6 py-4 font-mono text-primary font-bold">
                      #{rep.attachment_id}
                    </td>
                    <td className="px-6 py-4 text-mainText">{rep.reason}</td>
                    <td className="px-6 py-4 font-mono text-mainText-subtle">
                      {rep.reported_at
                        ? new Date(rep.reported_at).toLocaleDateString('fa-IR')
                        : '-'}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={rep.status === 'resolved' ? 'primary' : 'warning'}>
                        {rep.status === 'resolved' ? 'بررسی شد' : 'در انتظار'}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {rep.status === 'pending' ? (
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => handleResolveReport(rep.id, 'dismiss')}
                            className="px-2.5 py-1 rounded-lg bg-card-surface hover:bg-card-hover text-mainText-muted hover:text-mainText text-[11px] border border-border transition-colors"
                          >
                            رد گزارش
                          </button>
                          <button
                            onClick={() => handleResolveReport(rep.id, 'resolve_delete')}
                            className="px-2.5 py-1 rounded-lg bg-rose-500/20 text-rose-500 hover:bg-rose-500/30 border border-rose-500/30 text-[11px] font-bold transition-colors"
                          >
                            حذف اتچمنت
                          </button>
                        </div>
                      ) : (
                        <span className="text-mainText-subtle text-[11px]">مختومه</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          5. REJECT REASON MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title="رد لوداوت ارسالی کاربر"
        maxWidth="md"
      >
        <div className="space-y-4">
          <p className="text-xs text-mainText-muted">
            علت رد لوداوت را انتخاب یا وارد کنید تا در پیام به کاربر ارسال شود:
          </p>

          <div className="space-y-2">
            {rejectPresets.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setRejectionReason(preset)}
                className={`w-full p-2.5 rounded-xl border text-right text-xs transition-all ${
                  rejectionReason === preset
                    ? 'bg-accent/20 text-mainText border-accent/50 font-bold'
                    : 'bg-card text-mainText-muted border-border hover:text-mainText hover:bg-card-hover'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              متن اختصاصی علت رد:
            </label>
            <textarea
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              className="w-full p-3 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-rose-500"
            />
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setRejectTarget(null)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium"
            >
              انصراف
            </button>
            <button
              type="button"
              onClick={handleRejectConfirm}
              className="px-5 py-2 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-bold text-xs shadow-rose-500/20 transition-all"
            >
              ثبت رد و ارسال پیام
            </button>
          </div>
        </div>
      </Modal>

      {/* ─────────────────────────────────────────────────────────────
          6. IMAGE PREVIEW MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={!!previewItem}
        onClose={() => setPreviewItem(null)}
        title={`پیش‌نمایش تصویر لوداوت ${previewItem?.weapon_name || ''}`}
        maxWidth="lg"
      >
        <div className="space-y-4 text-center">
          <div className="p-4 rounded-2xl bg-card border border-border flex items-center justify-center min-h-[300px]">
            <p className="text-xs text-mainText-muted">
              شناسه فایل تلگرام: <code className="font-mono text-primary font-bold">{previewItem?.image_file_id}</code>
            </p>
          </div>
          <button
            onClick={() => setPreviewItem(null)}
            className="px-4 py-2 rounded-xl bg-card-surface hover:bg-card-hover text-mainText text-xs font-bold border border-border"
          >
            بستن
          </button>
        </div>
      </Modal>
    </div>
  );
};
