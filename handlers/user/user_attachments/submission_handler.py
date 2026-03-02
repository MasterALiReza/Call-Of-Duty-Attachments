from core.context import CustomContext
"""
User Attachment Submission Handler
فرآیند ارسال اتچمنت توسط کاربران
"""

import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from config.config import WEAPON_CATEGORIES, GAME_MODES, build_category_keyboard, build_weapon_keyboard
from core.database.database_adapter import get_database_adapter
from utils.content_validator import get_validator
from utils.logger import get_logger
from utils.language import get_user_lang
from utils.i18n import t
from core.security.rate_limiter import SimpleRateLimiter
from utils.telegram_safety import safe_edit_message_text
from core.events import event_bus, EventTypes

logger = get_logger('user_attachments', 'user.log')

# Conversation states
(UA_MODE, UA_CATEGORY, UA_WEAPON_SELECT, UA_ATTACHMENT_NAME,
 UA_IMAGE, UA_CODE, UA_DESCRIPTION, UA_CONFIRM) = range(8)

# Rate Limiter (5 تلاش در 10 دقیقه)
submission_rate_limiter = SimpleRateLimiter(max_requests=5, window=600)

db = get_database_adapter()
validator = get_validator(db)

def _clear_submission_data(context: CustomContext):
    """پاک کردن فقط داده‌های مربوط به پروسه ثبت اتچمنت بدون دست زدن به تنظیمات کاربر"""
    submission_keys = [
        'mode', 'category', 'weapon_id', 'weapon_name', 'attachment_name',
        'image_file_id', 'code', 'description', 'submission_user_id'
    ]
    for key in submission_keys:
        if key in context.user_data:
            del context.user_data[key]

