from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from handlers.admin.admin_states import ADMIN_MENU
from core.database.repositories.user_repository import UserRepository
from core.security.role_manager import Permission
from telegram.ext import ConversationHandler

import handlers.admin.admin_handlers_modular as admin_handlers_modular
import handlers.admin.admin_entry_flow as admin_entry_flow
import handlers.admin.modules.system.admin_management as admin_management_module
import handlers.admin.modules.system.import_export as import_export_module
import handlers.admin.modules.system.notification_handler as notification_handler_module
import handlers.admin.modules.system.stats_backup as stats_backup_module
import handlers.admin.modules.system.user_management as user_management_module
import handlers.admin.modules.content.category_handler as category_handler_module
import handlers.admin.modules.content.cms_handler as cms_handler_module
import handlers.admin.modules.support.direct_contact_handler as direct_contact_handler_module
import handlers.admin.modules.support.faq_handler as faq_handler_module
import handlers.admin.modules.support.ticket_handler as ticket_handler_module
import handlers.channel.channel_handlers as channel_handlers
import handlers.channel.add_handlers as channel_add_actions
import handlers.channel.delete_handlers as channel_delete_actions
import handlers.channel.stats_handlers as channel_stats_handlers
import handlers.admin.user_attachments_admin.reports_handler as reports_handler
import handlers.admin.user_attachments_admin.review_handler as review_handler
from handlers.admin.user_attachments_admin.permissions import (
    has_manage_user_attachments_permission,
)


class _AsyncTx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _TxRecorder:
    def __init__(self, conn):
        self.conn = conn
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit_count += 1
        else:
            self.rollback_count += 1
        return False


class _CursorRecorder:
    def __init__(self, *, fetchone_values=None, execute_side_effect=None, rowcount: int = 1):
        self.execute = AsyncMock(side_effect=execute_side_effect)
        self.fetchone = AsyncMock(side_effect=fetchone_values)
        self.fetchall = AsyncMock(return_value=[])
        self.close = AsyncMock()
        self.rowcount = rowcount

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_has_manage_user_attachments_permission_allows_super_admin() -> None:
    role_manager = Mock()
    role_manager.is_super_admin = AsyncMock(return_value=True)
    role_manager.has_permission = AsyncMock(return_value=False)
    db = SimpleNamespace(users=SimpleNamespace(is_admin=AsyncMock(return_value=False)))

    allowed = await has_manage_user_attachments_permission(
        101,
        db=db,
        role_manager=role_manager,
    )

    assert allowed is True
    role_manager.is_super_admin.assert_awaited_once_with(101)
    role_manager.has_permission.assert_not_called()
    db.users.is_admin.assert_not_called()


async def test_has_manage_user_attachments_permission_uses_granular_permission() -> None:
    role_manager = Mock()
    role_manager.is_super_admin = AsyncMock(return_value=False)
    role_manager.has_permission = AsyncMock(return_value=True)
    db = SimpleNamespace(users=SimpleNamespace(is_admin=AsyncMock(return_value=False)))

    allowed = await has_manage_user_attachments_permission(
        202,
        db=db,
        role_manager=role_manager,
    )

    assert allowed is True
    role_manager.is_super_admin.assert_awaited_once_with(202)
    role_manager.has_permission.assert_awaited_once()
    db.users.is_admin.assert_not_called()


async def test_has_manage_user_attachments_permission_falls_back_to_legacy_admin() -> None:
    role_manager = Mock()
    role_manager.is_super_admin = AsyncMock(side_effect=RuntimeError("rbac unavailable"))
    role_manager.has_permission = AsyncMock(return_value=False)
    db = SimpleNamespace(users=SimpleNamespace(is_admin=AsyncMock(return_value=True)))

    allowed = await has_manage_user_attachments_permission(
        303,
        db=db,
        role_manager=role_manager,
    )

    assert allowed is True
    db.users.is_admin.assert_awaited_once_with(303)


async def test_check_channel_management_permission_uses_role_manager() -> None:
    role_manager = Mock()
    role_manager.is_super_admin = AsyncMock(return_value=False)
    role_manager.has_permission = AsyncMock(return_value=True)
    context = SimpleNamespace(bot_data={"role_manager": role_manager})

    allowed = await channel_handlers.check_channel_management_permission(404, context)

    assert allowed is True
    role_manager.is_super_admin.assert_awaited_once_with(404)
    role_manager.has_permission.assert_awaited_once()


async def test_check_channel_management_permission_falls_back_to_db_admin() -> None:
    db = SimpleNamespace(users=SimpleNamespace(is_admin=AsyncMock(return_value=True)))
    context = SimpleNamespace(bot_data={"database": db})

    allowed = await channel_handlers.check_channel_management_permission(505, context)

    assert allowed is True
    db.users.is_admin.assert_awaited_once_with(505)


async def test_check_channel_management_permission_falls_back_to_super_admin_id(monkeypatch) -> None:
    import config

    monkeypatch.setattr(config, "SUPER_ADMIN_ID", 606, raising=False)
    context = SimpleNamespace(bot_data={})

    assert await channel_handlers.check_channel_management_permission(606, context) is True
    assert await channel_handlers.check_channel_management_permission(607, context) is False


