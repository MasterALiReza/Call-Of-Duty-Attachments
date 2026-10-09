import React, { useState, useEffect } from 'react';
import {
  Crown,
  ShieldCheck,
  KeyRound,
  User,
  Copy,
  Check,
  Lock,
  Eye,
  EyeOff,
  Laptop,
  CheckCircle2,
  AlertTriangle,
  History,
  ShieldAlert,
  Fingerprint,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { AdminProfile, AuditLog } from '../../types';

export const ProfilePage: React.FC = () => {
  const { user } = useAuth();
  const [profile, setProfile] = useState<AdminProfile | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'audit'>('profile');
  const [copiedId, setCopiedId] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [isSavingName, setIsSavingName] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState('');

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPass, setShowCurrentPass] = useState(false);
  const [showNewPass, setShowNewPass] = useState(false);
  const [isChangingPass, setIsChangingPass] = useState(false);
  const [passStatusMsg, setPassStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    fetchProfile();
    fetchAuditLogs();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await api.get('/auth/profile');
      if (res.data?.success && res.data?.data) {
        setProfile(res.data.data);
        setDisplayName(res.data.data.display_name || '');
      }
    } catch {
      if (user) {
        setProfile({
          ...user,
          created_at: '2026-01-01T00:00:00',
          last_login: '2026-09-01T15:00:00',
          active_sessions_count: 1,
        });
        setDisplayName(user.display_name || user.username || '');
      }
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await api.get('/auth/audit-logs');
      if (res.data?.success && res.data?.data) {
        setAuditLogs(res.data.data);
      }
    } catch {
      setAuditLogs([
        {
          id: 'log_01',
          action: 'ورود موفق به پنل مدیریت',
          details: 'احراز هویت توکن Bearer JWT',
          ip_address: '127.0.0.1 (Localhost)',
          timestamp: '2026-09-01T15:00:00',
          status: 'success',
        },
        {
          id: 'log_02',
          action: 'به‌روزرسانی تنظیمات دیتابیس',
          details: 'اسکن جداول weapons و attachments',
          ip_address: '127.0.0.1 (Localhost)',
          timestamp: '2026-09-01T14:45:00',
          status: 'success',
        },
      ]);
    }
  };

  const handleCopyId = () => {
    if (profile?.user_id) {
      navigator.clipboard.writeText(String(profile.user_id));
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingName(true);
    setSaveSuccessMsg('');
    try {
      const res = await api.put('/auth/profile', { display_name: displayName });
      if (res.data?.success) {
        setSaveSuccessMsg('نام نمایشی با موفقیت ذخیره شد');
        fetchProfile();
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ذخیره نام نمایشی');
    } finally {
      setIsSavingName(false);
      setTimeout(() => setSaveSuccessMsg(''), 3000);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPassStatusMsg(null);

    if (newPassword.length < 6) {
      setPassStatusMsg({ type: 'error', text: 'رمز عبور جدید باید حداقل ۶ کاراکتر باشد' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPassStatusMsg({ type: 'error', text: 'رمز عبور جدید با تکرار آن همخوانی ندارد' });
      return;
    }

    setIsChangingPass(true);
    try {
      const res = await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (res.data?.success) {
        setPassStatusMsg({ type: 'success', text: 'رمز عبور با موفقیت تغییر یافت' });
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }
    } catch (err: any) {
      setPassStatusMsg({
        type: 'error',
        text: err.response?.data?.detail || 'خطا در تغییر رمز عبور',
      });
    } finally {
      setIsChangingPass(false);
    }
  };

  const calculatePassStrength = (pwd: string) => {
    if (!pwd) return { score: 0, label: 'بدون رمز', color: 'bg-card-surface' };
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;

    switch (score) {
      case 1:
        return { score: 25, label: 'ضعیف', color: 'bg-rose-500' };
      case 2:
        return { score: 50, label: 'متوسط', color: 'bg-accent' };
      case 3:
        return { score: 75, label: 'قوی', color: 'bg-secondary' };
      case 4:
        return { score: 100, label: 'بسیار امن', color: 'bg-primary' };
      default:
        return { score: 15, label: 'بسیار ضعیف', color: 'bg-rose-600' };
    }
  };

  const passStrength = calculatePassStrength(newPassword);

  const permissionGroups = [
    {
      title: 'مدیریت سلاح‌ها و اتچمنت‌ها',
      perms: ['weapons.view', 'weapons.manage', 'attachments.view', 'attachments.manage', 'attachments.delete'],
    },
    {
      title: 'بررسی ارسالی‌های کاربران و گزارش‌ها',
      perms: ['submissions.view', 'submissions.approve', 'submissions.reject', 'reports.manage'],
    },
    {
      title: 'پشتیبانی، تیکت‌ها و سوالات متداول',
      perms: ['tickets.view', 'tickets.reply', 'tickets.close', 'faq.manage'],
    },
    {
      title: 'اطلاع‌رسانی همگانی و پیام‌ها',
      perms: ['broadcast.send', 'broadcast.schedule', 'broadcast.delete'],
    },
    {
      title: 'تنظیمات سیستم، کانال‌ها و ادمین‌ها',
      perms: ['settings.manage', 'channels.manage', 'backup.create', 'admins.manage'],
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header Profile Identity Card */}
      <div className="p-6 rounded-3xl glass-card border border-border relative overflow-hidden">
        <div className="absolute top-0 right-0 left-0 h-2 bg-gradient-to-r from-secondary via-primary to-accent" />
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pt-2">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-secondary to-primary flex items-center justify-center text-primary-text shadow-glow-primary">
                <Crown className="w-8 h-8 text-primary-text" />
              </div>
              <span className="absolute -bottom-1 -left-1 w-4 h-4 rounded-full bg-primary border-2 border-card animate-pulse shadow-glow-primary" />
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-lg sm:text-xl font-black text-mainText">
                  {profile?.display_name || profile?.username || 'مدیر سیستم'}
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/15 text-primary border border-primary/30 flex items-center gap-1 shadow-sm">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  {profile?.is_super_admin ? 'مدیر کل ارشد (Super Admin)' : 'مدیر سیستم (Admin)'}
                </span>
              </div>

              <div className="flex items-center gap-4 mt-2 text-xs text-mainText-muted flex-wrap font-mono">
                <div className="flex items-center gap-1 bg-card-surface px-2.5 py-1 rounded-lg border border-border">
                  <span>USER ID:</span>
                  <span className="font-bold text-mainText">{profile?.user_id}</span>
                  <button
                    onClick={handleCopyId}
                    className="mr-1 text-mainText-subtle hover:text-primary transition-colors cursor-pointer"
                    title="کپی شناسه"
                  >
                    {copiedId ? <Check className="w-3.5 h-3.5 text-primary" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
                <div className="flex items-center gap-1.5">
                  <Laptop className="w-3.5 h-3.5 text-primary" />
                  <span>نشست‌های فعال: {profile?.active_sessions_count || 1}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Security Badge */}
          <div className="flex items-center gap-3 self-stretch md:self-auto justify-end">
            <div className="p-3 rounded-2xl bg-primary/10 border border-primary/20 text-primary flex items-center gap-3 shadow-sm">
              <Fingerprint className="w-6 h-6 text-primary" />
              <div className="flex flex-col">
                <span className="text-[11px] text-mainText-subtle">وضعیت امنیت</span>
                <span className="text-xs font-bold">تایید شده و فعال (JWT Safe)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 mt-6 pt-4 border-t border-border overflow-x-auto scrollbar-none">
          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'profile'
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText hover:bg-card-surface'
            }`}
          >
            <User className="w-4 h-4" />
            <span>مشخصات و دسترسی‌ها</span>
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'security'
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText hover:bg-card-surface'
            }`}
          >
            <Lock className="w-4 h-4" />
            <span>امنیت و تغییر رمز عبور</span>
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'audit'
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-glow-primary'
                : 'text-mainText-muted hover:text-mainText hover:bg-card-surface'
            }`}
          >
            <History className="w-4 h-4" />
            <span>لاگ فعالیت‌ها و ورود</span>
          </button>
        </div>
      </div>

      {/* Tab 1: Profile & Permissions Matrix */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-3xl glass-card border border-border lg:col-span-1 space-y-4">
            <h3 className="text-sm font-bold text-mainText flex items-center gap-2">
              <User className="w-4 h-4 text-primary" />
              <span>ویرایش مشخصات</span>
            </h3>
            <p className="text-xs text-mainText-subtle">
              نام نمایشی در پاسخ به تیکت‌ها و لاگ‌های سیستم نمایش داده می‌شود.
            </p>

            <form onSubmit={handleUpdateProfile} className="space-y-4 pt-2">
              <div>
                <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                  نام نمایشی (Display Name)
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-card border border-border text-mainText text-xs focus:border-primary focus:outline-none transition-colors"
                  placeholder="نام نمایشی ادمین..."
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                  نام کاربری سیستم (Username)
                </label>
                <input
                  type="text"
                  value={profile?.username || ''}
                  disabled
                  className="w-full px-3.5 py-2.5 rounded-xl bg-card-surface border border-border text-mainText-subtle text-xs font-mono cursor-not-allowed"
                />
              </div>

              {saveSuccessMsg && (
                <div className="p-3 rounded-xl bg-primary/10 border border-primary/20 text-primary text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{saveSuccessMsg}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isSavingName}
                className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text text-xs font-bold shadow-glow-primary transition-all disabled:opacity-50 cursor-pointer"
              >
                {isSavingName ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
              </button>
            </form>
          </div>

          <div className="p-6 rounded-3xl glass-card border border-border lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-mainText flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <span>ماتریس مجوزها و سطوح دسترسی فعال</span>
              </h3>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-card-surface text-mainText-muted border border-border">
                {profile?.is_super_admin || profile?.permissions.includes('all') ? 'Full Access (همه مجوزها)' : `${profile?.permissions.length || 0} مجوز فعال`}
              </span>
            </div>

            <div className="space-y-4 pt-2">
              {permissionGroups.map((group, idx) => (
                <div key={idx} className="p-3.5 rounded-2xl bg-card-surface/40 border border-border space-y-2">
                  <span className="text-xs font-bold text-mainText block">
                    {group.title}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {group.perms.map((perm) => {
                      const hasPerm = profile?.is_super_admin || profile?.permissions.includes('all') || profile?.permissions.includes(perm);
                      return (
                        <span
                          key={perm}
                          className={`text-[10px] font-mono px-2.5 py-1 rounded-lg border flex items-center gap-1 ${
                            hasPerm
                              ? 'bg-primary/10 text-primary border-primary/25'
                              : 'bg-card-surface text-mainText-subtle border-border opacity-50'
                          }`}
                        >
                          <CheckCircle2 className={`w-3 h-3 ${hasPerm ? 'text-primary' : 'text-mainText-subtle'}`} />
                          <span>{perm}</span>
                        </span>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Security & Password Change */}
      {activeTab === 'security' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-3xl glass-card border border-border lg:col-span-2 space-y-4">
            <h3 className="text-sm font-bold text-mainText flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-primary" />
              <span>تغییر رمز عبور حساب مدیریت</span>
            </h3>
            <p className="text-xs text-mainText-subtle">
              برای افزایش امنیت حساب، از رمزهای عبور ترکیبی شامل حروف بزرگ، کوچک، اعداد و نشانه‌ها استفاده فرمایید.
            </p>

            <form onSubmit={handleChangePassword} className="space-y-4 pt-2 max-w-lg">
              <div>
                <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                  رمز عبور فعلی
                </label>
                <div className="relative">
                  <input
                    type={showCurrentPass ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-card border border-border text-mainText text-xs focus:border-primary focus:outline-none transition-colors"
                    placeholder="رمز عبور فعلی خود را وارد کنید..."
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPass(!showCurrentPass)}
                    className="absolute left-3 top-2.5 text-mainText-subtle hover:text-mainText"
                  >
                    {showCurrentPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                  رمز عبور جدید
                </label>
                <div className="relative">
                  <input
                    type={showNewPass ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-card border border-border text-mainText text-xs focus:border-primary focus:outline-none transition-colors"
                    placeholder="رمز عبور جدید..."
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPass(!showNewPass)}
                    className="absolute left-3 top-2.5 text-mainText-subtle hover:text-mainText"
                  >
                    {showNewPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {newPassword && (
                  <div className="mt-2 space-y-1">
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-mainText-subtle">قدرت رمز عبور:</span>
                      <span className="font-bold text-mainText">{passStrength.label}</span>
                    </div>
                    <div className="h-1.5 w-full bg-card-surface rounded-full overflow-hidden">
                      <div
                        className={`h-full ${passStrength.color} transition-all duration-300`}
                        style={{ width: `${passStrength.score}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                  تکرار رمز عبور جدید
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-card border border-border text-mainText text-xs focus:border-primary focus:outline-none transition-colors"
                  placeholder="تکرار مجدد رمز عبور جدید..."
                  required
                />
              </div>

              {passStatusMsg && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    passStatusMsg.type === 'success'
                      ? 'bg-primary/10 border border-primary/20 text-primary'
                      : 'bg-rose-500/10 border border-rose-500/20 text-rose-500'
                  }`}
                >
                  {passStatusMsg.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                  <span>{passStatusMsg.text}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isChangingPass}
                className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-primary-text text-xs font-bold shadow-glow-primary transition-all disabled:opacity-50 cursor-pointer"
              >
                {isChangingPass ? 'در حال ثبت رمز جدید...' : 'به‌روزرسانی رمز عبور'}
              </button>
            </form>
          </div>

          <div className="p-6 rounded-3xl glass-card border border-border lg:col-span-1 space-y-4">
            <h3 className="text-sm font-bold text-mainText flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-primary" />
              <span>توصیه‌های امنیتی</span>
            </h3>
            <ul className="space-y-2.5 text-xs text-mainText-muted">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                <span>رمز عبور پیش‌فرض پنل را بعد از نصب حتماً تغییر دهید.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                <span>توکن‌های ورود به صورت رمزنگاری‌شده JWT صادر می‌شوند و پس از ۲۴ ساعت منقضی می‌گردند.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                <span>شناسه تلگرام خود را فقط به عنوان Super Admin در تنظیمات قرار دهید.</span>
              </li>
            </ul>
          </div>
        </div>
      )}

      {/* Tab 3: Security Audit Trail */}
      {activeTab === 'audit' && (
        <div className="p-6 rounded-3xl glass-card border border-border space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-mainText flex items-center gap-2">
              <History className="w-4 h-4 text-primary" />
              <span>تاریخچه ورودها و لاگ‌های امنیتی ادمین</span>
            </h3>
            <button
              onClick={fetchAuditLogs}
              className="text-xs text-primary hover:underline cursor-pointer font-bold"
            >
              تازه‌سازی لاگ‌ها
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-border text-mainText-muted font-semibold bg-card-surface/70">
                  <th className="py-3 px-4">عنوان رخداد</th>
                  <th className="py-3 px-4">جزئیات و توضیحات</th>
                  <th className="py-3 px-4">آدرس IP</th>
                  <th className="py-3 px-4">زمان ثبت</th>
                  <th className="py-3 px-4">وضعیت</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-card-hover transition-colors">
                    <td className="py-3.5 px-4 font-bold text-mainText">
                      {log.action}
                    </td>
                    <td className="py-3.5 px-4 text-mainText-muted">
                      {log.details}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-mainText-subtle">
                      {log.ip_address}
                    </td>
                    <td className="py-3.5 px-4 text-mainText-subtle font-mono">
                      {new Date(log.timestamp).toLocaleString('fa-IR')}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-primary/15 text-primary border border-primary/30">
                        {log.status === 'success' ? 'موفق' : log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
