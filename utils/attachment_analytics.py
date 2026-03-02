"""
Attachment Analytics Module
Tracking and analyzing attachment performance metrics

✨ Updated: 2026-02-27
- Fully asynchronous database operations
- Optimized for PostgreSQL with psycopg3
"""
import json
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from core.database.sql_helpers import get_date_interval, get_current_date

if TYPE_CHECKING:
    from core.database.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)

class AttachmentAnalytics:
    """
    Main class for attachment performance analytics
    """

    def __init__(self, db_adapter: 'DatabaseAdapter'):
        """
        Initialize analytics module
        
        Args:
            db_adapter: DatabaseAdapter instance (required)
        """
        if db_adapter is None:
            raise ValueError('db_adapter is required for AttachmentAnalytics')
        self.db = db_adapter
        if not hasattr(self.db, 'get_connection') or not hasattr(self.db, 'transaction'):
            raise ValueError('DatabaseAdapter must support pooled get_connection()/transaction()')
        logger.info('AttachmentAnalytics initialized with DatabaseAdapter')

    async def track_view(self, attachment_id: int, user_id: int=None, session_id: str=None) -> bool:
        """Track attachment view"""
        return await self._track_action(attachment_id, 'view', user_id, session_id)

    async def track_click(self, attachment_id: int, user_id: int=None, session_id: str=None) -> bool:
        """Track attachment click/selection"""
        return await self._track_action(attachment_id, 'click', user_id, session_id)

    async def track_share(self, attachment_id: int, user_id: int=None, session_id: str=None) -> bool:
        """Track attachment share"""
        return await self._track_action(attachment_id, 'share', user_id, session_id)

    async def track_copy(self, attachment_id: int, user_id: int=None, session_id: str=None) -> bool:
        """Track attachment copy (e.g., code copy)"""
        return await self._track_action(attachment_id, 'copy', user_id, session_id)

    async def track_rating(self, attachment_id: int, user_id: int, rating: int) -> bool:
        """Track user rating for attachment"""
        if not 1 <= rating <= 5:
            logger.error(f'Invalid rating value: {rating}')
            return False
        metadata = json.dumps({'rating': rating})
        success = await self._track_action(attachment_id, 'rate', user_id, metadata=metadata)
        if success:
            await self._update_user_engagement(user_id, attachment_id, rating=rating)
        return success

    async def _track_action(self, attachment_id: int, action_type: str, user_id: int=None, session_id: str=None, metadata: str=None) -> bool:
        """Internal method to track any action"""
        try:
            async with self.db.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('''
                        INSERT INTO attachment_metrics (
                            attachment_id, user_id, action_type, 
                            session_id, metadata
                        ) VALUES (%s, %s, %s, %s, %s)
                    ''', (attachment_id, user_id, action_type, session_id, metadata))
                    
                    if action_type == 'view':
                        await cursor.execute('UPDATE attachments SET total_views = total_views + 1 WHERE id = %s', (attachment_id,))
                    elif action_type == 'click':
                        await cursor.execute('UPDATE attachments SET total_clicks = total_clicks + 1 WHERE id = %s', (attachment_id,))
                    
                    if user_id:
                        await self._update_user_engagement(user_id, attachment_id, action_type, conn)
            return True
        except Exception as e:
            logger.error(f'Error tracking action: {e}')
            return False

    async def _update_user_engagement(self, user_id: int, attachment_id: int, action_type: str=None, conn=None, rating: int=None) -> None:
        """Update user engagement metrics"""
        try:
            if conn is not None:
                async with conn.cursor() as cursor:
                    await self._execute_engagement_update(cursor, user_id, attachment_id, action_type, rating)
            else:
                async with self.db.transaction() as trans_conn:
                    async with trans_conn.cursor() as cursor:
                        await self._execute_engagement_update(cursor, user_id, attachment_id, action_type, rating)
        except Exception as e:
            logger.error(f'Error updating user engagement: {e}')

    async def _execute_engagement_update(self, cursor, user_id: int, attachment_id: int, action_type: str=None, rating: int=None):
        """Helper method for executing engagement update"""
        await cursor.execute('''
            SELECT total_views, total_clicks 
            FROM user_attachment_engagement
            WHERE user_id = %s AND attachment_id = %s
        ''', (user_id, attachment_id))
        
        existing = await cursor.fetchone()
        if existing:
            updates = []
            params = []
            if action_type == 'view':
                updates.append('total_views = COALESCE(total_views, 0) + 1')
                updates.append('last_view_date = CURRENT_TIMESTAMP')
            elif action_type == 'click':
                updates.append('total_clicks = COALESCE(total_clicks, 0) + 1')
                updates.append('last_view_date = CURRENT_TIMESTAMP')
            
            if rating is not None:
                updates.append('rating = %s')
                params.append(rating)
            
            if updates:
                sql = f"UPDATE user_attachment_engagement SET {', '.join(updates)} WHERE user_id = %s AND attachment_id = %s"
                params.extend([user_id, attachment_id])
                await cursor.execute(sql, params)
        else:
            await cursor.execute('''
                INSERT INTO user_attachment_engagement (
                    user_id, attachment_id, first_view_date, 
                    last_view_date, total_views, total_clicks, rating
                ) VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s)
            ''', (user_id, attachment_id, 1 if action_type == 'view' else 0, 1 if action_type == 'click' else 0, rating))

    async def get_attachment_stats(self, attachment_id: int, days: int=30) -> Dict:
        """Get statistics for specific attachment"""
        stats = {
            'attachment_id': attachment_id, 
            'period_days': days, 
            'total_views': 0, 
            'total_clicks': 0, 
            'total_shares': 0, 
            'unique_users': 0, 
            'engagement_rate': 0, 
            'avg_rating': 0, 
            'daily_stats': [], 
            'top_users': []
        }
        
        try:
            days = max(1, min(int(days), 365))
        except (ValueError, TypeError):
            days = 30
            
        stats['period_days'] = days
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    date_filter = get_date_interval(days)
                    
                    # Core stats
                    await cursor.execute(f"""
                        SELECT 
                            COUNT(CASE WHEN action_type = 'view' THEN 1 END) as views,
                            COUNT(CASE WHEN action_type = 'click' THEN 1 END) as clicks,
                            COUNT(CASE WHEN action_type = 'share' THEN 1 END) as shares,
                            COUNT(DISTINCT user_id) as unique_users
                        FROM attachment_metrics
                        WHERE attachment_id = %s
                        AND DATE(action_date) >= {date_filter}
                    """, (attachment_id,))
                    
                    result = await cursor.fetchone()
                    if result:
                        stats['total_views'] = result['views'] or 0
                        stats['total_clicks'] = result['clicks'] or 0
                        stats['total_shares'] = result['shares'] or 0
                        stats['unique_users'] = result['unique_users'] or 0
                        if stats['total_views'] > 0:
                            stats['engagement_rate'] = (float(stats['total_clicks']) / stats['total_views']) * 100

                    # Average rating
                    await cursor.execute('''
                        SELECT AVG(rating) as avg_rating
                        FROM user_attachment_engagement
                        WHERE attachment_id = %s AND rating IS NOT NULL
                    ''', (attachment_id,))
                    result = await cursor.fetchone()
                    avg_rating = result['avg_rating'] if result and result.get('avg_rating') else 0
                    stats['avg_rating'] = round(float(avg_rating), 2)

                    # Daily stats
                    await cursor.execute(f"""
                        SELECT 
                            DATE(action_date) as date,
                            COUNT(CASE WHEN action_type = 'view' THEN 1 END) as views,
                            COUNT(CASE WHEN action_type = 'click' THEN 1 END) as clicks,
                            COUNT(DISTINCT user_id) as users
                        FROM attachment_metrics
                        WHERE attachment_id = %s
                        AND DATE(action_date) >= {date_filter}
                        GROUP BY DATE(action_date)
                        ORDER BY date DESC
                        LIMIT 7
                    """, (attachment_id,))
                    
                    async for row in cursor:
                        stats['daily_stats'].append({
                            'date': row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date']), 
                            'views': row['views'], 
                            'clicks': row['clicks'], 
                            'users': row['users']
                        })

                    # Top Users
                    await cursor.execute('''
                        SELECT 
                            u.username,
                            uae.total_views,
                            uae.total_clicks,
                            uae.rating
                        FROM user_attachment_engagement uae
                        LEFT JOIN users u ON uae.user_id = u.user_id
                        WHERE uae.attachment_id = %s
                        ORDER BY uae.total_views DESC
                        LIMIT 5
                    ''', (attachment_id,))
                    
                    async for row in cursor:
                        stats['top_users'].append({
                            'username': row['username'] or 'Unknown', 
                            'views': row['total_views'], 
                            'clicks': row['total_clicks'], 
                            'rating': row['rating']
                        })
                        
        except Exception as e:
            logger.error(f'Error getting attachment stats: {e}')
            
        return stats

    async def get_weapon_stats(self, weapon_id: int, mode: str='mp') -> Dict:
        """Get aggregated statistics for all attachments of a weapon"""
        stats = {
            'weapon_id': weapon_id, 
            'mode': mode, 
            'total_attachments': 0, 
            'total_views': 0, 
            'total_interactions': 0, 
            'top_attachments': [], 
            'bottom_attachments': []
        }
        
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('''
                        SELECT 
                            a.id,
                            a.name,
                            a.code,
                            a.total_views,
                            a.total_clicks,
                            a.avg_rating,
                            ap.popularity_score
                        FROM attachments a
                        LEFT JOIN attachment_performance ap ON a.id = ap.attachment_id
                        WHERE a.weapon_id = %s AND a.mode = %s
                        ORDER BY a.total_views DESC
                    ''', (weapon_id, mode))
                    
                    attachments = await cursor.fetchall()
                    stats['total_attachments'] = len(attachments)
                    for att in attachments:
                        stats['total_views'] += att['total_views'] or 0
                        stats['total_interactions'] += (att['total_views'] or 0) + (att['total_clicks'] or 0)
                    
                    if attachments:
                        for att in attachments[:5]:
                            stats['top_attachments'].append({
                                'id': att['id'], 'name': att['name'], 'code': att['code'], 
                                'views': att['total_views'] or 0, 'clicks': att['total_clicks'] or 0, 
                                'rating': att['avg_rating'] or 0, 'popularity': att['popularity_score'] or 0
                            })
                        for att in attachments[-3:]:
                            stats['bottom_attachments'].append({
                                'id': att['id'], 'name': att['name'], 'code': att['code'], 
                                'views': att['total_views'] or 0
                            })
        except Exception as e:
            logger.error(f'Error getting weapon stats: {e}')
            
        return stats

    async def calculate_performance_scores(self) -> None:
        """Calculate and update performance scores for all attachments"""
        try:
            async with self.db.transaction() as conn:
                async with conn.cursor() as cursor:
                    date_filter = get_date_interval(7)
                    await cursor.execute(f"""
                        SELECT DISTINCT a.id
                        FROM attachments a
                        JOIN attachment_metrics am ON a.id = am.attachment_id
                        WHERE DATE(am.action_date) >= {date_filter}
                    """)
                    
                    attachment_ids = [row['id'] for row in await cursor.fetchall()]
                    current_date = get_current_date()
                    
                    for att_id in attachment_ids:
                        scores = await self._calculate_single_attachment_scores(att_id)
                        await cursor.execute(f"""
                            INSERT INTO attachment_performance (
                                attachment_id, performance_date,
                                popularity_score, trending_score,
                                engagement_rate, quality_score
                            ) VALUES (%s, {current_date}, %s, %s, %s, %s)
                            ON CONFLICT (attachment_id, performance_date)
                            DO UPDATE SET
                                popularity_score = EXCLUDED.popularity_score,
                                trending_score = EXCLUDED.trending_score,
                                engagement_rate = EXCLUDED.engagement_rate,
                                quality_score = EXCLUDED.quality_score
                        """, (att_id, scores['popularity'], scores['trending'], scores['engagement'], scores['quality']))
                    
                    await self._update_rankings(cursor)
                    logger.info(f'✅ Updated performance scores for {len(attachment_ids)} attachments')
        except Exception as e:
            logger.error(f'Error calculating performance scores: {e}')

    async def _calculate_single_attachment_scores(self, attachment_id: int) -> Dict:
        """Calculate performance scores for single attachment"""
        scores = {'popularity': 0, 'trending': 0, 'engagement': 0, 'quality': 0}
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    date_filter = get_date_interval(30)
                    await cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total_actions,
                            COUNT(DISTINCT user_id) as unique_users,
                            COUNT(CASE WHEN action_type = 'view' THEN 1 END) as views,
                            COUNT(CASE WHEN action_type = 'click' THEN 1 END) as clicks,
                            COUNT(CASE WHEN action_type = 'share' THEN 1 END) as shares
                        FROM attachment_metrics
                        WHERE attachment_id = %s
                        AND DATE(action_date) >= {date_filter}
                    """, (attachment_id,))
                    
                    result = await cursor.fetchone()
                    if result:
                        views = result['views'] or 0
                        clicks = result['clicks'] or 0
                        shares = result['shares'] or 0
                        users = result['unique_users'] or 0
                        scores['popularity'] = (views * 1 + clicks * 3 + shares * 5 + users * 2) / 10
                        if views > 0:
                            scores['engagement'] = (clicks + shares) / views * 100

                    # Trending
                    date_filter_7 = get_date_interval(7)
                    date_filter_14 = get_date_interval(14)
                    date_filter_8 = get_date_interval(8)
                    await cursor.execute(f"""
                        SELECT 
                            COUNT(CASE WHEN DATE(action_date) >= {date_filter_7} THEN 1 END) as recent,
                            COUNT(CASE WHEN DATE(action_date) BETWEEN {date_filter_14} AND {date_filter_8} THEN 1 END) as previous
                        FROM attachment_metrics
                        WHERE attachment_id = %s
                    """, (attachment_id,))
                    
                    result = await cursor.fetchone()
                    recent = result['recent'] if result else 0
                    previous = result['previous'] if result else 0
                    if previous > 0:
                        growth_rate = (recent - previous) / previous * 100
                        scores['trending'] = max(0, min(100, growth_rate))
                    elif recent > 0:
                        scores['trending'] = 50

                    # Quality
                    await cursor.execute('''
                        SELECT AVG(rating) as avg_rating, COUNT(rating) as rating_count
                        FROM user_attachment_engagement
                        WHERE attachment_id = %s AND rating IS NOT NULL
                    ''', (attachment_id,))
                    
                    result = await cursor.fetchone()
                    avg_rating = result['avg_rating'] if result and result.get('avg_rating') else 0
                    rating_count = result['rating_count'] if result and result.get('rating_count') else 0
                    if avg_rating:
                        weight = min(1.0, float(rating_count) / 10)
                        scores['quality'] = float(avg_rating) / 5 * 100 * weight

                    # Top flags
                    await cursor.execute('SELECT is_top, is_season_top FROM attachments WHERE id = %s', (attachment_id,))
                    result = await cursor.fetchone()
                    if result:
                        if result['is_top']: scores['quality'] = min(100, scores['quality'] + 10)
                        if result['is_season_top']: scores['quality'] = min(100, scores['quality'] + 15)
                        
        except Exception as e:
            logger.error(f'Error calculating scores for attachment {attachment_id}: {e}')
            
        return scores

    async def _update_rankings(self, cursor) -> None:
        """Update attachment rankings"""
        current_date = get_current_date()
        
        # Weapon rank
        await cursor.execute(f"""
            WITH RankedAttachments AS (
                SELECT a.id, ROW_NUMBER() OVER (PARTITION BY a.weapon_id ORDER BY ap.popularity_score DESC) as weapon_rank
                FROM attachments a
                JOIN attachment_performance ap ON a.id = ap.attachment_id
                WHERE ap.performance_date = {current_date}
            )
            UPDATE attachment_performance
            SET rank_in_weapon = (SELECT weapon_rank FROM RankedAttachments WHERE id = attachment_performance.attachment_id)
            WHERE performance_date = {current_date}
        """)
        
        # Overall rank
        await cursor.execute(f"""
            WITH RankedAttachments AS (
                SELECT attachment_id, ROW_NUMBER() OVER (ORDER BY popularity_score DESC) as overall_rank
                FROM attachment_performance
                WHERE performance_date = {current_date}
            )
            UPDATE attachment_performance
            SET rank_overall = (SELECT overall_rank FROM RankedAttachments WHERE attachment_id = attachment_performance.attachment_id)
            WHERE performance_date = {current_date}
        """)

    async def get_trending_attachments(self, limit: int=10) -> List[Dict]:
        """Get currently trending attachments"""
        trending = []
        try:
            current_date = get_current_date()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT 
                            a.id, a.name, a.code, w.name as weapon_name, wc.name as category_name,
                            ap.trending_score, ap.popularity_score, a.total_views
                        FROM attachment_performance ap
                        JOIN attachments a ON ap.attachment_id = a.id
                        JOIN weapons w ON a.weapon_id = w.id
                        JOIN weapon_categories wc ON w.category_id = wc.id
                        WHERE ap.performance_date = {current_date}
                        AND ap.trending_score > 0
                        AND a.name NOT ILIKE '%%test%%'
                        ORDER BY ap.trending_score DESC
                        LIMIT %s
                    """, (limit,))
                    
                    async for row in cursor:
                        trending.append({
                            'id': row['id'], 'name': row['name'], 'code': row['code'], 
                            'weapon': row['weapon_name'], 'category': row['category_name'], 
                            'trending_score': row['trending_score'], 
                            'popularity_score': row['popularity_score'], 
                            'total_views': row['total_views']
                        })
        except Exception as e:
            logger.error(f'Error getting trending attachments: {e}')
            
        return trending

    async def get_underperforming_attachments(self, limit: int=10) -> List[Dict]:
        """Get attachments that need attention"""
        underperforming = []
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('SELECT AVG(total_views) as avg FROM attachments WHERE total_views > 0')
                    result = await cursor.fetchone()
                    avg_views = float(result['avg']) if result and result.get('avg') else 100.0
                    threshold = max(50, avg_views * 0.3)
                    
                    await cursor.execute(f"""
                        SELECT 
                            a.id, a.name, a.code, COALESCE(w.name, 'Unknown') as weapon_name,
                            a.total_views, a.total_clicks,
                            CASE 
                                WHEN a.image_file_id IS NULL THEN 'No Image'
                                WHEN a.total_views < %s THEN 'Low Views'
                                WHEN a.total_views >= 20 AND CAST(a.total_clicks AS REAL) / NULLIF(a.total_views, 0) * 100 < 5.0 THEN 'Low Engagement'
                                ELSE 'Other'
                            END as issue,
                            CASE WHEN a.image_file_id IS NULL THEN 3 WHEN a.total_views < %s THEN 2 ELSE 1 END as priority
                        FROM attachments a
                        LEFT JOIN weapons w ON a.weapon_id = w.id
                        WHERE (a.image_file_id IS NULL OR a.total_views < %s OR (a.total_views >= 20 AND CAST(a.total_clicks AS REAL) / NULLIF(a.total_views, 0) * 100 < 5.0))
                        AND a.name NOT ILIKE '%%test%%'
                        ORDER BY priority DESC, a.total_views ASC
                        LIMIT %s
                    """, (threshold, threshold, threshold, limit))
                    
                    async for row in cursor:
                        underperforming.append({
                            'id': row['id'], 'name': row['name'], 'code': row['code'], 
                            'weapon': row['weapon_name'], 'views': row['total_views'] or 0, 
                            'clicks': row['total_clicks'] or 0, 'issue': row['issue'], 
                            'priority': row['priority']
                        })
        except Exception as e:
            logger.error(f'Error getting underperforming attachments: {e}')
            
        return underperforming