async def show_user_attachments_menu(update: Update, context: CustomContext):
    """نمایش منوی اصلی اتچمنت کاربران"""
    # پشتیبانی از هم callback و هم message
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message
        query = None
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # بررسی فعال بودن سیستم
    system_enabled = await db.get_ua_setting('system_enabled') or '1'
    if system_enabled not in ('1', 'true', 'True'):
        text = t("error.generic", lang)
        if query:
            await safe_edit_message_text(
                query,
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="main_menu")
                ]])
            )
        else:
            await message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="main_menu")
                ]])
            )
        return
    
    # Track user
    await db.upsert_user(
        user_id=user_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name
    )
    
    keyboard = [
        [
            InlineKeyboardButton(t("ua.submit", lang), callback_data="ua_submit"),
            InlineKeyboardButton(t("ua.browse", lang), callback_data="ua_browse")
        ],
        [
            InlineKeyboardButton(t("ua.my_attachments", lang), callback_data="ua_my"),
            InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="main_menu")
        ]
    ]
    
    text = (
        f"{t('ua.title', lang)}\n"
        "━━━━━━━━━━━━━━\n"
        f"{t('ua.description', lang)}"
    )
    
    if query:
        # چک کردن آیا پیام photo هست
        try:
            await safe_edit_message_text(
                query,
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            # اگه پیام photo بود، پاک کن و جدید بفرست
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete previous user attachments menu message: {e}")
            await update.effective_chat.send_message(
                text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def start_submission(update: Update, context: CustomContext):
    """شروع فرآیند ارسال اتچمنت"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # Check if user is an admin
    user_role = await db.get_user_role(user_id)
    is_admin = user_role in ['owner', 'admin']
    
    # بررسی Rate Limit
    if not submission_rate_limiter.is_allowed(user_id, is_admin=is_admin):
        await safe_edit_message_text(
            query,
            t("ua.rate_limit", lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[ 
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")
            ]])
        )
        return ConversationHandler.END
    
    # بررسی وضعیت Ban
    stats = await db.get_user_submission_stats(user_id)
    if stats and stats['is_banned']:
        await safe_edit_message_text(
            query,
            t("ua.banned", lang, reason=stats['banned_reason'], date=(stats['banned_at'][:10] if stats['banned_at'] else '—')),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[ 
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")
            ]])
        )
        return ConversationHandler.END
    
    # بررسی محدودیت روزانه
    daily_limit = int(await db.get_ua_setting('daily_limit') or 5)
    if stats and stats['daily_submissions'] >= daily_limit:
        await safe_edit_message_text(
            query,
            t("ua.daily_limit", lang, limit=daily_limit),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[ 
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")
            ]])
        )
        return ConversationHandler.END
    
    # چک کردن آیا از Browse آمده (مود و دسته از قبل انتخاب شده)
    browse_mode = context.user_data.get('browse_mode')
    browse_category = context.user_data.get('browse_category')
    # اگر از "نمایش همه اتچمنت‌ها" آمده باشد، دسته 'all' به معنای عدم انتخاب دسته است
    if browse_category == 'all':
        browse_category = None
    
    # پاک کردن داده‌های قبلی به‌صورت ایمن
    _clear_submission_data(context)
    context.user_data['submission_user_id'] = user_id
    
    # اطمینان از وجود کاربر در دیتابیس
    await db.upsert_user(
        user_id=user_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name
    )
    
    # اگر از Browse آمده با مود و دسته، مستقیم برو به انتخاب سلاح
    if browse_mode and browse_category:
        context.user_data['mode'] = browse_mode
        context.user_data['category'] = browse_category
        
        lang = await get_user_lang(update, context, db) or 'fa'
        mode_name = t(f"mode.{browse_mode}_btn", lang)
        category_name = t(f"category.{browse_category}", 'en')
        
        # دریافت لیست سلاح‌های این دسته
        weapons = await db.get_weapons_in_category(browse_category)
        
        if not weapons:
            await safe_edit_message_text(
                query,
                f"{mode_name} > {category_name}\n\n" + t("ua.no_weapons", lang),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")],
                    [InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")]
                ])
            )
            return ConversationHandler.END
        
        # نمایش لیست سلاح‌ها
        keyboard = build_weapon_keyboard(weapons, "ua_weapon_", browse_category, add_emoji=True)
        keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
        keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")])
        
        await safe_edit_message_text(
            query,
            f"{mode_name} > {category_name}\n\n" + t("weapon.choose", lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return UA_WEAPON_SELECT
    
    # اگر فقط مود از Browse آمده، برو به انتخاب دسته
    elif browse_mode:
        context.user_data['mode'] = browse_mode
        
        lang = await get_user_lang(update, context, db) or 'fa'
        mode_name = t(f"mode.{browse_mode}_btn", lang)
        
        # نمایش دسته‌بندی‌ها
        keyboard = await build_category_keyboard(
            callback_prefix="ua_cat_",
            show_count=False,
            db=None,
            lang=lang,
            active_ids=list(WEAPON_CATEGORIES.keys())
        )
        keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
        keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")])
        
        await safe_edit_message_text(
            query,
            f"{mode_name}\n" + t("category.choose", 'en'),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return UA_CATEGORY
    
    # نمایش انتخاب مود
    # دریافت مودهای فعال
    enabled_modes_str = await db.get_ua_setting('enabled_modes') or '["mp","br"]'
    enabled_modes = json.loads(enabled_modes_str)
    
    keyboard = []
    # ترتیب: BR بالا، MP پایین (عمودی)
    lang = await get_user_lang(update, context, db) or 'fa'
    if 'br' in enabled_modes:
        keyboard.append([InlineKeyboardButton(t("mode.br_btn", lang), callback_data="ua_mode_br")])
    if 'mp' in enabled_modes:
        keyboard.append([InlineKeyboardButton(t("mode.mp_btn", lang), callback_data="ua_mode_mp")])
    
    if not keyboard:
        await safe_edit_message_text(
            query,
            t("ua.error.no_active_modes", lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")]
            ])
        )
        return ConversationHandler.END
    
    
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
    keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")])
    
    await safe_edit_message_text(
        query,
        t("mode.choose", lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return UA_MODE


async def mode_selected(update: Update, context: CustomContext):
    """انتخاب مود بازی"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace('ua_mode_', '')
    context.user_data['mode'] = mode
    
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
        await safe_edit_message_text(
            query,
            t('category.none', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")]
            ])
        )
        return ConversationHandler.END
    
    # نمایش دسته‌بندی‌ها
    keyboard = await build_category_keyboard(
        callback_prefix="ua_cat_",
        show_count=False,
        db=None,
        lang=lang,
        active_ids=list(active_categories.keys())
    )
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_menu")])
    keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")])
    
    await safe_edit_message_text(
        query,
        f"{mode_name}\n" + t("category.choose", 'en'),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return UA_CATEGORY


async def category_selected(update: Update, context: CustomContext):
    """انتخاب دسته"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace('ua_cat_', '')
    context.user_data['category'] = category
    
    lang = await get_user_lang(update, context, db) or 'fa'
    category_name = t(f"category.{category}", 'en')
    mode_name = t(f"mode.{context.user_data['mode']}_btn", lang)
    
    # دریافت لیست سلاح‌های موجود در این دسته
    weapons = await db.get_weapons_in_category(category)
    
    if not weapons:
        await safe_edit_message_text(
            query,
            f"{mode_name} > {category_name}\n\n" + t("ua.no_weapons", lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_back_to_mode")],
                [InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")]
            ])
        )
        return UA_CATEGORY
    
    # نمایش لیست سلاح‌ها
    keyboard = build_weapon_keyboard(weapons, "ua_weapon_", category, add_emoji=True)
    keyboard.append([InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_back_to_mode")])
    keyboard.append([InlineKeyboardButton(t("menu.buttons.cancel", lang), callback_data="ua_cancel")])
    
    await safe_edit_message_text(
        query,
        f"{mode_name} > {category_name}\n\n" + t("weapon.choose", lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return UA_WEAPON_SELECT


async def weapon_selected(update: Update, context: CustomContext):
    """انتخاب سلاح از لیست"""
    query = update.callback_query
    await query.answer()
    
    # callback_data format: ua_weapon_AK-47
    weapon_name = query.data.replace('ua_weapon_', '')
    category = context.user_data.get('category')
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # دریافت weapon_id از دیتابیس
    weapon = await db.get_weapon_by_name(category, weapon_name)
    if not weapon:
        await safe_edit_message_text(
            query,
            t('attachment.not_found', lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("menu.buttons.back", lang), callback_data="ua_back_to_category")
            ]])
        )
        return UA_WEAPON_SELECT
    
    context.user_data['weapon_id'] = weapon['id']
    context.user_data['weapon_name'] = weapon_name
    
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{context.user_data['mode']}_btn", lang)
    category_name = t(f"category.{context.user_data['category']}", 'en')
    
    # درخواست نام اتچمنت
    await safe_edit_message_text(
        query,
        f"{mode_name} > {category_name} > {weapon['name']}\n" + t('ua.prompt.attachment_name', lang),
        parse_mode='Markdown'
    )
    
    return UA_ATTACHMENT_NAME


async def name_entered(update: Update, context: CustomContext):
    """دریافت نام اتچمنت"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # Validation
    max_length = int(await db.get_ua_setting('max_name_length') or 100)
    valid, reason, violation = validator.validate_text(text, max_length, check_spam=True)
    
    if not valid:
        if violation:
            # تخلف - مدیریت Strike
            severity = violation['severity']
            
            # به‌روزرسانی آمار
            if severity == 3:
                strike_add = 2.0
            elif severity == 2:
                strike_add = 1.0
            else:
                strike_add = 0.5
            
            db.update_submission_stats(
                user_id=user_id,
                add_violation=1,
                add_strike=strike_add
            )
            
            # بررسی Strike Count
            stats = await db.get_user_submission_stats(user_id)
            if stats['strike_count'] >= 3.0:
                # Ban دائم
                await db.ban_user_from_submissions(
                    user_id=user_id,
                    reason=f"استفاده {stats['violation_count']} بار از کلمات نامناسب"
                )
                await update.message.reply_text(
                    t('ua.banned_simple', lang),
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            elif stats['strike_count'] >= 2.0:
                # اخطار جدی
                await update.message.reply_text(
                    t('ua.violation.name_serious', lang, strike=f"{stats['strike_count']:.1f}", reason=reason),
                    parse_mode='Markdown'
                )
                return UA_ATTACHMENT_NAME
            
            else:
                # اخطار معمولی
                await update.message.reply_text(
                    t('ua.violation.name_warning', lang, strike=f"{stats['strike_count']:.1f}", reason=reason),
                    parse_mode='Markdown'
                )
                return UA_ATTACHMENT_NAME
        
        # خطای معمولی (طول یا spam)
        await update.message.reply_text(
            t('ua.violation.name_try_again', lang, reason=reason),
            parse_mode='Markdown'
        )
        return UA_ATTACHMENT_NAME
    
    # نام معتبر است
    context.user_data['attachment_name'] = text
    
    # درخواست عکس اتچمنت
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{context.user_data['mode']}_btn", lang)
    category_name = t(f"category.{context.user_data['category']}", 'en')
    weapon_name = context.user_data['weapon_name']
    
    await update.message.reply_text(
        f"{mode_name} > {category_name} > {weapon_name}\n" + t('ua.prompt.image', lang),
        parse_mode='Markdown'
    )
    
    return UA_IMAGE


async def image_uploaded(update: Update, context: CustomContext):
    """دریافت تصویر"""
    lang = await get_user_lang(update, context, db) or 'fa'
    
    if not update.message.photo:
        await update.message.reply_text(
            t('ua.error.image_required', lang)
        )
        return UA_IMAGE
    
    # دریافت بزرگترین سایز تصویر
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # بررسی حجم
    max_size = int(await db.get_ua_setting('max_image_size') or 5242880)  # default 5 MB
    if getattr(photo, 'file_size', 0) > max_size:
        max_mb = max_size // (1024 * 1024)
        await update.message.reply_text(t('validation.image.too_large', lang, max_mb=max_mb))
        return UA_IMAGE
    
    context.user_data['image_file_id'] = file_id
    
    # درخواست کد اتچمنت
    max_code_length = int(await db.get_ua_setting('max_description_length') or 500)
    
    await update.message.reply_text(
        t('ua.prompt.code', lang, max=max_code_length),
        parse_mode='Markdown'
    )
    
    return UA_CODE


async def code_entered(update: Update, context: CustomContext):
    """دریافت کد اتچمنت"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # اگر skip بود
    if text == '/skip':
        context.user_data['code'] = None
    else:
        # Validation ساده برای کد
        max_length = 100
        if len(text) > max_length:
            await update.message.reply_text(
                t('ua.error.code_too_long', lang, max=max_length) + "\n\n" + t('ua.try_again_or_skip', lang)
            )
            return UA_CODE
        
        context.user_data['code'] = text
    
    # درخواست توضیحات
    max_desc_length = int(await db.get_ua_setting('max_description_length') or 200)
    
    await update.message.reply_text(
        t('ua.prompt.description', lang, max=max_desc_length),
        parse_mode='Markdown'
    )
    
    return UA_DESCRIPTION


async def description_entered(update: Update, context: CustomContext):
    """دریافت توضیحات"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    
    # اگر skip بود
    if text == '/skip':
        context.user_data['description'] = None
    else:
        # Validation
        max_length = int(await db.get_ua_setting('max_description_length') or 200)
        valid, reason, violation = validator.validate_text(text, max_length, check_spam=True)
        
        if not valid:
            if violation:
                # مشابه name - مدیریت Strike
                severity = violation['severity']
                strike_add = 2.0 if severity == 3 else (1.0 if severity == 2 else 0.5)
                
                await db.update_submission_stats(
                    user_id=user_id,
                    add_violation=1,
                    add_strike=strike_add
                )
                
                stats = await db.get_user_submission_stats(user_id)
                if stats['strike_count'] >= 3.0:
                    await db.ban_user_from_submissions(user_id, "تخلفات مکرر")
                    await update.message.reply_text(
                        t('ua.banned_simple', lang),
                        parse_mode='Markdown'
                    )
                    return ConversationHandler.END
                
                await update.message.reply_text(
                    t('ua.violation.description_try_again', lang, reason=reason),
                    parse_mode='Markdown'
                )
                return UA_DESCRIPTION
            
            await update.message.reply_text(
                f"{reason}\n" + t('ua.try_again_or_skip', lang),
                parse_mode='Markdown'
            )
            return UA_DESCRIPTION
        
        context.user_data['description'] = text
    
    # نمایش تایید نهایی
    await show_confirmation(update, context)
    return UA_CONFIRM


async def show_confirmation(update: Update, context: CustomContext):
    """نمایش صفحه تایید نهایی"""
    data = context.user_data
    
    lang = await get_user_lang(update, context, db) or 'fa'
    mode_name = t(f"mode.{data['mode']}_btn", lang)
    category_name = t(f"category.{data['category']}", 'en')
    weapon_name = data.get('weapon_name') or t('common.unknown', lang)
    attachment_name = data['attachment_name']
    code = data.get('code') or t('common.none', lang)
    description = data.get('description') or t('common.no_description', lang)
    
    # Escape متن‌های وارد شده توسط کاربر برای جلوگیری از خطای Markdown
    def _esc(text: str) -> str:
        for ch in ['_', '*', '`', '[']:
            text = text.replace(ch, f'\\{ch}')
        return text
    
    message = (
        f"{t('ua.confirm.title', lang)}\n\n"
        f"{t('ua.confirm.details_header', lang)}\n\n"
        f"🎮 {t('mode.label', lang)}: {mode_name}\n"
        f"📂 {t('category.label', lang)}: {category_name}\n"
        f"🔫 {t('weapon.label', lang)}: {_esc(weapon_name)}\n"
        f"📝 {t('attachment.name', lang)}: {_esc(attachment_name)}\n"
        f"🖼 {t('image.label', lang)}: ✓\n"
        f"📝 {t('attachment.code', lang)}: {_esc(code)}\n"
        f"💬 {t('description.label', lang)}: {_esc(description)}\n\n"
        f"{t('ua.pending_after_submit', lang)}"
    )
    
    keyboard = [
        [InlineKeyboardButton(t('ua.cta.confirm_and_send', lang), callback_data="ua_final_confirm")],
        [InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data="ua_cancel")]
    ]
    
    # ارسال تصویر با caption
    try:
        await update.message.reply_photo(
            photo=data['image_file_id'],
            caption=message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        # fallback: بدون parse_mode برای جلوگیری از crash
        plain_message = (
            f"{t('ua.confirm.title', lang)}\n\n"
            f"{t('ua.confirm.details_header', lang)}\n\n"
            f"Mode: {mode_name}\n"
            f"Category: {category_name}\n"
            f"Weapon: {weapon_name}\n"
            f"Name: {attachment_name}\n"
            f"Code: {code}\n"
            f"Description: {description}\n\n"
            f"{t('ua.pending_after_submit', lang)}"
        )
        await update.message.reply_photo(
            photo=data['image_file_id'],
            caption=plain_message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def final_confirm(update: Update, context: CustomContext):
    """تایید نهایی و ثبت"""
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    user_id = data['submission_user_id']
    lang = await get_user_lang(update, context, db) or 'fa'
    
    try:
        # ترکیب کد و توضیحات برای ذخیره در description
        code = data.get('code', '')
        desc = data.get('description', '')
        
        if code and desc:
            combined_desc = f"{t('attachment.code', lang)}: {code}\n\n{desc}"
        elif code:
            combined_desc = f"{t('attachment.code', lang)}: {code}"
        elif desc:
            combined_desc = desc
        else:
            combined_desc = None
        
        # ثبت در دیتابیس
        attachment_id = await db.add_user_attachment(
            user_id=user_id,
            weapon_id=data.get('weapon_id'),
            mode=data['mode'],
            category=data['category'],
            custom_weapon_name=data.get('weapon_name'),  # نام سلاح انتخابی
            attachment_name=data['attachment_name'],
            image_file_id=data['image_file_id'],
            description=combined_desc
        )
        
        if attachment_id:
            # به‌روزرسانی آمار
            await db.update_submission_stats(
                user_id=user_id,
                increment_total=True,
                increment_daily=True
            )
            
            # حذف پیام عکس قبلی
            try:
                await query.message.delete()
            except Exception:
                pass

            # پیام موفقیت جدید
            await context.bot.send_message(
                chat_id=user_id,
                text=t('ua.submit_success', lang),
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[ 
                    InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")
                ]])
            )
            
            # Emit Event for notification/analytics
            await event_bus.emit(
                EventTypes.ATTACHMENT_SUBMITTED,
                context=context,
                user_id=user_id,
                attachment_id=attachment_id,
                weapon=data.get('weapon_name'),
                mode=data['mode'],
                category=data['category']
            )
            
            logger.info(f"User attachment submitted: ID={attachment_id}, user={user_id}")
        else:
            raise Exception("Failed to save attachment")
    
    except Exception as e:
        logger.error(f"Error saving user attachment: {e}")
        
        # حذف پیام عکس در صورت خطا
        try:
            await query.message.delete()
        except Exception:
            pass
            
        await context.bot.send_message(
            chat_id=user_id,
            text=t('ua.save_error', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")
            ]])
        )
    
    # پاک کردن داده‌های موقت به‌صورت ایمن
    _clear_submission_data(context)
    return ConversationHandler.END


