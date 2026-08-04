#!/usr/bin/env python3
"""
OX_LOADOUT Attachments Bot - Database Setup Script
==============================================
This script creates a clean PostgreSQL database for the OX_LOADOUT bot.

Usage:
    python setup_database.py [--drop-existing] [--migrate-only]

Options:
    --drop-existing    Drop and recreate the database if it exists
    --migrate-only     Apply canonical migrations to an existing database only
"""

import sys
import os
import psycopg
from psycopg import sql
from pathlib import Path

# Configuration
DB_NAME = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "ox_loadout_bot"))
DB_USER = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "ox_loadout_admin"))
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost"))
DB_PORT = int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432")))

# PostgreSQL superuser credentials (for creating database)
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


# Colors for output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def mask_secret(secret: str, visible: int = 2) -> str:
    """Mask secret values for safe console output."""
    if not secret:
        return "(not set)"
    if len(secret) <= visible:
        return "*" * len(secret)
    return ("*" * (len(secret) - visible)) + secret[-visible:]


def print_success(msg):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.ENDC}")


def print_info(msg):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.ENDC}")


def print_warning(msg):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.ENDC}")


def print_error(msg):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.ENDC}")


def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{msg}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}\n")


def check_postgres_connection():
    """Check if we can connect to PostgreSQL"""
    print_info("Checking PostgreSQL connection...")
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={POSTGRES_USER} "
            + f"password={POSTGRES_PASSWORD} dbname=postgres",
            autocommit=True,
        )
        conn.close()
        print_success("PostgreSQL connection OK")
        return True
    except Exception as e:
        print_error(f"Cannot connect to PostgreSQL: {e}")
        return False


def ensure_database_user():
    """Ensure the application database role exists and can own the database."""
    if DB_USER == POSTGRES_USER:
        print_info(
            f"Database role '{DB_USER}' already uses the PostgreSQL superuser account"
        )
        return True

    print_info(f"Ensuring database role '{DB_USER}' exists...")
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={POSTGRES_USER} "
            + f"password={POSTGRES_PASSWORD} dbname=postgres",
            autocommit=True,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (DB_USER,))
        role_exists = cur.fetchone() is not None

        if role_exists:
            cur.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                    sql.Identifier(DB_USER)
                ),
                (DB_PASSWORD,),
            )
            print_success(f"Database role '{DB_USER}' updated")
        else:
            cur.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(DB_USER)
                ),
                (DB_PASSWORD,),
            )
            print_success(f"Database role '{DB_USER}' created")

        cur.execute(
            sql.SQL("ALTER USER {} WITH CREATEDB").format(sql.Identifier(DB_USER))
        )
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print_error(f"Error ensuring database role: {e}")
        return False


