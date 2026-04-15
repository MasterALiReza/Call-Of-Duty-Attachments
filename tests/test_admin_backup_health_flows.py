from pathlib import Path
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

from handlers.admin.admin_states import ADMIN_MENU, AWAITING_BACKUP_FILE
import handlers.admin.modules.reports.data_health_report as data_health_report
import handlers.admin.modules.system.data_management_handler as data_management_handler
from telegram.constants import ParseMode


def _fake_t(key: str, lang: str, **_: object) -> str:
    return key


def _build_callback_update(callback_data: str = "noop") -> SimpleNamespace:
    query = SimpleNamespace(
        data=callback_data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(
            reply_document=AsyncMock(),
            delete=AsyncMock(),
        ),
    )
    return SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1001, username=None, first_name="Admin"),
        effective_chat=SimpleNamespace(id=2002),
    )


def _build_context() -> SimpleNamespace:
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={}),
        bot=SimpleNamespace(
            send_message=AsyncMock(),
            send_document=AsyncMock(),
            get_file=AsyncMock(),
        ),
        user_data={},
    )


def _build_message_update(file_name: str, file_id: str = "file-1") -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        message=SimpleNamespace(
            document=SimpleNamespace(file_name=file_name, file_id=file_id),
            reply_text=AsyncMock(),
        ),
    )


def _new_data_management_handler(db: object) -> data_management_handler.DataManagementHandler:
    handler = object.__new__(data_management_handler.DataManagementHandler)
    handler.db = db
    handler.scheduler = None
    handler.role_manager = SimpleNamespace(
        has_permission=AsyncMock(return_value=True),
        is_super_admin=AsyncMock(return_value=False),
    )
    handler.send_permission_denied = AsyncMock()
    return handler


def _new_health_handler(
    db: object,
    *,
    db_path: str = "ignored.db",
) -> data_health_report.DataHealthReportHandler:
    handler = object.__new__(data_health_report.DataHealthReportHandler)
    handler.db = db
    handler.health_checker = SimpleNamespace(db_path=db_path)
    handler.check_permission = AsyncMock(return_value=True)
    handler.send_permission_denied = AsyncMock()
    return handler


async def test_data_management_menu_renders_backup_and_restore_actions(monkeypatch) -> None:
    update = _build_callback_update("admin_data_management")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_data_management_handler(db)

    monkeypatch.setattr(data_management_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_management_handler, "t", _fake_t)

    result = await handler.data_management_menu(update, context)

    assert result == ADMIN_MENU
    reply_markup = update.callback_query.edit_message_text.await_args.kwargs["reply_markup"]
    callback_data = [
        button.callback_data
        for row in reply_markup.inline_keyboard
        for button in row
    ]
    assert "admin_create_backup" in callback_data
    assert "restore_backup" in callback_data
    assert "admin_auto_backup_menu" in callback_data
    assert "admin_menu_return" in callback_data


async def test_data_management_create_backup_sends_file_and_back_button(
    monkeypatch,
    tmp_path: Path,
) -> None:
    update = _build_callback_update("admin_create_backup")
    context = _build_context()
    backup_file = tmp_path / "codm-backup.zip"
    backup_file.write_bytes(b"backup")

    db = SimpleNamespace(settings=SimpleNamespace(set_setting=AsyncMock()))
    handler = _new_data_management_handler(db)
    setattr(
        handler,
        "_get_scheduler",
        AsyncMock(
        return_value=SimpleNamespace(
            backup_manager=SimpleNamespace(
                create_full_backup=AsyncMock(return_value=str(backup_file))
            )
        )
        ),
    )

    monkeypatch.setattr(data_management_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_management_handler, "t", _fake_t)

    result = await handler.create_backup(update, context)

    assert result == ADMIN_MENU
    update.callback_query.answer.assert_awaited_once_with("admin.backup.processing")
    update.callback_query.edit_message_text.assert_awaited_once_with("admin.backup.processing")
    db.settings.set_setting.assert_awaited_once()
    update.callback_query.message.reply_document.assert_awaited_once()
    reply_call = update.callback_query.message.reply_document.await_args.kwargs
    assert reply_call["filename"] == "codm-backup.zip"
    update.callback_query.message.delete.assert_awaited_once()
    context.bot.send_message.assert_awaited_once()
    reply_markup = context.bot.send_message.await_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "admin_data_management"


