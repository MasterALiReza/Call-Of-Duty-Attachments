"""Admin menu routing helpers extracted from admin_handlers_modular."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Mapping, TypeAlias

from telegram import Update

from core.context import CustomContext

AdminRouteResult: TypeAlias = object | int | None
AdminActionHandler: TypeAlias = Callable[
    [Update, CustomContext], Awaitable[AdminRouteResult]
]
AdminActionMap: TypeAlias = Mapping[str, AdminActionHandler]

DEFAULT_ROUTE_KEY = "__default__"


def _iter_route_patterns(routes: AdminActionMap):
    for pattern, callback in routes.items():
        if pattern == DEFAULT_ROUTE_KEY:
            continue
        yield pattern, callback


def _matches_action(action: str, routes: AdminActionMap) -> bool:
    for pattern, _callback in _iter_route_patterns(routes):
        if pattern.endswith("*") and action.startswith(pattern[:-1]):
            return True
        if action == pattern:
            return True
    return False


async def _dispatch_action(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    exact_handler = routes.get(action)
    if exact_handler is not None:
        return await exact_handler(update, context)

    for pattern, callback in _iter_route_patterns(routes):
        if pattern.endswith("*") and action.startswith(pattern[:-1]):
            return await callback(update, context)

    default_handler = routes.get(DEFAULT_ROUTE_KEY)
    if default_handler is not None:
        return await default_handler(update, context)

    return None


async def route_notification_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route notification/template/schedule callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_data_management_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route data-management callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_support_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route support callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_content_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route CMS/content/category/weapon/text callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_analytics_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route analytics callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_health_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route data-health callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_feedback_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route feedback callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_admin_management_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route admin-management callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


async def route_user_management_actions(
    action: str,
    update: Update,
    context: CustomContext,
    routes: AdminActionMap,
) -> AdminRouteResult:
    """Route user-management callbacks."""
    if not _matches_action(action, routes):
        return None
    return await _dispatch_action(action, update, context, routes)


def build_admin_menu_exact_routes(handler: Any) -> AdminActionMap:
    return {
        "admin_menu_return": handler.admin_menu_return,
        "admin_back": handler.admin_menu_return,
        "admin_return": handler.admin_menu_return,
        "admin_main": handler.admin_menu_return,
        "manage_admins": handler.manage_admins_menu,
        "admin_manage_attachments": handler.attachment_management_menu,
        "admin_add_attachment": handler.add_attachment_start,
        "admin_delete_attachment": handler.delete_attachment_start,
        "admin_edit_attachment": handler.edit_attachment_start,
        "admin_set_top": handler.set_top_start,
        "admin_manage_suggested": handler.manage_suggested_menu,
        "admin_notify": handler.notify_start,
        "admin_notify_settings": handler.notify_settings_menu,
        "admin_stats": handler.admin_menu_return,
        "nav_back": handler.handle_navigation_back,
        "add_new_admin": handler.add_admin_start,
        "view_all_admins": handler.view_all_admins,
        "role_stats": handler.role_stats,
        "um_noop": handler._admin_menu_noop,
        "admin_exit": handler._admin_menu_exit,
    }


def build_notification_action_routes(handler: Any) -> AdminActionMap:
    return {
        "notify_compose": handler.notify_compose_start,
        "admin_sched_notifications": handler.schedules_menu,
        "notify_home": handler.notify_home_menu,
        "notif_toggle": handler.notify_toggle,
        "notif_auto_toggle": handler.notify_auto_toggle,
        "notif_templates": handler.template_list_menu,
        "notif_event_*": handler.notif_toggle_event,
        "tmpl_edit_*": handler.template_edit_start,
        "sched_delete_*": handler.schedule_delete,
        "sched_toggle_*": handler.schedule_toggle,
        "sched_edit_text_*": handler.schedule_edit_text_start,
        "sched_edit_*": handler.schedule_edit_open,
        "notify_confirm": handler.notify_confirm_selected,
        "nconf_*": handler.notify_confirm_selected,
        "notify_schedule": handler.notify_schedule_menu,
        "notif_sched_*": handler.notify_schedule_preset_selected,
        "notif_toggle_global": handler.notif_toggle_global,
        "notif_schedules": handler.schedules_menu,
        "notif_*": handler.notify_settings_menu,
        "tmpl_*": handler.notify_settings_menu,
        "sched_*": handler.notify_settings_menu,
        "notify_*": handler.notify_settings_menu,
    }


def build_data_management_action_routes(
    data_handler: Any, import_export_handler: Any
) -> AdminActionMap:
    return {
        "admin_data_management": data_handler.data_management_menu,
        "admin_backup": data_handler.create_backup,
        "admin_create_backup": data_handler.create_backup,
        "admin_auto_backup_menu": data_handler.auto_backup_menu,
        "toggle_auto_backup": data_handler.toggle_auto_backup,
        "set_ab_interval_*": data_handler.set_auto_backup_interval,
        "admin_import": import_export_handler.import_start,
        "admin_export": import_export_handler.export_start,
    }


def build_support_action_routes(handler: Any) -> AdminActionMap:
    return {
        "admin_faqs": handler.admin_faqs_menu,
        "adm_faq_add": handler.admin_faq_add_start,
        "adm_faq_cat_*": handler.admin_faq_category_selected,
        "adm_faq_list": handler.admin_faq_list,
        "admin_tickets": handler.admin_tickets_menu,
        "adm_direct_contact": handler.admin_direct_contact_menu,
    }


def build_content_action_routes(
    guides_handler: Any,
    category_handler: Any,
    weapon_handler: Any,
    text_handler: Any,
    cms_handler: Any,
) -> AdminActionMap:
    routes: dict[str, AdminActionHandler] = {
        "admin_guides": guides_handler.guides_menu,
        "gmode_*": guides_handler.guides_mode_selected,
        "gsel_*": guides_handler.guide_section_menu,
        "gop_*": guides_handler.guide_op_router,
        "admin_category_mgmt": category_handler.category_mgmt_menu,
        "cmm_*": category_handler.category_mode_selected,
        "adm_cat_toggle_*": category_handler.category_toggle_selected,
        "adm_cat_clear_*": category_handler.category_clear_prompt,
        "admin_weapon_mgmt": weapon_handler.weapon_mgmt_menu,
        "wmm_*": weapon_handler.weapon_mode_selected,
        "wmcat_*": weapon_handler.weapon_select_category_menu,
        "wmwpn_*": weapon_handler.weapon_select_weapon_menu,
        "wmact_*": weapon_handler.weapon_action_selected,
        "wmconf_*": weapon_handler.weapon_delete_confirmed,
        "cat_clear_confirm": category_handler.category_clear_confirm,
        "cat_clear_cancel": category_handler.category_clear_cancel,
        "admin_texts": text_handler.texts_menu,
        "text_edit_*": text_handler.text_edit_start,
    }
    if cms_handler is not None:
        routes.update(
            {
                "admin_cms": cms_handler.cms_menu,
                "cms_add": cms_handler.cms_add_start,
                "cms_list": cms_handler.cms_list_menu,
                "cms_search": cms_handler.cms_search_start,
                "cms_type_*": cms_handler.cms_type_selected,
                "cms_pub_*": cms_handler.cms_publish,
                "cms_del_*": cms_handler.cms_delete,
            }
        )
    return routes


def build_analytics_action_routes(
    handler: Any, analytics_menu: AdminActionHandler
) -> AdminActionMap:
    return {
        "analytics_view_trending": handler.view_trending,
        "analytics_view_underperforming": handler.view_underperforming,
        "analytics_view_weapon_stats": handler.view_weapon_stats,
        "analytics_search_attachment": handler.search_attachment_stats,
        "analytics_cohort_analysis": handler.analytics_cohort_analysis,
        "analytics_funnel_analysis": handler.analytics_funnel_analysis,
        "analytics_daily_report": handler.daily_report,
        "analytics_download_report": handler.download_report,
        "attachment_analytics": analytics_menu,
        "analytics_*": analytics_menu,
    }


def build_health_action_routes(
    handler: Any, data_health_menu: AdminActionHandler
) -> AdminActionMap:
    return {
        "health_run_check": handler.run_health_check,
        "health_view_full_report": handler.view_full_report,
        "health_view_critical": handler.view_critical,
        "health_view_warnings": handler.view_warnings,
        "health_view_detailed_stats": handler.view_detailed_stats,
        "health_view_check_history": handler.view_check_history,
        "health_fix_missing_images": handler.fix_missing_images,
        "health_fix_duplicate_codes": handler.fix_duplicate_codes,
        "health_fix_orphaned": handler.fix_orphaned,
        "health_fix_technical": handler.fix_technical,
        "health_restore_backup": handler.restore_backup_start,
        "admin_restore_backup": handler.restore_backup_start,
        "restore_backup": handler.restore_backup_start,
        "health_create_backup": handler.create_backup,
        "health_fix_issues_menu": handler.fix_issues_menu,
        "fix_issues_menu": handler.fix_issues_menu,
        "data_health": data_health_menu,
        "health_*": data_health_menu,
    }


def build_feedback_action_routes(handler: Any) -> AdminActionMap:
    return {
        "fb_dashboard": handler.show_feedback_dashboard,
        "fb_change_period": handler.change_period,
        "fb_period_*": handler.set_period,
        "fb_toggle_suggested": handler.toggle_suggested_only,
        "fb_top": handler.show_top_attachments,
        "fb_bottom": handler.show_bottom_attachments,
        "fb_comments": handler.show_user_comments,
        "fb_comments_page_*": handler.show_user_comments,
        "fb_trend": handler.show_weekly_trend,
        "fb_search": handler.show_search_menu,
        "fb_search_q_*": handler.execute_search_query,
        "fb_filter_mode": handler.filter_mode_menu,
        "fb_mode_*": handler.set_mode_filter,
        "fb_filter_category": handler.filter_category_menu,
        "fb_cat_*": handler.set_category_filter,
        "fb_*": handler.show_feedback_dashboard,
    }


def build_admin_management_action_routes(handler: Any) -> AdminActionMap:
    return {
        "selrole_*": handler.add_admin_role_selected,
        "edit_admin_role": handler.edit_admin_role_start,
        "view_roles": handler.view_roles_menu,
        "remove_admin": handler.remove_admin_start,
        "editadm_*": handler.edit_admin_role_select,
        "addrole_*": handler.add_role_to_admin,
        "newrole_*": handler.add_role_confirm,
        "delrole_*": handler.delete_role_from_admin,
        "delconfirm_*": handler.delete_role_confirm,
        "remove_*": handler.remove_admin_confirmed,
        "remove_confirm_*": handler.remove_admin_confirmed,
    }


def build_user_management_action_routes(handler: Any) -> AdminActionMap:
    return {
        "admin_users": handler.user_mgmt_menu,
        "um_list": handler.user_list,
        "um_page_*": handler.user_list,
        "um_search": handler.user_search_start,
        "um_filter_banned": handler.user_filter_banned,
        "um_detail_*": handler.user_detail,
        "um_ban_*": handler.user_ban_start,
        "um_unban_*": handler.user_unban,
    }
