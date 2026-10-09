import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Crosshair,
  Clock,
  LifeBuoy,
  Eye,
  Heart,
  TrendingUp,
  Activity,
  Server,
  Zap,
  Plus,
  Radio,
  Search,
  CheckCircle2,
  Sparkles,
  Layers,
  Shield,
  ArrowUpRight,
  Database,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from 'recharts';
import { StatsCard } from '../../components/ui/StatsCard';
import { api } from '../../services/api';
import {
  DashboardStats,
  CategoryStat,
  ModeStat,
  SearchTrendItem,
  SystemHealthInfo,
} from '../../types';

export const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [categories, setCategories] = useState<CategoryStat[]>([]);
  const [modes, setModes] = useState<ModeStat[]>([]);
  const [trends, setTrends] = useState<SearchTrendItem[]>([]);
  const [health, setHealth] = useState<SystemHealthInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  const fetchDashboardData = async () => {
    try {
      const [statsRes, catRes, modeRes, trendsRes, healthRes] = await Promise.all([
        api.get<{ success: boolean; data: DashboardStats }>('/dashboard/stats'),
        api.get<{ success: boolean; data: CategoryStat[] }>('/dashboard/categories-breakdown'),
        api.get<{ success: boolean; data: ModeStat[] }>('/dashboard/modes-breakdown'),
        api.get<{ success: boolean; data: SearchTrendItem[] }>('/dashboard/search-trends?limit=6'),
        api.get<{ success: boolean; data: SystemHealthInfo }>('/dashboard/system-health'),
      ]);

      if (statsRes.data?.data) setStats(statsRes.data.data);
      if (catRes.data?.data) setCategories(catRes.data.data);
      if (modeRes.data?.data) setModes(modeRes.data.data);
      if (trendsRes.data?.data) setTrends(trendsRes.data.data);
      if (healthRes.data?.data) setHealth(healthRes.data.data);
    } catch (error) {
      console.error('Failed to fetch dashboard metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 15000);
    return () => clearInterval(interval);
  }, []);

  const PIE_COLORS = ['#7AE2CF', '#38BDF8', '#3F72AF', '#FDEB9E'];

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. TOP HERO BANNER & QUICK ACTIONS
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-bold uppercase tracking-wider border border-primary/30">
              LIVE MONITORING
            </span>
            <span className="text-xs text-mainText-muted font-medium">
              پلتفرم مدیریت دیتای Call of Duty Mobile
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5">
            <span>مرکز کنترل و آمار تحلیلی ربات</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            وضعیت لحظه‌ای کاربران، صف بررسی لوداوت‌ها، توزیع اتچمنت‌ها و عملکرد سرور
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 relative z-10">
          <button
            onClick={() => navigate('/weapons')}
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105 active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>کاتالوگ سلاح‌ها</span>
          </button>
          <button
            onClick={() => navigate('/submissions')}
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl bg-card hover:bg-card-hover text-mainText font-bold text-xs border border-border transition-all duration-200 shadow-sm"
          >
            <Clock className="w-4 h-4 text-accent" />
            <span>بررسی لوداوت‌ها ({stats?.pending_submissions || 0})</span>
          </button>
          <button
            onClick={() => navigate('/broadcast')}
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl bg-card hover:bg-card-hover text-mainText font-bold text-xs border border-border transition-all duration-200 shadow-sm"
          >
            <Radio className="w-4 h-4 text-primary" />
            <span>ارسال همگانی</span>
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. KPI STATS CARDS GRID (Double-Bezel Hardware Archetype)
         ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="کاربران ثبت‌نامی"
          value={stats?.total_users || 0}
          icon={Users}
          subtitle={`+${stats?.new_users_today || 0} کاربر امروز`}
          color="blue"
          onClick={() => navigate('/settings')}
        />
        <StatsCard
          title="کاتالوگ سلاح‌ها"
          value={stats?.total_weapons || 130}
          icon={Crosshair}
          subtitle={`${stats?.total_attachments || 0} لوداوت فعال`}
          color="primary"
          onClick={() => navigate('/weapons')}
        />
        <StatsCard
          title="لوداوت‌های در انتظار"
          value={stats?.pending_submissions || 0}
          icon={Clock}
          subtitle="ارسالی از طرف کاربران"
          color="amber"
          onClick={() => navigate('/submissions')}
        />
        <StatsCard
          title="تیکت‌های باز"
          value={stats?.open_tickets || 0}
          icon={LifeBuoy}
          subtitle="پشتیبانی نیازمند پاسخ"
          color="rose"
          onClick={() => navigate('/tickets')}
        />
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. SECONDARY METRICS ROW
         ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-1 rounded-[22px] bg-card-surface/40 border border-border">
          <div className="p-4 rounded-[18px] bg-card border border-border-subtle flex items-center justify-between shadow-sm">
            <div>
              <p className="text-xs text-mainText-muted font-bold uppercase">
                مجموع بازدید اتچمنت‌ها
              </p>
              <h4 className="text-2xl font-black text-mainText mt-1">
                {(stats?.total_views || 0).toLocaleString('fa-IR')}
              </h4>
            </div>
            <div className="p-3 rounded-2xl bg-primary/10 text-primary border border-primary/30">
              <Eye className="w-5 h-5" />
            </div>
          </div>
        </div>

        <div className="p-1 rounded-[22px] bg-card-surface/40 border border-border">
          <div className="p-4 rounded-[18px] bg-card border border-border-subtle flex items-center justify-between shadow-sm">
            <div>
              <p className="text-xs text-mainText-muted font-bold uppercase">
                مجموع پسندها (Likes)
              </p>
              <h4 className="text-2xl font-black text-mainText mt-1">
                {(stats?.total_likes || 0).toLocaleString('fa-IR')}
              </h4>
            </div>
            <div className="p-3 rounded-2xl bg-rose-500/10 text-rose-500 border border-rose-500/30">
              <Heart className="w-5 h-5" />
            </div>
          </div>
        </div>

        <div className="p-1 rounded-[22px] bg-card-surface/40 border border-border">
          <div className="p-4 rounded-[18px] bg-card border border-border-subtle flex items-center justify-between shadow-sm">
            <div>
              <p className="text-xs text-mainText-muted font-bold uppercase">
                شاخص سلامت داده‌ها
              </p>
              <h4 className="text-2xl font-black text-primary mt-1">
                %{stats?.system_health_score || 100}
              </h4>
            </div>
            <div className="p-3 rounded-2xl bg-primary/10 text-primary border border-primary/30">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. CHARTS & CATEGORY DISTRIBUTION ROW
         ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Categories Bar Chart (2 cols) */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-3xl border border-border space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="text-sm font-bold text-mainText font-mono">
                توزیع سلاح‌ها و اتچمنت‌ها بر اساس دسته‌بندی
              </h3>
            </div>
            
            {/* Chart Legend */}
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5 font-medium text-mainText-muted">
                <span className="w-2.5 h-2.5 rounded-full bg-primary inline-block shadow-sm" />
                <span>سلاح‌ها</span>
              </div>
              <div className="flex items-center gap-1.5 font-medium text-mainText-muted">
                <span className="w-2.5 h-2.5 rounded-full bg-secondary inline-block shadow-sm" />
                <span>اتچمنت‌ها</span>
              </div>
            </div>
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categories} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="var(--border-subtle)"
                  opacity={0.5}
                />
                <XAxis
                  dataKey="display_name"
                  stroke="var(--text-subtle)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={{ stroke: 'var(--border-main)' }}
                />
                <YAxis
                  stroke="var(--text-subtle)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={{ stroke: 'var(--border-main)' }}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(122, 226, 207, 0.07)', radius: 8 }}
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="glass-panel p-3 rounded-2xl border border-border shadow-card-elevated min-w-[170px] space-y-2 text-right">
                          <p className="text-xs font-black text-mainText border-b border-border/60 pb-1.5 flex items-center justify-between">
                            <span>{label}</span>
                            <span className="text-[10px] text-mainText-subtle font-mono">CATEGORY</span>
                          </p>
                          <div className="space-y-1 text-xs">
                            <div className="flex items-center justify-between gap-3">
                              <span className="flex items-center gap-1.5 text-mainText-muted">
                                <span className="w-2 h-2 rounded-full bg-primary inline-block" />
                                تعداد سلاح:
                              </span>
                              <span className="font-mono font-bold text-mainText">{payload[0]?.value || 0}</span>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span className="flex items-center gap-1.5 text-mainText-muted">
                                <span className="w-2 h-2 rounded-full bg-secondary inline-block" />
                                تعداد اتچمنت:
                              </span>
                              <span className="font-mono font-bold text-secondary">{payload[1]?.value || 0}</span>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar
                  dataKey="weapon_count"
                  name="تعداد سلاح"
                  fill="var(--primary)"
                  radius={[6, 6, 0, 0]}
                />
                <Bar
                  dataKey="attachment_count"
                  name="تعداد اتچمنت"
                  fill="var(--secondary)"
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* BR vs MP Distribution (1 col) */}
        <div className="glass-panel p-6 rounded-3xl border border-border space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              <h3 className="text-sm font-bold text-mainText font-mono">
                سهم مودهای بتل رویال و مولتی
              </h3>
            </div>
            <p className="text-xs text-mainText-subtle mt-1">
              توزیع تفکیکی لوداوت‌های بتل رویال در برابر مولتی‌پلیر
            </p>
          </div>

          <div className="h-44 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={modes}
                  dataKey="count"
                  nameKey="mode"
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={65}
                  paddingAngle={5}
                >
                  {modes.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0];
                      return (
                        <div className="glass-panel p-3 rounded-2xl border border-border shadow-card-elevated text-right min-w-[150px]">
                          <p className="text-xs font-bold text-mainText mb-1 flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-full inline-block"
                              style={{ backgroundColor: item.payload?.fill || item.color }}
                            />
                            <span>{item.name === 'br' ? 'مود بتل رویال (BR)' : 'مود مولتی‌پلیر (MP)'}</span>
                          </p>
                          <p className="text-xs text-mainText-muted">
                            تعداد: <span className="font-bold font-mono text-mainText">{item.value}</span> لوداوت
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border text-xs">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-primary" />
              <span className="text-mainText-muted">بتل رویال (BR)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-secondary" />
              <span className="text-mainText-muted">مولتی‌پلیر (MP)</span>
            </div>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          5. SEARCH TRENDS & SERVER HEALTH STATUS
         ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Most Searched Weapons (2 cols) */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-3xl border border-border space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Search className="w-5 h-5 text-accent" />
              <h3 className="text-sm font-bold text-mainText font-mono">
                محبوب‌ترین و بیشترین سلاح‌های جستجو شده توسط کاربران
              </h3>
            </div>
            <span className="text-[11px] text-mainText-subtle">۷ روز گذشته</span>
          </div>

          <div className="divide-y divide-border">
            {trends.length === 0 ? (
              <div className="py-8 text-center text-xs text-mainText-subtle">
                هنوز رکورد جستجویی برای نمایش ثبت نشده است.
              </div>
            ) : (
              trends.map((item, index) => (
                <div
                  key={index}
                  className="py-3 flex items-center justify-between hover:bg-card-hover px-2 rounded-xl transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-mainText-subtle w-5 text-center">
                      #{index + 1}
                    </span>
                    <span className="font-mono font-bold text-sm text-mainText">
                      {item.query}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-primary font-semibold">
                      {item.search_count} بار جستجو
                    </span>
                    <button
                      onClick={() => navigate(`/attachments?search=${item.query}`)}
                      className="p-1 rounded-lg text-mainText-muted hover:text-primary transition-colors"
                      title="مشاهده اتچمنت‌ها"
                    >
                      <ArrowUpRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Server & Database Health (1 col) */}
        <div className="glass-panel p-6 rounded-3xl border border-border space-y-4">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-primary" />
            <h3 className="text-sm font-bold text-mainText font-mono">وضعیت منابع سرور و دیتابیس</h3>
          </div>

          {/* CPU Metric */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-mainText-muted">مصرف پردازنده (CPU)</span>
              <span className="font-mono text-mainText font-bold">{health?.cpu_percent || 0}%</span>
            </div>
            <div className="w-full h-2 bg-card-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-500"
                style={{ width: `${health?.cpu_percent || 10}%` }}
              />
            </div>
          </div>

          {/* RAM Metric */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-mainText-muted">مصرف حافظه (RAM)</span>
              <span className="font-mono text-mainText font-bold">{health?.memory_percent || 0}%</span>
            </div>
            <div className="w-full h-2 bg-card-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-secondary transition-all duration-500"
                style={{ width: `${health?.memory_percent || 25}%` }}
              />
            </div>
          </div>

          {/* Pool & Uptime */}
          <div className="pt-3 border-t border-border space-y-2 text-xs">
            <div className="flex justify-between text-mainText-muted">
              <span>اتصالات دیتابیس:</span>
              <span className="font-mono text-primary font-bold">
                {health?.pool_size || 20} کانکشن آماده
              </span>
            </div>
            <div className="flex justify-between text-mainText-muted">
              <span>مدت زمان آپ‌تایم:</span>
              <span className="font-mono text-mainText">
                {Math.floor((health?.uptime_seconds || 0) / 3600)} ساعت و{' '}
                {Math.floor(((health?.uptime_seconds || 0) % 3600) / 60)} دقیقه
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
