"""
Database mixin for Tickets and FAQ System.
"""
import logging
from .base_repository import BaseRepository
from typing import Optional, Dict, List
from utils.logger import log_exception
logger = logging.getLogger('database.support_mixin')

class SupportRepository(BaseRepository):
    """
    Mixin containing Tickets and FAQ operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    async def add_ticket(self, user_id: int, category: str, subject: str, description: str, priority: str='medium', attachments: List[str]=None) -> Optional[int]:
        """ایجاد تیکت جدید"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO tickets (user_id, category, subject, description, priority)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user_id, category, subject, description, priority))
                    result = await cursor.fetchone()
                    ticket_id = result['id']
                    if attachments:
                        for file_id in attachments:
                            await cursor.execute("""
                                INSERT INTO ticket_attachments (ticket_id, file_id, file_type)
                                VALUES (%s, %s, 'photo')
                            """, (ticket_id, file_id))
                logger.info(f'✅ Ticket created: {ticket_id}')
                return ticket_id
        except Exception as e:
            log_exception(logger, e, 'add_ticket')
            return None

    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """دریافت اطلاعات یک تیکت"""
        try:
            query_ticket = 'SELECT * FROM tickets WHERE id = %s'
            result = await self.execute_query(query_ticket, (ticket_id,), fetch_one=True)
            if not result:
                logger.warning(f'Ticket {ticket_id} not found')
                return None
            ticket = dict(result)
            query_att = '\n                SELECT file_id FROM ticket_attachments \n                WHERE ticket_id = %s AND reply_id IS NULL\n            '
            attachments = await self.execute_query(query_att, (ticket_id,), fetch_all=True)
            ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            return ticket
        except Exception as e:
            log_exception(logger, e, f'get_ticket({ticket_id})')
            return None

    async def get_user_tickets(self, user_id: int, status: Optional[str]=None) -> List[Dict]:
        """دریافت تیکت\u200cهای کاربر"""
        try:
            if status:
                query = '\n                    SELECT * FROM tickets \n                    WHERE user_id = %s AND status = %s \n                    ORDER BY created_at DESC\n                '
                results = await self.execute_query(query, (user_id, status), fetch_all=True)
            else:
                query = '\n                    SELECT * FROM tickets \n                    WHERE user_id = %s \n                    ORDER BY created_at DESC\n                '
                results = await self.execute_query(query, (user_id,), fetch_all=True)
            tickets = [dict(row) for row in results]
            for ticket in tickets:
                query_att = '\n                    SELECT file_id FROM ticket_attachments \n                    WHERE ticket_id = %s AND reply_id IS NULL\n                '
                attachments = await self.execute_query(query_att, (ticket['id'],), fetch_all=True)
                ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            return tickets
        except Exception as e:
            log_exception(logger, e, f'get_user_tickets({user_id})')
            return []

    async def get_all_tickets(self, status: Optional[str]=None, assigned_to: Optional[int]=None) -> List[Dict]:
        """دریافت همه تیکت\u200cها (برای ادمین)"""
        try:
            query = 'SELECT * FROM tickets WHERE TRUE'
            params = []
            if status:
                query += ' AND status = %s'
                params.append(status)
            if assigned_to:
                query += ' AND assigned_to = %s'
                params.append(assigned_to)
            query += ' ORDER BY created_at DESC'
            results = await self.execute_query(query, tuple(params), fetch_all=True)
            tickets = [dict(row) for row in results]
            for ticket in tickets:
                query_att = '\n                    SELECT file_id FROM ticket_attachments \n                    WHERE ticket_id = %s AND reply_id IS NULL\n                '
                attachments = await self.execute_query(query_att, (ticket['id'],), fetch_all=True)
                ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            return tickets
        except Exception as e:
            log_exception(logger, e, 'get_all_tickets')
            return []

    async def add_ticket_reply(self, ticket_id: int, user_id: int, message: str, is_admin: bool=False, attachments: List[str]=None) -> bool:
        """افزودن پاسخ به تیکت"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ticket_replies (ticket_id, user_id, message, is_admin)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (ticket_id, user_id, message, is_admin))
                    result = await cursor.fetchone()
                    reply_id = result['id']
                    if attachments:
                        for file_id in attachments:
                            await cursor.execute("""
                                INSERT INTO ticket_attachments (reply_id, file_id, file_type)
                                VALUES (%s, %s, 'photo')
                            """, (reply_id, file_id))
                    await cursor.execute("""
                        UPDATE tickets SET updated_at = NOW() WHERE id = %s
                    """, (ticket_id,))
                logger.info(f'✅ Reply added to ticket {ticket_id}')
                return True
        except Exception as e:
            log_exception(logger, e, 'add_ticket_reply')
            return False

    async def get_ticket_replies(self, ticket_id: int) -> List[Dict]:
        """دریافت پاسخ\u200cهای تیکت"""
        try:
            query = '\n                SELECT * FROM ticket_replies \n                WHERE ticket_id = %s \n                ORDER BY created_at ASC\n            '
            results = await self.execute_query(query, (ticket_id,), fetch_all=True)
            replies = [dict(row) for row in results]
            for reply in replies:
                query_att = '\n                    SELECT file_id FROM ticket_attachments WHERE reply_id = %s\n                '
                attachments = await self.execute_query(query_att, (reply['id'],), fetch_all=True)
                reply['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            return replies
        except Exception as e:
            log_exception(logger, e, f'get_ticket_replies({ticket_id})')
            return []

    async def update_ticket_status(self, ticket_id: int, new_status: str) -> bool:
        """تغییر وضعیت تیکت"""
        try:
            query = '\n                UPDATE tickets \n                SET status = %s, updated_at = NOW() \n                WHERE id = %s\n            '
            await self.execute_query(query, (new_status, ticket_id))
            logger.info(f'✅ Ticket {ticket_id} status updated to: {new_status}')
            return True
        except Exception as e:
            log_exception(logger, e, f'update_ticket_status({ticket_id}, {new_status})')
            return False

    async def update_ticket_priority(self, ticket_id: int, new_priority: str) -> bool:
        """تغییر اولویت تیکت"""
        try:
            query = '\n                UPDATE tickets \n                SET priority = %s, updated_at = NOW() \n                WHERE id = %s\n            '
            await self.execute_query(query, (new_priority, ticket_id))
            logger.info(f'✅ Ticket {ticket_id} priority updated to: {new_priority}')
            return True
        except Exception as e:
            log_exception(logger, e, f'update_ticket_priority({ticket_id})')
            return False

    async def assign_ticket(self, ticket_id: int, admin_id: int) -> bool:
        """اختصاص تیکت به ادمین"""
        try:
            query = "\n                UPDATE tickets \n                SET assigned_to = %s, status = 'in_progress', updated_at = NOW() \n                WHERE id = %s\n            "
            await self.execute_query(query, (admin_id, ticket_id))
            logger.info(f'✅ Ticket {ticket_id} assigned to admin {admin_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'assign_ticket({ticket_id})')
            return False

    async def close_ticket(self, ticket_id: int, admin_id: int, resolution: str='') -> bool:
        """بستن تیکت"""
        try:
            query = "\n                UPDATE tickets \n                SET status = 'closed', closed_at = NOW(), \n                    resolution = %s, updated_at = NOW() \n                WHERE id = %s\n            "
            await self.execute_query(query, (resolution, ticket_id))
            logger.info(f'✅ Ticket {ticket_id} closed by admin {admin_id}')
            return True
        except Exception as e:
            log_exception(logger, e, f'close_ticket({ticket_id})')
            return False

    async def search_tickets(self, query: str) -> List[Dict]:
        """جستجوی تیکت\u200cها"""
        try:
            search_term = f'%{query}%'
            query_sql = '\n                SELECT * FROM tickets \n                WHERE subject ILIKE %s OR description ILIKE %s OR CAST(id AS TEXT) LIKE %s\n                ORDER BY created_at DESC\n            '
            results = await self.execute_query(query_sql, (search_term, search_term, search_term), fetch_all=True)
            return [dict(row) for row in results]
        except Exception as e:
            log_exception(logger, e, f'search_tickets({query})')
            return []

    async def analyze_sentiment(self, text: str) -> str:
        """تحلیل لحن پیام (بهبود یافته برای زبان فارسی)"""
        if not text:
            return 'neutral'
            
        text_lower = text.lower()
        
        # وزندهی به کلمات برای دقت بیشتر
        positive_map = {
            'عالی': 2, 'خوب': 1, 'ممنون': 1, 'تشکر': 1, 'سپاس': 1, 'دمتون_گرم': 2, 
            'عشق': 1, 'بهترین': 2, 'perfect': 2, 'good': 1, 'thanks': 1, 'nice': 1,
            'راضی': 1, 'اوکی': 1, 'حل': 1, 'ایول': 2
        }
        
        negative_map = {
            'بد': 1, 'افتضاح': 2, 'کار_نمی‌کند': 2, 'خراب': 2, 'مشکل': 1, 'خطا': 1,
            'اشتباه': 1, 'نامناسب': 1, 'ضعیف': 1, 'کاش': 1, 'error': 2, 'bad': 1, 
            'broken': 2, 'issue': 1, 'not_working': 2, 'مزخرف': 2, 'ناراضی': 2,
            'مسخره': 1, 'چرا': 1, 'هک': 1
        }
        
        pos_score = 0
        neg_score = 0
        
        # بررسی کلمات و ترکیب‌ها
        for word, weight in positive_map.items():
            if word in text_lower:
                pos_score += weight
                
        for word, weight in negative_map.items():
            if word in text_lower:
                neg_score += weight
        
        if neg_score > pos_score:
            return 'negative'
        elif pos_score > neg_score:
            return 'positive'
        return 'neutral'

    async def get_ticket_stats(self, admin_id: Optional[int]=None) -> Dict:
        """آمار تیکت\u200cها"""
        try:
            if admin_id:
                query = '\n                    SELECT status, COUNT(*) as count \n                    FROM tickets \n                    WHERE assigned_to = %s\n                    GROUP BY status\n                '
                results = await self.execute_query(query, (admin_id,), fetch_all=True)
            else:
                query = '\n                    SELECT status, COUNT(*) as count \n                    FROM tickets \n                    GROUP BY status\n                '
                results = await self.execute_query(query, fetch_all=True)
            stats = {row['status']: row['count'] for row in results}
            stats['total'] = sum(stats.values())
            return stats
        except Exception as e:
            log_exception(logger, e, 'get_ticket_stats')
            return {}

    async def _ensure_faqs_language_column(self):
        """Ensure 'language' column exists on faqs table (rename 'lang' if exists)."""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name='faqs' AND column_name='language'")
                    if await cursor.fetchone():
                        return
                    await cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name='faqs' AND column_name='lang'")
                    if await cursor.fetchone():
                        await cursor.execute('ALTER TABLE faqs RENAME COLUMN lang TO language')
                        logger.info("Renamed 'lang' column to 'language' in faqs table")
                    else:
                        await cursor.execute("ALTER TABLE faqs ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'fa'")
                        logger.info("Added 'language' column to faqs table")
        except Exception as e:
            log_exception(logger, e, 'ensure_faqs_language_column')

    async def get_faqs(self, category: Optional[str]=None, lang: Optional[str]=None) -> List[Dict]:
        """دریافت FAQ ها (فیلتر بر اساس زبان در صورت ارائه)"""
        for attempt in range(2):
            try:
                if category and lang:
                    query = 'SELECT * FROM faqs WHERE category = %s AND language = %s ORDER BY views DESC'
                    results = await self.execute_query(query, (category, lang), fetch_all=True)
                elif category:
                    query = 'SELECT * FROM faqs WHERE category = %s ORDER BY views DESC'
                    results = await self.execute_query(query, (category,), fetch_all=True)
                elif lang:
                    query = 'SELECT * FROM faqs WHERE language = %s ORDER BY views DESC'
                    results = await self.execute_query(query, (lang,), fetch_all=True)
                else:
                    query = 'SELECT * FROM faqs ORDER BY views DESC'
                    results = await self.execute_query(query, fetch_all=True)
                return [dict(row) for row in results]
            except Exception as e:
                error_str = str(e).lower()
                if attempt == 0 and ('column' in error_str and ('lang' in error_str or 'language' in error_str)):
                    logger.warning(f'Schema mismatch in get_faqs, attempting fix... Error: {e}')
                    await self._ensure_faqs_language_column()
                    continue
                log_exception(logger, e, 'get_faqs')
                return []
        return []

    async def search_faqs(self, query: str, lang: Optional[str]=None) -> List[Dict]:
        """جستجو در FAQ ها (با فیلتر زبان اختیاری)"""
        try:
            search_term = f'%{query}%'
            if lang:
                query_sql = '\n                    SELECT * FROM faqs \n                    WHERE (question ILIKE %s OR answer ILIKE %s) AND language = %s\n                    ORDER BY views DESC\n                '
                params = (search_term, search_term, lang)
            else:
                query_sql = '\n                    SELECT * FROM faqs \n                    WHERE question ILIKE %s OR answer ILIKE %s\n                    ORDER BY views DESC\n                '
                params = (search_term, search_term)
            results = await self.execute_query(query_sql, params, fetch_all=True)
            return [dict(row) for row in results]
        except Exception as e:
            if 'column' in str(e).lower():
                try:
                    await self._ensure_faqs_language_column()
                    return await self.search_faqs(query, lang)
                except:
                    pass
            log_exception(logger, e, f'search_faqs({query})')
            return []

    async def add_faq(self, question: str, answer: str, category: str='general', lang: str='fa') -> bool:
        """افزودن FAQ جدید (با زبان)"""
        try:
            await self._ensure_faqs_language_column()
            query = '\n                INSERT INTO faqs (question, answer, category, language)\n                VALUES (%s, %s, %s, %s)\n            '
            await self.execute_query(query, (question, answer, category, lang))
            logger.info(f'✅ FAQ added: {question[:50]}... [{lang}]')
            return True
        except Exception as e:
            log_exception(logger, e, 'add_faq')
            return False

    async def increment_faq_views(self, faq_id: int) -> bool:
        """افزایش تعداد بازدید FAQ"""
        try:
            query = 'UPDATE faqs SET views = views + 1 WHERE id = %s'
            await self.execute_query(query, (faq_id,))
            return True
        except Exception as e:
            log_exception(logger, e, f'increment_faq_views({faq_id})')
            return False

    async def mark_faq_helpful(self, faq_id: int, helpful: bool=True) -> bool:
        """ثبت رای مفید/نامفید برای FAQ"""
        try:
            if helpful:
                query = 'UPDATE faqs SET helpful_count = helpful_count + 1 WHERE id = %s'
                await self.execute_query(query, (faq_id,))
                return True
            else:
                try:
                    query = 'UPDATE faqs SET not_helpful_count = not_helpful_count + 1 WHERE id = %s'
                    await self.execute_query(query, (faq_id,))
                    return True
                except Exception as inner:
                    try:
                        alter_sql = 'ALTER TABLE faqs ADD COLUMN IF NOT EXISTS not_helpful_count INTEGER NOT NULL DEFAULT 0;'
                        await self.execute_query(alter_sql)
                        query = 'UPDATE faqs SET not_helpful_count = not_helpful_count + 1 WHERE id = %s'
                        await self.execute_query(query, (faq_id,))
                        return True
                    except Exception as inner2:
                        log_exception(logger, inner2, 'mark_faq_not_helpful_migration_failed')
                        return False
        except Exception as e:
            log_exception(logger, e, f'mark_faq_helpful({faq_id}, {helpful})')
            return False

    async def update_faq(self, faq_id: int, question: str=None, answer: str=None, category: str=None) -> bool:
        """به\u200cروزرسانی FAQ"""
        try:
            updates = []
            params = []
            if question is not None:
                updates.append('question = %s')
                params.append(question)
            if answer is not None:
                updates.append('answer = %s')
                params.append(answer)
            if category is not None:
                updates.append('category = %s')
                params.append(category)
            if not updates:
                return False
            params.append(faq_id)
            query = 'UPDATE faqs SET {} WHERE id = %s'.format(', '.join(updates))
            await self.execute_query(query, tuple(params))
            logger.info(f'✅ FAQ {faq_id} updated')
            return True
        except Exception as e:
            log_exception(logger, e, f'update_faq({faq_id})')
            return False

    async def delete_faq(self, faq_id: int) -> bool:
        """حذف FAQ"""
        try:
            query = 'DELETE FROM faqs WHERE id = %s'
            await self.execute_query(query, (faq_id,))
            logger.info(f'✅ FAQ {faq_id} deleted')
            return True
        except Exception as e:
            log_exception(logger, e, f'delete_faq({faq_id})')
            return False

    async def vote_faq(self, user_id: int, faq_id: int, helpful: bool=True) -> Dict:
        """ثبت/تغییر رأی کاربر برای FAQ"""
        try:
            async with self.transaction() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT rating FROM user_faq_votes
                        WHERE user_id = %s AND faq_id = %s
                        FOR UPDATE
                    """, (user_id, faq_id))
                    row = await cursor.fetchone()
                    prev = row.get('rating') if row else None
                    new_rating = 1 if helpful else -1
                    if prev is None:
                        action = 'added'
                        final_rating = new_rating
                    elif prev == new_rating:
                        action = 'removed'
                        final_rating = None
                    else:
                        action = 'changed'
                        final_rating = new_rating
                    await cursor.execute("""
                        INSERT INTO user_faq_votes (user_id, faq_id, rating, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (user_id, faq_id) DO UPDATE
                        SET rating = EXCLUDED.rating,
                            updated_at = NOW()
                    """, (user_id, faq_id, final_rating))
                    dh = 0
                    dnh = 0
                    if action == 'added':
                        if new_rating == 1:
                            dh = 1
                        else:
                            dnh = 1
                    elif action == 'removed':
                        if prev == 1:
                            dh = -1
                        elif prev == -1:
                            dnh = -1
                    elif action == 'changed':
                        if prev == 1 and new_rating == -1:
                            dh = -1
                            dnh = 1
                        elif prev == -1 and new_rating == 1:
                            dh = 1
                            dnh = -1
                    try:
                        await cursor.execute("""
                            UPDATE faqs
                            SET helpful_count = GREATEST(helpful_count + %s, 0),
                                not_helpful_count = GREATEST(not_helpful_count + %s, 0),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (dh, dnh, faq_id))
                    except Exception:
                        await cursor.execute('ALTER TABLE faqs ADD COLUMN IF NOT EXISTS not_helpful_count INTEGER NOT NULL DEFAULT 0;')
                        await cursor.execute("""
                            UPDATE faqs
                            SET helpful_count = GREATEST(helpful_count + %s, 0),
                                not_helpful_count = GREATEST(not_helpful_count + %s, 0),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (dh, dnh, faq_id))
                    await cursor.execute('SELECT helpful_count, COALESCE(not_helpful_count, 0) as not_helpful_count FROM faqs WHERE id = %s', (faq_id,))
                    counts = await cursor.fetchone()
                    h = counts.get('helpful_count', 0) if counts else 0
                    nh = counts.get('not_helpful_count', 0) if counts else 0
                return {'success': True, 'action': action, 'previous_vote': prev, 'new_vote': final_rating if final_rating is not None else 0, 'helpful_count': h, 'not_helpful_count': nh}
        except Exception as e:
            log_exception(logger, e, f'vote_faq({user_id}, {faq_id}, {helpful})')
            return {'success': False, 'action': 'error', 'error': str(e)}
