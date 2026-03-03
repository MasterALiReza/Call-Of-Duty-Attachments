"""
Centralized Input Validation for Database Repositories

این ماژول تمام validation‌های ورودی را متمرکز می‌کند تا از SQL Injection جلوگیری شود
و کد تکراری در repositories حذف گردد.
"""

from typing import Optional, Set
import re


# === Whitelist Constants ===

ALLOWED_MODES: Set[str] = {'br', 'mp', 'zombies'}
ALLOWED_STATUSES: Set[str] = {'pending', 'approved', 'rejected', 'deleted'}
ALLOWED_SORTS: Set[str] = {'created_at', 'last_seen', 'username', 'user_id', 'submitted_at', 'approved_at', 'rejected_at'}
ALLOWED_CATEGORIES: Set[str] = {
    'assault_rifle', 'smg', 'lmg', 'sniper', 
    'marksman', 'shotgun', 'pistol', 'launcher'
}
ALLOWED_EVENT_TYPES: Set[str] = {
    'add_attachment', 'edit_name', 'edit_image', 
    'delete_attachment', 'set_top', 'view', 'copy'
}
ALLOWED_LANGUAGES: Set[str] = {'fa', 'en'}


# === Validation Functions ===

def validate_mode(mode: str) -> str:
    """
    اعتبارسنجی mode بازی
    
    Args:
        mode: مود بازی (br, mp, zombies)
        
    Returns:
        str: mode تایید شده
        
    Raises:
        ValueError: اگر mode نامعتبر باشد
    """
    if not mode:
        raise ValueError("Mode cannot be empty")
    mode_lower = mode.lower().strip()
    if mode_lower not in ALLOWED_MODES:
        raise ValueError(f"Invalid mode: '{mode}'. Allowed: {ALLOWED_MODES}")
    return mode_lower


def validate_status(status: str) -> str:
    """
    اعتبارسنجی وضعیت attachment
    
    Args:
        status: وضعیت (pending, approved, rejected, deleted)
        
    Returns:
        str: status تایید شده
        
    Raises:
        ValueError: اگر status نامعتبر باشد
    """
    if not status:
        raise ValueError("Status cannot be empty")
    status_lower = status.lower().strip()
    if status_lower not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: '{status}'. Allowed: {ALLOWED_STATUSES}")
    return status_lower


def validate_sort_column(sort_by: str, allowed: Optional[Set[str]] = None) -> str:
    """
    اعتبارسنجی ستون مرتب‌سازی
    
    Args:
        sort_by: نام ستون
        allowed: مجموعه مجاز (پیش‌فرض ALLOWED_SORTS)
        
    Returns:
        str: ستون تایید شده یا 'created_at' به عنوان پیش‌فرض
    """
    if allowed is None:
        allowed = ALLOWED_SORTS
    
    if not sort_by:
        return 'created_at'
    
    sort_lower = sort_by.lower().strip()
    
    # جلوگیری از SQL Injection در ORDER BY
    if sort_lower in allowed:
        return sort_lower
    
    return 'created_at'


def validate_category(category: str) -> str:
    """
    اعتبارسنجی دسته سلاح
    
    Args:
        category: نام دسته
        
    Returns:
        str: category تایید شده
        
    Raises:
        ValueError: اگر category نامعتبر باشد
    """
    if not category:
        raise ValueError("Category cannot be empty")
    category_lower = category.lower().strip()
    if category_lower not in ALLOWED_CATEGORIES:
        raise ValueError(f"Invalid category: '{category}'. Allowed: {ALLOWED_CATEGORIES}")
    return category_lower


def validate_language(lang: str) -> str:
    """
    اعتبارسنجی کد زبان
    
    Args:
        lang: کد زبان (fa, en)
        
    Returns:
        str: کد زبان تایید شده
    """
    if not lang:
        return 'fa'  # پیش‌فرض
    lang_lower = lang.lower().strip()
    if lang_lower not in ALLOWED_LANGUAGES:
        return 'fa'  # fallback به فارسی
    return lang_lower


