"""Initialization helpers for AdminHandlers."""

from __future__ import annotations

from handlers.admin.admin_menu_routing import (
    build_admin_management_action_routes,
    build_admin_menu_exact_routes,
    build_analytics_action_routes,
    build_content_action_routes,
    build_data_management_action_routes,
    build_feedback_action_routes,
    build_health_action_routes,
    build_notification_action_routes,
    build_support_action_routes,
    build_user_management_action_routes,
    route_admin_management_actions,
    route_analytics_actions,
    route_content_actions,
    route_data_management_actions,
    route_feedback_actions,
    route_health_actions,
    route_notification_actions,
    route_support_actions,
    route_user_management_actions,
)
from handlers.admin.modules.analytics import AttachmentsDashboardHandler
from handlers.admin.modules.attachments import (
    AddAttachmentHandler,
    AttachmentManagementHandler,
    DeleteAttachmentHandler,
    EditAttachmentHandler,
    SuggestedAttachmentsHandler,
    TopAttachmentsHandler,
)
from handlers.admin.modules.content import (
    CategoryHandler,
    GuidesHandler,
    TextHandler,
    WeaponHandler,
)
from handlers.admin.modules.reports import DataHealthReportHandler
from handlers.admin.modules.support import (
    DirectContactHandler,
    FAQHandler,
    TicketHandler,
)
from handlers.admin.modules.system import (
    AdminManagementHandler,
    DataManagementHandler,
    ImportExportHandler,
    NotificationHandler,
)


def init_attachment_handlers(handler) -> None:
    handler.add_attachment_handler = AddAttachmentHandler(handler.db)
    handler.delete_attachment_handler = DeleteAttachmentHandler(handler.db)
    handler.edit_attachment_handler = EditAttachmentHandler(handler.db)
    handler.top_attachments_handler = TopAttachmentsHandler(handler.db)
    handler.suggested_attachments_handler = SuggestedAttachmentsHandler(handler.db)
    handler.attachment_mgmt_handler = AttachmentManagementHandler(handler.db)

    from handlers.admin.modules.feedback.feedback_admin_handler import (
        FeedbackAdminHandler,
    )

    handler.feedback_admin = FeedbackAdminHandler(handler.db)

    handler._bind_handler_methods(
        handler.attachment_mgmt_handler, ("attachment_management_menu",)
    )
    handler._bind_handler_methods(
        handler.add_attachment_handler,
        (
            "add_attachment_start",
            "add_attachment_category_selected",
            "add_attachment_weapon_selected",
            "add_attachment_mode_selected",
            "add_attachment_new_weapon_name_received",
            "add_attachment_code_received",
            "add_attachment_name_received",
            "add_attachment_image_received",
            "add_attachment_top_selected",
            "add_attachment_season_selected",
            "add_attachment_top_ignore_text",
            "add_attachment_season_ignore_text",
        ),
    )
    handler._bind_handler_methods(
        handler.delete_attachment_handler,
        (
            "delete_attachment_start",
            "delete_attachment_category_selected",
            "delete_attachment_weapon_selected",
            "delete_attachment_mode_selected",
            "delete_attachment_code_selected",
        ),
    )
    handler._bind_handler_methods(
        handler.edit_attachment_handler,
        (
            "edit_attachment_start",
            "edit_attachment_category_selected",
            "edit_attachment_weapon_selected",
            "edit_attachment_mode_selected",
            "edit_attachment_selected",
            "edit_attachment_action_menu",
            "edit_attachment_action_selected",
            "edit_attachment_name_received",
            "edit_attachment_image_received",
            "edit_attachment_code_received",
        ),
    )
    handler._bind_handler_methods(
        handler.top_attachments_handler,
        (
            "set_top_start",
            "set_top_category_selected",
            "set_top_weapon_selected",
            "set_top_mode_selected",
            "set_top_attachment_selected",
            "set_top_confirm_answer",
            "set_top_confirm_save",
        ),
    )
    handler._bind_handler_methods(
        handler.suggested_attachments_handler,
        (
            "manage_suggested_menu",
            "suggested_add_start",
            "suggested_mode_selected",
            "suggested_category_selected",
            "suggested_weapon_selected",
            "suggested_attachment_selected",
            "suggested_remove_start",
            "suggested_remove_mode_selected",
            "suggested_delete_confirmed",
            "suggested_view_list",
            "suggested_analytics_menu",
            "analytics_sugg_trending",
            "analytics_sugg_underperforming",
            "analytics_sugg_weapon_stats",
        ),
    )