async def test_channel_management_menu_blocks_unauthorized_user(monkeypatch) -> None:
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        message=None,
        effective_user=SimpleNamespace(id=707),
    )
    context = SimpleNamespace(bot_data={"database": Mock()})
    audit_deny = AsyncMock()

    monkeypatch.setattr(
        channel_handlers,
        "check_channel_management_permission",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(channel_handlers, "audit_channel_permission_denied", audit_deny)
    monkeypatch.setattr(channel_handlers, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_handlers, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.channel_management_menu(update, context)

    assert result == ConversationHandler.END
    audit_deny.assert_awaited_once_with(707)
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_has_manage_user_attachments_permission_logs_denied_decision() -> None:
    role_manager = Mock()
    role_manager.is_super_admin = AsyncMock(return_value=False)
    role_manager.has_permission = AsyncMock(return_value=False)
    db = SimpleNamespace(users=SimpleNamespace(is_admin=AsyncMock(return_value=False)))
    audit_logger = Mock()
    audit_logger.log_permission_decision = AsyncMock()

    allowed = await has_manage_user_attachments_permission(
        304,
        db=db,
        role_manager=role_manager,
        audit_logger=audit_logger,
        route="ua_admin_reports",
        source="reports_handler",
    )

    assert allowed is False
    audit_logger.log_permission_decision.assert_awaited_once()
    assert audit_logger.log_permission_decision.await_args.kwargs["allowed"] is False
    assert audit_logger.log_permission_decision.await_args.kwargs["route"] == "ua_admin_reports"


async def test_import_start_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(import_export_module.ImportExportHandler)
    handler.role_manager = SimpleNamespace(get_user_permissions=AsyncMock(return_value=[]))
    handler.audit_permission_denied = AsyncMock()
    update = SimpleNamespace(
        callback_query=SimpleNamespace(
            from_user=SimpleNamespace(id=8080),
            answer=AsyncMock(),
        )
    )
    context = SimpleNamespace()

    result = await handler.import_start(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        8080,
        route="admin_import_start",
        permission=Permission.IMPORT_EXPORT,
        source="import_start",
    )
    assert update.callback_query.answer.await_count == 2


async def test_admin_start_msg_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(admin_handlers_modular.AdminHandlers)
    handler.db = SimpleNamespace()
    handler.is_admin = AsyncMock(return_value=False)
    handler.audit_permission_denied = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=9090, username=None, first_name="Denied"),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace()

    monkeypatch.setattr(admin_entry_flow, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(admin_entry_flow, "t", lambda key, lang, **kwargs: key)

    result = await handler.admin_start_msg(update, context)

    assert result == ConversationHandler.END
    handler.audit_permission_denied.assert_awaited_once_with(
        9090,
        route="admin_start_msg",
        permission="ADMIN_ACCESS",
        source="admin_start_msg",
    )
    update.message.reply_text.assert_awaited_once_with("admin.not_admin")


async def test_notify_home_menu_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(notification_handler_module.NotificationHandler)
    handler.role_manager = SimpleNamespace(
        get_user_permissions=AsyncMock(return_value=[]),
        is_super_admin=AsyncMock(return_value=False),
    )
    handler.db = SimpleNamespace()
    handler.audit_permission_denied = AsyncMock()
    query = SimpleNamespace(from_user=SimpleNamespace(id=9101), answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace()

    monkeypatch.setattr(notification_handler_module, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(notification_handler_module, "t", lambda key, lang, **kwargs: key)

    result = await handler.notify_home_menu(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        9101,
        route="admin_notify_home",
        permission=Permission.SEND_NOTIFICATIONS,
        source="notify_home_menu",
    )
    assert query.answer.await_count == 2
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_admin_tickets_menu_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(ticket_handler_module.TicketHandler)
    handler.role_manager = SimpleNamespace(has_permission=AsyncMock(return_value=False))
    handler.db = SimpleNamespace()
    handler.audit_permission_denied = AsyncMock()
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=9102, username=None, first_name="TicketDenied"),
    )
    context = SimpleNamespace()
    safe_edit = AsyncMock()

    monkeypatch.setattr(ticket_handler_module, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(ticket_handler_module, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(ticket_handler_module, "safe_edit_message_text", safe_edit)

    result = await handler.admin_tickets_menu(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        9102,
        route="admin_tickets_menu",
        permission=Permission.MANAGE_TICKETS,
        source="admin_tickets_menu",
    )
    safe_edit.assert_awaited_once_with(query, "common.no_permission")


async def test_admin_faqs_menu_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(faq_handler_module.FAQHandler)
    handler.role_manager = SimpleNamespace(has_permission=AsyncMock(return_value=False))
    handler.db = SimpleNamespace()
    handler.audit_permission_denied = AsyncMock()
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=9103, username=None, first_name="FaqDenied"),
    )
    context = SimpleNamespace(user_data={})

    monkeypatch.setattr(faq_handler_module, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(faq_handler_module, "t", lambda key, lang, **kwargs: key)

    result = await handler.admin_faqs_menu(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        9103,
        route="admin_faqs_menu",
        permission=Permission.MANAGE_FAQS,
        source="admin_faqs_menu",
    )
    query.edit_message_text.assert_awaited_once_with("common.no_permission")


async def test_manage_admins_menu_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(admin_management_module.AdminManagementHandler)
    handler.role_manager = SimpleNamespace(is_super_admin=AsyncMock(return_value=False))
    handler.db = SimpleNamespace()
    handler.audit_permission_denied = AsyncMock()
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=9104))
    context = SimpleNamespace(user_data={})
    safe_edit = AsyncMock()

    monkeypatch.setattr(admin_management_module, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(admin_management_module, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(admin_management_module, "safe_edit_message_text", safe_edit)

    result = await handler.manage_admins_menu(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        9104,
        route="manage_admins_menu",
        permission="SUPER_ADMIN",
        source="manage_admins_menu",
    )
    safe_edit.assert_awaited_once_with(query, "common.no_permission", parse_mode="Markdown")


async def test_direct_contact_menu_denied_records_permission_audit_via_decorator() -> None:
    handler = object.__new__(direct_contact_handler_module.DirectContactHandler)
    handler.role_manager = SimpleNamespace(
        is_admin=AsyncMock(return_value=True),
        get_user_permissions=AsyncMock(return_value=[]),
        is_super_admin=AsyncMock(return_value=False),
    )
    handler.audit_permission_denied = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=9105),
        callback_query=SimpleNamespace(answer=AsyncMock()),
    )
    context = SimpleNamespace()

    result = await handler.admin_direct_contact_menu(update, context)

    assert result is None
    handler.audit_permission_denied.assert_awaited_once_with(
        9105,
        route="admin_direct_contact_menu",
        permission=Permission.MANAGE_SETTINGS.value,
        reason="permission_denied",
        source="admin_direct_contact_menu",
    )


async def test_category_menu_denied_records_permission_audit_via_decorator() -> None:
    handler = object.__new__(category_handler_module.CategoryHandler)
    handler.role_manager = SimpleNamespace(
        is_admin=AsyncMock(return_value=True),
        get_user_permissions=AsyncMock(return_value=[]),
        is_super_admin=AsyncMock(return_value=False),
    )
    handler.audit_permission_denied = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=9106),
        callback_query=SimpleNamespace(answer=AsyncMock()),
    )
    context = SimpleNamespace()

    result = await handler.category_mgmt_menu(update, context)

    assert result is None
    handler.audit_permission_denied.assert_awaited_once_with(
        9106,
        route="category_mgmt_menu",
        permission=Permission.MANAGE_CATEGORIES.value,
        reason="permission_denied",
        source="category_mgmt_menu",
    )


