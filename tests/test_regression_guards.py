import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DB_DIRECT_CALL_PATTERN = re.compile(
    r"\b(?:self\.)?db\.(?!users\b|attachments\b|settings\b|analytics\b|cms\b|support\b|transaction\b|get_connection\b)[A-Za-z_][A-Za-z0-9_]*\("
)


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _iter_td06_guard_files() -> list[Path]:
    files: list[Path] = []
    for rel_root in ("handlers", "app", "tests", "config", "managers", "utils"):
        files.extend((ROOT / rel_root).rglob("*.py"))

    files.extend((ROOT / "core").rglob("*.py"))
    files.append(ROOT / "main.py")

    excluded_parts = {
        ("core", "database", "repositories"),
        ("core", "database", "mixins"),
    }

    filtered: list[Path] = []
    for path in files:
        parts = path.relative_to(ROOT).parts
        if any(parts[: len(prefix)] == prefix for prefix in excluded_parts):
            continue
        filtered.append(path)

    return sorted(set(filtered))


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _attribute_chain(node: ast.AST) -> str | None:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _is_awaited(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.Await):
            return True
        if isinstance(
            parent,
            (
                ast.Expr,
                ast.Assign,
                ast.Return,
                ast.BoolOp,
                ast.UnaryOp,
                ast.If,
                ast.Call,
                ast.keyword,
            ),
        ):
            current = parent
            continue
        current = parent
    return False


def test_admin_registry_import_export_state_keys_not_duplicated() -> None:
    text = _read("app/registry/admin_registry_states.py")
    assert text.count("IMPORT_FILE: [") == 1
    assert text.count("IMPORT_MODE: [") == 1
    assert text.count("EXPORT_START: [") == 1


def test_admin_registry_state_dict_has_no_duplicate_keys() -> None:
    source = _read("app/registry/admin_registry_states.py")
    tree = ast.parse(source)
    duplicates: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "states_dict"
            for target in node.targets
        ):
            continue

        seen: set[str] = set()
        for key in node.value.keys:
            if key is None:
                continue
            key_repr = ast.unparse(key)
            if key_repr in seen:
                duplicates.append(key_repr)
            else:
                seen.add(key_repr)

    assert not duplicates, f"Duplicate state keys found: {duplicates}"


def test_no_known_async_anti_patterns_in_critical_handlers() -> None:
    checks = {
        "handlers/channel/channel_handlers.py": [
            r"if\s+not\s+check_channel_management_permission\(",
        ],
        "handlers/channel/management_actions.py": [
            r"(?<!await )db\.get_required_channels\(",
            r"(?<!await )db\.remove_required_channel\(",
        ],
        "handlers/channel/add_handlers.py": [
            r"(?<!await )db\.add_required_channel\(",
        ],
        "handlers/channel/edit_handlers.py": [
            r"(?<!await )db\.update_required_channel\(",
        ],
        "handlers/channel/delete_handlers.py": [
            r"(?<!await )db\.get_required_channels\(",
            r"(?<!await )db\.remove_required_channel\(",
        ],
        "handlers/channel/details_handlers.py": [
            r"(?<!await )db\.toggle_channel_status\(",
        ],
        "handlers/channel/reorder_handlers.py": [
            r"(?<!await )db\.move_channel_up\(",
            r"(?<!await )db\.move_channel_down\(",
        ],
        "handlers/admin/user_attachments_admin/reports_handler.py": [
            r"async\s+with\s+await\s+db\.get_connection\(",
            r"async\s+with\s+await\s+db\.transaction\(",
            r"if\s+not\s+has_ua_perm\(",
        ],
        "handlers/admin/user_attachments_admin/review_handler.py": [
            r"if\s+not\s+check_ua_admin_permission\(",
            r"(?<!async )with\s+db\.transaction\(",
            r"attachment\s*=\s*db\.get_user_attachment\(",
        ],
        "handlers/admin/user_attachments_admin/settings_handler.py": [
            r"success\s*=\s*db\.remove_blacklisted_word\(",
        ],
        "handlers/admin/admin_handlers_modular.py": [
            r"if\s+self\.is_admin\(",
        ],
        "handlers/admin/modules/base_handler.py": [
            r"return\s+self\.is_admin\(",
        ],
        "handlers/admin/modules/system/data_management_handler.py": [
            r"(?<!await )self\.role_manager\.has_permission\(",
            r"(?<!await )self\.role_manager\.is_super_admin\(",
        ],
        "handlers/admin/modules/system/import_export.py": [
            r"(?<!await )self\.role_manager\.has_permission\(",
            r"(?<!await )self\.role_manager\.is_super_admin\(",
            r"(?<!await )self\.role_manager\.get_user_permissions\(",
        ],
        "handlers/admin/modules/system/admin_management.py": [
            r"if\s+self\.is_admin\(",
        ],
        "handlers/admin/modules/system/notification_handler.py": [
            r"if\s+self\.is_admin\(",
        ],
        "handlers/admin/modules/support/ticket_handler.py": [
            r"if\s+self\.is_admin\(",
        ],
        "handlers/admin/modules/support/faq_handler.py": [
            r"if\s+self\.is_admin\(",
        ],
    }

    for rel_path, patterns in checks.items():
        text = _read(rel_path)
        for pattern in patterns:
            assert re.search(pattern, text) is None, f"{rel_path} matched: {pattern}"


def test_no_missing_await_in_admin_permission_paths_via_ast() -> None:
    target_files = [
        "handlers/admin/modules/system/data_management_handler.py",
        "handlers/admin/modules/system/import_export.py",
        "handlers/admin/modules/system/admin_management.py",
        "handlers/admin/modules/system/notification_handler.py",
        "handlers/admin/modules/support/ticket_handler.py",
        "handlers/admin/modules/support/faq_handler.py",
    ]
    awaited_calls = {
        "self.is_admin",
        "self.role_manager.has_permission",
        "self.role_manager.is_admin",
        "self.role_manager.is_super_admin",
        "self.role_manager.get_user_permissions",
    }

    failures: list[str] = []
    for rel_path in target_files:
        source = _read(rel_path)
        tree = ast.parse(source, filename=rel_path)
        parents = _build_parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            chain = _attribute_chain(node.func)
            if chain not in awaited_calls:
                continue
            if not _is_awaited(node, parents):
                failures.append(f"{rel_path}:{node.lineno} -> {chain}")

    assert not failures, "Missing await in admin permission paths:\n" + "\n".join(
        failures
    )


