"""
Data Health Check Script
Performs comprehensive validation of database content and quality
"""
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING
from collections import defaultdict
from psycopg import sql
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.logger import get_logger
if TYPE_CHECKING:
    from core.database.database_adapter import DatabaseAdapter
import asyncio
logger = get_logger('data_health_check', 'health_checks.log')

class DataHealthChecker:
    """Main class for checking data health and quality"""

    def __init__(self, db_adapter: 'DatabaseAdapter'=None, auto_fix=False):
        """
        Initialize health checker
        
        Args:
            db_adapter: DatabaseAdapter instance (اگر None باشد، یک instance جدید می\u200cسازد)
            auto_fix: If True, automatically fix simple issues (dangerous!)
        """
        if db_adapter is None:
            from core.database.database_adapter import DatabaseAdapter
            self.db = DatabaseAdapter()
        else:
            self.db = db_adapter
        self.auto_fix = auto_fix
        self.issues = defaultdict(list)
        self.metrics = {}
        # Get DB path from adapter if possible
        self.db_path = getattr(self.db, 'db_path', None)

    def _get(self, row, key_or_idx, default=None):
        """Return a value from a dict_row (psycopg3 row_factory=dict_row)."""
        if row is None:
            return default
        if isinstance(key_or_idx, str):
            return row.get(key_or_idx, default)
        try:
            return list(row.values())[key_or_idx]
        except Exception:
            return default

    def connect(self):
        """Get database connection context manager from pool"""
        if hasattr(self.db, 'get_connection'):
            return self.db.get_connection()
        raise RuntimeError('Database connection not available through adapter')

    async def check_missing_images(self) -> List[Dict]:
        """Check for attachments without images"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute("\n                SELECT \n                    a.id,\n                    a.code,\n                    a.name,\n                    w.name as weapon,\n                    wc.name as category\n                FROM attachments a\n                JOIN weapons w ON a.weapon_id = w.id\n                JOIN weapon_categories wc ON w.category_id = wc.id\n                WHERE a.image_file_id IS NULL OR a.image_file_id = ''\n                ORDER BY wc.name, w.name, a.name\n            ")
                    missing_images = []
                    for row in await cursor.fetchall():
                        rid = self._get(row, 'id')
                        code = self._get(row, 'code')
                        name = self._get(row, 'name')
                        weapon = self._get(row, 'weapon')
                        category = self._get(row, 'category')
                        missing_images.append({'id': rid, 'code': code, 'name': name, 'weapon': weapon, 'category': category, 'issue': 'missing_image'})
            if missing_images:
                self.issues['CRITICAL'].append({'type': 'missing_images', 'count': len(missing_images), 'details': missing_images})
                logger.warning(f'⚠️ Found {len(missing_images)} attachments without images')
            else:
                logger.info('✅ All attachments have images')
            return missing_images
        except Exception as e:
            logger.error(f'Error checking missing images: {e}')
            return []

    async def check_duplicate_codes(self) -> List[Dict]:
        """Check for duplicate attachment codes (per weapon and globally)"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    # 1. Local duplicates (per weapon) - CRITICAL
                    await cursor.execute("""
                        SELECT 
                            w.name as weapon,
                            a.code,
                            COUNT(*) as count,
                            STRING_AGG(a.name, ', ') as names,
                            STRING_AGG(a.id::text, ', ') as ids
                        FROM attachments a
                        JOIN weapons w ON a.weapon_id = w.id
                        GROUP BY w.name, a.code
                        HAVING COUNT(*) > 1
                    """)
                    local_duplicates = []
                    for row in await cursor.fetchall():
                        local_duplicates.append({
                            'weapon': self._get(row, 'weapon'),
                            'code': self._get(row, 'code'),
                            'count': self._get(row, 'count'),
                            'names': self._get(row, 'names'),
                            'ids': self._get(row, 'ids'),
                            'issue': 'duplicate_code_per_weapon'
                        })
                    
                    # 2. Global duplicates (same code for different weapons) - WARNING
                    await cursor.execute("""
                        SELECT 
                            code,
                            COUNT(DISTINCT weapon_id) as weapon_count,
                            COUNT(*) as total_count,
                            STRING_AGG(DISTINCT w.name, ', ') as weapons
                        FROM attachments a
                        JOIN weapons w ON a.weapon_id = w.id
                        GROUP BY code
                        HAVING COUNT(DISTINCT weapon_id) > 1
                    """)
                    global_duplicates = []
                    for row in await cursor.fetchall():
                        global_duplicates.append({
                            'code': self._get(row, 'code'),
                            'weapon_count': self._get(row, 'weapon_count'),
                            'total_count': self._get(row, 'total_count'),
                            'weapons': self._get(row, 'weapons'),
                            'issue': 'duplicate_code_global'
                        })

            if local_duplicates:
                self.issues['CRITICAL'].append({'type': 'duplicate_codes_local', 'count': len(local_duplicates), 'details': local_duplicates})
                logger.warning(f'⚠️ Found {len(local_duplicates)} duplicate codes within weapons')
            
            if global_duplicates:
                self.issues['WARNING'].append({'type': 'duplicate_codes_global', 'count': len(global_duplicates), 'details': global_duplicates})
                logger.warning(f'⚠️ Found {len(global_duplicates)} codes shared across different weapons')
                
            return local_duplicates + global_duplicates
        except Exception as e:
            logger.error(f'Error checking duplicate codes: {e}')
            return []

    async def check_empty_weapons(self) -> List[Dict]:
        """Check for weapons without any attachments"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute('\n                SELECT \n                    w.id,\n                    w.name,\n                    wc.name as category\n                FROM weapons w\n                JOIN weapon_categories wc ON w.category_id = wc.id\n                LEFT JOIN attachments a ON a.weapon_id = w.id\n                WHERE a.id IS NULL\n                ORDER BY wc.name, w.name\n            ')
                    empty_weapons = []
                    for row in await cursor.fetchall():
                        wid = self._get(row, 'id')
                        name = self._get(row, 'name')
                        category = self._get(row, 'category')
                        empty_weapons.append({'id': wid, 'name': name, 'category': category, 'issue': 'no_attachments'})
            if empty_weapons:
                pol = getattr(self, 'policy_empty_weapons', 'ignore')
                if pol == 'ignore':
                    logger.info(f'ℹ️ Empty weapons found but ignored by policy: {len(empty_weapons)}')
                else:
                    sev = 'INFO' if pol == 'info' else 'WARNING' if pol == 'warning' else 'CRITICAL'
                    self.issues[sev].append({'type': 'empty_weapons', 'count': len(empty_weapons), 'details': empty_weapons})
                    logger.warning(f'⚠️ Empty weapons reported with severity={sev}: {len(empty_weapons)}')
            else:
                logger.info('✅ All weapons have attachments (or policy ignores check)')
            return empty_weapons
        except Exception as e:
            logger.error(f'Error checking empty weapons: {e}')
            return []

    async def check_required_indexes(self):
        """Verify presence of required indexes and extensions (read-only)."""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    try:
                        await cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
                        has_trgm = await cursor.fetchone() is not None
                    except Exception:
                        has_trgm = False
                    await cursor.execute('\n                    SELECT indexname FROM pg_indexes \n                    WHERE schemaname = current_schema()\n                ')
                    rows = await cursor.fetchall() or []
                    idx_names = set([r.get('indexname') for r in rows])
                    required = {
                        'idx_attachments_name_trgm', 'idx_attachments_code_trgm', 
                        'idx_weapons_name_trgm', 'idx_attachments_search_composite',
                        'ux_attachments_weapon_mode_code', 'idx_attachments_weapon_mode', 
                        'ux_suggested_attachment_mode', 'idx_suggested_mode', 
                        'ix_uae_attachment_id', 'ix_uae_attachment_id_rating', 
                        'ix_ticket_attachments_ticket_id', 'ix_ticket_attachments_reply_id'
                    }
                    missing = [i for i in required if i not in idx_names]
                    det = {'type': 'missing_indexes', 'count': len(missing) + (0 if has_trgm else 1)}
                    details = []
                    if not has_trgm:
                        details.append({'extension': 'pg_trgm'})
                    for i in missing:
                        details.append({'index': i})
                    if details:
                        det['details'] = details
                        self.issues['WARNING'].append(det)
        except Exception as e:
            logger.error(f'Error checking indexes: {e}')

    async def check_sequences_synced(self):
        """Check that sequences for id columns are present/synced."""
        tables = ['data_quality_metrics', 'data_health_checks']
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    for tbl in tables:
                        await cursor.execute("SELECT pg_get_serial_sequence(%s, 'id') as seq", (tbl,))
                        row = await cursor.fetchone()
                        seq = row.get('seq') if row else None
                        if not seq:
                            self.issues['WARNING'].append({'type': 'sequence_missing', 'table': tbl, 'count': 1})
                            continue
                        try:
                            query = sql.SQL('SELECT last_value FROM {}').format(sql.Identifier(seq))
                            await cursor.execute(query)
                            lv_row = await cursor.fetchone()
                            last_val = lv_row.get('last_value') if lv_row else 0
                        except Exception:
                            last_val = 0
                        
                        query = sql.SQL('SELECT COALESCE(MAX(id),0) FROM {}').format(sql.Identifier(tbl))
                        await cursor.execute(query)
                        max_row = await cursor.fetchone()
                        max_id = max_row.get('coalesce') if max_row and 'coalesce' in max_row else list(max_row.values())[0] if max_row else 0
                        if last_val < max_id:
                            self.issues['WARNING'].append({'type': 'sequence_desync', 'table': tbl, 'details': {'last_value': last_val, 'max_id': max_id}, 'count': 1})
        except Exception as e:
            logger.error(f'Error checking sequences: {e}')
            # If transaction is aborted, we might need to rollback or at least log it clearly.
            # But since we are usually in a read-only check context here, just logging is enough.
            # The next 'async with self.db.get_connection()' will get a fresh connection if needed.

    async def check_schema_columns(self):
        """Ensure required columns exist for core features."""
        required = {'attachments': ['updated_at', 'order_index'], 'user_attachment_engagement': ['rating', 'total_views', 'total_clicks', 'first_view_date', 'last_view_date', 'feedback']}
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    missing = []
                    for table, cols in required.items():
                        for col in cols:
                            await cursor.execute('\n                            SELECT 1 FROM information_schema.columns\n                            WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s\n                            ', (table, col))
                            if await cursor.fetchone() is None:
                                missing.append({'table': table, 'column': col})
                    if missing:
                        self.issues['CRITICAL'].append({'type': 'missing_columns', 'count': len(missing), 'details': missing})
        except Exception as e:
            logger.error(f'Error checking schema columns: {e}')

    async def check_sparse_weapons(self) -> List[Dict]:
        """Check for weapons with very few attachments (<3)"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute('\n                SELECT \n                    w.name as weapon,\n                    wc.name as category,\n                    COUNT(a.id) as attachment_count\n                FROM weapons w\n                JOIN weapon_categories wc ON w.category_id = wc.id\n                LEFT JOIN attachments a ON a.weapon_id = w.id\n                GROUP BY w.id, w.name, wc.name\n                HAVING COUNT(a.id) BETWEEN 1 AND 2\n                ORDER BY attachment_count ASC, wc.name, w.name\n            ')
                    sparse_weapons = []
                    for row in await cursor.fetchall():
                        name = self._get(row, 'weapon')
                        category = self._get(row, 'category')
                        att_cnt = self._get(row, 'attachment_count')
                        sparse_weapons.append({'name': name, 'category': category, 'attachment_count': att_cnt, 'issue': 'too_few_attachments'})
            if sparse_weapons:
                self.issues['WARNING'].append({'type': 'sparse_weapons', 'count': len(sparse_weapons), 'details': sparse_weapons})
                logger.info(f'ℹ️ Found {len(sparse_weapons)} weapons with <3 attachments')
            return sparse_weapons
        except Exception as e:
            logger.error(f'Error checking sparse weapons: {e}')
            return []

    async def check_orphaned_attachments(self) -> List[Dict]:
        """Check for attachments pointing to non-existent weapons"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute('\n                SELECT \n                    a.id,\n                    a.code,\n                    a.name,\n                    a.weapon_id\n                FROM attachments a\n                LEFT JOIN weapons w ON a.weapon_id = w.id\n                WHERE w.id IS NULL\n            ')
                    orphaned = []
                    for row in await cursor.fetchall():
                        rid = self._get(row, 'id')
                        code = self._get(row, 'code')
                        name = self._get(row, 'name')
                        weapon_id = self._get(row, 'weapon_id')
                        orphaned.append({'id': rid, 'code': code, 'name': name, 'weapon_id': weapon_id, 'issue': 'orphaned_attachment'})
            if orphaned:
                self.issues['CRITICAL'].append({'type': 'orphaned_attachments', 'count': len(orphaned), 'details': orphaned})
                logger.error(f'❌ Found {len(orphaned)} orphaned attachments!')
            else:
                logger.info('✅ No orphaned attachments found')
            return orphaned
        except Exception as e:
            logger.error(f'Error checking orphaned attachments: {e}')
            return []

    async def check_data_freshness(self) -> Dict:
        """Check how recently data was updated"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute('\n                SELECT \n                    MAX(created_at) as last_created\n                FROM attachments\n                WHERE created_at IS NOT NULL\n            ')
                    row = await cursor.fetchone()
                    last_created = self._get(row, 'last_created')
                    if last_created:
                        if isinstance(last_created, str):
                            last_date = datetime.fromisoformat(last_created)
                        else:
                            last_date = last_created
                        days_old = (datetime.now() - last_date).days
                        if days_old > 30:
                            self.issues['INFO'].append({'type': 'stale_data', 'days_old': days_old, 'last_update': str(last_date)})
                            logger.info(f'ℹ️ Data is {days_old} days old')
                    else:
                        logger.info('ℹ️ No timestamp data available')
        except Exception as e:
            logger.error(f'Error checking data freshness: {e}')

    async def calculate_metrics(self) -> Dict:
        """Calculate overall data quality metrics"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    metrics = {}
                    await cursor.execute('SELECT COUNT(*) as cnt FROM weapon_categories')
                    metrics['total_categories'] = self._get(await cursor.fetchone(), 'cnt')
                    await cursor.execute('SELECT COUNT(*) as cnt FROM weapons')
                    metrics['total_weapons'] = self._get(await cursor.fetchone(), 'cnt')
                    await cursor.execute('SELECT COUNT(*) as cnt FROM attachments')
                    metrics['total_attachments'] = self._get(await cursor.fetchone(), 'cnt')
                    await cursor.execute('\n                SELECT \n                    wc.name as category,\n                    COUNT(DISTINCT w.id) as weapon_count,\n                    COUNT(a.id) as attachment_count\n                FROM weapon_categories wc\n                LEFT JOIN weapons w ON w.category_id = wc.id\n                LEFT JOIN attachments a ON a.weapon_id = w.id\n                GROUP BY wc.id, wc.name\n                ORDER BY wc.name\n            ')
                    metrics['category_distribution'] = []
                    for row in await cursor.fetchall():
                        category = self._get(row, 'category')
                        weapons = self._get(row, 'weapon_count')
                        attachments = self._get(row, 'attachment_count')
                        metrics['category_distribution'].append({'category': category, 'weapons': weapons, 'attachments': attachments})
                    await cursor.execute('SELECT COUNT(*) as cnt FROM attachments WHERE is_top = TRUE')
                    metrics['top_attachments'] = self._get(await cursor.fetchone(), 'cnt', default=0)
                    await cursor.execute('SELECT COUNT(*) as cnt FROM attachments WHERE is_season_top = TRUE')
                    metrics['season_attachments'] = self._get(await cursor.fetchone(), 'cnt', default=0)
                    await cursor.execute("SELECT COUNT(*) as cnt FROM attachments WHERE image_file_id IS NOT NULL AND image_file_id != ''")
                    with_images = self._get(await cursor.fetchone(), 'cnt', default=0)
                    metrics['attachments_with_images'] = with_images
                    metrics['attachments_without_images'] = metrics['total_attachments'] - with_images
                    metrics['image_coverage'] = with_images / metrics['total_attachments'] * 100 if metrics['total_attachments'] > 0 else 0
                    self.metrics = metrics
                    return metrics
        except Exception as e:
            logger.error(f'Error calculating metrics: {e}')
            return {}

    async def save_results(self) -> int:
        """Save health check results to database"""
        try:
            async with self.db.transaction() as tconn:
                async with tconn.cursor() as cursor:
                    check_id = None
                    try:
                        await cursor.execute('\n                        ALTER TABLE data_health_checks \n                        DROP CONSTRAINT IF EXISTS data_health_checks_severity_check\n                    ')
                    except Exception:
                        pass
                    for severity, issues_list in self.issues.items():
                        for issue in issues_list:
                            if check_id is None:
                                await cursor.execute('\n                                INSERT INTO data_health_checks (\n                                    check_type, severity, category, \n                                    issue_count, details\n                                ) VALUES (%s, %s, %s, %s, %s)\n                                RETURNING id\n                                ', (issue['type'], severity, issue.get('category', 'general'), issue.get('count', 0), json.dumps(issue, ensure_ascii=False)))
                                row = await cursor.fetchone()
                                check_id = self._get(row, 'id')
                            else:
                                await cursor.execute('\n                                INSERT INTO data_health_checks (\n                                    check_type, severity, category, \n                                    issue_count, details\n                                ) VALUES (%s, %s, %s, %s, %s)\n                                ', (issue['type'], severity, issue.get('category', 'general'), issue.get('count', 0), json.dumps(issue, ensure_ascii=False)))
                    if self.metrics:
                        empty_weapons_count = 0
                        for sev in ('CRITICAL', 'WARNING'):
                            for it in self.issues.get(sev, []):
                                if it.get('type') == 'empty_weapons':
                                    empty_weapons_count += int(it.get('count', 0))
                        total_weapons = int(self.metrics.get('total_weapons', 0))
                        total_attachments = int(self.metrics.get('total_attachments', 0))
                        image_coverage = float(self.metrics.get('image_coverage', 0))
                        with_images = int(total_attachments * image_coverage / 100)
                        without_images = int(total_attachments * (100 - image_coverage) / 100)
                        weapons_with_attachments = max(0, total_weapons - empty_weapons_count)
                        weapons_without_attachments = max(0, empty_weapons_count)
                        try:
                            await cursor.execute('\n                            INSERT INTO data_quality_metrics (\n                                total_weapons, total_attachments,\n                                weapons_with_attachments, weapons_without_attachments,\n                                attachments_with_images, attachments_without_images,\n                                health_score\n                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)\n                            ', (total_weapons, total_attachments, weapons_with_attachments, weapons_without_attachments, with_images, without_images, self.calculate_health_score()))
                        except Exception:
                            try:
                                await cursor.execute("\n                                SELECT setval(\n                                  pg_get_serial_sequence('data_quality_metrics','id'),\n                                  COALESCE((SELECT MAX(id) FROM data_quality_metrics), 0) + 1,\n                                  false\n                                )\n                                ")
                                await cursor.execute('\n                                INSERT INTO data_quality_metrics (\n                                    total_weapons, total_attachments,\n                                    weapons_with_attachments, weapons_without_attachments,\n                                    attachments_with_images, attachments_without_images,\n                                    health_score\n                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)\n                                ', (total_weapons, total_attachments, weapons_with_attachments, weapons_without_attachments, with_images, without_images, self.calculate_health_score()))
                            except Exception as retry_err:
                                raise retry_err
            logger.info(f'✅ Results saved to database (Check ID: {check_id})')
            return check_id
        except Exception as e:
            logger.error(f'❌ Error saving results: {e}')
            return None

    async def fix_technical_issues(self) -> bool:
        """Fix technical issues like missing indexes and sequence desyncs."""
        try:
            logger.info('🛠️ Starting technical fix operation...')
            
            # Re-ensure extensions and core schema (including indexes)
            if hasattr(self.db, '_ensure_schema'):
                # _ensure_schema is synchronous in the current implementation, but it calls connect()
                # We can call it directly to rebuild indexes/extensions.
                self.db._ensure_schema()
            
            # Specifically fix sequences
            async with self.db.transaction() as conn:
                async with conn.cursor() as cursor:
                    # Tables and their PK column names for sequence syncing
                    tables_pk = {
                        'analytics_events': 'id',
                        'weapon_categories': 'id',
                        'weapons': 'id',
                        'attachments': 'id',
                        'roles': 'id',
                        'user_attachments': 'id',
                        'user_attachment_reports': 'id',
                        'tickets': 'id',
                        'ticket_replies': 'id',
                        'ticket_attachments': 'id',
                        'faqs': 'id',
                        'feedback': 'id',
                        'search_history': 'id',
                        'guides': 'id',
                        'guide_photos': 'id',
                        'guide_videos': 'id',
                        'data_health_checks': 'id',
                        'data_quality_metrics': 'id',
                        'cms_content': 'content_id',
                        'scheduled_notifications': 'id',
                        'attachment_metrics': 'id'
                    }
                    
                    for tbl, pk_col in tables_pk.items():
                        # Find sequence name safely
                        await cursor.execute(
                            "SELECT pg_get_serial_sequence(%s, %s) as seq", 
                            (tbl, pk_col)
                        )
                        row = await cursor.fetchone()
                        seq = row.get('seq') if row else None
                        
                        if seq:
                            logger.info(f"Syncing sequence {seq} for table {tbl}")
                            # Reset sequence to MAX(pk_col) + 1
                            # We use sql.Identifier for the column name to be safe
                            query = sql.SQL("""
                                SELECT setval(
                                    %s,
                                    COALESCE((SELECT MAX({}) FROM {}), 0) + 1,
                                    false
                                )
                            """).format(sql.Identifier(pk_col), sql.Identifier(tbl))
                            
                            await cursor.execute(query, (seq,))
            
            logger.info('✅ Technical fix operation completed.')
            return True
        except Exception as e:
            logger.error(f'❌ Error fixing technical issues: {e}')
            return False

    def calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0
        critical_count = sum((issue.get('count', 0) for issue in self.issues.get('CRITICAL', [])))
        score -= min(critical_count * 5, 50)
        warning_count = sum((issue.get('count', 0) for issue in self.issues.get('WARNING', [])))
        score -= min(warning_count * 2, 30)
        image_coverage = self.metrics.get('image_coverage', 100)
        if image_coverage < 80:
            score -= (80 - image_coverage) / 2
        return max(0, score)

    def generate_report(self, format='text') -> str:
        """Generate human-readable report"""
        if format == 'text':
            return self._generate_text_report()
        elif format == 'markdown':
            return self._generate_markdown_report()
        else:
            raise ValueError(f'Unknown format: {format}')

    def _generate_text_report(self) -> str:
        """Generate plain text report"""
        lines = []
        lines.append('=' * 50)
        lines.append('📊 DATA HEALTH CHECK REPORT')
        lines.append('=' * 50)
        lines.append(f"🗓️ Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        db_label = 'PostgreSQL'
        if hasattr(self, 'db_path') and self.db_path:
            db_label = os.path.basename(self.db_path)
        lines.append(f'📁 Database: {db_label}')
        lines.append('')
        lines.append('📈 SUMMARY METRICS:')
        lines.append(f"  • Total Categories: {self.metrics.get('total_categories', 0)}")
        lines.append(f"  • Total Weapons: {self.metrics.get('total_weapons', 0)}")
        lines.append(f"  • Total Attachments: {self.metrics.get('total_attachments', 0)}")
        lines.append(f"  • Image Coverage: {self.metrics.get('image_coverage', 0):.1f}%")
        lines.append(f"  • Top Attachments: {self.metrics.get('top_attachments', 0)}")
        lines.append(f"  • Season Best: {self.metrics.get('season_attachments', 0)}")
        lines.append('')
        for severity in ['CRITICAL', 'WARNING', 'INFO']:
            if severity in self.issues:
                lines.append(f"{('❌' if severity == 'CRITICAL' else '⚠️' if severity == 'WARNING' else 'ℹ️')} {severity} ISSUES:")
                for issue in self.issues[severity]:
                    lines.append(f"  • {issue['type']}: {issue.get('count', 0)} found")
                lines.append('')
        score = self.calculate_health_score()
        emoji = '🟢' if score >= 80 else '🟡' if score >= 60 else '🔴'
        lines.append(f'{emoji} HEALTH SCORE: {score:.1f}/100')
        lines.append('=' * 50)
        return '\n'.join(lines)

    def _generate_markdown_report(self) -> str:
        """Generate markdown report"""
        lines = []
        lines.append('# 📊 Data Health Check Report')
        lines.append('')
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        db_label = 'PostgreSQL'
        if hasattr(self, 'db_path') and self.db_path:
            db_label = os.path.basename(self.db_path)
        lines.append(f'**Database:** `{db_label}`')
        lines.append('')
        lines.append('## 📈 Summary Metrics')
        lines.append('')
        lines.append('| Metric | Value |')
        lines.append('|--------|-------|')
        lines.append(f"| Total Categories | {self.metrics.get('total_categories', 0)} |")
        lines.append(f"| Total Weapons | {self.metrics.get('total_weapons', 0)} |")
        lines.append(f"| Total Attachments | {self.metrics.get('total_attachments', 0)} |")
        lines.append(f"| Image Coverage | {self.metrics.get('image_coverage', 0):.1f}% |")
        lines.append(f"| Top Attachments | {self.metrics.get('top_attachments', 0)} |")
        lines.append(f"| Season Best | {self.metrics.get('season_attachments', 0)} |")
        lines.append('')
        if self.metrics.get('category_distribution'):
            lines.append('## 📦 Category Distribution')
            lines.append('')
            lines.append('| Category | Weapons | Attachments |')
            lines.append('|----------|---------|-------------|')
            for cat in self.metrics['category_distribution']:
                lines.append(f"| {cat['category']} | {cat['weapons']} | {cat['attachments']} |")
            lines.append('')
        lines.append('## 🔍 Issues Found')
        lines.append('')
        for severity in ['CRITICAL', 'WARNING', 'INFO']:
            if severity in self.issues:
                emoji = '❌' if severity == 'CRITICAL' else '⚠️' if severity == 'WARNING' else 'ℹ️'
                lines.append(f'### {emoji} {severity}')
                lines.append('')
                for issue in self.issues[severity]:
                    lines.append(f"- **{issue['type']}**: {issue.get('count', 0)} found")
                lines.append('')
        score = self.calculate_health_score()
        emoji = '🟢' if score >= 80 else '🟡' if score >= 60 else '🔴'
        lines.append(f'## {emoji} Health Score: {score:.1f}/100')
        lines.append('')
        lines.append('## 💡 Recommendations')
        lines.append('')
        if 'missing_images' in [i['type'] for i in self.issues.get('CRITICAL', [])]:
            lines.append('1. **Upload missing images** for attachments through admin panel')
        if 'duplicate_codes_local' in [i['type'] for i in self.issues.get('CRITICAL', [])]:
            lines.append('2. **Fix duplicate codes** (per weapon) to ensure unique identification')
        if 'duplicate_codes_global' in [i['type'] for i in self.issues.get('WARNING', [])]:
            lines.append('3. **Review shared codes** across weapons (if they should be unique)')
        if 'invalid_images' in [i['type'] for i in self.issues.get('WARNING', [])]:
            lines.append('4. **Resolve suspicious image IDs** by re-uploading them')
        if 'empty_weapons' in [i['type'] for i in self.issues.get('WARNING', [])]:
            lines.append("5. **Add attachments** to weapons that don't have any")
        return '\n'.join(lines)

    async def check_invalid_images(self) -> List[Dict]:
        """Check for attachments with suspicious or invalid Telegram file IDs"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, code, name, image_file_id 
                        FROM attachments 
                        WHERE image_file_id IS NOT NULL 
                          AND (length(image_file_id) < 20 OR image_file_id ~ '^[0-9]+$')
                    """)
                    invalid_images = []
                    for row in await cursor.fetchall():
                        invalid_images.append({
                            'id': self._get(row, 'id'),
                            'code': self._get(row, 'code'),
                            'name': self._get(row, 'name'),
                            'file_id': self._get(row, 'image_file_id'),
                            'issue': 'suspicious_file_id'
                        })
                    
                    if invalid_images:
                        self.issues['WARNING'].append({'type': 'invalid_images', 'count': len(invalid_images), 'details': invalid_images})
                        logger.warning(f'⚠️ Found {len(invalid_images)} attachments with suspicious image IDs')
                    return invalid_images
        except Exception as e:
            logger.error(f'Error checking invalid images: {e}')
            return []

    async def check_slow_searches(self, threshold_ms: int=500) -> List[Dict]:
        """Check search history for frequent queries"""
        try:
            async with self.db.get_connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT query, COUNT(*) as count, AVG(length(query)) as avg_len
                        FROM search_history
                        WHERE created_at > NOW() - INTERVAL '7 days'
                        GROUP BY query
                        HAVING COUNT(*) > 5
                        ORDER BY count DESC
                        LIMIT 20
                    """)
                    stats = []
                    for row in await cursor.fetchall():
                        stats.append({
                            'query': self._get(row, 'query'),
                            'count': self._get(row, 'count'),
                            'avg_len': self._get(row, 'avg_len'),
                            'issue': 'frequent_query'
                        })
                    
                    if stats:
                        self.issues['INFO'].append({
                            'type': 'slow_searches',
                            'count': len(stats),
                            'details': stats
                        })
                        logger.info(f'ℹ️ Found {len(stats)} frequent/potentially slow searches')
                    return stats
        except Exception as e:
            logger.error(f'Error checking slow searches: {e}')
            return []

    async def run_full_check(self, save_to_db=True) -> Dict:
        """Run all health checks"""
        logger.info('🔍 Starting data health check...')
        await self.check_missing_images()
        await self.check_duplicate_codes()
        await self.check_empty_weapons()
        await self.check_sparse_weapons()
        await self.check_orphaned_attachments()
        await self.check_data_freshness()
        await self.check_invalid_images()
        await self.check_slow_searches()
        await self.check_required_indexes()
        await self.check_sequences_synced()
        await self.check_schema_columns()
        await self.calculate_metrics()
        check_id = None
        if save_to_db:
            check_id = await self.save_results()
        text_report = self.generate_report('text')
        markdown_report = self.generate_report('markdown')
        print(text_report)
        try:
            import tempfile
            report_dir = os.environ.get('HEALTH_REPORT_DIR', tempfile.gettempdir())
            report_path = os.path.join(report_dir, f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(markdown_report)
            logger.info(f'📝 Report saved to: {report_path}')
        except Exception as e:
            logger.warning(f'Could not save report to file: {e}')
            report_path = None
        return {'check_id': check_id, 'health_score': self.calculate_health_score(), 'critical_count': sum((i.get('count', 0) for i in self.issues.get('CRITICAL', []))), 'warning_count': sum((i.get('count', 0) for i in self.issues.get('WARNING', []))), 'info_count': sum((i.get('count', 0) for i in self.issues.get('INFO', []))), 'report_path': report_path}
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Check data health and quality')
    parser.add_argument('--auto-fix', action='store_true', help='Automatically fix simple issues (USE WITH CAUTION)')
    parser.add_argument('--no-save', action='store_true', help="Don't save results to database")
    parser.add_argument('--format', choices=['text', 'markdown'], default='text', help='Output format')
    args = parser.parse_args()
    async def main():
        checker = DataHealthChecker(auto_fix=args.auto_fix)
        results = await checker.run_full_check(save_to_db=not args.no_save)
        if results['critical_count'] > 0:
            sys.exit(1)
            
    asyncio.run(main())