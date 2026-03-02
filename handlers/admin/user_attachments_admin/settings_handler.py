from core.context import CustomContext
"""
Settings Handler - تنظیمات سیستم اتچمنت کاربران
"""

import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from core.database.database_adapter import get_database_adapter
from core.security.role_manager import RoleManager, Permission
from utils.logger import get_logger
from utils.i18n import t
from utils.language import get_user_lang

logger = get_logger('ua_settings', 'admin.log')
db = get_database_adapter()

# RBAC helper
role_manager = RoleManager(db)

async def has_ua_perm(user_id: int) -> bool:
    """Check if user can manage user attachments (UA)."""
    try:
        if await role_manager.is_super_admin(user_id):
            return True
        return await role_manager.has_permission(user_id, Permission.MANAGE_USER_ATTACHMENTS)
    except Exception:
        return await db.is_admin(user_id)

# States برای مدیریت blacklist
ADD_BLACKLIST_WORD, REMOVE_BLACKLIST_WORD = range(2)


async def show_ua_settings(update: Update, context: CustomContext):
    """نمایش تنظیمات سیستم"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    try:
        # دریافت تنظیمات
        settings = {}
        all_settings = await db.get_all_user_attachment_settings()
        for setting in all_settings:
            settings[setting['setting_key']] = setting['setting_value']
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        settings = {}
    
    # تبدیل به boolean/int
    system_enabled = settings.get('system_enabled', '1') == '1'
    
    # Parse enabled_modes JSON
    enabled_modes_str = settings.get('enabled_modes', '["mp","br"]')
    try:
        enabled_modes = json.loads(enabled_modes_str)
        br_enabled = 'br' in enabled_modes
        mp_enabled = 'mp' in enabled_modes
    except Exception as e:
        logger.error(f"Error parsing enabled_modes: {e}")
        br_enabled = True
        mp_enabled = True
    
    daily_limit = settings.get('daily_limit', '5')
    max_image_size = settings.get('max_image_size', '5242880')
    max_image_size_mb = int(max_image_size) / (1024 * 1024)
    auto_approve = settings.get('auto_approve_enabled', 'false') == 'true'
    
    message = (
        f"{t('admin.ua.settings.title', lang)}\n\n"
        f"{t('admin.ua.settings.status.header', lang)}\n"
        f"• {t('admin.ua.settings.system', lang)}: {'✅ ' + t('common.enabled_word', lang) if system_enabled else '🔴 ' + t('common.disabled_word', lang)}\n"
        f"• {t('mode.br_short', lang)}: {'✅' if br_enabled else '❌'}\n"
        f"• {t('mode.mp_short', lang)}: {'✅' if mp_enabled else '❌'}\n\n"
        f"{t('admin.ua.settings.limits.header', lang)}\n"
        f"• {t('admin.ua.limits.lines.daily', lang, n=daily_limit)}\n"
        f"• {t('admin.ua.limits.lines.image', lang, mb=f'{max_image_size_mb:.1f}')}\n"
        f"• {t('admin.ua.settings.auto_approve', lang)}: {'✅ ' + t('common.enabled_word', lang) if auto_approve else '❌ ' + t('common.disabled_word', lang)}"
    )
    
    keyboard = [
        [InlineKeyboardButton(
            t('admin.ua.settings.buttons.disable_system', lang) if system_enabled else t('admin.ua.settings.buttons.enable_system', lang),
            callback_data="ua_settings_toggle_system"
        )],
        [
            InlineKeyboardButton(
                f"{t('mode.br_short', lang)}: {'✅' if br_enabled else '❌'}",
                callback_data="ua_settings_toggle_br"
            ),
            InlineKeyboardButton(
                f"{t('mode.mp_short', lang)}: {'✅' if mp_enabled else '❌'}",
                callback_data="ua_settings_toggle_mp"
            )
        ],
        [
            InlineKeyboardButton(t('admin.ua.settings.buttons.categories', lang), callback_data="ua_settings_categories"),
            InlineKeyboardButton(t('admin.ua.settings.buttons.blacklist', lang), callback_data="ua_settings_blacklist")
        ],
        [InlineKeyboardButton(t('admin.ua.settings.buttons.limits', lang), callback_data="ua_settings_limits")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_admin_menu")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_system(update: Update, context: CustomContext):
    """فعال/غیرفعال کردن کل سیستم"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    try:
        current_value = await db.get_ua_setting('system_enabled')
        new_value = '0' if current_value == '1' else '1'
        await db.set_user_attachment_setting('system_enabled', new_value, user_id)
        
        status_word = t('common.enabled_word', lang) if new_value == '1' else t('common.disabled_word', lang)
        await query.answer(t('admin.ua.settings.system.toggled', lang, status=status_word), show_alert=True)
        
        # بازگشت به منو
        await show_ua_settings(update, context)
        
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)


