"""
Database mixin for Tickets and FAQ System.
"""

import logging
from typing import Optional, Dict, List
from utils.logger import log_exception

logger = logging.getLogger('database.support_mixin')


class SupportDatabaseMixin:
    """
    Mixin containing Tickets and FAQ operations.
    Requires self.execute_query and self.transaction to be provided by the base class.
    """

    # ==========================================================================
    # Tickets System
    # ==========================================================================
    
    def add_ticket(self, user_id: int, category: str, subject: str,
                   description: str, priority: str = "medium",
                   attachments: List[str] = None) -> Optional[int]:
        """ایجاد تیکت جدید"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO tickets (user_id, category, subject, description, priority)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, category, subject, description, priority))
                
                result = cursor.fetchone()
                ticket_id = result['id']
                
                # اضافه کردن attachments
                if attachments:
                    for file_id in attachments:
                        cursor.execute("""
                            INSERT INTO ticket_attachments (ticket_id, file_id, file_type)
                            VALUES (%s, %s, 'photo')
                        """, (ticket_id, file_id))
                
                cursor.close()
                logger.info(f"✅ Ticket created: {ticket_id}")
                return ticket_id
        except Exception as e:
            log_exception(logger, e, "add_ticket")
            return None
    
    def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """دریافت اطلاعات یک تیکت"""
        try:
            query_ticket = "SELECT * FROM tickets WHERE id = %s"
            result = self.execute_query(query_ticket, (ticket_id,), fetch_one=True)
            
            if not result:
                logger.warning(f"Ticket {ticket_id} not found")
                return None
            
            ticket = dict(result)
            
            # دریافت attachments
            query_att = """
                SELECT file_id FROM ticket_attachments 
                WHERE ticket_id = %s AND reply_id IS NULL
            """
            attachments = self.execute_query(query_att, (ticket_id,), fetch_all=True)
            ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            
            return ticket
        except Exception as e:
            log_exception(logger, e, f"get_ticket({ticket_id})")
            return None
    
    def get_user_tickets(self, user_id: int, status: Optional[str] = None) -> List[Dict]:
        """دریافت تیکت‌های کاربر"""
        try:
            if status:
                query = """
                    SELECT * FROM tickets 
                    WHERE user_id = %s AND status = %s 
                    ORDER BY created_at DESC
                """
                results = self.execute_query(query, (user_id, status), fetch_all=True)
            else:
                query = """
                    SELECT * FROM tickets 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """
                results = self.execute_query(query, (user_id,), fetch_all=True)
            
            tickets = [dict(row) for row in results]
            
            # اضافه کردن attachments به هر تیکت
            for ticket in tickets:
                query_att = """
                    SELECT file_id FROM ticket_attachments 
                    WHERE ticket_id = %s AND reply_id IS NULL
                """
                attachments = self.execute_query(query_att, (ticket['id'],), fetch_all=True)
                ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            
            return tickets
        except Exception as e:
            log_exception(logger, e, f"get_user_tickets({user_id})")
            return []
    
    def get_all_tickets(self, status: Optional[str] = None, 
                       assigned_to: Optional[int] = None) -> List[Dict]:
        """دریافت همه تیکت‌ها (برای ادمین)"""
        try:
            query = "SELECT * FROM tickets WHERE TRUE"
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            if assigned_to:
                query += " AND assigned_to = %s"
                params.append(assigned_to)
            
            query += " ORDER BY created_at DESC"
            
            results = self.execute_query(query, tuple(params), fetch_all=True)
            tickets = [dict(row) for row in results]
            
            # اضافه کردن attachments
            for ticket in tickets:
                query_att = """
                    SELECT file_id FROM ticket_attachments 
                    WHERE ticket_id = %s AND reply_id IS NULL
                """
                attachments = self.execute_query(query_att, (ticket['id'],), fetch_all=True)
                ticket['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            
            return tickets
        except Exception as e:
            log_exception(logger, e, "get_all_tickets")
            return []
    
    def add_ticket_reply(self, ticket_id: int, user_id: int, message: str,
                        is_admin: bool = False, attachments: List[str] = None) -> bool:
        """افزودن پاسخ به تیکت"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO ticket_replies (ticket_id, user_id, message, is_admin)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (ticket_id, user_id, message, is_admin))
                
                result = cursor.fetchone()
                reply_id = result['id']
                
                # attachments
                if attachments:
                    for file_id in attachments:
                        cursor.execute("""
                            INSERT INTO ticket_attachments (reply_id, file_id, file_type)
                            VALUES (%s, %s, 'photo')
                        """, (reply_id, file_id))
                
                # به‌روزرسانی زمان
                cursor.execute("""
                    UPDATE tickets SET updated_at = NOW() WHERE id = %s
                """, (ticket_id,))
                
                cursor.close()
                logger.info(f"✅ Reply added to ticket {ticket_id}")
                return True
        except Exception as e:
            log_exception(logger, e, "add_ticket_reply")
            return False
    
    def get_ticket_replies(self, ticket_id: int) -> List[Dict]:
        """دریافت پاسخ‌های تیکت"""
        try:
            query = """
                SELECT * FROM ticket_replies 
                WHERE ticket_id = %s 
                ORDER BY created_at ASC
            """
            results = self.execute_query(query, (ticket_id,), fetch_all=True)
            replies = [dict(row) for row in results]
            
            # اضافه کردن attachments به هر reply
            for reply in replies:
                query_att = """
                    SELECT file_id FROM ticket_attachments WHERE reply_id = %s
                """
                attachments = self.execute_query(query_att, (reply['id'],), fetch_all=True)
                reply['attachments'] = [row['file_id'] for row in attachments] if attachments else []
            
            return replies
        except Exception as e:
            log_exception(logger, e, f"get_ticket_replies({ticket_id})")
            return []
    
    def update_ticket_status(self, ticket_id: int, new_status: str) -> bool:
        """تغییر وضعیت تیکت"""
        try:
            query = """
                UPDATE tickets 
                SET status = %s, updated_at = NOW() 
                WHERE id = %s
            """
            self.execute_query(query, (new_status, ticket_id))
            logger.info(f"✅ Ticket {ticket_id} status updated to: {new_status}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_ticket_status({ticket_id}, {new_status})")
            return False
    
    def update_ticket_priority(self, ticket_id: int, new_priority: str) -> bool:
        """تغییر اولویت تیکت"""
        try:
            query = """
                UPDATE tickets 
                SET priority = %s, updated_at = NOW() 
                WHERE id = %s
            """
            self.execute_query(query, (new_priority, ticket_id))
            logger.info(f"✅ Ticket {ticket_id} priority updated to: {new_priority}")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_ticket_priority({ticket_id})")
            return False
    
    def assign_ticket(self, ticket_id: int, admin_id: int) -> bool:
        """اختصاص تیکت به ادمین"""
        try:
            query = """
                UPDATE tickets 
                SET assigned_to = %s, status = 'in_progress', updated_at = NOW() 
                WHERE id = %s
            """
            self.execute_query(query, (admin_id, ticket_id))
            logger.info(f"✅ Ticket {ticket_id} assigned to admin {admin_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"assign_ticket({ticket_id})")
            return False
    
    def close_ticket(self, ticket_id: int, admin_id: int, resolution: str = "") -> bool:
        """بستن تیکت"""
        try:
            query = """
                UPDATE tickets 
                SET status = 'closed', closed_at = NOW(), 
                    resolution = %s, updated_at = NOW() 
                WHERE id = %s
            """
            self.execute_query(query, (resolution, ticket_id))
            logger.info(f"✅ Ticket {ticket_id} closed by admin {admin_id}")
            return True
        except Exception as e:
            log_exception(logger, e, f"close_ticket({ticket_id})")
            return False
    
    def search_tickets(self, query: str) -> List[Dict]:
        """جستجوی تیکت‌ها"""
        try:
            search_term = f"%{query}%"
            query_sql = """
                SELECT * FROM tickets 
                WHERE subject ILIKE %s OR description ILIKE %s OR CAST(id AS TEXT) LIKE %s
                ORDER BY created_at DESC
            """
            results = self.execute_query(query_sql, (search_term, search_term, search_term), fetch_all=True)
            return [dict(row) for row in results]
        except Exception as e:
            log_exception(logger, e, f"search_tickets({query})")
            return []
    
    def get_ticket_stats(self, admin_id: Optional[int] = None) -> Dict:
        """آمار تیکت‌ها"""
        try:
            if admin_id:
                query = """
                    SELECT status, COUNT(*) as count 
                    FROM tickets 
                    WHERE assigned_to = %s
                    GROUP BY status
                """
                results = self.execute_query(query, (admin_id,), fetch_all=True)
            else:
                query = """
                    SELECT status, COUNT(*) as count 
                    FROM tickets 
                    GROUP BY status
                """
                results = self.execute_query(query, fetch_all=True)
            
            stats = {row['status']: row['count'] for row in results}
            stats['total'] = sum(stats.values())
            
            return stats
        except Exception as e:
            log_exception(logger, e, "get_ticket_stats")
            return {}
    
    # ==========================================================================
    # FAQ System
    # ==========================================================================
    
    def _ensure_faqs_language_column(self):
        """Ensure 'language' column exists on faqs table (rename 'lang' if exists)."""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name='faqs' AND column_name='language'")
                if cursor.fetchone():
                    return
                
                cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_name='faqs' AND column_name='lang'")
                if cursor.fetchone():
                    cursor.execute("ALTER TABLE faqs RENAME COLUMN lang TO language")
                    logger.info("Renamed 'lang' column to 'language' in faqs table")
                else:
                    cursor.execute("ALTER TABLE faqs ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'fa'")
                    logger.info("Added 'language' column to faqs table")
                    
        except Exception as e:
            log_exception(logger, e, "ensure_faqs_language_column")
    
    def get_faqs(self, category: Optional[str] = None, lang: Optional[str] = None) -> List[Dict]:
        """دریافت FAQ ها (فیلتر بر اساس زبان در صورت ارائه)"""
        for attempt in range(2):
            try:
                if category and lang:
                    query = "SELECT * FROM faqs WHERE category = %s AND language = %s ORDER BY views DESC"
                    results = self.execute_query(query, (category, lang), fetch_all=True)
                elif category:
                    query = "SELECT * FROM faqs WHERE category = %s ORDER BY views DESC"
                    results = self.execute_query(query, (category,), fetch_all=True)
                elif lang:
                    query = "SELECT * FROM faqs WHERE language = %s ORDER BY views DESC"
                    results = self.execute_query(query, (lang,), fetch_all=True)
                else:
                    query = "SELECT * FROM faqs ORDER BY views DESC"
                    results = self.execute_query(query, fetch_all=True)
                
                return [dict(row) for row in results]
                
            except Exception as e:
                error_str = str(e).lower()
                if attempt == 0 and ("column" in error_str and ("lang" in error_str or "language" in error_str)):
                    logger.warning(f"Schema mismatch in get_faqs, attempting fix... Error: {e}")
                    self._ensure_faqs_language_column()
                    continue
                
                log_exception(logger, e, "get_faqs")
                return []
        return []
    
    def search_faqs(self, query: str, lang: Optional[str] = None) -> List[Dict]:
        """جستجو در FAQ ها (با فیلتر زبان اختیاری)"""
        try:
            search_term = f"%{query}%"
            if lang:
                query_sql = """
                    SELECT * FROM faqs 
                    WHERE (question ILIKE %s OR answer ILIKE %s) AND language = %s
                    ORDER BY views DESC
                """
                params = (search_term, search_term, lang)
            else:
                query_sql = """
                    SELECT * FROM faqs 
                    WHERE question ILIKE %s OR answer ILIKE %s
                    ORDER BY views DESC
                """
                params = (search_term, search_term)
            results = self.execute_query(query_sql, params, fetch_all=True)
            return [dict(row) for row in results]
        except Exception as e:
            if "column" in str(e).lower():
                 try:
                     self._ensure_faqs_language_column()
                     return self.search_faqs(query, lang)
                 except:
                     pass
            log_exception(logger, e, f"search_faqs({query})")
            return []
    
    def add_faq(self, question: str, answer: str, category: str = "general", lang: str = 'fa') -> bool:
        """افزودن FAQ جدید (با زبان)"""
        try:
            self._ensure_faqs_language_column()
            query = """
                INSERT INTO faqs (question, answer, category, language)
                VALUES (%s, %s, %s, %s)
            """
            self.execute_query(query, (question, answer, category, lang))
            logger.info(f"✅ FAQ added: {question[:50]}... [{lang}]")
            return True
        except Exception as e:
            log_exception(logger, e, "add_faq")
            return False
    
    def increment_faq_views(self, faq_id: int) -> bool:
        """افزایش تعداد بازدید FAQ"""
        try:
            query = "UPDATE faqs SET views = views + 1 WHERE id = %s"
            self.execute_query(query, (faq_id,))
            return True
        except Exception as e:
            log_exception(logger, e, f"increment_faq_views({faq_id})")
            return False

    def mark_faq_helpful(self, faq_id: int, helpful: bool = True) -> bool:
        """ثبت رای مفید/نامفید برای FAQ"""
        try:
            if helpful:
                query = "UPDATE faqs SET helpful_count = helpful_count + 1 WHERE id = %s"
                self.execute_query(query, (faq_id,))
                return True
            else:
                try:
                    query = "UPDATE faqs SET not_helpful_count = not_helpful_count + 1 WHERE id = %s"
                    self.execute_query(query, (faq_id,))
                    return True
                except Exception as inner:
                    try:
                        alter_sql = (
                            "ALTER TABLE faqs ADD COLUMN IF NOT EXISTS not_helpful_count INTEGER NOT NULL DEFAULT 0;"
                        )
                        self.execute_query(alter_sql)
                        query = "UPDATE faqs SET not_helpful_count = not_helpful_count + 1 WHERE id = %s"
                        self.execute_query(query, (faq_id,))
                        return True
                    except Exception as inner2:
                        log_exception(logger, inner2, "mark_faq_not_helpful_migration_failed")
                        return False
        except Exception as e:
            log_exception(logger, e, f"mark_faq_helpful({faq_id}, {helpful})")
            return False
    
    def update_faq(self, faq_id: int, question: str = None, 
                   answer: str = None, category: str = None) -> bool:
        """به‌روزرسانی FAQ"""
        try:
            updates = []
            params = []
            
            if question is not None:
                updates.append("question = %s")
                params.append(question)
            
            if answer is not None:
                updates.append("answer = %s")
                params.append(answer)
            
            if category is not None:
                updates.append("category = %s")
                params.append(category)
            
            if not updates:
                return False
            
            params.append(faq_id)
            query = "UPDATE faqs SET {} WHERE id = %s".format(", ".join(updates))
            
            self.execute_query(query, tuple(params))
            logger.info(f"✅ FAQ {faq_id} updated")
            return True
        except Exception as e:
            log_exception(logger, e, f"update_faq({faq_id})")
            return False
    
    def delete_faq(self, faq_id: int) -> bool:
        """حذف FAQ"""
        try:
            query = "DELETE FROM faqs WHERE id = %s"
            self.execute_query(query, (faq_id,))
            logger.info(f"✅ FAQ {faq_id} deleted")
            return True
        except Exception as e:
            log_exception(logger, e, f"delete_faq({faq_id})")
            return False
    
    def vote_faq(self, user_id: int, faq_id: int, helpful: bool = True) -> Dict:
        """ثبت/تغییر رأی کاربر برای FAQ"""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT rating FROM user_faq_votes
                    WHERE user_id = %s AND faq_id = %s
                    FOR UPDATE
                    """,
                    (user_id, faq_id),
                )
                row = cursor.fetchone()
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
                
                cursor.execute(
                    """
                    INSERT INTO user_faq_votes (user_id, faq_id, rating, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id, faq_id) DO UPDATE
                    SET rating = EXCLUDED.rating,
                        updated_at = NOW()
                    """,
                    (user_id, faq_id, final_rating),
                )
                
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
                    cursor.execute(
                        """
                        UPDATE faqs
                        SET helpful_count = GREATEST(helpful_count + %s, 0),
                            not_helpful_count = GREATEST(not_helpful_count + %s, 0),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (dh, dnh, faq_id),
                    )
                except Exception:
                    cursor.execute("ALTER TABLE faqs ADD COLUMN IF NOT EXISTS not_helpful_count INTEGER NOT NULL DEFAULT 0;")
                    cursor.execute(
                        """
                        UPDATE faqs
                        SET helpful_count = GREATEST(helpful_count + %s, 0),
                            not_helpful_count = GREATEST(not_helpful_count + %s, 0),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (dh, dnh, faq_id),
                    )
                
                cursor.execute(
                    "SELECT helpful_count, COALESCE(not_helpful_count, 0) as not_helpful_count FROM faqs WHERE id = %s",
                    (faq_id,),
                )
                counts = cursor.fetchone()
                h = counts.get('helpful_count', 0) if counts else 0
                nh = counts.get('not_helpful_count', 0) if counts else 0
                cursor.close()
                return {
                    'success': True,
                    'action': action,
                    'previous_vote': prev,
                    'new_vote': final_rating if final_rating is not None else 0,
                    'helpful_count': h,
                    'not_helpful_count': nh,
                }
        except Exception as e:
            log_exception(logger, e, f"vote_faq({user_id}, {faq_id}, {helpful})")
            return {'success': False, 'action': 'error', 'error': str(e)}