async def test_stats_backup_denied_records_permission_audit(monkeypatch) -> None:
    handler = object.__new__(stats_backup_module.StatsBackupHandler)
    handler.role_manager = SimpleNamespace(get_user_permissions=AsyncMock(return_value=[]))
    handler.audit_permission_denied = AsyncMock()
    handler.db = SimpleNamespace()
    query = SimpleNamespace(from_user=SimpleNamespace(id=9107), answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace()

    monkeypatch.setattr(stats_backup_module, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(stats_backup_module, "t", lambda key, lang, **kwargs: key)

    result = await handler.create_backup(update, context)

    assert result == ADMIN_MENU
    handler.audit_permission_denied.assert_awaited_once_with(
        9107,
        route="stats_backup_create_backup",
        permission=Permission.BACKUP_DATA,
        source="create_backup",
    )


async def test_user_mgmt_menu_denied_uses_explicit_route(monkeypatch) -> None:
    handler = object.__new__(user_management_module.UserManagementHandler)
    handler.check_permission = AsyncMock(return_value=False)
    handler.role_manager = SimpleNamespace(is_super_admin=AsyncMock(return_value=False))
    handler.send_permission_denied = AsyncMock()
    handler.db = SimpleNamespace()
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=9108))
    context = SimpleNamespace(user_data={})

    monkeypatch.setattr(user_management_module, "get_user_lang", AsyncMock(return_value="fa"))

    result = await handler.user_mgmt_menu(update, context)

    assert result == ADMIN_MENU
    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="user_mgmt_menu",
        permission=Permission.MANAGE_USERS,
        source="user_mgmt_menu",
    )


async def test_cms_menu_denied_uses_explicit_route(monkeypatch) -> None:
    handler = object.__new__(cms_handler_module.CMSHandler)
    handler.check_permission = AsyncMock(return_value=False)
    handler.send_permission_denied = AsyncMock()
    handler.db = SimpleNamespace()
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=9109))
    context = SimpleNamespace()

    monkeypatch.setattr(cms_handler_module, "get_user_lang", AsyncMock(return_value="fa"))

    result = await handler.cms_menu(update, context)

    assert result == ADMIN_MENU
    handler.send_permission_denied.assert_awaited_once_with(
        update,
        context,
        route="cms_menu",
        permission=Permission.MANAGE_TEXTS,
        source="cms_menu",
    )


async def test_channel_management_menu_renders_for_authorized_user(monkeypatch) -> None:
    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        message=None,
        effective_user=SimpleNamespace(id=808),
    )
    db = SimpleNamespace(cms=SimpleNamespace(get_required_channels=AsyncMock(return_value=[])))
    context = SimpleNamespace(bot_data={"database": db})

    menu_edit = AsyncMock()
    monkeypatch.setattr(
        channel_handlers,
        "check_channel_management_permission",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(channel_handlers, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_handlers, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(channel_handlers, "safe_edit_message_text", menu_edit)

    result = await channel_handlers.channel_management_menu(update, context)

    assert result == channel_handlers.CHANNEL_MENU
    query.answer.assert_awaited_once_with()
    db.cms.get_required_channels.assert_awaited_once_with()
    menu_edit.assert_awaited_once()
    assert menu_edit.await_args is not None
    rendered_message = menu_edit.await_args.args[1]
    assert "admin.channels.menu.empty" in rendered_message


async def test_save_channel_confirm_persists_channel_and_clears_temp_state(monkeypatch) -> None:
    import managers.channel_manager as channel_manager

    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=811),
    )
    db = SimpleNamespace(cms=SimpleNamespace(add_required_channel=AsyncMock(return_value=True)))
    context = SimpleNamespace(
        bot_data={"database": db},
        user_data={
            "temp_channel": {
                "channel_id": "-10011",
                "display_title": "Channel A",
                "url": "https://t.me/channel_a",
            }
        },
    )

    class _Analytics:
        track_channel_added = AsyncMock()

    menu_edit = AsyncMock()

    monkeypatch.setattr(channel_add_actions, "Analytics", _Analytics)
    monkeypatch.setattr(channel_manager, "invalidate_all_cache", lambda: 0)
    monkeypatch.setattr(channel_add_actions, "safe_edit_message_text", menu_edit)
    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.save_channel_confirm(update, context)

    assert result == channel_handlers.CHANNEL_MENU
    db.cms.add_required_channel.assert_awaited_once_with(
        channel_id="-10011",
        title="Channel A",
        url="https://t.me/channel_a",
    )
    _Analytics.track_channel_added.assert_awaited_once()
    menu_edit.assert_awaited_once()
    assert "temp_channel" not in context.user_data


