"""
PostgreSQL Database Wrapper
این wrapper تمام عملیات DatabaseSQL را با PostgreSQL پیاده\u200cسازی می\u200cکند
"""
import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from utils.logger import get_logger, log_exception
from utils.metrics import measure_query_time
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
logger = get_logger('database.postgres', 'database.log')

class DatabasePostgres:
    """
    PostgreSQL Database Handler
    Compatible با DatabaseSQL interface - تمام متدها را دارد
    """

    def __init__(self, database_url: str=None):
        """
        Initialize PostgreSQL connection settings
        
        Args:
            database_url: PostgreSQL connection string
        """
        if database_url is None:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError('DATABASE_URL is required for PostgreSQL')
        self.database_url = database_url
        self.db_path = database_url.split('@')[-1] if '@' in database_url else '[hidden]'
        pool_size = int(os.getenv('DB_POOL_SIZE', 20))
        max_overflow = int(os.getenv('DB_POOL_MAX_OVERFLOW', 10))
        pool_timeout = float(os.getenv('DB_POOL_TIMEOUT', 30.0))
        
        self._pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=2,
            max_size=pool_size + max_overflow,
            kwargs={'row_factory': dict_row},
            open=False,
            timeout=pool_timeout
        )
        self.fuzzy_engine = None
        
        # Repositories for modular access
        from .repositories.user_repository import UserRepository
        from .repositories.attachment_repository import AttachmentRepository
        from .repositories.settings_repository import SettingsRepository
        from .repositories.analytics_repository import AnalyticsRepository
        from .repositories.cms_repository import CMSRepository
        from .repositories.support_repository import SupportRepository
        
        self.users = UserRepository(self)
        self.attachments = AttachmentRepository(self)
        self.settings = SettingsRepository(self)
        self.analytics = AnalyticsRepository(self)
        self.cms = CMSRepository(self)
        self.support = SupportRepository(self)
        
        # Backup Manager
        from managers.backup_manager import BackupManager
        self.backup_manager = BackupManager(self)
        
        logger.info(f'PostgreSQL connection pool initialized (ready for open): {pool_size} connections')
        
    async def is_postgres(self) -> bool:
        """برگرداندن True برای تمام موارد در این کلاس"""
        return True
        
    def is_postgres_sync(self) -> bool:
        """نسخه سنکرون"""
        return True

    async def initialize(self):
        """راه‌اندازی نامتقارن (Async) اتصال‌ها با retry logic"""
        await self._connect_with_retry()
        
        await self._init_fuzzy_engine()
        # _ensure_schema contains sync code and should remain sync-compatible or async
        self._ensure_schema()
        logger.info('DatabasePostgres opened and initialized successfully')
    
    @retry(
        stop=stop_after_attempt(int(os.getenv('DB_RETRY_ATTEMPTS', '3'))),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((psycopg.OperationalError, psycopg.InterfaceError, ConnectionError, OSError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Database connection attempt {retry_state.attempt_number} failed, retrying in {retry_state.next_action.sleep} seconds..."
        ),
        reraise=True
    )
    async def _connect_with_retry(self):
        """Establish database connection with exponential backoff retry"""
        try:
            await self._pool.open()
            async with self.get_connection() as conn:
                cursor = conn.cursor()
                await cursor.execute('SELECT version() as version')
                result = await cursor.fetchone()
                version = result['version'] if result else 'unknown'
                logger.info(f"Connected to: {version.split(',')[0]}")
        except Exception as e:
            logger.error(f'Failed to open PostgreSQL pool: {e}')
            log_exception(logger, e, 'DatabasePostgres._connect_with_retry')
            raise



    @asynccontextmanager
    async def get_connection(self):
        """Context manager برای دریافت connection از pool"""
        async with self._pool.connection() as conn:
            try:
                yield conn
            finally:
                # Always ensure rollback to clean up any aborted or pending transaction 
                # before returning the connection to the pool.
                try:
                    if not conn.closed:
                        await conn.rollback()
                except Exception:
                    pass

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager برای transaction
        Compatible با DatabaseSQL.transaction()
        """
        async with self.get_connection() as conn:
            try:
                yield conn
                await conn.commit()
            except psycopg.Error as e:
                await conn.rollback()
                logger.error(f'PostgreSQL transaction error: {e}')
                log_exception(logger, e, 'transaction')
                raise
            except Exception as e:
                await conn.rollback()
                logger.error(f'Transaction error: {e}')
                log_exception(logger, e, 'transaction')
                raise

    async def execute_query(self, query: str, params: tuple=None, fetch_one: bool=False, fetch_all: bool=False, as_dict: bool=True) -> Any:
        """
        اجرای query با تبدیل خودکار placeholders و tracking performance
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                try:
                    with measure_query_time(query[:200], params):
                        await cursor.execute(query, params or ())
                    if fetch_one:
                        result = await cursor.fetchone()
                        return dict(result) if result and as_dict else result
                    elif fetch_all:
                        results = await cursor.fetchall()
                        return [dict(r) for r in results] if as_dict else results
                    else:
                        await conn.commit()
                        return cursor.rowcount
                except psycopg.Error as e:
                    await conn.rollback()
                    logger.error(f'PostgreSQL query error: {e}')
                    logger.error(f'Query: {query[:200]}')
                    logger.error(f'Params: {params}')
                    raise
                except Exception as e:
                    await conn.rollback()
                    logger.error(f'Query execution error: {e}')
                    logger.error(f'Query: {query[:200]}')
                    raise

    async def _init_fuzzy_engine(self):
        """راه\u200cاندازی fuzzy search (compatible با DatabaseSQL)"""
        try:
            from utils.search_fuzzy import FuzzySearchEngine
            self.fuzzy_engine = FuzzySearchEngine(self)
            logger.info('Fuzzy search engine initialized')
        except ImportError:
            logger.warning('FuzzySearchEngine not available')
        except Exception as e:
            logger.error(f'Failed to initialize fuzzy search: {e}')

    def _ensure_schema(self):
        """
        Ensure required columns/tweaks exist on PostgreSQL schema.
        This is a safe, idempotent guard that runs at startup.
        """
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
                cursor = conn.cursor()

                def _column_exists(table: str, column: str) -> bool:
                    cursor.execute('\n                        SELECT 1\n                        FROM information_schema.columns\n                        WHERE table_schema = current_schema()\n                          AND table_name = %s\n                          AND column_name = %s\n                        ', (table, column))
                    return cursor.fetchone() is not None

                def _table_exists(table: str) -> bool:
                    cursor.execute('\n                        SELECT EXISTS (\n                            SELECT 1\n                            FROM information_schema.tables\n                            WHERE table_schema = current_schema()\n                              AND table_name = %s\n                        ) AS exists\n                        ', (table,))
                    row = cursor.fetchone()
                    return bool(row.get('exists')) if row else False
                try:
                    cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
                    conn.commit()
                    cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent')
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.warning(f'ensure_schema(extensions) warning: {e}')
                tables_sql = [
                    "\n                    CREATE TABLE IF NOT EXISTS analytics_events (\n                        id SERIAL PRIMARY KEY,\n                        user_id BIGINT,\n                        event_type TEXT NOT NULL,\n                        metadata JSONB,\n                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS weapon_categories (\n                        id SERIAL PRIMARY KEY,\n                        name TEXT NOT NULL UNIQUE,\n                        display_name TEXT,\n                        icon TEXT,\n                        sort_order INTEGER DEFAULT 0,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS weapons (\n                        id SERIAL PRIMARY KEY,\n                        category_id INTEGER NOT NULL REFERENCES weapon_categories(id) ON DELETE CASCADE,\n                        name TEXT NOT NULL,\n                        display_name TEXT,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP,\n                        UNIQUE (category_id, name)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS attachments (\n                        id SERIAL PRIMARY KEY,\n                        weapon_id INTEGER NOT NULL REFERENCES weapons(id) ON DELETE CASCADE,\n                        mode TEXT NOT NULL CHECK (mode IN ('br', 'mp')),\n                        code TEXT NOT NULL,\n                        name TEXT NOT NULL,\n                        image_file_id TEXT,\n                        is_top BOOLEAN NOT NULL DEFAULT FALSE,\n                        is_season_top BOOLEAN NOT NULL DEFAULT FALSE,\n                        order_index INTEGER,\n                        views_count INTEGER DEFAULT 0,\n                        shares_count INTEGER DEFAULT 0,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMPTZ DEFAULT NOW(),\n                        CONSTRAINT uq_attachment UNIQUE (weapon_id, mode, code)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS users (\n                        user_id BIGINT PRIMARY KEY,\n                        username TEXT,\n                        first_name TEXT,\n                        last_name TEXT,\n                        language TEXT DEFAULT 'fa' CHECK (language IN ('fa', 'en')),\n                        is_banned BOOLEAN DEFAULT FALSE,\n                        ban_reason TEXT,\n                        banned_until TIMESTAMP,\n                        last_seen TIMESTAMP,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS roles (\n                        id SERIAL PRIMARY KEY,\n                        name TEXT NOT NULL UNIQUE,\n                        display_name TEXT NOT NULL,\n                        description TEXT,\n                        icon TEXT,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS role_permissions (\n                        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,\n                        permission TEXT NOT NULL,\n                        PRIMARY KEY (role_id, permission)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS admins (\n                        user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,\n                        display_name TEXT,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS admin_roles (\n                        user_id BIGINT NOT NULL REFERENCES admins(user_id) ON DELETE CASCADE,\n                        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,\n                        assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        assigned_by BIGINT,\n                        PRIMARY KEY (user_id, role_id)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS user_attachments (\n                        id SERIAL PRIMARY KEY,\n                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,\n                        weapon_id INTEGER REFERENCES weapons(id) ON DELETE SET NULL,\n                        mode TEXT NOT NULL CHECK (mode IN ('br', 'mp')),\n                        category TEXT,\n                        custom_weapon_name TEXT,\n                        attachment_name TEXT NOT NULL,\n                        description TEXT,\n                        image_file_id TEXT,\n                        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),\n                        submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        approved_at TIMESTAMP,\n                        approved_by BIGINT REFERENCES admins(user_id),\n                        rejected_at TIMESTAMP,\n                        rejected_by BIGINT REFERENCES admins(user_id),\n                        rejection_reason TEXT,\n                        like_count INTEGER NOT NULL DEFAULT 0,\n                        report_count INTEGER NOT NULL DEFAULT 0,\n                        views_count INTEGER DEFAULT 0\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS user_submission_stats (\n                        user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,\n                        total_submissions INTEGER NOT NULL DEFAULT 0,\n                        approved_count INTEGER NOT NULL DEFAULT 0,\n                        rejected_count INTEGER NOT NULL DEFAULT 0,\n                        pending_count INTEGER NOT NULL DEFAULT 0,\n                        daily_submissions INTEGER NOT NULL DEFAULT 0,\n                        daily_reset_date DATE,\n                        violation_count INTEGER NOT NULL DEFAULT 0,\n                        strike_count REAL NOT NULL DEFAULT 0,\n                        last_submission_at TIMESTAMP,\n                        updated_at TIMESTAMP,\n                        is_banned BOOLEAN NOT NULL DEFAULT FALSE,\n                        banned_reason TEXT,\n                        banned_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS user_attachment_engagement (\n                        user_id BIGINT NOT NULL,\n                        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,\n                        rating SMALLINT CHECK (rating IN (-1, 1)),\n                        total_views INTEGER DEFAULT 0,\n                        total_clicks INTEGER DEFAULT 0,\n                        first_view_date TIMESTAMP,\n                        last_view_date TIMESTAMP,\n                        feedback TEXT,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP,\n                        PRIMARY KEY (user_id, attachment_id)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS user_attachment_reports (\n                        id SERIAL PRIMARY KEY,\n                        attachment_id INTEGER NOT NULL REFERENCES user_attachments(id) ON DELETE CASCADE,\n                        reporter_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,\n                        reason TEXT,\n                        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'resolved', 'dismissed')),\n                        reported_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        resolved_by BIGINT REFERENCES admins(user_id),\n                        resolved_at TIMESTAMP,\n                        resolution_notes TEXT\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS tickets (\n                        id SERIAL PRIMARY KEY,\n                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,\n                        category TEXT,\n                        subject TEXT NOT NULL,\n                        description TEXT,\n                        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'waiting_user', 'resolved', 'closed')),\n                        priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),\n                        assigned_to BIGINT REFERENCES admins(user_id),\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP,\n                        closed_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS ticket_replies (\n                        id SERIAL PRIMARY KEY,\n                        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,\n                        user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,\n                        message TEXT NOT NULL,\n                        is_admin BOOLEAN NOT NULL DEFAULT FALSE,\n                        attachments TEXT[],\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS ticket_attachments (\n                        id SERIAL PRIMARY KEY,\n                        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,\n                        reply_id INTEGER REFERENCES ticket_replies(id) ON DELETE CASCADE,\n                        file_id TEXT NOT NULL,\n                        file_type TEXT,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS faqs (\n                        id SERIAL PRIMARY KEY,\n                        question TEXT NOT NULL,\n                        answer TEXT NOT NULL,\n                        category TEXT,\n                        language TEXT DEFAULT 'fa' CHECK (language IN ('fa', 'en')),\n                        views INTEGER NOT NULL DEFAULT 0,\n                        helpful_count INTEGER NOT NULL DEFAULT 0,\n                        not_helpful_count INTEGER NOT NULL DEFAULT 0,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS feedback (\n                        id SERIAL PRIMARY KEY,\n                        user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,\n                        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),\n                        category TEXT,\n                        message TEXT,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS search_history (\n                        id SERIAL PRIMARY KEY,\n                        user_id BIGINT,\n                        query TEXT NOT NULL,\n                        results_count INTEGER NOT NULL DEFAULT 0,\n                        execution_time_ms REAL NOT NULL DEFAULT 0,\n                        search_type TEXT,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS popular_searches (\n                        query TEXT PRIMARY KEY,\n                        search_count INTEGER NOT NULL DEFAULT 0,\n                        last_searched TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS suggested_attachments (\n                        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,\n                        mode TEXT NOT NULL CHECK (mode IN ('br', 'mp')),\n                        priority INTEGER NOT NULL DEFAULT 999,\n                        reason TEXT,\n                        added_by BIGINT REFERENCES admins(user_id),\n                        added_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        is_active BOOLEAN DEFAULT TRUE,\n                        UNIQUE (attachment_id, mode)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS required_channels (\n                        channel_id TEXT PRIMARY KEY,\n                        title TEXT NOT NULL,\n                        url TEXT NOT NULL,\n                        priority INTEGER NOT NULL DEFAULT 999,\n                        is_active BOOLEAN NOT NULL DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS blacklisted_words (\n                        word TEXT PRIMARY KEY,\n                        category TEXT NOT NULL DEFAULT 'general',\n                        severity INTEGER NOT NULL DEFAULT 1 CHECK (severity >= 1 AND severity <= 3),\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS settings (\n                        key TEXT PRIMARY KEY,\n                        value TEXT,\n                        description TEXT,\n                        category TEXT,\n                        data_type TEXT DEFAULT 'string' CHECK (data_type IN ('string', 'integer', 'boolean', 'json')),\n                        updated_by BIGINT,\n                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS guides (\n                        id SERIAL PRIMARY KEY,\n                        key TEXT NOT NULL UNIQUE,\n                        mode TEXT NOT NULL CHECK (mode IN ('br', 'mp')),\n                        name TEXT,\n                        code TEXT,\n                        description TEXT,\n                        is_active BOOLEAN DEFAULT TRUE,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMP\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS guide_photos (\n                        id SERIAL PRIMARY KEY,\n                        guide_id INTEGER NOT NULL REFERENCES guides(id) ON DELETE CASCADE,\n                        file_id TEXT NOT NULL,\n                        caption TEXT,\n                        sort_order INTEGER DEFAULT 0\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS guide_videos (\n                        id SERIAL PRIMARY KEY,\n                        guide_id INTEGER NOT NULL REFERENCES guides(id) ON DELETE CASCADE,\n                        file_id TEXT NOT NULL,\n                        caption TEXT,\n                        sort_order INTEGER DEFAULT 0\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS ua_stats_cache (\n                        id INTEGER PRIMARY KEY DEFAULT 1,\n                        total_attachments INTEGER DEFAULT 0,\n                        pending_count INTEGER DEFAULT 0,\n                        approved_count INTEGER DEFAULT 0,\n                        rejected_count INTEGER DEFAULT 0,\n                        total_users INTEGER DEFAULT 0,\n                        active_users INTEGER DEFAULT 0,\n                        banned_users INTEGER DEFAULT 0,\n                        br_count INTEGER DEFAULT 0,\n                        mp_count INTEGER DEFAULT 0,\n                        total_likes INTEGER DEFAULT 0,\n                        total_reports INTEGER DEFAULT 0,\n                        pending_reports INTEGER DEFAULT 0,\n                        last_week_submissions INTEGER DEFAULT 0,\n                        last_week_approvals INTEGER DEFAULT 0,\n                        updated_at TIMESTAMP DEFAULT NOW(),\n                        CONSTRAINT single_row_cache CHECK (id = 1)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS ua_top_weapons_cache (\n                        weapon_name TEXT NOT NULL,\n                        mode TEXT,\n                        attachment_count INTEGER NOT NULL,\n                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS ua_top_users_cache (\n                        user_id BIGINT NOT NULL,\n                        username TEXT,\n                        approved_count INTEGER NOT NULL,\n                        total_likes INTEGER NOT NULL,\n                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS data_health_checks (\n                        id SERIAL PRIMARY KEY,\n                        check_type TEXT NOT NULL,\n                        severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),\n                        category TEXT,\n                        issue_count INTEGER NOT NULL DEFAULT 0,\n                        details JSONB,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS data_quality_metrics (\n                        id SERIAL PRIMARY KEY,\n                        total_weapons INTEGER NOT NULL DEFAULT 0,\n                        total_attachments INTEGER NOT NULL DEFAULT 0,\n                        weapons_with_attachments INTEGER NOT NULL DEFAULT 0,\n                        weapons_without_attachments INTEGER NOT NULL DEFAULT 0,\n                        attachments_with_images INTEGER NOT NULL DEFAULT 0,\n                        attachments_without_images INTEGER NOT NULL DEFAULT 0,\n                        health_score REAL NOT NULL DEFAULT 0,\n                        created_at TIMESTAMP NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS user_notification_preferences (\n                        user_id BIGINT PRIMARY KEY,\n                        enabled BOOLEAN NOT NULL DEFAULT TRUE,\n                        modes JSONB NOT NULL DEFAULT \'[\"br\",\"mp\"]\'::jsonb,\n                        events JSONB NOT NULL DEFAULT \'{}\'::jsonb,\n                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS scheduled_notifications (\n                        id SERIAL PRIMARY KEY,\n                        message_type TEXT NOT NULL CHECK (message_type IN ('text','photo')),\n                        message_text TEXT,\n                        photo_file_id TEXT,\n                        parse_mode TEXT DEFAULT 'Markdown',\n                        interval_hours INTEGER NOT NULL,\n                        enabled BOOLEAN NOT NULL DEFAULT TRUE,\n                        last_sent_at TIMESTAMPTZ,\n                        next_run_at TIMESTAMPTZ NOT NULL,\n                        created_by BIGINT,\n                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS attachment_metrics (\n                        id SERIAL PRIMARY KEY,\n                        attachment_id INTEGER NOT NULL,\n                        user_id BIGINT,\n                        action_type TEXT NOT NULL CHECK (action_type IN ('view','click','share','copy','rate')),\n                        session_id TEXT,\n                        metadata JSONB,\n                        action_date TIMESTAMPTZ NOT NULL DEFAULT NOW()\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS attachment_performance (\n                        attachment_id INTEGER NOT NULL,\n                        performance_date DATE NOT NULL,\n                        popularity_score REAL NOT NULL DEFAULT 0,\n                        trending_score REAL NOT NULL DEFAULT 0,\n                        engagement_rate REAL NOT NULL DEFAULT 0,\n                        quality_score REAL NOT NULL DEFAULT 0,\n                        rank_in_weapon INTEGER,\n                        rank_overall INTEGER,\n                        PRIMARY KEY (attachment_id, performance_date)\n                    )\n                    ",
                    "\n                    CREATE TABLE IF NOT EXISTS cms_content (\n                        content_id SERIAL PRIMARY KEY,\n                        content_type TEXT NOT NULL,\n                        title TEXT NOT NULL,\n                        body TEXT NOT NULL,\n                        tags JSONB NOT NULL DEFAULT '[]'::jsonb,\n                        author_id BIGINT,\n                        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),\n                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n                        published_at TIMESTAMPTZ\n                    )\n                    "
                ]
                for sql in tables_sql:
                    try:
                        cursor.execute(sql)
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.error(f'ensure_schema(create table) error: {e}')
                indexes_sql = ['CREATE INDEX IF NOT EXISTS idx_attachments_weapon_mode ON attachments (weapon_id, mode)', 'CREATE INDEX IF NOT EXISTS idx_attachments_is_top ON attachments (weapon_id, mode) WHERE is_top = TRUE', 'CREATE INDEX IF NOT EXISTS idx_attachments_code_trgm ON attachments USING gin (code gin_trgm_ops)', 'CREATE INDEX IF NOT EXISTS idx_attachments_name_trgm ON attachments USING gin (name gin_trgm_ops)', 'CREATE INDEX IF NOT EXISTS idx_weapons_name_trgm ON weapons USING gin (name gin_trgm_ops)', 'CREATE INDEX IF NOT EXISTS idx_attachments_search_composite ON attachments (weapon_id, mode, is_top DESC, is_season_top DESC)', 'CREATE INDEX IF NOT EXISTS idx_attachments_views ON attachments (views_count DESC)', 'CREATE INDEX IF NOT EXISTS idx_users_language ON users (language)', 'CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users (last_seen DESC)', 'CREATE INDEX IF NOT EXISTS idx_user_attachments_status ON user_attachments (status, submitted_at DESC)', 'CREATE INDEX IF NOT EXISTS idx_user_attachments_user ON user_attachments (user_id)', 'CREATE INDEX IF NOT EXISTS idx_ua_user_status_submitted ON user_attachments (user_id, status, submitted_at DESC)', "CREATE INDEX IF NOT EXISTS idx_user_attachments_approved ON user_attachments (approved_at DESC) WHERE status = 'approved'", 'CREATE INDEX IF NOT EXISTS idx_uae_attachment_rating ON user_attachment_engagement (attachment_id, rating)', 'CREATE INDEX IF NOT EXISTS idx_uae_attachment_views ON user_attachment_engagement (attachment_id, total_views DESC)', 'CREATE INDEX IF NOT EXISTS idx_uar_attachment ON user_attachment_reports (attachment_id)', 'CREATE INDEX IF NOT EXISTS idx_uar_status ON user_attachment_reports (status, reported_at DESC)', "CREATE UNIQUE INDEX IF NOT EXISTS ux_uar_att_reporter ON user_attachment_reports (attachment_id, reporter_id) WHERE status = 'pending'", 'CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status, created_at DESC)', 'CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets (user_id)', 'CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets (assigned_to) WHERE assigned_to IS NOT NULL', 'CREATE INDEX IF NOT EXISTS idx_ticket_replies_ticket ON ticket_replies (ticket_id, created_at)', 'CREATE INDEX IF NOT EXISTS idx_faqs_category ON faqs (category) WHERE is_active = TRUE', 'CREATE INDEX IF NOT EXISTS idx_faqs_language ON faqs (language) WHERE is_active = TRUE', 'CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history (created_at DESC)', 'CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history (user_id) WHERE user_id IS NOT NULL', 'CREATE INDEX IF NOT EXISTS idx_suggested_mode_priority ON suggested_attachments (mode, priority) WHERE is_active = TRUE', 'CREATE INDEX IF NOT EXISTS idx_required_channels_priority ON required_channels (priority ASC) WHERE is_active = TRUE', 'CREATE INDEX IF NOT EXISTS idx_ua_top_weapons_count ON ua_top_weapons_cache (attachment_count DESC)', 'CREATE INDEX IF NOT EXISTS idx_ua_top_users_approved ON ua_top_users_cache (approved_count DESC)', 'CREATE INDEX IF NOT EXISTS idx_health_checks_created ON data_health_checks (created_at DESC)', 'CREATE UNIQUE INDEX IF NOT EXISTS ux_attachments_weapon_mode_code ON attachments (weapon_id, mode, code)', 'CREATE UNIQUE INDEX IF NOT EXISTS ux_suggested_attachment_mode ON suggested_attachments (attachment_id, mode)', 'CREATE INDEX IF NOT EXISTS ix_suggested_mode ON suggested_attachments (mode)', 'CREATE INDEX IF NOT EXISTS ix_uae_attachment_id ON user_attachment_engagement (attachment_id)', 'CREATE INDEX IF NOT EXISTS ix_uae_attachment_id_rating ON user_attachment_engagement (attachment_id, rating)', 'CREATE INDEX IF NOT EXISTS ix_ticket_attachments_ticket_id ON ticket_attachments (ticket_id)', 'CREATE INDEX IF NOT EXISTS ix_ticket_attachments_reply_id ON ticket_attachments (reply_id)', 'CREATE INDEX IF NOT EXISTS ix_sched_notif_next_run ON scheduled_notifications (next_run_at)', 'CREATE INDEX IF NOT EXISTS ix_sched_notif_enabled_next ON scheduled_notifications (enabled, next_run_at)', 'CREATE INDEX IF NOT EXISTS ix_am_attachment_date ON attachment_metrics (attachment_id, action_date)', 'CREATE INDEX IF NOT EXISTS ix_am_action_date ON attachment_metrics (action_type, action_date)', 'CREATE INDEX IF NOT EXISTS ix_am_attachment_action ON attachment_metrics (attachment_id, action_type)', 'CREATE INDEX IF NOT EXISTS ix_am_user ON attachment_metrics (user_id)', 'CREATE INDEX IF NOT EXISTS ix_uae_attachment ON user_attachment_engagement (attachment_id)', 'CREATE INDEX IF NOT EXISTS ix_cms_content_status_pub ON cms_content (status, published_at DESC)', 'CREATE INDEX IF NOT EXISTS ix_cms_content_type_status ON cms_content (content_type, status)', 'CREATE INDEX IF NOT EXISTS ix_cms_content_tags_gin ON cms_content USING gin (tags)']
                for sql in indexes_sql:
                    try:
                        cursor.execute(sql)
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.warning(f'ensure_schema(create index) warning: {e}')
                try:
                    cursor.execute("\n                        INSERT INTO weapon_categories (name, display_name, sort_order) VALUES\n                            ('assault_rifle', 'Assault Rifle', 1),\n                            ('smg', 'SMG', 2),\n                            ('lmg', 'LMG', 3),\n                            ('sniper', 'Sniper', 4),\n                            ('marksman', 'Marksman', 5),\n                            ('shotgun', 'Shotgun', 6),\n                            ('pistol', 'Pistol', 7),\n                            ('launcher', 'Launcher', 8)\n                        ON CONFLICT (name) DO UPDATE SET\n                            display_name = EXCLUDED.display_name,\n                            sort_order = EXCLUDED.sort_order\n                    ")
                    # NOTE: Roles are managed exclusively by RoleManager._init_predefined_roles().
                    # Do NOT seed roles here -- it would re-insert obsolete roles on every startup.
                    cursor.execute("\n                        INSERT INTO settings (key, value, description, category, data_type, updated_at)\n                        VALUES ('system_enabled', 'true', 'Enable/Disable User Attachments System', 'user_attachments', 'boolean', NOW())\n                        ON CONFLICT (key) DO NOTHING\n                    ")
                    cursor.execute('INSERT INTO ua_stats_cache (id) VALUES (1) ON CONFLICT DO NOTHING')
                    
                    # Ensure deleted_count exists in ua_stats_cache
                    if not _column_exists('ua_stats_cache', 'deleted_count'):
                        cursor.execute('ALTER TABLE ua_stats_cache ADD COLUMN deleted_count INTEGER DEFAULT 0')
                        logger.info('Added deleted_count column to ua_stats_cache')
                    
                    # Ensure registration_source exists in analytics_users
                    if _table_exists('analytics_users') and not _column_exists('analytics_users', 'registration_source'):
                        cursor.execute('ALTER TABLE analytics_users ADD COLUMN registration_source TEXT')
                        logger.info('Added registration_source column to analytics_users')
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f'ensure_schema(seed data) error: {e}')
                logger.info('Database schema ensured successfully')
        except Exception as e:
            logger.error(f'Database schema check failed: {e}')

    # get_users_for_notification has been moved to UserRepository

    async def close(self):
        """بستن connection pool"""
        if hasattr(self, '_pool'):
            try:
                try:
                    wait_timeout = float(os.getenv('DB_POOL_WAIT_TIMEOUT', '2'))
                except Exception:
                    wait_timeout = 2.0
                try:
                    close_timeout = float(os.getenv('DB_POOL_CLOSE_TIMEOUT', '10'))
                except Exception:
                    close_timeout = 10.0
                suppress_warn = str(os.getenv('DB_SUPPRESS_POOL_WARNINGS', 'false')).lower() in ('1', 'true', 'yes')
                pool_logger = logging.getLogger('psycopg.pool')
                previous_level = pool_logger.level if suppress_warn else None
                if suppress_warn:
                    try:
                        pool_logger.setLevel(logging.ERROR)
                    except Exception:
                        pass
                
                # Async variants of pool methods
                if hasattr(self, '_pool') and self._pool:
                    try:
                        # Check if pool is actually open before waiting/closing
                        # This prevents "PoolClosed" error if bot crashed before DB init
                        await self._pool.wait(timeout=wait_timeout)
                        await self._pool.close(timeout=close_timeout)
                        logger.info('PostgreSQL connection pool closed gracefully')
                    except Exception as pool_err:
                        if "not open yet" in str(pool_err):
                            logger.info("PostgreSQL pool was not initialized, skipping close.")
                        else:
                            raise
                else:
                    logger.info("PostgreSQL pool was not created, skipping close.")
            except Exception as e:
                try:
                    await self._pool.close(timeout=0)
                except Exception as close_exc:
                    logger.exception(f'Error forcing PostgreSQL pool close: {close_exc}')
                logger.exception(f'Connection pool forced close: {e}')
            finally:
                if 'suppress_warn' in locals() and suppress_warn and (previous_level is not None):
                    try:
                        pool_logger.setLevel(previous_level)
                    except Exception:
                        pass

    async def get_all_blacklisted_words(self) -> List[Dict]:
        """دریافت تمام کلمات ممنوعه برای ContentValidator"""
        query = "SELECT word, category, severity FROM blacklisted_words"
        return await self.execute_query(query, fetch_all=True)

    # ========== Settings & Scheduler Methods ==========

    async def get_setting(self, key: str, default: str = None) -> str:
        """دریافت تنظیمات"""
        try:
            query = "SELECT value FROM settings WHERE key = %s"
            result = await self.execute_query(query, (key,), fetch_one=True)
            return result['value'] if result else default
        except Exception as e:
            logger.error(f"Error in get_setting({key}): {e}")
            return default

    async def set_setting(self, key: str, value: str, description: str = None, category: str = 'general') -> bool:
        """تنظیم/به‌روزرسانی تنظیمات"""
        try:
            query = """
                INSERT INTO settings (key, value, description, category, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    description = COALESCE(EXCLUDED.description, settings.description),
                    category = COALESCE(EXCLUDED.category, settings.category),
                    updated_at = NOW()
            """
            await self.execute_query(query, (key, value, description, category))
            return True
        except Exception as e:
            logger.error(f"Error in set_setting({key}): {e}")
            return False

    async def get_due_scheduled_notifications(self, now_ts) -> List[Dict]:
        """دریافت اعلان‌های سررسید شده"""
        try:
            query = """
                SELECT * FROM scheduled_notifications
                WHERE enabled = TRUE AND next_run_at <= %s
                ORDER BY next_run_at ASC
            """
            return await self.execute_query(query, (now_ts,), fetch_all=True)
        except Exception as e:
            logger.error(f"Error in get_due_scheduled_notifications: {e}")
            return []

    async def mark_schedule_sent(self, schedule_id: int, last_sent_at, next_run_at) -> bool:
        """به‌روزرسانی زمان ارسال برای یک اعلان زمان‌بندی شده"""
        try:
            query = """
                UPDATE scheduled_notifications
                SET last_sent_at = %s,
                    next_run_at = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            await self.execute_query(query, (last_sent_at, next_run_at, schedule_id))
            return True
        except Exception as e:
            logger.error(f"Error in mark_schedule_sent({schedule_id}): {e}")
            return False

    # ========== Proxy Methods for Repository Logic (Backward Compatibility) ==========

    async def get_user_language(self, user_id: int) -> Optional[str]:
        return await self.users.get_user_language(user_id)

    async def set_user_language(self, user_id: int, lang: str) -> bool:
        return await self.users.set_user_language(user_id, lang)

    async def create_role_if_not_exists(self, *args, **kwargs) -> bool:
        return await self.users.create_role_if_not_exists(*args, **kwargs)

    async def is_admin(self, user_id: int) -> bool:
        return await self.users.is_admin(user_id)

    async def get_all_admins(self) -> List[Dict]:
        return await self.users.get_all_admins()

    async def get_user_role(self, user_id: int):
        return await self.users.get_user_role(user_id)

    async def get_ua_setting(self, key: str, default: Any = None) -> Any:
        return await self.settings.get_ua_setting(key, default)

    async def get_all_attachments(self, *args, **kwargs):
        return await self.attachments.get_all_attachments(*args, **kwargs)

    async def get_attachment_by_id(self, attachment_id: int):
        return await self.attachments.get_attachment_by_id(attachment_id)

    async def get_suggested_count(self, mode: str = None) -> int:
        return await self.attachments.get_suggested_count(mode)

    async def get_suggested_ranked(self, *args, **kwargs):
        return await self.attachments.get_suggested_ranked(*args, **kwargs)

    async def search(self, query_text: str):
        return await self.attachments.search(query_text)

    async def track_search(self, *args, **kwargs):
        return await self.analytics.track_search(*args, **kwargs)

    async def track_attachment_view(self, *args, **kwargs):
        return await self.analytics.track_attachment_view(*args, **kwargs)

    async def get_attachment_stats(self, *args, **kwargs):
        return await self.analytics.get_attachment_stats(*args, **kwargs)

    async def get_user_notification_preferences(self, user_id: int):
        return await self.settings.get_user_notification_preferences(user_id)

    async def update_user_notification_preferences(self, user_id: int, prefs: dict):
        return await self.settings.update_user_notification_preferences(user_id, prefs)

    async def get_users_for_notification(self, event_types: List[str], mode: str):
        return await self.users.get_users_for_notification(event_types, mode)

    # --- Support & FAQ Proxies ---
    async def get_faqs(self, *args, **kwargs):
        return await self.support.get_faqs(*args, **kwargs)
    
    async def add_faq(self, *args, **kwargs):
        return await self.support.add_faq(*args, **kwargs)
    
    async def update_faq(self, *args, **kwargs):
        return await self.support.update_faq(*args, **kwargs)
    
    async def delete_faq(self, *args, **kwargs):
        return await self.support.delete_faq(*args, **kwargs)
        
    async def get_ticket(self, *args, **kwargs):
        return await self.support.get_ticket(*args, **kwargs)
        
    async def get_all_tickets(self, *args, **kwargs):
        return await self.support.get_all_tickets(*args, **kwargs)
        
    async def add_ticket_reply(self, *args, **kwargs):
        return await self.support.add_ticket_reply(*args, **kwargs)
        
    async def update_ticket_status(self, *args, **kwargs):
        return await self.support.update_ticket_status(*args, **kwargs)
        
    async def update_ticket_priority(self, *args, **kwargs):
        return await self.support.update_ticket_priority(*args, **kwargs)
        
    async def assign_ticket(self, *args, **kwargs):
        return await self.support.assign_ticket(*args, **kwargs)
        
    async def get_ticket_stats(self, *args, **kwargs):
        return await self.support.get_ticket_stats(*args, **kwargs)
    
    async def get_ticket_replies(self, *args, **kwargs):
        return await self.support.get_ticket_replies(*args, **kwargs)
        
    async def search_tickets(self, *args, **kwargs):
        return await self.support.search_tickets(*args, **kwargs)

    def __getattr__(self, name):
        """
        Dynamically route missing method calls to the appropriate repository.
        Fallback for backward compatibility with handlers calling db.method().
        """
        # Prevent recursion if repositories themselves are missing or queried
        repo_names = ('users', 'attachments', 'settings', 'analytics', 'cms', 'support')
        if name in repo_names:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
        for repo_name in repo_names:
            repo = self.__dict__.get(repo_name)
            if repo and hasattr(repo, name):
                return getattr(repo, name)
                
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
_instance = None

def get_postgres_instance(database_url: str=None) -> DatabasePostgres:
    """دریافت instance singleton"""
    global _instance
    if _instance is None:
        _instance = DatabasePostgres(database_url)
    return _instance