import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Crosshair,
  Search,
  Plus,
  Filter,
  Star,
  Flame,
  Trash2,
  Edit2,
  Eye,
  Share2,
  ThumbsUp,
  Image as ImageIcon,
  Check,
  X,
  Copy,
  Layers,
  Sparkles,
  Zap,
  Target,
  Compass,
  Gamepad2,
} from 'lucide-react';
import { api } from '../../services/api';
import { AttachmentItem, CategoryItem, WeaponItem, PaginatedResponse } from '../../types';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { CategoryIcon } from '../../components/ui/CategoryIcon';
import { Select } from '../../components/ui/Select';

export const AttachmentsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialWeaponId = searchParams.get('weapon_id')
    ? Number(searchParams.get('weapon_id'))
    : 'all';

  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [weapons, setWeapons] = useState<WeaponItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedCodeId, setCopiedCodeId] = useState<number | null>(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<number | 'all'>('all');
  const [selectedWeapon, setSelectedWeapon] = useState<number | 'all'>(initialWeaponId);
  const [modeFilter, setModeFilter] = useState<'br' | 'mp' | 'all'>('all');
  const [topFilter, setTopFilter] = useState<boolean | 'all'>('all');
  const [seasonFilter, setSeasonFilter] = useState<boolean | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // Create / Edit Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAttachment, setEditingAttachment] = useState<AttachmentItem | null>(null);
  const [modalForm, setModalForm] = useState({
    weapon_id: 0,
    mode: 'br' as 'br' | 'mp',
    name: '',
    code: '',
    image_file_id: '',
    is_top: false,
    is_season_top: false,
    order_index: 0,
  });

  // Delete Confirm Modal
  const [deleteTarget, setDeleteTarget] = useState<AttachmentItem | null>(null);

  // Fetch Categories & Weapons
  const fetchMetadata = async () => {
    try {
      const [catRes, wpnRes] = await Promise.all([
        api.get('/weapons/categories'),
        api.get('/weapons'),
      ]);
      if (catRes.data?.data) setCategories(catRes.data.data);
      if (wpnRes.data?.data) setWeapons(wpnRes.data.data);
    } catch (err) {
      console.error('Failed to load categories/weapons:', err);
    }
  };

  // Fetch Attachments
  const fetchAttachments = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: 15,
      };
      if (modeFilter !== 'all') params.mode = modeFilter;
      if (selectedCategory !== 'all') params.category_id = selectedCategory;
      if (selectedWeapon !== 'all') params.weapon_id = selectedWeapon;
      if (topFilter !== 'all') params.is_top = topFilter;
      if (seasonFilter !== 'all') params.is_season_top = seasonFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const res = await api.get<{ success: boolean; data: PaginatedResponse<AttachmentItem> }>(
        '/attachments',
        { params }
      );

      if (res.data?.data) {
        setAttachments(res.data.data.items);
        setTotalPages(res.data.data.meta.total_pages);
        setTotalItems(res.data.data.meta.total_items);
      }
    } catch (err) {
      console.error('Failed to fetch attachments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetadata();
  }, []);

  useEffect(() => {
    fetchAttachments();
  }, [modeFilter, selectedCategory, selectedWeapon, topFilter, seasonFilter, page]);

  const handleCopyCode = (id: number, code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCodeId(id);
    setTimeout(() => setCopiedCodeId(null), 2000);
  };

  const handleOpenCreateModal = () => {
    setEditingAttachment(null);
    const defaultWpnId =
      selectedWeapon !== 'all' ? selectedWeapon : weapons[0]?.id || 1;
    setModalForm({
      weapon_id: defaultWpnId,
      mode: modeFilter !== 'all' ? modeFilter : 'br',
      name: '',
      code: '',
      image_file_id: '',
      is_top: false,
      is_season_top: false,
      order_index: 0,
    });
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (att: AttachmentItem) => {
    setEditingAttachment(att);
    setModalForm({
      weapon_id: att.weapon_id,
      mode: att.mode,
      name: att.name,
      code: att.code,
      image_file_id: att.image_file_id || '',
      is_top: att.is_top,
      is_season_top: att.is_season_top,
      order_index: att.order_index || 0,
    });
    setIsModalOpen(true);
  };

  const handleSaveAttachment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingAttachment) {
        await api.put(`/attachments/${editingAttachment.id}`, modalForm);
      } else {
        await api.post('/attachments', modalForm);
      }
      setIsModalOpen(false);
      fetchAttachments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'خطا در ذخیره اتچمنت');
    }
  };

  const handleToggleTop = async (id: number) => {
    try {
      await api.post(`/attachments/${id}/toggle-top`);
      fetchAttachments();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleSeasonTop = async (id: number) => {
    try {
      await api.post(`/attachments/${id}/toggle-season-top`);
      fetchAttachments();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteAttachment = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/attachments/${deleteTarget.id}`);
      setDeleteTarget(null);
      fetchAttachments();
    } catch (err) {
      console.error(err);
    }
  };

  // Weapons list filtered by selectedCategory
  const availableWeapons =
    selectedCategory === 'all'
      ? weapons
      : weapons.filter((w) => w.category_id === selectedCategory);

  return (
    <div className="space-y-6">
      {/* ─────────────────────────────────────────────────────────────
          1. HEADER BANNER
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-6 rounded-3xl border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative overflow-hidden">
        <div className="absolute -right-12 -top-12 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-mono font-bold uppercase tracking-wider border border-primary/30">
              OFFICIAL BUILDS
            </span>
            <span className="text-xs text-mainText-muted font-mono">
              {totalItems} اتچمنت ثبت‌شده
            </span>
          </div>

          <h2 className="text-2xl font-black text-mainText tracking-tight flex items-center gap-2.5 mt-1.5 font-mono">
            <span>مدیریت بیلدها و اتچمنت‌های رسمی</span>
          </h2>
          <p className="text-xs text-mainText-subtle mt-1">
            کدهای اشتراک‌گذاری، برچسب‌های متای برتر و فصل را فیلتر و مدیریت کنید.
          </p>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="relative z-10 flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-primary hover:bg-primary-hover text-primary-text font-black text-xs shadow-glow-primary transition-all duration-200 hover:scale-105 active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>افزودن اتچمنت رسمی جدید</span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. CATEGORY PILLS BAR
         ───────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        <button
          onClick={() => {
            setSelectedCategory('all');
            setSelectedWeapon('all');
            setPage(1);
          }}
          className={`px-3.5 py-2 rounded-xl text-xs font-bold shrink-0 border transition-all flex items-center gap-1.5 shadow-sm ${
            selectedCategory === 'all'
              ? 'bg-primary text-primary-text border-primary shadow-glow-primary font-black'
              : 'bg-card text-mainText-muted border-border hover:text-mainText hover:bg-card-hover'
          }`}
        >
          <Target className="w-3.5 h-3.5" />
          <span>همه دسته‌ها</span>
        </button>

        {categories.map((c) => (
          <button
            key={c.id}
            onClick={() => {
              setSelectedCategory(c.id);
              setSelectedWeapon('all');
              setPage(1);
            }}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold shrink-0 border transition-all flex items-center gap-1.5 shadow-sm ${
              selectedCategory === c.id
                ? 'bg-primary text-primary-text border-primary shadow-glow-primary font-black'
                : 'bg-card text-mainText-muted border-border hover:text-mainText hover:bg-card-hover'
            }`}
          >
            <CategoryIcon slug={c.name} className="w-4 h-4 text-primary" />
            <span>{c.display_name}</span>
          </button>
        ))}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. FILTER & TOOLBAR
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel p-4 rounded-2xl border border-border flex flex-wrap items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-mainText-subtle" />
          <input
            type="text"
            placeholder="جستجوی نام بیلد، نام سلاح یا کد اشتراک‌گذاری..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full pr-10 pl-4 py-2 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary transition-all font-sans"
          />
        </div>

        {/* Weapons Dropdown */}
        <div className="w-56 min-w-[180px]">
          <Select<number | 'all'>
            value={selectedWeapon}
            onChange={(val) => {
              setSelectedWeapon(val);
              setPage(1);
            }}
            searchable={availableWeapons.length > 5}
            searchPlaceholder="جستجوی سلاح..."
            options={[
              { value: 'all', label: `همه سلاح‌ها (${availableWeapons.length})` },
              ...availableWeapons.map((w) => ({
                value: w.id,
                label: w.name,
                sublabel: w.display_name,
              })),
            ]}
          />
        </div>

        {/* Mode Filter */}
        <div className="w-48 min-w-[150px]">
          <Select<'all' | 'br' | 'mp'>
            value={modeFilter}
            onChange={(val) => {
              setModeFilter(val);
              setPage(1);
            }}
            options={[
              { value: 'all', label: 'همه مودها (BR & MP)' },
              {
                value: 'br',
                label: 'بتل رویال (BR)',
                badge: <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />,
              },
              {
                value: 'mp',
                label: 'مولتی‌پلیر (MP)',
                badge: <span className="w-2 h-2 rounded-full bg-primary inline-block" />,
              },
            ]}
          />
        </div>

        {/* Badges Filters */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setTopFilter(topFilter === true ? 'all' : true);
              setPage(1);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
              topFilter === true
                ? 'bg-accent/20 text-accent border-accent/40 shadow-glow-accent'
                : 'bg-card text-mainText-muted border-border hover:text-mainText'
            }`}
          >
            <Star className="w-3.5 h-3.5" />
            <span>اتچمنت‌های برتر</span>
          </button>

          <button
            onClick={() => {
              setSeasonFilter(seasonFilter === true ? 'all' : true);
              setPage(1);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
              seasonFilter === true
                ? 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-sm'
                : 'bg-card text-mainText-muted border-border hover:text-mainText'
            }`}
          >
            <Flame className="w-3.5 h-3.5" />
            <span>متای فصل جاری</span>
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. ATTACHMENTS TABLE / CARDS
         ───────────────────────────────────────────────────────────── */}
      <div className="glass-panel rounded-3xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-card-surface/70 border-b border-border text-mainText-muted font-semibold">
              <tr>
                <th className="px-6 py-4">سلاح و دسته</th>
                <th className="px-6 py-4">عنوان بیلد اتچمنت</th>
                <th className="px-6 py-4">مود بازی</th>
                <th className="px-6 py-4">کد لوداوت (Share Code)</th>
                <th className="px-6 py-4">وضعیت نشان‌ها</th>
                <th className="px-6 py-4">آمار تعامل</th>
                <th className="px-6 py-4 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-mainText-muted">
                    <span className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin inline-block mb-2" />
                    <p>در حال بارگذاری لیست اتچمنت‌ها...</p>
                  </td>
                </tr>
              ) : attachments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-mainText-muted">
                    هیچ اتچمنتی با فیلترهای انتخابی یافت نشد.
                  </td>
                </tr>
              ) : (
                attachments.map((att) => (
                  <tr key={att.id} className="hover:bg-card-hover transition-colors group">
                    {/* Weapon & Category */}
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-black text-mainText font-mono text-sm group-hover:text-primary transition-colors">
                          {att.weapon_name}
                        </span>
                        <span className="text-[11px] text-mainText-muted">{att.category_name}</span>
                      </div>
                    </td>

                    {/* Attachment Name */}
                    <td className="px-6 py-4 font-bold text-mainText">{att.name}</td>

                    {/* Mode */}
                    <td className="px-6 py-4">
                      <Badge variant={att.mode === 'br' ? 'primary' : 'secondary'}>
                        <span className="flex items-center gap-1">
                          {att.mode === 'br' ? (
                            <Compass className="w-3 h-3 text-primary" />
                          ) : (
                            <Gamepad2 className="w-3 h-3 text-secondary" />
                          )}
                          <span>{att.mode === 'br' ? 'BR' : 'MP'}</span>
                        </span>
                      </Badge>
                    </td>

                    {/* Code & Copy button */}
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleCopyCode(att.id, att.code)}
                        className="inline-flex items-center gap-1.5 font-mono bg-card-surface px-2.5 py-1 rounded-lg text-primary border border-border text-[11px] hover:border-primary transition-colors shadow-sm font-bold"
                        title="کپی کردن کد لوداوت"
                      >
                        <span>{att.code}</span>
                        {copiedCodeId === att.id ? (
                          <Check className="w-3.5 h-3.5 text-primary" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-mainText-subtle" />
                        )}
                      </button>
                    </td>

                    {/* Badges Toggles */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleToggleTop(att.id)}
                          className={`p-1.5 rounded-lg border transition-all ${
                            att.is_top
                              ? 'bg-accent/20 text-accent border-accent/50 shadow-sm'
                              : 'bg-card-surface text-mainText-subtle border-border hover:text-mainText'
                          }`}
                          title={att.is_top ? 'حذف از اتچمنت‌های برتر' : 'تنظیم به عنوان اتچمنت برتر'}
                        >
                          <Star className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleSeasonTop(att.id)}
                          className={`p-1.5 rounded-lg border transition-all ${
                            att.is_season_top
                              ? 'bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-sm'
                              : 'bg-card-surface text-mainText-subtle border-border hover:text-mainText'
                          }`}
                          title={att.is_season_top ? 'حذف از متای فصل' : 'تنظیم به عنوان متای فصل'}
                        >
                          <Flame className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>

                    {/* Engagement Stats */}
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3 text-mainText-muted text-[11px] font-mono">
                        <span className="flex items-center gap-1">
                          <Eye className="w-3.5 h-3.5" />
                          {att.views_count || 0}
                        </span>
                        <span className="flex items-center gap-1 text-primary font-bold">
                          <ThumbsUp className="w-3.5 h-3.5" />
                          {att.likes_count || 0}
                        </span>
                      </div>
                    </td>

                    {/* Action buttons */}
                    <td className="px-6 py-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => handleOpenEditModal(att)}
                          className="p-1.5 rounded-lg text-mainText-muted hover:text-mainText hover:bg-card-surface transition-colors"
                          title="ویرایش"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setDeleteTarget(att)}
                          className="p-1.5 rounded-lg text-mainText-muted hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                          title="حذف"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="px-6 py-4 border-t border-border bg-card-surface/30 flex items-center justify-between text-xs text-mainText-muted">
          <span>مجموع: {totalItems} اتچمنت</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1.5 rounded-lg bg-card hover:bg-card-hover text-mainText border border-border disabled:opacity-40 transition-colors shadow-sm"
            >
              صفحه قبل
            </button>
            <span className="font-mono text-mainText font-bold">
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1.5 rounded-lg bg-card hover:bg-card-hover text-mainText border border-border disabled:opacity-40 transition-colors shadow-sm"
            >
              صفحه بعد
            </button>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          5. CREATE / EDIT ATTACHMENT MODAL
         ───────────────────────────────────────────────────────────── */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingAttachment ? 'ویرایش اطلاعات اتچمنت' : 'افزودن اتچمنت رسمی جدید'}
        maxWidth="lg"
      >
        <form onSubmit={handleSaveAttachment} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Weapon Select */}
            <div>
              <Select<number>
                label="انتخاب سلاح"
                required
                searchable
                searchPlaceholder="جستجو در سلاح‌ها..."
                value={modalForm.weapon_id}
                onChange={(val) => setModalForm({ ...modalForm, weapon_id: val })}
                options={weapons.map((w) => ({
                  value: w.id,
                  label: w.name,
                  sublabel: w.display_name || w.category_name,
                }))}
              />
            </div>

            {/* Mode Select */}
            <div>
              <Select<'br' | 'mp'>
                label="مود بازی"
                value={modalForm.mode}
                onChange={(val) => setModalForm({ ...modalForm, mode: val })}
                options={[
                  {
                    value: 'br',
                    label: 'بتل رویال (Battle Royale)',
                    badge: <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />,
                  },
                  {
                    value: 'mp',
                    label: 'مولتی‌پلیر (Multiplayer)',
                    badge: <span className="w-2 h-2 rounded-full bg-primary inline-block" />,
                  },
                ]}
              />
            </div>
          </div>

          {/* Attachment Name */}
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              عنوان / نام بیلد اتچمنت
            </label>
            <input
              type="text"
              required
              placeholder="مثال: بیلد دوربرد و بدون لگد (Long Range Meta)"
              value={modalForm.name}
              onChange={(e) => setModalForm({ ...modalForm, name: e.target.value })}
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText focus:outline-none focus:border-primary"
            />
          </div>

          {/* Loadout Code */}
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              کد اشتراک‌گذاری (Share Code)
            </label>
            <input
              type="text"
              required
              placeholder="مثال: AK47-1A2B3C4D5E"
              value={modalForm.code}
              onChange={(e) =>
                setModalForm({ ...modalForm, code: e.target.value.toUpperCase() })
              }
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-primary font-mono focus:outline-none focus:border-primary uppercase"
            />
          </div>

          {/* Telegram Image File ID */}
          <div>
            <label className="block text-xs font-semibold text-mainText-muted mb-1.5">
              شناسه تصویر تلگرام (اختیاری)
            </label>
            <input
              type="text"
              placeholder="AgACAgIAAxkBAAI..."
              value={modalForm.image_file_id}
              onChange={(e) => setModalForm({ ...modalForm, image_file_id: e.target.value })}
              className="w-full px-3 py-2.5 bg-card border border-border rounded-xl text-xs text-mainText font-mono focus:outline-none focus:border-primary"
            />
          </div>

          {/* Checkboxes */}
          <div className="flex items-center gap-6 pt-2">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-mainText">
              <input
                type="checkbox"
                checked={modalForm.is_top}
                onChange={(e) => setModalForm({ ...modalForm, is_top: e.target.checked })}
                className="w-4 h-4 rounded text-primary bg-card border-border focus:ring-primary"
              />
              <span className="flex items-center gap-1">
                <Star className="w-3.5 h-3.5 text-accent" />
                <span>اتچمنت برتر (Top Build)</span>
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-mainText">
              <input
                type="checkbox"
                checked={modalForm.is_season_top}
                onChange={(e) => setModalForm({ ...modalForm, is_season_top: e.target.checked })}
                className="w-4 h-4 rounded text-primary bg-card border-border focus:ring-primary"
              />
              <span className="flex items-center gap-1">
                <Flame className="w-3.5 h-3.5 text-rose-400" />
                <span>متای سیزن جاری (Season Meta)</span>
              </span>
            </label>
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 rounded-xl bg-card-surface hover:bg-card-hover text-mainText-muted hover:text-mainText text-xs font-medium transition-colors"
            >
              انصراف
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-primary hover:bg-primary-hover text-primary-text font-bold text-xs shadow-glow-primary transition-all"
            >
              {editingAttachment ? 'ذخیره تغییرات' : 'افزودن اتچمنت'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="تایید حذف اتچمنت"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-xs text-mainText-muted leading-relaxed">
            آیا از حذف اتچمنت <strong className="text-mainText">"{deleteTarget?.name}"</strong> مربوط به سلاح <strong className="text-mainText">{deleteTarget?.weapon_name}</strong> اطمینان دارید؟
          </p>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setDeleteTarget(null)}
              className="px-4 py-2 rounded-xl bg-card-surface text-mainText-muted hover:text-mainText text-xs font-medium transition-colors"
            >
              انصراف
            </button>
            <button
              onClick={handleDeleteAttachment}
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