async def test_delete_channel_execute_requires_selected_channel(monkeypatch) -> None:
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=822),
    )
    db = SimpleNamespace(cms=SimpleNamespace(remove_required_channel=AsyncMock(return_value=True)))
    context = SimpleNamespace(bot_data={"database": db}, user_data={})

    monkeypatch.setattr(channel_delete_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_delete_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.delete_channel_execute(update, context)

    assert result == ConversationHandler.END
    assert query.answer.await_count == 2
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.cms.remove_required_channel.assert_not_called()
    query.edit_message_text.assert_not_called()


async def test_delete_channel_execute_removes_channel_and_returns_menu(monkeypatch) -> None:
    import managers.channel_manager as channel_manager

    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=833),
    )
    db = SimpleNamespace(cms=SimpleNamespace(remove_required_channel=AsyncMock(return_value=True)))
    context = SimpleNamespace(
        bot_data={"database": db},
        user_data={"deleting_channel_id": "-10022"},
    )

    class _Analytics:
        track_channel_removed = AsyncMock()

    monkeypatch.setattr(channel_delete_actions, "Analytics", _Analytics)
    monkeypatch.setattr(channel_manager, "invalidate_all_cache", lambda: 0)
    monkeypatch.setattr(channel_delete_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_delete_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.delete_channel_execute(update, context)

    assert result == channel_handlers.CHANNEL_MENU
    db.cms.remove_required_channel.assert_awaited_once_with("-10022")
    _Analytics.track_channel_removed.assert_awaited_once_with(
        channel_id="-10022",
        admin_id=833,
    )
    query.edit_message_text.assert_awaited_once()
    assert "deleting_channel_id" not in context.user_data


async def test_handle_move_channel_rejects_invalid_operation(monkeypatch) -> None:
    query = SimpleNamespace(data="bad", answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(bot_data={"database": Mock()})

    monkeypatch.setattr(channel_handlers, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_handlers, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.handle_move_channel(update, context)

    assert result == channel_handlers.REORDER_CHANNELS
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_handle_move_channel_moves_up_and_refreshes_menu(monkeypatch) -> None:
    import managers.channel_manager as channel_manager

    query = SimpleNamespace(data="move_up_-10033", answer=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    db = SimpleNamespace(cms=SimpleNamespace(move_channel_up=AsyncMock(return_value=True)))
    context = SimpleNamespace(bot_data={"database": db})

    reorder_menu = AsyncMock(return_value=channel_handlers.REORDER_CHANNELS)
    monkeypatch.setattr(channel_handlers, "reorder_channels_menu", reorder_menu)
    monkeypatch.setattr(channel_manager, "invalidate_all_cache", lambda: 0)
    monkeypatch.setattr(channel_handlers, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_handlers, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.handle_move_channel(update, context)

    assert result == channel_handlers.REORDER_CHANNELS
    db.cms.move_channel_up.assert_awaited_once_with("-10033")
    query.answer.assert_awaited_once()
    reorder_menu.assert_awaited_once_with(update, context)


async def test_add_channel_id_rejects_invalid_input(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="invalid", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=901),
    )
    context = SimpleNamespace(bot_data={"database": Mock()}, user_data={}, bot=SimpleNamespace(get_chat=AsyncMock()))

    monkeypatch.setattr("utils.validators.validate_channel_id", lambda _: (False, "invalid channel id"))
    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.add_channel_id(update, context)

    assert result == channel_handlers.ADD_CHANNEL_ID
    update.message.reply_text.assert_awaited_once()
    sent_text = update.message.reply_text.await_args.args[0]
    assert "invalid channel id" in sent_text
    context.bot.get_chat.assert_not_called()


async def test_add_channel_id_accepts_valid_channel_and_moves_to_title(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="https://t.me/mychannel", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=902),
    )
    fake_chat = SimpleNamespace(title="My Channel", id=-100555)
    context = SimpleNamespace(
        bot_data={"database": Mock()},
        user_data={},
        bot=SimpleNamespace(get_chat=AsyncMock(return_value=fake_chat)),
    )

    monkeypatch.setattr("utils.validators.validate_channel_id", lambda value: (True, value))
    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.add_channel_id(update, context)

    assert result == channel_handlers.ADD_CHANNEL_TITLE
    context.bot.get_chat.assert_awaited_once_with("@mychannel")
    assert context.user_data["temp_channel"]["channel_id"] == "-100555"
    assert context.user_data["temp_channel"]["title"] == "My Channel"
    update.message.reply_text.assert_awaited_once()


async def test_add_channel_id_handles_channel_access_error(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="@private_channel", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=903),
    )
    context = SimpleNamespace(
        bot_data={"database": Mock()},
        user_data={},
        bot=SimpleNamespace(get_chat=AsyncMock(side_effect=RuntimeError("forbidden"))),
    )

    monkeypatch.setattr("utils.validators.validate_channel_id", lambda value: (True, value))
    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.add_channel_id(update, context)

    assert result == channel_handlers.ADD_CHANNEL_ID
    context.bot.get_chat.assert_awaited_once_with("@private_channel")
    update.message.reply_text.assert_awaited_once()
    sent_text = update.message.reply_text.await_args.args[0]
    assert "admin.channels.errors.access_channel" in sent_text


async def test_add_channel_url_rejects_invalid_link(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="http://bad-link", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=904),
    )
    context = SimpleNamespace(
        bot_data={"database": Mock()},
        user_data={"temp_channel": {"channel_id": "-1007", "display_title": "T"}},
    )

    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.add_channel_url(update, context)

    assert result == channel_handlers.ADD_CHANNEL_URL
    update.message.reply_text.assert_awaited_once()
    assert update.message.reply_text.await_args.args[0] == "admin.channels.errors.invalid_link"


async def test_add_channel_url_accepts_valid_link_and_moves_to_confirm(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="https://t.me/ch_ok", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=905),
    )
    context = SimpleNamespace(
        bot_data={"database": Mock()},
        user_data={"temp_channel": {"channel_id": "-1008", "display_title": "Good Channel"}},
    )

    monkeypatch.setattr(channel_add_actions, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_add_actions, "t", lambda key, lang, **kwargs: key)

    result = await channel_handlers.add_channel_url(update, context)

    assert result == channel_handlers.ADD_CHANNEL_CONFIRM
    assert context.user_data["temp_channel"]["url"] == "https://t.me/ch_ok"
    update.message.reply_text.assert_awaited_once()
    sent_text = update.message.reply_text.await_args.args[0]
    assert "admin.channels.add.confirm.title" in sent_text


async def test_dismiss_report_blocks_unauthorized_admin(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_dismiss_11",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=909),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    db = Mock()
    db.transaction = Mock()
    cache = Mock()
    cache.invalidate = AsyncMock()
    show_reports = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=False))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.dismiss_report(update, context)

    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.transaction.assert_not_called()
    cache.invalidate.assert_not_called()
    show_reports.assert_not_called()


async def test_dismiss_report_uses_transaction_and_refreshes_state(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_dismiss_22",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1001),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    cursor = SimpleNamespace(
        execute=AsyncMock(),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))

    tx = _TxRecorder(conn)
    db = SimpleNamespace(transaction=Mock(return_value=tx))
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.dismiss_report(update, context)

    db.transaction.assert_called_once_with()
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    conn.cursor.assert_called_once()
    cursor.execute.assert_awaited_once()
    executed_sql = cursor.execute.await_args.args[0]
    assert "SET status = 'dismissed'" in executed_sql
    assert cursor.execute.await_args.args[1] == (1001, 22)
    cursor.close.assert_awaited_once_with()
    assert cache.invalidate.await_count == 2
    show_reports.assert_awaited_once_with(update, context)
    query.answer.assert_awaited_once()


