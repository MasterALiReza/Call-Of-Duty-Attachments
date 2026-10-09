import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'warning' | 'danger' | 'info' | 'outline' | 'ghost';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'primary',
  size = 'sm',
  className = '',
}) => {
  const variantStyles = {
    primary: 'bg-primary/15 text-primary border-primary/30 font-semibold',
    secondary: 'bg-secondary/15 text-secondary border-secondary/30 font-semibold',
    warning: 'bg-accent/15 text-accent border-accent/40 font-semibold',
    danger: 'bg-rose-500/10 text-rose-500 border-rose-500/30 font-semibold',
    info: 'bg-sky-500/10 text-sky-500 border-sky-500/30 font-semibold',
    outline: 'bg-transparent text-mainText-muted border-border',
    ghost: 'bg-card-surface text-mainText border-transparent',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  };

  return (
    <span
      className={`inline-flex items-center gap-1 font-medium rounded-lg border ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};
