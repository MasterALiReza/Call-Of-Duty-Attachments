#!/usr/bin/env python3
"""
OX_LOADOUT Bot Health Check Script
=============================
Quick health check utility for bot status verification.
Used by ox-loadout CLI tool for detailed status checks.

Usage:
    python health_check.py [--json] [--mode full|readiness]
"""

import argparse
import os
import sys
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment
from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def derive_overall_status(checks: list[dict]) -> str:
    """Determine overall status from check list."""
    overall_status = "ok"
    for check in checks:
        if check["status"] == "error":
            return "error"
        if check["status"] == "warning":
            overall_status = "warning"
    return overall_status


def check_database() -> dict:
    """Check PostgreSQL database connection."""
    result = {"name": "Database", "status": "unknown", "details": {}}

    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg import sql

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            result["status"] = "error"
            result["details"]["error"] = "DATABASE_URL not configured"
            return result

        start_time = datetime.now()
        conn = psycopg.connect(database_url, connect_timeout=5, row_factory=dict_row)
        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        cur = conn.cursor()

        # Get PostgreSQL version
        cur.execute("SELECT version()")
        version = cur.fetchone()["version"].split(",")[0]

        # Count tables
        cur.execute(
            "SELECT COUNT(*) as count FROM pg_tables WHERE schemaname = 'public'"
        )
        tables_count = cur.fetchone()["count"]

        # Check key tables exist
        key_tables = ["users", "admins", "weapons", "attachments"]
        cur.execute(
            """
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' AND tablename = ANY(%s)
        """,
            (key_tables,),
        )
        existing_tables = [row["tablename"] for row in cur.fetchall()]

        # Count data
        counts = {}
        for table in ["users", "admins", "attachments"]:
            try:
                query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(
                    sql.Identifier(table)
                )
                cur.execute(query)
                counts[table] = cur.fetchone()["count"]
            except:
                counts[table] = -1

        conn.close()

        result["status"] = "ok"
        result["details"] = {
            "version": version,
            "tables_count": tables_count,
            "key_tables_ok": len(existing_tables) == len(key_tables),
            "response_time_ms": round(elapsed, 2),
            "record_counts": counts,
        }

    except ImportError:
        result["status"] = "error"
        result["details"]["error"] = "psycopg not installed"
    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)

    return result


def check_telegram() -> dict:
    """Check Telegram Bot API connection."""
    result = {"name": "Telegram API", "status": "unknown", "details": {}}

    try:
        import requests

        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            result["status"] = "error"
            result["details"]["error"] = "BOT_TOKEN not configured"
            return result

        start_time = datetime.now()
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10
        )
        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                result["status"] = "ok"
                result["details"] = {
                    "bot_id": bot_info.get("id"),
                    "bot_username": bot_info.get("username"),
                    "bot_name": bot_info.get("first_name"),
                    "response_time_ms": round(elapsed, 2),
                }
            else:
                result["status"] = "error"
                result["details"]["error"] = data.get("description", "Unknown error")
        else:
            result["status"] = "error"
            result["details"]["error"] = f"HTTP {response.status_code}"

    except ImportError:
        result["status"] = "error"
        result["details"]["error"] = "requests not installed"
    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)

    return result


def check_environment(required_vars: list[str] | None = None) -> dict:
    """Check required environment variables."""
    result = {"name": "Environment", "status": "unknown", "details": {}}

    required_vars = required_vars or ["BOT_TOKEN", "DATABASE_URL", "SUPER_ADMIN_ID"]
    optional_vars = ["DEFAULT_LANG", "DB_POOL_SIZE"]

    missing = []
    configured = []

    for var in required_vars:
        if os.getenv(var):
            configured.append(var)
        else:
            missing.append(var)

    optional_status = {var: bool(os.getenv(var)) for var in optional_vars}

    result["status"] = "ok" if not missing else "error"
    result["details"] = {
        "required_configured": configured,
        "required_missing": missing,
        "optional_status": optional_status,
    }

    return result


