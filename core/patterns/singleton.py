"""
Singleton Pattern Implementation

این ماژول یک thread-safe singleton pattern ارائه می‌دهد که می‌تواند 
در تمام کلاس‌های پروژه برای یکسان‌سازی استفاده شود.
"""

import threading
from typing import TypeVar, Generic, Optional, Any

T = TypeVar('T')


class SingletonMixin:
    """
    Thread-safe Singleton Pattern Mixin
    
    استفاده:
        class MyService(SingletonMixin):
            def __init__(self, config):
                self.config = config
        
        # دریافت instance
        service = MyService.get_instance(config)
        
        # برای تست‌ها - ریست کردن
        MyService.reset_instance()
    """
    
    _instance: Optional['SingletonMixin'] = None
    _lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get_instance(cls: type[T], *args: Any, **kwargs: Any) -> T:
        """
        دریافت singleton instance
        
        Args:
            *args: آرگومان‌های سازنده
            **kwargs: keyword آرگومان‌های سازنده
            
        Returns:
            singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = cls(*args, **kwargs)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        ریست کردن instance - فقط برای تست‌ها
        
        توجه: در production استفاده نشود
        """
        with cls._lock:
            cls._instance = None
    
    @classmethod
    def has_instance(cls) -> bool:
        """بررسی اینکه آیا instance ایجاد شده است"""
        return cls._instance is not None


class SingletonMeta(type):
    """
    Metaclass برای Singleton Pattern
    
    استفاده:
        class MyService(metaclass=SingletonMeta):
            def __init__(self, config):
                self.config = config
        
        # هر بار که MyService() صدا زده شود، همان instance برمی‌گردد
        service1 = MyService(config)
        service2 = MyService()  # همان instance
        assert service1 is service2  # True
    """
    
    _instances: dict = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
    
    @classmethod
    def reset_instance(mcs, cls: type) -> None:
        """ریست کردن instance برای یک کلاس خاص"""
        with mcs._lock:
            if cls in mcs._instances:
                del mcs._instances[cls]


def singleton(cls: type[T]) -> type[T]:
    """
    Decorator برای تبدیل کلاس به Singleton
    
    استفاده:
        @singleton
        class MyService:
            def __init__(self, config):
                self.config = config
        
        # MyService() همیشه همان instance را برمی‌گرداند
        service = MyService(config)
    """
    instances: dict = {}
    lock = threading.Lock()
    
    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    def reset():
        """ریست کردن instance"""
        with lock:
            instances.clear()
    
    # اضافه کردن متدهای جدید به کلاس
    get_instance.reset = reset
    get_instance.__name__ = cls.__name__
    get_instance.__doc__ = cls.__doc__
    
    return get_instance