async def back_to_mode(update: Update, context: CustomContext):
    """بازگشت به انتخاب مود"""
    query = update.callback_query
    await query.answer()
    
    # بازنشانی داده‌های سابمیشن و نگه داشتن شناسایی کاربر
    user_id = context.user_data.get('submission_user_id')
    _clear_submission_data(context)
    context.user_data['submission_user_id'] = user_id
    
    # نمایش انتخاب مود
    # دریافت مودهای فعال
    enabled_modes_str = await db.get_ua_setting('enabled_modes') or '["mp","br"]'
    enabled_modes = json.loads(enabled_modes_str)
    
    keyboard = []
    mode_buttons = []
    
    # ترتیب: BR راست، MP چپ
    lang = await get_user_lang(update, context, db) or 'fa'
    if 'br' in enabled_modes:
        mode_buttons.append(InlineKeyboardButton(t('mode.br_btn', lang), callback_data="ua_mode_br"))
    if 'mp' in enabled_modes:
        mode_buttons.append(InlineKeyboardButton(t('mode.mp_btn', lang), callback_data="ua_mode_mp"))
    
    if mode_buttons:
        if len(mode_buttons) == 2:
            keyboard.append(mode_buttons)
        else:
            for btn in mode_buttons:
                keyboard.append([btn])
    
    if not mode_buttons:
        await safe_edit_message_text(
            query,
            t('ua.error.no_active_modes', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")]
            ])
        )
        return ConversationHandler.END
    
    keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")])
    keyboard.append([InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data="ua_cancel")])
    
    await safe_edit_message_text(
        query,
        t('mode.choose', lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return UA_MODE


async def back_to_category(update: Update, context: CustomContext):
    """بازگشت به انتخاب دسته"""
    query = update.callback_query
    await query.answer()
    
    mode = context.user_data.get('mode')
    if not mode:
        return await back_to_mode(update, context)
    
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
        await safe_edit_message_text(
            query,
            t('category.none', lang),
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")]
            ])
        )
        return ConversationHandler.END
    
    # نمایش دسته‌بندی‌ها
    keyboard = await build_category_keyboard(
        callback_prefix="ua_cat_",
        show_count=False,
        db=None,
        lang=lang,
        active_ids=list(WEAPON_CATEGORIES.keys())
    )
    keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_back_to_mode")])
    keyboard.append([InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data="ua_cancel")])
    
    await safe_edit_message_text(
        query,
        f"{mode_name}\n" + t('category.choose', lang),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return UA_CATEGORY


async def cancel_submission(update: Update, context: CustomContext):
    """لغو فرآیند"""
    query = update.callback_query
    lang = await get_user_lang(update, context, db) or 'fa'
    await query.answer(t('ua.cancelled', lang))
    
    _clear_submission_data(context)
    
    await safe_edit_message_text(
        query,
        t('ua.cancelled', lang),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_menu")
        ]])
    )
    
    return ConversationHandler.END