def check_database_readiness() -> dict:
    """Fast database readiness check for container health probes."""
    result = {"name": "Database Readiness", "status": "unknown", "details": {}}

    try:
        import psycopg
        from psycopg.rows import dict_row

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            result["status"] = "error"
            result["details"]["error"] = "DATABASE_URL not configured"
            return result

        required_tables = ("users", "admins", "attachments")
        start_time = datetime.now()
        conn = psycopg.connect(database_url, connect_timeout=5, row_factory=dict_row)
        cur = conn.cursor()
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()

        cur.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY(%s)
            """,
            (list(required_tables),),
        )
        existing_tables = {row["tablename"] for row in cur.fetchall()}
        missing_tables = [
            table for table in required_tables if table not in existing_tables
        ]
        conn.close()

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        if missing_tables:
            result["status"] = "warning"
            result["details"] = {
                "missing_tables": missing_tables,
                "response_time_ms": round(elapsed, 2),
            }
            return result

        result["status"] = "ok"
        result["details"] = {
            "required_tables": list(required_tables),
            "response_time_ms": round(elapsed, 2),
        }
        return result
    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)
        return result


def check_files() -> dict:
    """Check required files exist."""
    result = {"name": "Files", "status": "unknown", "details": {}}

    required_files = [
        "main.py",
        "requirements.txt",
        ".env",
        "core/database/database_pg.py",
        "scripts/setup_database.py",
        "scripts/init_postgres.sql",
    ]
    required_dirs = [
        "scripts/migrations",
    ]

    missing = []
    found = []

    for file in required_files:
        path = os.path.join(PROJECT_ROOT, file)
        if os.path.exists(path):
            found.append(file)
        else:
            missing.append(file)

    for directory in required_dirs:
        path = os.path.join(PROJECT_ROOT, directory)
        if os.path.isdir(path):
            found.append(directory)
        else:
            missing.append(directory)

    result["status"] = "ok" if not missing else "warning"
    result["details"] = {"found": found, "missing": missing}

    return result


def check_super_admin() -> dict:
    """Check if super admin is configured in database."""
    result = {"name": "Super Admin", "status": "unknown", "details": {}}

    try:
        import psycopg
        from psycopg.rows import dict_row

        super_admin_id = os.getenv("SUPER_ADMIN_ID")
        if not super_admin_id:
            result["status"] = "error"
            result["details"]["error"] = "SUPER_ADMIN_ID not configured"
            return result

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            result["status"] = "error"
            result["details"]["error"] = "DATABASE_URL not configured"
            return result

        conn = psycopg.connect(database_url, connect_timeout=5, row_factory=dict_row)
        cur = conn.cursor()

        # Check if super admin exists in admins table
        cur.execute(
            """
            SELECT a.user_id, a.is_active, u.username
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.user_id = %s
        """,
            (int(super_admin_id),),
        )

        admin = cur.fetchone()
        conn.close()

        if admin:
            result["status"] = "ok"
            result["details"] = {
                "user_id": admin["user_id"],
                "username": admin.get("username"),
                "is_active": admin["is_active"],
                "in_database": True,
            }
        else:
            result["status"] = "warning"
            result["details"] = {
                "user_id": int(super_admin_id),
                "in_database": False,
                "note": "Super admin will be added on first bot startup",
            }

    except Exception as e:
        result["status"] = "error"
        result["details"]["error"] = str(e)

    return result


def run_all_checks() -> dict:
    """Run all health checks and return combined result."""
    checks = [
        check_environment(),
        check_files(),
        check_database(),
        check_telegram(),
        check_super_admin(),
    ]

    overall_status = derive_overall_status(checks)

    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall_status,
        "checks": checks,
    }


def run_readiness_checks() -> dict:
    """Run readiness-focused checks for container runtime probes."""
    checks = [
        check_environment(),
        check_database_readiness(),
    ]

    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": derive_overall_status(checks),
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="OX_LOADOUT bot health checks")
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    parser.add_argument(
        "--mode",
        choices=("full", "readiness"),
        default="full",
        help="Health check mode",
    )
    return parser.parse_args()


def print_human_readable(result: dict):
    """Print results in human-readable format."""
    status_icons = {"ok": "✅", "warning": "⚠️", "error": "❌", "unknown": "❓"}

    print("\n" + "=" * 60)
    print("         OX_LOADOUT Bot Health Check Report")
    print("=" * 60)
    print(f"\nTimestamp: {result['timestamp']}")
    print(
        f"Overall Status: {status_icons.get(result['overall_status'], '?')} {result['overall_status'].upper()}"
    )
    print("\n" + "-" * 60)

    for check in result["checks"]:
        icon = status_icons.get(check["status"], "?")
        print(f"\n{icon} {check['name']}: {check['status'].upper()}")

        details = check.get("details", {})
        if "error" in details:
            print(f"   Error: {details['error']}")
        else:
            for key, value in details.items():
                if isinstance(value, dict):
                    print(f"   {key}:")
                    for k, v in value.items():
                        print(f"      {k}: {v}")
                elif isinstance(value, list):
                    print(
                        f"   {key}: {', '.join(map(str, value)) if value else 'None'}"
                    )
                else:
                    print(f"   {key}: {value}")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    args = parse_args()
    output_json = args.json

    if args.mode == "readiness":
        result = run_readiness_checks()
    else:
        result = run_all_checks()

    if output_json:
        print(json.dumps(result, indent=2))
    else:
        if args.mode == "readiness":
            print(f"Readiness: {result['overall_status'].upper()}")
        else:
            print_human_readable(result)

    # Exit code based on status
    if result["overall_status"] == "error":
        sys.exit(1)
    elif result["overall_status"] == "warning":
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
