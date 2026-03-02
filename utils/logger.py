"""
سیستم Logging حرفه\u200cای و جامع
این ماژول یک سیستم لاگینگ پیشرفته با قابلیت\u200cهای زیر فراهم می\u200cکند:
- Log Rotation خودکار
- سطوح مختلف logging
- فایل\u200cهای لاگ جداگانه برای هر بخش
- Context logging (user_id, request_id)
- Performance tracking
- Thread-safe operations
- Structured logging (JSON format option)
"""
import logging
import logging.handlers
import os
import sys
import json
import traceback
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from functools import wraps
import uuid
import time
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)
DETAILED_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-25s | [%(filename)s:%(lineno)d] | %(funcName)s() | %(message)s'
SIMPLE_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
JSON_FORMAT = '%(message)s'
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
COLORS = {'DEBUG': '\x1b[36m', 'INFO': '\x1b[32m', 'WARNING': '\x1b[33m', 'ERROR': '\x1b[31m', 'CRITICAL': '\x1b[1;31m', 'RESET': '\x1b[0m'}

class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Windows-safe RotatingFileHandler that closes the file before rotating."""

    def doRollover(self):
        """Close the stream before rotating to avoid WinError 32 on Windows."""
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()


class RequestContext:
    """مدیریت context برای هر request"""
    _context = threading.local()

    @classmethod
    def set_context(cls, **kwargs):
        """تنظیم context برای thread جاری"""
        if not hasattr(cls._context, 'data'):
            cls._context.data = {}
        cls._context.data.update(kwargs)

    @classmethod
    def get_context(cls) -> Dict:
        """دریافت context فعلی"""
        if not hasattr(cls._context, 'data'):
            return {}
        return cls._context.data.copy()

    @classmethod
    def clear_context(cls):
        """پاک کردن context"""
        if hasattr(cls._context, 'data'):
            cls._context.data.clear()

    @classmethod
    def get_request_id(cls) -> str:
        """دریافت یا ایجاد request_id"""
        context = cls.get_context()
        if 'request_id' not in context:
            context['request_id'] = str(uuid.uuid4())[:8]
            cls.set_context(**context)
        return context['request_id']

class ContextFilter(logging.Filter):
    """اضافه کردن context info به log records"""

    def filter(self, record):
        context = RequestContext.get_context()
        record.request_id = context.get('request_id', 'N/A')
        record.user_id = context.get('user_id', 'N/A')
        record.username = context.get('username', 'N/A')
        return True

class JSONFormatter(logging.Formatter):
    """فرمت کردن لاگ\u200cها به صورت JSON"""

    def format(self, record):
        log_data = {'timestamp': datetime.utcnow().isoformat(), 'level': record.levelname, 'logger': record.name, 'module': record.module, 'function': record.funcName, 'line': record.lineno, 'message': record.getMessage(), 'request_id': getattr(record, 'request_id', 'N/A'), 'user_id': getattr(record, 'user_id', 'N/A')}
        if record.exc_info:
            log_data['exception'] = {'type': record.exc_info[0].__name__, 'message': str(record.exc_info[1]), 'traceback': traceback.format_exception(*record.exc_info)}
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        return json.dumps(log_data, ensure_ascii=False, default=str)

class ColoredFormatter(logging.Formatter):
    """فرمت کردن لاگ\u200cهای console با رنگ"""

    def format(self, record):
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"
        result = super().format(record)
        record.levelname = levelname
        return result

class LoggerManager:
    """مدیریت مرکزی تمام loggers"""
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.loggers = {}
            self._setup_root_logger()
            LoggerManager._initialized = True

    def _setup_root_logger(self):
        """راه\u200cاندازی root logger"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        context_filter = ContextFilter()
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)
        main_log = LOG_DIR / 'app.log'
        main_handler = SafeRotatingFileHandler(main_log, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(DETAILED_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
        main_handler.setFormatter(main_formatter)
        main_handler.addFilter(context_filter)
        root_logger.addHandler(main_handler)
        error_log = LOG_DIR / 'errors.log'
        error_handler = SafeRotatingFileHandler(error_log, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | [%(filename)s:%(lineno)d]\nFunction: %(funcName)s()\nMessage: %(message)s\nRequest ID: %(request_id)s | User ID: %(user_id)s\n%(separator)s\n', datefmt='%Y-%m-%d %H:%M:%S')
        error_handler.setFormatter(error_formatter)
        error_handler.addFilter(context_filter)
        error_handler.addFilter(self._add_separator_filter())
        root_logger.addHandler(error_handler)
        logging.info(f'Logging system initialized successfully | Directory: {LOG_DIR.absolute()}')

    def _add_separator_filter(self):
        """فیلتر برای اضافه کردن خط جداکننده"""

        class SeparatorFilter(logging.Filter):

            def filter(self, record):
                record.separator = '=' * 100
                return True
        return SeparatorFilter()

    def get_logger(self, name: str, log_file: Optional[str]=None, level: int=logging.DEBUG, use_json: bool=False) -> logging.Logger:
        """
        دریافت یا ایجاد logger با تنظیمات مشخص
        
        Args:
            name: نام logger
            log_file: نام فایل لاگ (اختیاری) - اگر مشخص شود فایل جداگانه می\u200cسازد
            level: سطح logging
            use_json: استفاده از فرمت JSON
        
        Returns:
            logger instance
        """
        if name in self.loggers:
            return self.loggers[name]
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if log_file:
            log_path = LOG_DIR / log_file
            file_handler = SafeRotatingFileHandler(log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
            file_handler.setLevel(level)
            if use_json:
                formatter = JSONFormatter()
            else:
                formatter = logging.Formatter(DETAILED_FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            file_handler.addFilter(ContextFilter())
            logger.addHandler(file_handler)
        self.loggers[name] = logger
        return logger
_logger_manager = LoggerManager()

def get_logger(name: str, log_file: Optional[str]=None, level: int=logging.DEBUG, use_json: bool=False) -> logging.Logger:
    """
    دریافت logger با تنظیمات مشخص
    
    Examples:
        >>> logger = get_logger('database', 'database.log')
        >>> logger.info('Database operation completed')
    """
    return _logger_manager.get_logger(name, log_file, level, use_json)

def log_execution(logger: Optional[logging.Logger]=None, level: int=logging.DEBUG):
    """
    Decorator برای لاگ کردن اجرای تابع با اندازه\u200cگیری زمان
    
    Args:
        logger: logger مورد استفاده (اگر None باشد از logging.getLogger استفاده می\u200cشود)
        level: سطح لاگ
    
    Example:
        >>> @log_execution(logger, logging.INFO)
        >>> async def my_function(param1, param2):
        >>>     ...
    """

    def decorator(func: Callable):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            func_name = func.__qualname__
            start_time = time.time()
            logger.log(level, f'[START] Executing {func_name}')
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.log(level, f'[SUCCESS] {func_name} completed | Time: {elapsed:.3f}s')
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f'[ERROR] {func_name} failed | Time: {elapsed:.3f}s | Error: {type(e).__name__}: {str(e)}', exc_info=True)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            func_name = func.__qualname__
            start_time = time.time()
            logger.log(level, f'[START] Executing {func_name}')
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.log(level, f'[SUCCESS] {func_name} completed | Time: {elapsed:.3f}s')
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f'[ERROR] {func_name} failed | Time: {elapsed:.3f}s | Error: {type(e).__name__}: {str(e)}', exc_info=True)
                raise
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

def log_db_operation(operation_name: str=None):
    """
    Decorator مخصوص عملیات database
    
    Example:
        >>> @log_db_operation("add_weapon")
        >>> def add_weapon(self, category, weapon_name):
        >>>     ...
    """

    def decorator(func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):
            db_logger = get_logger('database', 'database.log')
            op_name = operation_name or func.__name__
            params_str = f'args={(args[1:3] if len(args) > 1 else args)}, kwargs={kwargs}'
            db_logger.info(f'[DB] Operation: {op_name} | {params_str}')
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                db_logger.info(f'[DB-SUCCESS] {op_name} | Time: {elapsed:.3f}s | Result: {result}')
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                db_logger.error(f'[DB-ERROR] {op_name} | Time: {elapsed:.3f}s | Error: {type(e).__name__}: {str(e)}', exc_info=True)
                raise
        return wrapper
    return decorator

def log_user_action(action_name: str=None):
    """
    Decorator برای لاگ کردن اکشن\u200cهای کاربر
    
    Example:
        >>> @log_user_action("view_weapon")
        >>> async def show_weapons(self, update, context):
        >>>     ...
    """

    def decorator(func: Callable):

        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_logger = get_logger('user_actions', 'user.log')
            action = action_name or func.__name__
            update = None
            for arg in args:
                if hasattr(arg, 'effective_user'):
                    update = arg
                    break
            if update and update.effective_user:
                user_id = update.effective_user.id
                username = update.effective_user.username or update.effective_user.first_name
                RequestContext.set_context(user_id=user_id, username=username)
                user_logger.info(f'[USER] Action: {action} | User: {username} ({user_id})')
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                user_logger.error(f'[USER-ERROR] Action failed: {action} | Error: {str(e)}')
                raise
            finally:
                RequestContext.clear_context()
        return wrapper
    return decorator

def log_admin_action(action_name: str=None):
    """
    Decorator برای لاگ کردن اکشن\u200cهای ادمین
    
    Example:
        >>> @log_admin_action("delete_attachment")
        >>> async def delete_attachment(self, update, context):
        >>>     ...
    """

    def decorator(func: Callable):

        @wraps(func)
        async def wrapper(*args, **kwargs):
            admin_logger = get_logger('admin_actions', 'admin.log')
            action = action_name or func.__name__
            update = None
            for arg in args:
                if hasattr(arg, 'effective_user'):
                    update = arg
                    break
            if update and update.effective_user:
                admin_id = update.effective_user.id
                admin_name = update.effective_user.username or update.effective_user.first_name
                RequestContext.set_context(user_id=admin_id, username=admin_name)
                admin_logger.warning(f'[ADMIN] Action: {action} | Admin: {admin_name} ({admin_id})')
            try:
                result = await func(*args, **kwargs)
                admin_logger.warning(f'[ADMIN-SUCCESS] {action}')
                return result
            except Exception as e:
                admin_logger.error(f'[ADMIN-ERROR] Action failed: {action} | Error: {str(e)}', exc_info=True)
                raise
            finally:
                RequestContext.clear_context()
        return wrapper
    return decorator

def log_exception(logger: logging.Logger, exc: Exception, context: str=''):
    """
    لاگ کردن exception با جزئیات کامل
    
    Args:
        logger: logger مورد استفاده
        exc: exception
        context: توضیحات اضافی
    """
    logger.error(f"{('[' + context + '] ' if context else '')}Exception: {type(exc).__name__}: {str(exc)}", exc_info=True, extra={'extra_data': {'context': context}})

def log_performance(logger: logging.Logger, operation: str, duration: float, threshold: float=1.0):
    """
    لاگ کردن performance با هشدار اگر از threshold بیشتر شود
    
    Args:
        logger: logger مورد استفاده
        operation: نام عملیات
        duration: مدت زمان به ثانیه
        threshold: آستانه هشدار (پیش\u200cفرض 1 ثانیه)
    """
    if duration > threshold:
        logger.warning(f'[SLOW] Operation: {operation} | Time: {duration:.3f}s (threshold: {threshold}s)')
    else:
        logger.debug(f'[FAST] Operation: {operation} | Time: {duration:.3f}s')

def setup_logging(log_level: str='INFO') -> logging.Logger:
    """
    راه\u200cاندازی سیستم logging (برای backward compatibility)
    
    Args:
        log_level: سطح logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        root logger
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(level)
    return logging.getLogger()

class LogStats:
    """آمارگیری از لاگ\u200cها"""
    _stats = {'DEBUG': 0, 'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0}
    _lock = threading.Lock()

    @classmethod
    def increment(cls, level: str):
        """افزایش شمارنده یک سطح"""
        with cls._lock:
            if level in cls._stats:
                cls._stats[level] += 1

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """دریافت آمار"""
        with cls._lock:
            return cls._stats.copy()

    @classmethod
    def reset(cls):
        """ریست کردن آمار"""
        with cls._lock:
            for key in cls._stats:
                cls._stats[key] = 0
database_logger = get_logger('database', 'database.log', logging.DEBUG)
admin_logger = get_logger('admin', 'admin.log', logging.INFO)
user_logger = get_logger('user', 'user.log', logging.INFO)
error_logger = get_logger('errors', 'errors.log', logging.ERROR)
performance_logger = get_logger('performance', 'performance.log', logging.DEBUG)
__all__ = ['get_logger', 'log_execution', 'log_db_operation', 'log_user_action', 'log_admin_action', 'log_exception', 'log_performance', 'setup_logging', 'RequestContext', 'LogStats', 'database_logger', 'admin_logger', 'user_logger', 'error_logger', 'performance_logger']