# ConversationHandler
user_attachment_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_submission, pattern="^ua_submit$")
    ],
    states={
        UA_MODE: [
            CallbackQueryHandler(mode_selected, pattern="^ua_mode_(br|mp)$")
        ],
        UA_CATEGORY: [
            CallbackQueryHandler(category_selected, pattern="^ua_cat_")
        ],
        UA_WEAPON_SELECT: [
            CallbackQueryHandler(weapon_selected, pattern="^ua_weapon_")
        ],
        UA_ATTACHMENT_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, name_entered)
        ],
        UA_IMAGE: [
            MessageHandler(filters.PHOTO, image_uploaded)
        ],
        UA_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, code_entered)
        ],
        UA_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, description_entered)
        ],
        UA_CONFIRM: [
            CallbackQueryHandler(final_confirm, pattern="^ua_final_confirm$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(show_user_attachments_menu, pattern="^ua_menu$"),
        CallbackQueryHandler(back_to_mode, pattern="^ua_back_to_mode$"),
        CallbackQueryHandler(back_to_category, pattern="^ua_back_to_category$"),
        CallbackQueryHandler(cancel_submission, pattern="^ua_cancel$"),
        MessageHandler(filters.Regex("^/cancel$"), cancel_submission)
    ],
    name="user_attachment_submission",
    persistent=False,
    per_message=True,
    allow_reentry=True
)