async def test_data_management_create_backup_denied_uses_permission_contract(
    monkeypatch,
) -> None:
    update = _build_callback_update("admin_create_backup")
    context = _build_context()
    db = SimpleNamespace(settings=SimpleNamespace(set_setting=AsyncMock()))
    handler = _new_data_management_handler(db)
    handler.role_manager.has_permission = AsyncMock(return_value=False)
    handler.role_manager.is_super_admin = AsyncMock(return_value=False)

    monkeypatch.setattr(data_management_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_management_handler, "t", _fake_t)

    result = await handler.create_backup(update, context)

    assert result == ADMIN_MENU
    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="admin_create_backup",
        permission=data_management_handler.Permission.BACKUP_DATA,
        source="create_backup",
    )
    update.callback_query.answer.assert_not_awaited()


async def test_health_fix_issues_menu_exposes_backup_and_restore_actions(monkeypatch) -> None:
    update = _build_callback_update("health_fix_issues_menu")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)
    safe_edit = AsyncMock()

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report, "safe_edit_message_text", safe_edit)

    await handler.fix_issues_menu(update, context)

    update.callback_query.answer.assert_awaited_once()
    assert safe_edit.await_args is not None
    safe_call = safe_edit.await_args.kwargs
    reply_markup = safe_call["reply_markup"]
    callback_data = [
        button.callback_data
        for row in reply_markup.inline_keyboard
        for button in row
    ]
    assert "health_create_backup" in callback_data
    assert "health_restore_backup" in callback_data
    assert "health_data_health" in callback_data


async def test_health_fix_issues_menu_denied_uses_permission_contract(monkeypatch) -> None:
    update = _build_callback_update("health_fix_issues_menu")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)
    handler.check_permission = AsyncMock(return_value=False)

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    await handler.fix_issues_menu(update, context)

    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="health_fix_issues_menu",
        permission=data_health_report.Permission.MANAGE_SETTINGS,
        source="data_health_report.fix_issues_menu",
    )


async def test_health_create_backup_sends_file_and_returns_fix_menu(
    monkeypatch,
    tmp_path: Path,
) -> None:
    update = _build_callback_update("health_create_backup")
    context = _build_context()
    backup_file = tmp_path / "health-backup.zip"
    backup_file.write_bytes(b"backup")

    db = SimpleNamespace(
        settings=SimpleNamespace(
            backup_database=AsyncMock(return_value=str(backup_file))
        )
    )
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    safe_edit = AsyncMock()

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report, "safe_edit_message_text", safe_edit)

    await handler.create_backup(update, context)

    update.callback_query.answer.assert_awaited_once_with("admin.health.backup.start")
    context.bot.send_document.assert_awaited_once()
    send_call = context.bot.send_document.await_args.kwargs
    assert send_call["filename"] == "health-backup.zip"
    assert not backup_file.exists()
    assert safe_edit.await_args is not None
    reply_markup = safe_edit.await_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_create_backup_denied_uses_permission_contract(monkeypatch) -> None:
    update = _build_callback_update("health_create_backup")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)
    handler.check_permission = AsyncMock(return_value=False)

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    await handler.create_backup(update, context)

    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="health_create_backup",
        permission=data_health_report.Permission.MANAGE_SETTINGS,
        source="data_health_report.create_backup",
    )


async def test_health_restore_backup_start_sets_expected_state(monkeypatch) -> None:
    update = _build_callback_update("health_restore_backup")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)
    safe_edit = AsyncMock()

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report, "safe_edit_message_text", safe_edit)

    result = await handler.restore_backup_start(update, context)

    assert result == AWAITING_BACKUP_FILE
    update.callback_query.answer.assert_awaited_once()
    assert safe_edit.await_args is not None
    reply_markup = safe_edit.await_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_start_denied_uses_permission_contract(monkeypatch) -> None:
    update = _build_callback_update("health_restore_backup")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)
    handler.check_permission = AsyncMock(return_value=False)

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_start(update, context)

    assert result == ADMIN_MENU
    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="health_restore_backup",
        permission=data_health_report.Permission.MANAGE_SETTINGS,
        source="data_health_report.restore_backup_start",
    )


