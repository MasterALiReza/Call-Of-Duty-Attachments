import pytest
from pathlib import Path
from core.database.sql_helpers import sanitize_identifier
from core.database.database_pg import DatabasePostgres

# Setup root directory for finding migrations
ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "scripts" / "migrations"


@pytest.mark.asyncio
async def test_execute_query_commits_on_fetch_one():
    """F5-T1: BUG-01 regression test - execute_query with fetch_one=True commits the transaction."""

    # We will use a mock or an actual test database if available.
    # Since we might not have a running test DB, we'll try to instantiate DatabasePostgres
    # and mock the underlying cursor.
    class MockCursor:
        def __init__(self):
            self.execute_called = False
            self.fetchone_called = False
            self.rowcount = 1

        async def execute(self, query, params=None):
            self.execute_called = True

        async def fetchone(self):
            self.fetchone_called = True
            return {"id": 1, "name": "test"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockConnection:
        def __init__(self):
            self.commit_called = False
            self.rollback_called = False
            self.mock_cursor = MockCursor()

        def cursor(self):
            return self.mock_cursor

        async def commit(self):
            self.commit_called = True

        async def rollback(self):
            self.rollback_called = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockPool:
        def connection(self):
            return MockConnection()

    db = DatabasePostgres(database_url="postgresql://mock")
    db.pool = MockPool()

    # Actually, the connection object comes from get_connection(), let's override that:
    mock_conn = MockConnection()
    db.get_connection = lambda: mock_conn

    execute_query = getattr(db, "execute_query")
    result = await execute_query(
        "INSERT INTO test_table (name) VALUES ('test') RETURNING id", fetch_one=True
    )

    assert mock_conn.mock_cursor.execute_called is True
    assert mock_conn.mock_cursor.fetchone_called is True
    assert mock_conn.commit_called is True, (
        "commit() was not called when fetch_one=True"
    )
    assert result == {"id": 1, "name": "test"}


def test_safe_identifier_rejects_injection():
    """F5-T2: BUG-03 regression test - sql_helpers.sanitize_identifier rejects bad inputs."""
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        sanitize_identifier("users; DROP TABLE users--")

    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        sanitize_identifier("1_bad_start")

    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        sanitize_identifier(
            "some_table_name_that_is_way_too_long_for_postgres_identifier_limits_because_it_is_more_than_63_chars"
        )

    assert sanitize_identifier("valid_table") == "valid_table"
    assert sanitize_identifier("v1") == "v1"


def test_migration_files_are_valid_sql():
    """F5-T4: BUG-22 regression test - ensure all migration files have matched $$ delimiters."""
    for migration in MIGRATIONS_DIR.glob("*.sql"):
        content = migration.read_text(encoding="utf-8")
        dollar_count = content.count("$$")
        assert dollar_count % 2 == 0, f"{migration.name}: unmatched $$ delimiters"
