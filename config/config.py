"""
تنظیمات ربات تلگرام CODM Attachments
"""

import os
import sys
from dotenv import load_dotenv
from core.cache.cache_manager import cached

# Load environment variables from .env file
load_dotenv()

# i18n
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "fa")
SUPPORTED_LANGS = [s.strip() for s in os.getenv("SUPPORTED_LANGS", "fa,en").split(",") if s.strip()]
FALLBACK_LANG = os.getenv("FALLBACK_LANG", "en")
LANGUAGE_ONBOARDING = os.getenv("LANGUAGE_ONBOARDING", "true").lower() == "true"

# توکن ربات تلگرام - از متغیر محیطی خوانده می‌شود
BOT_TOKEN = os.getenv("BOT_TOKEN")

# بررسی وجود توکن
if not BOT_TOKEN:
    print("❌ خطا: توکن ربات یافت نشد!")
    print("لطفاً فایل .env را ایجاد کرده و BOT_TOKEN را تنظیم کنید.")
    print("می‌توانید از .env.example به عنوان نمونه استفاده کنید.")
    sys.exit(1)

# ----------------------------------------------------------------------------
# Webhook Configuration
# ----------------------------------------------------------------------------
# حالت اجرا: "polling" (پیش‌فرض) یا "webhook"
BOT_MODE = os.getenv("BOT_MODE", "polling").lower()

# آدرس کامل سرور بدون مسیر (مثال: https://bot.example.com)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")

# پورت داخلی که bot روی آن listen می‌کند
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))

# مسیر endpoint (مثال: /webhook)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

# توکن امنیتی - اگر خالی باشد به صورت خودکار تولید می‌شود
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "")

# مسیر گواهی SSL (فقط برای self-signed certificate - برای reverse proxy خالی بگذارید)
WEBHOOK_CERT_PATH = os.getenv("WEBHOOK_CERT_PATH", "").strip()
WEBHOOK_KEY_PATH = os.getenv("WEBHOOK_KEY_PATH", "").strip()

# آیدی سوپراادمین (صاحب ربات) - از متغیر محیطی
SUPER_ADMIN_ID = None
admin_id_str = os.getenv("SUPER_ADMIN_ID")
if admin_id_str:
    try:
        SUPER_ADMIN_ID = int(admin_id_str)
    except ValueError:
        print("⚠️ خطا: SUPER_ADMIN_ID باید یک عدد معتبر باشد")
else:
    print("⚠️ توجه: SUPER_ADMIN_ID تنظیم نشده. ربات بدون ادمین اصلی شروع می‌شود.")
    print("برای تنظیم ادمین، فایل .env را ویرایش کنید.")

# تنظیمات دیتابیس
BACKUP_DIR = "backups"

# دسته‌بندی سلاح‌ها (IDs)
WEAPON_CATEGORIES_IDS = [
    "assault_rifle", "smg", "lmg", "sniper", 
    "marksman", "shotgun", "pistol", "launcher"
]

WEAPON_CATEGORIES = {
    "assault_rifle": "Assault Rifle",
    "smg": "SMG",
    "lmg": "LMG",
    "sniper": "Sniper",
    "marksman": "Marksman",
    "shotgun": "Shotgun",
    "pistol": "Pistol",
    "launcher": "Launcher"
}

WEAPON_CATEGORIES_SHORT = {
    "assault_rifle": "AR",
    "smg": "SMG",
    "lmg": "LMG",
    "sniper": "Sniper",
    "marksman": "Marksman",
    "shotgun": "SG",
    "pistol": "Pistol",
    "launcher": "Launcher"
}

CATEGORIES = WEAPON_CATEGORIES

# تنظیمات Mode (Battle Royale / Multiplayer)
GAME_MODES = {
    "br": "🪂 BR",
    "mp": "🎮 MP"
}

