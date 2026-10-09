import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layers,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
  Search,
  Crosshair,
  ExternalLink,
  Sparkles,
  SlidersHorizontal,
  Flame,
  Shield,
  Zap,
  Target,
  Compass,
  Gamepad2,
} from 'lucide-react';
import { api } from '../../services/api';
import { CategoryItem, WeaponItem } from '../../types';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { CategoryIcon } from '../../components/ui/CategoryIcon';
import { Select } from '../../components/ui/Select';

export const WeaponsPage: React.FC = () => {
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [weapons, setWeapons] = useState<WeaponItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Active Category & View Filters
  const [selectedCategory, setSelectedCategory] = useState<CategoryItem | 'all'>('all');
  const [activeTab, setActiveTab] = useState<'weapons' | 'categories'>('weapons');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);

  const navigate = useNavigate();

  // Weapon Modal State
  const [isWeaponModalOpen, setIsWeaponModalOpen] = useState(false);
  const [editingWeapon, setEditingWeapon] = useState<WeaponItem | null>(null);
  const [weaponForm, setWeaponForm] = useState({
    category_id: 1,
    name: '',
    display_name: '',
    is_active: true,
  });

  // Category Modal State
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    display_name: '',
    icon: '🔫',
    sort_order: 0,
    is_active: true,
  });

  // Delete Weapon State
  const [deleteTargetWeapon, setDeleteTargetWeapon] = useState<WeaponItem | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [catRes, wpnRes] = await Promise.all([
        api.get('/weapons/categories'),
        api.get('/weapons'),
      ]);
      if (catRes.data?.data) {
        setCategories(catRes.data.data);
      }
      if (wpnRes.data?.data) {
        setWeapons(wpnRes.data.data);
      }
    } catch (err) {
      console.error('Failed to load weapons & categories:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Filtered Weapons logic
  const filteredWeapons = weapons.filter((w) => {
    const matchesCat =
      selectedCategory === 'all' || w.category_id === selectedCategory.id;
    const matchesSearch =
      !searchQuery.trim() ||
      w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (w.display_name && w.display_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (w.category_name && w.category_name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesActive = !activeOnly || w.is_active;

    return matchesCat && matchesSearch && matchesActive;
  });

  // Handle Weapon Form Submit
  const handleSaveWeapon = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingWeapon) {
        await api.put(`/weapons/${editingWeapon.id}`, weaponForm);
      } else {
        await api.post('/weapons', weaponForm);
      }
      setIsWeaponModalOpen(false);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت سلاح');
    }
  };

  // Handle Category Form Submit
  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingCategory) {
        await api.put(`/weapons/categories/${editingCategory.id}`, categoryForm);
      } else {
        await api.post('/weapons/categories', categoryForm);
      }
      setIsCategoryModalOpen(false);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ثبت دسته‌بندی');
    }
  };

  const handleToggleWeaponActive = async (weapon: WeaponItem) => {
    try {
      await api.put(`/weapons/${weapon.id}`, {
        is_active: !weapon.is_active,
      });
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در تغییر وضعیت سلاح');
    }
  };

  const handleDeleteWeapon = async () => {
    if (!deleteTargetWeapon) return;
    try {
      await api.delete(`/weapons/${deleteTargetWeapon.id}`);
      setDeleteTargetWeapon(null);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در حذف سلاح');
    }
  };

  const handleOpenWeaponModal = (wpn?: WeaponItem) => {
    if (wpn) {
      setEditingWeapon(wpn);
      setWeaponForm({
        category_id: wpn.category_id,
        name: wpn.name,
        display_name: wpn.display_name || '',
        is_active: wpn.is_active,
      });
    } else {
      setEditingWeapon(null);
      const defaultCatId =
        selectedCategory !== 'all' ? selectedCategory.id : categories[0]?.id || 1;
      setWeaponForm({
        category_id: defaultCatId,
        name: '',
        display_name: '',
        is_active: true,
      });
    }
    setIsWeaponModalOpen(true);
  };

  const handleOpenCategoryModal = (cat?: CategoryItem) => {
    if (cat) {
      setEditingCategory(cat);
      setCategoryForm({
        name: cat.name,
        display_name: cat.display_name,
        icon: cat.icon || '🔫',
        sort_order: cat.sort_order,
        is_active: cat.is_active,
      });
    } else {
      setEditingCategory(null);
      setCategoryForm({
        name: '',
        display_name: '',
        icon: '🔫',
        sort_order: categories.length + 1,
        is_active: true,
      });
    }
    setIsCategoryModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER & TOP BANNER
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        {/* Subtle Ambient Glow */}
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/30">
              WEAPONS HUB
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              {weapons.length} سلاح در {categories.length} دسته‌بندی
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>کاتالوگ سلاح‌ها و دسته‌بندی‌ها</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            دسته‌بندی مورد نظر را از نوار زیر انتخاب کنید تا سلاح‌های مربوطه فیلتر و مدیریت شوند.
          </p>
        </div>

        {/* View Switcher & Actions */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="p-1 rounded-2xl bg-card-surface/60 border border-border flex items-center gap-1 shadow-inner">
            <button
              onClick={() => setActiveTab('weapons')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 ${
                activeTab === 'weapons'
                  ? 'bg-primary text-primary-text shadow-glow-primary font-black'
                  : 'text-mainText-muted hover:text-mainText'
              }`}
            >
              سلاح‌ها ({weapons.length})
            </button>
            <button
              onClick={() => setActiveTab('categories')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200 ${
                activeTab === 'categories'
                  ? 'bg-primary text-primary-text shadow-glow-primary font-black'
                  : 'text-mainText-muted hover:text-mainText'
              }`}
            >
              دسته‌بندی‌ها ({categories.length})
            </button>
          </div>

          <button
            onClick={() =>
              activeTab === 'weapons'
                ? handleOpenWeaponModal()
                : handleOpenCategoryModal()
            }
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105 active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>{activeTab === 'weapons' ? 'افزودن سلاح جدید' : 'افزودن دسته جدید'}</span>
          </button>
        </div>
      </div>

      {activeTab === 'weapons' ? (
        <>
          {/* ─────────────────────────────────────────────────────────────
              2. INTERACTIVE CATEGORY SELECTOR CARDS (Category-First Flow)
             ───────────────────────────────────────────────────────────── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-mainText-muted flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-primary" />
                <span>انتخاب دسته‌بندی سلاح (Category Navigation)</span>
              </span>
              <span className="text-[11px] text-mainText-subtle">
                کلیک روی هر دسته برای فیلتر آنی
              </span>
            </div>

            {/* Horizontal Scrollable Category Cards Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-2.5">
              {/* "All Weapons" Pill */}
              <button
                onClick={() => setSelectedCategory('all')}
                className={`p-3 rounded-2xl border text-right transition-all duration-200 flex flex-col justify-between group shadow-sm ${
                  selectedCategory === 'all'
                    ? 'bg-primary/15 border-primary shadow-glow-primary'
                    : 'bg-card border-border hover:border-primary/40 hover:bg-card-hover'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <Target className="w-5 h-5 text-primary" />
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md ${
                      selectedCategory === 'all'
                        ? 'bg-primary text-primary-text'
                        : 'bg-card-surface text-mainText-muted'
                    }`}
                  >
                    {weapons.length}
                  </span>
                </div>
                <span
                  className={`text-xs font-bold mt-2 truncate ${
                    selectedCategory === 'all' ? 'text-mainText' : 'text-mainText-muted'
                  }`}
                >
                  همه دسته‌ها
                </span>
              </button>

              {/* Each Category Card */}
              {categories.map((cat) => {
                const isSelected =
                  selectedCategory !== 'all' && selectedCategory.id === cat.id;
                const catCount = weapons.filter((w) => w.category_id === cat.id).length;

                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat)}
                    className={`p-3 rounded-2xl border text-right transition-all duration-200 flex flex-col justify-between group shadow-sm ${
                      isSelected
                        ? 'bg-primary/15 border-primary shadow-glow-primary'
                        : 'bg-card border-border hover:border-primary/40 hover:bg-card-hover'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <div className="group-hover:scale-110 transition-transform">
                        <CategoryIcon slug={cat.name} className="w-5 h-5 text-primary" />
                      </div>
                      <span
                        className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md ${
                          isSelected
                            ? 'bg-primary text-primary-text'
                            : 'bg-card-surface text-mainText-muted'
                        }`}
                      >
                        {catCount}
                      </span>
                    </div>

                    <div className="mt-2 overflow-hidden">
                      <span
                        className={`text-xs font-bold block truncate ${
                          isSelected ? 'text-mainText' : 'text-mainText-muted'
                        }`}
                      >
                        {cat.display_name}
                      </span>
                      <span className="text-[10px] text-mainText-subtle font-mono block truncate">
                        {cat.name}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────
              3. SEARCH & ACTIVE FILTER TOOLBAR
             ───────────────────────────────────────────────────────────── */}
          <div className="glass-panel p-4 rounded-2xl border border-border flex flex-wrap items-center justify-between gap-3">
            <div className="relative flex-1 min-w-[280px]">
              <Search className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-mainText-subtle" />
              <input
                type="text"
                placeholder={
                  selectedCategory === 'all'
                    ? 'جستجو در تمام ۱۳۰ سلاح بازی (مثلا: AK47, DLQ, KRM, M4)...'
                    : `جستجو در دسته ${selectedCategory.display_name}...`
                }
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary transition-all font-sans"
              />
            </div>

            <div className="flex items-center gap-3">
              {/* Active Only Filter */}
              <label className="flex items-center gap-2 cursor-pointer text-xs text-mainText-muted px-3 py-2 rounded-xl bg-card border border-border hover:text-mainText transition-colors">
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={(e) => setActiveOnly(e.target.checked)}
                  className="w-3.5 h-3.5 rounded text-primary bg-card border-border focus:ring-primary"
                />
                <span>فقط سلاح‌های فعال</span>
              </label>

              {/* Active Category Summary */}
              {selectedCategory !== 'all' && (
                <button
                  onClick={() => handleOpenWeaponModal()}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 text-xs font-semibold transition-all shadow-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>افزودن سلاح به {selectedCategory.display_name}</span>
                </button>
              )}
            </div>
          </div>

          {/* ─────────────────────────────────────────────────────────────
              4. WEAPONS GRID (Double-Bezel Hardware Cards)
             ───────────────────────────────────────────────────────────── */}
          {loading ? (
            <div className="py-20 text-center text-mainText-muted">
              <span className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block mb-3" />
              <p className="text-xs">در حال بارگذاری کاتالوگ سلاح‌ها...</p>
            </div>
          ) : filteredWeapons.length === 0 ? (
            <div className="glass-panel p-12 rounded-3xl border border-border text-center space-y-3">
              <Search className="w-10 h-10 text-mainText-muted mx-auto" />
              <h3 className="text-sm font-bold text-mainText">سلاحی با این مشخصات یافت نشد</h3>
              <p className="text-xs text-mainText-subtle max-w-sm mx-auto">
                عبارت جستجو یا فیلتر دسته‌بندی را تغییر دهید یا سلاح جدیدی اضافه کنید.
              </p>
              <button
                onClick={() => handleOpenWeaponModal()}
                className="mt-2 px-4 py-2 rounded-xl bg-primary text-primary-text font-bold text-xs shadow-glow-primary hover:bg-primary-hover transition-all"
              >
                افزودن سلاح جدید
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {filteredWeapons.map((wpn) => {
                return (
                  <div
                    key={wpn.id}
                    className="p-1 rounded-[22px] bg-card-surface/40 border border-border hover:border-primary/50 hover:shadow-card-elevated transition-all duration-300 group"
                  >
                    {/* Inner Core Container */}
                    <div className="p-4 rounded-[18px] bg-card border border-border-subtle flex flex-col justify-between h-full space-y-4 shadow-sm">
                      {/* Top Row: Category tag & Active switch */}
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded-md bg-card-surface border border-border text-mainText-muted">
                          {wpn.category_name}
                        </span>

                        {/* Active Toggle Pill */}
                        <button
                          onClick={() => handleToggleWeaponActive(wpn)}
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border transition-all ${
                            wpn.is_active
                              ? 'bg-primary/15 text-primary border-primary/30'
                              : 'bg-rose-500/10 text-rose-500 border-rose-500/30'
                          }`}
                          title="کلیک برای تغییر وضعیت فعال/غیرفعال"
                        >
                          {wpn.is_active ? '● فعال' : '○ غیرفعال'}
                        </button>
                      </div>

                      {/* Middle: Weapon Title */}
                      <div>
                        <h3 className="text-xl font-black text-mainText font-mono tracking-wide group-hover:text-primary transition-colors">
                          {wpn.name}
                        </h3>
                        {wpn.display_name && wpn.display_name !== wpn.name ? (
                          <p className="text-xs text-mainText-muted mt-0.5">{wpn.display_name}</p>
                        ) : (
                          <p className="text-xs text-mainText-subtle mt-0.5 font-mono">
                            ID: {wpn.id}
                          </p>
                        )}
                      </div>

                      {/* Bottom Stats & Quick Actions */}
                      <div className="pt-3 border-t border-border flex items-center justify-between">
                        {/* Attachments Counters */}
                        <div
                          onClick={() => navigate(`/attachments?weapon_id=${wpn.id}`)}
                          className="flex items-center gap-2 text-[11px] font-mono cursor-pointer hover:text-primary transition-colors"
                          title="مشاهده اتچمنت‌های این سلاح"
                        >
                          <span className="text-primary font-bold flex items-center gap-1">
                            <Compass className="w-3 h-3 text-primary" />
                            <span>{wpn.attachment_count_br || 0}</span>
                          </span>
                          <span className="text-mainText-subtle">•</span>
                          <span className="text-secondary font-bold flex items-center gap-1">
                            <Gamepad2 className="w-3 h-3 text-secondary" />
                            <span>{wpn.attachment_count_mp || 0}</span>
                          </span>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => navigate(`/attachments?weapon_id=${wpn.id}`)}
                            className="p-1.5 rounded-lg text-mainText-muted hover:text-primary hover:bg-primary/10 transition-colors"
                            title="مدیریت و افزودن اتچمنت برای این سلاح"
                          >
                            <Crosshair className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleOpenWeaponModal(wpn)}
                            className="p-1.5 rounded-lg text-mainText-muted hover:text-mainText hover:bg-card-surface transition-colors"
                            title="ویرایش نام سلاح"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteTargetWeapon(wpn)}
                            className="p-1.5 rounded-lg text-mainText-muted hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                            title="حذف سلاح"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        /* ─────────────────────────────────────────────────────────────
            5. CATEGORIES MANAGEMENT TABLE
           ───────────────────────────────────────────────────────────── */
        <div className="glass-panel rounded-3xl border border-border overflow-hidden">
          <table className="w-full text-right text-xs">
            <thead className="bg-card-surface/70 border-b border-border text-mainText-muted font-semibold">
              <tr>
                <th className="px-6 py-4">آیکون</th>
                <th className="px-6 py-4">نام شناسه انگلیسی (Slug)</th>
                <th className="px-6 py-4">عنوان نمایشی فارسی</th>
                <th className="px-6 py-4">ترتیب نمایش</th>
                <th className="px-6 py-4">آمار سلاح‌ها و بیلدها</th>
                <th className="px-6 py-4">وضعیت</th>
                <th className="px-6 py-4 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {categories.map((cat) => (
                <tr key={cat.id} className="hover:bg-card-hover transition-colors">
                  <td className="px-6 py-4">
                    <CategoryIcon slug={cat.name} className="w-5 h-5 text-primary" />
                  </td>
                  <td className="px-6 py-4 font-mono text-primary font-bold">
                    {cat.name}
                  </td>
                  <td className="px-6 py-4 font-bold text-mainText">{cat.display_name}</td>
                  <td className="px-6 py-4 font-mono text-mainText-muted">{cat.sort_order}</td>
                  <td className="px-6 py-4 font-mono text-mainText-muted">
                    <span className="text-mainText font-bold">{cat.weapon_count || 0}</span> سلاح /{' '}
                    <span className="text-primary font-bold">{cat.attachment_count || 0}</span> اتچمنت
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={cat.is_active ? 'primary' : 'ghost'}>
                      {cat.is_active ? 'فعال' : 'غیرفعال'}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <button
                      onClick={() => handleOpenCategoryModal(cat)}
                      className="p-1.5 rounded-lg text-mainText-muted hover:text-mainText hover:bg-card-surface transition-colors"
                      title="ویرایش دسته‌بندی"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          6. MODALS
         ───────────────────────────────────────────────────────────── */}

      {/* Weapon Modal */}
      <Modal
        isOpen={isWeaponModalOpen}
        onClose={() => setIsWeaponModalOpen(false)}
        title={editingWeapon ? 'ویرایش اطلاعات سلاح' : 'ثبت سلاح جدید در کاتالوگ'}
        maxWidth="md"
      >
        <form onSubmit={handleSaveWeapon} className="space-y-4">
          <div>
            <Select<number>
              label="دسته‌بندی سلاح"
              required
              value={weaponForm.category_id}
              onChange={(val) => setWeaponForm({ ...weaponForm, category_id: val })}
              options={categories.map((c) => ({
                value: c.id,
                label: `${c.display_name} (${c.name})`,
              }))}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              نام انگلیسی سلاح (بزرگ)
            </label>
            <input
              type="text"
              required
              placeholder="مثال: AK47, DLQ33, KRM262, BP50"
              value={weaponForm.name}
              onChange={(e) =>
                setWeaponForm({ ...weaponForm, name: e.target.value.toUpperCase() })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText font-mono uppercase focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              عنوان نمایشی فارسی (اختیاری)
            </label>
            <input
              type="text"
              placeholder="مثال: کلاشنیکف AK-47"
              value={weaponForm.display_name}
              onChange={(e) =>
                setWeaponForm({ ...weaponForm, display_name: e.target.value })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-xs text-mainText pt-1">
            <input
              type="checkbox"
              checked={weaponForm.is_active}
              onChange={(e) =>
                setWeaponForm({ ...weaponForm, is_active: e.target.checked })
              }
              className="w-4 h-4 rounded text-primary bg-card border-border focus:ring-primary"
            />
            <span>سلاح فعال باشد و در ربات و پنل نمایش داده شود</span>
          </label>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsWeaponModalOpen(false)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium transition-colors"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              {editingWeapon ? 'ذخیره تغییرات' : 'ثبت سلاح'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Category Modal */}
      <Modal
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        title={editingCategory ? 'ویرایش دسته‌بندی' : 'ثبت دسته‌بندی جدید'}
        maxWidth="md"
      >
        <form onSubmit={handleSaveCategory} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              نام شناسه انگلیسی (Slug)
            </label>
            <input
              type="text"
              required
              disabled={!!editingCategory}
              placeholder="مثال: assault_rifle, sniper, smg"
              value={categoryForm.name}
              onChange={(e) =>
                setCategoryForm({ ...categoryForm, name: e.target.value.toLowerCase() })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText font-mono focus:outline-none focus:border-primary disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              عنوان نمایشی فارسی
            </label>
            <input
              type="text"
              required
              placeholder="مثال: اسنایپر (Sniper Rifle)"
              value={categoryForm.display_name}
              onChange={(e) =>
                setCategoryForm({ ...categoryForm, display_name: e.target.value })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                آیکون پیش‌فرض
              </label>
              <input
                type="text"
                placeholder="SVG"
                value={categoryForm.icon}
                onChange={(e) =>
                  setCategoryForm({ ...categoryForm, icon: e.target.value })
                }
                className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
                ترتیب نمایش
              </label>
              <input
                type="number"
                value={categoryForm.sort_order}
                onChange={(e) =>
                  setCategoryForm({
                    ...categoryForm,
                    sort_order: Number(e.target.value),
                  })
                }
                className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsCategoryModalOpen(false)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium transition-colors"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              {editingCategory ? 'ذخیره تغییرات' : 'ثبت دسته‌بندی'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deleteTargetWeapon}
        onClose={() => setDeleteTargetWeapon(null)}
        title="تایید حذف سلاح"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-xs text-mainText-muted leading-relaxed">
            آیا از حذف سلاح <strong className="text-mainText">"{deleteTargetWeapon?.name}"</strong> اطمینان دارید؟ تمام اتچمنت‌های ثبت‌شده برای این سلاح نیز حذف خواهند شد.
          </p>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setDeleteTargetWeapon(null)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium transition-colors"
            >
              انصراف
            </button>
            <button
              onClick={handleDeleteWeapon}
              className="px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-bold text-xs shadow-rose-500/20 transition-all"
            >
              حذف قطعی
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
