#!/usr/bin/env python3
"""
Secure administrative operations script for ox-loadout interface.
Replaces inline Python heredoc strings to prevent shell injection and SQL injection.
"""

import argparse
import os
import sys
import time

import psycopg
from psycopg import sql


def get_db_connection(timeout: int = 10) -> psycopg.Connection:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "❌ Error: DATABASE_URL environment variable is not set.", file=sys.stderr
        )
        sys.exit(1)
    try:
        return psycopg.connect(db_url, connect_timeout=timeout)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)


def check_status() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit(1)
    try:
        conn = psycopg.connect(db_url, connect_timeout=5)
        conn.close()
        sys.exit(0)
    except Exception:
        sys.exit(1)


def test_connection() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL environment variable not found.")
        sys.exit(1)
    try:
        start_time = time.time()
        conn = psycopg.connect(db_url, connect_timeout=5)
        elapsed = (time.time() - start_time) * 1000
        cur = conn.cursor()
        cur.execute("SELECT version()")
        row = cur.fetchone()
        version = row[0] if row else "Unknown"
        cur.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = %s", ("public",))
        tables_row = cur.fetchone()
        tables = tables_row[0] if tables_row else 0
        conn.close()
        print(f"✅ Connection successful! ({elapsed:.1f}ms)")
        print(f"   PostgreSQL: {version.split(',')[0]}")
        print(f"   Tables: {tables}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")


def show_stats() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    stats = {}
    tables = [
        "users",
        "admins",
        "weapons",
        "attachments",
        "user_attachments",
        "tickets",
    ]
    for table in tables:
        try:
            query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
            cur.execute(query)
            row = cur.fetchone()
            stats[table] = row[0] if row else 0
        except Exception:
            conn.rollback()
            stats[table] = "N/A"

    try:
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        size_row = cur.fetchone()
        db_size = size_row[0] if size_row else "Unknown"
    except Exception:
        conn.rollback()
        db_size = "Unknown"

    conn.close()

    print(f"Database Size: {db_size}")
    print("")
    print(f"{'Table':<20} {'Records':<10}")
    print("-" * 30)
    for table, count in stats.items():
        print(f"{table:<20} {count:<10}")


def list_admins() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.user_id, u.username, u.first_name, a.is_active, a.created_at
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.created_at
        """)
        rows = cur.fetchall()
        if rows:
            print(f"{'User ID':<15} {'Username':<20} {'Name':<20} {'Active':<8}")
            print("-" * 65)
            for row in rows:
                uid, username, name, active, _ = row
                username_str = str(username) if username is not None else "N/A"
                name_str = str(name) if name is not None else "N/A"
                status = "✅" if active else "❌"
                print(f"{uid:<15} {username_str:<20} {name_str:<20} {status}")
        else:
            print("No admins found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()


def add_admin(user_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,)
        )
        cur.execute(
            """
            INSERT INTO admins (user_id, is_active) 
            VALUES (%s, TRUE) 
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE
        """,
            (user_id,),
        )
        cur.execute("SELECT id FROM roles WHERE name = %s", ("admin",))
        role = cur.fetchone()
        if role:
            cur.execute(
                """
                INSERT INTO admin_roles (user_id, role_id) 
                VALUES (%s, %s) 
                ON CONFLICT DO NOTHING
            """,
                (user_id, role[0]),
            )
        conn.commit()
        print("✅ Admin added successfully!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def remove_admin(user_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE admins SET is_active = FALSE WHERE user_id = %s", (user_id,)
        )
        cur.execute("DELETE FROM admin_roles WHERE user_id = %s", (user_id,))
        conn.commit()
        print("✅ Admin removed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def change_super_admin(user_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,)
        )
        cur.execute(
            """
            INSERT INTO admins (user_id, is_active) 
            VALUES (%s, TRUE) 
            ON CONFLICT (user_id) DO UPDATE SET is_active = TRUE
        """,
            (user_id,),
        )
        cur.execute("SELECT id FROM roles WHERE name = %s", ("super_admin",))
        role = cur.fetchone()
        if role:
            cur.execute(
                """
                INSERT INTO admin_roles (user_id, role_id) 
                VALUES (%s, %s) 
                ON CONFLICT DO NOTHING
            """,
                (user_id, role[0]),
            )
        conn.commit()
        print("✅ Super Admin ID updated!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Administrative DB operations for ox-loadout"
    )
    parser.add_argument(
        "command",
        choices=[
            "check-status",
            "test-connection",
            "show-stats",
            "list-admins",
            "add-admin",
            "remove-admin",
            "change-super-admin",
        ],
        help="Command to run",
    )
    parser.add_argument(
        "--user-id", type=int, help="Telegram User ID for admin operations"
    )

    args = parser.parse_args()

    if args.command in ["add-admin", "remove-admin", "change-super-admin"]:
        if args.user_id is None:
            print(
                f"❌ Error: --user-id is required for {args.command}", file=sys.stderr
            )
            sys.exit(1)

    if args.command == "check-status":
        check_status()
    elif args.command == "test-connection":
        test_connection()
    elif args.command == "show-stats":
        show_stats()
    elif args.command == "list-admins":
        list_admins()
    elif args.command == "add-admin":
        if args.user_id is not None:
            add_admin(args.user_id)
    elif args.command == "remove-admin":
        if args.user_id is not None:
            remove_admin(args.user_id)
    elif args.command == "change-super-admin":
        if args.user_id is not None:
            change_super_admin(args.user_id)


if __name__ == "__main__":
    main()
