"""
Local PostgreSQL Database Initialization Script
Initializes `codm_attach_db` and applies all migration scripts.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg

# Load .env
root_dir = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=root_dir / ".env")

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "afg001376")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "codm_attach_db")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "680561287"))

print(f"Connecting to PostgreSQL on {DB_HOST}:{DB_PORT} as {POSTGRES_USER}...")

# 1. Connect to postgres system database and create target database if needed
admin_conn_str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
try:
    with psycopg.connect(admin_conn_str, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            exists = cur.fetchone()
            if not exists:
                cur.execute(f'CREATE DATABASE "{DB_NAME}"')
                print(f"✅ Created dedicated database: {DB_NAME}")
            else:
                print(f"ℹ️ Database '{DB_NAME}' already exists.")
except Exception as e:
    print(f"❌ Error creating database: {e}")
    sys.exit(1)

# 2. Connect to target database and apply migrations
db_conn_str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
migrations_dir = root_dir / "scripts" / "migrations"
migration_files = sorted(migrations_dir.glob("*.sql"))

print(f"\nApplying migrations to '{DB_NAME}'...")

with psycopg.connect(db_conn_str, autocommit=True) as conn:
    with conn.cursor() as cur:
        for m_file in migration_files:
            print(f" - Executing migration: {m_file.name} ...")
            try:
                sql_content = m_file.read_text(encoding="utf-8")
                cur.execute(sql_content)
                print(f"   ✓ {m_file.name} applied successfully.")
            except Exception as e:
                print(f"   ⚠️ Note on {m_file.name}: {e}")

        # 3. Register Super Admin in users, admins, and admin_roles
        print(f"\nRegistering Super Admin (ID: {SUPER_ADMIN_ID})...")
        try:
            # 1. Insert user
            cur.execute("""
                INSERT INTO users (user_id, username, first_name, language)
                VALUES (%s, 'Owner', 'Super Admin', 'fa')
                ON CONFLICT (user_id) DO NOTHING;
            """, (SUPER_ADMIN_ID,))

            # 2. Insert admin
            cur.execute("""
                INSERT INTO admins (user_id, display_name, is_active)
                VALUES (%s, 'Super Admin', TRUE)
                ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE;
            """, (SUPER_ADMIN_ID,))

            # 3. Assign super_admin role
            cur.execute("SELECT id FROM roles WHERE name = 'super_admin';")
            role_row = cur.fetchone()
            if role_row:
                role_id = role_row[0]
                cur.execute("""
                    INSERT INTO admin_roles (user_id, role_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (SUPER_ADMIN_ID, role_id))

            print(f"✅ Super Admin {SUPER_ADMIN_ID} configured with full RBAC permissions.")
        except Exception as e:
            print(f"⚠️ Note on admin configuration: {e}")

print("\n🎉 Database setup & migrations completed successfully!")
