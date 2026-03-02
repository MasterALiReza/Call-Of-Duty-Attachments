"""
Database mixin for Analytics, Engagement, Search, and Voting operations.
"""

import logging
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.analytics_mixin')


class AnalyticsDatabaseMixin:
    """
    Mixin containing analytics, engagement, search, and voting operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    # ==========================================================================
    # Voting & Engagement
    # ==========================================================================
    
    def vote_attachment(self, user_id: int, attachment_id: int, vote: int) -> Dict:
        """
        ثبت یا تغییر رأی کاربر برای اتچمنت (Atomic UPSERT)
        """
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                # ATOMIC UPSERT 
                cursor.execute("""
                    SELECT rating FROM user_attachment_engagement
                    WHERE user_id = %s AND attachment_id = %s
                    FOR UPDATE NOWAIT
                """, (user_id, attachment_id))
                
                existing = cursor.fetchone()
                previous_vote = existing['rating'] if existing else None
                
                if previous_vote is None:
                    new_rating = vote if vote != 0 else None
                    action = "added" if vote != 0 else "none"
                elif previous_vote == vote:
                    new_rating = None
                    action = "removed"
                elif vote == 0:
                    new_rating = None
                    action = "removed"
                else:
                    new_rating = vote
                    action = "changed"
                
                cursor.execute("""
                    INSERT INTO user_attachment_engagement 
                    (user_id, attachment_id, rating, first_view_date, last_view_date)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (user_id, attachment_id) DO UPDATE
                    SET rating = EXCLUDED.rating,
                        last_view_date = NOW()
                """, (user_id, attachment_id, new_rating))
                
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN rating = 1 THEN 1 END) as likes,
                        COUNT(CASE WHEN rating = -1 THEN 1 END) as dislikes
                    FROM user_attachment_engagement
                    WHERE attachment_id = %s AND rating IS NOT NULL
                """, (attachment_id,))
                
                stats = cursor.fetchone()
                like_count = stats['likes']
                dislike_count = stats['dislikes']
                cursor.close()
                
                logger.info(f"✅ Vote (atomic): user={user_id}, att={attachment_id}, {previous_vote}→{new_rating}, action={action}")
                
                return {
                    'success': True,
                    'action': action,
                    'previous_vote': previous_vote,
                    'new_vote': new_rating if new_rating is not None else 0,
                    'like_count': like_count,
                    'dislike_count': dislike_count
                }
                
        except Exception as e:
            log_exception(logger, e, f"vote_attachment({user_id}, {attachment_id})")
            return {'success': False, 'action': 'error', 'error': str(e)}

    def get_user_vote(self, attachment_id: int, user_id: int) -> Optional[int]:
        """دریافت رأی فعلی کاربر"""
        try:
            query = """
                SELECT rating FROM user_attachment_engagement
                WHERE user_id = %s AND attachment_id = %s
            """
            result = self.execute_query(query, (user_id, attachment_id), fetch_one=True)
            return result['rating'] if result else None
        except Exception as e:
            log_exception(logger, e, f"get_user_vote({attachment_id}, {user_id})")
            return None

    def track_attachment_view(self, user_id: int, attachment_id: int) -> bool:
        """ثبت بازدید اتچمنت"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_views FROM user_attachment_engagement
                    WHERE user_id = %s AND attachment_id = %s
                """, (user_id, attachment_id))
                
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE user_attachment_engagement
                        SET total_views = COALESCE(total_views, 0) + 1,
                            last_view_date = NOW()
                        WHERE user_id = %s AND attachment_id = %s
                    """, (user_id, attachment_id))
                else:
                    cursor.execute("""
                        INSERT INTO user_attachment_engagement
                        (user_id, attachment_id, total_views, first_view_date, last_view_date)
                        VALUES (%s, %s, 1, NOW(), NOW())
                    """, (user_id, attachment_id))
                cursor.close()
                return True
        except Exception as e:
            log_exception(logger, e, f"track_attachment_view({user_id}, {attachment_id})")
            return False
            
    def track_attachment_copy(self, user_id: int, attachment_id: int) -> bool:
        """ثبت کپی کد اتچمنت"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT total_clicks FROM user_attachment_engagement
                    WHERE user_id = %s AND attachment_id = %s
                """, (user_id, attachment_id))
                
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE user_attachment_engagement
                        SET total_clicks = COALESCE(total_clicks, 0) + 1,
                            last_view_date = NOW()
                        WHERE user_id = %s AND attachment_id = %s
                    """, (user_id, attachment_id))
                else:
                    cursor.execute("""
                        INSERT INTO user_attachment_engagement
                        (user_id, attachment_id, total_clicks, first_view_date, last_view_date)
                        VALUES (%s, %s, 1, NOW(), NOW())
                    """, (user_id, attachment_id))
                cursor.close()
                return True
        except Exception as e:
            log_exception(logger, e, f"track_attachment_copy({user_id}, {attachment_id})")
            return False
            
    def get_popular_attachments(self, category: str = None, weapon: str = None,
                               mode: str = None, limit: int = 10, days: int = 14,
                               suggested_only: bool = False) -> List[Dict]:
        """دریافت محبوب‌ترین اتچمنت‌ها بر اساس رأی و تعامل"""
        try:
            where_clauses = []
            params = []
            
            if category:
                where_clauses.append("wc.name = %s")
                params.append(category)
            
            if weapon:
                where_clauses.append("w.name = %s")
                params.append(weapon)
            
            if mode:
                where_clauses.append("a.mode = %s")
                params.append(mode)
            
            where_clauses.append("uae.last_view_date >= NOW() - make_interval(days => %s)")
            params.append(days)
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            join_suggested = "JOIN suggested_attachments sa ON a.id = sa.attachment_id AND sa.mode = a.mode" if suggested_only else ""
            
            query = f"""
                SELECT 
                    a.id, a.name, a.code, a.mode,
                    w.name as weapon, wc.name as category,
                    COUNT(CASE WHEN uae.rating = 1 THEN 1 END) as likes,
                    COUNT(CASE WHEN uae.rating = -1 THEN 1 END) as dislikes,
                    COUNT(DISTINCT uae.user_id) as unique_users,
                    SUM(COALESCE(uae.total_views, 0)) as views,
                    SUM(COALESCE(uae.total_clicks, 0)) as total_clicks,
                    (COUNT(CASE WHEN uae.rating = 1 THEN 1 END) - 
                     COUNT(CASE WHEN uae.rating = -1 THEN 1 END)) as net_score
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories wc ON w.category_id = wc.id
                {join_suggested}
                LEFT JOIN user_attachment_engagement uae ON a.id = uae.attachment_id
                {where_sql}
                GROUP BY a.id, a.name, a.code, a.mode, w.name, wc.name
                ORDER BY net_score DESC, views DESC, likes DESC
                LIMIT %s
            """
            params.append(limit)
            results = self.execute_query(query, tuple(params), fetch_all=True)
            return results
        except Exception as e:
            log_exception(logger, e, "get_popular_attachments")
            return []
            
    def get_attachment_stats(self, attachment_id: int, period: str = 'all') -> Dict:
        """دریافت آمار بازخورد اتچمنت"""
        try:
            date_filter = ""
            if period == 'week':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '7 days'"
            elif period == 'month':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '30 days'"
            elif period == 'year':
                date_filter = "AND last_view_date >= NOW() - INTERVAL '365 days'"
            
            query_votes = f"""
                SELECT 
                    SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as likes,
                    SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END) as dislikes,
                    COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as total_votes,
                    SUM(COALESCE(total_views, 0)) as total_views,
                    SUM(COALESCE(total_clicks, 0)) as total_clicks,
                    COUNT(DISTINCT user_id) as unique_users
                FROM user_attachment_engagement
                WHERE attachment_id = %s {date_filter}
            """
            vote_stats = self.execute_query(query_votes, (attachment_id,), fetch_one=True)
            
            likes = vote_stats['likes'] or 0
            dislikes = vote_stats['dislikes'] or 0
            total_votes = vote_stats['total_votes'] or 0
            
            like_ratio = (likes / total_votes * 100) if total_votes > 0 else 0
            dislike_ratio = (dislikes / total_votes * 100) if total_votes > 0 else 0
            
            return {
                'like_count': likes,
                'dislike_count': dislikes,
                'total_votes': total_votes,
                'like_ratio': round(like_ratio, 1),
                'dislike_ratio': round(dislike_ratio, 1),
                'net_score': likes - dislikes,
                'total_views': vote_stats['total_views'] or 0,
                'total_clicks': vote_stats['total_clicks'] or 0,
                'unique_users': vote_stats['unique_users'] or 0,
                'period': period
            }
        except Exception as e:
            log_exception(logger, e, f"get_attachment_stats({attachment_id})")
            return {
                'like_count': 0, 'dislike_count': 0, 'total_votes': 0,
                'like_ratio': 0, 'dislike_ratio': 0, 'net_score': 0,
                'total_views': 0, 'total_clicks': 0, 'unique_users': 0,
                'period': period
            }

    # ==========================================================================
    # Search Analytics
    # ==========================================================================

    def search_attachments_like(self, query: str, limit: int = 30) -> List[Dict]:
        """جستجوی ساده با LIKE (fallback)"""
        try:
            normalized_query = '%' + ''.join(c.lower() for c in query if c.isalnum()) + '%'
            query_sql = """
                SELECT c.name as category, w.name as weapon, a.mode,
                       a.code, a.name as att_name, a.image_file_id as image,
                       a.is_top, a.is_season_top
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE LOWER(REPLACE(REPLACE(a.name, ' ', ''), '-', '')) LIKE %s
                   OR LOWER(REPLACE(REPLACE(w.name, ' ', ''), '-', '')) LIKE %s
                   OR LOWER(a.code) LIKE %s
                ORDER BY a.is_season_top DESC, a.is_top DESC
                LIMIT %s
            """
            results = self.execute_query(
                query_sql, 
                (normalized_query, normalized_query, normalized_query, limit),
                fetch_all=True
            )
            
            items = []
            for row in results:
                items.append({
                    'category': row['category'],
                    'weapon': row['weapon'],
                    'mode': row['mode'],
                    'attachment': {
                        'code': row['code'],
                        'name': row['att_name'],
                        'image': row['image'],
                        'is_top': row.get('is_top', False),
                        'is_season_top': row.get('is_season_top', False)
                    }
                })
            return items
        except Exception as e:
            log_exception(logger, e, f"search_attachments_like({query})")
            return []
    
    def search_attachments_fts(self, query: str, limit: int = 30) -> List[Dict]:
        """جستجوی پیشرفته با pg_trgm (PostgreSQL)"""
        try:
            q = (query or '').strip()
            if not q:
                return []
            if len(q) < 3 or q.isdigit():
                return self.search_attachments_like(query, limit)

            query_sql = """
                SELECT 
                    c.name as category,
                    w.name as weapon,
                    a.mode,
                    a.code,
                    a.name as att_name,
                    a.image_file_id as image,
                    a.is_top,
                    a.is_season_top,
                    GREATEST(
                        similarity(a.name, %s),
                        similarity(w.name, %s),
                        similarity(a.code, %s)
                    ) as score
                FROM attachments a
                JOIN weapons w ON a.weapon_id = w.id
                JOIN weapon_categories c ON w.category_id = c.id
                WHERE 
                    a.name %% %s 
                    OR w.name %% %s
                    OR a.code %% %s
                    OR a.code ILIKE %s
                    OR a.name ILIKE %s
                    OR w.name ILIKE %s
                ORDER BY score DESC, a.is_season_top DESC, a.is_top DESC
                LIMIT %s
            """
            like_pattern = f"%{q}%"
            results = self.execute_query(
                query_sql,
                (q, q, q, q, q, q, like_pattern, like_pattern, like_pattern, limit),
                fetch_all=True
            )
            
            items = []
            for row in results:
                items.append({
                    'category': row['category'],
                    'weapon': row['weapon'],
                    'mode': row['mode'],
                    'attachment': {
                        'code': row['code'],
                        'name': row['att_name'],
                        'image': row['image'],
                        'is_top': row.get('is_top', False),
                        'is_season_top': row.get('is_season_top', False)
                    }
                })
            if not items:
                return self.search_attachments_like(query, limit)
            return items
        except Exception as e:
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
            return self.search_attachments_like(query, limit)
    
    def search_attachments(self, query: str) -> List[Dict]:
        """جستجوی هوشمند (wrapper)"""
        try:
            return self.search_attachments_fts(query, limit=30)
        except Exception as e:
            log_exception(logger, e, f"search_attachments({query})")
            return []
            
    def track_search(self, user_id: int, query: str, results_count: int, 
                    execution_time_ms: float) -> bool:
        """ثبت جستجو برای Analytics"""
        try:
            query_normalized = query.strip().lower()
            if not query_normalized or len(query_normalized) < 2:
                return False
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO search_history (user_id, query, results_count, execution_time_ms)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, query_normalized, results_count, execution_time_ms))
                
                cursor.execute("""
                    INSERT INTO popular_searches (query, search_count, last_searched)
                    VALUES (%s, 1, NOW())
                    ON CONFLICT(query) DO UPDATE SET
                        search_count = popular_searches.search_count + 1,
                        last_searched = NOW()
                """, (query_normalized,))
                cursor.close()
            return True
        except Exception as e:
            logger.warning(f"Error tracking search: {e}")
            return False
    
    def get_popular_searches(self, limit: int = 5) -> List[str]:
        """دریافت محبوب‌ترین جستجوها"""
        try:
            query = """
                SELECT query
                FROM popular_searches
                ORDER BY search_count DESC, last_searched DESC
                LIMIT %s
            """
            results = self.execute_query(query, (limit,), fetch_all=True)
            return [r['query'] for r in results]
        except Exception as e:
            log_exception(logger, e, "get_popular_searches")
            return []
    
    def get_search_analytics(self, days: int = 30) -> Dict:
        """دریافت آمار جستجو"""
        try:
            query_stats = """
                SELECT 
                    COUNT(*) as total_searches,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(results_count) as avg_results,
                    AVG(execution_time_ms) as avg_time_ms,
                    SUM(CASE WHEN results_count = 0 THEN 1 ELSE 0 END) as zero_results
                FROM search_history
                WHERE created_at >= NOW() - make_interval(days => %s)
            """
            stats = self.execute_query(query_stats, (days,), fetch_one=True)
            
            query_top = """
                SELECT query, COUNT(*) as count
                FROM search_history
                WHERE created_at >= NOW() - make_interval(days => %s)
                GROUP BY query
                ORDER BY count DESC
                LIMIT 10
            """
            top_queries = self.execute_query(query_top, (days,), fetch_all=True)
            
            query_failed = """
                SELECT query, COUNT(*) as count
                FROM search_history
                WHERE results_count = 0
                  AND created_at >= NOW() - make_interval(days => %s)
                GROUP BY query
                ORDER BY count DESC
                LIMIT 10
            """
            failed_queries = self.execute_query(query_failed, (days,), fetch_all=True)
            
            total = stats['total_searches'] or 1
            zero_rate = (stats['zero_results'] / total) * 100 if total > 0 else 0
            
            return {
                'total_searches': stats['total_searches'] or 0,
                'unique_users': stats['unique_users'] or 0,
                'avg_results': round(stats['avg_results'] or 0, 1),
                'avg_time_ms': round(stats['avg_time_ms'] or 0, 1),
                'zero_results': stats['zero_results'] or 0,
                'zero_rate': round(zero_rate, 1),
                'top_queries': [{'query': q['query'], 'count': q['count']} for q in top_queries],
                'failed_queries': [{'query': q['query'], 'count': q['count']} for q in failed_queries]
            }
        except Exception as e:
            log_exception(logger, e, "get_search_analytics")
            return {
                'total_searches': 0, 'unique_users': 0, 'avg_results': 0, 'avg_time_ms': 0,
                'zero_results': 0, 'zero_rate': 0, 'top_queries': [], 'failed_queries': []
            }

    # ==========================================================================
    # Feedback & General Statistics
    # ==========================================================================
    
    def add_feedback(self, user_id: int, rating: int, category: str = "general", message: str = "") -> bool:
        """ثبت بازخورد کاربر"""
        try:
            query = """
                INSERT INTO feedback (user_id, rating, category, message)
                VALUES (%s, %s, %s, %s)
            """
            self.execute_query(query, (user_id, rating, category, message))
            logger.info(f"✅ Feedback added: user={user_id}, rating={rating}")
            return True
        except Exception as e:
            log_exception(logger, e, "add_feedback")
            return False
    
    def get_feedback_stats(self) -> Dict:
        """آمار بازخوردها - بهینه شده"""
        try:
            query = """
                SELECT 
                    rating,
                    COUNT(*) as count,
                    (SELECT COUNT(*) FROM feedback) as total,
                    (SELECT AVG(rating) FROM feedback) as avg_rating
                FROM feedback
                GROUP BY rating
            """
            results = self.execute_query(query, fetch_all=True)
            
            if results:
                total = results[0]['total']
                avg_rating = results[0]['avg_rating'] or 0
                distribution = {str(row['rating']): row['count'] for row in results}
            else:
                total = 0
                avg_rating = 0
                distribution = {}
            
            return {
                "average_rating": round(float(avg_rating), 2),
                "total": total,
                "rating_distribution": distribution
            }
        except Exception as e:
            log_exception(logger, e, "get_feedback_stats")
            return {"average_rating": 0, "total": 0, "rating_distribution": {}}
            
    def get_statistics(self) -> Dict:
        """دریافت آمار کامل و تفصیلی دیتابیس"""
        try:
            stats = {
                'total_weapons': 0,
                'total_attachments': 0,
                'total_attachments_br': 0,
                'total_attachments_mp': 0,
                'total_top_attachments': 0,
                'total_season_attachments': 0,
                'total_guides': 0,
                'total_guides_br': 0,
                'total_guides_mp': 0,
                'total_channels': 0,
                'total_admins': 0,
                'categories': {},
                'weapons_with_attachments': 0,
                'weapons_without_attachments': 0
            }
            
            stats['total_weapons'] = self.execute_query("SELECT COUNT(*) as count FROM weapons", fetch_one=True)['count']
            stats['total_attachments'] = self.execute_query("SELECT COUNT(*) as count FROM attachments", fetch_one=True)['count']
            stats['total_attachments_br'] = self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE mode = 'br'", fetch_one=True)['count']
            stats['total_attachments_mp'] = self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE mode = 'mp'", fetch_one=True)['count']
            stats['total_top_attachments'] = self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE is_top = TRUE", fetch_one=True)['count']
            stats['total_season_attachments'] = self.execute_query("SELECT COUNT(*) as count FROM attachments WHERE is_season_top = TRUE", fetch_one=True)['count']
            
            return stats
            
        except Exception as e:
            log_exception(logger, e, "get_statistics")
            return {}
    
    def submit_attachment_feedback(self, user_id: int, attachment_id: int, 
                                   feedback_text: str) -> bool:
        """ثبت بازخورد متنی برای اتچمنت"""
        try:
            feedback_text = feedback_text[:500].strip()
            
            if not feedback_text:
                logger.warning(f"Empty feedback rejected: user={user_id}, att={attachment_id}")
                return False
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 1 FROM user_attachment_engagement
                    WHERE user_id = %s AND attachment_id = %s
                """, (user_id, attachment_id))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE user_attachment_engagement
                        SET feedback = %s, last_view_date = NOW()
                        WHERE user_id = %s AND attachment_id = %s
                    """, (feedback_text, user_id, attachment_id))
                else:
                    cursor.execute("""
                        INSERT INTO user_attachment_engagement
                        (user_id, attachment_id, feedback, first_view_date, last_view_date)
                        VALUES (%s, %s, %s, NOW(), NOW())
                    """, (user_id, attachment_id, feedback_text))
                
                cursor.close()
                logger.info(f"✅ Feedback submitted: user={user_id}, att={attachment_id}")
                return True
                
        except Exception as e:
            log_exception(logger, e, f"submit_attachment_feedback({user_id}, {attachment_id})")
            return False
