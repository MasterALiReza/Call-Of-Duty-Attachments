"""
PostgreSQL Database Wrapper
Ø§ÛŒÙ† wrapper ØªÙ…Ø§Ù… Ø¹Ù…Ù„ÛŒØ§Øª DatabaseSQL Ø±Ø§ Ø¨Ø§ PostgreSQL Ù¾ÛŒØ§Ø¯Ù‡\u200cØ³Ø§Ø²ÛŒ Ù…ÛŒ\u200cÚ©Ù†Ø¯
"""

import os
import asyncio
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from typing import Any
from contextlib import asynccontextmanager
from utils.logger import get_logger, log_exception
from utils.metrics import measure_query_time
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = get_logger("database.postgres", "database.log")


class DatabasePostgres:
    """
    PostgreSQL Database Handler
    Compatible Ø¨Ø§ DatabaseSQL interface - ØªÙ…Ø§Ù… Ù…ØªØ¯Ù‡Ø§ Ø±Ø§ Ø¯Ø§Ø±Ø¯
    """

    def __init__(self, database_url: str = None):
        """
        Initialize PostgreSQL connection settings

        Args:
            database_url: PostgreSQL connection string
        """
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                raise ValueError("DATABASE_URL is required for PostgreSQL")
        self.database_url = database_url
        self.db_path = (
            database_url.split("@")[-1] if "@" in database_url else "[hidden]"
        )
        self.environment = os.getenv(
            "ENVIRONMENT", os.getenv("ENV", "production")
        ).lower()
        pool_size = int(os.getenv("DB_POOL_SIZE", 20))
        max_overflow = int(os.getenv("DB_POOL_MAX_OVERFLOW", 10))
        pool_timeout = float(os.getenv("DB_POOL_TIMEOUT", 30.0))
        self.runtime_schema_ensure = str(
            os.getenv("DB_RUNTIME_SCHEMA_ENSURE", "true")
        ).lower() in (
            "1",
            "true",
            "yes",
        )

        self._pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=2,
            max_size=pool_size + max_overflow,
            kwargs={"row_factory": dict_row},
            open=False,
            timeout=pool_timeout,
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

        logger.info(
            f"PostgreSQL connection pool initialized (ready for open): {pool_size} connections"
        )

    async def initialize(self):
        """Ø±Ø§Ù‡â€ŒØ§Ù†Ø¯Ø§Ø²ÛŒ Ù†Ø§Ù…ØªÙ‚Ø§Ø±Ù† (Async) Ø§ØªØµØ§Ù„â€ŒÙ‡Ø§ Ø¨Ø§ retry logic"""
        await self._connect_with_retry()

        await self._init_fuzzy_engine()
        if self.runtime_schema_ensure:
            await asyncio.to_thread(self._ensure_runtime_guards)
        else:
            logger.info(
                "Skipping runtime schema guards (DB_RUNTIME_SCHEMA_ENSURE=false). "
                "Expecting schema to be provided by migrations."
            )
        logger.info("DatabasePostgres opened and initialized successfully")

    @retry(
        stop=stop_after_attempt(int(os.getenv("DB_RETRY_ATTEMPTS", "3"))),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (psycopg.OperationalError, psycopg.InterfaceError, ConnectionError, OSError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Database connection attempt {retry_state.attempt_number} failed, retrying in {retry_state.next_action.sleep} seconds..."
        ),
        reraise=True,
    )
    async def _connect_with_retry(self):
        """Establish database connection with exponential backoff retry"""
        try:
            await self._pool.open()
            async with self.get_connection() as conn:
                cursor = conn.cursor()
                await cursor.execute("SELECT version() as version")
                result = await cursor.fetchone()
                version = result["version"] if result else "unknown"
                logger.info(f"Connected to: {version.split(',')[0]}")
        except Exception as e:
            logger.error(f"Failed to open PostgreSQL pool: {e}")
            log_exception(logger, e, "DatabasePostgres._connect_with_retry")
            raise

    @asynccontextmanager
    async def get_connection(self):
        """Context manager Ø¨Ø±Ø§ÛŒ Ø¯Ø±ÛŒØ§ÙØª connection Ø§Ø² pool"""
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
        Context manager Ø¨Ø±Ø§ÛŒ transaction
        Compatible Ø¨Ø§ DatabaseSQL.transaction()
        """
        async with self.get_connection() as conn:
            try:
                yield conn
                await conn.commit()
            except psycopg.Error as e:
                await conn.rollback()
                logger.error(f"PostgreSQL transaction error: {e}")
                log_exception(logger, e, "transaction")
                raise
            except Exception as e:
                await conn.rollback()
                logger.error(f"Transaction error: {e}")
                log_exception(logger, e, "transaction")
                raise

    async def execute_query(
        self,
        query: str,
        params: tuple = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        as_dict: bool = True,
    ) -> Any:
        """
        Ø§Ø¬Ø±Ø§ÛŒ query Ø¨Ø§ ØªØ¨Ø¯ÛŒÙ„ Ø®ÙˆØ¯Ú©Ø§Ø± placeholders Ùˆ tracking performance
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                try:
                    with measure_query_time(query[:200], params):
                        await cursor.execute(query, params or ())
                    if fetch_one:
                        result = await cursor.fetchone()
                        await conn.commit()
                        return dict(result) if result and as_dict else result
                    elif fetch_all:
                        results = await cursor.fetchall()
                        await conn.commit()
                        return [dict(r) for r in results] if as_dict else results
                    else:
                        await conn.commit()
                        return cursor.rowcount
                except psycopg.Error as e:
                    await conn.rollback()
                    logger.error(f"PostgreSQL query error: {e}")
                    logger.error(f"Query: {query[:200]}")
                    if self.environment != "production":
                        logger.error(f"Params: {params}")
                    raise
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Query execution error: {e}")
                    logger.error(f"Query: {query[:200]}")
                    if self.environment != "production":
                        logger.error(f"Params: {params}")
                    raise

    async def _init_fuzzy_engine(self):
        """Ø±Ø§Ù‡\u200cØ§Ù†Ø¯Ø§Ø²ÛŒ fuzzy search (compatible Ø¨Ø§ DatabaseSQL)"""
        try:
            from utils.search_fuzzy import FuzzySearchEngine

            self.fuzzy_engine = FuzzySearchEngine(self)
            logger.info("Fuzzy search engine initialized")
        except ImportError:
            logger.warning("FuzzySearchEngine not available")
        except Exception as e:
            logger.error(f"Failed to initialize fuzzy search: {e}")

    def _ensure_runtime_guards(self):
        """
        Schema ownership belongs to SQL migrations.
        Runtime guards remain temporary, additive compatibility checks only.
        """
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
                cursor = conn.cursor()

                def _column_exists(table: str, column: str) -> bool:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = %s
                          AND column_name = %s
                        """,
                        (table, column),
                    )
                    return cursor.fetchone() is not None

                def _table_exists(table: str) -> bool:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = current_schema()
                              AND table_name = %s
                        ) AS exists
                        """,
                        (table,),
                    )
                    row = cursor.fetchone()
                    return bool(row.get("exists")) if row else False

                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                    conn.commit()
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"runtime_guards(extensions) warning: {e}")

                required_seed_tables = (
                    "weapon_categories",
                    "settings",
                    "ua_stats_cache",
                )
                missing_seed_tables = [
                    table for table in required_seed_tables if not _table_exists(table)
                ]

                if missing_seed_tables:
                    logger.warning(
                        "Skipping runtime seed guards because canonical migrations are missing required tables: "
                        + ", ".join(missing_seed_tables)
                    )
                else:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO weapon_categories (name, display_name, sort_order) VALUES
                                ('assault_rifle', 'Assault Rifle', 1),
                                ('smg', 'SMG', 2),
                                ('lmg', 'LMG', 3),
                                ('sniper', 'Sniper', 4),
                                ('marksman', 'Marksman', 5),
                                ('shotgun', 'Shotgun', 6),
                                ('pistol', 'Pistol', 7),
                                ('launcher', 'Launcher', 8)
                            ON CONFLICT (name) DO UPDATE SET
                                display_name = EXCLUDED.display_name,
                                sort_order = EXCLUDED.sort_order
                            """
                        )
                        cursor.execute(
                            """
                            INSERT INTO settings (key, value, description, category, data_type, updated_at)
                            VALUES ('system_enabled', 'true', 'Enable/Disable User Attachments System', 'user_attachments', 'boolean', NOW())
                            ON CONFLICT (key) DO NOTHING
                            """
                        )
                        cursor.execute(
                            "INSERT INTO ua_stats_cache (id) VALUES (1) ON CONFLICT DO NOTHING"
                        )
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"runtime_guards(seed data) error: {e}")

                try:
                    if _table_exists("ua_stats_cache") and not _column_exists(
                        "ua_stats_cache", "deleted_count"
                    ):
                        cursor.execute(
                            "ALTER TABLE ua_stats_cache ADD COLUMN deleted_count INTEGER DEFAULT 0"
                        )
                        logger.info("Added deleted_count column to ua_stats_cache")

                    if _table_exists("analytics_users") and not _column_exists(
                        "analytics_users", "registration_source"
                    ):
                        cursor.execute(
                            "ALTER TABLE analytics_users ADD COLUMN registration_source TEXT"
                        )
                        logger.info(
                            "Added registration_source column to analytics_users"
                        )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.error(f"runtime_guards(compatibility) error: {e}")
                logger.info(
                    "Database runtime guards completed successfully; schema ownership remains migration-only"
                )
        except Exception as e:
            logger.error(f"Database runtime guard check failed: {e}")

    # get_users_for_notification has been moved to UserRepository

    async def close(self):
        """Ø¨Ø³ØªÙ† connection pool"""
        if hasattr(self, "_pool"):
            try:
                try:
                    wait_timeout = float(os.getenv("DB_POOL_WAIT_TIMEOUT", "2"))
                except Exception:
                    wait_timeout = 2.0
                try:
                    close_timeout = float(os.getenv("DB_POOL_CLOSE_TIMEOUT", "10"))
                except Exception:
                    close_timeout = 10.0
                suppress_warn = str(
                    os.getenv("DB_SUPPRESS_POOL_WARNINGS", "false")
                ).lower() in ("1", "true", "yes")
                pool_logger = logging.getLogger("psycopg.pool")
                previous_level = pool_logger.level if suppress_warn else None
                if suppress_warn:
                    try:
                        pool_logger.setLevel(logging.ERROR)
                    except Exception:
                        pass

                # Async variants of pool methods
                if hasattr(self, "_pool") and self._pool:
                    try:
                        # Check if pool is actually open before waiting/closing
                        # This prevents "PoolClosed" error if bot crashed before DB init
                        await self._pool.wait(timeout=wait_timeout)
                        await self._pool.close(timeout=close_timeout)
                        logger.info("PostgreSQL connection pool closed gracefully")
                    except Exception as pool_err:
                        if "not open yet" in str(pool_err):
                            logger.info(
                                "PostgreSQL pool was not initialized, skipping close."
                            )
                        else:
                            raise
                else:
                    logger.info("PostgreSQL pool was not created, skipping close.")
            except Exception as e:
                try:
                    await self._pool.close(timeout=0)
                except Exception as close_exc:
                    logger.exception(
                        f"Error forcing PostgreSQL pool close: {close_exc}"
                    )
                logger.exception(f"Connection pool forced close: {e}")
            finally:
                if (
                    "suppress_warn" in locals()
                    and suppress_warn
                    and (previous_level is not None)
                ):
                    try:
                        pool_logger.setLevel(previous_level)
                    except Exception:
                        pass


_instance = None


def get_postgres_instance(database_url: str = None) -> DatabasePostgres:
    """Ø¯Ø±ÛŒØ§ÙØª instance singleton"""
    global _instance
    if _instance is None:
        _instance = DatabasePostgres(database_url)
    return _instance
