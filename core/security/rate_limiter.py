"""
سیستم Rate Limiting برای جلوگیری از ban شدن ربات
"""
import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import deque
import logging
from config.constants import (
    TELEGRAM_API_CALLS_PER_SECOND,
    TELEGRAM_API_RATE_PERIOD,
    TELEGRAM_FILE_UPLOAD_PER_SECOND,
    BROADCAST_MAX_RETRIES
)
logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """تعریف محدودیت نرخ"""
    calls: int
    period: int
    burst: Optional[int] = None

class RateLimiter:
    """
    مدیریت rate limiting برای عملیات\u200cهای مختلف خروجی تلگرام (Global API Call Limits)
    برای جلوگیری از مسدود شدن ربات (429 Too Many Requests) به خاطر ارسال پیام زیاد.
    """
    TELEGRAM_LIMITS = {
        'broadcast': RateLimit(calls=TELEGRAM_API_CALLS_PER_SECOND, period=TELEGRAM_API_RATE_PERIOD),
        'bulk_message': RateLimit(calls=TELEGRAM_API_CALLS_PER_SECOND, period=TELEGRAM_API_RATE_PERIOD, burst=50),
        'api_call': RateLimit(calls=TELEGRAM_API_CALLS_PER_SECOND, period=TELEGRAM_API_RATE_PERIOD),
        'file_upload': RateLimit(calls=TELEGRAM_FILE_UPLOAD_PER_SECOND, period=TELEGRAM_API_RATE_PERIOD)
    }

    def __init__(self):
        self.call_history: Dict[str, deque] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    def _get_history(self, key: str) -> deque:
        """دریافت تاریخچه فراخوانی\u200cها"""
        if key not in self.call_history:
            self.call_history[key] = deque(maxlen=1000)
        return self.call_history[key]

    def _get_lock(self, key: str) -> asyncio.Lock:
        """دریافت lock برای یک کلید"""
        if key not in self.locks:
            self.locks[key] = asyncio.Lock()
        return self.locks[key]

    def _clean_history(self, history: deque, period: int):
        """پاکسازی تاریخچه قدیمی"""
        current_time = time.time()
        cutoff = current_time - period
        while history and history[0] < cutoff:
            history.popleft()

    async def check_rate_limit(self, key: str, limit: Optional[RateLimit]=None) -> tuple[bool, float]:
        """
        بررسی rate limit
        Returns: (is_allowed, wait_time)
        """
        if limit is None:
            limit = self.TELEGRAM_LIMITS.get(key, RateLimit(calls=TELEGRAM_API_CALLS_PER_SECOND, period=TELEGRAM_API_RATE_PERIOD))
        async with self._get_lock(key):
            history = self._get_history(key)
            current_time = time.time()
            self._clean_history(history, limit.period)
            if len(history) >= limit.calls:
                oldest_call = history[0]
                wait_time = limit.period - (current_time - oldest_call)
                if wait_time > 0:
                    return (False, wait_time)
            history.append(current_time)
            return (True, 0)

    async def wait_if_needed(self, key: str, limit: Optional[RateLimit]=None):
        """صبر کردن در صورت نیاز برای رعایت rate limit"""
        while True:
            allowed, wait_time = await self.check_rate_limit(key, limit)
            if allowed:
                break
            logger.debug(f'Rate limit reached for {key}, waiting {wait_time:.2f}s')
            await asyncio.sleep(wait_time)

