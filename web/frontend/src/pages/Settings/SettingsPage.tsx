import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Radio,
  Database,
  ShieldAlert,
  Activity,
  Plus,
  Trash2,
  Edit2,
  Download,
  Play,
  Save,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  Server,
  Layers,
  Sparkles,
} from 'lucide-react';
import { api } from '../../services/api';
import {
  ChannelItem,
  SystemSettingItem,
  BlacklistWordItem,
  BackupFileItem,
  HealthIssueItem,
} from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<
    'channels' | 'settings' | 'blacklist' | 'backups' | 'health'
  >('channels');

  // Channels
  const [channels, setChannels] = useState<ChannelItem[]>([]);
  const [editingChannel, setEditingChannel] = useState<ChannelItem | null>(null);
  const [isChannelModalOpen, setIsChannelModalOpen] = useState(false);
  const [channelForm, setChannelForm] = useState({
    channel_id: '',
    title: '',
    url: '',
    priority: 1,
    is_active: true,
  });

  // System Settings
  const [settingsList, setSettingsList] = useState<SystemSettingItem[]>([]);
  const [editingSettings, setEditingSettings] = useState<Record<string, string>>({});
  const [savingSettings, setSavingSettings] = useState(false);

  // Blacklist
  const [blacklist, setBlacklist] = useState<BlacklistWordItem[]>([]);
  const [newWord, setNewWord] = useState('');
  const [newSeverity, setNewSeverity] = useState(1);

  // Backups
  const [backups, setBackups] = useState<BackupFileItem[]>([]);
  const [creatingBackup, setCreatingBackup] = useState(false);

  // Health & Integrity
  const [healthIssues, setHealthIssues] = useState<HealthIssueItem[]>([]);
  const [runningHealthCheck, setRunningHealthCheck] = useState(false);
  const [healthScore, setHealthScore] = useState(100);

  const fetchChannels = async () => {
    try {
      const res = await api.get<{ success: boolean; data: ChannelItem[] }>('/cms/channels');
      if (res.data?.data) setChannels(res.data.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await api.get<{ success: boolean; data: SystemSettingItem[] }>(
        '/system/settings'
      );
      if (res.data?.data) {
        setSettingsList(res.data.data);
        const map: Record<string, string> = {};
        res.data.data.forEach((s) => {
          map[s.key] = s.value || '';
        });
        setEditingSettings(map);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchBlacklist = async () => {
    try {
      const res = await api.get<{ success: boolean; data: BlacklistWordItem[] }>(
        '/system/blacklist'
      );
      if (res.data?.data) setBlacklist(res.data.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchBackups = async () => {
    try {
      const res = await api.get<{ success: boolean; data: BackupFileItem[] }>(
        '/system/backups'
      );
      if (res.data?.data) setBackups(res.data.data);
    } catch (err) {
      console.error(err);
    }
  };

  const runHealthCheck = async () => {
    setRunningHealthCheck(true);
    try {
      const res = await api.get<{
        success: boolean;
        data: { score: number; issues: HealthIssueItem[] };
      }>('/system/health-audit');
      if (res.data?.data) {
        setHealthScore(res.data.data.score);
        setHealthIssues(res.data.data.issues || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setRunningHealthCheck(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'channels') fetchChannels();
    if (activeTab === 'settings') fetchSettings();
    if (activeTab === 'blacklist') fetchBlacklist();
    if (activeTab === 'backups') fetchBackups();
    if (activeTab === 'health') runHealthCheck();
  }, [activeTab]);

  // Channel Handlers
  const handleSaveChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingChannel) {
        await api.put(`/cms/channels/${encodeURIComponent(editingChannel.channel_id)}`, {
          title: channelForm.title,
          url: channelForm.url,
          priority: Number(channelForm.priority),
          is_active: channelForm.is_active,
        });
      } else {
        await api.post('/cms/channels', {
          ...channelForm,
          priority: Number(channelForm.priority),
        });
      }
      setIsChannelModalOpen(false);
      setEditingChannel(null);
      fetchChannels();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت کانال');
    }
  };

  const handleToggleChannel = async (channelId: string) => {
    try {
      await api.post(`/cms/channels/${encodeURIComponent(channelId)}/toggle`);
      fetchChannels();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteChannel = async (channelId: string) => {
    if (!confirm('آیا از حذف این کانال اطمینان دارید؟')) return;
    try {
      await api.delete(`/cms/channels/${encodeURIComponent(channelId)}`);
      fetchChannels();
    } catch (err) {
      console.error(err);
    }
  };

  // Settings Handlers
  const handleSaveAllSettings = async () => {
    setSavingSettings(true);
    try {
      await api.put('/system/settings', { settings: editingSettings });
      alert('تنظیمات با موفقیت ذخیره شدند.');
      fetchSettings();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ذخیره تنظیمات');
    } finally {
      setSavingSettings(false);
    }
  };

  // Blacklist Handlers
  const handleAddBlacklist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWord.trim()) return;
    try {
      await api.post('/system/blacklist', {
        word: newWord.trim(),
        severity: newSeverity,
      });
      setNewWord('');
      fetchBlacklist();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت کلمه');
    }
  };

  const handleDeleteBlacklist = async (word: string) => {
    try {
      await api.delete(`/system/blacklist/${encodeURIComponent(word)}`);
      fetchBlacklist();
    } catch (err) {
      console.error(err);
    }
  };

  // Backup Handlers
  const handleCreateBackup = async () => {
    setCreatingBackup(true);
    try {
      const res = await api.post('/system/backups/create');
      alert(res.data?.message || 'پشتیبان با موفقیت ایجاد شد.');
      fetchBackups();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ایجاد پشتیبان');
    } finally {
      setCreatingBackup(false);
    }
  };

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
              SYSTEM CONFIG
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              تنظیمات هسته، کانال‌های اجباری و سلامت دیتابیس
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>تنظیمات و نگهداری زیرساخت</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            مدیریت عضویت اجباری کانال‌ها، فیلتر کلمات، متغیرهای سیستم و بکاپ‌گیری دوره‌ای
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="p-1 rounded-2xl bg-card border border-border flex flex-wrap items-center gap-1 relative z-10 shadow-inner">
          <button
            onClick={() => setActiveTab('channels')}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'channels'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            کانال‌های اجباری ({channels.length})
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'settings'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            تنظیمات عمومی
          </button>
          <button
            onClick={() => setActiveTab('blacklist')}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'blacklist'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            لیست سیاه کلمات
          </button>
          <button
            onClick={() => setActiveTab('backups')}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'backups'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            پشتیبان‌گیری (Backups)
          </button>
          <button
            onClick={() => setActiveTab('health')}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === 'health'
                ? 'bg-primary text-primary-text font-black shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText'
            }`}
          >
            سلامت داده‌ها
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. TAB CONTENT
         ───────────────────────────────────────────────────────────── */}

      {/* TAB: CHANNELS */}
      {activeTab === 'channels' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-mainText-muted font-medium">
              کاربران برای استفاده از ربات ملزم به عضویت در کانال‌های فعال زیر هستند:
            </span>
            <button
              onClick={() => {
                setEditingChannel(null);
                setChannelForm({
                  channel_id: '',
                  title: '',
                  url: '',
                  priority: channels.length + 1,
                  is_active: true,
                });
                setIsChannelModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105 active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>افزودن کانال جدید</span>
            </button>
          </div>

          {channels.length === 0 ? (
            <div className="p-12 rounded-3xl bg-card border border-border text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 rounded-3xl bg-primary/10 border border-primary/20 text-primary flex items-center justify-center mx-auto shadow-glow-primary">
                <Radio className="w-8 h-8" />
              </div>
              <div className="max-w-md mx-auto space-y-1.5">
                <h3 className="text-base font-bold text-mainText">هیچ کانال اجباری ثبت نشده است</h3>
                <p className="text-xs text-mainText-muted leading-relaxed">
                  در حال حاضر کاربران بدون هیچ‌گونه قفل یا محدودیت عضویت، می‌توانند مستقیماً از تمامی امکانات ربات استفاده کنند.
                </p>
              </div>
              <button
                onClick={() => {
                  setEditingChannel(null);
                  setChannelForm({
                    channel_id: '',
                    title: '',
                    url: '',
                    priority: 1,
                    is_active: true,
                  });
                  setIsChannelModalOpen(true);
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105"
              >
                <Plus className="w-4 h-4" />
                <span>افزودن اولین کانال اجباری</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {channels.map((ch) => (
                <div
                  key={ch.channel_id}
                  className="p-1 rounded-[24px] bg-card border border-border hover:border-primary/50 transition-all group shadow-sm hover:shadow-glow-primary"
                >
                  <div className="p-5 rounded-[20px] bg-card-surface/40 border border-border/40 flex flex-col justify-between h-full space-y-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <h4 className="font-bold text-sm text-mainText truncate">{ch.title}</h4>
                        <p className="text-xs text-primary font-bold mt-0.5 truncate">
                          {ch.channel_id}
                        </p>
                      </div>

                      <button
                        onClick={() => handleToggleChannel(ch.channel_id)}
                        className={`px-3 py-1 rounded-full text-[10px] font-bold border transition-all shrink-0 ${
                          ch.is_active
                            ? 'bg-primary/15 text-primary border-primary/30 shadow-glow-primary'
                            : 'bg-card-surface text-mainText-subtle border-border'
                        }`}
                      >
                        {ch.is_active ? '● فعال' : '○ غیرفعال'}
                      </button>
                    </div>

                    <div className="pt-3 border-t border-border flex items-center justify-between text-xs">
                      <span className="text-mainText-subtle font-medium">
                        اولویت: #{ch.priority}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {ch.url && (
                          <a
                            href={ch.url}
                            target="_blank"
                            rel="noreferrer"
                            className="p-2 rounded-xl bg-card border border-border text-mainText-muted hover:text-mainText hover:border-primary transition-all"
                            title="مشاهده کانال در تلگرام"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}
                        <button
                          onClick={() => {
                            setEditingChannel(ch);
                            setChannelForm({
                              channel_id: ch.channel_id,
                              title: ch.title,
                              url: ch.url,
                              priority: ch.priority,
                              is_active: ch.is_active,
                            });
                            setIsChannelModalOpen(true);
                          }}
                          className="p-2 rounded-xl bg-card border border-border text-mainText-muted hover:text-primary hover:border-primary transition-all"
                          title="ویرایش کانال"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteChannel(ch.channel_id)}
                          className="p-2 rounded-xl bg-card border border-border text-mainText-muted hover:text-rose-500 hover:border-rose-500/50 transition-all"
                          title="حذف کانال"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB: SYSTEM SETTINGS */}
      {activeTab === 'settings' && (
        <div className="glass-panel p-6 rounded-3xl border border-border space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <div>
              <h3 className="text-sm font-bold text-mainText">پارامترها و پیکربندی ربات</h3>
              <p className="text-xs text-mainText-subtle mt-0.5">
                تغییر مقادیر کش، آستانه امتیازها و رفتارهای پیش‌فرض
              </p>
            </div>

            <button
              onClick={handleSaveAllSettings}
              disabled={savingSettings}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{savingSettings ? 'در حال ذخیره...' : 'ذخیره تمام تنظیمات'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {settingsList.map((st) => (
              <div
                key={st.key}
                className="p-4 rounded-2xl bg-card-surface/40 border border-border space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-mainText">{st.key}</span>
                  <span className="font-mono text-[10px] text-mainText-subtle">{st.data_type}</span>
                </div>
                {st.description && (
                  <p className="text-[11px] text-mainText-muted leading-relaxed">
                    {st.description}
                  </p>
                )}
                <input
                  type="text"
                  value={editingSettings[st.key] || ''}
                  onChange={(e) =>
                    setEditingSettings({
                      ...editingSettings,
                      [st.key]: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 bg-card border border-border rounded-xl text-xs text-primary font-mono focus:outline-none focus:border-primary"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB: BLACKLIST */}
      {activeTab === 'blacklist' && (
        <div className="space-y-4">
          <form
            onSubmit={handleAddBlacklist}
            className="glass-panel p-4 rounded-2xl border border-border flex flex-wrap items-center gap-3"
          >
            <input
              type="text"
              required
              placeholder="کلمه نامناسب جدید برای فیلتر خودکار..."
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
              className="flex-1 min-w-[200px] px-3.5 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
            />
            <div className="w-56">
              <Select<number>
                size="sm"
                value={newSeverity}
                onChange={(val) => setNewSeverity(val)}
                options={[
                  {
                    value: 1,
                    label: 'شدت: ۱ (هشدار و لاگ)',
                    badge: <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />,
                  },
                  {
                    value: 2,
                    label: 'شدت: ۲ (مسدودسازی پیام)',
                    badge: <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />,
                  },
                  {
                    value: 3,
                    label: 'شدت: ۳ (بن خودکار کاربر)',
                    badge: <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />,
                  },
                ]}
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              افزودن به لیست سیاه
            </button>
          </form>

          <div className="glass-panel p-6 rounded-3xl border border-border">
            <div className="flex flex-wrap gap-2">
              {blacklist.map((item) => (
                <div
                  key={item.word}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-card border border-border text-xs text-mainText shadow-sm"
                >
                  <span className="font-bold">{item.word}</span>
                  <span className="text-[10px] text-mainText-subtle font-mono">
                    L{item.severity}
                  </span>
                  <button
                    onClick={() => handleDeleteBlacklist(item.word)}
                    className="text-mainText-subtle hover:text-rose-500 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB: BACKUPS */}
      {activeTab === 'backups' && (
        <div className="glass-panel p-6 rounded-3xl border border-border space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <div>
              <h3 className="text-sm font-bold text-mainText">
                پشتیبان‌گیری دستی و خودکار دیتابیس PostgreSQL
              </h3>
              <p className="text-xs text-mainText-subtle mt-0.5">
                فایل‌های پشتیبان در پوشه backups سرور ذخیره می‌شوند.
              </p>
            </div>

            <button
              onClick={handleCreateBackup}
              disabled={creatingBackup}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all disabled:opacity-50"
            >
              <Database className="w-4 h-4" />
              <span>{creatingBackup ? 'در حال تهیه پشتیبان...' : 'تهیه پشتیبان دستی جدید'}</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-card-surface/70 border-b border-border text-mainText-muted font-semibold">
                <tr>
                  <th className="px-6 py-4">نام فایل بکاپ</th>
                  <th className="px-6 py-4">حجم فایل</th>
                  <th className="px-6 py-4">تاریخ ایجاد</th>
                  <th className="px-6 py-4 text-center">دانلود</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {backups.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="text-center py-12 text-mainText-muted">
                      هیچ فایل پشتیبانی ثبت نشده است.
                    </td>
                  </tr>
                ) : (
                  backups.map((b, idx) => (
                    <tr key={idx} className="hover:bg-card-hover transition-colors">
                      <td className="px-6 py-4 font-mono text-primary font-bold">
                        {b.filename}
                      </td>
                      <td className="px-6 py-4 font-mono text-mainText-muted">{b.size_mb} MB</td>
                      <td className="px-6 py-4 font-mono text-mainText-subtle">
                        {new Date(b.created_at).toLocaleDateString('fa-IR')}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <a
                          href={`/api/v1/system/backups/${b.filename}`}
                          className="inline-flex p-1.5 rounded-lg text-mainText-muted hover:text-primary transition-colors"
                          title="دانلود فایل بکاپ"
                        >
                          <Download className="w-4 h-4" />
                        </a>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB: HEALTH & AUDIT */}
      {activeTab === 'health' && (
        <div className="glass-panel p-6 rounded-3xl border border-border space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-primary/15 border border-primary/30 flex items-center justify-center text-primary font-mono font-black text-lg shadow-glow-primary">
                %{healthScore}
              </div>
              <div>
                <h3 className="text-sm font-bold text-mainText">شاخص یکپارچگی و سلامت ساختار داده</h3>
                <p className="text-xs text-mainText-subtle mt-0.5">
                  بررسی ناهماهنگی در جداول، سلاح‌های بدون اتچمنت، و رکوردهای یتیم
                </p>
              </div>
            </div>

            <button
              onClick={runHealthCheck}
              disabled={runningHealthCheck}
              className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-card hover:bg-card-hover text-mainText font-bold text-xs border border-border transition-all shadow-sm"
            >
              <RefreshCw
                className={`w-4 h-4 ${runningHealthCheck ? 'animate-spin' : ''}`}
              />
              <span>اسکن مجدد سلامت</span>
            </button>
          </div>

          <div className="space-y-3">
            {healthIssues.length === 0 ? (
              <div className="p-8 rounded-2xl bg-primary/10 border border-primary/30 text-center text-xs text-primary flex items-center justify-center gap-2 shadow-sm">
                <CheckCircle2 className="w-5 h-5 text-primary" />
                <span>تمامی ساختار داده‌ها و روابط جداول در بالاترین سطح سلامت قرار دارند.</span>
              </div>
            ) : (
              healthIssues.map((issue, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl bg-card border border-border flex items-center justify-between shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="w-5 h-5 text-accent shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-mainText">{issue.check_type}</h4>
                      <p className="text-[11px] text-mainText-muted mt-0.5">
                        {issue.issue_count} مورد شناسایی شد ({issue.category || 'سیستم'})
                      </p>
                    </div>
                  </div>
                  <Badge variant={issue.severity === 'high' ? 'danger' : 'warning'}>
                    {issue.severity === 'high' ? 'مهم' : 'متوسط'}
                  </Badge>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          3. ADD / EDIT CHANNEL MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={isChannelModalOpen}
        onClose={() => {
          setIsChannelModalOpen(false);
          setEditingChannel(null);
        }}
        title={editingChannel ? 'ویرایش اطلاعات کانال اجباری' : 'افزودن کانال عضویت اجباری'}
        maxWidth="md"
      >
        <form onSubmit={handleSaveChannel} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5 flex items-center justify-between">
              <span>آیدی کانال تلگرام (با @ یا عددی -100...)</span>
              {editingChannel && (
                <span className="text-[10px] text-amber-500 font-medium">شناسه کانال غیرقابل تغییر است</span>
              )}
            </label>
            <input
              type="text"
              required
              disabled={!!editingChannel}
              placeholder="مثال: @OxLoadoutChannel"
              value={channelForm.channel_id}
              onChange={(e) =>
                setChannelForm({ ...channelForm, channel_id: e.target.value })
              }
              className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText font-mono focus:outline-none focus:border-primary disabled:opacity-60 disabled:bg-card-surface/50"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              عنوان نمایشی کانال
            </label>
            <input
              type="text"
              required
              placeholder="مثال: کانال رسمی لوداوت‌های کالاف"
              value={channelForm.title}
              onChange={(e) =>
                setChannelForm({ ...channelForm, title: e.target.value })
              }
              className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary font-sans"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              لینک جوین کانال (URL)
            </label>
            <input
              type="url"
              required
              placeholder="https://t.me/..."
              value={channelForm.url}
              onChange={(e) => setChannelForm({ ...channelForm, url: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-xs text-primary font-mono focus:outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                اولویت نمایش (Priority)
              </label>
              <input
                type="number"
                min={1}
                max={999}
                value={channelForm.priority}
                onChange={(e) =>
                  setChannelForm({ ...channelForm, priority: Number(e.target.value) })
                }
                className="w-full px-3.5 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText font-mono focus:outline-none focus:border-primary"
              />
            </div>

            <div className="flex flex-col justify-end">
              <label className="text-xs font-semibold text-mainText-muted mb-2">وضعیت فعالیت</label>
              <label className="flex items-center gap-2 cursor-pointer py-1.5">
                <input
                  type="checkbox"
                  checked={channelForm.is_active}
                  onChange={(e) =>
                    setChannelForm({ ...channelForm, is_active: e.target.checked })
                  }
                  className="w-4 h-4 rounded text-primary focus:ring-primary/40 bg-card border-border"
                />
                <span className="text-xs font-bold text-mainText">کانال فعال باشد</span>
              </label>
            </div>
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsChannelModalOpen(false);
                setEditingChannel(null);
              }}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all duration-200"
            >
              {editingChannel ? 'ذخیره تغییرات' : 'ثبت کانال'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