async def toggle_mode(update: Update, context: CustomContext):
    """فعال/غیرفعال کردن BR یا MP"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # تشخیص mode
    if 'br' in query.data:
        mode = 'br'
        mode_name = t('mode.br_short', lang)
    else:
        mode = 'mp'
        mode_name = t('mode.mp_short', lang)
    
    try:
        # دریافت enabled_modes فعلی
        enabled_modes_str = await db.get_ua_setting('enabled_modes') or '["mp","br"]'
        enabled_modes = json.loads(enabled_modes_str)
        
        # toggle کردن mode
        if mode in enabled_modes:
            enabled_modes.remove(mode)
            status_word = t('common.disabled_word', lang)
        else:
            enabled_modes.append(mode)
            status_word = t('common.enabled_word', lang)
        
        # ذخیره تغییرات
        new_value = json.dumps(enabled_modes)
        success = await db.set_user_attachment_setting('enabled_modes', new_value, user_id)
        
        if success:
            logger.info(f"Mode {mode} toggled | New modes: {enabled_modes}")
            await query.answer(t('admin.ua.settings.mode.toggled', lang, mode=mode_name, status=status_word), show_alert=True)
        else:
            await query.answer(t('error.generic', lang), show_alert=True)
            return
        
        # بازگشت به منو
        await show_ua_settings(update, context)
        
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)


async def show_blacklist(update: Update, context: CustomContext):
    """نمایش لیست کلمات ممنوعه"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    try:
        blacklist = await db.get_all_blacklisted_words()
    except Exception as e:
        logger.error(f"Error fetching blacklist: {e}")
        blacklist = []
    
    if not blacklist:
        message = t('admin.ua.blacklist.empty_title', lang)
    else:
        message = t('admin.ua.blacklist.title', lang, n=len(blacklist)) + "\n\n"
        high = [w for w in blacklist if w['severity'] == 3]
        medium = [w for w in blacklist if w['severity'] == 2]
        low = [w for w in blacklist if w['severity'] == 1]
        if high:
            message += t('admin.ua.blacklist.severity.high_label', lang) + "\n"
            words_high = [w['word'] for w in high]
            message += ", ".join(words_high[:15])
            if len(high) > 15:
                message += f" ... (+{len(high)-15})"
            message += "\n\n"
        if medium:
            message += t('admin.ua.blacklist.severity.medium_label', lang) + "\n"
            words_medium = [w['word'] for w in medium]
            message += ", ".join(words_medium[:15])
            if len(medium) > 15:
                message += f" ... (+{len(medium)-15})"
            message += "\n\n"
        if low:
            message += t('admin.ua.blacklist.severity.low_label', lang) + "\n"
            words_low = [w['word'] for w in low]
            message += ", ".join(words_low[:15])
            if len(low) > 15:
                message += f" ... (+{len(low)-15})"
    
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.blacklist.buttons.add', lang), callback_data="ua_settings_blacklist_add")],
        [InlineKeyboardButton(t('admin.ua.blacklist.buttons.remove', lang), callback_data="ua_settings_blacklist_remove")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_admin_settings")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_limits_settings(update: Update, context: CustomContext):
    """نمایش تنظیمات محدودیت‌ها"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    try:
        # دریافت تنظیمات
        settings = {}
        all_settings = await db.get_all_user_attachment_settings()
        for setting in all_settings:
            settings[setting['setting_key']] = setting['setting_value']
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        settings = {}
    
    # دریافت مقادیر
    daily_limit = settings.get('daily_limit', '5')
    max_image_size = settings.get('max_image_size', '5242880')
    max_image_size_mb = int(max_image_size) / (1024 * 1024)
    rate_limit_requests = settings.get('rate_limit_requests', '5')
    rate_limit_window = settings.get('rate_limit_window', '600')
    rate_limit_minutes = int(rate_limit_window) / 60
    max_name_length = settings.get('max_name_length', '100')
    max_description_length = settings.get('max_description_length', '100')
    
    message = (
        f"{t('admin.ua.limits.title', lang)}\n\n"
        f"{t('admin.ua.limits.current.header', lang)}\n\n"
        f"{t('admin.ua.limits.lines.daily', lang, n=daily_limit)}\n"
        f"{t('admin.ua.limits.lines.image', lang, mb=f'{max_image_size_mb:.1f}')}\n"
        f"{t('admin.ua.limits.lines.rate', lang, requests=rate_limit_requests, minutes=int(rate_limit_minutes))}\n"
        f"{t('admin.ua.limits.lines.name', lang, n=max_name_length)}\n"
        f"{t('admin.ua.limits.lines.desc', lang, n=max_description_length)}\n\n"
        f"{t('admin.ua.limits.hint', lang)}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=daily_limit), callback_data="ua_settings_limit_daily"),
            InlineKeyboardButton(t('admin.ua.limits.buttons.image', lang, mb=f'{max_image_size_mb:.1f}'), callback_data="ua_settings_limit_image")
        ],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.rate', lang, requests=rate_limit_requests, minutes=int(rate_limit_minutes), min_label=t('common.min', lang)), callback_data="ua_settings_limit_rate")],
        [
            InlineKeyboardButton(t('admin.ua.limits.buttons.name', lang, n=max_name_length), callback_data="ua_settings_limit_name"),
            InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=max_description_length), callback_data="ua_settings_limit_desc")
        ],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_admin_settings")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_categories_settings(update: Update, context: CustomContext):
    """نمایش تنظیمات دسته‌ها"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # لیست ثابت دسته‌های بازی
    all_categories = [
        'assault_rifle',
        'smg',
        'lmg',
        'sniper',
        'shotgun',
        'marksman',
        'pistol',
        'launcher'
    ]
    
    try:
        # دریافت enabled_categories
        enabled_categories_str = await db.get_ua_setting('enabled_categories') or '[]'
        enabled_categories = json.loads(enabled_categories_str)
    except Exception as e:
        logger.error(f"Error fetching enabled_categories: {e}")
        enabled_categories = all_categories.copy()  # پیش‌فرض: همه فعال
    
    emoji_map = {
        'assault_rifle': '🔫',
        'smg': '🔥',
        'lmg': '💪',
        'sniper': '🎯',
        'shotgun': '💥',
        'marksman': '🏹',
        'pistol': '🔫',
        'launcher': '🚀'
    }
    message = f"{t('admin.ua.categories.title', lang)}\n\n"
    message += t('admin.ua.categories.summary', lang, total=len(all_categories), enabled=len(enabled_categories)) + "\n\n"
    message += t('admin.ua.categories.prompt', lang)
    
    # ساخت دکمه‌های دو ستونه
    keyboard = []
    row = []
    for cat_name in all_categories:
        is_enabled = cat_name in enabled_categories
        status_icon = "✅" if is_enabled else "❌"
        # Force English for category names
        display_name = f"{emoji_map.get(cat_name, '')} {t('category.' + cat_name, 'en')}"
        
        row.append(
            InlineKeyboardButton(
                f"{status_icon} {display_name}",
                callback_data=f"ua_settings_cat_toggle_{cat_name}"
            )
        )
        
        # هر 2 دکمه یک سطر
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # اگه دکمه باقی‌مونده اضافه کن
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_admin_settings")])
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_category(update: Update, context: CustomContext):
    """فعال/غیرفعال کردن یک دسته"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # استخراج نام دسته
    category_name = query.data.replace('ua_settings_cat_toggle_', '')
    
    try:
        # دریافت enabled_categories فعلی
        enabled_categories_str = await db.get_ua_setting('enabled_categories') or '[]'
        enabled_categories = json.loads(enabled_categories_str)
        
        # toggle کردن
        if category_name in enabled_categories:
            enabled_categories.remove(category_name)
            status_word = t('common.disabled_word', lang)
        else:
            enabled_categories.append(category_name)
            status_word = t('common.enabled_word', lang)
        
        # ذخیره
        new_value = json.dumps(enabled_categories)
        success = await db.set_user_attachment_setting('enabled_categories', new_value, user_id)
        
        if success:
            # Force English for category name in toggle message
            await query.answer(t('admin.ua.categories.toggled', lang, category=t('category.' + category_name, 'en'), status=status_word), show_alert=True)
        else:
            await query.answer(t('error.generic', lang), show_alert=True)
            return
        
        # بازگشت به منو
        await show_categories_settings(update, context)
        
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)


# Handlers برای افزودن و حذف کلمه (placeholder - نیاز به ConversationHandler)
async def start_add_blacklist_word(update: Update, context: CustomContext):
    """شروع فرآیند افزودن کلمه"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    message = (
        f"{t('admin.ua.blacklist.add.title', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.prompt', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.format', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.levels', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.example_one', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.example_multi', lang)}\n\n"
        f"{t('admin.ua.blacklist.add.hint_cancel', lang)}"
    )
    
    keyboard = [[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data="ua_settings_blacklist")]]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ADD_BLACKLIST_WORD


