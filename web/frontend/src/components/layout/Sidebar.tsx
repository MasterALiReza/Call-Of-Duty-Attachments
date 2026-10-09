import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Crosshair,
  ShieldAlert,
  Inbox,
  LifeBuoy,
  Radio,
  Sliders,
  LogOut,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Layers,
  Crown,
  UserCheck,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, setCollapsed }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navigationItems = [
    {
      name: 'داشبورد',
      to: '/',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      name: 'اتچمنت‌ها',
      to: '/attachments',
      icon: Crosshair,
      badge: null,
    },
    {
      name: 'سلاح‌ها و دسته‌ها',
      to: '/weapons',
      icon: Layers,
      badge: null,
    },
    {
      name: 'تاییدیه کاربران',
      to: '/submissions',
      icon: Inbox,
      badge: 'بررسی',
      badgeColor: 'bg-accent/15 text-accent border border-accent/30',
    },
    {
      name: 'میز پشتیبانی و تیکت',
      to: '/tickets',
      icon: LifeBuoy,
      badge: null,
    },
    {
      name: 'اطلاع‌رسانی همگانی',
      to: '/broadcast',
      icon: Radio,
      badge: null,
    },
    {
      name: 'تنظیمات و نگهداری',
      to: '/settings',
      icon: Sliders,
      badge: null,
    },
    {
      name: 'پروفایل و امنیت ادمین',
      to: '/profile',
      icon: UserCheck,
      badge: null,
    },
  ];

  return (
    <aside
      className={`fixed top-0 bottom-0 right-0 z-30 flex flex-col glass-panel border-l border-border transition-all duration-300 select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between px-4 h-16 border-b border-border">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-secondary to-primary flex items-center justify-center shadow-glow-primary shrink-0">
            <Sparkles className="w-5 h-5 text-primary-text" />
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-black text-base text-mainText tracking-tight leading-none">
                OX-LOADOUT
              </span>
              <span className="text-[10px] text-primary font-bold mt-1 tracking-wider uppercase">
                پنل مدیریت پیشرفته
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto scrollbar-none">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-2.5 rounded-2xl font-medium text-xs transition-all duration-200 group overflow-hidden ${
                  isActive
                    ? 'bg-primary/15 text-primary border border-primary/40 shadow-glow-primary font-bold'
                    : 'text-mainText-muted hover:text-mainText hover:bg-card-surface/60 border border-transparent'
                }`
              }
              title={collapsed ? item.name : undefined}
            >
              {({ isActive }) => (
                <>
                  {/* Glowing vertical bar for active link */}
                  {isActive && (
                    <span className="absolute right-0 top-1.5 bottom-1.5 w-1 bg-primary rounded-l-full shadow-glow-primary" />
                  )}

                  {/* Collapsed Badge Indicator Dot */}
                  {collapsed && item.badge && (
                    <span className="absolute top-2 left-2 w-2 h-2 rounded-full bg-accent animate-pulse" />
                  )}

                  <Icon
                    className={`w-4 h-4 shrink-0 transition-transform duration-200 group-hover:scale-110 ${
                      isActive
                        ? 'text-primary'
                        : 'text-mainText-subtle group-hover:text-mainText'
                    }`}
                  />

                  {!collapsed && (
                    <div className="flex-1 flex items-center justify-between min-w-0 pr-1">
                      <span className="truncate font-semibold">{item.name}</span>
                      {item.badge && (
                        <span
                          className={`text-[9px] px-2 py-0.5 rounded-full font-bold shrink-0 mr-2 ${item.badgeColor}`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse Toggle Button */}
      <div className="px-3 py-2 border-t border-border">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-xl text-mainText-muted hover:text-mainText hover:bg-card-surface transition-colors"
          title={collapsed ? 'گسترش منو' : 'جمع کردن منو'}
        >
          {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* User Info Footer */}
      <div className="p-3 border-t border-border bg-card-surface/30">
        <div
          onClick={() => navigate('/profile')}
          className="flex items-center justify-between p-2 rounded-2xl bg-card border border-border hover:border-primary transition-all cursor-pointer group shadow-sm"
          title="مشاهده پروفایل و امنیت ادمین"
        >
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-xl bg-primary/15 text-primary border border-primary/30 flex items-center justify-center font-bold text-xs shrink-0 group-hover:scale-105 transition-transform">
              <Crown className="w-4 h-4 text-primary" />
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span
                  className="text-xs font-bold text-mainText truncate group-hover:text-primary transition-colors"
                  title={user?.display_name || user?.username || 'مدیر سیستم'}
                >
                  {user?.display_name || user?.username || 'مدیر سیستم'}
                </span>
                <span className="text-[10px] text-primary font-bold truncate">
                  {user?.is_super_admin ? 'Super Admin' : 'Admin'}
                </span>
              </div>
            )}
          </div>
          {!collapsed && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                logout();
              }}
              className="p-1.5 rounded-xl text-mainText-subtle hover:text-rose-500 hover:bg-rose-500/10 transition-colors shrink-0 -scale-x-100"
              title="خروج از حساب"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};
