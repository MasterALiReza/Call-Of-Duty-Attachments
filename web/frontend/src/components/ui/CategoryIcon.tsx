import React from 'react';
import {
  Crosshair,
  Zap,
  Target,
  Flame,
  Shield,
  Radio,
  Sword,
  Bomb,
  Layers,
  LucideIcon,
} from 'lucide-react';

const CATEGORY_ICON_MAP: Record<string, LucideIcon> = {
  assault_rifle: Crosshair,
  smg: Zap,
  sniper: Target,
  lmg: Shield,
  shotgun: Flame,
  marksman: Radio,
  pistol: Crosshair,
  melee: Sword,
  launcher: Bomb,
};

interface CategoryIconProps {
  slug?: string;
  className?: string;
  fallback?: LucideIcon;
}

export const CategoryIcon: React.FC<CategoryIconProps> = ({
  slug,
  className = 'w-5 h-5',
  fallback: Fallback = Layers,
}) => {
  if (!slug) return <Fallback className={className} />;
  const normalized = slug.toLowerCase().trim().replace(/\s+/g, '_');
  const IconComponent = CATEGORY_ICON_MAP[normalized] || Fallback;
  return <IconComponent className={className} />;
};
