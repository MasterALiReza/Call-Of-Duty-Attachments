from types import SimpleNamespace
from unittest.mock import AsyncMock

import handlers.admin.admin_menu_routing as admin_menu_routing


async def test_route_notification_actions_accepts_admin_schedule_alias() -> None:
    handler = SimpleNamespace(schedules_menu=AsyncMock(return_value="scheduled"))
    routes = admin_menu_routing.build_notification_action_routes(
        SimpleNamespace(
            notify_compose_start=AsyncMock(),
            schedules_menu=handler.schedules_menu,
            notify_home_menu=AsyncMock(),
            notify_toggle=AsyncMock(),
            notify_auto_toggle=AsyncMock(),
            template_list_menu=AsyncMock(),
            notif_toggle_event=AsyncMock(),
            template_edit_start=AsyncMock(),
            schedule_delete=AsyncMock(),
            schedule_toggle=AsyncMock(),
            schedule_edit_text_start=AsyncMock(),
            schedule_edit_open=AsyncMock(),
            notify_confirm_selected=AsyncMock(),
            notify_schedule_menu=AsyncMock(),
            notify_schedule_preset_selected=AsyncMock(),
            notif_toggle_global=AsyncMock(),
            notify_settings_menu=AsyncMock(),
        )
    )

    result = await admin_menu_routing.route_notification_actions(
        "admin_sched_notifications",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "scheduled"
    handler.schedules_menu.assert_awaited_once()


async def test_route_health_actions_accepts_restore_backup_alias() -> None:
    health_handler = SimpleNamespace(
        run_health_check=AsyncMock(),
        view_full_report=AsyncMock(),
        view_critical=AsyncMock(),
        view_warnings=AsyncMock(),
        view_detailed_stats=AsyncMock(),
        view_check_history=AsyncMock(),
        fix_missing_images=AsyncMock(),
        fix_duplicate_codes=AsyncMock(),
        fix_orphaned=AsyncMock(),
        fix_technical=AsyncMock(),
        restore_backup_start=AsyncMock(return_value="restore"),
        create_backup=AsyncMock(),
        fix_issues_menu=AsyncMock(),
    )
    routes = admin_menu_routing.build_health_action_routes(
        health_handler,
        AsyncMock(return_value="health-menu"),
    )

    result = await admin_menu_routing.route_health_actions(
        "restore_backup",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "restore"
    health_handler.restore_backup_start.assert_awaited_once()


async def test_route_health_actions_accepts_health_create_backup_alias() -> None:
    health_handler = SimpleNamespace(
        run_health_check=AsyncMock(),
        view_full_report=AsyncMock(),
        view_critical=AsyncMock(),
        view_warnings=AsyncMock(),
        view_detailed_stats=AsyncMock(),
        view_check_history=AsyncMock(),
        fix_missing_images=AsyncMock(),
        fix_duplicate_codes=AsyncMock(),
        fix_orphaned=AsyncMock(),
        fix_technical=AsyncMock(),
        restore_backup_start=AsyncMock(),
        create_backup=AsyncMock(return_value="backup"),
        fix_issues_menu=AsyncMock(),
    )
    routes = admin_menu_routing.build_health_action_routes(
        health_handler,
        AsyncMock(return_value="health-menu"),
    )

    result = await admin_menu_routing.route_health_actions(
        "health_create_backup",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "backup"
    health_handler.create_backup.assert_awaited_once()


async def test_route_health_actions_accepts_fix_issues_alias() -> None:
    health_handler = SimpleNamespace(
        run_health_check=AsyncMock(),
        view_full_report=AsyncMock(),
        view_critical=AsyncMock(),
        view_warnings=AsyncMock(),
        view_detailed_stats=AsyncMock(),
        view_check_history=AsyncMock(),
        fix_missing_images=AsyncMock(),
        fix_duplicate_codes=AsyncMock(),
        fix_orphaned=AsyncMock(),
        fix_technical=AsyncMock(),
        restore_backup_start=AsyncMock(),
        create_backup=AsyncMock(),
        fix_issues_menu=AsyncMock(return_value="fix-menu"),
    )
    routes = admin_menu_routing.build_health_action_routes(
        health_handler,
        AsyncMock(return_value="health-menu"),
    )

    result = await admin_menu_routing.route_health_actions(
        "fix_issues_menu",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "fix-menu"
    health_handler.fix_issues_menu.assert_awaited_once()


async def test_route_data_management_actions_handles_backup_alias() -> None:
    data_handler = SimpleNamespace(
        data_management_menu=AsyncMock(),
        create_backup=AsyncMock(return_value="backup"),
        auto_backup_menu=AsyncMock(),
        toggle_auto_backup=AsyncMock(),
        set_auto_backup_interval=AsyncMock(),
    )
    import_export_handler = SimpleNamespace(
        import_start=AsyncMock(),
        export_start=AsyncMock(),
    )
    routes = admin_menu_routing.build_data_management_action_routes(data_handler, import_export_handler)

    result = await admin_menu_routing.route_data_management_actions(
        "admin_create_backup",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "backup"
    data_handler.create_backup.assert_awaited_once()


async def test_route_data_management_actions_handles_import() -> None:
    data_handler = SimpleNamespace(
        data_management_menu=AsyncMock(),
        create_backup=AsyncMock(),
        auto_backup_menu=AsyncMock(),
        toggle_auto_backup=AsyncMock(),
        set_auto_backup_interval=AsyncMock(),
    )
    import_export_handler = SimpleNamespace(
        import_start=AsyncMock(return_value="import"),
        export_start=AsyncMock(),
    )
    routes = admin_menu_routing.build_data_management_action_routes(data_handler, import_export_handler)

    result = await admin_menu_routing.route_data_management_actions(
        "admin_import",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "import"
    import_export_handler.import_start.assert_awaited_once()


async def test_route_support_actions_handles_faq_category() -> None:
    handler = SimpleNamespace(
        admin_faqs_menu=AsyncMock(),
        admin_faq_add_start=AsyncMock(),
        admin_faq_category_selected=AsyncMock(return_value="faq-category"),
        admin_faq_list=AsyncMock(),
        admin_tickets_menu=AsyncMock(),
        admin_direct_contact_menu=AsyncMock(),
    )
    routes = admin_menu_routing.build_support_action_routes(handler)

    result = await admin_menu_routing.route_support_actions(
        "adm_faq_cat_general",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "faq-category"
    handler.admin_faq_category_selected.assert_awaited_once()


async def test_route_content_actions_handles_text_edit_prefix() -> None:
    guides_handler = SimpleNamespace(
        guides_menu=AsyncMock(),
        guides_mode_selected=AsyncMock(),
        guide_section_menu=AsyncMock(),
        guide_op_router=AsyncMock(),
    )
    category_handler = SimpleNamespace(
        category_mgmt_menu=AsyncMock(),
        category_mode_selected=AsyncMock(),
        category_toggle_selected=AsyncMock(),
        category_clear_prompt=AsyncMock(),
        category_clear_confirm=AsyncMock(),
        category_clear_cancel=AsyncMock(),
    )
    weapon_handler = SimpleNamespace(
        weapon_mgmt_menu=AsyncMock(),
        weapon_mode_selected=AsyncMock(),
        weapon_select_category_menu=AsyncMock(),
        weapon_select_weapon_menu=AsyncMock(),
        weapon_action_selected=AsyncMock(),
        weapon_delete_confirmed=AsyncMock(),
    )
    text_handler = SimpleNamespace(
        texts_menu=AsyncMock(),
        text_edit_start=AsyncMock(return_value="text-edit"),
    )
    routes = admin_menu_routing.build_content_action_routes(
        guides_handler,
        category_handler,
        weapon_handler,
        text_handler,
        cms_handler=None,
    )

    result = await admin_menu_routing.route_content_actions(
        "text_edit_home_title",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "text-edit"
    text_handler.text_edit_start.assert_awaited_once()


async def test_route_content_actions_handles_cms_disabled_safely() -> None:
    routes = admin_menu_routing.build_content_action_routes(
        guides_handler=SimpleNamespace(
            guides_menu=AsyncMock(),
            guides_mode_selected=AsyncMock(),
            guide_section_menu=AsyncMock(),
            guide_op_router=AsyncMock(),
        ),
        category_handler=SimpleNamespace(
            category_mgmt_menu=AsyncMock(),
            category_mode_selected=AsyncMock(),
            category_toggle_selected=AsyncMock(),
            category_clear_prompt=AsyncMock(),
            category_clear_confirm=AsyncMock(),
            category_clear_cancel=AsyncMock(),
        ),
        weapon_handler=SimpleNamespace(
            weapon_mgmt_menu=AsyncMock(),
            weapon_mode_selected=AsyncMock(),
            weapon_select_category_menu=AsyncMock(),
            weapon_select_weapon_menu=AsyncMock(),
            weapon_action_selected=AsyncMock(),
            weapon_delete_confirmed=AsyncMock(),
        ),
        text_handler=SimpleNamespace(
            texts_menu=AsyncMock(),
            text_edit_start=AsyncMock(),
        ),
        cms_handler=None,
    )

    result = await admin_menu_routing.route_content_actions(
        "admin_cms",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result is None


async def test_route_content_actions_handles_weapon_action_prefix() -> None:
    weapon_handler = SimpleNamespace(
        weapon_mgmt_menu=AsyncMock(),
        weapon_mode_selected=AsyncMock(),
        weapon_select_category_menu=AsyncMock(),
        weapon_select_weapon_menu=AsyncMock(),
        weapon_action_selected=AsyncMock(return_value="weapon-action"),
        weapon_delete_confirmed=AsyncMock(),
    )
    routes = admin_menu_routing.build_content_action_routes(
        guides_handler=SimpleNamespace(
            guides_menu=AsyncMock(),
            guides_mode_selected=AsyncMock(),
            guide_section_menu=AsyncMock(),
            guide_op_router=AsyncMock(),
        ),
        category_handler=SimpleNamespace(
            category_mgmt_menu=AsyncMock(),
            category_mode_selected=AsyncMock(),
            category_toggle_selected=AsyncMock(),
            category_clear_prompt=AsyncMock(),
            category_clear_confirm=AsyncMock(),
            category_clear_cancel=AsyncMock(),
        ),
        weapon_handler=weapon_handler,
        text_handler=SimpleNamespace(
            texts_menu=AsyncMock(),
            text_edit_start=AsyncMock(),
        ),
        cms_handler=None,
    )

    result = await admin_menu_routing.route_content_actions(
        "wmact_delete",
        SimpleNamespace(),
        SimpleNamespace(),
        routes,
    )

    assert result == "weapon-action"
    weapon_handler.weapon_action_selected.assert_awaited_once()