async def receive_new_blacklist_word(update: Update, context: CustomContext):
    """دریافت کلمه جدید از ادمین (تک یا چند کلمه)"""
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await update.message.reply_text(t('error.unauthorized', lang))
        return ConversationHandler.END
    
    text = update.message.text.strip()
    
    # بررسی فرمت: کلمه,سطح
    if ',' not in text:
        await update.message.reply_text(
            t('admin.ua.blacklist.add.invalid_format', lang) + "\n\n" +
            t('admin.ua.blacklist.add.format', lang) + "\n\n" +
            t('admin.ua.blacklist.add.example_one', lang) + "\n\n" +
            t('admin.ua.blacklist.add.example_multi', lang),
            parse_mode='Markdown'
        )
        return ADD_BLACKLIST_WORD
    
    # پردازش چند خطی (multi-line support)
    lines = text.strip().split('\n')
    
    success_count = 0
    failed_count = 0
    success_words = []
    failed_words = []
    severity_names = {1: t('admin.ua.blacklist.severity.low', lang), 2: t('admin.ua.blacklist.severity.medium', lang), 3: t('admin.ua.blacklist.severity.high', lang)}
    
    for line in lines:
        line = line.strip()
        if not line or ',' not in line:
            continue
        
        try:
            parts = line.split(',')
            word = parts[0].strip()
            severity = int(parts[1].strip())
            
            # بررسی سطح
            if severity not in [1, 2, 3]:
                failed_words.append(f"{word} (سطح نامعتبر)")
                failed_count += 1
                continue
            
            # اضافه کردن به database
            success = await db.add_blacklisted_word(word, 'profanity', severity, user_id)
            
            if success:
                success_words.append(f"{word} ({severity_names[severity]})")
                success_count += 1
            else:
                failed_words.append(f"{word} (تکراری)")
                failed_count += 1
                
        except (ValueError, IndexError):
            failed_words.append(f"{line} (فرمت اشتباه)")
            failed_count += 1
    
    # ساخت پیام نتیجه
    if success_count == 0 and failed_count == 0:
        message = t('error.generic', lang)
    else:
        message = f"{t('admin.ua.blacklist.result.title', lang)}\n\n"
        if success_count > 0:
            message += t('admin.ua.blacklist.result.success', lang, count=success_count) + "\n"
            display_success = success_words[:5]
            message += "• " + "\n• ".join(display_success)
            if len(success_words) > 5:
                message += f"\n• ... {len(success_words)-5}"
            message += "\n\n"
        if failed_count > 0:
            message += t('admin.ua.blacklist.result.failed', lang, count=failed_count) + "\n"
            display_failed = failed_words[:3]
            message += "• " + "\n• ".join(display_failed)
            if len(failed_words) > 3:
                message += f"\n• ... {len(failed_words)-3}"
    
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.blacklist.buttons.add', lang), callback_data="ua_settings_blacklist_add")],
        [InlineKeyboardButton(t('admin.ua.blacklist.buttons.back', lang), callback_data="ua_settings_blacklist")]
    ]
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END