def init_system_handlers(handler) -> None:
    handler.category_handler = CategoryHandler(handler.db)
    handler.weapon_handler = WeaponHandler(handler.db)
    handler.admin_mgmt_handler = AdminManagementHandler(handler.db)
    handler.admin_mgmt_handler.set_role_manager(handler.role_manager)
    handler.import_export_handler = ImportExportHandler(handler.db)
    handler.notification_handler = NotificationHandler(handler.db)
    handler.data_mgmt_handler = DataManagementHandler(handler.db)

    from handlers.admin.modules.system.user_management import UserManagementHandler

    handler.user_mgmt_handler = UserManagementHandler(handler.db)

    handler._bind_handler_methods(
        handler.notification_handler,
        (
            "notify_start",
            "notify_home_menu",
            "notify_compose_start",
            "notify_compose_received",
            "notify_settings_menu",
            "notify_toggle",
            "notify_auto_toggle",
            "template_list_menu",
            "notif_toggle_event",
            "template_edit_start",
            "schedule_delete",
            "schedule_toggle",
            "schedule_edit_open",
            "schedule_edit_text_start",
            "schedule_edit_text_received",
            "notify_confirm_selected",
            "notify_schedule_menu",
            "notify_schedule_preset_selected",
            "notif_toggle_global",
            "schedules_menu",
        ),
    )
    handler._bind_handler_methods(
        handler.admin_mgmt_handler,
        (
            "manage_admins_menu",
            "add_admin_start",
            "add_admin_role_selected",
            "add_admin_id_received",
            "add_admin_display_name_received",
            "edit_admin_role_start",
            "edit_admin_role_select",
            "add_role_to_admin",
            "add_role_confirm",
            "delete_role_from_admin",
            "delete_role_confirm",
            "remove_admin_start",
            "remove_admin_confirmed",
            "view_all_admins",
            "role_stats",
            "view_roles_menu",
        ),
    )
    handler._bind_handler_methods(
        handler.data_mgmt_handler,
        (
            "data_management_menu",
            "auto_backup_menu",
            "toggle_auto_backup",
            "set_auto_backup_interval",
        ),
    )
    handler._bind_handler_methods(
        handler.import_export_handler,
        (
            "import_start",
            "import_file_received",
            "import_mode_selected",
            "export_start",
            "export_type_selected",
        ),
    )
    handler._bind_handler_methods(
        handler.user_mgmt_handler,
        (
            "user_mgmt_menu",
            "user_list",
            "user_search_start",
            "user_search_received",
            "user_detail",
            "user_ban_start",
            "user_ban_confirm",
            "user_unban",
            "user_filter_banned",
        ),
    )


def init_support_handlers(handler) -> None:
    handler.admin_faq_handler = FAQHandler(handler.db)
    handler.admin_ticket_handler = TicketHandler(handler.db)
    handler.direct_contact_handler = DirectContactHandler(handler.db)

    handler._bind_handler_methods(
        handler.admin_faq_handler,
        (
            "admin_faqs_menu",
            "admin_faq_list",
            "admin_faq_view",
            "admin_faq_stats",
            "admin_feedback_stats",
            "admin_faq_add_start",
            "admin_faq_category_selected",
            "admin_faq_question_received",
            "admin_faq_answer_received",
            "admin_faq_edit",
            "admin_faq_edit_field_select",
            "admin_faq_edit_question_received",
            "admin_faq_edit_answer_received",
            "admin_faq_delete",
            "admin_faq_set_lang",
        ),
    )
    handler._bind_handler_methods(
        handler.admin_ticket_handler,
        (
            "admin_tickets_menu",
            "admin_tickets_list",
            "admin_tickets_page_navigation",
            "admin_ticket_detail",
            "admin_ticket_reply_start",
            "admin_ticket_reply_received",
            "admin_ticket_change_status",
            "admin_ticket_set_status",
            "admin_ticket_close",
            "admin_ticket_search_start",
            "admin_ticket_search_received",
            "admin_ticket_view_attachments",
            "admin_ticket_change_priority",
            "admin_ticket_set_priority",
            "admin_ticket_assign_start",
            "admin_ticket_assign_confirm",
            "admin_tickets_filter_category",
            "admin_tickets_mine",
        ),
    )
    handler._bind_handler_methods(
        handler.direct_contact_handler,
        (
            "admin_direct_contact_menu",
            "direct_contact_toggle_status",
            "direct_contact_edit_name_start",
            "direct_contact_name_received",
            "direct_contact_edit_link_start",
            "direct_contact_link_received",
        ),
    )