class BroadcastQueue:
    """صف هوشمند برای ارسال پیام\u200cهای broadcast"""

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter
        self.queue: asyncio.Queue = asyncio.Queue()
        self.failed_messages: List[Dict] = []
        self.success_count = 0
        self.fail_count = 0
        self.is_running = False

    async def add_message(self, user_id: int, send_func: Callable, *args, **kwargs):
        """اضافه کردن پیام به صف"""
        await self.queue.put({'user_id': user_id, 'send_func': send_func, 'args': args, 'kwargs': kwargs, 'retry_count': 0})

    async def process_queue(self):
        """پردازش صف پیام\u200cها"""
        self.is_running = True
        while not self.queue.empty() or self.is_running:
            try:
                try:
                    message = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self.queue.empty():
                        break
                    continue
                await self.rate_limiter.wait_if_needed('broadcast')
                try:
                    await message['send_func'](*message['args'], **message['kwargs'])
                    self.success_count += 1
                    logger.debug(f"Message sent to user {message['user_id']}")
                except Exception as e:
                    self.fail_count += 1
                    message['retry_count'] += 1
                    message['error'] = str(e)
                    if message['retry_count'] < BROADCAST_MAX_RETRIES and self._is_retryable_error(e):
                        await asyncio.sleep(2 ** message['retry_count'])
                        await self.queue.put(message)
                        logger.warning(f"Retrying message to user {message['user_id']} (attempt {message['retry_count']})")
                    else:
                        self.failed_messages.append(message)
                        logger.error(f"Failed to send message to user {message['user_id']}: {e}")
            except Exception as e:
                logger.error(f'Error in broadcast queue processing: {e}')
        self.is_running = False

    def _is_retryable_error(self, error: Exception) -> bool:
        """تشخیص خطاهای قابل تلاش مجدد"""
        error_str = str(error).lower()
        retryable_keywords = ['timeout', 'network', 'connection', 'rate']
        return any((keyword in error_str for keyword in retryable_keywords))

    def get_stats(self) -> Dict:
        """دریافت آمار ارسال"""
        return {'success': self.success_count, 'failed': self.fail_count, 'pending': self.queue.qsize(), 'failed_users': [msg['user_id'] for msg in self.failed_messages]}

    async def stop(self):
        """متوقف کردن پردازش صف"""
        self.is_running = False
        timeout = 30
        start_time = time.time()
        while not self.queue.empty() and time.time() - start_time < timeout:
            await asyncio.sleep(1)
        if not self.queue.empty():
            logger.warning(f'Stopped with {self.queue.qsize()} messages in queue')
rate_limiter = RateLimiter()