async def cancel_blacklist_operation(update: Update, context: CustomContext):
    """لغو عملیات"""
    lang = await get_user_lang(update, context, db) or 'fa'
    if update.callback_query:
        query = update.callback_query
        await query.answer(t('common.cancelled', lang))
        await show_blacklist(update, context)
    else:
        await update.message.reply_text(t('common.cancelled', lang))
    
    return ConversationHandler.END


# تغییر محدودیت‌ها با دکمه‌های از پیش تعریف شده
async def change_limit_daily(update: Update, context: CustomContext):
    """تغییر محدودیت روزانه"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    message = f"{t('admin.ua.limits.title', lang)}\n\n{t('common.choose_value', lang)}"
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=3), callback_data="ua_limit_daily_set_3"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=5), callback_data="ua_limit_daily_set_5")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=10), callback_data="ua_limit_daily_set_10"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=15), callback_data="ua_limit_daily_set_15")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.daily', lang, n=t('common.unlimited', lang)), callback_data="ua_limit_daily_set_999")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_limits")]
    ]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def change_limit_description(update: Update, context: CustomContext):
    """تغییر طول توضیحات"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    message = f"{t('admin.ua.limits.title', lang)}\n\n{t('common.choose_value', lang)}"
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=50), callback_data="ua_limit_desc_set_50"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=100), callback_data="ua_limit_desc_set_100")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=150), callback_data="ua_limit_desc_set_150"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=200), callback_data="ua_limit_desc_set_200")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=300), callback_data="ua_limit_desc_set_300"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.desc', lang, n=500), callback_data="ua_limit_desc_set_500")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_limits")]
    ]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def change_limit_name(update: Update, context: CustomContext):
    """تغییر طول نام"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    message = f"{t('admin.ua.limits.title', lang)}\n\n{t('common.choose_value', lang)}"
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.limits.buttons.name', lang, n=50), callback_data="ua_limit_name_set_50"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.name', lang, n=75), callback_data="ua_limit_name_set_75")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.name', lang, n=100), callback_data="ua_limit_name_set_100"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.name', lang, n=150), callback_data="ua_limit_name_set_150")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_limits")]
    ]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def change_limit_image(update: Update, context: CustomContext):
    """تغییر حجم تصویر"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    message = f"{t('admin.ua.limits.title', lang)}\n\n{t('common.choose_value', lang)}"
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.limits.buttons.image', lang, mb=2), callback_data="ua_limit_image_set_2097152"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.image', lang, mb=5), callback_data="ua_limit_image_set_5242880")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.image', lang, mb=10), callback_data="ua_limit_image_set_10485760"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.image', lang, mb=15), callback_data="ua_limit_image_set_15728640")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_limits")]
    ]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def change_limit_rate(update: Update, context: CustomContext):
    """تغییر Rate Limit"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_lang(update, context, db) or 'fa'
    message = f"{t('admin.ua.limits.title', lang)}\n\n{t('common.choose_value', lang)}"
    keyboard = [
        [InlineKeyboardButton(t('admin.ua.limits.buttons.rate', lang, requests=3, minutes=5, min_label=t('common.min', lang)), callback_data="ua_limit_rate_set_3_300"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.rate', lang, requests=5, minutes=10, min_label=t('common.min', lang)), callback_data="ua_limit_rate_set_5_600")],
        [InlineKeyboardButton(t('admin.ua.limits.buttons.rate', lang, requests=10, minutes=15, min_label=t('common.min', lang)), callback_data="ua_limit_rate_set_10_900"),
         InlineKeyboardButton(t('admin.ua.limits.buttons.rate', lang, requests=15, minutes=30, min_label=t('common.min', lang)), callback_data="ua_limit_rate_set_15_1800")],
        [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_limits")]
    ]
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def set_limit_value(update: Update, context: CustomContext):
    """ذخیره مقدار جدید محدودیت"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return
    
    # استخراج setting key و value از callback_data
    # فرمت: ua_limit_{type}_set_{value} یا ua_limit_rate_set_{requests}_{window}
    parts = query.data.split('_')
    if len(parts) < 5:
        await query.answer(t('error.generic', lang), show_alert=True)
        return
    
    limit_type = parts[2]  # daily, desc, name, image, rate
    
    try:
        # بررسی نوع محدودیت
        if limit_type == 'rate':
            # فرمت خاص برای rate: ua_limit_rate_set_{requests}_{window}
            if len(parts) < 6:
                await query.answer(t('error.generic', lang), show_alert=True)
                return
            requests = parts[4]
            window = parts[5]
            
            # ذخیره هر دو مقدار
            success1 = await db.set_user_attachment_setting('rate_limit_requests', requests, user_id)
            success2 = await db.set_user_attachment_setting('rate_limit_window', window, user_id)
            
            if success1 and success2:
                await query.answer("✅ " + t('admin.ua.limits.buttons.rate', lang, requests=requests, minutes=int(window)/60, min_label=t('common.min', lang)), show_alert=True)
                await show_limits_settings(update, context)
            else:
                await query.answer(t('error.generic', lang), show_alert=True)
        else:
            # محدودیت‌های عادی
            new_value = parts[4]
            
            # تعیین setting key
            setting_map = {
                'daily': 'daily_limit',
                'desc': 'max_description_length',
                'name': 'max_name_length',
                'image': 'max_image_size'
            }
            
            setting_key = setting_map.get(limit_type)
            if not setting_key:
                await query.answer(t('error.generic', lang), show_alert=True)
                return
            
            # ذخیره در database
            success = await db.set_user_attachment_setting(setting_key, new_value, user_id)
            
            if success:
                if limit_type == 'image':
                    mb_value = int(new_value) / (1024 * 1024)
                    await query.answer("✅ " + t('admin.ua.limits.buttons.image', lang, mb=f"{mb_value:.1f}"), show_alert=True)
                elif limit_type == 'daily':
                    await query.answer("✅ " + t('admin.ua.limits.buttons.daily', lang, n=new_value), show_alert=True)
                elif limit_type == 'name':
                    await query.answer("✅ " + t('admin.ua.limits.buttons.name', lang, n=new_value), show_alert=True)
                elif limit_type == 'desc':
                    await query.answer("✅ " + t('admin.ua.limits.buttons.desc', lang, n=new_value), show_alert=True)
                await show_limits_settings(update, context)
            else:
                await query.answer(t('error.generic', lang), show_alert=True)
                
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)