def test_no_missing_await_in_admin_repo_db_paths_via_ast() -> None:
    target_files = [
        "handlers/admin/modules/system/data_management_handler.py",
        "handlers/admin/modules/system/import_export.py",
        "handlers/admin/modules/system/admin_management.py",
        "handlers/admin/modules/system/notification_handler.py",
        "handlers/admin/modules/support/ticket_handler.py",
        "handlers/admin/modules/support/faq_handler.py",
    ]
    repo_prefixes = (
        "db.users.",
        "db.settings.",
        "db.analytics.",
        "db.cms.",
        "db.support.",
        "db.attachments.",
        "self.db.users.",
        "self.db.settings.",
        "self.db.analytics.",
        "self.db.cms.",
        "self.db.support.",
        "self.db.attachments.",
    )

    failures: list[str] = []
    for rel_path in target_files:
        source = _read(rel_path)
        tree = ast.parse(source, filename=rel_path)
        parents = _build_parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            chain = _attribute_chain(node.func)
            if chain is None or not chain.startswith(repo_prefixes):
                continue
            if not _is_awaited(node, parents):
                failures.append(f"{rel_path}:{node.lineno} -> {chain}")

    assert not failures, "Missing await in admin repo/db paths:\n" + "\n".join(failures)


def test_setup_script_has_no_hardcoded_password_output() -> None:
    text = _read("scripts/setup_database.py")
    assert "Ox Loadout_Secure_2025!@#" not in text
    assert 'print(f"  Password: {DB_PASSWORD}")' not in text
    assert "mask_secret(" in text


def test_migration_baseline_is_wired_as_schema_source() -> None:
    compose = _read("docker-compose.yml")
    deploy = _read("deploy.sh")
    setup_py = _read("scripts/setup_database.py")
    init_sql = _read("scripts/init_postgres.sql")
    migration_0001 = _read("scripts/migrations/0001_baseline.sql")

    assert "./scripts/migrations:/docker-entrypoint-initdb.d:ro" in compose
    assert "DB_RUNTIME_SCHEMA_ENSURE=false" in compose
    assert "DB_RUNTIME_SCHEMA_ENSURE=false" in deploy
    assert (ROOT / "scripts/migrations/0001_baseline.sql").exists()
    assert (ROOT / "scripts/migrations/0002_guides_split_tables.sql").exists()
    assert (ROOT / "scripts/migrations/0003_runtime_parity_tables.sql").exists()
    assert (ROOT / "scripts/migrations/0004_schema_canonical_backfill.sql").exists()
    assert "migrations" in setup_py
    assert "_migrations" in setup_py
    assert "migrations/0001_baseline.sql" in init_sql
    assert "migrations/0002_guides_split_tables.sql" in init_sql
    assert "migrations/0003_runtime_parity_tables.sql" in init_sql
    assert "migrations/0004_schema_canonical_backfill.sql" in init_sql
    assert "pg_get_userbyid(datdba)" in migration_0001
    assert "ox_loadout_bot_user" not in migration_0001


def test_callback_routing_contracts_for_attachment_details() -> None:
    user_registry = _read("app/registry/user_registry.py")
    search_handler = _read("handlers/user/modules/search/search_handler.py")
    all_handler = _read("handlers/user/modules/attachments/all_handler.py")

    # Notification callbacks keep the double-underscore namespace and run in group=-1.
    assert 'pattern="^attm__"' in user_registry
    # General attachment-with-mode handler must not catch attm__ callbacks.
    assert 'pattern=r"^attm_(?!_)"' in user_registry
    # Search quick callbacks are explicitly routed to SearchHandler.
    assert 'pattern="^qatt_"' in user_registry
    # Dead branch removed: attm path should not blindly redirect to qatt handler.
    assert (
        "return await self.send_attachment_quick(update, context)" not in search_handler
    )
    # attachment_detail_with_mode should initialize lang before using it.
    assert "lang = await get_user_lang" in all_handler


def test_ua_admin_permission_logic_is_centralized() -> None:
    ua_files = [
        "handlers/admin/user_attachments_admin/reports_handler.py",
        "handlers/admin/user_attachments_admin/stats_handler.py",
        "handlers/admin/user_attachments_admin/settings_handler.py",
        "handlers/admin/user_attachments_admin/banned_handler.py",
        "handlers/admin/user_attachments_admin/review_handler.py",
    ]

    for rel_path in ua_files:
        text = _read(rel_path)
        assert "has_manage_user_attachments_permission" in text, rel_path
        assert "Permission.MANAGE_USER_ATTACHMENTS" not in text, rel_path


def test_review_conversations_do_not_use_per_message_true_with_message_states() -> None:
    review_handler = _read("handlers/admin/user_attachments_admin/review_handler.py")
    assert 'name="ua_admin_reject"' in review_handler
    assert 'name="ua_admin_edit_weapon"' in review_handler
    assert "per_message=True" not in review_handler


def test_environment_and_db_defaults_are_consistent() -> None:
    deploy = _read("deploy.sh")
    compose = _read("docker-compose.yml")
    setup_py = _read("scripts/setup_database.py")
    env_example = _read(".env.example")
    db_pg = _read("core/database/database_pg.py")

    assert 'DEFAULT_DB_NAME="ox_loadout_bot"' in deploy
    assert 'DEFAULT_DB_USER="ox_loadout_admin"' in deploy

    assert "POSTGRES_DB=ox_loadout_bot" in compose
    assert "POSTGRES_USER=ox_loadout_admin" in compose
    assert (
        "postgresql://ox_loadout_admin:${POSTGRES_PASSWORD}@postgres:5432/ox_loadout_bot" in compose
    )

    assert 'os.getenv("POSTGRES_DB", "ox_loadout_bot")' in setup_py
    assert 'os.getenv("POSTGRES_USER", "ox_loadout_admin")' in setup_py
    assert "DB_RUNTIME_SCHEMA_ENSURE=false" in env_example

    assert '"ENVIRONMENT", os.getenv("ENV"' in db_pg.replace("'", '"')


def test_dockerfile_is_hardened_for_non_root_runtime() -> None:
    dockerfile = _read("Dockerfile")

    assert "python -m venv /opt/venv" in dockerfile
    assert "COPY --from=builder /opt/venv /opt/venv" in dockerfile
    assert "adduser --system --ingroup app --home /app app" in dockerfile
    assert "USER app" in dockerfile
    assert "PATH=/opt/venv/bin:$PATH" in dockerfile