def init_content_handlers(handler) -> None:
    handler.guides_handler = GuidesHandler(handler.db)
    handler.guides_handler.set_role_manager(handler.role_manager)
    if not hasattr(handler, "category_handler"):
        handler.category_handler = CategoryHandler(handler.db)
    if not hasattr(handler, "weapon_handler"):
        handler.weapon_handler = WeaponHandler(handler.db)
    handler.text_handler = TextHandler(handler.db)

    try:
        from handlers.admin.modules.content import CMSHandler

        handler.cms_handler = CMSHandler(handler.db)
    except Exception:
        handler.cms_handler = None

    handler.category_handler.set_role_manager(handler.role_manager)
    handler._bind_handler_methods(
        handler.guides_handler,
        (
            "guides_menu",
            "guides_mode_selected",
            "guide_section_menu",
            "guide_op_router",
            "guide_rename_received",
            "guide_photo_received",
            "guide_video_received",
            "guide_media_confirmed",
            "guide_code_received",
        ),
    )
    handler._bind_handler_methods(
        handler.category_handler,
        (
            "category_mgmt_menu",
            "category_mode_selected",
            "category_toggle_selected",
            "category_clear_prompt",
            "category_clear_confirm",
            "category_clear_cancel",
        ),
    )
    handler._bind_handler_methods(
        handler.weapon_handler,
        (
            "weapon_mgmt_menu",
            "weapon_mode_selected",
            "weapon_select_category_menu",
            "weapon_select_weapon_menu",
            "weapon_action_selected",
            "weapon_delete_confirmed",
        ),
    )
    handler._bind_handler_methods(
        handler.text_handler,
        (
            "texts_menu",
            "text_edit_start",
            "text_edit_received",
        ),
    )
    if handler.cms_handler:
        handler._bind_handler_methods(
            handler.cms_handler,
            (
                "cms_menu",
                "cms_add_start",
                "cms_type_selected",
                "cms_title_received",
                "cms_body_received",
                "cms_list_menu",
                "cms_publish",
                "cms_delete",
                "cms_search_start",
                "cms_search_received",
            ),
        )


def init_new_feature_handlers(handler) -> None:
    from core.security.role_manager import RoleManager

    role_manager = RoleManager(handler.db)

    handler.analytics_handler = AttachmentsDashboardHandler(handler.db)
    handler._bind_handler_methods(
        handler.analytics_handler,
        (
            "analytics_menu",
            "view_trending",
            "view_underperforming",
            "view_weapon_stats",
            "weapon_stats_select_mode",
            "weapon_stats_show_results",
            "view_user_behavior",
            "user_behavior_details",
            "daily_report",
            "weekly_report",
            "search_attachment_stats",
            "handle_search_text",
            "download_report",
            "refresh_trending",
            "daily_chart",
            "download_daily_csv",
            "weapon_details",
            "att_daily_chart",
            "att_download_csv",
        ),
    )

    handler.health_handler = DataHealthReportHandler(handler.db, role_manager)
    handler._bind_handler_methods(
        handler.health_handler,
        (
            "data_health_menu",
            "run_health_check",
            "view_full_report",
            "view_critical",
            "view_warnings",
            "view_detailed_stats",
            "view_check_history",
            "fix_issues_menu",
            "fix_missing_images",
            "fix_duplicate_codes",
            "fix_orphaned",
            "fix_technical",
            "restore_backup_start",
            "restore_backup_file",
        ),
    )


def init_action_routes(handler) -> None:
    handler._admin_menu_exact_routes = build_admin_menu_exact_routes(handler)
    handler._notification_action_routes = build_notification_action_routes(handler)
    handler._data_management_action_routes = build_data_management_action_routes(
        handler.data_mgmt_handler,
        handler.import_export_handler,
    )
    handler._support_action_routes = build_support_action_routes(handler)
    handler._content_action_routes = build_content_action_routes(
        handler.guides_handler,
        handler.category_handler,
        handler.weapon_handler,
        handler.text_handler,
        handler.cms_handler,
    )
    handler._analytics_action_routes = build_analytics_action_routes(
        handler.analytics_handler,
        handler.analytics_menu,
    )
    handler._health_action_routes = build_health_action_routes(
        handler.health_handler,
        handler.data_health_menu,
    )
    handler._feedback_action_routes = build_feedback_action_routes(
        handler.feedback_admin
    )
    handler._admin_management_action_routes = build_admin_management_action_routes(
        handler
    )
    handler._user_management_action_routes = build_user_management_action_routes(
        handler
    )
    handler._admin_menu_route_groups = (
        (route_notification_actions, handler._notification_action_routes),
        (route_data_management_actions, handler._data_management_action_routes),
        (route_support_actions, handler._support_action_routes),
        (route_content_actions, handler._content_action_routes),
        (route_analytics_actions, handler._analytics_action_routes),
        (route_health_actions, handler._health_action_routes),
        (route_feedback_actions, handler._feedback_action_routes),
        (route_admin_management_actions, handler._admin_management_action_routes),
        (route_user_management_actions, handler._user_management_action_routes),
    )