def rate_limit_decorator(key: str=None, calls: int=TELEGRAM_API_CALLS_PER_SECOND, period: int=TELEGRAM_API_RATE_PERIOD):
    """Decorator برای اعمال rate limiting به توابع"""

    def decorator(func):

        async def wrapper(*args, **kwargs):
            limit_key = key or func.__name__
            limit = RateLimit(calls=calls, period=period)
            await rate_limiter.wait_if_needed(limit_key, limit)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class SimpleRateLimiter:
    """
    Simple Rate Limiter برای استفاده ساده (Inbound User Action Limits)
    برای جلوگیری از اسپم کردن کاربران (مثبت سابمیت کردن پی در پی).
    به صورت Per-User کار می‌کند.
    ✨ Updated for Role-based Limiting (Admin vs User)
    ✨ Thread-safe with per-user locks to prevent race conditions
    """

    def __init__(self, max_requests: int, window: int, admin_max_requests: int = None, admin_window: int = None):
        """
        Args:
            max_requests: حداکثر تعداد درخواست برای کاربران عادی
            window: بازه زمانی (ثانیه) برای کاربران عادی
            admin_max_requests: حداکثر درخواست برای ادمین‌ها (پیش‌فرض: ۲ برابر)
            admin_window: بازه زمانی برای ادمین‌ها (پیش‌فرض: نصف کاربر عادی)
        """
        self.max_requests = max_requests
        self.window = window

        # Default admin limits to be more lenient if not specified
        self.admin_max_requests = admin_max_requests if admin_max_requests is not None else (max_requests * 2)
        self.admin_window = admin_window if admin_window is not None else max(1, window // 2)

        self.requests: Dict[int, deque] = {}
        # Thread-safe lock per user to prevent race conditions
        self._locks: Dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_limits(self, is_admin: bool) -> tuple[int, int]:
        """Returns (max_requests, window) based on role."""
        if is_admin:
            return self.admin_max_requests, self.admin_window
        return self.max_requests, self.window

    async def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific user (thread-safe)."""
        if user_id not in self._locks:
            async with self._global_lock:
                if user_id not in self._locks:
                    self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def _cleanup_loop(self):
        """پردازش پس‌زمینه برای پاک کردن یوزرهای بیکار"""
        while True:
            await asyncio.sleep(self.window * 2)
            current_time = time.time()
            cutoff_time = current_time - max(self.window, self.admin_window)
            empty_keys = []
            for uid, q in self.requests.items():
                while q and q[0] < cutoff_time:
                    q.popleft()
                if not q:
                    empty_keys.append(uid)
            for uid in empty_keys:
                self.requests.pop(uid, None)
                self._locks.pop(uid, None)  # Clean up locks too

    async def is_allowed_async(self, user_id: int, is_admin: bool = False) -> bool:
        """
        Async version - بررسی اینکه آیا کاربر مجاز به درخواست است (thread-safe)
        
        Args:
            user_id: شناسه کاربر
            is_admin: آیا کاربر صلاحت ادمین دارد؟
        
        Returns:
            True اگر مجاز باشد، False در غیر این صورت
        """
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            current_time = time.time()
            max_req, win = self._get_limits(is_admin)

            if user_id not in self.requests:
                self.requests[user_id] = deque()
            user_requests = self.requests[user_id]
            cutoff_time = current_time - win

            while user_requests and user_requests[0] < cutoff_time:
                user_requests.popleft()

            if len(user_requests) >= max_req:
                return False
                
            user_requests.append(current_time)
            return True

    def is_allowed(self, user_id: int, is_admin: bool = False) -> bool:
        """
        Sync version (for backward compatibility) - بررسی اینکه آیا کاربر مجاز به درخواست است
        
        Note: This sync version is NOT thread-safe in async context.
        Use is_allowed_async() in async code for proper locking.
        
        Args:
            user_id: شناسه کاربر
            is_admin: آیا کاربر صلاحت ادمین دارد؟
        
        Returns:
            True اگر مجاز باشد، False در غیر این صورت
        """
        current_time = time.time()
        max_req, win = self._get_limits(is_admin)

        if user_id not in self.requests:
            self.requests[user_id] = deque()
        user_requests = self.requests[user_id]
        cutoff_time = current_time - win

        while user_requests and user_requests[0] < cutoff_time:
            user_requests.popleft()

        if len(user_requests) >= max_req:
            return False
            
        user_requests.append(current_time)
        return True

    async def get_remaining_time_async(self, user_id: int, is_admin: bool = False) -> float:
        """
        Async version - محاسبه زمان باقی‌مانده تا درخواست بعدی (thread-safe)
        """
        user_lock = await self._get_user_lock(user_id)
        async with user_lock:
            return self._calculate_remaining_time(user_id, is_admin)

    def get_remaining_time(self, user_id: int, is_admin: bool = False) -> float:
        """
        Sync version - محاسبه زمان باقی‌مانده تا درخواست بعدی
        
        Args:
            user_id: شناسه کاربر
            is_admin: آیا کاربر صلاحت ادمین دارد؟
        
        Returns:
            زمان باقی‌مانده (ثانیه)
        """
        return self._calculate_remaining_time(user_id, is_admin)

    def _calculate_remaining_time(self, user_id: int, is_admin: bool) -> float:
        """Internal method to calculate remaining time."""
        if user_id not in self.requests:
            return 0
            
        max_req, win = self._get_limits(is_admin)
        user_requests = self.requests[user_id]
        
        if not user_requests:
            return 0
            
        current_time = time.time()
        cutoff_time = current_time - win
        
        while user_requests and user_requests[0] < cutoff_time:
            user_requests.popleft()
            
        if not user_requests:
            return 0
            
        if len(user_requests) < max_req:
            return 0
            
        oldest_request = user_requests[0]
        remaining = win - (current_time - oldest_request)
        return max(0, remaining)