@cached(ttl=300, key_func=lambda callback_prefix, show_count=False, db=None, lang='fa', active_ids=None, **kwargs: f"cat_kb:{callback_prefix}:{show_count}:{lang}:{active_ids}")
async def build_category_keyboard(callback_prefix: str, show_count: bool = False, db=None, lang: str = 'fa', active_ids: list = None) -> list:
    """
    ساخت کیبورد 2 ستونی برای دسته‌بندی‌ها با استفاده از i18n
    
    Args:
        callback_prefix: پیشوند callback_data (مثل "cat_", "aac_")
        show_count: نمایش تعداد سلاح‌ها
        db: شیء دیتابیس (فقط برای show_count=True)
        lang: زبان (fa/en) برای translation
        active_ids: لیست IDهای فعال (اگر None باشد، همه نمایش داده می‌شوند)
    
    Returns:
        لیست ردیف‌های کیبورد
    """
    from telegram import InlineKeyboardButton
    from utils.i18n import t
    
    keyboard = []
    buttons = []
    
    counts = {}
    if show_count and db:
        try:
            # کش در خود متد دیتابیس هندل می‌شود
            counts = await db.get_all_category_counts()
        except Exception:
            counts = {}
    
    target_ids = active_ids if active_ids is not None else WEAPON_CATEGORIES_IDS
    
    for key in target_ids:
        # دریافت نام نمایشی از i18n - همیشه انگلیسی به درخواست کاربر
        display_name = t(f"category.{key}", lang='en')
        
        # اضافه کردن ایموجی بر اساس ID
        emojis = {
            "assault_rifle": "🔫", "smg": "⚡", "lmg": "🎯", "sniper": "🔭",
            "marksman": "🎪", "shotgun": "💥", "pistol": "🔫", "launcher": "🚀"
        }
        emoji = emojis.get(key, "")
        button_text = f"{emoji} {display_name}" if emoji else display_name
        
        if show_count and db:
            weapons_count = counts.get(key, 0)
            button_text = f"{button_text} ({weapons_count})"
        
        buttons.append(InlineKeyboardButton(button_text, callback_data=f"{callback_prefix}{key}"))
    
    # تقسیم دکمه‌ها به ردیف‌های 2 تایی
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.append([buttons[i], buttons[i + 1]])
        else:
            keyboard.append([buttons[i]])
    
    return keyboard

def build_weapon_keyboard(weapons: list, callback_prefix: str, category: str = None, add_emoji: bool = False) -> list:
    """
    ساخت کیبورد برای سلاح‌ها با تعداد ستون‌های متغیر بر اساس دسته
    
    Args:
        weapons: لیست نام سلاح‌ها
        callback_prefix: پیشوند callback_data (مثل "wpn_", "aaw_")
        category: دسته سلاح (برای تعیین تعداد ستون‌ها)
        add_emoji: اضافه کردن ایموجی 🔫 به متن دکمه
    
    Returns:
        لیست ردیف‌های کیبورد
    """
    from telegram import InlineKeyboardButton
    
    # تعیین تعداد ستون‌ها بر اساس دسته
    # AR و SMG: 3 ستونی، بقیه: 2 ستونی
    columns = 3 if category in ['assault_rifle', 'smg'] else 2
    
    keyboard = []
    for i in range(0, len(weapons), columns):
        row = []
        for j in range(columns):
            if i + j < len(weapons):
                weapon = weapons[i + j]
                button_text = f"🔫 {weapon}" if add_emoji else weapon
                row.append(InlineKeyboardButton(
                    button_text, 
                    callback_data=f"{callback_prefix}{weapon}"
                ))
        keyboard.append(row)
    
    return keyboard