def test_compose_healthcheck_uses_readiness_probe_script() -> None:
    compose = _read("docker-compose.yml")
    health_script = _read("scripts/health_check.py")

    assert (
        'test: [ "CMD", "python", "scripts/health_check.py", "--mode", "readiness" ]'
        in compose
    )
    assert "def run_readiness_checks() -> dict:" in health_script
    assert "check_database_readiness()" in health_script


def test_gitignore_does_not_exclude_all_docs_and_reports() -> None:
    gitignore = _read(".gitignore")

    assert "\ndocs/\n" not in gitignore
    assert "\n/reports/\n" not in gitignore
    assert "/reports/generated/" in gitignore


def test_guide_schema_split_tables_are_consistent_across_sources() -> None:
    migration_0001 = _read("scripts/migrations/0001_baseline.sql")
    migration_0002 = _read("scripts/migrations/0002_guides_split_tables.sql")
    migration_0004 = _read("scripts/migrations/0004_schema_canonical_backfill.sql")
    db_pg = _read("core/database/database_pg.py")

    assert "CREATE TABLE IF NOT EXISTS guide_media" in migration_0001
    assert "CREATE TABLE IF NOT EXISTS guide_photos" in migration_0002
    assert "CREATE TABLE IF NOT EXISTS guide_videos" in migration_0002
    assert "guide_media" in migration_0002
    assert "CREATE TABLE IF NOT EXISTS guide_media" in migration_0004
    assert "CREATE TABLE IF NOT EXISTS guide_photos" not in db_pg
    assert "CREATE TABLE IF NOT EXISTS guide_videos" not in db_pg


def test_runtime_parity_tables_are_owned_by_migrations_only() -> None:
    migration_0003 = _read("scripts/migrations/0003_runtime_parity_tables.sql")
    setup_sql = _read("scripts/setup_database.sql")
    db_pg = _read("core/database/database_pg.py")

    tables = [
        "analytics_events",
        "user_notification_preferences",
        "scheduled_notifications",
        "attachment_metrics",
        "attachment_performance",
        "cms_content",
        "analytics_users",
        "analytics_channels",
        "analytics_daily_stats",
        "subscribers",
    ]

    for table in tables:
        clause = f"CREATE TABLE IF NOT EXISTS {table}"
        assert clause in migration_0003
        assert clause not in setup_sql
        assert clause not in db_pg


def test_runtime_schema_is_guard_only_and_migration_owned() -> None:
    db_pg = _read("core/database/database_pg.py")
    assert "self._ensure_runtime_guards" in db_pg
    assert "def _ensure_runtime_guards(self):" in db_pg
    assert "tables_sql = [" not in db_pg
    assert "indexes_sql = [" not in db_pg
    assert db_pg.count("CREATE TABLE IF NOT EXISTS") == 0
    assert db_pg.count("CREATE INDEX IF NOT EXISTS") == 0
    assert "Schema ownership belongs to SQL migrations." in db_pg


def test_td06_no_legacy_db_direct_calls_outside_repository_layer() -> None:
    offenders: list[str] = []

    for path in _iter_td06_guard_files():
        rel_path = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for match in LEGACY_DB_DIRECT_CALL_PATTERN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{rel_path}:{line_no}:{match.group(0)}")

    assert not offenders, "Legacy direct database calls remain:\n" + "\n".join(
        offenders[:40]
    )


def test_td06_database_postgres_has_no_compat_proxy() -> None:
    db_pg = _read("core/database/database_pg.py")

    assert "def __getattr__(self, name):" not in db_pg


def test_td07_no_database_mixins_imports_or_runtime_files() -> None:
    offenders: list[str] = []
    import_patterns = tuple(
        re.compile(pattern)
        for pattern in (
            r"from\s+core\.database\.mixins(?:\.|\s+import\s+)",
            r"import\s+core\.database\.mixins(?:\.|\s|$)",
            r"from\s+\.mixins(?:\.|\s+import\s+)",
        )
    )

    for path in _iter_td06_guard_files():
        rel_path = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for pattern in import_patterns:
            if pattern.search(text):
                offenders.append(f"{rel_path}:{pattern.pattern}")

    mixin_files = sorted((ROOT / "core/database/mixins").glob("*.py"))
    if mixin_files:
        offenders.extend(f"core/database/mixins/{path.name}" for path in mixin_files)

    assert not offenders, (
        "Legacy database mixins remain in repo/runtime path:\n"
        + "\n".join(offenders[:40])
    )


def test_td08_error_taxonomy_exists() -> None:
    errors = _read("core/errors.py")

    required = [
        "class AppError(Exception):",
        "class UserFacingError(AppError):",
        "class PermissionDeniedError(UserFacingError):",
        "class ValidationError(UserFacingError):",
        "class NotFoundError(UserFacingError):",
        "class ConflictError(UserFacingError):",
        "class InfrastructureError(AppError):",
        "class ExternalDependencyError(InfrastructureError):",
        "class TransientError(InfrastructureError):",
    ]

    for clause in required:
        assert clause in errors


def test_td08_restore_flow_uses_typed_errors_and_helper_download() -> None:
    health_report = _read("handlers/admin/modules/reports/data_health_report.py")

    assert "ExternalDependencyError" in health_report
    assert "InfrastructureError" in health_report
    assert "async def _download_restore_file(" in health_report
    assert (
        "file = await self._download_restore_file(context, file_id, temp_path)"
        in health_report
    )
    assert (
        'raise Exception("Network Error: Could not connect to Telegram API. Check your proxy/VPN.")'
        not in health_report
    )
    assert (
        'raise Exception("Network Error: Connection failed during download. This is likely a proxy/VPN issue.")'
        not in health_report
    )