def drop_database_if_exists():
    """Drop the database if it exists"""
    print_info(f"Dropping database '{DB_NAME}' if exists...")
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={POSTGRES_USER} "
            + f"password={POSTGRES_PASSWORD} dbname=postgres",
            autocommit=True,
        )
        cur = conn.cursor()

        # Terminate existing connections
        cur.execute(
            sql.SQL("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid != pg_backend_pid()
        """),
            [DB_NAME],
        )

        # Drop database
        cur.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DB_NAME))
        )

        cur.close()
        conn.close()
        print_success(f"Database '{DB_NAME}' dropped")
        return True
    except Exception as e:
        print_error(f"Error dropping database: {e}")
        return False


def create_database():
    """Create the database"""
    print_info(f"Creating database '{DB_NAME}'...")
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={POSTGRES_USER} "
            + f"password={POSTGRES_PASSWORD} dbname=postgres",
            autocommit=True,
        )
        cur = conn.cursor()

        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                sql.Identifier(DB_NAME), sql.Identifier(DB_USER)
            )
        )

        cur.close()
        conn.close()
        print_success(f"Database '{DB_NAME}' created")
        return True
    except Exception as e:
        print_error(f"Error creating database: {e}")
        return False


def run_setup_script():
    """Run schema setup with migration-first strategy."""
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print_error(
            "Migration files are required; scripts/setup_database.sql is deprecated and is not the schema source."
        )
        return False

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print_error(
            "Migration files are required; scripts/setup_database.sql is deprecated and is not the schema source."
        )
        return False

    print_info(f"Running {len(migration_files)} migration(s)...")
    conn = None
    cur = None
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={DB_USER} "
            + f"password={DB_PASSWORD} dbname={DB_NAME}"
        )
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        conn.commit()

        for migration_path in migration_files:
            migration_name = migration_path.name
            cur.execute("SELECT 1 FROM _migrations WHERE name = %s", (migration_name,))
            if cur.fetchone():
                print_info(f"Skipping already applied migration: {migration_name}")
                continue

            print_info(f"Applying migration: {migration_name}")
            with open(migration_path, "r", encoding="utf-8") as f:
                sql_script = f.read()

            cur.execute(sql_script)
            cur.execute(
                "INSERT INTO _migrations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (migration_name,),
            )
            conn.commit()
            print_success(f"Applied migration: {migration_name}")

        print_success("Migrations executed successfully")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print_error(f"Error running migrations: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def verify_setup():
    """Verify the database setup"""
    print_info("Verifying database setup...")
    try:
        conn = psycopg.connect(
            f"host={DB_HOST} port={DB_PORT} user={DB_USER} "
            + f"password={DB_PASSWORD} dbname={DB_NAME}"
        )
        cur = conn.cursor()

        # Count tables
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cur.fetchone()[0]
        print_success(f"Tables created: {table_count}")

        # Check extensions
        cur.execute(
            "SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent')"
        )
        extensions = [row[0] for row in cur.fetchall()]
        print_success(f"Extensions: {', '.join(extensions)}")

        # Check categories
        cur.execute("SELECT COUNT(*) FROM weapon_categories")
        category_count = cur.fetchone()[0]
        print_success(f"Weapon categories: {category_count}")

        # Check roles
        cur.execute("SELECT COUNT(*) FROM roles")
        role_count = cur.fetchone()[0]
        print_success(f"Roles: {role_count}")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        print_error(f"Verification failed: {e}")
        return False


def update_env_file():
    """Update the .env file with new credentials"""
    print_info("Updating .env file...")
    try:
        env_path = Path(__file__).parent.parent / ".env"

        if not env_path.exists():
            print_warning(".env file not found, skipping update")
            return True

        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Update database configuration
        new_lines = []
        for line in lines:
            if line.startswith("DATABASE_URL="):
                new_lines.append(
                    f"DATABASE_URL=postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}\n"
                )
            elif line.startswith("DB_NAME="):
                new_lines.append(f"DB_NAME={DB_NAME}\n")
            elif line.startswith("DB_USER="):
                new_lines.append(f"DB_USER={DB_USER}\n")
            elif line.startswith("DB_PASSWORD="):
                new_lines.append(f"DB_PASSWORD={DB_PASSWORD}\n")
            else:
                new_lines.append(line)

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print_success(".env file updated")
        return True
    except Exception as e:
        print_warning(f"Could not update .env file: {e}")
        return True  # Non-critical


def main():
    """Main setup process"""
    print_header("OX_LOADOUT Attachments Bot - Database Setup")

    # Check arguments
    drop_existing = "--drop-existing" in sys.argv
    migrate_only = "--migrate-only" in sys.argv

    if not DB_PASSWORD:
        print_error(
            "DB_PASSWORD is not set. Export DB_PASSWORD (or add it to .env) and retry."
        )
        return 1

    if migrate_only and drop_existing:
        print_error("--migrate-only and --drop-existing cannot be used together")
        return 1

    if migrate_only:
        print_header("Applying Canonical Migrations")
        if not run_setup_script():
            print_error("Migration-only setup aborted")
            return 1

        print_header("Verifying Setup")
        if not verify_setup():
            print_error("Setup verification failed")
            return 1

        print_success("Migration-only setup completed")
        return 0

    # Step 1: Check PostgreSQL connection
    if not check_postgres_connection():
        print_error("Setup aborted")
        return 1

    # Step 2: Drop existing database if requested
    if drop_existing:
        print_header("Dropping Existing Database")
        if not drop_database_if_exists():
            print_error("Setup aborted")
            return 1

    # Step 3: Ensure application role exists before creating the database
    print_header("Ensuring Database User")
    if not ensure_database_user():
        print_error("Setup aborted")
        return 1

    # Step 4: Create database
    print_header("Creating Database")
    if not create_database():
        print_warning("Database might already exist, continuing...")

    # Step 5: Run canonical migrations
    print_header("Applying Canonical Migrations")
    if not run_setup_script():
        print_error("Setup aborted")
        return 1

    # Step 6: Verify setup
    print_header("Verifying Setup")
    if not verify_setup():
        print_error("Setup verification failed")
        return 1

    # Step 7: Update .env file
    print_header("Updating Configuration")
    update_env_file()

    # Success!
    print_header("Setup Complete!")
    print_success(f"Database '{DB_NAME}' is ready to use")
    print_info("\nConnection Details:")
    print(f"  Host: {DB_HOST}")
    print(f"  Port: {DB_PORT}")
    print(f"  Database: {DB_NAME}")
    print(f"  User: {DB_USER}")
    print(f"  Password: {mask_secret(DB_PASSWORD)}")
    print(f"\n{Colors.BLUE}You can now run: python main.py{Colors.ENDC}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