# وضعیت فعال/غیرفعال بودن هر دسته برای نمایش به کاربران
# ساختار mode-based: {'mp': {'category': {'enabled': bool}}, 'br': {...}}
DEFAULT_CATEGORY_SETTINGS = {
    'mp': {
        'assault_rifle': {'enabled': True},
        'launcher': {'enabled': True},
        'lmg': {'enabled': True},
        'marksman': {'enabled': True},
        'pistol': {'enabled': True},
        'shotgun': {'enabled': True},
        'smg': {'enabled': True},
        'sniper': {'enabled': True}
    },
    'br': {
        'assault_rifle': {'enabled': True},
        'launcher': {'enabled': True},
        'lmg': {'enabled': True},
        'marksman': {'enabled': True},
        'pistol': {'enabled': True},
        'shotgun': {'enabled': True},
        'smg': {'enabled': True},
        'sniper': {'enabled': True}
    }
}

import json

async def get_all_category_settings(db=None) -> dict:
    if db:
        val = await db.get_setting('category_settings')
        if val:
            try:
                return json.loads(val)
            except Exception:
                pass
    return DEFAULT_CATEGORY_SETTINGS

CATEGORY_SETTINGS = DEFAULT_CATEGORY_SETTINGS

async def get_category_setting(category: str, mode: str = None, db=None) -> dict:
    """دریافت تنظیمات یک دسته برای mode مشخص از دیتابیس"""
    if mode is None:
        mode = 'mp'  # default
    settings = await get_all_category_settings(db)
    if mode in settings and category in settings[mode]:
        return settings[mode][category]
    return {'enabled': True}

async def is_category_enabled(category: str, mode: str = None, db=None) -> bool:
    """بررسی فعال بودن یک دسته برای mode مشخص"""
    settings = await get_category_setting(category, mode, db)
    return settings.get('enabled', True)

async def set_category_enabled(category: str, enabled: bool, mode: str = None, db=None):
    """تنظیم وضعیت فعال/غیرفعال یک دسته در دیتابیس"""
    settings = await get_all_category_settings(db)
    
    if mode is None:
        for m in ['mp', 'br']:
            if m not in settings:
                settings[m] = {}
            if category not in settings[m]:
                settings[m][category] = {}
            settings[m][category]['enabled'] = enabled
    else:
        if mode not in settings:
            settings[mode] = {}
        if category not in settings[mode]:
            settings[mode][category] = {}
        settings[mode][category]['enabled'] = enabled
    
    if db:
        await db.set_setting('category_settings', json.dumps(settings), "Category enable/disable settings")

DEFAULT_NOTIFICATION_SETTINGS = {
    "enabled": True,
    "events": {
        "add_attachment": True,
        "edit_name": True,
        "edit_image": True,
        "edit_code": True,
        "delete_attachment": True,
        "top_set": True,
        "top_added": True,
        "top_removed": True
    },
    "templates": {
        "add_attachment": "notification.template.add_attachment",
        "edit_name": "notification.template.edit_name",
        "edit_image": "notification.template.edit_image",
        "edit_code": "notification.template.edit_code",
        "delete_attachment": "notification.template.delete_attachment",
        "top_set": "notification.template.top_set",
        "top_added": "notification.template.top_added",
        "top_removed": "notification.template.top_removed"
    },
    "auto_notify": True
}

async def get_notification_settings(db=None) -> dict:
    if db:
        val = await db.get_setting('notification_settings')
        if val:
            try:
                settings = json.loads(val)
                merged = {**DEFAULT_NOTIFICATION_SETTINGS, **settings}
                merged['events'] = {**DEFAULT_NOTIFICATION_SETTINGS.get('events', {}), **settings.get('events', {})}
                merged['templates'] = {**DEFAULT_NOTIFICATION_SETTINGS.get('templates', {}), **settings.get('templates', {})}
                return merged
            except Exception:
                pass
    return DEFAULT_NOTIFICATION_SETTINGS

async def set_notification_settings(settings: dict, db=None) -> bool:
    if db:
        return await db.set_setting('notification_settings', json.dumps(settings), "Global notification settings")
    return False



# تنظیمات صفحه‌بندی
ITEMS_PER_PAGE = 10

# تنظیمات لاگ
LOG_FILE = "bot.log"
LOG_LEVEL = "INFO"

# End of configuration