def test_td08_ua_admin_live_paths_use_error_taxonomy_helpers() -> None:
    reports_handler = _read("handlers/admin/user_attachments_admin/reports_handler.py")
    review_handler = _read("handlers/admin/user_attachments_admin/review_handler.py")

    assert "from core.errors import ValidationError" in reports_handler
    assert "from utils.logger import get_logger, log_exception" in reports_handler
    assert "def _parse_report_action_ids(" in reports_handler
    assert "async def _send_report_owner_notification(" in reports_handler
    assert (
        'log_exception(logger, e, "ua_reports.delete_reported_attachment")'
        in reports_handler
    )
    assert (
        'log_exception(logger, e, "ua_reports.warn_owner_about_report")'
        in reports_handler
    )
    assert 'log_exception(logger, e, "ua_reports.dismiss_report")' in reports_handler

    assert "from core.errors import ValidationError" in review_handler
    assert "from utils.logger import get_logger, log_exception" in review_handler
    assert "def _parse_attachment_action_id(" in review_handler
    assert "async def _send_attachment_owner_notification(" in review_handler
    assert "UA attachment view source message" in review_handler
    assert "await _invalidate_review_cache(\"stats\", \"count\")" in review_handler.replace("'", '"')
    assert 'log_exception(logger, e, "ua_admin.approve_attachment")' in review_handler
    assert (
        'log_exception(logger, e, "ua_admin.receive_reject_reason")' in review_handler
    )
    assert 'log_exception(logger, e, "ua_admin.show_attachment_view")' in review_handler
    assert (
        'log_exception(logger, e, "ua_admin.delete_attachment_admin")' in review_handler
    )
    assert (
        'log_exception(logger, e, "ua_admin.restore_attachment_admin")'
        in review_handler
    )
    assert (
        'log_exception(logger, e, "ua_admin.receive_new_weapon_name")' in review_handler
    )
    assert "db.settings.update_submission_stats(" not in review_handler


def test_td08_channel_stats_handlers_use_shared_fallback_helpers() -> None:
    stats_handlers = _read("handlers/channel/stats_handlers.py")

    assert "from core.errors import InfrastructureError" in stats_handlers
    assert (
        "async def _resolve_lang(update: Update, context: CustomContext) -> str:"
        in stats_handlers
    )
    assert "def _format_added_at(added_at: object) -> str:" in stats_handlers
    assert "async def _render_stats_error(" in stats_handlers
    assert "lang = await _resolve_lang(update, context)" in stats_handlers
    assert "raise InfrastructureError(" in stats_handlers


def test_td02_remaining_admin_modules_record_permission_denials() -> None:
    notification_handler = _read(
        "handlers/admin/modules/system/notification_handler.py"
    )
    ticket_handler = _read("handlers/admin/modules/support/ticket_handler.py")
    faq_handler = _read("handlers/admin/modules/support/faq_handler.py")
    admin_management = _read("handlers/admin/modules/system/admin_management.py")
    user_management = _read("handlers/admin/modules/system/user_management.py")
    stats_backup = _read("handlers/admin/modules/system/stats_backup.py")
    cms_handler = _read("handlers/admin/modules/content/cms_handler.py")
    role_manager = _read("core/security/role_manager.py")
    health_report = _read("handlers/admin/modules/reports/data_health_report.py")

    assert 'route="admin_notify_home"' in notification_handler
    assert 'route="admin_schedule_edit_open"' in notification_handler
    assert 'route="admin_notify_compose_start"' in notification_handler
    assert 'route="admin_schedules_menu"' in notification_handler
    assert 'route="admin_schedule_toggle"' in notification_handler
    assert 'route="admin_schedule_delete"' in notification_handler

    assert 'route="admin_tickets_menu"' in ticket_handler

    assert 'route="admin_faqs_menu"' in faq_handler
    assert 'route="admin_faq_list"' in faq_handler
    assert 'route="admin_faq_view"' in faq_handler
    assert 'route="admin_faq_stats"' in faq_handler
    assert 'route="admin_faq_add_start"' in faq_handler

    assert 'route="manage_admins_menu"' in admin_management
    assert 'route="add_admin_start"' in admin_management

    assert "route=func.__name__" in role_manager
    assert "source=func.__name__" in role_manager
    assert "await _audit_denial(\"not_admin\")" in role_manager.replace("'", '"')
    assert "await _audit_denial(\"permission_denied\")" in role_manager.replace("'", '"')

    assert 'route="stats_backup_create_backup"' in stats_backup

    assert 'route="user_mgmt_menu"' in user_management
    assert 'route="user_list"' in user_management
    assert 'route="user_search_start"' in user_management
    assert 'route="user_filter_banned"' in user_management
    assert 'route="user_detail"' in user_management
    assert 'route="user_ban_start"' in user_management
    assert 'route="user_unban"' in user_management
    assert 'route="user_search_received"' in user_management
    assert 'route="user_ban_confirm"' in user_management

    assert 'route="cms_menu"' in cms_handler
    assert 'route="cms_add_start"' in cms_handler
    assert 'route="cms_list_menu"' in cms_handler

    assert 'route="health_run_check"' in health_report
    assert 'route="health_fix_issues_menu"' in health_report
    assert 'route="health_check_missing_images"' in health_report
    assert 'route="health_check_duplicate_codes"' in health_report
    assert 'route="health_check_orphaned"' in health_report
    assert 'route="health_create_backup"' in health_report
    assert 'route="health_restore_backup"' in health_report
    assert 'route="health_restore_backup_file"' in health_report


def test_setup_script_requires_migrations_and_never_falls_back_to_setup_sql() -> None:
    setup_py = _read("scripts/setup_database.py")

    assert "Migration files are required" in setup_py
    assert "setup_database.sql is deprecated and is not the schema source" in setup_py
    assert "falling back to setup_database.sql" not in setup_py
    assert 'script_path = Path(__file__).parent / "setup_database.sql"' not in setup_py
    assert "def ensure_database_user():" in setup_py
    assert "ALTER USER {} WITH CREATEDB" in setup_py


def test_setup_database_sql_is_deprecated_shim_only() -> None:
    setup_sql = _read("scripts/setup_database.sql")

    assert "DEPRECATED / NON-AUTHORITATIVE" in setup_sql
    assert (
        "Schema ownership belongs exclusively to scripts/migrations/*.sql." in setup_sql
    )
    assert (
        "Deprecated shim: use scripts/setup_database.py or scripts/init_postgres.sql with migrations"
        in setup_sql
    )
    assert "CREATE TABLE IF NOT EXISTS" not in setup_sql
    assert "CREATE INDEX IF NOT EXISTS" not in setup_sql


def test_migration_smoke_ci_job_and_verifier_are_present() -> None:
    workflow = _read(".github/workflows/ci.yml")
    verifier = _read("scripts/verify_canonical_bootstrap.py")

    assert "migration-smoke:" in workflow
    assert "image: postgres:16" in workflow
    assert "python scripts/setup_database.py --drop-existing" in workflow
    assert "python scripts/verify_canonical_bootstrap.py" in workflow
    assert "--require-migration 0004_schema_canonical_backfill.sql" in workflow
    assert "EXPECTED_MIGRATIONS" in verifier
    assert "EXPECTED_TABLES" in verifier
    assert "Expected bootstrap-owned tables to belong to" in verifier
    assert "--require-migration" in verifier


