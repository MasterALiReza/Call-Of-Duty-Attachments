"""
موتور جستجوی Fuzzy برای تحمل تایپوها و مطابقت هوشمند
"""
from fuzzywuzzy import fuzz, process
from typing import List, Tuple, Dict, Optional
import threading
import time
from utils.logger import get_logger
logger = get_logger('search.fuzzy', 'user.log')

class FuzzySearchEngine:
    """موتور جستجوی Fuzzy با cache و بهینه\u200cسازی"""

    def __init__(self, db):
        self.db = db
        self._cache = {'weapons': [], 'attachments': [], 'codes': []}
        self._cache_lock = threading.Lock()
        self._cache_time = 0
        self._cache_ttl = 3600
        logger.info('FuzzySearchEngine initialized')

    def _should_rebuild_cache(self) -> bool:
        """بررسی نیاز به rebuild کردن cache"""
        if not self._cache['weapons']:
            return True
        if time.time() - self._cache_time > self._cache_ttl:
            return True
        return False

    async def build_search_index(self, force: bool=False):
        """ساخت index برای جستجوی fuzzy
        
        Args:
            force: اجبار به rebuild حتی اگر cache معتبر باشد
        """
        if not force and (not self._should_rebuild_cache()):
            logger.debug('Using cached search index')
            return
        logger.info('Building fuzzy search index...')
        start_time = time.time()
        with self._cache_lock:
            try:
                async with self.db.get_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute('SELECT DISTINCT name FROM weapons ORDER BY name')
                        weapons = await cursor.fetchall()
                        self._cache['weapons'] = [w['name'] for w in weapons]
                        await cursor.execute('SELECT DISTINCT name FROM attachments ORDER BY name')
                        attachments = await cursor.fetchall()
                        self._cache['attachments'] = [a['name'] for a in attachments]
                        await cursor.execute('SELECT DISTINCT code FROM attachments ORDER BY code')
                        codes = await cursor.fetchall()
                        self._cache['codes'] = [c['code'] for c in codes]
                self._cache_time = time.time()
                elapsed = time.time() - start_time
                logger.info(f"Fuzzy index built in {elapsed:.3f}s: {len(self._cache['weapons'])} weapons, {len(self._cache['attachments'])} attachments, {len(self._cache['codes'])} codes")
            except Exception as e:
                logger.error(f'Error building fuzzy index: {e}')
                raise

    async def fuzzy_match_weapons(self, query: str, threshold: int=70, limit: int=5) -> List[Tuple[str, int]]:
        """پیدا کردن سلاح\u200cهای مشابه با query
        
        Args:
            query: متن جستجو
            threshold: حداقل امتیاز مطابقت (0-100)
            limit: حداکثر تعداد نتایج
            
        Returns:
            لیست (نام سلاح, امتیاز)
        """
        if not self._cache['weapons']:
            await self.build_search_index()
        if not query or len(query) < 2:
            return []
        try:
            matches = process.extract(query, self._cache['weapons'], scorer=fuzz.ratio, limit=limit)
            results = [(name, score) for name, score in matches if score >= threshold]
            logger.debug(f"Fuzzy weapon matches for '{query}': {len(results)} results")
            return results
        except Exception as e:
            logger.error(f'Error in fuzzy weapon matching: {e}')
            return []

    async def fuzzy_match_attachments(self, query: str, threshold: int=70, limit: int=10) -> List[Tuple[str, int]]:
        """پیدا کردن اتچمنت\u200cهای مشابه با query
        
        Args:
            query: متن جستجو
            threshold: حداقل امتیاز مطابقت (0-100)
            limit: حداکثر تعداد نتایج
            
        Returns:
            لیست (نام اتچمنت, امتیاز)
        """
        if not self._cache['attachments']:
            await self.build_search_index()
        if not query or len(query) < 2:
            return []
        try:
            matches = process.extract(query, self._cache['attachments'], scorer=fuzz.ratio, limit=limit)
            results = [(name, score) for name, score in matches if score >= threshold]
            logger.debug(f"Fuzzy attachment matches for '{query}': {len(results)} results")
            return results
        except Exception as e:
            logger.error(f'Error in fuzzy attachment matching: {e}')
            return []

    async def fuzzy_match_codes(self, query: str, threshold: int=80, limit: int=5) -> List[Tuple[str, int]]:
        """پیدا کردن کدهای مشابه با query
        
        Args:
            query: متن جستجو
            threshold: حداقل امتیاز (برای کدها باید بالاتر باشد)
            limit: حداکثر تعداد نتایج
            
        Returns:
            لیست (کد, امتیاز)
        """
        if not self._cache['codes']:
            await self.build_search_index()
        if not query or len(query) < 2:
            return []
        try:
            matches = process.extract(query, self._cache['codes'], scorer=fuzz.ratio, limit=limit)
            results = [(code, score) for code, score in matches if score >= threshold]
            logger.debug(f"Fuzzy code matches for '{query}': {len(results)} results")
            return results
        except Exception as e:
            logger.error(f'Error in fuzzy code matching: {e}')
            return []

    def fuzzy_match(self, query: str, threshold: int=70) -> Dict[str, List[Tuple[str, int]]]:
        """جستجوی جامع در همه موارد
        
        Args:
            query: متن جستجو
            threshold: حداقل امتیاز مطابقت
            
        Returns:
            دیکشنری {'weapons': [...], 'attachments': [...], 'codes': [...]}
        """
        # Ensure cache is built (sync wrapper for async build_search_index is not possible, so assume built)
        # In practice, AttachmentRepository will ensure it is built.
        return {
            'weapons': process.extract(query, self._cache['weapons'], scorer=fuzz.ratio, limit=5),
            'attachments': process.extract(query, self._cache['attachments'], scorer=fuzz.ratio, limit=10),
            'codes': process.extract(query, self._cache['codes'], scorer=fuzz.ratio, limit=5)
        }

    async def get_suggestions(self, partial_query: str, limit: int=5) -> List[str]:
        """پیشنهادات سریع بر اساس query جزئی"""
        if not partial_query or len(partial_query) < 2:
            return []
        
        if not self._cache['weapons']:
            await self.build_search_index()
            
        suggestions = []
        q_low = partial_query.lower()
        for weapon in self._cache['weapons']:
            if weapon.lower().startswith(q_low):
                suggestions.append(weapon)
                if len(suggestions) >= limit:
                    return suggestions
        
        if len(suggestions) < limit:
            matches = process.extract(partial_query, self._cache['weapons'], scorer=fuzz.ratio, limit=limit)
            for name, score in matches:
                if score >= 80 and name not in suggestions:
                    suggestions.append(name)
        
        return suggestions[:limit]

    def clear_cache(self):
        """پاک کردن cache"""
        with self._cache_lock:
            self._cache = {'weapons': [], 'attachments': [], 'codes': []}
            self._cache_time = 0
            logger.info('Fuzzy search cache cleared')
