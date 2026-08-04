#!/usr/bin/env python3
"""Verify canonical migration bootstrap on a freshly provisioned PostgreSQL database."""

import argparse
import os
import sys
import psycopg


DB_NAME = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "ox_loadout_bot"))
DB_USER = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "ox_loadout_admin"))
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost"))
DB_PORT = int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432")))

EXPECTED_MIGRATIONS = [
    "0001_baseline.sql",
    "0002_guides_split_tables.sql",
    "0003_runtime_parity_tables.sql",
    "0004_schema_canonical_backfill.sql",
]

EXPECTED_TABLES = [
    "user_attachments",
    "user_submission_stats",
    "user_faq_votes",
    "guide_media",
    "guide_photos",
    "guide_videos",
    "ua_stats_cache",
    "analytics_users",
]

EXPECTED_COLUMNS = {
    "user_attachments": {"deleted_at", "deleted_by", "view_count"},
    "user_submission_stats": {"deleted_count"},
    "ua_stats_cache": {"deleted_count"},
    "analytics_users": {"registration_source"},
}


def fail(message: str) -> int:
    print(f"[verify_canonical_bootstrap] {message}", file=sys.stderr)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-migration",
        action="append",
        default=[],
        help="Require a specific migration to be present in _migrations.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not DB_PASSWORD:
        return fail("DB_PASSWORD is required for verification")

    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={DB_USER} "
            + f"password={DB_PASSWORD} dbname={DB_NAME}"
        )
    except Exception as exc:
        return fail(f"Unable to connect to target database: {exc}")

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM _migrations ORDER BY name")
            applied_migrations = [row[0] for row in cur.fetchall()]
            if applied_migrations != EXPECTED_MIGRATIONS:
                return fail(
                    "Unexpected migration chain: "
                    + f"expected={EXPECTED_MIGRATIONS}, actual={applied_migrations}"
                )
            for required_migration in args.require_migration:
                if required_migration not in applied_migrations:
                    return fail(
                        f"Required migration missing from _migrations: {required_migration}"
                    )

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            existing_tables = {row[0] for row in cur.fetchall()}
            missing_tables = sorted(set(EXPECTED_TABLES) - existing_tables)
            if missing_tables:
                return fail(f"Missing expected tables: {missing_tables}")

            for table_name, columns in EXPECTED_COLUMNS.items():
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                existing_columns = {row[0] for row in cur.fetchall()}
                missing_columns = sorted(columns - existing_columns)
                if missing_columns:
                    return fail(
                        f"Missing expected columns in {table_name}: {missing_columns}"
                    )

            cur.execute(
                """
                SELECT tablename, tableowner
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename = ANY(%s)
                """,
                (EXPECTED_TABLES,),
            )
            table_owners = {row[0]: row[1] for row in cur.fetchall()}
            wrong_owners = sorted(
                table_name
                for table_name in EXPECTED_TABLES
                if table_owners.get(table_name) != DB_USER
            )
            if wrong_owners:
                return fail(
                    f"Expected bootstrap-owned tables to belong to {DB_USER}, mismatched={wrong_owners}"
                )
    finally:
        conn.close()

    print("[verify_canonical_bootstrap] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
