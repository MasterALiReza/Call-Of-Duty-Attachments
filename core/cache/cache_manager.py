"""
Redis-backed Cache Management System.
Provides a caching decorator and manager to offload expensive static DB reads.
"""
import os
import time
import json
import asyncio
from typing import Any, Optional, Dict, Callable
from functools import wraps
import threading
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
from utils.logger import get_logger
from utils.metrics import get_metrics, log_cache_access
logger = get_logger('cache', 'cache.log')

# Configuration from environment variables
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
MAX_CACHE_SIZE = int(os.getenv('MAX_CACHE_SIZE', '10000'))  # Maximum in-memory cache entries
DEFAULT_CACHE_TTL = int(os.getenv('DEFAULT_CACHE_TTL', '300'))

class CacheEntry:
    """In-memory cache entry with TTL (Fallback Mode)"""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expiry = time.time() + (int(ttl) if isinstance(ttl, str) else ttl)
        self.last_access = time.time()  # For LRU tracking

    def is_expired(self) -> bool:
        return time.time() > self.expiry
    
    def touch(self):
        """Update last access time for LRU."""
        self.last_access = time.time()

class RedisCacheManager:
    """
    Manages Cache natively via Redis, but falls back to in-memory dictionaries
    if Redis is unavailable or unconfigured.
    
    Features:
    - LRU eviction when max_size is reached
    - TTL-based expiration
    - Thread-safe operations
    """

    def __init__(self, max_size: int = None):
        self._metrics = get_metrics()
        self.use_redis = REDIS_AVAILABLE
        self.redis_client = None
        self.max_size = max_size or MAX_CACHE_SIZE
        
        if self.use_redis:
            try:
                self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                logger.info(f'Initialized CacheManager with Redis: {REDIS_URL}')
            except Exception as e:
                logger.error(f'Failed to connect to Redis, falling back to memory: {e}')
                self.use_redis = False
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        logger.info(f'CacheManager initialized with max_size={self.max_size}')

    def _evict_lru(self):
        """
        Evict least recently used entries when cache exceeds max_size.
        Must be called with lock held.
        """
        if len(self._cache) < self.max_size:
            return
        
        # Remove expired entries first
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
            self._metrics.cache_metrics.record_eviction()
        
        # If still over max_size, remove LRU entries
        while len(self._cache) >= self.max_size:
            # Find LRU entry
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
            del self._cache[lru_key]
            self._metrics.cache_metrics.record_eviction()
            logger.debug(f'LRU evicted: {lru_key}')

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (async)"""
        if self.use_redis and self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    log_cache_access(hit=True)
                    logger.debug(f'Redis Cache HIT: {key}')
                    import ast
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        return ast.literal_eval(data)
            except Exception as e:
                logger.debug(f'Redis get error: {e}')
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.touch()  # Update LRU timestamp
                    log_cache_access(hit=True)
                    logger.debug(f'Mem Cache HIT: {key}')
                    return entry.value
                else:
                    del self._cache[key]
                    self._metrics.cache_metrics.record_eviction()
        log_cache_access(hit=False)
        logger.debug(f'Cache MISS: {key}')
        return None

    def get_sync(self, key: str) -> Optional[Any]:
        """Synchronous wrapper for get (used by legacy decorators)"""
        if self.use_redis:
            try:
                loop = asyncio.get_running_loop()
                pass
            except RuntimeError:
                pass
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.touch()  # Update LRU timestamp
                    log_cache_access(hit=True)
                    return entry.value
                else:
                    del self._cache[key]
        log_cache_access(hit=False)
        return None

    async def set(self, key: str, value: Any, ttl: int=DEFAULT_CACHE_TTL):
        """Set value in cache (async)"""
        import copy
        # Perform deepcopy to prevent source pollution
        cache_value = copy.deepcopy(value) if isinstance(value, (dict, list)) else value
        
        if self.use_redis and self.redis_client:
            try:
                data = json.dumps(cache_value) if isinstance(cache_value, (dict, list)) else str(cache_value)
                await self.redis_client.setex(key, ttl, data)
                logger.debug(f'Redis Cache SET: {key} (TTL={ttl}s)')
                return
            except Exception as e:
                logger.debug(f'Redis set error: {e}')
        with self._lock:
            self._evict_lru()  # Ensure space for new entry
            self._cache[key] = CacheEntry(cache_value, ttl)
            logger.debug(f'Mem Cache SET: {key} (TTL={ttl}s)')

    def set_sync(self, key: str, value: Any, ttl: int=DEFAULT_CACHE_TTL):
        import copy
        cache_value = copy.deepcopy(value) if isinstance(value, (dict, list)) else value
        with self._lock:
            self._evict_lru()  # Ensure space for new entry
            self._cache[key] = CacheEntry(cache_value, ttl)

    async def delete(self, key: str):
        if self.use_redis and self.redis_client:
            await self.redis_client.delete(key)
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache keys matching a pattern.
        
        Args:
            pattern: Pattern to match (substring match)
            
        Returns:
            Number of keys invalidated
        """
        count = 0
        
        # Redis invalidation
        if self.use_redis and self.redis_client:
            try:
                keys_to_delete = []
                async for key in self.redis_client.scan_iter(f'*{pattern}*'):
                    keys_to_delete.append(key)
                
                if keys_to_delete:
                    count = await self.redis_client.delete(*keys_to_delete)
                    logger.info(f'Redis invalidated {count} keys matching: {pattern}')
            except Exception as e:
                logger.warning(f'Redis pattern invalidation error: {e}')
        
        # In-memory invalidation
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
        
        if count > 0:
            logger.info(f'Cache invalidated {count} keys matching: {pattern}')
        
        return count

    def invalidate_pattern_sync(self, pattern: str) -> int:
        """
        Synchronous pattern invalidation.
        
        Args:
            pattern: Pattern to match
            
        Returns:
            Number of keys invalidated
        """
        count = 0
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1
        
        if count > 0:
            logger.debug(f'Sync invalidated {count} keys matching: {pattern}')
        
        return count

    def clear(self):
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self):
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]

