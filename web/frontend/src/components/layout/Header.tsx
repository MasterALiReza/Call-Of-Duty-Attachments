import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  Bell,
  Search,
  Shield,
  Zap,
  Sparkles,
  Layers,
  Crosshair,
  Radio,
  ExternalLink,
  Sun,
  Moon,
  Laptop,
  Crown,
  User,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

interface HeaderProps {
  sidebarCollapsed: boolean;
}

export const Header: React.FC<HeaderProps> = ({ sidebarCollapsed }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

  const getPageInfo = () => {
    switch (location.pathname) {
      case '/':
        return {
          title: 'داشبورد و مانیتورینگ',
          subtitle: 'مرکز تحلیل داده‌ها و وضعیت سلامت ربات',
        };
      case '/attachments':
        return {
          title: 'مدیریت اتچمنت‌ها',
          subtitle: 'لوداوت‌های رسمی، متای سیزن و کدهای اشتراک‌گذاری',
        };
      case '/weapons':
        return {
          title: 'کاتالوگ سلاح‌ها و دسته‌ها',
          subtitle: 'تعریف و تفکیک سلاح‌های بتل رویال و مولتی‌پلیر',
        };
      case '/submissions':
        return {
          title: 'صف تایید لوداوت‌های کاربران',
          subtitle: 'بررسی کیفی، تصاویر ارسالی و مدیریت ریپورت‌ها',
        };
      case '/tickets':
        return {
          title: 'میز پشتیبانی و پایگاه دانش',
          subtitle: 'پاسخگویی به تیکت‌ها و بانک سوالات متداول FAQ',
        };
      case '/broadcast':
        return {
          title: 'ارسال پیام همگانی',
          subtitle: 'کمپین‌های تلگرامی، زمان‌بندی و پیش‌نمایش موبایل',
        };
      case '/settings':
        return {
          title: 'تنظیمات، کانال‌ها و بکاپ',
          subtitle: 'کانال‌های اجباری، پارامترهای سیستم و سلامت دیتابیس',
        };
      case '/profile':
        return {
          title: 'پروفایل و امنیت ادمین',
          subtitle: 'مدیریت حساب کاربری، سطوح دسترسی و تغییر رمز عبور',
        };
      default:
        return {
          title: 'پنل مدیریت Ox-Loadout',
          subtitle: 'سیستم هوشمند مدیریت اتچمنت‌های CoDM',
        };
    }
  };

  const page = getPageInfo();

  return (
    <header
      className={`fixed top-0 left-0 z-20 h-16 glass-panel border-b border-border flex items-center justify-between px-6 transition-all duration-300 ${
        sidebarCollapsed ? 'right-20' : 'right-64'
      }`}
    >
      {/* Page Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col">
          <h1 className="text-sm sm:text-base font-extrabold text-mainText tracking-wide flex items-center gap-2">
            <span>{page.title}</span>
          </h1>
          <span className="text-[11px] text-mainText-muted hidden md:inline">
            {page.subtitle}
          </span>
        </div>
      </div>

      {/* Right Controls: Theme Switcher & Profile */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Theme Switcher (Light / Dark / System) */}
        <div className="flex items-center p-1 rounded-xl bg-card-surface/60 border border-border">
          <button
            onClick={() => setTheme('light')}
            className={`p-1.5 rounded-lg text-xs transition-all ${
              theme === 'light'
                ? 'bg-card text-primary shadow-sm font-bold border border-border'
                : 'text-mainText-muted hover:text-mainText'
            }`}
            title="تم روشن (Light)"
          >
            <Sun className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setTheme('system')}
            className={`p-1.5 rounded-lg text-xs transition-all ${
              theme === 'system'
                ? 'bg-primary text-primary-text shadow-sm font-bold'
                : 'text-mainText-muted hover:text-mainText'
            }`}
            title="پیروی خودکار از تم دستگاه کاربر (System)"
          >
            <Laptop className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setTheme('dark')}
            className={`p-1.5 rounded-lg text-xs transition-all ${
              theme === 'dark'
                ? 'bg-card text-primary shadow-sm font-bold border border-border'
                : 'text-mainText-muted hover:text-mainText'
            }`}
            title="تم تاریک (Dark)"
          >
            <Moon className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* System Online Badge */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-glow-primary" />
          <span className="font-mono text-[11px]">POSTGRES 18 LIVE</span>
        </div>

        {/* User Role Tag & Link to Profile */}
        <button
          onClick={() => navigate('/profile')}
          className="flex items-center gap-2 px-3 py-1 rounded-xl bg-card hover:bg-card-hover border border-border text-xs text-mainText transition-all cursor-pointer group shadow-sm"
          title="مشاهده پروفایل و امنیت ادمین"
        >
          <div className="w-5 h-5 rounded-lg bg-gradient-to-tr from-secondary to-primary text-primary-text flex items-center justify-center font-bold text-[10px] shadow-glow-primary">
            <Crown className="w-3 h-3 text-primary-text" />
          </div>
          <span className="font-semibold group-hover:text-primary transition-colors">
            {user?.display_name || user?.username}
          </span>
        </button>
      </div>
    </header>
  );
};