def test_deploy_and_runtime_bootstrap_use_canonical_setup_runner_only() -> None:
    deploy = _read("deploy.sh")
    ox_loadout = _read("scripts/ox-loadout")
    health_check = _read("scripts/health_check.py")

    assert "setup_database.sql" not in deploy
    assert "setup_database.sql" not in ox_loadout
    assert '"scripts/setup_database.sql"' not in health_check
    assert 'scripts/setup_database.py" --migrate-only' in deploy
    assert 'scripts/setup_database.py" --migrate-only' in ox_loadout


def test_permission_deny_audit_contracts_are_present() -> None:
    audit = _read("core/audit.py")
    admin_base = _read("handlers/admin/modules/base_handler.py")
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    admin_entry_flow = _read("handlers/admin/admin_entry_flow.py")
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    channel_menu_handlers = _read("handlers/channel/menu_handlers.py")
    data_mgmt = _read("handlers/admin/modules/system/data_management_handler.py")
    import_export = _read("handlers/admin/modules/system/import_export.py")
    ua_permissions = _read("handlers/admin/user_attachments_admin/permissions.py")

    assert "async def log_permission_decision(" in audit
    assert '"PERMISSION_DENIED"' in audit
    assert "async def audit_permission_denied(" in admin_base
    assert "async def send_permission_denied(" in admin_base
    assert "run_admin_start(" in admin_modular
    assert "run_admin_start_msg(" in admin_modular
    assert 'route="admin_start"' in admin_entry_flow
    assert 'route="admin_start_msg"' in admin_entry_flow
    assert 'route="admin_menu"' in admin_modular
    assert "async def audit_channel_permission_denied(" in channel_handlers
    assert "audit_permission_denied=audit_channel_permission_denied" in channel_handlers
    assert (
        "await audit_permission_denied(update.effective_user.id)"
        in channel_menu_handlers
    )
    assert 'route="admin_data_management"' in data_mgmt
    assert 'route="admin_create_backup"' in data_mgmt
    assert 'route="admin_import_start"' in import_export
    assert 'route="admin_export_start"' in import_export
    assert "audit_logger: AuditLogger | None = None" in ua_permissions
    assert '"permission_denied"' in ua_permissions


def test_schema_canonical_backfill_migration_covers_legacy_drift() -> None:
    migration_0004 = _read("scripts/migrations/0004_schema_canonical_backfill.sql")

    required_snippets = [
        "ALTER TABLE user_attachments\n    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;",
        "ALTER TABLE user_attachments\n    ADD COLUMN IF NOT EXISTS deleted_by BIGINT REFERENCES admins(user_id);",
        "ALTER TABLE user_attachments\n    ADD COLUMN IF NOT EXISTS view_count INTEGER NOT NULL DEFAULT 0;",
        "ALTER TABLE user_submission_stats\n    ADD COLUMN IF NOT EXISTS deleted_count INTEGER NOT NULL DEFAULT 0;",
        "ALTER TABLE analytics_users\n    ADD COLUMN IF NOT EXISTS registration_source TEXT;",
        "ALTER TABLE ua_stats_cache\n    ADD COLUMN IF NOT EXISTS deleted_count INTEGER DEFAULT 0;",
        "CREATE TABLE IF NOT EXISTS user_faq_votes",
        "CREATE TABLE IF NOT EXISTS guide_media",
        "ADD CONSTRAINT user_attachments_status_check",
    ]

    for snippet in required_snippets:
        assert snippet in migration_0004


def test_channel_history_stats_handler_is_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    stats_handlers = _read("handlers/channel/stats_handlers.py")
    diagnostics_handlers = _read("handlers/channel/diagnostics_handlers.py")

    assert "show_channel_history_impl" in channel_handlers
    assert "show_channel_history_impl" in channel_handlers
    assert (
        "async def show_channel_history_impl("
        in stats_handlers
    )
    assert "test_channel_access_impl" in channel_handlers
    assert "return await test_channel_access_impl(" in channel_handlers
    assert "async def test_channel_access_impl(" in diagnostics_handlers


def test_channel_reorder_handlers_are_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    reorder_handlers = _read("handlers/channel/reorder_handlers.py")

    assert "reorder_channels_menu_impl" in channel_handlers
    assert "handle_move_channel_impl" in channel_handlers
    assert "return await reorder_channels_menu_impl(" in channel_handlers
    assert "return await handle_move_channel_impl(" in channel_handlers
    assert "async def reorder_channels_menu_impl(" in reorder_handlers
    assert "async def handle_move_channel_impl(" in reorder_handlers


def test_channel_management_conversation_uses_per_message_false() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    assert "def get_channel_management_handler():" in channel_handlers
    assert "per_message=False" in channel_handlers


def test_channel_details_handlers_are_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    details_handlers = _read("handlers/channel/details_handlers.py")

    assert "view_channel_details_impl" in channel_handlers
    assert "toggle_channel_status_impl" in channel_handlers
    assert "return await view_channel_details_impl(" in channel_handlers
    assert "return await toggle_channel_status_impl(" in channel_handlers
    assert "async def view_channel_details_impl(" in details_handlers
    assert "async def toggle_channel_status_impl(" in details_handlers


def test_channel_permission_logic_is_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    permissions = _read("handlers/channel/permissions.py")

    assert "check_channel_management_permission_impl" in channel_handlers
    assert (
        "return await check_channel_management_permission_impl(user_id, context)"
        in channel_handlers
    )
    assert "async def check_channel_management_permission_impl(" in permissions


def test_channel_navigation_handlers_are_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    navigation_handlers = _read("handlers/channel/navigation_handlers.py")

    assert "cancel_impl" in channel_handlers
    assert "return_to_admin_menu_impl" in channel_handlers
    assert "return await cancel_impl(" in channel_handlers
    assert "return await return_to_admin_menu_impl(" in channel_handlers
    assert "async def cancel_impl(" in navigation_handlers
    assert "async def return_to_admin_menu_impl(" in navigation_handlers


