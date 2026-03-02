from core.context import CustomContext
"""
Browse Handler - نمایش اتچمنت‌های تایید شده کاربران
"""

import json
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config.config import WEAPON_CATEGORIES, WEAPON_CATEGORIES_SHORT, GAME_MODES, build_category_keyboard
from core.database.database_adapter import get_database_adapter
from core.cache.ua_cache_manager import get_ua_cache
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t

logger = get_logger('browse_attachments', 'user.log')
db = get_database_adapter()
cache = get_ua_cache(db, ttl_seconds=300)

# تعداد اتچمنت در هر صفحه
ATTACHMENTS_PER_PAGE = 5


async def browse_attachments_menu(update: Update, context: CustomContext):
    """منوی اصلی Browse"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # دریافت مودهای فعال
    enabled_modes_str = await db.get_ua_setting('enabled_modes') or '["mp","br"]'
    enabled_modes = json.loads(enabled_modes_str)
    
    keyboard = []
    mode_buttons = []
    
    # ترتیب: BR راست، MP چپ
    if 'br' in enabled_modes:
        mode_buttons.append(InlineKeyboardButton(t("mode.br_btn", lang), callback_data="ua_browse_mode_br"))
    if 'mp' in enabled_modes:
        mode_buttons.append(InlineKeyboardButton(t("mode.mp_btn", lang), callback_data="ua_browse_mode_mp"))
    
    if not mode_buttons:
        await query.edit_message_text(
            t('ua.error.no_active_modes', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")]
            ])
        )
        return
    
    # Always show mode buttons vertically (one per row)
    for btn in mode_buttons:
        keyboard.append([btn])
    
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
    
    await query.edit_message_text(
        f"{t('ua.browse', lang)}\n\n" + t('mode.choose', lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def browse_mode_selected(update: Update, context: CustomContext):
    """انتخاب مود برای Browse"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.split('_')[-1]  # br یا mp
    context.user_data['browse_mode'] = mode
    
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{mode}_btn", lang)
    
    # منوی فیلتر: همه یا انتخاب دسته
    keyboard = [
        [InlineKeyboardButton(t("list.show", lang), callback_data=f"ua_browse_all_{mode}")],
        [InlineKeyboardButton(t("category.choose", lang), callback_data=f"ua_browse_select_cat_{mode}")],
        [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_browse")]
    ]
    
    await query.edit_message_text(
        f"*{t('ua.browse', lang)}*\n━━━━━━━━━━━━━━\n{t('mode.label', lang)}: {mode_name}\n\n{t('mode.choose', lang)}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def browse_show_category_menu(update: Update, context: CustomContext):
    """نمایش منوی انتخاب دسته‌بندی"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.split('_')[-1]  # br یا mp
    context.user_data['browse_mode'] = mode
    
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{mode}_btn", lang)
    
    # فیلتر کردن دسته‌های فعال برای mode انتخاب شده
    from config.config import is_category_enabled
    active_categories = {}
    db_instance = context.bot_data.get('db')
    for k, v in WEAPON_CATEGORIES.items():
        if await is_category_enabled(k, mode, db_instance):
            active_categories[k] = v
    
    if not active_categories:
        await query.edit_message_text(
            f"{t('mode.label', lang)}: {mode_name}\n\n" + t('category.none', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_browse")]
            ])
        )
        return
    
    # نمایش دسته‌بندی‌ها
    keyboard = await build_category_keyboard(
        callback_prefix="ua_browse_cat_",
        show_count=False,
        db=None,
        lang=lang,
        active_ids=list(active_categories.keys())
    )
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data=f"ua_browse_mode_{mode}")])
    
    await query.edit_message_text(
        f"{t('mode.label', lang)}: {mode_name}\n" + t('category.choose', lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def browse_show_all_attachments(update: Update, context: CustomContext):
    """نمایش همه اتچمنت‌ها (تمام دسته‌ها)"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.split('_')[-1]  # br یا mp
    context.user_data['browse_mode'] = mode
    context.user_data['browse_category'] = 'all'  # علامت همه دسته‌ها
    
    # فیلتر کردن دسته‌های فعال برای mode انتخاب شده
    from config.config import is_category_enabled
    enabled_categories = [k for k in WEAPON_CATEGORIES.keys() if await is_category_enabled(k, mode, context.bot_data.get('db'))]
    
    # آماده‌سازی صفحه‌بندی
    context.user_data['browse_page'] = 0
    
    # نمایش صفحه اول
    await show_attachments_page(update, context)


async def browse_category_selected(update: Update, context: CustomContext):
    """انتخاب دسته - نمایش مستقیم اتچمنت‌ها"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace('ua_browse_cat_', '')
    context.user_data['browse_category'] = category
    
    mode = context.user_data['browse_mode']
    
    # آماده‌سازی صفحه‌بندی
    context.user_data['browse_page'] = 0
    
    # نمایش صفحه اول
    await show_attachments_page(update, context)


async def show_attachments_page(update: Update, context: CustomContext):
    """نمایش یک صفحه از اتچمنت‌ها"""
    query = update.callback_query
    if query:
        await query.answer()
    
    mode = context.user_data.get('browse_mode', 'br')
    category = context.user_data.get('browse_category', 'all')
    page = context.user_data.get('browse_page', 0)
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # دریافت آمار و داده‌ها از دیتابیس
    total_count = await db.get_approved_user_attachments_count(mode, category)
    if total_count == 0:
        mode_name = t(f"mode.{mode}_btn", lang)
        cat_name = t(f"category.{category}", 'en') if category != 'all' else t('ua.all_categories', lang)
        await query.edit_message_text(
            f"{t('mode.label', lang)}: {mode_name} › {cat_name}\n\n" + t('attachment.none', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("ua.submit", lang), callback_data="ua_submit"),
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data=f"ua_browse_mode_{mode}")
            ]])
        )
        return

    attachments = await db.get_approved_user_attachments_paginated(
        mode, category, 
        limit=ATTACHMENTS_PER_PAGE, 
        offset=page * ATTACHMENTS_PER_PAGE
    )
    
    # اطمینان از صحت نمایش نام سلاح
    for att in attachments:
        if not att.get('weapon_display') and att.get('custom_weapon_name'):
            att['weapon_display'] = att['custom_weapon_name']
    
    mode_name = t(f"mode.{mode}_btn", lang)
    cat_display = t('ua.all_categories', lang) if category == 'all' else WEAPON_CATEGORIES_SHORT.get(category, category)
    
    total_pages = (total_count - 1) // ATTACHMENTS_PER_PAGE + 1
    start_idx = page * ATTACHMENTS_PER_PAGE + 1
    end_idx = start_idx + len(attachments) - 1
    
    # ساخت پیام
    message = (
        f"*{t('ua.browse', lang)}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{t('mode.label', lang)}: {mode_name}  |  {cat_display}\n"
        f"{t('pagination.page_of', lang, page=page+1, total=total_pages)}  •  "
        f"{t('pagination.showing_range', lang, start=start_idx, end=end_idx, total=total_count)}\n"
    )
    
    # ساخت کیبورد
    keyboard = []
    
    for att in attachments:
        weapon = att.get('custom_weapon_name') or t('common.unknown', lang)
        att_name = att.get('name') or att.get('attachment_name') or t('common.unknown', lang)
        likes = att.get('like_count', 0)
        username = (att.get('username') or att.get('first_name') or t('user.anonymous', lang))
        cat_key = att.get('category', '')
        
        # اگر همه دسته‌ها: نمایش مخفف دسته
        if category == 'all':
            cat_short = WEAPON_CATEGORIES_SHORT.get(cat_key, cat_key)
            button_text = f"{cat_short} • {weapon} — {att_name[:18]}"
        else:
            button_text = f"🔫 {weapon} — {att_name[:22]}"
        
        # نمایش لایک‌ها اگر وجود داشت
        if likes > 0:
            button_text += f"  👍{likes}"
        
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"ua_view_{att['id']}"
            )
        ])
    
    # دکمه‌های pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(t('nav.prev', lang), callback_data="ua_browse_prev"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(t('nav.next', lang), callback_data="ua_browse_next"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data=f"ua_browse_mode_{context.user_data['browse_mode']}")])
    
    if query:
        try:
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            # اگر پیام photo بود، نمیشه edit کرد
            # پس delete کن و پیام جدید بفرست
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete previous browse message: {e}")
            await update.effective_chat.send_message(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def browse_prev_page(update: Update, context: CustomContext):
    """صفحه قبل"""
    context.user_data['browse_page'] = max(0, context.user_data.get('browse_page', 0) - 1)
    await show_attachments_page(update, context)


async def browse_next_page(update: Update, context: CustomContext):
    """صفحه بعد"""
    context.user_data['browse_page'] = context.user_data.get('browse_page', 0) + 1
    await show_attachments_page(update, context)


async def view_attachment_detail(update: Update, context: CustomContext):
    """نمایش جزئیات یک اتچمنت"""
    query = update.callback_query
    await query.answer()
    
    attachment_id = int(query.data.replace('ua_view_', ''))
    
    # دریافت اتچمنت
    attachment = await db.get_user_attachment(attachment_id)
    
    if not attachment:
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('attachment.not_found', lang), show_alert=True)
        return
    
    # افزایش view_count
    try:
        async with db.transaction() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE user_attachments 
                    SET view_count = view_count + 1 
                    WHERE id = %s
                """, (attachment_id,))
    except Exception as e:
        logger.error(f"Error updating view count: {e}")
    
    # ساخت پیام
    from telegram.helpers import escape_markdown
    
    lang = await get_user_lang(update, context, db) or 'fa'
    username = attachment.get('username') or attachment.get('first_name') or t('user.anonymous', lang)
    description = attachment.get('description') or t('common.no_description', lang)
    views = attachment.get('view_count', 0) + 1
    
    mode_name = t(f"mode.{attachment['mode']}_short", lang)
    
    # Escape for MarkdownV2
    att_name = escape_markdown(str(attachment.get('attachment_name', attachment.get('name', 'Unknown'))), version=2)
    mode_name_esc = escape_markdown(str(mode_name), version=2)
    
    # Safe access for weapon name
    weapon_raw = attachment.get('custom_weapon_name') or attachment.get('weapon_name') or t('common.unknown', lang)
    weapon_name = escape_markdown(str(weapon_raw), version=2)
    
    # دریافت نام دسته با ترجمه
    category_key = attachment.get('category', attachment.get('category_name', ''))
    category_local = t(f"category.{category_key}", 'en')
    category_name = escape_markdown(str(category_local), version=2)
    
    description_esc = escape_markdown(str(description), version=2)
    # Format submitted_at safely (datetime | date | str | None)
    sub_at = attachment.get('submitted_at')
    if isinstance(sub_at, datetime):
        sub_ts = sub_at.date().isoformat()
    elif isinstance(sub_at, date):
        sub_ts = sub_at.isoformat()
    elif isinstance(sub_at, str):
        sub_ts = sub_at[:10]
    else:
        sub_ts = t('common.unknown', lang)
    date_str = escape_markdown(sub_ts, version=2)
    
    caption = (
        f"📎 *{att_name}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎮 *{t('mode.label', lang)}:* {mode_name_esc}  •  "
        f"📂 {category_name}\n"
        f"🔫 *{t('weapon.label', lang)}:* {weapon_name}\n\n"
        f"💬 {description_esc}\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 @{escape_markdown(str(username), version=2)}  •  "
        f"📅 {date_str}  •  👁 {views}"
    )
    
    # بررسی اینکه کاربر قبلاً این پست را گزارش کرده یا نه، برای مخفی کردن دکمه گزارش
    already_reported = False
    try:
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(
                        """
                        SELECT 1 FROM user_attachment_reports
                        WHERE attachment_id = %s AND reporter_id = %s
                        LIMIT 1
                        """,
                        (attachment_id, update.effective_user.id),
                    )
                except Exception:
                    await cur.execute(
                        """
                        SELECT 1 FROM user_attachment_reports
                        WHERE attachment_id = %s AND user_id = %s
                        LIMIT 1
                        """,
                        (attachment_id, update.effective_user.id),
                    )
                already_reported = await cur.fetchone() is not None
    except Exception as _pre_err:
        logger.error(f"Error prechecking already_reported: {_pre_err}")

    row1 = [InlineKeyboardButton("👍", callback_data=f"ua_like_{attachment_id}")]
    if not already_reported:
        row1.append(InlineKeyboardButton("⚠️", callback_data=f"ua_report_{attachment_id}"))
    keyboard = [
        row1,
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_browse_back")]
    ]
    
    # ارسال تصویر
    await query.message.reply_photo(
        photo=attachment['image_file_id'],
        caption=caption,
        parse_mode='MarkdownV2',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # حذف پیام قبلی
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete previous attachment detail message: {e}")


async def like_attachment(update: Update, context: CustomContext):
    """لایک اتچمنت"""
    query = update.callback_query
    
    attachment_id = int(query.data.replace('ua_like_', ''))
    
    try:
        async with db.transaction() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE user_attachments 
                    SET like_count = like_count + 1 
                    WHERE id = %s
                """, (attachment_id,))
        
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('success.generic', lang), show_alert=True)
    except Exception as e:
        logger.error(f"Error liking attachment: {e}")
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('error.generic', lang), show_alert=True)


async def report_attachment(update: Update, context: CustomContext):
    """گزارش اتچمنت"""
    query = update.callback_query
    
    attachment_id = int(query.data.replace('ua_report_', ''))
    reporter_id = update.effective_user.id
    
    # محدودیت‌ها: هر کاربر فقط یکبار برای هر پست، و حداکثر 5 گزارش در روز
    today_count = 0
    try:
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                # بررسی گزارش تکراری برای همان پست
                try:
                    await cur.execute(
                        """
                        SELECT 1 
                        FROM user_attachment_reports 
                        WHERE attachment_id = %s AND reporter_id = %s 
                        LIMIT 1
                        """,
                        (attachment_id, reporter_id),
                    )
                except Exception:
                    # سازگاری با اسکیما قدیمی (user_id به جای reporter_id)
                    await cur.execute(
                        """
                        SELECT 1 
                        FROM user_attachment_reports 
                        WHERE attachment_id = %s AND user_id = %s 
                        LIMIT 1
                        """,
                        (attachment_id, reporter_id),
                    )
                dup = await cur.fetchone()
                if dup:
                    lang = await get_user_lang(update, context, db) or 'fa'
                    await query.answer(t('ua.report.duplicate', lang), show_alert=True)
                    return
                
                # محدودیت ۵ گزارش در روز
                today_count = 0
                try:
                    await cur.execute(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM user_attachment_reports 
                        WHERE reporter_id = %s AND reported_at >= CURRENT_DATE
                        """,
                        (reporter_id,),
                    )
                except Exception:
                    # سازگاری با ستون created_at
                    await cur.execute(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM user_attachment_reports 
                        WHERE user_id = %s AND created_at >= CURRENT_DATE
                        """,
                        (reporter_id,),
                    )
                row = await cur.fetchone()
                today_count = int((row or {}).get('cnt') or 0)
                if today_count >= 5:
                    lang = await get_user_lang(update, context, db) or 'fa'
                    await query.answer(t('ua.report.limit_reached', lang), show_alert=True)
                    return
    except Exception as pre_err:
        logger.error(f"Precheck error on reporting attachment: {pre_err}")

    # ذخیره report (ساده)
    try:
        async with db.transaction() as conn:
            async with conn.cursor() as cursor:
                # افزایش report_count
                await cursor.execute("""
                    UPDATE user_attachments 
                    SET report_count = report_count + 1 
                    WHERE id = %s
                """, (attachment_id,))
                
                # ثبت در جدول reports (با fallback برای اسکیما قدیمی)
                try:
                    await cursor.execute("""
                        INSERT INTO user_attachment_reports (attachment_id, reporter_id, reason, reported_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    """, (attachment_id, reporter_id, 'محتوای نامناسب'))
                except Exception:
                    await cursor.execute("""
                        INSERT INTO user_attachment_reports (attachment_id, user_id, reason, created_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    """, (attachment_id, reporter_id, 'محتوای نامناسب'))
        # بعد از ثبت گزارش، کش آمار را پاک می‌کنیم تا شمارنده‌ها به‌روز شوند
        try:
            await cache.invalidate('stats')
        except Exception:
            pass
        used_now = (today_count or 0) + 1
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('ua.report.saved_today', lang, used=used_now), show_alert=True)
    except Exception as e:
        logger.error(f"Error reporting attachment: {e}")
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('ua.report.duplicate', lang), show_alert=True)


async def browse_back_to_list(update: Update, context: CustomContext):
    """بازگشت به لیست"""
    query = update.callback_query
    await query.answer()
    
    # حذف پیام تصویر
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete browse image message: {e}")
    
    # نمایش مجدد لیست
    await show_attachments_page(update, context)


# Export handlers
browse_handlers = [
    CallbackQueryHandler(browse_attachments_menu, pattern="^ua_browse$"),
    CallbackQueryHandler(browse_mode_selected, pattern="^ua_browse_mode_(br|mp)$"),
    CallbackQueryHandler(browse_show_all_attachments, pattern="^ua_browse_all_(br|mp)$"),
    CallbackQueryHandler(browse_show_category_menu, pattern="^ua_browse_select_cat_(br|mp)$"),
    CallbackQueryHandler(browse_category_selected, pattern="^ua_browse_cat_(?!.*select)"),
    CallbackQueryHandler(browse_prev_page, pattern="^ua_browse_prev$"),
    CallbackQueryHandler(browse_next_page, pattern="^ua_browse_next$"),
    CallbackQueryHandler(view_attachment_detail, pattern="^ua_view_\\d+$"),
    CallbackQueryHandler(like_attachment, pattern="^ua_like_\\d+$"),
    CallbackQueryHandler(report_attachment, pattern="^ua_report_\\d+$"),
    CallbackQueryHandler(browse_back_to_list, pattern="^ua_browse_back$"),
]