async def test_health_restore_backup_start_without_callback_falls_back_to_bot(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        effective_chat=SimpleNamespace(id=2002),
        callback_query=None,
    )
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db)

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_start(update, context)

    assert result == AWAITING_BACKUP_FILE
    send_args = context.bot.send_message.await_args
    assert send_args is not None
    assert send_args.args[0] == 2002
    assert "admin.health.restore.start.title" in send_args.args[1]
    assert send_args.kwargs["parse_mode"] == ParseMode.HTML
    assert send_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_rejects_invalid_postgres_extension(monkeypatch) -> None:
    update = _build_message_update("bad.txt")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == AWAITING_BACKUP_FILE
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.invalid_format\nadmin.health.restore.start.cancel"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_denied_uses_permission_contract(monkeypatch) -> None:
    update = _build_message_update("restore.sql")
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    handler.check_permission = AsyncMock(return_value=False)

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="health_restore_backup_file",
        permission=data_health_report.Permission.MANAGE_SETTINGS,
        source="data_health_report.restore_backup_file",
    )


async def test_health_restore_backup_file_without_message_reprompts_via_bot(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        effective_chat=SimpleNamespace(id=2002),
        message=None,
    )
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == AWAITING_BACKUP_FILE
    context.bot.send_message.assert_awaited_once_with(
        2002,
        "admin.health.restore.file_required\nadmin.health.restore.start.cancel",
    )


async def test_health_restore_backup_file_without_document_reprompts_via_message(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        message=SimpleNamespace(document=None, reply_text=AsyncMock()),
    )
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == AWAITING_BACKUP_FILE
    update.message.reply_text.assert_awaited_once_with(
        "admin.health.restore.file_required\nadmin.health.restore.start.cancel",
    )


async def test_health_restore_backup_file_without_file_name_reprompts_via_message(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        message=SimpleNamespace(
            document=SimpleNamespace(file_name="", file_id="tg-missing-name"),
            reply_text=AsyncMock(),
        ),
    )
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == AWAITING_BACKUP_FILE
    update.message.reply_text.assert_awaited_once()
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.file_required\nadmin.health.restore.start.cancel"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_without_file_id_reprompts_via_message(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        message=SimpleNamespace(
            document=SimpleNamespace(file_name="restore.sql", file_id=""),
            reply_text=AsyncMock(),
        ),
    )
    context = _build_context()
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == AWAITING_BACKUP_FILE
    update.message.reply_text.assert_awaited_once()
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.file_required\nadmin.health.restore.start.cancel"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_error_without_reply_text_falls_back_to_bot(monkeypatch) -> None:
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1001),
        effective_chat=SimpleNamespace(id=2002),
        message=SimpleNamespace(
            document=SimpleNamespace(file_name="restore.sql", file_id="tg-fallback-error"),
        ),
    )
    context = _build_context()
    context.bot.get_file = AsyncMock(side_effect=RuntimeError("ConnectError: telegram unavailable"))
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    send_args = context.bot.send_message.await_args
    assert send_args is not None
    assert send_args.args[0] == 2002
    assert send_args.args[1] == "admin.health.restore.error"
    assert send_args.kwargs["parse_mode"] == ParseMode.HTML
    assert send_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_postgres_success_uses_canonical_reply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_text("SELECT 1;", encoding="utf-8")

    update = _build_message_update("restore.sql", file_id="tg-sql")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.sql",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    setattr(handler, "get_pg_tool_path", lambda tool_name: tool_name)

    captured: dict[str, object] = {}

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.subprocess, "run", _fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_USER", "db-user")
    monkeypatch.setenv("POSTGRES_DB", "db-name")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db-pass")
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    context.bot.get_file.assert_awaited_once_with("tg-sql")
    args = captured["args"]
    assert isinstance(args, list)
    assert args[:8] == ["psql", "-h", "db-host", "-U", "db-user", "-d", "db-name", "-f"]
    restore_path = Path(str(args[8]))
    assert restore_path.parent == tmp_path
    assert restore_path.name.startswith("restore_")
    assert restore_path.suffix == ".sql"
    assert not restore_path.exists()
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PGPASSWORD"] == "db-pass"
    update.message.reply_text.assert_awaited_once()
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    reply_markup = reply_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "health_fix_issues_menu"
    assert reply_args.args[0] == "admin.health.restore.success.title\n\nadmin.health.restore.success.restart"


