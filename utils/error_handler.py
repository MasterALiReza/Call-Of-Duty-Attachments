"""
سیستم مدیریت خطا و logging مرکزی
"""
import logging
import traceback
from typing import Optional, Any
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import os
from utils.logger import setup_logging as core_setup_logging
from core.context import CustomContext

def setup_logging(log_file: str='bot.log', level: str='INFO'):
    """راه\u200cاندازی سیستم logging (Delegate به utils.logger.setup_logging)"""
    return core_setup_logging(level)

class ErrorHandler:
    """کلاس مرکزی برای مدیریت خطاها"""

    def __init__(self, logger: Optional[logging.Logger]=None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_count = {}

    def log_error(self, error: Exception, context: str='', user_id: Optional[int]=None) -> tuple[str, str]:
        """ثبت خطا با جزئیات کامل
        
        Args:
            error: Exception object to log
            context: Context string describing where the error occurred
            user_id: Optional user ID (will be masked for privacy)
            
        Returns:
            Tuple of (error_type, error_message)
        """
        error_type = type(error).__name__
        error_msg = str(error)
        if error_type not in self.error_count:
            self.error_count[error_type] = 0
        self.error_count[error_type] += 1
        log_msg = f'[{context}] {error_type}: {error_msg}'
        if user_id:
            masked_id = str(user_id)[:-4] + '****' if len(str(user_id)) > 4 else '****'
            log_msg += f' | User: {masked_id}'
        if error_type not in ['BadRequest', 'Forbidden', 'NetworkError']:
            self.logger.error(log_msg)
            self.logger.error(f'Traceback:\n{traceback.format_exc()}')
        else:
            self.logger.warning(log_msg)
        return (error_type, error_msg)

    async def handle_telegram_error(self, update: Update, context: CustomContext, error: Exception) -> None:
        """مدیریت خطاهای تلگرام
        
        Args:
            update: Telegram Update object
            context: Telegram context
            error: Exception that occurred
        """
        user_id = update.effective_user.id if update and update.effective_user else None
        error_type, error_msg = self.log_error(error, 'Telegram', user_id)
        user_message = self._get_user_friendly_message(error_type, error_msg)
        try:
            if update:
                if update.callback_query:
                    await update.callback_query.answer(user_message, show_alert=True if len(user_message) < 200 else False)
                elif update.message:
                    await update.message.reply_text(user_message)
        except Exception as e:
            self.logger.error(f'خطا در ارسال پیام خطا به کاربر: {e}')

    def _get_user_friendly_message(self, error_type: str, error_msg: str) -> str:
        """تبدیل خطا به پیام کاربرپسند"""
        messages = {'BadRequest': '⚠️ درخواست نامعتبر. لطفاً دوباره تلاش کنید.', 'Forbidden': '🚫 دسترسی محدود شده است.', 'NetworkError': '🌐 خطای اتصال. لطفاً اتصال اینترنت خود را بررسی کنید.', 'TimedOut': '⏱️ زمان درخواست به پایان رسید. لطفاً دوباره تلاش کنید.', 'FileNotFoundError': '📂 فایل مورد نظر یافت نشد.', 'ValueError': '❌ مقدار وارد شده نامعتبر است.', 'KeyError': '🔑 داده مورد نظر یافت نشد.', 'JSONDecodeError': '📊 خطا در خواندن داده\u200cها.'}
        if error_type in messages:
            return messages[error_type]
        if 'rate limit' in error_msg.lower():
            return '⏳ تعداد درخواست\u200cها بیش از حد مجاز. لطفاً کمی صبر کنید.'
        elif 'not found' in error_msg.lower():
            return '❌ مورد درخواستی یافت نشد.'
        elif 'permission' in error_msg.lower():
            return '🔒 شما دسترسی لازم را ندارید.'
        else:
            return '⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.'

    def get_error_stats(self) -> dict:
        """دریافت آمار خطاها"""
        return {'total_errors': sum(self.error_count.values()), 'error_types': self.error_count, 'most_common': max(self.error_count, key=self.error_count.get) if self.error_count else None}

def safe_execute(func):
    """Decorator برای اجرای ایمن توابع با error handling"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(func.__module__)
            logger.error(f'خطا در {func.__name__}: {e}')
            logger.error(traceback.format_exc())
            return None

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(func.__module__)
            logger.error(f'خطا در {func.__name__}: {e}')
            logger.error(traceback.format_exc())
            return None
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def log_function_call(func):
    """Decorator برای log کردن فراخوانی توابع"""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f'فراخوانی {func.__name__}')
        start_time = datetime.now()
        try:
            result = await func(*args, **kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f'{func.__name__} کامل شد در {elapsed:.2f} ثانیه')
            return result
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f'{func.__name__} با خطا مواجه شد بعد از {elapsed:.2f} ثانیه: {e}')
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f'فراخوانی {func.__name__}')
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.debug(f'{func.__name__} کامل شد در {elapsed:.2f} ثانیه')
            return result
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f'{func.__name__} با خطا مواجه شد بعد از {elapsed:.2f} ثانیه: {e}')
            raise
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
error_handler = ErrorHandler()