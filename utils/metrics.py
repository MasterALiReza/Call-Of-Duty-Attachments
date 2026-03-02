"""
سیستم Metrics و Monitoring
ردیابی performance و آمار cache/query برای بهینه‌سازی
"""

import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

# from config.constants import SLOW_QUERY_THRESHOLD_SEC

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """آمار کش با محاسبه hit rate"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)
    
    def record_hit(self):
        """ثبت cache hit"""
        with self._lock:
            self.hits += 1
    
    def record_miss(self):
        """ثبت cache miss"""
        with self._lock:
            self.misses += 1
    
    def record_eviction(self):
        """ثبت cache eviction"""
        with self._lock:
            self.evictions += 1
    
    @property
    def total_requests(self) -> int:
        """تعداد کل درخواست‌ها"""
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        """نرخ موفقیت کش (0.0 - 1.0)"""
        total = self.total_requests
        return (self.hits / total) if total > 0 else 0.0
    
    @property
    def hit_rate_percent(self) -> float:
        """نرخموفقیت کش به درصد"""
        return self.hit_rate * 100
    
    def get_stats(self) -> Dict[str, any]:
        """
        دریافت آمار کامل کش
        
        Returns:
            دیکشنری شامل hits, misses, hit_rate, etc.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
            "hit_rate_percent": round(self.hit_rate_percent, 2)
        }
    
    def reset(self):
        """ری‌ست کردن آمار"""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0


@dataclass
class QueryMetrics:
    """آمار query های دیتابیس با ردیابی slow queries"""
    total_queries: int = 0
    slow_queries: int = 0
    total_duration: float = 0.0
    slow_query_log: List[Dict] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _max_slow_log_size: int = 100  # نگه داشتن آخرین 100 slow query
    
    def record_query(self, duration: float, query: str, params: Optional[tuple] = None):
        """
        ثبت یک query و بررسی slow بودن آن
        
        Args:
            duration: مدت زمان اجرا (seconds)
            query: SQL query
            params: پارامترهای query (اختیاری)
        """
        with self._lock:
            self.total_queries += 1
            self.total_duration += duration
            
            # بررسی slow query
            from config.constants import SLOW_QUERY_THRESHOLD_SEC
            if duration > SLOW_QUERY_THRESHOLD_SEC:
                self.slow_queries += 1
                
                # log slow query
                slow_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "duration": round(duration, 4),
                    "query": query[:200],  # فقط 200 کاراکتر اول
                    "params": str(params)[:100] if params else None
                }
                
                self.slow_query_log.append(slow_entry)
                
                # محدود کردن سایز log
                if len(self.slow_query_log) > self._max_slow_log_size:
                    self.slow_query_log = self.slow_query_log[-self._max_slow_log_size:]
                
                # log warning
                logger.warning(
                    f"Slow query detected: {duration:.3f}s - {query[:100]}..."
                )
    
    @property
    def average_duration(self) -> float:
        """میانگین مدت زمان query ها"""
        return (self.total_duration / self.total_queries) if self.total_queries > 0 else 0.0
    
    @property
    def slow_query_rate(self) -> float:
        """نرخ slow queries (0.0 - 1.0)"""
        return (self.slow_queries / self.total_queries) if self.total_queries > 0 else 0.0
    
    def get_stats(self) -> Dict[str, any]:
        """
        دریافت آمار کامل queries
        
        Returns:
            دیکشنری شامل total, slow, average_duration, etc.
        """
        return {
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "slow_query_rate": round(self.slow_query_rate, 4),
            "average_duration_ms": round(self.average_duration * 1000, 2),
            "total_duration_sec": round(self.total_duration, 2),
            "recent_slow_queries": self.slow_query_log[-10:]  # آخرین 10 slow query
        }
    
    def reset(self):
        """ری‌ست کردن آمار"""
        with self._lock:
            self.total_queries = 0
            self.slow_queries = 0
            self.total_duration = 0.0
            self.slow_query_log.clear()