async def test_health_restore_backup_file_postgres_partial_success_is_handled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_text("SELECT 1;", encoding="utf-8")

    update = _build_message_update("restore.sql", file_id="tg-partial")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.sql",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    setattr(handler, "get_pg_tool_path", lambda tool_name: tool_name)

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stderr="relation already exists")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.subprocess, "run", _fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_USER", "db-user")
    monkeypatch.setenv("POSTGRES_DB", "db-name")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db-pass")
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    update.message.reply_text.assert_awaited_once()
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    reply_markup = reply_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "health_fix_issues_menu"
    assert (
        reply_args.args[0]
        == "admin.health.restore.partial_success\n\nadmin.health.restore.success.restart"
    )



async def test_health_restore_backup_file_zip_dump_uses_pg_restore(
    monkeypatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "restore.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/backup.dump", b"dump-bytes")

    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_bytes(archive_path.read_bytes())

    update = _build_message_update("restore.zip", file_id="tg-zip")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.zip",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    setattr(handler, "get_pg_tool_path", lambda tool_name: tool_name)

    captured: dict[str, object] = {}

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.subprocess, "run", _fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_USER", "db-user")
    monkeypatch.setenv("POSTGRES_DB", "db-name")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db-pass")
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    args = captured["args"]
    assert isinstance(args, list)
    assert args[:9] == [
        "pg_restore",
        "-h",
        "db-host",
        "-U",
        "db-user",
        "-d",
        "db-name",
        "--clean",
        "--no-owner",
    ]
    restore_path = Path(str(args[9]))
    assert restore_path.suffix == ".dump"
    assert restore_path.name == "backup.dump"
    assert not restore_path.exists()
    assert not list(tmp_path.glob("extract_*"))
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_sqlite_success_creates_safety_backup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    sqlite_db = tmp_path / "codm.sqlite3"
    sqlite_db.write_bytes(b"original-db")

    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_bytes(b"restored-db")

    update = _build_message_update("restore.db", file_id="tg-sqlite")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.db",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path=str(sqlite_db))

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    assert sqlite_db.read_bytes() == b"restored-db"
    safety_backups = list(tmp_path.glob("codm.sqlite3.before_restore_*.bak"))
    assert len(safety_backups) == 1
    assert safety_backups[0].read_bytes() == b"original-db"
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"
    assert (
        reply_args.args[0]
        == "admin.health.restore.success.title\n\nadmin.health.restore.success.safety_backup\n\nadmin.health.restore.success.restart"
    )