async def test_dismiss_report_rolls_back_on_execute_error(monkeypatch) -> None:
    from utils.error_handler import error_handler

    query = SimpleNamespace(
        data="ua_admin_report_dismiss_23",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1002),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    cursor = SimpleNamespace(
        execute=AsyncMock(side_effect=RuntimeError("dismiss failed")),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)

    db = SimpleNamespace(transaction=Mock(return_value=tx))
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()
    handle_error = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(error_handler, "handle_telegram_error", handle_error)

    await reports_handler.dismiss_report(update, context)

    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    cache.invalidate.assert_not_called()
    show_reports.assert_not_called()
    handle_error.assert_awaited_once()


async def test_delete_reported_attachment_handles_missing_attachment(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_delete_70_71",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1301),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    cursor = SimpleNamespace(
        execute=AsyncMock(),
        fetchone=AsyncMock(return_value=None),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    db = SimpleNamespace(
        transaction=Mock(return_value=_AsyncTx(conn)),
        update_submission_stats=AsyncMock(),
        get_user_submission_stats=AsyncMock(),
        ban_user_from_submissions=AsyncMock(),
    )
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.delete_reported_attachment(update, context)

    db.transaction.assert_called_once_with()
    conn.cursor.assert_called_once()
    cursor.execute.assert_awaited_once()
    cursor.close.assert_awaited_once_with()
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.update_submission_stats.assert_not_called()
    db.get_user_submission_stats.assert_not_called()
    db.ban_user_from_submissions.assert_not_called()
    cache.invalidate.assert_not_called()
    context.bot.send_message.assert_not_called()
    show_reports.assert_not_called()


async def test_delete_reported_attachment_uses_transaction_and_notifies_owner(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_delete_33_44",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1101),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    cursor = SimpleNamespace(
        execute=AsyncMock(),
        fetchone=AsyncMock(
            side_effect=[
                {
                    "user_id": 4001,
                    "attachment_name": "Test Attachment",
                    "username": "u1",
                    "first_name": "User One",
                },
                {"strike_count": 1.0, "is_banned": False},
            ]
        ),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)

    db = SimpleNamespace(
        transaction=Mock(return_value=tx),
    )
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.delete_reported_attachment(update, context)

    db.transaction.assert_called_once_with()
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    conn.cursor.assert_called_once()
    assert cursor.execute.await_count == 5
    assert cache.invalidate.await_count == 2
    context.bot.send_message.assert_awaited_once()
    show_reports.assert_awaited_once_with(update, context)
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_delete_reported_attachment_rolls_back_on_write_error(monkeypatch) -> None:
    from utils.error_handler import error_handler

    query = SimpleNamespace(
        data="ua_admin_report_delete_33_44",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1102),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    execute = AsyncMock(side_effect=[None, RuntimeError("delete failed")])
    cursor = SimpleNamespace(
        execute=execute,
        fetchone=AsyncMock(
            return_value={
                "user_id": 4001,
                "attachment_name": "Test Attachment",
                "username": "u1",
                "first_name": "User One",
            }
        ),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    db = SimpleNamespace(transaction=Mock(return_value=tx))
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()
    handle_error = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(error_handler, "handle_telegram_error", handle_error)

    await reports_handler.delete_reported_attachment(update, context)

    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    cache.invalidate.assert_not_called()
    context.bot.send_message.assert_not_called()
    show_reports.assert_not_called()
    handle_error.assert_awaited_once()


async def test_warn_owner_about_report_uses_transaction_and_refreshes_list(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_warn_77_88",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1201),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    cursor = SimpleNamespace(
        execute=AsyncMock(),
        fetchone=AsyncMock(
            side_effect=[
                {
                    "attachment_name": "Warned Attachment",
                    "username": "u2",
                    "first_name": "User Two",
                },
                {"strike_count": 1.5, "is_banned": False},
            ]
        ),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)

    db = SimpleNamespace(
        transaction=Mock(return_value=tx),
    )
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.warn_owner_about_report(update, context)

    db.transaction.assert_called_once_with()
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    conn.cursor.assert_called_once()
    assert cursor.execute.await_count == 4
    assert cache.invalidate.await_count == 2
    context.bot.send_message.assert_awaited_once()
    show_reports.assert_awaited_once_with(update, context)
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_warn_owner_about_report_rolls_back_on_write_error(monkeypatch) -> None:
    from utils.error_handler import error_handler

    query = SimpleNamespace(
        data="ua_admin_report_warn_77_88",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1202),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    execute = AsyncMock(side_effect=[None, RuntimeError("warn failed")])
    cursor = SimpleNamespace(
        execute=execute,
        fetchone=AsyncMock(
            return_value={
                "attachment_name": "Warned Attachment",
                "username": "u2",
                "first_name": "User Two",
            }
        ),
        close=AsyncMock(),
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    db = SimpleNamespace(transaction=Mock(return_value=tx))
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_reports = AsyncMock()
    handle_error = AsyncMock()

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "cache", cache)
    monkeypatch.setattr(reports_handler, "show_reports_list", show_reports)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(error_handler, "handle_telegram_error", handle_error)

    await reports_handler.warn_owner_about_report(update, context)

    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    cache.invalidate.assert_not_called()
    context.bot.send_message.assert_not_called()
    show_reports.assert_not_called()
    handle_error.assert_awaited_once()


async def test_warn_owner_about_report_rejects_malformed_payload(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_report_warn_bad_payload",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1203),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    db = SimpleNamespace(transaction=Mock())

    monkeypatch.setattr(reports_handler, "db", db)
    monkeypatch.setattr(reports_handler, "has_ua_perm", AsyncMock(return_value=True))
    monkeypatch.setattr(reports_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(reports_handler, "t", lambda key, lang, **kwargs: key)

    await reports_handler.warn_owner_about_report(update, context)

    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.transaction.assert_not_called()
    context.bot.send_message.assert_not_called()


async def test_approve_attachment_uses_fallback_language_and_refreshes_pending(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_approve_55",
        answer=AsyncMock(),
        message=SimpleNamespace(delete=AsyncMock()),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2201),
    )
    attachment = {
        "id": 55,
        "status": "pending",
        "user_id": 4401,
        "mode": "mp",
        "weapon_name": "AK117",
        "name": "Red Dot",
    }
    db = SimpleNamespace(
        users=SimpleNamespace(
            get_user_attachment=AsyncMock(return_value=attachment),
            approve_user_attachment=AsyncMock(return_value=True),
            get_user_language=AsyncMock(side_effect=RuntimeError("lang unavailable")),
        ),
    )
    cache = SimpleNamespace(
        invalidate=AsyncMock(),
        get_paginated_count=AsyncMock(return_value=1),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
    )
    show_pending = AsyncMock()
    show_menu = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_pending_list", show_pending)
    monkeypatch.setattr(review_handler, "show_ua_admin_menu", show_menu)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: f"{key}:{lang}")

    await review_handler.approve_attachment(update, context)

    db.users.get_user_attachment.assert_awaited_once_with(55)
    db.users.approve_user_attachment.assert_awaited_once_with(55, 2201)
    assert cache.invalidate.await_count == 3
    cache.get_paginated_count.assert_awaited_once_with("pending")
    context.bot.send_message.assert_awaited_once()
    assert context.bot.send_message.await_args.kwargs["text"] == "user.ua.approved:fa"
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    query.message.delete.assert_awaited_once_with()
    assert context.user_data["temp_query_data"] == "ua_admin_pending"
    show_pending.assert_awaited_once_with(update, context)
    show_menu.assert_not_called()


async def test_approve_attachment_stops_before_side_effects_when_repo_approval_fails(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_approve_56",
        answer=AsyncMock(),
        message=SimpleNamespace(delete=AsyncMock()),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2204),
    )
    attachment = {
        "id": 56,
        "status": "pending",
        "user_id": 4402,
        "mode": "mp",
        "weapon_name": "DLQ33",
        "name": "Scope",
    }
    db = SimpleNamespace(
        users=SimpleNamespace(
            get_user_attachment=AsyncMock(return_value=attachment),
            approve_user_attachment=AsyncMock(return_value=False),
        ),
    )
    cache = SimpleNamespace(
        invalidate=AsyncMock(),
        get_paginated_count=AsyncMock(),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock()),
        user_data={},
    )
    show_pending = AsyncMock()
    show_menu = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_pending_list", show_pending)
    monkeypatch.setattr(review_handler, "show_ua_admin_menu", show_menu)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: f"{key}:{lang}")

    await review_handler.approve_attachment(update, context)

    db.users.get_user_attachment.assert_awaited_once_with(56)
    db.users.approve_user_attachment.assert_awaited_once_with(56, 2204)
    cache.invalidate.assert_not_called()
    cache.get_paginated_count.assert_not_called()
    context.bot.send_message.assert_not_called()
    query.message.delete.assert_not_called()
    show_pending.assert_not_called()
    show_menu.assert_not_called()
    assert "temp_query_data" not in context.user_data
    assert query.answer.await_count == 1
    assert query.answer.await_args.kwargs.get("show_alert") is True