async def start_remove_blacklist_word(update: Update, context: CustomContext):
    """شروع فرآیند حذف کلمه"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await query.answer(t('error.unauthorized', lang), show_alert=True)
        return ConversationHandler.END
    
    # دریافت لیست کلمات
    try:
        blacklist = await db.get_all_blacklisted_words()
        if not blacklist:
            await query.answer(t('admin.ua.blacklist.empty_title', lang), show_alert=True)
            await show_blacklist(update, context)
            return ConversationHandler.END
    except Exception as e:
        from utils.error_handler import error_handler
        await error_handler.handle_telegram_error(update, context, e)
        return ConversationHandler.END
    
    message = (
        f"{t('admin.ua.blacklist.remove.title', lang)}\n\n"
        f"{t('admin.ua.blacklist.remove.prompt', lang)}\n\n"
    )
    examples = [w['word'] for w in blacklist[:10]]
    message += f"{t('admin.ua.blacklist.remove.examples', lang)}\n"
    message += ", ".join(examples)
    if len(blacklist) > 10:
        message += f" ... (+{len(blacklist)-10})"
    message += "\n\n" + t('admin.ua.blacklist.add.hint_cancel', lang)
    
    keyboard = [[InlineKeyboardButton(t('menu.buttons.cancel', lang), callback_data="ua_settings_blacklist")]]
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return REMOVE_BLACKLIST_WORD


async def receive_word_to_remove(update: Update, context: CustomContext):
    """دریافت کلمه برای حذف"""
    user_id = update.effective_user.id
    lang = await get_user_lang(update, context, db) or 'fa'
    if not await has_ua_perm(user_id):
        await update.message.reply_text(t('error.unauthorized', lang))
        return ConversationHandler.END
    
    word = update.message.text.strip()
    
    try:
        # پیدا کردن ID کلمه
        blacklist = await db.get_all_blacklisted_words()
        word_entry = next((w for w in blacklist if w['word'].lower() == word.lower()), None)
        
        if not word_entry:
            await update.message.reply_text(
                t('admin.ua.blacklist.remove.not_found', lang, word=word)
            )
            return REMOVE_BLACKLIST_WORD
        
        # حذف کلمه
        success = db.remove_blacklisted_word(word_entry['id'])
        
        if success:
            keyboard = [
                [InlineKeyboardButton(t('admin.ua.blacklist.buttons.remove', lang), callback_data="ua_settings_blacklist_remove")],
                [InlineKeyboardButton(t('admin.ua.blacklist.buttons.back', lang), callback_data="ua_settings_blacklist")]
            ]
            await update.message.reply_text(
                t('admin.ua.blacklist.remove.success', lang, word=word),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton(t('menu.buttons.retry', lang), callback_data="ua_settings_blacklist_remove")],
                [InlineKeyboardButton(t('menu.buttons.back', lang), callback_data="ua_settings_blacklist")]
            ]
            await update.message.reply_text(
                t('admin.ua.blacklist.remove.error', lang),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error removing word: {e}")
        await update.message.reply_text(t('admin.ua.blacklist.remove.error', lang))
        return ConversationHandler.END


# ConversationHandler برای افزودن کلمه ممنوعه
add_blacklist_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_add_blacklist_word, pattern="^ua_settings_blacklist_add$")
    ],
    states={
        ADD_BLACKLIST_WORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_blacklist_word)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_blacklist_operation, pattern="^ua_settings_blacklist$"),
        MessageHandler(filters.Regex("^/cancel$"), cancel_blacklist_operation)
    ],
    name="ua_add_blacklist",
    persistent=False,
    per_message=False,
    allow_reentry=True
)

# ConversationHandler برای حذف کلمه ممنوعه
remove_blacklist_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_remove_blacklist_word, pattern="^ua_settings_blacklist_remove$")
    ],
    states={
        REMOVE_BLACKLIST_WORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_word_to_remove)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_blacklist_operation, pattern="^ua_settings_blacklist$"),
        MessageHandler(filters.Regex("^/cancel$"), cancel_blacklist_operation)
    ],
    name="ua_remove_blacklist",
    persistent=False,
    per_message=False,
    allow_reentry=True
)

# Export handlers
settings_handlers = [
    CallbackQueryHandler(show_ua_settings, pattern="^ua_admin_settings$"),
    CallbackQueryHandler(toggle_system, pattern="^ua_settings_toggle_system$"),
    CallbackQueryHandler(toggle_mode, pattern="^ua_settings_toggle_(br|mp)$"),
    CallbackQueryHandler(show_blacklist, pattern="^ua_settings_blacklist$"),
    CallbackQueryHandler(show_limits_settings, pattern="^ua_settings_limits$"),
    
    # محدودیت‌ها
    CallbackQueryHandler(change_limit_daily, pattern="^ua_settings_limit_daily$"),
    CallbackQueryHandler(change_limit_description, pattern="^ua_settings_limit_desc$"),
    CallbackQueryHandler(change_limit_name, pattern="^ua_settings_limit_name$"),
    CallbackQueryHandler(change_limit_image, pattern="^ua_settings_limit_image$"),
    CallbackQueryHandler(change_limit_rate, pattern="^ua_settings_limit_rate$"),
    CallbackQueryHandler(set_limit_value, pattern="^ua_limit_(daily|desc|name|image|rate)_set_"),
    
    CallbackQueryHandler(show_categories_settings, pattern="^ua_settings_categories$"),
    CallbackQueryHandler(toggle_category, pattern="^ua_settings_cat_toggle_"),
    
    # ConversationHandlers برای blacklist
    add_blacklist_conv,
    remove_blacklist_conv,
]
