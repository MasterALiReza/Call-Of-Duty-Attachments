import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  color?: 'primary' | 'secondary' | 'amber' | 'purple' | 'rose' | 'emerald' | 'blue';
  onClick?: () => void;
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  icon: Icon,
  subtitle,
  trend,
  color = 'primary',
  onClick,
}) => {
  const colorMap = {
    primary: {
      bg: 'bg-primary/15 text-primary border-primary/30',
      glow: 'group-hover:shadow-glow-primary group-hover:border-primary/50',
      accent: 'bg-primary',
    },
    secondary: {
      bg: 'bg-secondary/15 text-secondary border-secondary/30',
      glow: 'group-hover:border-secondary/50',
      accent: 'bg-secondary',
    },
    emerald: {
      bg: 'bg-primary/15 text-primary border-primary/30',
      glow: 'group-hover:shadow-glow-primary group-hover:border-primary/50',
      accent: 'bg-primary',
    },
    blue: {
      bg: 'bg-secondary/15 text-secondary border-secondary/30',
      glow: 'group-hover:border-secondary/50',
      accent: 'bg-secondary',
    },
    amber: {
      bg: 'bg-accent/15 text-accent border-accent/40',
      glow: 'group-hover:shadow-glow-accent group-hover:border-accent/50',
      accent: 'bg-accent',
    },
    purple: {
      bg: 'bg-primary/15 text-primary border-primary/30',
      glow: 'group-hover:shadow-glow-primary group-hover:border-primary/50',
      accent: 'bg-primary',
    },
    rose: {
      bg: 'bg-rose-500/15 text-rose-500 border-rose-500/30',
      glow: 'group-hover:shadow-rose-500/20 group-hover:border-rose-500/50',
      accent: 'bg-rose-500',
    },
  };

  const scheme = colorMap[color];

  return (
    <div
      onClick={onClick}
      className={`p-1 rounded-[24px] bg-card-surface/40 border border-border transition-all duration-300 group ${
        scheme.glow
      } ${onClick ? 'cursor-pointer hover:-translate-y-1' : ''}`}
    >
      {/* Inner Core Container */}
      <div className="p-5 rounded-[20px] bg-card border border-border-subtle flex flex-col justify-between h-full relative overflow-hidden shadow-sm">
        {/* Subtle Top Border Line */}
        <div
          className={`absolute top-0 right-0 left-0 h-[2px] opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${scheme.accent}`}
        />

        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-bold text-mainText-muted uppercase tracking-wider">
              {title}
            </p>
            <h3 className="text-2xl sm:text-3xl font-black text-mainText mt-1.5 tracking-tight">
              {typeof value === 'number' ? value.toLocaleString('fa-IR') : value}
            </h3>
            {subtitle && (
              <p className="text-xs text-mainText-subtle mt-1 leading-snug">{subtitle}</p>
            )}
          </div>

          <div
            className={`p-3 rounded-2xl border ${scheme.bg} transition-all duration-300 group-hover:scale-110 shadow-sm`}
          >
            <Icon className="w-5 h-5" />
          </div>
        </div>

        {trend && (
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs">
            <span
              className={`font-bold text-[11px] ${
                trend.isPositive ? 'text-primary' : 'text-rose-500'
              }`}
            >
              {trend.value}
            </span>
            <span className="text-mainText-subtle text-[10px]">نسبت به دوره قبل</span>
          </div>
        )}
      </div>
    </div>
  );
};