def validate_user_id(user_id: int) -> int:
    """
    اعتبارسنجی Telegram User ID
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        int: user_id تایید شده
        
    Raises:
        ValueError: اگر user_id نامعتبر باشد
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}. Must be positive integer")
    return user_id


def validate_attachment_id(attachment_id: int) -> int:
    """
    اعتبارسنجی Attachment ID
    
    Args:
        attachment_id: شناسه اتچمنت
        
    Returns:
        int: attachment_id تایید شده
        
    Raises:
        ValueError: اگر attachment_id نامعتبر باشد
    """
    if not isinstance(attachment_id, int) or attachment_id <= 0:
        raise ValueError(f"Invalid attachment_id: {attachment_id}. Must be positive integer")
    return attachment_id


def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """
    پاکسازی عبارت جستجو
    
    Args:
        query: عبارت جستجو
        max_length: حداکثر طول مجاز
        
    Returns:
        str: عبارت پاک شده
    """
    if not query:
        return ''
    
    # حذف کاراکترهای خطرناک
    sanitized = re.sub(r"[;'\"]", '', query.strip())
    
    # محدود کردن طول
    return sanitized[:max_length]


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    پاکسازی رشته عمومی
    
    Args:
        value: رشته ورودی
        max_length: حداکثر طول مجاز
        
    Returns:
        str: رشته پاک شده
    """
    if not value:
        return ''
    
    # حذف null bytes و کنترل کاراکترها
    sanitized = ''.join(c for c in value if c.isprintable() or c in '\n\r\t')
    
    return sanitized.strip()[:max_length]


def validate_limit_offset(limit: Optional[int], offset: Optional[int], max_limit: int = 100) -> tuple:
    """
    اعتبارسنجی پارامترهای صفحه‌بندی
    
    Args:
        limit: تعداد آیتم‌ها در هر صفحه
        offset: شروع از آیتم
        max_limit: حداکثر limit مجاز
        
    Returns:
        tuple: (limit, offset) تایید شده
    """
    # اعتبارسنجی limit
    if limit is None:
        limit = 10
    elif not isinstance(limit, int) or limit < 1:
        limit = 10
    elif limit > max_limit:
        limit = max_limit
    
    # اعتبارسنجی offset
    if offset is None:
        offset = 0
    elif not isinstance(offset, int) or offset < 0:
        offset = 0
    
    return limit, offset


def validate_int(value: int, min_val: int = None, max_val: int = None, default: int = 0) -> int:
    """
    اعتبارسنجی عدد صحیح
    
    Args:
        value: مقدار ورودی
        min_val: حداقل مجاز
        max_val: حداکثر مجاز
        default: مقدار پیش‌فرض
        
    Returns:
        int: مقدار تایید شده
    """
    if not isinstance(value, int):
        return default
    
    if min_val is not None and value < min_val:
        return min_val
    
    if max_val is not None and value > max_val:
        return max_val
    
    return value


# === Safe Value Functions (برای استفاده در f-strings) ===

def safe_sort_column(sort_by: str, allowed: Optional[Set[str]] = None) -> str:
    """
    ستون مرتب‌سازی امن برای استفاده در SQL
    
    این تابع همیشه یک مقدار امن برمی‌گرداند و exception نمی‌زند
    """
    try:
        return validate_sort_column(sort_by, allowed)
    except (ValueError, TypeError, AttributeError):
        return 'created_at'


def safe_mode(mode: str) -> str:
    """مود امن - همیشه مقدار معتبر برمی‌گرداند"""
    try:
        return validate_mode(mode)
    except (ValueError, TypeError, AttributeError):
        return 'br'  # پیش‌فرض


def safe_status(status: str) -> str:
    """وضعیت امن"""
    try:
        return validate_status(status)
    except (ValueError, TypeError, AttributeError):
        return 'pending'  # پیش‌فرض
