from core.context import CustomContext
"""
My Attachments Handler - مدیریت اتچمنت‌های شخصی کاربر
"""

from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from config.config import GAME_MODES, WEAPON_CATEGORIES
from core.database.database_adapter import get_database_adapter
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t
from utils.validation import safe_int

logger = get_logger('my_attachments', 'user.log')
db = get_database_adapter()

# تعداد اتچمنت در هر صفحه
MY_ATTACHMENTS_PER_PAGE = 5


async def my_attachments_menu(update: Update, context: CustomContext):
    """منوی اتچمنت‌های من"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    
    user_id = update.effective_user.id
    
    # دریافت آمار کاربر
    stats = await db.get_user_submission_stats(user_id)
    
    # دریافت تمام اتچمنت‌های کاربر
    try:
        async with db.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT ua.*
                    FROM user_attachments ua
                    WHERE ua.user_id = %s
                    ORDER BY ua.submitted_at DESC
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()
        all_attachments = [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching user attachments: {e}")
        all_attachments = []
    
    # دسته‌بندی بر اساس وضعیت
    pending = [a for a in all_attachments if a['status'] == 'pending']
    approved = [a for a in all_attachments if a['status'] == 'approved']
    rejected = [a for a in all_attachments if a['status'] == 'rejected']
    
    # پیام آمار
    divider = "━━━━━━━━━━━━━━"
    total = stats.get('total_submissions', 0)
    approved_n = stats.get('approved_count', 0)
    rejected_n = stats.get('rejected_count', 0)
    pending_n = len(pending)

    message = (
        f"{t('ua.my.title', lang)}\n"
        f"{divider}\n"
        f"{t('ua.my.stats_header', lang)}\n"
        f"{t('ua.my.stats.total', lang, n=total)}\n"
        f"{t('ua.my.stats.approved', lang, n=approved_n)}\n"
        f"{t('ua.my.stats.rejected', lang, n=rejected_n)}\n"
        f"{t('ua.my.stats.pending', lang, n=pending_n)}\n"
        f"{divider}\n"
    )

    if stats.get('is_banned'):
        message += t('ua.my.status.banned', lang) + "\n"
    elif stats.get('strike_count', 0) > 0:
        message += t('ua.my.status.strikes', lang, strike=f"{stats['strike_count']:.1f}") + "\n"
    
    # کیبورد
    keyboard = []
    
    if pending:
        keyboard.append([InlineKeyboardButton(t("ua.my.filter.pending", lang, n=len(pending)), callback_data="ua_my_pending")])
    
    if approved:
        keyboard.append([InlineKeyboardButton(t("ua.my.filter.approved", lang, n=len(approved)), callback_data="ua_my_approved")])
    
    if rejected:
        keyboard.append([InlineKeyboardButton(t("ua.my.filter.rejected", lang, n=len(rejected)), callback_data="ua_my_rejected")])
    
    if not all_attachments:
        message += ("\n" + t('attachment.none', lang))
        keyboard.append([InlineKeyboardButton(t("ua.submit", lang), callback_data="ua_submit")])
    
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
    
    # تنظیم صفحه اولیه برای فیلترها
    context.user_data['my_att_page'] = 0
    
    try:
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        # اگر پیام photo بود، نمیشه edit کرد
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete previous my_attachments menu message: {e}")
        await update.effective_chat.send_message(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_my_attachments_by_status(update: Update, context: CustomContext):
    """نمایش اتچمنت‌های کاربر بر اساس وضعیت با صفحه‌بندی"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    
    status_map = {
        'ua_my_pending': 'pending',
        'ua_my_approved': 'approved',
        'ua_my_rejected': 'rejected'
    }
    
    # دریافت وضعیت از callback یا user_data
    if query.data in status_map:
        status = status_map[query.data]
        context.user_data['my_att_status'] = status
        context.user_data['my_att_page'] = 0
    else:
        status = context.user_data.get('my_att_status', 'pending')
    
    page = context.user_data.get('my_att_page', 0)
    user_id = update.effective_user.id
    
    # دریافت تعداد کل برای صفحه‌بندی
    total_count = await db.get_user_attachments_count(user_id, status)
    total_pages = (total_count - 1) // MY_ATTACHMENTS_PER_PAGE + 1
    
    # دریافت اتچمنت‌های این صفحه
    attachments = await db.get_user_attachments_paginated(
        user_id, 
        status, 
        limit=MY_ATTACHMENTS_PER_PAGE, 
        offset=page * MY_ATTACHMENTS_PER_PAGE
    )
    
    # عنوان بر اساس وضعیت
    status_titles = {
        'pending': t('ua.my.status_title.pending', lang),
        'approved': t('ua.my.status_title.approved', lang),
        'rejected': t('ua.my.status_title.rejected', lang)
    }
    
    message = f"📁 {status_titles[status]}\n\n"
    if not attachments:
        message += t('attachment.none', lang)
        keyboard = [[InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_my")]]
    else:
        start_idx = page * MY_ATTACHMENTS_PER_PAGE + 1
        end_idx = min(start_idx + len(attachments) - 1, total_count)
        
        message += t('pagination.showing_range', lang, start=start_idx, end=end_idx, total=total_count) + "\n"
        message += t('pagination.page_of', lang, page=page+1, total=total_pages) + "\n\n"
        
        keyboard = []
        for att in attachments:
            mode_icon = "🎮" if att['mode'] == 'mp' else "🪂"
            weapon = att.get('weapon_display') or att.get('weapon_name') or t('common.unknown', lang)
            btn_text = f"{mode_icon} {att['attachment_name'][:25]} - {weapon}"
            callback_data = f"ua_my_detail_{att['id']}"
            
            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=callback_data)
            ])
        
        # دکمه‌های ناوبری صفحه‌بندی
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(t('nav.prev', lang), callback_data="ua_my_prev"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(t('nav.next', lang), callback_data="ua_my_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
            
        keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_my")])
    
    try:
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        # اگر پیام photo بود، نمیشه edit کرد
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete previous my_attachments status message: {e}")
        await update.effective_chat.send_message(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_my_attachment_detail(update: Update, context: CustomContext):
    """نمایش جزئیات اتچمنت شخصی"""
    query = update.callback_query
    await query.answer()
    
    attachment_id = safe_int(query.data.replace('ua_my_detail_', ''))
    
    # دریافت اتچمنت
    attachment = await db.get_user_attachment(attachment_id)
    
    if not attachment:
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('attachment.not_found', lang), show_alert=True)
        return
    
    if attachment['user_id'] != update.effective_user.id:
        lang = await get_user_lang(update, context, db) or 'fa'
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # ساخت پیام
    from telegram.helpers import escape_markdown
    
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{attachment['mode']}_short", lang)
    status_icons = {
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌'
    }
    
    status_icon = status_icons.get(attachment['status'], '❓')
    description = attachment.get('description') or t('common.no_description', lang)
    
    # دریافت نام دسته از کلید
    category_key = attachment.get('category', attachment.get('category_name', ''))
    category_persian = t(f"category.{category_key}", 'en')
    
    # Escape for MarkdownV2
    att_name = escape_markdown(str(attachment['attachment_name']), version=2)
    status_text = escape_markdown(str(attachment['status'].upper()), version=2)
    mode_name_esc = escape_markdown(str(mode_name), version=2)
    weapon_raw = attachment.get('custom_weapon_name', attachment.get('weapon_name', t('common.unknown', lang)))
    weapon_name = escape_markdown(str(weapon_raw), version=2)
    category_name_esc = escape_markdown(str(category_persian), version=2)
    description_esc = escape_markdown(str(description), version=2)
    # Format submitted_at safely
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
        f"📎 *{att_name}*\n\n"
        f"{status_icon} *وضعیت:* {status_text}\n"
        f"🎮 {t('mode.label', lang)}: {mode_name_esc}\n"
        f"🔫 {t('weapon.label', lang)}: {weapon_name}\n"
        f"📂 {t('category.label', lang)}: {category_name_esc}\n\n"
        f"💬 توضیحات:\n{description_esc}\n\n"
        f"📅 تاریخ ارسال: {date_str}\n"
    )
    
    # اطلاعات اضافی بر اساس وضعیت
    if attachment['status'] == 'approved':
        # Format approved_at safely
        appr_at = attachment.get('approved_at')
        if isinstance(appr_at, datetime):
            appr_ts = appr_at.date().isoformat()
        elif isinstance(appr_at, date):
            appr_ts = appr_at.isoformat()
        elif isinstance(appr_at, str):
            appr_ts = appr_at[:10]
        else:
            appr_ts = t('common.unknown', lang)
        approved_date = escape_markdown(appr_ts, version=2)
        caption += (
            f"✅ {escape_markdown(t('ua.approved_at', lang), version=2)}: {approved_date}\n"
            f"👁 {escape_markdown(t('ua.views', lang), version=2)}: {attachment.get('view_count', 0)}\n"
            f"👍 {escape_markdown(t('ua.likes', lang), version=2)}: {attachment.get('like_count', 0)}\n"
        )
    elif attachment['status'] == 'rejected':
        reason = escape_markdown(str(attachment.get('rejection_reason', t('common.no_description', lang))), version=2)
        caption += f"\n❌ {escape_markdown(t('ua.rejected.reason', lang), version=2)}\n{reason}\n"
    elif attachment['status'] == 'pending':
        caption += "\n" + escape_markdown(t('ua.pending.review', lang), version=2)
    
    # کیبورد
    keyboard = []
    
    # دکمه حذف برای همه وضعیت‌ها فعال است
    keyboard.append([InlineKeyboardButton(t("menu.buttons.delete", lang), callback_data=f"ua_my_ask_del_{attachment_id}")])
    
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data=f"ua_my_{attachment['status']}")])
    
    # ارسال تصویر
    try:
        await update.effective_chat.send_photo(
            photo=attachment['image_file_id'],
            caption=caption,
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error sending photo for attachment {attachment_id}: {e}")
        await query.answer(t('ua.error.view_image', lang), show_alert=True)
        return
    
    # حذف پیام قبلی
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete previous my_attachments detail message: {e}")


async def ask_delete_confirmation(update: Update, context: CustomContext):
    """پرسش برای تایید حذف"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    
    attachment_id = safe_int(query.data.replace('ua_my_ask_del_', ''))
    
    keyboard = [
        [
            InlineKeyboardButton(t("common.yes", lang) + " 🗑️", callback_data=f"ua_my_confirm_del_{attachment_id}"),
            InlineKeyboardButton(t("common.no", lang), callback_data=f"ua_my_detail_{attachment_id}")
        ]
    ]
    
    try:
        # اگر پیام عکس است، کپشن را ادیت می‌کنیم
        await query.edit_message_caption(
            caption=t("ua.my.delete_confirm", lang),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        # اگر خطا داد (مثلاً اگر عکس نیست)، متن را ادیت می‌کنیم
        try:
            await query.edit_message_text(
                t("ua.my.delete_confirm", lang),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
             # Fallback: ارسال پیام جدید
            await query.message.reply_text(
                t("ua.my.delete_confirm", lang),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


async def perform_delete_my_attachment(update: Update, context: CustomContext):
    """اجرای حذف اتچمنت شخصی"""
    query = update.callback_query
    
    attachment_id = safe_int(query.data.replace('ua_my_confirm_del_', ''))
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # بررسی مالکیت
    attachment = await db.get_user_attachment(attachment_id)
    
    if not attachment or attachment['user_id'] != user_id:
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # حذف با متد جدید دیتابیس
    try:
        if await db.delete_user_attachment(attachment_id, deleted_by=user_id):
            await query.answer(t('ua.success.deleted', lang), show_alert=True)
            
            # حذف پیام و بازگشت
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete message after delete: {e}")
            
            # نمایش لیست pending (یا وضعیت قبلی اگر ذخیره شده باشد، اما پیش‌فرض pending خوب است)
            # بهتر است به منوی اصلی برگردیم چون شاید لیست خالی شده باشد
            await my_attachments_menu(update, context)
            
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)


async def my_attachments_prev_page(update: Update, context: CustomContext):
    """صفحه قبل اتچمنت‌های من"""
    context.user_data['my_att_page'] = max(0, context.user_data.get('my_att_page', 0) - 1)
    await show_my_attachments_by_status(update, context)


async def my_attachments_next_page(update: Update, context: CustomContext):
    """صفحه بعد اتچمنت‌های من"""
    context.user_data['my_att_page'] = context.user_data.get('my_att_page', 0) + 1
    await show_my_attachments_by_status(update, context)


# Export handlers
my_attachments_handlers = [
    CallbackQueryHandler(show_my_attachment_detail, pattern="^ua_my_detail_\\d+$"),
    CallbackQueryHandler(ask_delete_confirmation, pattern="^ua_my_ask_del_\\d+$"),
    CallbackQueryHandler(perform_delete_my_attachment, pattern="^ua_my_confirm_del_\\d+$"),
    CallbackQueryHandler(my_attachments_prev_page, pattern="^ua_my_prev$"),
    CallbackQueryHandler(my_attachments_next_page, pattern="^ua_my_next$"),
    CallbackQueryHandler(show_my_attachments_by_status, pattern="^ua_my_(pending|approved|rejected)$"),
    CallbackQueryHandler(my_attachments_menu, pattern="^ua_my$"),
]
