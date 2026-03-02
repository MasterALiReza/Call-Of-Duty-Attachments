"""
Database mixin for Analytics, Engagement, Search, and Voting operations.
"""
import logging
import json
import datetime
from .base_repository import BaseRepository
from typing import Optional, Dict, List, Any
from utils.logger import log_exception
logger = logging.getLogger('database.analytics_mixin')

class AnalyticsRepository(BaseRepository):
    """
    Mixin containing analytics, engagement, search, and voting operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    async def vote_attachment(self, user_id: int, attachment_id: int, vote: int) -> Dict:
        """
        ثبت یا تغییر رأی کاربر برای اتچمنت (Atomic UPSERT)
        """
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT rating FROM user_attachment_engagement
                        WHERE user_id = %s AND attachment_id = %s
                        FOR UPDATE NOWAIT
                    """, (user_id, attachment_id))
                    existing = await cursor.fetchone()
                    previous_vote = existing['rating'] if existing else None
                    if previous_vote is None:
                        new_rating = vote if vote != 0 else None
                        action = 'added' if vote != 0 else 'none'
                    elif previous_vote == vote:
                        new_rating = None
                        action = 'removed'
                    elif vote == 0:
                        new_rating = None
                        action = 'removed'
                    else:
                        new_rating = vote
                        action = 'changed'
                    await cursor.execute("""
                        INSERT INTO user_attachment_engagement 
                        (user_id, attachment_id, rating, first_view_date, last_view_date)
                        VALUES (%s, %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, attachment_id) DO UPDATE
                        SET rating = EXCLUDED.rating,
                            last_view_date = NOW()
                    """, (user_id, attachment_id, new_rating))
                    await cursor.execute("""
                        SELECT 
                            COUNT(CASE WHEN rating = 1 THEN 1 END) as likes,
                            COUNT(CASE WHEN rating = -1 THEN 1 END) as dislikes
                        FROM user_attachment_engagement
                        WHERE attachment_id = %s AND rating IS NOT NULL
                    """, (attachment_id,))
                    stats = await cursor.fetchone()
                    like_count = stats['likes']
                    dislike_count = stats['dislikes']
                logger.info(f'✅ Vote (atomic): user={user_id}, att={attachment_id}, {previous_vote}→{new_rating}, action={action}')
                return {'success': True, 'action': action, 'previous_vote': previous_vote, 'new_vote': new_rating if new_rating is not None else 0, 'like_count': like_count, 'dislike_count': dislike_count}
        except Exception as e:
            log_exception(logger, e, f'vote_attachment({user_id}, {attachment_id})')
            return {'success': False, 'action': 'error', 'error': str(e)}

    async def get_user_vote(self, attachment_id: int, user_id: int) -> Optional[int]:
        """دریافت رأی فعلی کاربر"""
        try:
            query = '\n                SELECT rating FROM user_attachment_engagement\n                WHERE user_id = %s AND attachment_id = %s\n            '
            result = await self.execute_query(query, (user_id, attachment_id), fetch_one=True)
            return result['rating'] if result else None
        except Exception as e:
            log_exception(logger, e, f'get_user_vote({attachment_id}, {user_id})')
            return None

    async def track_attachment_view(self, user_id: int, attachment_id: int) -> bool:
        """ثبت بازدید اتچمنت (هم در metrics و هم در engagement)"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    # 1. Individual Metric
                    await cursor.execute("""
                        INSERT INTO attachment_metrics (attachment_id, user_id, action_type)
                        VALUES (%s, %s, 'view')
                    """, (attachment_id, user_id))
                    
                    await cursor.execute("""
                        INSERT INTO user_attachment_engagement (user_id, attachment_id, total_views, first_view_date, last_view_date)
                        VALUES (%s, %s, 1, NOW(), NOW())
                        ON CONFLICT (user_id, attachment_id) DO UPDATE SET
                            total_views = COALESCE(user_attachment_engagement.total_views, 0) + 1,
                            last_view_date = NOW()
                    """, (user_id, attachment_id))
                    
                    # Track in unified events as well
                    await self.track_event(user_id, 'view', {'attachment_id': attachment_id})
                return True
        except Exception as e:
            log_exception(logger, e, f"track_attachment_view({user_id}, {attachment_id})")
            return False

    async def track_attachment_copy(self, user_id: int, attachment_id: int) -> bool:
        """ثبت کپی کد اتچمنت (هم در metrics و هم در engagement)"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    # 1. Individual Metric
                    await cursor.execute("""
                        INSERT INTO attachment_metrics (attachment_id, user_id, action_type)
                        VALUES (%s, %s, 'copy')
                    """, (attachment_id, user_id))
                    
                    await cursor.execute("""
                        INSERT INTO user_attachment_engagement (user_id, attachment_id, total_clicks, last_view_date)
                        VALUES (%s, %s, 1, NOW())
                        ON CONFLICT (user_id, attachment_id) DO UPDATE SET
                            total_clicks = COALESCE(user_attachment_engagement.total_clicks, 0) + 1,
                            last_view_date = NOW()
                    """, (user_id, attachment_id))
                    
                    # Track in unified events as well
                    await self.track_event(user_id, 'copy', {'attachment_id': attachment_id})
                return True
        except Exception as e:
            log_exception(logger, e, f"track_attachment_copy({user_id}, {attachment_id})")
            return False

    async def get_popular_attachments(self, category: str=None, weapon: str=None, mode: str=None, limit: int=10, days: int=14, suggested_only: bool=False) -> List[Dict]:
        """دریافت محبوب\u200cترین اتچمنت\u200cها بر اساس رأی و تعامل"""
        try:
            where_clauses = []
            params = []
            if category:
                where_clauses.append('wc.name = %s')
                params.append(category)
            if weapon:
                where_clauses.append('w.name = %s')
                params.append(weapon)
            if mode:
                where_clauses.append('a.mode = %s')
                params.append(mode)
            where_clauses.append('uae.last_view_date >= NOW() - make_interval(days => %s)')
            params.append(days)
            where_sql = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
            join_suggested = 'JOIN suggested_attachments sa ON a.id = sa.attachment_id AND sa.mode = a.mode' if suggested_only else ''
            query = f'\n                SELECT \n                    a.id, a.name, a.code, a.mode,\n                    w.name as weapon, wc.name as category,\n                    COUNT(CASE WHEN uae.rating = 1 THEN 1 END) as likes,\n                    COUNT(CASE WHEN uae.rating = -1 THEN 1 END) as dislikes,\n                    COUNT(DISTINCT uae.user_id) as unique_users,\n                    SUM(COALESCE(uae.total_views, 0)) as views,\n                    SUM(COALESCE(uae.total_clicks, 0)) as total_clicks,\n                    (COUNT(CASE WHEN uae.rating = 1 THEN 1 END) - \n                     COUNT(CASE WHEN uae.rating = -1 THEN 1 END)) as net_score\n                FROM attachments a\n                JOIN weapons w ON a.weapon_id = w.id\n                JOIN weapon_categories wc ON w.category_id = wc.id\n                {join_suggested}\n                LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id\n                {where_sql}\n                GROUP BY a.id, a.name, a.code, a.mode, w.name, wc.name\n                ORDER BY net_score DESC, views DESC, likes DESC\n                LIMIT %s\n            '
            params.append(limit)
            results = await self.execute_query(query, tuple(params), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, 'get_popular_attachments')
            return []

    async def get_attachment_stats(self, attachment_id: int, period: str='all') -> Dict:
        """دریافت آمار بازخورد اتچمنت"""
        try:
            date_filter = ''
            if period == 'week':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '7 days'"
            elif period == 'month':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '30 days'"
            elif period == 'year':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '365 days'"
            query_votes = f'\n                SELECT \n                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as likes,\n                    SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as dislikes,\n                    COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as total_votes,\n                    SUM(COALESCE(total_views, 0)) as total_views,\n                    SUM(COALESCE(total_clicks, 0)) as total_clicks,\n                    COUNT(DISTINCT user_id) as unique_users\n                FROM user_attachment_engagement\n                WHERE attachment_id = %s {date_filter}\n            '
            vote_stats = await self.execute_query(query_votes, (attachment_id,), fetch_one=True)
            likes = vote_stats['likes'] or 0
            dislikes = vote_stats['dislikes'] or 0
            total_votes = vote_stats['total_votes'] or 0
            like_ratio = likes / total_votes * 100 if total_votes > 0 else 0
            dislike_ratio = dislikes / total_votes * 100 if total_votes > 0 else 0
            return {'like_count': likes, 'dislike_count': dislikes, 'total_votes': total_votes, 'like_ratio': round(like_ratio, 1), 'dislike_ratio': round(dislike_ratio, 1), 'net_score': likes - dislikes, 'total_views': vote_stats['total_views'] or 0, 'total_clicks': vote_stats['total_clicks'] or 0, 'unique_users': vote_stats['unique_users'] or 0, 'period': period}
        except Exception as e:
            log_exception(logger, e, f'get_attachment_stats({attachment_id})')
            return {'like_count': 0, 'dislike_count': 0, 'total_votes': 0, 'like_ratio': 0, 'dislike_ratio': 0, 'net_score': 0, 'total_views': 0, 'total_clicks': 0, 'unique_users': 0, 'period': period}

    async def search_attachments_like(self, query: str, limit: int=30) -> List[Dict]:
        """جستجوی ساده با LIKE (fallback)"""
        try:
            normalized_query = '%' + ''.join((c.lower() for c in query if c.isalnum())) + '%'
            query_sql = "\n                SELECT c.name as category, w.name as weapon, a.mode,\n                       a.code, a.name as att_name, a.image_file_id as image,\n                       a.is_top, a.is_season_top\n                FROM attachments a\n                JOIN weapons w ON a.weapon_id = w.id\n                JOIN weapon_categories c ON w.category_id = c.id\n                WHERE LOWER(REPLACE(REPLACE(a.name, ' ', ''), '-', '')) LIKE %s\n                   OR LOWER(REPLACE(REPLACE(w.name, ' ', ''), '-', '')) LIKE %s\n                   OR LOWER(a.code) LIKE %s\n                ORDER BY a.is_season_top DESC, a.is_top DESC\n                LIMIT %s\n            "
            results = await self.execute_query(query_sql, (normalized_query, normalized_query, normalized_query, limit), fetch_all=True)
            items = []
            for row in results:
                items.append({'category': row['category'], 'weapon': row['weapon'], 'mode': row['mode'], 'attachment': {'code': row['code'], 'name': row['att_name'], 'image': row['image'], 'is_top': row.get('is_top', False), 'is_season_top': row.get('is_season_top', False)}})
            return items
        except Exception as e:
            log_exception(logger, e, f'search_attachments_like({query})')
            return []

    async def search_attachments_fts(self, query: str, limit: int=30) -> List[Dict]:
        """جستجوی پیشرفته با pg_trgm (PostgreSQL)"""
        try:
            q = (query or '').strip()
            if not q:
                return []
            if len(q) < 3 or q.isdigit():
                return await self.search_attachments_like(query, limit)
            query_sql = '\n                SELECT \n                    c.name as category,\n                    w.name as weapon,\n                    a.mode,\n                    a.code,\n                    a.name as att_name,\n                    a.image_file_id as image,\n                    a.is_top,\n                    a.is_season_top,\n                    GREATEST(\n                        similarity(a.name, %s),\n                        similarity(w.name, %s),\n                        similarity(a.code, %s)\n                    ) as score\n                FROM attachments a\n                JOIN weapons w ON a.weapon_id = w.id\n                JOIN weapon_categories c ON w.category_id = c.id\n                WHERE \n                    a.name %% %s \n                    OR w.name %% %s\n                    OR a.code %% %s\n                    OR a.code ILIKE %s\n                    OR a.name ILIKE %s\n                    OR w.name ILIKE %s\n                ORDER BY score DESC, a.is_season_top DESC, a.is_top DESC\n                LIMIT %s\n            '
            like_pattern = f'%{q}%'
            results = await self.execute_query(query_sql, (q, q, q, q, q, q, like_pattern, like_pattern, like_pattern, limit), fetch_all=True)
            items = []
            for row in results:
                items.append({'category': row['category'], 'weapon': row['weapon'], 'mode': row['mode'], 'attachment': {'code': row['code'], 'name': row['att_name'], 'image': row['image'], 'is_top': row.get('is_top', False), 'is_season_top': row.get('is_season_top', False)}})
            if not items:
                return await self.search_attachments_like(query, limit)
            return items
        except Exception as e:
            logger.warning(f'FTS search failed, falling back to LIKE: {e}')
            return await self.search_attachments_like(query, limit)

    async def search_attachments(self, query: str) -> List[Dict]:
        """جستجوی هوشمند (wrapper)"""
        try:
            return await self.search_attachments_fts(query, limit=30)
        except Exception as e:
            log_exception(logger, e, f'search_attachments({query})')
            return []

    async def track_search(self, user_id: int, query: str, results_count: int, execution_time_ms: float) -> bool:
        """ثبت جستجو برای Analytics"""
        try:
            query_normalized = query.strip().lower()
            if not query_normalized or len(query_normalized) < 2:
                return False
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO search_history (user_id, query, results_count, execution_time_ms)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, query_normalized, results_count, execution_time_ms))
                    await cursor.execute("""
                        INSERT INTO popular_searches (query, search_count, last_searched)
                        VALUES (%s, 1, NOW())
                        ON CONFLICT(query) DO UPDATE SET
                            search_count = popular_searches.search_count + 1,
                            last_searched = NOW()
                    """, (query_normalized,))
            return True
        except Exception as e:
            logger.warning(f'Error tracking search: {e}')
            return False

    async def get_popular_searches(self, limit: int=5) -> List[str]:
        """دریافت محبوب\u200cترین جستجوها"""
        try:
            query = '\n                SELECT query\n                FROM popular_searches\n                ORDER BY search_count DESC, last_searched DESC\n                LIMIT %s\n            '
            results = await self.execute_query(query, (limit,), fetch_all=True)
            return [r['query'] for r in results]
        except Exception as e:
            log_exception(logger, e, 'get_popular_searches')
            return []

    async def get_search_analytics(self, days: int=30) -> Dict:
        """دریافت آمار جستجو"""
        try:
            query_stats = '\n                SELECT \n                    COUNT(*) as total_searches,\n                    COUNT(DISTINCT user_id) as unique_users,\n                    AVG(results_count) as avg_results,\n                    AVG(execution_time_ms) as avg_time_ms,\n                    SUM(CASE WHEN results_count = 0 THEN 1 ELSE 0 END) as zero_results\n                FROM search_history\n                WHERE created_at >= NOW() - make_interval(days => %s)\n            '
            stats = await self.execute_query(query_stats, (days,), fetch_one=True)
            query_top = '\n                SELECT query, COUNT(*) as count\n                FROM search_history\n                WHERE created_at >= NOW() - make_interval(days => %s)\n                GROUP BY query\n                ORDER BY count DESC\n                LIMIT 10\n            '
            top_queries = await self.execute_query(query_top, (days,), fetch_all=True)
            query_failed = '\n                SELECT query, COUNT(*) as count\n                FROM search_history\n                WHERE results_count = 0\n                  AND created_at >= NOW() - make_interval(days => %s)\n                GROUP BY query\n                ORDER BY count DESC\n                LIMIT 10\n            '
            failed_queries = await self.execute_query(query_failed, (days,), fetch_all=True)
            total = stats['total_searches'] or 1
            zero_rate = stats['zero_results'] / total * 100 if total > 0 else 0
            return {'total_searches': stats['total_searches'] or 0, 'unique_users': stats['unique_users'] or 0, 'avg_results': round(stats['avg_results'] or 0, 1), 'avg_time_ms': round(stats['avg_time_ms'] or 0, 1), 'zero_results': stats['zero_results'] or 0, 'zero_rate': round(zero_rate, 1), 'top_queries': [{'query': q['query'], 'count': q['count']} for q in top_queries], 'failed_queries': [{'query': q['query'], 'count': q['count']} for q in failed_queries]}
        except Exception as e:
            log_exception(logger, e, 'get_search_analytics')
            return {'total_searches': 0, 'unique_users': 0, 'avg_results': 0, 'avg_time_ms': 0, 'zero_results': 0, 'zero_rate': 0, 'top_queries': [], 'failed_queries': []}

    async def add_feedback(self, user_id: int, rating: int, category: str='general', message: str='') -> bool:
        """ثبت بازخورد کاربر"""
        try:
            query = '\n                INSERT INTO feedback (user_id, rating, category, message)\n                VALUES (%s, %s, %s, %s)\n            '
            await self.execute_query(query, (user_id, rating, category, message))
            logger.info(f'✅ Feedback added: user={user_id}, rating={rating}')
            return True
        except Exception as e:
            log_exception(logger, e, 'add_feedback')
            return False

    async def get_feedback_stats(self) -> Dict:
        """آمار بازخوردها - بهینه شده"""
        try:
            query = '\n                SELECT \n                    rating,\n                    COUNT(*) as count,\n                    (SELECT COUNT(*) FROM feedback) as total,\n                    (SELECT AVG(rating) FROM feedback) as avg_rating\n                FROM feedback\n                GROUP BY rating\n            '
            results = await self.execute_query(query, fetch_all=True)
            if results:
                total = results[0]['total']
                avg_rating = results[0]['avg_rating'] or 0
                distribution = {str(row['rating']): row['count'] for row in results}
            else:
                total = 0
                avg_rating = 0
                distribution = {}
            return {'average_rating': round(float(avg_rating), 2), 'total': total, 'rating_distribution': distribution}
        except Exception as e:
            log_exception(logger, e, 'get_feedback_stats')
            return {'average_rating': 0, 'total': 0, 'rating_distribution': {}}

    async def get_statistics(self) -> Dict:
        """دریافت آمار کامل و تفصیلی دیتابیس"""
        try:
            stats = {'total_weapons': 0, 'total_attachments': 0, 'total_attachments_br': 0, 'total_attachments_mp': 0, 'total_top_attachments': 0, 'total_season_attachments': 0, 'total_guides': 0, 'total_guides_br': 0, 'total_guides_mp': 0, 'total_channels': 0, 'total_admins': 0, 'categories': {}, 'weapons_with_attachments': 0, 'weapons_without_attachments': 0}
            stats['total_weapons'] = await self.execute_query('SELECT COUNT(*) as count FROM weapons', fetch_one=True)['count']
            stats['total_attachments'] = await self.execute_query('SELECT COUNT(*) as count FROM attachments', fetch_one=True)['count']
            stats['total_attachments_br'] = await self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE mode = 'br'", fetch_one=True)['count']
            stats['total_attachments_mp'] = await self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE mode = 'mp'", fetch_one=True)['count']
            stats['total_top_attachments'] = await self.execute_query('SELECT COUNT(*) as count FROM attachments WHERE is_top = TRUE', fetch_one=True)['count']
            stats['total_season_attachments'] = await self.execute_query('SELECT COUNT(*) as count FROM attachments WHERE is_season_top = TRUE', fetch_one=True)['count']
            return stats
        except Exception as e:
            log_exception(logger, e, 'get_statistics')
            return {}

    async def submit_attachment_feedback(self, user_id: int, attachment_id: int, feedback_text: str) -> bool:
        """ثبت بازخورد متنی برای اتچمنت"""
        try:
            feedback_text = feedback_text[:500].strip()
            if not feedback_text:
                logger.warning(f"Empty feedback rejected: user={user_id}, att={attachment_id}")
                return False
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO user_attachment_engagement (user_id, attachment_id, feedback, first_view_date, last_view_date)
                        VALUES (%s, %s, %s, NOW(), NOW())
                        ON CONFLICT (user_id, attachment_id) DO UPDATE SET
                            feedback = EXCLUDED.feedback,
                            last_view_date = NOW()
                    """, (user_id, attachment_id, feedback_text))
                return True
        except Exception as e:
            log_exception(logger, e, f"submit_attachment_feedback({user_id}, {attachment_id})")
            return False

    # ===== Unified Event Tracking =====

    async def track_event(self, user_id: int, event_type: str = 'general', metadata: Dict = None, **kwargs) -> bool:
        """Unified entry point for tracking user events in analytics_events table"""
        try:
            # Merge kwargs into metadata
            final_metadata = metadata.copy() if metadata else {}
            if kwargs:
                final_metadata.update(kwargs)
                
            query = """
                INSERT INTO analytics_events (user_id, event_type, metadata)
                VALUES (%s, %s, %s)
            """
            await self.execute_query(query, (user_id, event_type, json.dumps(final_metadata) if final_metadata else None))
            return True
        except Exception as e:
            log_exception(logger, e, f"track_event({user_id}, {event_type})")
            return False

    async def get_user_leaderboard(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """
        دریافت لیست برترین کاربران بر اساس فعالیت (Leaderboard)
        امتیازدهی: هر بازدید 1 امتیاز، هر کپی 20 امتیاز، هر رأی 10 امتیاز
        """
        try:
            query = """
                SELECT 
                    uae.user_id,
                    u.username,
                    u.first_name,
                    SUM(COALESCE(uae.total_views, 0)) as views,
                    SUM(COALESCE(uae.total_clicks, 0)) as clicks,
                    COUNT(CASE WHEN uae.rating IS NOT NULL THEN 1 END) as votes,
                    (SUM(COALESCE(uae.total_views, 0)) * 1 + 
                     SUM(COALESCE(uae.total_clicks, 0)) * 20 + 
                     COUNT(CASE WHEN uae.rating IS NOT NULL THEN 1 END) * 10) as score
                FROM user_attachment_engagement uae
                LEFT JOIN users u ON uae.user_id = u.user_id
                WHERE uae.last_view_date >= NOW() - make_interval(days => %s)
                GROUP BY uae.user_id, u.username, u.first_name
                ORDER BY score DESC
                LIMIT %s
            """
            return await self.execute_query(query, (days, limit), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_user_leaderboard")
            return []

    # ===== Mandatory Channel Analytics =====

    async def track_user_start(self, user_id: int, source: str = None) -> bool:
        """ثبت اولین ورود کاربر به ربات"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO analytics_users (user_id, first_seen, registration_source)
                        VALUES (%s, NOW(), %s)
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING user_id
                    """, (user_id, source))
                    is_new = await cursor.fetchone() is not None
                    
                    if is_new:
                        today = datetime.date.today()
                        await cursor.execute("""
                            INSERT INTO analytics_daily_stats (date, new_users)
                            VALUES (%s, 1)
                            ON CONFLICT (date) DO UPDATE SET new_users = analytics_daily_stats.new_users + 1
                        """, (today,))
                        await self.track_event(user_id, "start", {"source": source})
                    return True
        except Exception as e:
            log_exception(logger, e, f"track_user_start({user_id})")
            return False

    async def track_join_success(self, user_id: int, channel_id: str) -> bool:
        """ثبت عضویت موفق در کانال"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE analytics_users
                        SET successful_joins = successful_joins + 1
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    await cursor.execute("UPDATE analytics_channels SET total_joins = total_joins + 1 WHERE channel_id = %s", (channel_id,))
                    
                    today = datetime.date.today()
                    await cursor.execute("""
                        INSERT INTO analytics_daily_stats (date, successful_joins)
                        VALUES (%s, 1)
                        ON CONFLICT (date) DO UPDATE SET successful_joins = analytics_daily_stats.successful_joins + 1
                    """, (today,))
                    
                    await self.track_event(user_id, "join_success", {"channel_id": channel_id})
                    return True
        except Exception as e:
            log_exception(logger, e, f"track_join_success({user_id}, {channel_id})")
            return False

    async def track_join_attempt(self, user_id: int, channel_id: str) -> bool:
        """ثبت تلاش برای عضویت"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    # 1. Update user attempts
                    await cursor.execute("""
                        INSERT INTO analytics_users (user_id, first_seen)
                        VALUES (%s, NOW())
                        ON CONFLICT (user_id) DO UPDATE SET
                            join_attempts = analytics_users.join_attempts + 1
                    """, (user_id,))
                    
                    # 2. Update channel attempts
                    await cursor.execute("""
                        UPDATE analytics_channels
                        SET total_join_attempts = total_join_attempts + 1
                        WHERE channel_id = %s
                    """, (channel_id,))
                    
                    # 3. Daily stats
                    today = datetime.date.today()
                    await cursor.execute("""
                        INSERT INTO analytics_daily_stats (date, total_attempts)
                        VALUES (%s, 1)
                        ON CONFLICT (date) DO UPDATE SET total_attempts = analytics_daily_stats.total_attempts + 1
                    """, (today,))
                    
                    await self.track_event(user_id, "join_attempt", {"channel_id": channel_id})
                    return True
        except Exception as e:
            log_exception(logger, e, f"track_join_attempt({user_id}, {channel_id})")
            return False

    # ===== Dashboard & Reporting =====

    async def get_overview_stats(self, days: int = 30) -> Dict:
        """Get high-level overview stats for the dashboard"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    # 1. Core Metrics (Views, Clicks, etc.)
                    await cursor.execute("""
                        SELECT 
                            COUNT(CASE WHEN action_type = 'view' THEN 1 END) as views,
                            COUNT(CASE WHEN action_type = 'click' THEN 1 END) as clicks,
                            COUNT(CASE WHEN action_type = 'share' THEN 1 END) as shares,
                            COUNT(DISTINCT user_id) as unique_users
                        FROM attachment_metrics
                        WHERE action_date >= NOW() - INTERVAL '%s days'
                    """, (days,))
                    core = await cursor.fetchone() or {}
                    
                    # 2. Top Performer
                    await cursor.execute("""
                        SELECT a.name, COUNT(*) as views
                        FROM attachment_metrics m
                        JOIN attachments a ON m.attachment_id = a.id
                        WHERE m.action_type = 'view'
                        GROUP BY a.id, a.name
                        ORDER BY views DESC
                        LIMIT 1
                    """)
                    top = await cursor.fetchone()
                    
                    # 3. Most Engaging
                    await cursor.execute("""
                        SELECT a.name, 
                               (CAST(COUNT(CASE WHEN m.action_type='click' THEN 1 END) AS FLOAT) / 
                                NULLIF(COUNT(CASE WHEN m.action_type='view' THEN 1 END), 0)) * 100 as rate
                        FROM attachment_metrics m
                        JOIN attachments a ON m.attachment_id = a.id
                        GROUP BY a.id, a.name
                        HAVING COUNT(CASE WHEN m.action_type='view' THEN 1 END) > 50
                        ORDER BY rate DESC
                        LIMIT 1
                    """)
                    engaging = await cursor.fetchone()

                    # 4. Highest Rated
                    await cursor.execute("""
                        SELECT a.name, AVG(uae.rating) as avg_rating
                        FROM user_attachment_engagement uae
                        JOIN attachments a ON uae.attachment_id = a.id
                        WHERE uae.rating IS NOT NULL
                        GROUP BY a.id, a.name
                        HAVING COUNT(uae.rating) >= 5
                        ORDER BY avg_rating DESC
                        LIMIT 1
                    """)
                    rated = await cursor.fetchone()

                    return {
                        "total_views": core.get("views", 0),
                        "total_clicks": core.get("clicks", 0),
                        "total_shares": core.get("shares", 0),
                        "unique_users": core.get("unique_users", 0),
                        "engagement_rate": (core.get("clicks", 0) / core.get("views", 1) * 100) if core.get("views", 0) > 0 else 0,
                        "top_performer": {"name": top["name"], "views": top["views"]} if top else None,
                        "most_engaging": {"name": engaging["name"], "rate": engaging["rate"]} if engaging else None,
                        "highest_rated": {"name": rated["name"], "rating": rated["avg_rating"]} if rated else None
                    }
        except Exception as e:
            log_exception(logger, e, "get_overview_stats")
            return {}

    async def get_trending_growth_stats(self, limit: int = 10) -> List[Dict]:
        """Get trending attachments based on week-over-week growth"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        WITH week_stats AS (
                            SELECT 
                                attachment_id,
                                COUNT(CASE WHEN action_date >= NOW() - INTERVAL '7 days' THEN 1 END) as recent_week,
                                COUNT(CASE WHEN action_date BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days' THEN 1 END) as previous_week
                            FROM attachment_metrics
                            WHERE action_date >= NOW() - INTERVAL '14 days'
                            AND action_type = 'view'
                            GROUP BY attachment_id
                        ),
                        growth_calc AS (
                            SELECT 
                                attachment_id,
                                recent_week,
                                previous_week,
                                CASE 
                                    WHEN previous_week = 0 THEN 100.0
                                    WHEN previous_week > 0 THEN ((recent_week::float - previous_week) / previous_week * 100)
                                    ELSE 0
                                END as growth_rate
                            FROM week_stats
                            WHERE recent_week > 0
                        )
                        SELECT 
                            a.id, a.name, COALESCE(w.name, 'Unknown') as weapon,
                            gc.recent_week as views, gc.growth_rate
                        FROM growth_calc gc
                        JOIN attachments a ON gc.attachment_id = a.id
                        LEFT JOIN weapons w ON a.weapon_id = w.id
                        WHERE gc.growth_rate > 0 OR gc.recent_week >= 5
                        ORDER BY gc.growth_rate DESC, gc.recent_week DESC
                        LIMIT %s
                    """, (limit,))
                    return await cursor.fetchall() or []
        except Exception as e:
            log_exception(logger, e, "get_trending_growth_stats")
            return []

    # ===== Advanced Analytics: Cohort & Funnel =====

    async def get_cohort_retention(self, weeks: int = 4) -> List[Dict]:
        """محاسبه نرخ بازگشت کاربران (Cohort Analysis) بر اساس هفته"""
        try:
            query = """
                WITH cohorts AS (
                    SELECT 
                        user_id,
                        date_trunc('week', first_seen) as cohort_week
                    FROM analytics_users
                    WHERE first_seen >= NOW() - make_interval(weeks => %s)
                ),
                user_activities AS (
                    SELECT DISTINCT
                        user_id,
                        date_trunc('week', created_at) as activity_week
                    FROM analytics_events
                    WHERE created_at >= NOW() - make_interval(weeks => %s)
                )
                SELECT 
                    c.cohort_week::date,
                    COUNT(DISTINCT c.user_id) as cohort_size,
                    floor(extract(day from (ua.activity_week - c.cohort_week)) / 7) as week_number,
                    COUNT(DISTINCT ua.user_id) as active_users
                FROM cohorts c
                LEFT JOIN user_activities ua ON c.user_id = ua.user_id
                WHERE ua.activity_week >= c.cohort_week
                GROUP BY 1, 3
                ORDER BY 1 DESC, 3 ASC
            """
            return await self.execute_query(query, (weeks+8, weeks+8), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_cohort_retention")
            return []

    async def get_full_journey_funnel(self) -> List[Dict]:
        """تحلیل کامل مسیر کاربر از اولین ورود تا کپی کد (ساختاریافته برای UI)"""
        try:
            query = """
                SELECT
                    (SELECT COUNT(*) FROM analytics_users) as total_started,
                    (SELECT COUNT(*) FROM analytics_users WHERE join_attempts > 0) as reached_join_screen,
                    (SELECT COUNT(*) FROM analytics_users WHERE successful_joins > 0) as completed_join,
                    (SELECT COUNT(DISTINCT user_id) FROM analytics_events WHERE event_type = 'search') as performed_search,
                    (SELECT COUNT(DISTINCT user_id) FROM attachment_metrics WHERE action_type = 'view') as viewed_attachment,
                    (SELECT COUNT(DISTINCT user_id) FROM attachment_metrics WHERE action_type = 'copy') as copied_code
            """
            raw = await self.execute_query(query, fetch_one=True)
            if not raw:
                return []
                
            steps = [
                ("User Started", raw['total_started']),
                ("Reached Join Screen", raw['reached_join_screen']),
                ("Completed Join", raw['completed_join']),
                ("Performed Search", raw['performed_search']),
                ("Viewed Attachment", raw['viewed_attachment']),
                ("Copied Code", raw['copied_code'])
            ]
            
            funnel = []
            max_val = raw['total_started'] or 1
            
            for step_name, count in steps:
                funnel.append({
                    'step': step_name,
                    'count': count,
                    'conversion_rate': round(count / max_val * 100, 1) if max_val > 0 else 0
                })
                
            return funnel
        except Exception as e:
            log_exception(logger, e, "get_full_journey_funnel")
            return []

    async def get_attachment_search_results(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Search attachments with their view/click counts for admin dashboard"""
        try:
            pattern = f"%{query_text.lower()}%"
            query = """
                WITH base AS (
                    SELECT a.id, a.name, a.code, w.name AS weapon, wc.name AS category
                    FROM attachments a
                    LEFT JOIN weapons w ON a.weapon_id = w.id
                    LEFT JOIN weapon_categories wc ON w.category_id = wc.id
                    WHERE LOWER(a.name) LIKE %s
                       OR CAST(a.code AS TEXT) LIKE %s
                       OR LOWER(w.name) LIKE %s
                ),
                agg AS (
                    SELECT m.attachment_id,
                           COUNT(CASE WHEN m.action_type='view' THEN 1 END) AS views,
                           COUNT(CASE WHEN m.action_type='click' THEN 1 END) AS clicks
                    FROM attachment_metrics m
                    WHERE m.attachment_id IN (SELECT id FROM base)
                    GROUP BY m.attachment_id
                )
                SELECT b.id AS att_id,
                       b.name AS attachment,
                       COALESCE(b.weapon,'Unknown') AS weapon,
                       COALESCE(b.category,'Unknown') AS category,
                       COALESCE(agg.views,0) AS views,
                       COALESCE(agg.clicks,0) AS clicks
                FROM base b
                LEFT JOIN agg ON agg.attachment_id = b.id
                ORDER BY views DESC
                LIMIT %s
            """
            return await self.execute_query(query, (pattern, pattern, pattern, limit), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_attachment_search_results")
            return []

    async def get_csv_report_data(self, days: int = 7, limit: int = 200) -> List[Dict]:
        """Get flattened attachment performance data for CSV export"""
        try:
            query = """
                SELECT 
                    a.name as attachment,
                    COALESCE(w.name,'Unknown') as weapon,
                    COALESCE(wc.name,'Unknown') as category,
                    COUNT(CASE WHEN m.action_type='view' THEN 1 END) as views,
                    COUNT(CASE WHEN m.action_type='click' THEN 1 END) as clicks,
                    COUNT(DISTINCT m.user_id) as users
                FROM attachment_metrics m
                JOIN attachments a ON m.attachment_id = a.id
                LEFT JOIN weapons w ON a.weapon_id = w.id
                LEFT JOIN weapon_categories wc ON w.category_id = wc.id
                WHERE m.action_date >= NOW() - make_interval(days => %s)
                GROUP BY a.id, a.name, w.name, wc.name
                ORDER BY views DESC
                LIMIT %s
            """
            return await self.execute_query(query, (days, limit), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_csv_report_data")
            return []

    async def get_daily_breakdown(self, days: int = 7) -> List[Dict]:
        """Get daily views/clicks/users for the last N days"""
        try:
            query = """
                SELECT 
                    DATE(action_date) as date,
                    COUNT(CASE WHEN action_type='view' THEN 1 END) as views,
                    COUNT(CASE WHEN action_type='click' THEN 1 END) as clicks,
                    COUNT(DISTINCT user_id) as users
                FROM attachment_metrics
                WHERE action_date >= NOW() - make_interval(days => %s)
                GROUP BY DATE(action_date)
                ORDER BY date ASC
            """
            return await self.execute_query(query, (days,), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_daily_breakdown")
            return []

    async def get_attachment_detailed_stats(self, attachment_id: int) -> Dict:
        """Get full stats including metadata, 30d summary, and 7d breakdown for an attachment"""
        try:
            # Meta
            meta_query = """
                SELECT a.name as attachment, a.code, a.mode,
                       COALESCE(w.name,'Unknown') as weapon,
                       COALESCE(wc.name,'Unknown') as category
                FROM attachments a
                LEFT JOIN weapons w ON a.weapon_id = w.id
                LEFT JOIN weapon_categories wc ON w.category_id = wc.id
                WHERE a.id = %s
            """
            meta = await self.execute_query(meta_query, (attachment_id,), fetch_one=True)
            if not meta:
                return {}

            # 30d summary
            summary_query = """
                SELECT 
                    COUNT(CASE WHEN action_type='view' THEN 1 END) as views,
                    COUNT(CASE WHEN action_type='click' THEN 1 END) as clicks,
                    COUNT(DISTINCT user_id) as users
                FROM attachment_metrics
                WHERE attachment_id = %s AND action_date >= NOW() - INTERVAL '30 days'
            """
            summary = await self.execute_query(summary_query, (attachment_id,), fetch_one=True)
            
            # 7d breakdown
            breakdown_query = """
                SELECT DATE(action_date) as date,
                       COUNT(CASE WHEN action_type='view' THEN 1 END) as views,
                       COUNT(CASE WHEN action_type='click' THEN 1 END) as clicks
                FROM attachment_metrics
                WHERE attachment_id = %s AND action_date >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(action_date)
                ORDER BY date ASC
            """
            breakdown = await self.execute_query(breakdown_query, (attachment_id,), fetch_all=True)

            return {
                "attachment": meta,
                "summary_30d": summary,
                "daily_7d": breakdown
            }
        except Exception as e:
            log_exception(logger, e, "get_attachment_detailed_stats")
            return {}

    async def get_attachment_behavior_analytics(self, days: int = 7) -> Dict:
        """Analyze user behavior for attachments"""
        # Placeholder for extended attachment analytics if needed
        return {}

    # ===== Feedback Dashboard Refined Methods =====

    async def get_attachment_feedback_stats(self, suggested_only: bool = False, days: int = 30) -> Dict:
        """دریافت آمار کلی بازخورد اتچمنت‌ها برای داشبورد"""
        try:
            from core.database.sql_helpers import get_datetime_interval
            dt_filter = get_datetime_interval(days)
            
            base_sql = f"""
                SELECT 
                    COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as total_votes, 
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as total_likes, 
                    SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as total_dislikes, 
                    COALESCE(SUM(total_views), 0) as total_views, 
                    COUNT(CASE WHEN feedback IS NOT NULL AND feedback != '' THEN 1 END) as total_feedbacks, 
                    COUNT(DISTINCT user_id) as active_users 
                FROM user_attachment_engagement 
                WHERE last_view_date >= {dt_filter}
            """
            
            if suggested_only:
                base_sql += ' AND attachment_id IN (SELECT attachment_id FROM suggested_attachments)'
                
            row = await self.execute_query(base_sql, fetch_one=True)
            
            return {
                'total_votes': int(row['total_votes'] or 0),
                'total_likes': int(row['total_likes'] or 0),
                'total_dislikes': int(row['total_dislikes'] or 0),
                'total_views': int(row['total_views'] or 0),
                'total_feedbacks': int(row['total_feedbacks'] or 0),
                'active_users': int(row['active_users'] or 0)
            }
        except Exception as e:
            log_exception(logger, e, 'get_attachment_feedback_stats')
            return {'total_votes': 0, 'total_likes': 0, 'total_dislikes': 0, 'total_views': 0, 'total_feedbacks': 0, 'active_users': 0}

    async def get_attachment_feedback_list(self, page: int = 1, per_page: int = 5, suggested_only: bool = False) -> Dict:
        """دریافت لیست نظرات کاربران با صفحه‌بندی"""
        try:
            where_clause = "WHERE uae.feedback IS NOT NULL AND uae.feedback != ''"
            if suggested_only:
                where_clause += " AND uae.attachment_id IN (SELECT attachment_id FROM suggested_attachments)"
                
            count_sql = f"SELECT COUNT(*) as count FROM user_attachment_engagement uae {where_clause}"
            total_row = await self.execute_query(count_sql, fetch_one=True)
            total = int(total_row['count'] or 0)
            
            list_sql = f"""
                SELECT 
                    uae.user_id, uae.feedback, uae.last_view_date, 
                    a.name as attachment_name, a.code, 
                    u.username, u.first_name 
                FROM user_attachment_engagement uae 
                JOIN attachments a ON uae.attachment_id = a.id 
                LEFT JOIN users u ON u.user_id = uae.user_id 
                {where_clause}
                ORDER BY uae.last_view_date DESC 
                LIMIT %s OFFSET %s
            """
            
            offset = (page - 1) * per_page
            feedbacks = await self.execute_query(list_sql, (per_page, offset), fetch_all=True)
            
            return {
                'items': feedbacks or [],
                'total': total,
                'total_pages': max(1, (total + per_page - 1) // per_page),
                'current_page': page
            }
        except Exception as e:
            log_exception(logger, e, 'get_attachment_feedback_list')
            return {'items': [], 'total': 0, 'total_pages': 1, 'current_page': 1}

    async def get_attachment_stats_by_category(self, suggested_only: bool = False, days: int = 30) -> List[Dict]:
        """آمار تجمیعی بر اساس دسته‌بندی سلاح‌ها"""
        try:
            from core.database.sql_helpers import get_datetime_interval
            dt_filter = get_datetime_interval(days)
            
            query = f"""
                SELECT 
                    wc.name AS category, 
                    COUNT(DISTINCT a.id) AS attachments, 
                    COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) AS likes, 
                    COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) AS dislikes 
                FROM attachments a 
                JOIN weapons w ON a.weapon_id = w.id 
                JOIN weapon_categories wc ON w.category_id = wc.id 
                LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id AND uae.last_view_date >= {dt_filter}
            """
            
            if suggested_only:
                query += ' JOIN suggested_attachments sa ON sa.attachment_id = a.id AND sa.mode = a.mode'
            
            query += ' GROUP BY wc.name ORDER BY likes DESC'
            return await self.execute_query(query, fetch_all=True)
        except Exception as e:
            log_exception(logger, e, 'get_attachment_stats_by_category')
            return []

    async def get_attachment_stats_by_mode(self, suggested_only: bool = False, days: int = 30) -> List[Dict]:
        """آمار تجمیعی بر اساس مود بازی (MP/BR)"""
        try:
            from core.database.sql_helpers import get_datetime_interval
            dt_filter = get_datetime_interval(days)
            
            query = f"""
                SELECT 
                    a.mode, 
                    COUNT(CASE WHEN uae.rating IS NOT NULL THEN 1 END) AS votes, 
                    COALESCE(SUM(CASE WHEN uae.rating = 1 THEN 1 ELSE 0 END), 0) AS likes, 
                    COALESCE(SUM(CASE WHEN uae.rating = -1 THEN 1 ELSE 0 END), 0) AS dislikes 
                FROM attachments a 
                LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id AND uae.last_view_date >= {dt_filter}
            """
            
            if suggested_only:
                query += ' JOIN suggested_attachments sa ON sa.attachment_id = a.id AND sa.mode = a.mode'
            
            query += ' GROUP BY a.mode'
            return await self.execute_query(query, fetch_all=True)
        except Exception as e:
            log_exception(logger, e, 'get_attachment_stats_by_mode')
            return []

    async def get_attachment_weekly_trend(self, suggested_only: bool = False, weeks: int = 8) -> List[Dict]:
        """روند هفتگی تعاملات در هفته‌های اخیر"""
        try:
            from core.database.sql_helpers import get_datetime_interval
            days = weeks * 7
            dt_filter = get_datetime_interval(days)
            
            query = f"""
                SELECT 
                    to_char(date_trunc('week', uae.last_view_date), 'IYYY-IW') AS week_label, 
                    COUNT(CASE WHEN uae.rating IS NOT NULL THEN 1 END) AS votes 
                FROM user_attachment_engagement uae
            """
            
            if suggested_only:
                query += ' JOIN attachments a ON a.id = uae.attachment_id JOIN suggested_attachments sa ON sa.attachment_id = a.id AND sa.mode = a.mode'
            
            query += f' WHERE uae.last_view_date >= {dt_filter} GROUP BY week_label ORDER BY week_label'
            return await self.execute_query(query, fetch_all=True)
        except Exception as e:
            log_exception(logger, e, 'get_attachment_weekly_trend')
            return []

    async def get_user_behavior_analytics(self, days: int = 7) -> Dict:
        """Analyze user behavior: activity levels, segments, and top users"""
        try:
            # 1. Summary Metrics
            summary_query = """
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(CASE WHEN action_type='view' THEN 1 END) as total_views,
                    COUNT(CASE WHEN action_type='click' THEN 1 END) as total_clicks,
                    (SELECT COUNT(DISTINCT user_id) FROM analytics_users) as total_users_all_time
                FROM attachment_metrics
                WHERE action_date >= NOW() - make_interval(days => %s)
            """
            summary = await self.execute_query(summary_query, (days,), fetch_one=True)

            # 2. Per-user stats for segmenting
            per_user_query = """
                SELECT 
                    user_id,
                    COUNT(CASE WHEN action_type='view' THEN 1 END) as views,
                    COUNT(CASE WHEN action_type='click' THEN 1 END) as clicks,
                    COUNT(DISTINCT attachment_id) as unique_attachments,
                    MAX(action_date) as last_active
                FROM attachment_metrics
                WHERE action_date >= NOW() - make_interval(days => %s)
                GROUP BY user_id
                ORDER BY views DESC
                LIMIT 50
            """
            user_stats = await self.execute_query(per_user_query, (days,), fetch_all=True)

            # 3. Top attachments by reach (distinct users)
            top_reach_query = """
                SELECT a.name, COUNT(DISTINCT m.user_id) as unique_users
                FROM attachment_metrics m
                JOIN attachments a ON m.attachment_id = a.id
                WHERE m.action_type='view' AND m.action_date >= NOW() - make_interval(days => %s)
                GROUP BY a.id, a.name
                ORDER BY unique_users DESC
                LIMIT 5
            """
            top_reach = await self.execute_query(top_reach_query, (days,), fetch_all=True)

            return {
                "summary": summary,
                "per_user_stats": user_stats,
                "top_attachments_reach": top_reach
            }
        except Exception as e:
            log_exception(logger, e, "get_user_behavior_analytics")
            return {}

    async def get_weapon_category_stats(self, category_id: int, mode: str = None) -> Dict:
        """Get aggregated stats for a specific weapon category"""
        try:
            where_clause = "WHERE wc.id = %s"
            params = [category_id]
            if mode:
                where_clause += " AND a.mode = %s"
                params.append(mode)

            query = f"""
                WITH base AS (
                    SELECT a.id, a.name
                    FROM attachments a
                    JOIN weapons w ON a.weapon_id = w.id
                    JOIN weapon_categories wc ON w.category_id = wc.id
                    {where_clause}
                ),
                views AS (
                    SELECT m.attachment_id, COUNT(*) AS v
                    FROM attachment_metrics m
                    WHERE m.action_type = 'view'
                    GROUP BY m.attachment_id
                )
                SELECT 
                    (SELECT name FROM weapon_categories WHERE id = %s) AS category_name,
                    (SELECT COUNT(*) FROM base) AS attachment_count,
                    COALESCE(SUM(v), 0) AS total_views,
                    COALESCE(AVG(v), 0) AS average_views,
                    COALESCE(MAX(v), 0) AS max_views
                FROM base b
                LEFT JOIN views v ON b.id = v.attachment_id
            """
            params.append(category_id)
            return await self.execute_query(query, tuple(params), fetch_one=True)
        except Exception as e:
            log_exception(logger, e, f"get_weapon_category_stats({category_id})")
            return {}

    async def get_weapon_categories(self) -> List[Dict]:
        """Get all weapon categories"""
        try:
            return await self.execute_query("SELECT id, name FROM weapon_categories ORDER BY name", fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_weapon_categories")
            return []

    async def get_underperforming_stats(self, limit: int = 20) -> List[Dict]:
        """Identify underperforming attachments (low views or low engagement)"""
        try:
            query = """
                WITH agg AS (
                    SELECT attachment_id,
                           COUNT(CASE WHEN action_type='view' THEN 1 END) AS views,
                           COUNT(CASE WHEN action_type='click' THEN 1 END) AS clicks
                    FROM attachment_metrics
                    GROUP BY attachment_id
                )
                SELECT 
                    a.id,
                    a.name,
                    COALESCE(w.name, 'Unknown') as weapon,
                    COALESCE(agg.views,0) AS views,
                    COALESCE(agg.clicks,0) AS clicks
                FROM attachments a
                LEFT JOIN agg ON agg.attachment_id = a.id
                LEFT JOIN weapons w ON a.weapon_id = w.id
                WHERE COALESCE(agg.views,0) < 20
                   OR (CAST(COALESCE(agg.clicks,0) AS FLOAT) / NULLIF(COALESCE(agg.views,0), 0)) * 100 < 5
                ORDER BY views ASC
                LIMIT %s
            """
            return await self.execute_query(query, (limit,), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_underperforming_stats")
            return []

    async def get_top_attachments(self, days: int = 1, limit: int = 5) -> List[Dict]:
        """Get most viewed attachments over a period"""
        try:
            query = """
                SELECT a.name, COALESCE(w.name,'Unknown') as weapon, COUNT(*) as views
                FROM attachment_metrics m
                JOIN attachments a ON m.attachment_id = a.id
                LEFT JOIN weapons w ON a.weapon_id = w.id
                WHERE m.action_type='view' 
                  AND m.action_date >= NOW() - make_interval(days => %s)
                GROUP BY a.id, a.name, w.name
                ORDER BY views DESC
                LIMIT %s
            """
            return await self.execute_query(query, (days, limit), fetch_all=True)
        except Exception as e:
            log_exception(logger, e, "get_top_attachments")
            return []

    async def get_report_summary(self, days: int = 1) -> Dict:
        """Get aggregated metrics for a period (views, clicks, users)"""
        try:
            query = """
                SELECT 
                    COUNT(CASE WHEN action_type='view' THEN 1 END) as views,
                    COUNT(CASE WHEN action_type='click' THEN 1 END) as clicks,
                    COUNT(DISTINCT user_id) as users
                FROM attachment_metrics
                WHERE action_date >= NOW() - make_interval(days => %s)
            """
            result = await self.execute_query(query, (days,), fetch_one=True)
            return {
                "views": result['views'] or 0,
                "clicks": result['clicks'] or 0,
                "users": result['users'] or 0
            }
        except Exception as e:
            log_exception(logger, e, "get_report_summary")
            return {"views": 0, "clicks": 0, "users": 0}