def test_channel_menu_helpers_are_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    menu_helpers = _read("handlers/channel/menu_helpers.py")
    menu_handlers = _read("handlers/channel/menu_handlers.py")

    assert "channel_management_menu_impl" in channel_handlers
    assert "noop_cb_impl" in channel_handlers
    assert "handle_page_navigation_impl" in channel_handlers
    assert "return await channel_management_menu_impl(" in channel_handlers
    assert "return await noop_cb_impl(update, context)" in channel_handlers
    assert "return await handle_page_navigation_impl(" in channel_handlers
    assert (
        "def paginate_list(items: list, page: int, per_page: int) -> tuple:"
        in menu_helpers
    )
    assert "def build_channel_menu_view(" in menu_helpers
    assert (
        "async def noop_cb_impl(update: Update, context: CustomContext):"
        in menu_helpers
    )
    assert "async def handle_page_navigation_impl(" in menu_helpers
    assert "async def channel_management_menu_impl(" in menu_handlers
    assert "build_channel_menu_view(" in menu_handlers


def test_channel_clear_action_is_extracted() -> None:
    channel_handlers = _read("handlers/channel/channel_handlers.py")
    management_actions = _read("handlers/channel/management_actions.py")
    add_handlers = _read("handlers/channel/add_handlers.py")
    edit_handlers = _read("handlers/channel/edit_handlers.py")
    delete_handlers = _read("handlers/channel/delete_handlers.py")

    assert "clear_channels_impl" in channel_handlers
    assert "return await clear_channels_impl(" in channel_handlers
    assert "async def clear_channels_impl(" in management_actions
    assert "delete_channel_start_impl" in channel_handlers
    assert "delete_channel_confirm_impl" in channel_handlers
    assert "delete_channel_execute_impl" in channel_handlers
    assert "return await delete_channel_start_impl(" in channel_handlers
    assert "return await delete_channel_confirm_impl(" in channel_handlers
    assert "return await delete_channel_execute_impl(" in channel_handlers
    assert "async def delete_channel_start_impl(" in delete_handlers
    assert "async def delete_channel_confirm_impl(" in delete_handlers
    assert "async def delete_channel_execute_impl(" in delete_handlers
    assert "edit_channel_start_impl" in channel_handlers
    assert "edit_channel_select_impl" in channel_handlers
    assert "edit_channel_field_impl" in channel_handlers
    assert "edit_channel_value_impl" in channel_handlers
    assert "return await edit_channel_start_impl(" in channel_handlers
    assert "return await edit_channel_select_impl(" in channel_handlers
    assert "return await edit_channel_field_impl(" in channel_handlers
    assert "return await edit_channel_value_impl(" in channel_handlers
    assert "async def edit_channel_start_impl(" in edit_handlers
    assert "async def edit_channel_select_impl(" in edit_handlers
    assert "async def edit_channel_field_impl(" in edit_handlers
    assert "async def edit_channel_value_impl(" in edit_handlers
    assert "add_channel_start_impl" in channel_handlers
    assert "add_channel_id_impl" in channel_handlers
    assert "use_default_title_impl" in channel_handlers
    assert "add_channel_title_impl" in channel_handlers
    assert "add_channel_url_impl" in channel_handlers
    assert "save_channel_confirm_impl" in channel_handlers
    assert "return await add_channel_start_impl(" in channel_handlers
    assert "return await add_channel_id_impl(" in channel_handlers
    assert "return await use_default_title_impl(" in channel_handlers
    assert "return await add_channel_title_impl(" in channel_handlers
    assert "return await add_channel_url_impl(" in channel_handlers
    assert "return await save_channel_confirm_impl(" in channel_handlers
    assert "async def add_channel_start_impl(" in add_handlers
    assert "async def add_channel_id_impl(" in add_handlers
    assert "async def use_default_title_impl(" in add_handlers
    assert "async def add_channel_title_impl(" in add_handlers
    assert "async def add_channel_url_impl(" in add_handlers
    assert "async def save_channel_confirm_impl(" in add_handlers


def test_channel_module_size_guards() -> None:
    module_limits = {
        "handlers/channel/channel_handlers.py": 500,
        "handlers/channel/stats_handlers.py": 420,
        "handlers/channel/add_handlers.py": 500,
        "handlers/channel/edit_handlers.py": 300,
        "handlers/channel/delete_handlers.py": 220,
        "handlers/channel/diagnostics_handlers.py": 180,
    }

    for rel_path, max_lines in module_limits.items():
        line_count = len(_read(rel_path).splitlines())
        assert line_count <= max_lines, (
            f"{rel_path} grew to {line_count} lines (limit={max_lines})"
        )


def test_admin_modular_handler_initialization_guards() -> None:
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    admin_setup = _read("handlers/admin/admin_handler_setup.py")

    # Duplicate overwrite bug guard: handler must be initialized once.
    assert "init_attachment_handlers(self)" in admin_modular
    assert (
        admin_setup.count(
            "handler.top_attachments_handler = TopAttachmentsHandler(handler.db)"
        )
        == 1
    )

    # Content init must not recreate category/weapon handlers after system init.
    content_start = admin_setup.index("def init_content_handlers")
    content_end = admin_setup.index("def init_new_feature_handlers")
    content_block = admin_setup[content_start:content_end]

    assert 'if not hasattr(handler, "category_handler")' in content_block
    assert 'if not hasattr(handler, "weapon_handler")' in content_block
    assert (
        content_block.count("handler.category_handler = CategoryHandler(handler.db)")
        == 1
    )
    assert (
        content_block.count("handler.weapon_handler = WeaponHandler(handler.db)") == 1
    )