async def test_approve_attachment_succeeds_even_if_notification_and_cache_fail(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_approve_57",
        answer=AsyncMock(),
        message=SimpleNamespace(delete=AsyncMock()),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2205),
    )
    attachment = {
        "id": 57,
        "status": "pending",
        "user_id": 4403,
        "mode": "br",
        "weapon_name": "Krig",
        "name": "Laser",
    }
    db = SimpleNamespace(
        users=SimpleNamespace(
            get_user_attachment=AsyncMock(return_value=attachment),
            approve_user_attachment=AsyncMock(return_value=True),
            get_user_language=AsyncMock(side_effect=RuntimeError("lang failed")),
        ),
    )
    cache = SimpleNamespace(
        invalidate=AsyncMock(side_effect=RuntimeError("cache failed")),
        get_paginated_count=AsyncMock(side_effect=RuntimeError("count failed")),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("notify failed"))),
        user_data={},
    )
    show_pending = AsyncMock()
    show_menu = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_pending_list", show_pending)
    monkeypatch.setattr(review_handler, "show_ua_admin_menu", show_menu)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: f"{key}:{lang}")

    await review_handler.approve_attachment(update, context)

    db.users.approve_user_attachment.assert_awaited_once_with(57, 2205)
    assert cache.invalidate.await_count == 3
    cache.get_paginated_count.assert_awaited_once_with("pending")
    context.bot.send_message.assert_awaited_once()
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    query.message.delete.assert_awaited_once_with()
    show_pending.assert_not_called()
    show_menu.assert_awaited_once_with(update, context)


async def test_user_repository_approve_user_attachment_commits_once() -> None:
    cursor = _CursorRecorder(fetchone_values=[{"user_id": 4401}])
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.approve_user_attachment(55, 2201)

    assert result is True
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    conn.cursor.assert_called_once_with()
    assert cursor.execute.await_count == 3