@dataclass
class BroadcastMetrics:
    """آمار پخش زنده (Broadcast)"""
    total_broadcasts: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_duration: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_broadcast(self, sent: int, failed: int, duration: float):
        with self._lock:
            self.total_broadcasts += 1
            self.total_sent += sent
            self.total_failed += failed
            self.total_duration += duration

    @property
    def success_rate(self) -> float:
        total = self.total_sent + self.total_failed
        return (self.total_sent / total) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, any]:
        return {
            "total_broadcasts": self.total_broadcasts,
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "success_rate_percent": round(self.success_rate * 100, 2),
            "average_duration_sec": round(self.total_duration / self.total_broadcasts, 2) if self.total_broadcasts > 0 else 0
        }

    def reset(self):
        with self._lock:
            self.total_broadcasts = 0
            self.total_sent = 0
            self.total_failed = 0
            self.total_duration = 0.0


class MetricsCollector:
    """جمع‌آوری و مدیریت تمام metrics"""
    
    def __init__(self):
        self.cache_metrics = CacheMetrics()
        self.query_metrics = QueryMetrics()
        self.broadcast_metrics = BroadcastMetrics()
        self.handler_response_times: List[float] = []
        self._start_time = datetime.now()
        self._lock = Lock()
    
    @property
    def uptime(self) -> timedelta:
        """مدت زمان اجرای سیستم"""
        return datetime.now() - self._start_time
    
    def get_all_stats(self) -> Dict[str, any]:
        """
        دریافت تمام آمار
        
        Returns:
            دیکشنری شامل cache_stats, query_stats, uptime
        """
        return {
            "uptime_hours": round(self.uptime.total_seconds() / 3600, 2),
            "cache": self.cache_metrics.get_stats(),
            "queries": self.query_metrics.get_stats(),
            "broadcasts": self.broadcast_metrics.get_stats(),
            "avg_handler_response_ms": round(sum(self.handler_response_times) / len(self.handler_response_times) * 1000, 2) if self.handler_response_times else 0
        }
    
    def generate_report(self) -> str:
        """
        ایجاد گزارش متنی از آمار
        
        Returns:
            متن گزارش فرمت شده
        """
        stats = self.get_all_stats()
        
        report = f"""
📊 **Metrics Report**

⏱ **Uptime**: {stats['uptime_hours']:.2f} hours

💾 **Cache Stats**:
  • Hits: {stats['cache']['hits']:,}
  • Misses: {stats['cache']['misses']:,}
  • Hit Rate: {stats['cache']['hit_rate_percent']:.2f}%
  • Evictions: {stats['cache']['evictions']:,}

🗄 **Query Stats**:
  • Total Queries: {stats['queries']['total_queries']:,}
  • Slow Queries: {stats['queries']['slow_queries']:,}
  • Slow Rate: {stats['queries']['slow_query_rate']*100:.2f}%
  • Avg Duration: {stats['queries']['average_duration_ms']:.2f}ms
"""
        return report.strip()
    
    def reset_all(self):
        """ری‌ست کردن تمام آمار"""
        self.cache_metrics.reset()
        self.query_metrics.reset()
        self._start_time = datetime.now()


# Global metrics instance
_metrics_instance: Optional[MetricsCollector] = None
_instance_lock = Lock()


def get_metrics() -> MetricsCollector:
    """
    دریافت singleton instance از MetricsCollector
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_instance
    
    if _metrics_instance is None:
        with _instance_lock:
            if _metrics_instance is None:
                _metrics_instance = MetricsCollector()
    
    return _metrics_instance


# ====================================
# Context Managers برای اندازه‌گیری
# ====================================

class measure_query_time:
    """
    Context manager برای اندازه‌گیری زمان query
    
    Usage:
        with measure_query_time(query_text):
            cursor.execute(query)
    """
    
    def __init__(self, query: str, params: Optional[tuple] = None):
        self.query = query
        self.params = params
        self.start_time = None
        self.metrics = get_metrics()
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.metrics.query_metrics.record_query(duration, self.query, self.params)
        return False


def log_cache_access(hit: bool):
    """
    Helper برای log کردن cache access
    
    Args:
        hit: True اگر cache hit، False اگر cache miss
    """
    metrics = get_metrics()
    if hit:
        metrics.cache_metrics.record_hit()
    else:
        metrics.cache_metrics.record_miss()