async def invalidate_attachment_caches(category: str, weapon: str):
    """Invalidate all caches related to a specific weapon and general attachment lists."""
    cache = get_cache()
    # patterns to invalidate
    patterns = [
        f"_{category}_{weapon}",
        "get_all_attachments",
        "get_weapon_attachments",
        "get_top_attachments",
        "category_counts"
    ]
    for pattern in patterns:
        await cache.invalidate_pattern(pattern)
_cache = RedisCacheManager()

def get_cache() -> RedisCacheManager:
    return _cache

async def warm_cache(data_loader: Callable, keys: list, ttl: int = DEFAULT_CACHE_TTL) -> int:
    """
    Pre-populate cache with frequently accessed data.
    
    Args:
        data_loader: Async function to load data for a key
        keys: List of cache keys to warm
        ttl: TTL for cached entries
        
    Returns:
        Number of entries successfully cached
    """
    cache = get_cache()
    count = 0
    
    for key in keys:
        try:
            data = await data_loader(key)
            if data:
                await cache.set(key, data, ttl)
                count += 1
        except Exception as e:
            logger.warning(f'Cache warming failed for {key}: {e}')
    
    logger.info(f'Cache warmed {count}/{len(keys)} entries')
    return count

def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dict with cache stats (size, hit rate, etc.)
    """
    cache = get_cache()
    with cache._lock:
        return {
            'size': len(cache._cache),
            'max_size': cache.max_size,
            'use_redis': cache.use_redis,
            'utilization': len(cache._cache) / cache.max_size if cache.max_size > 0 else 0
        }

def cached(ttl_or_key=300, key_func: Optional[Callable]=None, ttl: Optional[int]=None):
    """
    Decorator for caching function outputs.
    Fully backwards compatible with synchronous code by utilizing the memory fallback.
    """
    if ttl is not None:
        cache_ttl = ttl
        cache_key_prefix = None
    elif isinstance(ttl_or_key, str):
        cache_key_prefix = ttl_or_key
        cache_ttl = 300
    else:
        cache_key_prefix = None
        cache_ttl = ttl_or_key if isinstance(ttl_or_key, int) else 300

    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if cache_key_prefix:
                cache_key = cache_key_prefix
            elif key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__qualname__}:{'_'.join((str(a) for a in args))}:{'_'.join((f'{k}={v}' for k, v in sorted(kwargs.items())))}"
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                # Return deepcopy for mutable types to prevent cache pollution
                if isinstance(cached_value, (list, dict)):
                    import copy
                    return copy.deepcopy(cached_value)
                return cached_value
            result = await func(*args, **kwargs)
            # Perform deepcopy before storing to ensure purity
            import copy
            await _cache.set(cache_key, result, cache_ttl)
            # Return a copy to the first caller as well
            if isinstance(result, (list, dict)):
                return copy.deepcopy(result)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if cache_key_prefix:
                cache_key = cache_key_prefix
            elif key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__qualname__}:{'_'.join((str(a) for a in args))}:{'_'.join((f'{k}={v}' for k, v in sorted(kwargs.items())))}"
            cached_value = _cache.get_sync(cache_key)
            if cached_value is not None:
                # Return deepcopy for mutable types to prevent cache pollution
                if isinstance(cached_value, (list, dict)):
                    import copy
                    return copy.deepcopy(cached_value)
                return cached_value
            result = func(*args, **kwargs)
            import copy
            _cache.set_sync(cache_key, result, cache_ttl)
            if isinstance(result, (list, dict)):
                return copy.deepcopy(result)
            return result
        wrapper = async_wrapper if is_async else sync_wrapper
        wrapper.cache_clear = lambda: _cache.invalidate_pattern_sync(func.__qualname__)
        return wrapper
    return decorator

def invalidate_cache_on_write(patterns: list):
    """Decorator to invalidate caches after write operations"""

    def decorator(func):
        is_async = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if result:
                for pattern in patterns:
                    await _cache.invalidate_pattern(pattern)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if result:
                for pattern in patterns:
                    _cache.invalidate_pattern_sync(pattern)
            return result
        return async_wrapper if is_async else sync_wrapper
    return decorator

async def cache_cleanup_task():
    """Background task for cleaning up expired memory cache entries"""
    while True:
        await asyncio.sleep(60)
        _cache.cleanup_expired()