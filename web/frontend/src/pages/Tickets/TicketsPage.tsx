import React, { useState, useEffect } from 'react';
import {
  LifeBuoy,
  MessageSquare,
  Send,
  CheckCircle,
  Clock,
  AlertCircle,
  HelpCircle,
  Plus,
  Search,
  User,
  Shield,
  ThumbsUp,
  ThumbsDown,
  Edit2,
  Trash2,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '../../services/api';
import { TicketItem, TicketReplyItem, FAQItem, PaginatedResponse } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';

export const TicketsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'tickets' | 'faqs'>('tickets');
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<TicketItem | null>(null);
  const [replies, setReplies] = useState<TicketReplyItem[]>([]);
  const [replyMessage, setReplyMessage] = useState('');
  const [closeOnReply, setCloseOnReply] = useState(false);
  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<'open' | 'in_progress' | 'waiting_user' | 'resolved' | 'closed' | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<'critical' | 'high' | 'medium' | 'low' | 'all'>('all');
  const [faqSearchQuery, setFaqSearchQuery] = useState('');
  const [expandedFaqId, setExpandedFaqId] = useState<number | null>(null);

  // FAQ Modal
  const [isFaqModalOpen, setIsFaqModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQItem | null>(null);
  const [faqForm, setFaqForm] = useState({
    question: '',
    answer: '',
    category: 'general',
    language: 'fa' as 'fa' | 'en',
    is_active: true,
  });

  const fetchTickets = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page: 1, page_size: 30 };
      if (statusFilter !== 'all') params.status_filter = statusFilter;
      if (priorityFilter !== 'all') params.priority = priorityFilter;

      const res = await api.get<{ success: boolean; data: PaginatedResponse<TicketItem> }>('/support/tickets', {
        params,
      });
      if (res.data?.data) {
        setTickets(res.data.data.items);
        if (res.data.data.items.length > 0 && !selectedTicket) {
          handleSelectTicket(res.data.data.items[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load tickets:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFaqs = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ success: boolean; data: FAQItem[] }>('/support/faqs');
      if (res.data?.data) {
        setFaqs(res.data.data);
      }
    } catch (err) {
      console.error('Failed to load faqs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTicket = async (ticket: TicketItem) => {
    setSelectedTicket(ticket);
    try {
      const res = await api.get<{ success: boolean; data: TicketItem }>(`/support/tickets/${ticket.id}`);
      if (res.data?.data) {
        setReplies(res.data.data.replies || []);
      }
    } catch (err) {
      console.error('Failed to load ticket thread:', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'tickets') {
      fetchTickets();
    } else {
      fetchFaqs();
    }
  }, [activeTab, statusFilter, priorityFilter]);

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || !replyMessage.trim()) return;

    try {
      await api.post(`/support/tickets/${selectedTicket.id}/reply`, {
        message: replyMessage.trim(),
        close_ticket: closeOnReply,
      });
      setReplyMessage('');
      handleSelectTicket(selectedTicket);
      fetchTickets();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ارسال پاسخ');
    }
  };

  const handleSaveFaq = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingFaq) {
        await api.put(`/support/faqs/${editingFaq.id}`, faqForm);
      } else {
        await api.post('/support/faqs', faqForm);
      }
      setIsFaqModalOpen(false);
      fetchFaqs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت FAQ');
    }
  };

  const handleDeleteFaq = async (id: number) => {
    if (!confirm('آیا از حذف این سوال متداول اطمینان دارید؟')) return;
    try {
      await api.delete(`/support/faqs/${id}`);
      fetchFaqs();
    } catch (err) {
      console.error(err);
    }
  };

  const cannedReplies = [
    'سلام دوست عزیز، درخواست شما بررسی و اتچمنت مورد نظر در ربات ثبت شد ✅',
    'لطفا نام دقیق انگلیسی سلاح و کد اشتراک‌گذاری داخل بازی را ارسال کنید 🔫',
    'با تشکر از گزارش شما، مشکل به بخش فنی ارجاع داده شد و برطرف گردید 🛠️',
  ];

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'critical':
        return <Badge variant="danger">بحرانی</Badge>;
      case 'high':
        return <Badge variant="warning">فوری</Badge>;
      case 'medium':
        return <Badge variant="secondary">عادی</Badge>;
      default:
        return <Badge variant="ghost">پایین</Badge>;
    }
  };

  const filteredFaqs = faqs.filter(
    (f) =>
      f.question.toLowerCase().includes(faqSearchQuery.toLowerCase()) ||
      f.answer.toLowerCase().includes(faqSearchQuery.toLowerCase()) ||
      f.category.toLowerCase().includes(faqSearchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER & TABS
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/30">
              SUPPORT CENTER
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              پاسخگویی زنده به تیکت‌ها و پایگاه دانش
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>میز خدمت، تیکتینگ و پایگاه دانش</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            ارتباط مستقیم با کاربران ربات، پاسخگویی به درخواست‌ها و مدیریت سوالات متداول FAQ
          </p>
        </div>

        <div className="flex items-center gap-3 relative z-10">
          <div className="p-1 rounded-2xl bg-card border border-border flex items-center gap-1 shadow-inner">
            <button
              onClick={() => setActiveTab('tickets')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 ${
                activeTab === 'tickets'
                  ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                  : 'text-mainText-muted hover:text-mainText'
              }`}
            >
              تیکت‌های کاربران ({tickets.length})
            </button>
            <button
              onClick={() => setActiveTab('faqs')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 ${
                activeTab === 'faqs'
                  ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                  : 'text-mainText-muted hover:text-mainText'
              }`}
            >
              بانک سوالات FAQ ({faqs.length})
            </button>
          </div>

          {activeTab === 'faqs' && (
            <button
              onClick={() => {
                setEditingFaq(null);
                setFaqForm({
                  question: '',
                  answer: '',
                  category: 'general',
                  language: 'fa',
                  is_active: true,
                });
                setIsFaqModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>افزودن FAQ</span>
            </button>
          )}
        </div>
      </div>

      {activeTab === 'tickets' ? (
        /* ─────────────────────────────────────────────────────────────
            2. SPLIT-PANE TICKETS WORKBENCH
           ───────────────────────────────────────────────────────────── */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[720px]">
          {/* Tickets Sidebar (5 cols in RTL) */}
          <div className="lg:col-span-5 glass-panel rounded-3xl border border-border flex flex-col overflow-hidden">
            {/* Filter Toolbar */}
            <div className="p-3 border-b border-border bg-card-surface/40 flex items-center justify-between gap-2.5">
              <div className="flex-1">
                <Select<'open' | 'in_progress' | 'waiting_user' | 'resolved' | 'closed' | 'all'>
                  size="sm"
                  value={statusFilter}
                  onChange={(val) => setStatusFilter(val)}
                  options={[
                    { value: 'all', label: 'همه وضعیت‌ها' },
                    {
                      value: 'open',
                      label: 'تیکت‌های باز',
                      badge: <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />,
                    },
                    {
                      value: 'in_progress',
                      label: 'در حال بررسی',
                      badge: <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />,
                    },
                    {
                      value: 'waiting_user',
                      label: 'منتظر پاسخ کاربر',
                      badge: <span className="w-2 h-2 rounded-full bg-sky-400 inline-block" />,
                    },
                    {
                      value: 'resolved',
                      label: 'حل شده',
                      badge: <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />,
                    },
                    {
                      value: 'closed',
                      label: 'بسته شده',
                      badge: <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />,
                    },
                  ]}
                />
              </div>

              <div className="flex-1">
                <Select<'critical' | 'high' | 'medium' | 'low' | 'all'>
                  size="sm"
                  value={priorityFilter}
                  onChange={(val) => setPriorityFilter(val)}
                  options={[
                    { value: 'all', label: 'همه اولویت‌ها' },
                    {
                      value: 'critical',
                      label: 'بحرانی',
                      badge: <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />,
                    },
                    {
                      value: 'high',
                      label: 'فوری',
                      badge: <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />,
                    },
                    {
                      value: 'medium',
                      label: 'عادی',
                      badge: <span className="w-2 h-2 rounded-full bg-primary inline-block" />,
                    },
                    {
                      value: 'low',
                      label: 'پایین',
                      badge: <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />,
                    },
                  ]}
                />
              </div>
            </div>

            {/* Ticket List Items */}
            <div className="flex-1 overflow-y-auto divide-y divide-border p-2 scrollbar-none">
              {loading ? (
                <div className="p-8 text-center text-mainText-muted text-xs">
                  در حال بارگذاری تیکت‌ها...
                </div>
              ) : tickets.length === 0 ? (
                <div className="p-8 text-center text-mainText-muted text-xs">
                  تیکتی با این فیلترها یافت نشد.
                </div>
              ) : (
                tickets.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => handleSelectTicket(t)}
                    className={`p-4 rounded-2xl cursor-pointer transition-all ${
                      selectedTicket?.id === t.id
                        ? 'bg-primary/15 border border-primary/40 shadow-glow-primary'
                        : 'hover:bg-card-hover border border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-mainText text-xs truncate max-w-[200px]">
                        {t.subject}
                      </span>
                      {getPriorityBadge(t.priority)}
                    </div>

                    <p className="text-mainText-muted text-[11px] truncate mt-1">
                      {t.description || 'بدون متن اولیه'}
                    </p>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-border text-[11px] text-mainText-subtle">
                      <span className="font-mono">@{t.username || t.user_id}</span>
                      <span>
                        {t.created_at
                          ? new Date(t.created_at).toLocaleDateString('fa-IR')
                          : '-'}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Conversation & Reply Thread (7 cols) */}
          <div className="lg:col-span-7 glass-panel rounded-3xl border border-border flex flex-col overflow-hidden">
            {selectedTicket ? (
              <>
                {/* Active Ticket Header */}
                <div className="p-5 border-b border-border bg-card-surface/70 flex items-center justify-between">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-sm text-mainText">
                        {selectedTicket.subject}
                      </h3>
                      {getPriorityBadge(selectedTicket.priority)}
                    </div>
                    <span className="text-[11px] text-mainText-subtle font-mono mt-0.5">
                      کاربر: @{selectedTicket.username || selectedTicket.user_id} (ID: {selectedTicket.user_id})
                    </span>
                  </div>

                  <Badge
                    variant={
                      selectedTicket.status === 'closed' || selectedTicket.status === 'resolved'
                        ? 'ghost'
                        : 'primary'
                    }
                  >
                    {selectedTicket.status === 'closed'
                      ? 'بسته شده'
                      : selectedTicket.status === 'in_progress'
                      ? 'در حال بررسی'
                      : 'باز'}
                  </Badge>
                </div>

                {/* Messages Thread Box */}
                <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-card-surface/20 scrollbar-none">
                  {/* Original Ticket Description */}
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-secondary/20 text-secondary flex items-center justify-center font-bold text-xs shrink-0">
                      <User className="w-4 h-4 text-secondary" />
                    </div>
                    <div className="flex-1 p-4 rounded-2xl bg-card border border-border text-xs text-mainText leading-relaxed shadow-sm">
                      <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-border text-[10px] text-mainText-subtle">
                        <span className="font-bold text-mainText">
                          @{selectedTicket.username || selectedTicket.user_id}
                        </span>
                        <span>
                          {selectedTicket.created_at
                            ? new Date(selectedTicket.created_at).toLocaleTimeString('fa-IR')
                            : ''}
                        </span>
                      </div>
                      <p>{selectedTicket.description}</p>
                    </div>
                  </div>

                  {/* Replies */}
                  {replies.map((r) => (
                    <div
                      key={r.id}
                      className={`flex items-start gap-3 ${
                        r.is_admin ? 'flex-row-reverse' : ''
                      }`}
                    >
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                          r.is_admin
                            ? 'bg-primary/20 text-primary'
                            : 'bg-secondary/20 text-secondary'
                        }`}
                      >
                        {r.is_admin ? (
                          <Shield className="w-4 h-4 text-primary" />
                        ) : (
                          <User className="w-4 h-4 text-secondary" />
                        )}
                      </div>
                      <div
                        className={`max-w-[80%] p-4 rounded-2xl text-xs leading-relaxed ${
                          r.is_admin
                            ? 'bg-primary/15 border border-primary/30 text-mainText font-medium'
                            : 'bg-card border border-border text-mainText'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5 text-[10px] text-mainText-subtle gap-4">
                          <span className="font-bold text-mainText">
                            {r.is_admin ? 'پشتیبان سیستم' : `@${selectedTicket.username}`}
                          </span>
                          <span>
                            {r.created_at
                              ? new Date(r.created_at).toLocaleTimeString('fa-IR')
                              : ''}
                          </span>
                        </div>
                        <p>{r.message}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Reply Composer & Canned Replies */}
                <div className="p-4 border-t border-border bg-card-surface/40 space-y-3">
                  {/* Canned Quick Replies */}
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                    <span className="text-[10px] text-mainText-muted shrink-0">پاسخ‌های سریع:</span>
                    {cannedReplies.map((text, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setReplyMessage(text)}
                        className="px-2.5 py-1 rounded-lg bg-card hover:bg-card-hover text-mainText-muted hover:text-mainText text-[10px] shrink-0 transition-colors border border-border"
                      >
                        {text.slice(0, 32)}...
                      </button>
                    ))}
                  </div>

                  {/* Input Form */}
                  <form onSubmit={handleSendReply} className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="متن پاسخ پشتیبانی را بنویسید..."
                        value={replyMessage}
                        onChange={(e) => setReplyMessage(e.target.value)}
                        className="flex-1 px-4 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary transition-all font-sans"
                      />
                      <button
                        type="submit"
                        className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary flex items-center gap-1.5 transition-all"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>ارسال</span>
                      </button>
                    </div>

                    <label className="flex items-center gap-2 cursor-pointer text-xs text-mainText-muted pt-1">
                      <input
                        type="checkbox"
                        checked={closeOnReply}
                        onChange={(e) => setCloseOnReply(e.target.checked)}
                        className="w-3.5 h-3.5 rounded text-primary bg-card border-border"
                      />
                      <span>همزمان با ارسال پاسخ، تیکت به وضعیت «بسته شده» تغییر کند</span>
                    </label>
                  </form>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-mainText-subtle space-y-2">
                <LifeBuoy className="w-12 h-12 text-mainText-subtle opacity-50" />
                <p className="text-xs">یک تیکت را از لیست سمت راست انتخاب کنید.</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ─────────────────────────────────────────────────────────────
            3. FAQS KNOWLEDGE BASE
           ───────────────────────────────────────────────────────────── */
        <div className="space-y-4">
          <div className="glass-panel p-4 rounded-2xl border border-border flex items-center justify-between gap-3">
            <div className="relative flex-1 min-w-[280px]">
              <Search className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-mainText-subtle" />
              <input
                type="text"
                placeholder="جستجو در سوالات و پاسخ‌های متداول..."
                value={faqSearchQuery}
                onChange={(e) => setFaqSearchQuery(e.target.value)}
                className="w-full pr-10 pl-4 py-2 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary transition-all font-sans"
              />
            </div>
          </div>

          <div className="space-y-3">
            {filteredFaqs.length === 0 ? (
              <div className="glass-panel p-12 rounded-3xl border border-border text-center text-xs text-mainText-muted">
                سوالی با این مشخصات یافت نشد.
              </div>
            ) : (
              filteredFaqs.map((faq) => {
                const isExpanded = expandedFaqId === faq.id;
                return (
                  <div
                    key={faq.id}
                    className="p-1 rounded-[22px] bg-card border border-border transition-all shadow-sm"
                  >
                    <div className="p-4 rounded-[18px] bg-card-surface/40 border border-border/40 space-y-3">
                      <div className="flex items-center justify-between">
                        <div
                          onClick={() => setExpandedFaqId(isExpanded ? null : faq.id)}
                          className="flex items-center gap-3 cursor-pointer flex-1"
                        >
                          <HelpCircle className="w-4 h-4 text-primary shrink-0" />
                          <h4 className="font-bold text-xs text-mainText">{faq.question}</h4>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-card-surface text-mainText-muted border border-border">
                            {faq.category}
                          </span>
                          <button
                            onClick={() => {
                              setEditingFaq(faq);
                              setFaqForm({
                                question: faq.question,
                                answer: faq.answer,
                                category: faq.category,
                                language: faq.language as any,
                                is_active: faq.is_active,
                              });
                              setIsFaqModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg text-mainText-muted hover:text-mainText transition-colors"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteFaq(faq.id)}
                            className="p-1.5 rounded-lg text-mainText-muted hover:text-rose-500 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="pt-3 border-t border-border text-xs text-mainText-muted leading-relaxed">
                          {faq.answer}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          4. FAQ MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={isFaqModalOpen}
        onClose={() => setIsFaqModalOpen(false)}
        title={editingFaq ? 'ویرایش سوال متداول' : 'افزودن سوال متداول جدید'}
        maxWidth="md"
      >
        <form onSubmit={handleSaveFaq} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              متن سوال
            </label>
            <input
              type="text"
              required
              placeholder="مثال: چگونه می‌توانم اتچمنت اختصاصی ارسال کنم؟"
              value={faqForm.question}
              onChange={(e) => setFaqForm({ ...faqForm, question: e.target.value })}
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-sans"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              پاسخ تفصیلی
            </label>
            <textarea
              rows={4}
              required
              placeholder="پاسخ کامل سوال را وارد نمایید..."
              value={faqForm.answer}
              onChange={(e) => setFaqForm({ ...faqForm, answer: e.target.value })}
              className="w-full p-3 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary leading-relaxed font-sans"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                دسته‌بندی موضوعی
              </label>
              <input
                type="text"
                value={faqForm.category}
                onChange={(e) => setFaqForm({ ...faqForm, category: e.target.value })}
                className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-sans"
              />
            </div>
            <div>
              <Select<'fa' | 'en'>
                label="زبان"
                value={faqForm.language}
                onChange={(val) => setFaqForm({ ...faqForm, language: val })}
                options={[
                  { value: 'fa', label: 'فارسی (FA)' },
                  { value: 'en', label: 'English (EN)' },
                ]}
              />
            </div>
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsFaqModalOpen(false)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              {editingFaq ? 'ذخیره تغییرات' : 'ثبت سوال'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