def test_admin_menu_notification_routing_is_extracted() -> None:
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    admin_setup = _read("handlers/admin/admin_handler_setup.py")
    routing = _read("handlers/admin/admin_menu_routing.py")

    assert "init_action_routes(self)" in admin_modular
    assert "route_notification_actions" in admin_setup
    assert "route_data_management_actions" in admin_setup
    assert "route_support_actions" in admin_setup
    assert "route_content_actions" in admin_setup
    assert "build_admin_menu_exact_routes" in admin_setup
    assert "build_notification_action_routes" in admin_setup
    assert "build_data_management_action_routes" in admin_setup
    assert "build_support_action_routes" in admin_setup
    assert "build_content_action_routes" in admin_setup
    assert "async def route_notification_actions(" in routing
    assert "async def route_data_management_actions(" in routing
    assert "async def route_support_actions(" in routing
    assert "async def route_content_actions(" in routing
    assert "route_analytics_actions" in admin_setup
    assert "route_health_actions" in admin_setup
    assert "route_feedback_actions" in admin_setup
    assert "route_admin_management_actions" in admin_setup
    assert "route_user_management_actions" in admin_setup
    assert "handler._admin_menu_route_groups = (" in admin_setup
    assert "for router, routes in self._admin_menu_route_groups:" in admin_modular
    assert (
        "route_result = await router(action, update, context, routes)" in admin_modular
    )
    assert (
        "handler._notification_action_routes = build_notification_action_routes(handler)"
        in admin_setup
    )
    assert (
        "handler._data_management_action_routes = build_data_management_action_routes("
        in admin_setup
    )
    assert (
        "handler._support_action_routes = build_support_action_routes(handler)"
        in admin_setup
    )
    assert (
        "handler._content_action_routes = build_content_action_routes(" in admin_setup
    )
    assert (
        "handler._analytics_action_routes = build_analytics_action_routes("
        in admin_setup
    )
    assert "handler._health_action_routes = build_health_action_routes(" in admin_setup
    assert "build_feedback_action_routes(" in admin_setup
    assert (
        "build_admin_management_action_routes("
        in admin_setup
    )
    assert (
        "build_user_management_action_routes("
        in admin_setup
    )
    assert "async def route_analytics_actions(" in routing
    assert "async def route_health_actions(" in routing
    assert "async def route_feedback_actions(" in routing
    assert "async def route_admin_management_actions(" in routing
    assert "async def route_user_management_actions(" in routing
    assert "def __getattr__(" not in admin_modular


def test_admin_navigation_back_routing_is_extracted() -> None:
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    navigation = _read("handlers/admin/navigation_routing.py")
    routing = _read("handlers/admin/admin_menu_routing.py")

    assert "handle_admin_navigation_back" in admin_modular
    assert '"nav_back": handler.handle_navigation_back' in routing
    assert "return await handle_admin_navigation_back(" in admin_modular
    assert "fallback=super().handle_navigation_back" in admin_modular
    assert "async def handle_admin_navigation_back(" in navigation


def test_admin_menu_duplicate_legacy_routing_is_removed() -> None:
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    admin_entry_flow = _read("handlers/admin/admin_entry_flow.py")
    admin_setup = _read("handlers/admin/admin_handler_setup.py")

    assert (
        'if (action.startswith("notif_") or action.startswith("tmpl_")'
        not in admin_modular
    )
    assert (
        'if action.startswith("analytics_") or action == "attachment_analytics"'
        not in admin_modular
    )
    assert (
        'elif action.startswith("health_") or action == "data_health"'
        not in admin_modular
    )
    assert 'elif action.startswith("fb_")' not in admin_modular
    assert 'if action.startswith("selrole_")' not in admin_modular
    assert 'elif action == "admin_users"' not in admin_modular
    assert 'elif action == "admin_data_management":' not in admin_modular
    assert 'elif action == "admin_faqs":' not in admin_modular
    assert 'elif action == "admin_guides":' not in admin_modular
    assert 'elif action == "admin_cms" and self.cms_handler:' not in admin_modular
    assert (
        'elif action == "admin_texts" or action.startswith("text_edit_"):'
        not in admin_modular
    )
    assert "async def run_admin_start(" in admin_entry_flow
    assert "async def run_admin_start_msg(" in admin_entry_flow
    assert "async def run_admin_cancel(" in admin_entry_flow
    assert "async def run_search_cancel_and_admin(" in admin_entry_flow
    assert "async def run_admin_exit_silent(" in admin_entry_flow
    assert "def init_attachment_handlers(handler) -> None:" in admin_setup
    assert "def init_action_routes(handler) -> None:" in admin_setup
    assert len(admin_modular.splitlines()) <= 500


def test_backup_restore_routing_contracts_are_consistent() -> None:
    routing = _read("handlers/admin/admin_menu_routing.py")
    registry = _read("app/registry/admin_registry_states.py")
    admin_modular = _read("handlers/admin/admin_handlers_modular.py")
    admin_setup = _read("handlers/admin/admin_handler_setup.py")

    assert '"admin_create_backup": data_handler.create_backup' in routing
    assert '"health_create_backup": handler.create_backup' in routing
    assert '"admin_restore_backup": handler.restore_backup_start' in routing
    assert "admin_handlers.data_mgmt_handler.create_backup" in registry
    assert (
        "admin_handlers.health_handler.restore_backup_start"
        in registry
    )
    assert (
        "admin_handlers.data_management_menu"
        in registry
    )
    assert (
        "admin_handlers.health_handler.fix_issues_menu"
        in registry
    )
    assert "init_action_routes(self)" in admin_modular
    assert (
        "handler._data_management_action_routes = build_data_management_action_routes("
        in admin_setup
    )
    assert (
        'elif action == "admin_backup" or action == "admin_create_backup":'
        not in admin_modular
    )


def test_health_restore_reply_contracts_are_canonical() -> None:
    health_report = _read("handlers/admin/modules/reports/data_health_report.py")
    fa_locale = _read("locales/fa.json")
    en_locale = _read("locales/en.json")

    assert "def _restore_back_markup(" in health_report
    assert "async def _reply_restore_message(" in health_report
    assert "def _build_restore_success_message(" in health_report
    assert "def _is_local_sqlite_path(" in health_report
    assert "if not db_path or ':' in db_path" not in health_report
    assert 'callback_data="fix_issues_menu"' not in health_report
    assert "reply_markup = self._restore_back_markup(lang)" in health_report
    assert "await self._reply_restore_message(" in health_report
    assert 'file_name = getattr(document, "file_name", "") or ""' in health_report
    assert 'file_id = getattr(document, "file_id", "") or ""' in health_report
    assert 'getattr(file, "file_path", "<unknown>")' in health_report
    assert "except zipfile.BadZipFile as exc:" in health_report
    assert "if query:" in health_report
    assert "await context.bot.send_message(" in health_report
    assert "t('admin.health.restore.success', lang)" not in health_report
    assert '"admin.health.restore.partial_success"' in fa_locale
    assert '"admin.health.restore.partial_success"' in en_locale


