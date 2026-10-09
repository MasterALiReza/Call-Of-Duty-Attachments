import React, { useState, useEffect } from 'react';
import {
  Radio,
  Send,
  Calendar,
  Clock,
  Plus,
  Trash2,
  Sparkles,
  Smartphone,
  Eye,
  CheckCircle2,
  Layers,
  Image as ImageIcon,
  ExternalLink,
  Code2,
  Bold,
  Italic,
} from 'lucide-react';
import { api } from '../../services/api';
import { ScheduledNotificationItem } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';

export const BroadcastPage: React.FC = () => {
  // Broadcast Composer State
  const [messageText, setMessageText] = useState(
    '🔥 <b>متای جدید سیزن Call of Duty Mobile منتشر شد!</b>\n\n' +
    'اتچمنت‌های برتر اسنایپر و رایفل برای سیزن جدید در ربات ثبت شدند.\n' +
    'همین الان از منوی اصلی سلاح مورد نظرتون رو انتخاب کنید! 🎯'
  );
  const [parseMode, setParseMode] = useState<'HTML' | 'Markdown' | 'plain'>('HTML');
  const [photoFileId, setPhotoFileId] = useState('');
  const [targetLanguage, setTargetLanguage] = useState<'all' | 'fa' | 'en'>('all');
  const [buttonText, setButtonText] = useState('مشاهده اتچمنت‌ها 🔫');
  const [buttonUrl, setButtonUrl] = useState('https://t.me/OxLoadoutBot');
  const [sending, setSending] = useState(false);
  const [sendSuccessMessage, setSendSuccessMessage] = useState<string | null>(null);

  // Scheduled Notifications State
  const [scheduledList, setScheduledList] = useState<ScheduledNotificationItem[]>([]);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    message_type: 'text' as 'text' | 'photo',
    message_text: '',
    photo_file_id: '',
    parse_mode: 'HTML',
    interval_hours: 24,
    enabled: true,
  });

  const fetchScheduled = async () => {
    try {
      const res = await api.get<{ success: boolean; data: ScheduledNotificationItem[] }>(
        '/broadcast/scheduled'
      );
      if (res.data?.data) {
        setScheduledList(res.data.data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchScheduled();
  }, []);

  const handleSendBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!messageText.trim()) return;

    if (!confirm('آیا از ارسال این پیام همگانی برای تمام کاربران ربات مطمئن هستید؟')) {
      return;
    }

    setSending(true);
    setSendSuccessMessage(null);
    try {
      const payload: Record<string, any> = {
        message_text: messageText.trim(),
        parse_mode: parseMode,
        photo_file_id: photoFileId.trim() || undefined,
        target_language: targetLanguage === 'all' ? undefined : targetLanguage,
      };

      if (buttonText.trim() && buttonUrl.trim()) {
        payload.buttons = [{ text: buttonText.trim(), url: buttonUrl.trim() }];
      }

      const res = await api.post('/broadcast', payload);
      setSendSuccessMessage(res.data?.message || 'پیام همگانی با موفقیت در صف ارسال قرار گرفت.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ارسال پیام همگانی');
    } finally {
      setSending(false);
    }
  };

  const handleToggleScheduled = async (id: number) => {
    try {
      await api.post(`/broadcast/scheduled/${id}/toggle`);
      fetchScheduled();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteScheduled = async (id: number) => {
    if (!confirm('آیا از حذف این اعلان خودکار اطمینان دارید؟')) return;
    try {
      await api.delete(`/broadcast/scheduled/${id}`);
      fetchScheduled();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/broadcast/scheduled', scheduleForm);
      setIsScheduleModalOpen(false);
      fetchScheduled();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت اعلان خودکار');
    }
  };

  const insertTag = (tag: string) => {
    if (tag === 'b') setMessageText((prev) => `${prev}<b>متن ضخیم</b>`);
    if (tag === 'i') setMessageText((prev) => `${prev}<i>متن مورب</i>`);
    if (tag === 'code') setMessageText((prev) => `${prev}<code>کد</code>`);
  };

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER BANNER
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/30">
              BROADCAST STUDIO
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              کمپین‌های همگانی و زمان‌بندی تلگرام
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>ارسال پیام همگانی و اعلان‌های دوره‌ای</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            طراحی پیام، شبیه‌سازی پیش‌نمایش در موبایل، ارسال سریع و تنظیم اعلان‌های خودکار
          </p>
        </div>

        <button
          onClick={() => {
            setScheduleForm({
              message_type: 'text',
              message_text: '',
              photo_file_id: '',
              parse_mode: 'HTML',
              interval_hours: 24,
              enabled: true,
            });
            setIsScheduleModalOpen(true);
          }}
          className="relative z-10 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105 active:scale-95"
        >
          <Clock className="w-4 h-4" />
          <span>افزودن اعلان خودکار دوره‌ای</span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. COMPOSER & TELEGRAM MOBILE SIMULATOR ROW
         ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Message Composer (7 cols) */}
        <div className="lg:col-span-7 glass-panel p-6 rounded-3xl border border-border space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <h3 className="font-bold text-sm text-mainText flex items-center gap-2">
              <Radio className="w-4 h-4 text-primary" />
              <span>تنظیم متن و پارامترهای پیام</span>
            </h3>
            <span className="text-xs text-mainText-subtle font-mono">
              {messageText.length} کاراکتر
            </span>
          </div>

          {sendSuccessMessage && (
            <div className="p-3.5 rounded-2xl bg-primary/15 border border-primary/40 text-primary text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
              <span>{sendSuccessMessage}</span>
            </div>
          )}

          <form onSubmit={handleSendBroadcast} className="space-y-4">
            {/* Formatting Toolbar */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => insertTag('b')}
                  className="p-1.5 rounded-lg bg-card-surface border border-border text-mainText-muted hover:text-mainText text-xs font-bold"
                  title="ضخیم"
                >
                  <Bold className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => insertTag('i')}
                  className="p-1.5 rounded-lg bg-card-surface border border-border text-mainText-muted hover:text-mainText text-xs"
                  title="مورب"
                >
                  <Italic className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => insertTag('code')}
                  className="p-1.5 rounded-lg bg-card-surface border border-border text-mainText-muted hover:text-mainText text-xs font-mono"
                  title="کد"
                >
                  <Code2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Target Audience Language */}
              <div className="flex items-center gap-2 min-w-[210px]">
                <span className="text-[11px] text-mainText-muted flex-shrink-0">مخاطبان:</span>
                <div className="flex-1">
                  <Select<'all' | 'fa' | 'en'>
                    size="sm"
                    value={targetLanguage}
                    onChange={(val) => setTargetLanguage(val)}
                    options={[
                      { value: 'all', label: 'همه کاربران (تمامی زبان‌ها)' },
                      { value: 'fa', label: 'فارسی‌زبانان (FA)' },
                      { value: 'en', label: 'انگلیسی‌زبانان (EN)' },
                    ]}
                  />
                </div>
              </div>
            </div>

            {/* Main Textarea */}
            <div>
              <textarea
                rows={6}
                required
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                placeholder="متن پیام همگانی خود را اینجا بنویسید..."
                className="w-full p-4 bg-card border border-border rounded-2xl text-xs text-mainText focus:outline-none focus:border-primary font-sans leading-relaxed transition-all"
              />
            </div>

            {/* Photo File ID Input */}
            <div>
              <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                شناسه تصویر تلگرام (اختیاری):
              </label>
              <input
                type="text"
                placeholder="AgACAgIAAxkBAAI..."
                value={photoFileId}
                onChange={(e) => setPhotoFileId(e.target.value)}
                className="w-full px-3.5 py-2 bg-card border border-border rounded-xl text-xs text-mainText font-mono focus:outline-none focus:border-primary"
              />
            </div>

            {/* Inline Button Builder */}
            <div className="p-4 rounded-2xl bg-card-surface/40 border border-border space-y-3">
              <span className="text-xs font-bold text-mainText block">
                دکمه شیشه‌ای زیر پیام (Inline URL Button)
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="عنوان دکمه (مثال: ورود به ربات)"
                  value={buttonText}
                  onChange={(e) => setButtonText(e.target.value)}
                  className="px-3 py-2 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-sans"
                />
                <input
                  type="url"
                  placeholder="لینک دکمه (https://...)"
                  value={buttonUrl}
                  onChange={(e) => setButtonUrl(e.target.value)}
                  className="px-3 py-2 bg-card border border-border rounded-xl text-xs text-primary font-mono focus:outline-none focus:border-primary"
                />
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={sending || !messageText.trim()}
                className="w-full py-3 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>{sending ? 'در حال ارسال برای کاربران...' : 'ارسال قطعی پیام همگانی'}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Right Side: Telegram Mobile Simulator (5 cols) */}
        <div className="lg:col-span-5 glass-panel p-6 rounded-3xl border border-border flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <h3 className="font-bold text-sm text-mainText flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-primary" />
              <span>پیش‌نمایش در تلگرام (Live Preview)</span>
            </h3>
            <span className="text-[11px] text-mainText-subtle font-mono">Telegram UI</span>
          </div>

          {/* Smartphone Screen Mockup */}
          <div className="p-4 rounded-[28px] bg-card border-2 border-border shadow-2xl flex flex-col space-y-3">
            {/* Top Telegram Header bar */}
            <div className="flex items-center justify-between px-2 pb-2 border-b border-border text-[11px] text-mainText-muted">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-primary text-primary-text flex items-center justify-center font-bold text-[10px] shadow-sm">
                  OX
                </div>
                <span className="font-bold text-mainText">Ox-Loadout Bot</span>
              </div>
              <span className="text-[10px] text-mainText-subtle font-mono">bot</span>
            </div>

            {/* Message Bubble Container */}
            <div className="p-4 rounded-2xl bg-card-surface border border-border text-mainText space-y-3 shadow-md">
              {photoFileId && (
                <div className="w-full h-32 rounded-xl bg-card border border-border flex items-center justify-center text-mainText-muted text-xs">
                  <ImageIcon className="w-6 h-6 text-mainText-subtle" />
                </div>
              )}

              <div
                className="text-xs leading-relaxed font-sans whitespace-pre-wrap"
                dangerouslySetInnerHTML={{
                  __html: messageText || '<span class="text-mainText-subtle">متن پیام...</span>',
                }}
              />

              <div className="text-left text-[9px] text-mainText-subtle font-mono">
                {new Date().toLocaleTimeString('fa-IR', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </div>

              {/* Inline Button Mockup */}
              {buttonText.trim() && (
                <div className="pt-2">
                  <div className="w-full py-2 rounded-xl bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 text-center font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer">
                    <span>{buttonText}</span>
                    <ExternalLink className="w-3 h-3 text-primary" />
                  </div>
                </div>
              )}
            </div>
          </div>

          <p className="text-[11px] text-mainText-subtle text-center">
            این پیش‌نمایش نحوه رندر تگ‌های HTML و دکمه‌های شیشه‌ای را نمایش می‌دهد.
          </p>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. SCHEDULED NOTIFICATIONS TABLE
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <h3 className="font-bold text-sm text-mainText flex items-center gap-2">
            <Calendar className="w-4 h-4 text-accent" />
            <span>اعلان‌های زمان‌بندی شده و دوره‌ای (Cron Schedule)</span>
          </h3>
          <span className="text-xs text-mainText-muted">
            {scheduledList.length} اعلان خودکار فعال
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-card-surface/70 border-b border-border text-mainText-muted font-semibold">
              <tr>
                <th className="px-6 py-4">شناسه</th>
                <th className="px-6 py-4">متن اعلان</th>
                <th className="px-6 py-4">دوره تکرار</th>
                <th className="px-6 py-4">آخرین ارسال</th>
                <th className="px-6 py-4">وضعیت</th>
                <th className="px-6 py-4 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {scheduledList.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-mainText-muted">
                    هیچ اعلان خودکاری ثبت نشده است. با دکمه بالا یک اعلان دوره‌ای تعریف کنید.
                  </td>
                </tr>
              ) : (
                scheduledList.map((item) => (
                  <tr key={item.id} className="hover:bg-card-hover transition-colors">
                    <td className="px-6 py-4 font-mono text-mainText-subtle">#{item.id}</td>
                    <td className="px-6 py-4 max-w-sm truncate text-mainText font-bold">
                      {item.message_text}
                    </td>
                    <td className="px-6 py-4 font-mono text-primary font-bold">
                      هر {item.interval_hours} ساعت
                    </td>
                    <td className="px-6 py-4 font-mono text-mainText-subtle">
                      {item.last_sent_at
                        ? new Date(item.last_sent_at).toLocaleDateString('fa-IR')
                        : 'تاکنون ارسال نشده'}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleToggleScheduled(item.id)}
                        className={`px-2.5 py-1 rounded-full text-[10px] font-bold border transition-all ${
                          item.enabled
                            ? 'bg-primary/15 text-primary border-primary/30'
                            : 'bg-card-surface text-mainText-subtle border-border'
                        }`}
                      >
                        {item.enabled ? '● فعال' : '○ غیرفعال'}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleDeleteScheduled(item.id)}
                        className="p-1.5 rounded-lg text-mainText-muted hover:text-rose-500 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. CREATE SCHEDULE MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={isScheduleModalOpen}
        onClose={() => setIsScheduleModalOpen(false)}
        title="افزودن اعلان خودکار دوره‌ای"
        maxWidth="md"
      >
        <form onSubmit={handleSaveSchedule} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              متن پیام اعلان
            </label>
            <textarea
              rows={4}
              required
              placeholder="متن اعلان دوره‌ای..."
              value={scheduleForm.message_text}
              onChange={(e) =>
                setScheduleForm({ ...scheduleForm, message_text: e.target.value })
              }
              className="w-full p-3 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-sans leading-relaxed"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              فاصله زمانی ارسال (ساعت)
            </label>
            <input
              type="number"
              min={1}
              required
              value={scheduleForm.interval_hours}
              onChange={(e) =>
                setScheduleForm({
                  ...scheduleForm,
                  interval_hours: Number(e.target.value),
                })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-mono"
            />
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsScheduleModalOpen(false)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              ثبت اعلان زمان‌بندی
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