async def test_health_restore_backup_file_handles_get_file_connect_error(
    monkeypatch,
) -> None:
    update = _build_message_update("restore.sql", file_id="tg-get-file-error")
    context = _build_context()
    context.bot.get_file = AsyncMock(side_effect=RuntimeError("ConnectError: telegram unavailable"))
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_zip_without_backup_payload_returns_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "restore-empty.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("notes/readme.txt", b"no backup here")

    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_bytes(archive_path.read_bytes())

    update = _build_message_update("restore.zip", file_id="tg-empty-zip")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore-empty.zip",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_zip_with_multiple_payloads_returns_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "restore-multi.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("one.dump", b"dump-1")
        archive.writestr("two.sql", b"SELECT 1;")

    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_bytes(archive_path.read_bytes())

    update = _build_message_update("restore.zip", file_id="tg-multi-zip")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore-multi.zip",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_invalid_zip_returns_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    broken_zip_path = tmp_path / "restore-broken.zip"
    broken_zip_path.write_bytes(b"not-a-real-zip")

    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_bytes(broken_zip_path.read_bytes())

    update = _build_message_update("restore.zip", file_id="tg-bad-zip")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore-broken.zip",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_handles_download_connect_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    update = _build_message_update("restore.sql", file_id="tg-download-error")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.sql",
            download_to_drive=AsyncMock(side_effect=RuntimeError("ConnectError: download failed")),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_health_restore_backup_file_handles_subprocess_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    async def _download_to_drive(destination: str) -> None:
        Path(destination).write_text("SELECT 1;", encoding="utf-8")

    update = _build_message_update("restore.sql", file_id="tg-subprocess-error")
    context = _build_context()
    context.bot.get_file = AsyncMock(
        return_value=SimpleNamespace(
            file_path="telegram/restore.sql",
            download_to_drive=AsyncMock(side_effect=_download_to_drive),
        )
    )
    db = SimpleNamespace()
    handler = _new_health_handler(db, db_path="postgresql://stub/db")
    setattr(handler, "get_pg_tool_path", lambda tool_name: tool_name)

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stderr="fatal restore failure")

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report.subprocess, "run", _fake_run)
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_USER", "db-user")
    monkeypatch.setenv("POSTGRES_DB", "db-name")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db-pass")
    monkeypatch.setattr(data_health_report.tempfile, "gettempdir", lambda: str(tmp_path))

    result = await handler.restore_backup_file(update, context)

    assert result == ADMIN_MENU
    reply_args = update.message.reply_text.await_args
    assert reply_args is not None
    assert reply_args.args[0] == "admin.health.restore.error"
    assert reply_args.kwargs["parse_mode"] == ParseMode.HTML
    assert reply_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_fix_issues_menu"


async def test_run_health_check_success_sends_report_and_updates_message(
    monkeypatch,
    tmp_path: Path,
) -> None:
    update = _build_callback_update("health_run_check")
    context = _build_context()
    report_path = tmp_path / "health-report.html"
    report_path.write_text("report", encoding="utf-8")
    handler = _new_health_handler(SimpleNamespace())
    handler.health_checker = SimpleNamespace(
        run_full_check=AsyncMock(
            return_value={
                "health_score": 82.5,
                "critical_count": 1,
                "warning_count": 2,
                "info_count": 3,
                "report_path": str(report_path),
            }
        )
    )
    safe_edit = AsyncMock()

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report, "safe_edit_message_text", safe_edit)

    await handler.run_health_check(update, context)

    update.callback_query.answer.assert_awaited_once_with("admin.health.run.start")
    handler.health_checker.run_full_check.assert_awaited_once_with(save_to_db=True)
    assert safe_edit.await_count == 2
    progress_call = safe_edit.await_args_list[0]
    final_call = safe_edit.await_args_list[1]
    assert progress_call.args[1] == "admin.health.run.progress"
    assert "admin.health.run.completed.title" in final_call.args[1]
    assert "admin.health.run.completed.saved" in final_call.args[1]
    assert final_call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_data_health"
    context.bot.send_document.assert_awaited_once()
    send_call = context.bot.send_document.await_args
    assert send_call is not None
    assert send_call.kwargs["filename"] == "health-report.html"
    assert send_call.kwargs["caption"] == "admin.health.run.report_caption"


async def test_run_health_check_error_updates_message_without_report(monkeypatch) -> None:
    update = _build_callback_update("health_run_check")
    context = _build_context()
    handler = _new_health_handler(SimpleNamespace())
    handler.health_checker = SimpleNamespace(
        run_full_check=AsyncMock(side_effect=RuntimeError("health checker boom"))
    )
    safe_edit = AsyncMock()

    monkeypatch.setattr(data_health_report, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(data_health_report, "t", _fake_t)
    monkeypatch.setattr(data_health_report, "safe_edit_message_text", safe_edit)

    await handler.run_health_check(update, context)

    update.callback_query.answer.assert_awaited_once_with("admin.health.run.start")
    handler.health_checker.run_full_check.assert_awaited_once_with(save_to_db=True)
    assert safe_edit.await_count == 2
    final_call = safe_edit.await_args_list[1]
    assert final_call.args[1] == "admin.health.run.error"
    assert final_call.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "health_data_health"
    context.bot.send_document.assert_not_awaited()