def test_td08_support_repository_faq_schema_repair_is_typed() -> None:
    support_repo = _read("core/database/repositories/support_repository.py")

    assert "from core.errors import InfrastructureError" in support_repo
    assert "def _is_faq_language_schema_error(exc: Exception) -> bool:" in support_repo
    assert (
        "def _is_faq_not_helpful_schema_error(exc: Exception) -> bool:" in support_repo
    )
    assert (
        "async def _ensure_faq_not_helpful_count_column(self) -> None:" in support_repo
    )
    assert (
        'raise InfrastructureError("Failed to repair FAQ language schema.") from e'
        in support_repo
    )
    assert "Failed to repair FAQ not_helpful_count schema." in support_repo
    assert "except InfrastructureError as repair_error:" in support_repo
    assert "except:" not in support_repo


def test_td08_user_repository_json_aggregate_decoding_is_centralized() -> None:
    user_repo = _read("core/database/repositories/user_repository.py")

    assert "import json" in user_repo
    assert "def _decode_json_list(value: object, context: str) -> list:" in user_repo
    assert "self._decode_json_list(" in user_repo
    assert "import json as _json" not in user_repo
    assert "import json\n                    perms = json.loads(perms)" not in user_repo


def test_wave1_notification_manager_contract() -> None:
    notif_file = _read("managers/notification_manager.py")
    add_att = _read("handlers/admin/modules/attachments/add_attachment.py")
    edit_att = _read("handlers/admin/modules/attachments/edit_attachment.py")
    del_att = _read("handlers/admin/modules/attachments/delete_attachment.py")
    top_att = _read("handlers/admin/modules/attachments/top_attachments.py")

    assert "def __init__(self, db, subscribers=None, broadcaster=None):" in notif_file
    assert "async def queue_notification(" in notif_file
    assert "async def send_notification(" in notif_file
    assert "await notif_manager.queue_notification(context, event, payload)" in add_att
    assert "await notif_manager.queue_notification(context, event, payload)" in edit_att
    assert "await notif_manager.queue_notification(context, event, payload)" in del_att
    assert "await notif_manager.queue_notification(context, event, payload)" in top_att


def test_wave1_channel_manager_membership_cache_contract() -> None:
    chan_mgr = _read("managers/channel_manager.py")

    assert "_membership_cache[user_id] = (is_member, not_joined or [], datetime.now())" in chan_mgr
    assert "not_joined_cached = entry[1] if len(entry) >= 3 else []" in chan_mgr
    assert "return False, not_joined_cached" in chan_mgr


def test_wave1_database_autocommit_safeguard() -> None:
    health_check = _read("utils/data_health_check.py")
    db_pg = _read("core/database/database_pg.py")

    assert "set_autocommit" not in health_check
    assert 'if getattr(conn, "autocommit", False):' in db_pg
    assert "await conn.set_autocommit(False)" in db_pg


def test_wave1_health_server_and_backup_scheduler_contract() -> None:
    backup_sched = _read("managers/backup_scheduler.py")
    health_srv = _read("core/monitoring/health_server.py")

    assert "def is_alive(self) -> bool:" in backup_sched
    assert 'if hasattr(sched, "is_alive") and callable(sched.is_alive):' in health_srv


def test_wave2_smart_cache_async_support() -> None:
    cache_file = _read("core/cache/smart_cache.py")

    assert "async def warm_cache(self, db):" in cache_file
    assert "if asyncio.iscoroutinefunction(func):" in cache_file


def test_wave2_guides_handler_safe_message() -> None:
    guide_file = _read("handlers/user/modules/guides/guides_handler.py")

    assert "target_message = update.effective_message or (" in guide_file
    assert "update.callback_query.message if update.callback_query else None" in guide_file


def test_ui_formatter_persian_digits() -> None:
    from utils.ui_formatter import to_persian_digits

    assert to_persian_digits("AK117 (1)") == "AK۱۱۷ (۱)"
    assert to_persian_digits(12345) == "۱۲۳۴۵"
    assert to_persian_digits(0) == "۰"
    assert to_persian_digits(None) == ""


def test_ui_formatter_mode_badge() -> None:
    from utils.ui_formatter import format_mode_badge

    assert "بتل رویال" in format_mode_badge("br", "fa")
    assert "مولتی‌پلیر" in format_mode_badge("mp", "fa")
    assert "Battle Royale" in format_mode_badge("br", "en")
    assert "Multiplayer" in format_mode_badge("mp", "en")


def test_ui_formatter_weapon_card() -> None:
    from utils.ui_formatter import format_weapon_card

    card_fa = format_weapon_card("AK117", "Assault Rifle", "br", 5, 2, "fa")
    assert "🔫 **سلاح:** `AK117`" in card_fa
    assert "🎮 **مود بازی:** بتل رویال (BR)" in card_fa
    assert "📊 **کل اتچمنت‌ها:** ۵" in card_fa
    assert "⭐ **اتچمنت‌های برتر:** ۲" in card_fa

    card_en = format_weapon_card("AK117", "Assault Rifle", "br", 5, 2, "en")
    assert "🔫 **Weapon:** `AK117`" in card_en
    assert "📊 **Total Attachments:** 5" in card_en


def test_ui_formatter_button_label() -> None:
    from utils.ui_formatter import format_button_label

    assert format_button_label("⭐ برترین‌ها", 1, "fa") == "⭐ برترین‌ها (۱)"
    assert format_button_label("⭐ Top", 1, "en") == "⭐ Top (1)"
    assert format_button_label("🔙 بازگشت", None, "fa") == "🔙 بازگشت"


def test_i18n_regex_persian_digits_matching() -> None:
    import re
    from utils.i18n import build_regex_for_key

    pattern = build_regex_for_key("weapon.menu.top")
    assert re.match(pattern, "⭐ برترین اتچمنت‌ها")
    assert re.match(pattern, "⭐ برترین اتچمنت‌ها (1)")
    assert re.match(pattern, "⭐ برترین اتچمنت‌ها (۱)")
    assert re.match(pattern, "⭐ Top Attachments")
    assert re.match(pattern, "⭐ Top Attachments (5)")


def test_locales_menu_buttons_start_with_emoji() -> None:
    import json
    from pathlib import Path

    locales_dir = Path("locales")
    with open(locales_dir / "fa.json", encoding="utf-8") as f:
        fa = json.load(f)
    with open(locales_dir / "en.json", encoding="utf-8") as f:
        en = json.load(f)

    for k, v in fa.items():
        if k.startswith("menu.buttons.") and isinstance(v, str):
            assert len(v) > 0
            # Ensure it has characters
            assert v.strip() != ""

    for k, v in en.items():
        if k.startswith("menu.buttons.") and isinstance(v, str):
            assert len(v) > 0
            assert v.strip() != ""