async def test_user_repository_approve_user_attachment_rolls_back_on_stats_write_error() -> None:
    cursor = _CursorRecorder(
        fetchone_values=[{"user_id": 4401}],
        execute_side_effect=[None, None, RuntimeError("stats update failed")],
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.approve_user_attachment(55, 2201)

    assert result is False
    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    assert cursor.execute.await_count == 3


async def test_user_repository_reject_user_attachment_rolls_back_on_stats_write_error() -> None:
    cursor = _CursorRecorder(
        fetchone_values=[{"user_id": 5501}],
        execute_side_effect=[None, None, RuntimeError("reject stats failed")],
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.reject_user_attachment(66, 2202, "bad attachment")

    assert result is False
    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    assert cursor.execute.await_count == 3


async def test_user_repository_reject_user_attachment_commits_once() -> None:
    cursor = _CursorRecorder(fetchone_values=[{"user_id": 5501}])
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.reject_user_attachment(66, 2202, "bad attachment")

    assert result is True
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    assert cursor.execute.await_count == 3


async def test_receive_reject_reason_clears_state_and_handles_runtime_error(monkeypatch) -> None:
    from utils.error_handler import error_handler

    update = SimpleNamespace(
        message=SimpleNamespace(text="bad attachment", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=2202),
    )
    context = SimpleNamespace(
        user_data={"ua_reject_attachment_id": 66},
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    attachment = {
        "id": 66,
        "user_id": 5501,
        "mode": "mp",
        "weapon_name": "M13",
        "name": "Stock",
    }
    db = SimpleNamespace(
        users=SimpleNamespace(
            get_user_attachment=AsyncMock(return_value=attachment),
            reject_user_attachment=AsyncMock(side_effect=RuntimeError("reject failed")),
            get_user_language=AsyncMock(return_value="fa"),
        )
    )
    cache = SimpleNamespace(invalidate=AsyncMock())
    handle_error = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)
    monkeypatch.setattr(error_handler, "handle_telegram_error", handle_error)

    result = await review_handler.receive_reject_reason(update, context)

    assert result == ConversationHandler.END
    db.users.get_user_attachment.assert_awaited_once_with(66)
    db.users.reject_user_attachment.assert_awaited_once_with(66, 2202, "bad attachment")
    handle_error.assert_awaited_once()
    cache.invalidate.assert_not_called()
    context.bot.send_message.assert_not_called()
    assert "ua_reject_attachment_id" not in context.user_data


async def test_receive_reject_reason_succeeds_even_if_notification_and_cache_fail(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="duplicate", reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=2206),
    )
    context = SimpleNamespace(
        user_data={"ua_reject_attachment_id": 67},
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("notify failed"))),
    )
    attachment = {
        "id": 67,
        "user_id": 5502,
        "mode": "mp",
        "weapon_name": "Type 19",
        "name": "Grip",
    }
    db = SimpleNamespace(
        users=SimpleNamespace(
            get_user_attachment=AsyncMock(return_value=attachment),
            reject_user_attachment=AsyncMock(return_value=True),
            get_user_language=AsyncMock(side_effect=RuntimeError("lang failed")),
        )
    )
    cache = SimpleNamespace(invalidate=AsyncMock(side_effect=RuntimeError("cache failed")))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    result = await review_handler.receive_reject_reason(update, context)

    assert result == ConversationHandler.END
    db.users.reject_user_attachment.assert_awaited_once_with(67, 2206, "duplicate")
    assert cache.invalidate.await_count == 3
    context.bot.send_message.assert_awaited_once()
    update.message.reply_text.assert_awaited_once()
    assert update.message.reply_text.await_args.args[0] == "admin.ua.reject.success"
    assert "ua_reject_attachment_id" not in context.user_data


async def test_show_attachment_view_rejects_malformed_payload(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_view_bad",
        answer=AsyncMock(),
        message=SimpleNamespace(reply_photo=AsyncMock(), delete=AsyncMock()),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2301),
    )
    context = SimpleNamespace()
    db = SimpleNamespace(users=SimpleNamespace(get_user_attachment=AsyncMock()))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    await review_handler.show_attachment_view(update, context)

    assert query.answer.await_count == 2
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.users.get_user_attachment.assert_not_called()
    query.message.reply_photo.assert_not_called()


async def test_delete_attachment_admin_invalidates_cache_and_shows_deleted_list(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_delete_77",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2302),
    )
    context = SimpleNamespace()
    db = SimpleNamespace(users=SimpleNamespace(delete_user_attachment=AsyncMock(return_value=True)))
    cache = SimpleNamespace(invalidate=AsyncMock())
    show_deleted = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_deleted_list", show_deleted)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    await review_handler.delete_attachment_admin(update, context)

    db.users.delete_user_attachment.assert_awaited_once_with(77, deleted_by=2302)
    assert cache.invalidate.await_count == 2
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    show_deleted.assert_awaited_once_with(update, context)


async def test_delete_attachment_admin_succeeds_even_if_cache_invalidation_fails(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_delete_78",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2304),
    )
    context = SimpleNamespace()
    db = SimpleNamespace(users=SimpleNamespace(delete_user_attachment=AsyncMock(return_value=True)))
    cache = SimpleNamespace(invalidate=AsyncMock(side_effect=RuntimeError("cache failed")))
    show_deleted = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_deleted_list", show_deleted)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    await review_handler.delete_attachment_admin(update, context)

    db.users.delete_user_attachment.assert_awaited_once_with(78, deleted_by=2304)
    assert cache.invalidate.await_count == 2
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    show_deleted.assert_awaited_once_with(update, context)


async def test_restore_attachment_admin_rejects_malformed_payload(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_restore_bad",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2303),
    )
    context = SimpleNamespace()
    db = SimpleNamespace(users=SimpleNamespace(restore_user_attachment=AsyncMock()))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    await review_handler.restore_attachment_admin(update, context)

    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.users.restore_user_attachment.assert_not_called()


async def test_restore_attachment_admin_succeeds_even_if_cache_invalidation_fails(monkeypatch) -> None:
    query = SimpleNamespace(
        data="ua_admin_restore_79",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=2305),
    )
    context = SimpleNamespace()
    db = SimpleNamespace(users=SimpleNamespace(restore_user_attachment=AsyncMock(return_value=True)))
    cache = SimpleNamespace(invalidate=AsyncMock(side_effect=RuntimeError("cache failed")))
    show_pending = AsyncMock()

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "cache", cache)
    monkeypatch.setattr(review_handler, "show_pending_list", show_pending)
    monkeypatch.setattr(review_handler, "check_ua_admin_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    await review_handler.restore_attachment_admin(update, context)

    db.users.restore_user_attachment.assert_awaited_once_with(79)
    assert cache.invalidate.await_count == 2
    query.answer.assert_awaited_once()
    assert query.answer.await_args.kwargs.get("show_alert") is True
    show_pending.assert_awaited_once_with(update, context)


async def test_user_repository_delete_user_attachment_commits_once() -> None:
    cursor = _CursorRecorder(fetchone_values=[{"user_id": 6601, "status": "approved"}])
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.delete_user_attachment(77, deleted_by=2302)

    assert result is True
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    assert cursor.execute.await_count == 3


async def test_user_repository_delete_user_attachment_rolls_back_on_stats_write_error() -> None:
    cursor = _CursorRecorder(
        fetchone_values=[{"user_id": 6601, "status": "approved"}],
        execute_side_effect=[None, None, RuntimeError("delete stats failed")],
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.delete_user_attachment(77, deleted_by=2302)

    assert result is False
    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    assert cursor.execute.await_count == 3


async def test_user_repository_restore_user_attachment_rolls_back_on_pending_count_write_error() -> None:
    cursor = _CursorRecorder(
        fetchone_values=[{"user_id": 7701, "status": "deleted"}],
        execute_side_effect=[None, None, None, RuntimeError("pending count failed")],
    )
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.restore_user_attachment(78)

    assert result is False
    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    assert cursor.execute.await_count == 4


async def test_user_repository_restore_user_attachment_commits_once() -> None:
    cursor = _CursorRecorder(fetchone_values=[{"user_id": 7701, "status": "deleted"}])
    conn = SimpleNamespace(cursor=Mock(return_value=cursor))
    tx = _TxRecorder(conn)
    repo = UserRepository(SimpleNamespace(transaction=Mock(return_value=tx)))

    result = await repo.restore_user_attachment(78)

    assert result is True
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    assert cursor.execute.await_count == 4


async def test_receive_new_weapon_name_clears_state_on_runtime_error(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="M4A1", reply_text=AsyncMock()),
    )
    context = SimpleNamespace(user_data={"ua_edit_weapon_attachment_id": 88})
    cur = SimpleNamespace(
        execute=AsyncMock(side_effect=RuntimeError("update failed")),
        close=AsyncMock(),
    )
    tconn = SimpleNamespace(cursor=Mock(return_value=cur))
    db = SimpleNamespace(transaction=Mock(return_value=_AsyncTx(tconn)))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    result = await review_handler.receive_new_weapon_name(update, context)

    assert result == ConversationHandler.END
    db.transaction.assert_called_once_with()
    cur.execute.assert_awaited_once()
    update.message.reply_text.assert_awaited_once_with("admin.ua.edit_weapon.error")
    assert "ua_edit_weapon_attachment_id" not in context.user_data


async def test_receive_new_weapon_name_commits_once_on_success(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="M4A1", reply_text=AsyncMock()),
    )
    context = SimpleNamespace(user_data={"ua_edit_weapon_attachment_id": 89})
    cur = _CursorRecorder()
    tconn = SimpleNamespace(cursor=Mock(return_value=cur))
    tx = _TxRecorder(tconn)
    db = SimpleNamespace(transaction=Mock(return_value=tx))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    result = await review_handler.receive_new_weapon_name(update, context)

    assert result == ConversationHandler.END
    db.transaction.assert_called_once_with()
    assert tx.commit_count == 1
    assert tx.rollback_count == 0
    cur.execute.assert_awaited_once()
    cur.close.assert_awaited_once_with()
    update.message.reply_text.assert_awaited_once()
    assert "ua_edit_weapon_attachment_id" not in context.user_data


async def test_receive_new_weapon_name_rolls_back_on_write_error(monkeypatch) -> None:
    update = SimpleNamespace(
        message=SimpleNamespace(text="M4A1", reply_text=AsyncMock()),
    )
    context = SimpleNamespace(user_data={"ua_edit_weapon_attachment_id": 88})
    cur = _CursorRecorder(execute_side_effect=RuntimeError("update failed"))
    tconn = SimpleNamespace(cursor=Mock(return_value=cur))
    tx = _TxRecorder(tconn)
    db = SimpleNamespace(transaction=Mock(return_value=tx))

    monkeypatch.setattr(review_handler, "db", db)
    monkeypatch.setattr(review_handler, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(review_handler, "t", lambda key, lang, **kwargs: key)

    result = await review_handler.receive_new_weapon_name(update, context)

    assert result == ConversationHandler.END
    db.transaction.assert_called_once_with()
    assert tx.commit_count == 0
    assert tx.rollback_count == 1
    cur.execute.assert_awaited_once()
    cur.close.assert_not_called()
    update.message.reply_text.assert_awaited_once_with("admin.ua.edit_weapon.error")
    assert "ua_edit_weapon_attachment_id" not in context.user_data


async def test_show_single_channel_stats_falls_back_to_fa_on_missing_channel(monkeypatch) -> None:
    query = SimpleNamespace(
        data="channel_stat_-10055",
        answer=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    db = SimpleNamespace(cms=SimpleNamespace(get_channel_by_id=AsyncMock(return_value=None)))
    context = SimpleNamespace(bot_data={"database": db})
    channel_menu = AsyncMock(return_value="CHANNEL_MENU")

    class _Analytics:
        async def get_channel_stats(self, channel_id):
            raise AssertionError("analytics should not be called when channel is missing")

    monkeypatch.setattr(channel_stats_handlers, "Analytics", _Analytics)
    monkeypatch.setattr(channel_stats_handlers, "get_user_lang", AsyncMock(side_effect=RuntimeError("lang failed")))
    monkeypatch.setattr(channel_stats_handlers, "t", lambda key, lang, **kwargs: f"{key}:{lang}")

    result = await channel_stats_handlers.show_single_channel_stats_impl(
        update,
        context,
        channel_management_menu=channel_menu,
        channel_menu_state="CHANNEL_MENU",
    )

    assert result == "CHANNEL_MENU"
    assert query.answer.await_count == 2
    assert query.answer.await_args.kwargs.get("show_alert") is True
    db.cms.get_channel_by_id.assert_awaited_once_with("-10055")
    channel_menu.assert_awaited_once_with(update, context)


async def test_show_channel_stats_renders_error_with_back_button(monkeypatch) -> None:
    query = SimpleNamespace(
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(bot_data={"database": Mock()})
    safe_edit = AsyncMock()

    class _Analytics:
        async def generate_admin_dashboard(self):
            raise RuntimeError("dashboard failed")

    monkeypatch.setattr(channel_stats_handlers, "Analytics", _Analytics)
    monkeypatch.setattr(channel_stats_handlers, "get_user_lang", AsyncMock(return_value="fa"))
    monkeypatch.setattr(channel_stats_handlers, "safe_edit_message_text", safe_edit)
    monkeypatch.setattr(channel_stats_handlers, "t", lambda key, lang, **kwargs: f"{key}:{lang}")

    result = await channel_stats_handlers.show_channel_stats_impl(
        update,
        context,
        channel_menu_state="CHANNEL_MENU",
    )

    assert result == "CHANNEL_MENU"
    query.answer.assert_awaited_once_with()
    safe_edit.assert_awaited_once()
    assert safe_edit.await_args is not None
    assert safe_edit.await_args.args[1] == "admin.channels.stats.error:fa"
    reply_markup = safe_edit.await_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "channel_menu"

