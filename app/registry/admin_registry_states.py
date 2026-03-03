from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ConversationHandler
from handlers.admin.admin_states import *
from utils.i18n import build_regex_for_key, build_regex_for_keys

# لیست کلیدهای خروج سریع
EXIT_SILENT_KEYS = [
    'menu.buttons.admin',
    'menu.buttons.attachments',
    'menu.buttons.top_list',
    'menu.buttons.search',
    'menu.buttons.suggested',
    'menu.buttons.settings',
    'menu.buttons.notifications',
    'menu.buttons.help'
]

def get_admin_conversation_states(admin_handlers):
    """
    برگرداندن وضعیت‌های مکالمه ادمین
    این فایل شامل تمام روتینگ‌های پنل ادمین است
    """
    states_dict = {
        ADMIN_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_main$"),
            
            # --- Tickets & Support ---
            CallbackQueryHandler(admin_handlers.admin_tickets_menu, pattern="^admin_tickets$"),
            CallbackQueryHandler(admin_handlers.admin_tickets_list, pattern="^adm_tickets_(new|progress|waiting|resolved|all)$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_search_start, pattern="^adm_tickets_search$"),
            CallbackQueryHandler(admin_handlers.admin_tickets_filter_category, pattern="^adm_tickets_filter_category$"),
            CallbackQueryHandler(admin_handlers.admin_tickets_mine, pattern="^adm_tickets_mine$"),
            CallbackQueryHandler(admin_handlers.admin_tickets_page_navigation, pattern="^ticket_page_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_detail, pattern="^adm_ticket_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_reply_start, pattern="^adm_reply_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_view_attachments, pattern="^adm_attach_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_change_status, pattern="^adm_status_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_change_priority, pattern="^adm_priority_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_assign_start, pattern="^adm_assign_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_close, pattern="^adm_close_\\d+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_set_status, pattern="^adm_setstatus_\\d+_.+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_set_priority, pattern="^adm_setpriority_\\d+_.+$"),
            CallbackQueryHandler(admin_handlers.admin_ticket_assign_confirm, pattern="^adm_doassign_\\d+_\\d+$"),
            
            # --- FAQs & Support ---
            CallbackQueryHandler(admin_handlers.admin_faqs_menu, pattern="^admin_faqs$"),
            CallbackQueryHandler(admin_handlers.admin_faq_add_start, pattern="^adm_faq_add$"),
            CallbackQueryHandler(admin_handlers.admin_faq_list, pattern="^adm_faq_list$"),
            CallbackQueryHandler(admin_handlers.admin_faq_stats, pattern="^adm_faq_stats$"),
            CallbackQueryHandler(admin_handlers.admin_feedback_stats, pattern="^adm_feedback$"),
            CallbackQueryHandler(admin_handlers.admin_faq_set_lang, pattern="^adm_faq_lang_"),
            CallbackQueryHandler(admin_handlers.admin_faq_view, pattern="^adm_faq_view_"),
            CallbackQueryHandler(admin_handlers.admin_faq_edit, pattern="^adm_faq_edit_"),
            CallbackQueryHandler(admin_handlers.admin_faq_delete, pattern="^adm_faq_del_"),
            
            # --- Direct Contact ---
            CallbackQueryHandler(admin_handlers.admin_direct_contact_menu, pattern="^adm_direct_contact$"),
            CallbackQueryHandler(admin_handlers.direct_contact_edit_name_start, pattern="^dc_change_name$"),
            CallbackQueryHandler(admin_handlers.direct_contact_edit_link_start, pattern="^dc_change_link$"),
            CallbackQueryHandler(admin_handlers.direct_contact_toggle_status, pattern="^dc_(en|dis)able$"),

            # Fallback menu proxy — گسترش رگکس برای پوشش کالبک‌های مدیریتی
            CallbackQueryHandler(admin_handlers.admin_menu, pattern="^(admin_|adm_|gmode_|gsel_|gop_|cmm_|wmm_|wmcat_|wmwpn_|wmact_|wmconf_|text_edit_|cat_clear_|nav_back|fb_|manage_|add_|edit_|view_|role_|_admin|editadm_|addrole_|delrole_|newrole_|selrole_|delconfirm_|aconf_|dconf_|remove_|um_|notif_|sched_|tmpl_|notify_|nconf_|attachment_analytics|data_health|analytics_.*|health_.*|restore_backup|toggle_auto_backup|set_ab_interval_|fix_issues_menu)"),
        ],
        
        # ========== Attachment Management Flow ==========
        ADD_ATTACHMENT_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_attachment_category_selected, pattern="^acat_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        ADD_ATTACHMENT_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_attachment_weapon_selected, pattern="^awpn_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        ADD_ATTACHMENT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_attachment_mode_selected, pattern="^amode_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        ADD_WEAPON_NAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.Regex(build_regex_for_keys(EXIT_SILENT_KEYS)), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_attachment_new_weapon_name_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_ATTACHMENT_CODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_attachment_code_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_ATTACHMENT_NAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_attachment_name_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_ATTACHMENT_IMAGE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.PHOTO | filters.ATTACHMENT, admin_handlers.add_attachment_image_received),
            CallbackQueryHandler(admin_handlers.add_attachment_image_received, pattern="^skip_image$"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_ATTACHMENT_TOP: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_attachment_top_selected, pattern="^atop_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_attachment_top_ignore_text)
        ],
        ADD_ATTACHMENT_SEASON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_attachment_season_selected, pattern="^aseason_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_attachment_season_ignore_text)
        ],
        
        # ========== Delete Attachment ==========
        DELETE_ATTACHMENT_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.delete_attachment_category_selected, pattern="^dcat_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        DELETE_ATTACHMENT_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.delete_attachment_weapon_selected, pattern="^dwpn_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        DELETE_ATTACHMENT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.delete_attachment_mode_selected, pattern="^dmode_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        DELETE_ATTACHMENT_CODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.delete_attachment_code_selected, pattern="^delatt_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        
        # ========== Edit Attachment ==========
        EDIT_ATTACHMENT_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_attachment_category_selected, pattern="^ecat_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        EDIT_ATTACHMENT_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_attachment_weapon_selected, pattern="^ewpn_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        EDIT_ATTACHMENT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_attachment_mode_selected, pattern="^emode_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        EDIT_ATTACHMENT_SELECT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_attachment_selected, pattern="^edatt_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        EDIT_ATTACHMENT_ACTION: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_attachment_action_selected, pattern="^edact_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        EDIT_ATTACHMENT_NAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.edit_attachment_name_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        EDIT_ATTACHMENT_IMAGE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.PHOTO | filters.ATTACHMENT, admin_handlers.edit_attachment_image_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        EDIT_ATTACHMENT_CODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.edit_attachment_code_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Top Attachments ==========
        SET_TOP_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.set_top_category_selected, pattern="^tcat_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        SET_TOP_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.set_top_weapon_selected, pattern="^twpn_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SET_TOP_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.set_top_mode_selected, pattern="^tmode_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SET_TOP_ATTACHMENT: [
             MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
             CallbackQueryHandler(admin_handlers.set_top_attachment_selected, pattern="^tatt_"),
             CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SET_TOP_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.set_top_confirm_answer, pattern="^top_ans_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SET_TOP_SAVE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.set_top_confirm_save, pattern="^top_save_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        
        # ========== Suggested Attachments ==========
        MANAGE_SUGGESTED_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_add_start, pattern="^sugg_add$"),
            CallbackQueryHandler(admin_handlers.suggested_remove_start, pattern="^sugg_remove$"),
            CallbackQueryHandler(admin_handlers.suggested_view_list, pattern="^sugg_list$"),
            CallbackQueryHandler(admin_handlers.suggested_analytics_menu, pattern="^sugg_analytics$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        SUGGESTED_ADD_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_mode_selected, pattern="^samode_"),
            CallbackQueryHandler(admin_handlers.manage_suggested_menu, pattern="^admin_manage_suggested$")
        ],
        SUGGESTED_ADD_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_category_selected, pattern="^sacat_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SUGGESTED_ADD_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_weapon_selected, pattern="^sawpn_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SUGGESTED_ADD_ATTACHMENT: [
             MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
             CallbackQueryHandler(admin_handlers.suggested_attachment_selected, pattern="^saatt_"),
             CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        SUGGESTED_REMOVE_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_remove_mode_selected, pattern="^srmode_"),
            CallbackQueryHandler(admin_handlers.manage_suggested_menu, pattern="^admin_manage_suggested$")
        ],
        SUGGESTED_REMOVE_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.suggested_delete_confirmed, pattern="^sdel_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        
        # ========== Notifications ==========
        NOTIFY_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.notify_compose_start, pattern="^notify_compose$"),
            CallbackQueryHandler(admin_handlers.notify_schedule_menu, pattern="^notif_schedule$"),
            CallbackQueryHandler(admin_handlers.notify_settings_menu, pattern="^notif_settings$"),
            CallbackQueryHandler(admin_handlers.schedules_menu, pattern="^notif_active_schedules$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        NOTIFY_COMPOSE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, admin_handlers.notify_compose_received),
            CallbackQueryHandler(admin_handlers.notify_home_menu, pattern="^admin_notify$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        NOTIFY_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.notify_confirm_selected, pattern="^nconf_"),
            CallbackQueryHandler(admin_handlers.notify_confirm_selected, pattern="^notify_confirm$"),
            CallbackQueryHandler(admin_handlers.notify_schedule_menu, pattern="^notify_schedule$"),
            CallbackQueryHandler(admin_handlers.notify_home_menu, pattern="^notify_home$"),
            CallbackQueryHandler(admin_handlers.notify_compose_start, pattern="^notify_compose$")
        ],
        NOTIFY_SCHEDULE_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.notify_schedule_preset_selected, pattern="^nsched_"),
            CallbackQueryHandler(admin_handlers.notify_home_menu, pattern="^admin_notify$")
        ],
        NOTIFY_SCHEDULE_TIME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.notify_schedule_preset_selected), # Custom time input
            CallbackQueryHandler(admin_handlers.notify_schedule_menu, pattern="^notif_schedule$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        NOTIFY_SETTINGS: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.notify_toggle, pattern="^ntog_"),
            CallbackQueryHandler(admin_handlers.notify_home_menu, pattern="^admin_notify$")
        ],
        SCHEDULED_NOTIFS_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.schedule_toggle, pattern="^stog_"),
            CallbackQueryHandler(admin_handlers.schedule_delete, pattern="^sdel_"),
            CallbackQueryHandler(admin_handlers.schedule_edit_open, pattern="^sedit_"),
            CallbackQueryHandler(admin_handlers.notify_home_menu, pattern="^admin_notify$")
        ],
        EDIT_SCHEDULE_OPEN: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.schedule_edit_text_start, pattern="^setxt_"),
            CallbackQueryHandler(admin_handlers.schedules_menu, pattern="^notif_active_schedules$")
        ],
        EDIT_SCHEDULE_TEXT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.schedule_edit_text_received),
            CallbackQueryHandler(admin_handlers.schedules_menu, pattern="^notif_active_schedules$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Data Management ==========
        DATA_MGMT_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.health_handler.create_backup, pattern="^admin_create_backup$"),
            CallbackQueryHandler(admin_handlers.auto_backup_menu, pattern="^admin_auto_backup_menu$"),
            CallbackQueryHandler(admin_handlers.health_handler.restore_backup_start, pattern="^restore_backup$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        AUTO_BACKUP_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.toggle_auto_backup, pattern="^toggle_auto_backup$"),
            CallbackQueryHandler(admin_handlers.set_auto_backup_interval, pattern="^set_ab_interval_"),
            CallbackQueryHandler(admin_handlers.data_management_menu, pattern="^admin_data_management$")
        ],
        AWAITING_BACKUP_FILE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.Document.ALL, admin_handlers.health_handler.restore_backup_file),
            CallbackQueryHandler(admin_handlers.health_handler.fix_issues_menu, pattern="^admin_data_management$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        IMPORT_START: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        IMPORT_FILE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.Document.ALL, admin_handlers.import_file_received),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        IMPORT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.import_mode_selected, pattern="^imp_mode_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        EXPORT_START: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.export_type_selected, pattern="^exp_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        
        # ========== Admin Management ==========
        MANAGE_ADMINS: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_admin_start, pattern="^add_new_admin$"),
            CallbackQueryHandler(admin_handlers.edit_admin_role_start, pattern="^edit_admin_role$"),
            CallbackQueryHandler(admin_handlers.remove_admin_start, pattern="^remove_admin$"),
            CallbackQueryHandler(admin_handlers.view_all_admins, pattern="^view_all_admins$"),
            CallbackQueryHandler(admin_handlers.view_roles_menu, pattern="^view_roles$"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        ADD_ADMIN_ROLE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_admin_role_selected, pattern="^selrole_"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        ADD_ADMIN_ID: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_admin_id_received),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_ADMIN_DISPLAY_NAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_admin_display_name_received),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        REMOVE_ADMIN_ID: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.remove_admin_confirmed, pattern="^remove_"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        EDIT_ADMIN_SELECT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.edit_admin_role_select, pattern="^editadm_$"), # pattern fix for single admin select if needed
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        ADD_ROLE_SELECT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_role_to_admin, pattern="^addrole_"),
            CallbackQueryHandler(admin_handlers.delete_role_from_admin, pattern="^delrole_"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        ADD_ROLE_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.add_role_confirm, pattern="^newrole_"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        DELETE_ROLE_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.delete_role_confirm, pattern="^delconfirm_"),
            CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        VIEW_ROLES: [
             MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
             CallbackQueryHandler(admin_handlers.manage_admins_menu, pattern="^manage_admins$")
        ],
        
        # ========== Support (FAQs & Tickets) ==========
        ADMIN_FAQS_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_faq_add_start, pattern="^adm_faq_add$"),
            CallbackQueryHandler(admin_handlers.admin_faq_list, pattern="^adm_faq_list$"),
            CallbackQueryHandler(admin_handlers.admin_faq_stats, pattern="^adm_faq_stats$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        ADD_FAQ_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_faq_category_selected, pattern="^adm_faq_cat_"),
            CallbackQueryHandler(admin_handlers.admin_faqs_menu, pattern="^admin_faqs$")
        ],
        ADD_FAQ_QUESTION: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_faq_question_received),
            CallbackQueryHandler(admin_handlers.admin_faq_set_lang, pattern="^adm_faq_lang_"),
            CallbackQueryHandler(admin_handlers.admin_faqs_menu, pattern="^admin_faqs$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        ADD_FAQ_ANSWER: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_faq_answer_received),
            CallbackQueryHandler(admin_handlers.admin_faq_set_lang, pattern="^adm_faq_lang_"),
            CallbackQueryHandler(admin_handlers.admin_faqs_menu, pattern="^admin_faqs$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        EDIT_FAQ_SELECT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_faq_edit_field_select, pattern="^edit_faq_"),
            CallbackQueryHandler(admin_handlers.admin_faq_view, pattern="^adm_faq_view_"),
            CallbackQueryHandler(admin_handlers.admin_faqs_menu, pattern="^admin_faqs$")
        ],
        EDIT_FAQ_QUESTION: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_faq_edit_question_received),
            CallbackQueryHandler(admin_handlers.admin_faq_edit, pattern="^adm_faq_edit_"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        EDIT_FAQ_ANSWER: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_faq_edit_answer_received),
            CallbackQueryHandler(admin_handlers.admin_faq_edit, pattern="^adm_faq_edit_"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        TICKET_REPLY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_ticket_reply_received),
            CallbackQueryHandler(admin_handlers.admin_tickets_menu, pattern="^admin_tickets$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        TICKET_SEARCH: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.admin_ticket_search_received),
            CallbackQueryHandler(admin_handlers.admin_tickets_menu, pattern="^admin_tickets$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Direct Contact ==========
        DIRECT_CONTACT_NAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.direct_contact_name_received),
            CallbackQueryHandler(admin_handlers.admin_direct_contact_menu, pattern="^adm_direct_contact$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        DIRECT_CONTACT_LINK: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.direct_contact_link_received),
            CallbackQueryHandler(admin_handlers.admin_direct_contact_menu, pattern="^adm_direct_contact$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Guides ==========
        GUIDES_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.guides_mode_selected, pattern="^guide_mode_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        GUIDES_SECTION: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.guide_section_menu, pattern="^gsection_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        GUIDE_OP_ROUTER: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.guide_op_router, pattern="^gop_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        GUIDE_RENAME: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.guide_rename_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        GUIDE_MEDIA_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.guide_media_confirmed, pattern="^gmedconf_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        GUIDE_PHOTO: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.PHOTO & ~filters.COMMAND, admin_handlers.guide_photo_received),
            CallbackQueryHandler(admin_handlers.guide_op_router, pattern="^gop_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        GUIDE_VIDEO: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.VIDEO & ~filters.COMMAND, admin_handlers.guide_video_received),
            CallbackQueryHandler(admin_handlers.guide_op_router, pattern="^gop_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        GUIDE_CODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.guide_code_received),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Category Mgmt (Toggle/Clear) ==========
        CATEGORY_MGMT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.category_mode_selected, pattern="^cmm_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        CATEGORY_MGMT_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.category_toggle_selected, pattern="^adm_cat_toggle_"),
            CallbackQueryHandler(admin_handlers.category_clear_prompt, pattern="^adm_cat_clear_"),
            CallbackQueryHandler(admin_handlers.category_clear_confirm, pattern="^cat_clear_confirm$"),
            CallbackQueryHandler(admin_handlers.category_clear_cancel, pattern="^cat_clear_cancel$"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        
        # ========== Weapon Mgmt (Stats/Toggle/Delete) ==========
        WEAPON_SELECT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_mode_selected, pattern="^wmm_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        WEAPON_SELECT_CATEGORY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_select_category_menu, pattern="^(wmcat_|nav_back)"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        WEAPON_SELECT_WEAPON: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_select_weapon_menu, pattern="^(wmwpn_|nav_back)"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        WEAPON_ACTION_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_action_selected, pattern="^wmact_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        WEAPON_DELETE_CONFIRM: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_delete_confirmed, pattern="^wmconf_"),
            CallbackQueryHandler(admin_handlers.handle_navigation_back, pattern="^nav_back$")
        ],
        
        # ========== Text Edit & CMS ==========
        TEXT_EDIT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.text_edit_received),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        CMS_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_menu, pattern="^cms_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        CMS_ADD_TYPE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.cms_type_selected, pattern="^cms_type_"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$|^admin_cms$")
        ],
        CMS_ADD_TITLE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.cms_title_received),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$|^admin_cms$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        CMS_ADD_BODY: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.cms_body_received),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$|^admin_cms$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        CMS_SEARCH_TEXT: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.cms_search_received),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$|^admin_cms$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input)
        ],
        
        # ========== System / Data Management ==========
        IMPORT_FILE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.Document.ALL, admin_handlers.import_file_received),
            CallbackQueryHandler(admin_handlers.admin_menu, pattern="^(attachment_analytics|data_health|analytics_.*|health_.*|admin_notify)$"),
            MessageHandler(filters.ALL, admin_handlers.handle_invalid_input)
        ],
        IMPORT_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.import_mode_selected, pattern="^import_merge$|^import_replace$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        EXPORT_START: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.export_type_selected, pattern="^export_json$|^export_csv$|^export_backup$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$|^admin_data_management$")
        ],
        
        # ========== Analytics ==========
        ANALYTICS_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.view_trending, pattern="^analytics_trending$"),
            CallbackQueryHandler(admin_handlers.view_underperforming, pattern="^analytics_underperforming$"),
            CallbackQueryHandler(admin_handlers.view_weapon_stats, pattern="^analytics_weapon_stats$"),
            CallbackQueryHandler(admin_handlers.view_user_behavior, pattern="^analytics_user_behavior$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        WEAPON_STATS_MODE: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.weapon_stats_select_mode, pattern="^wstats_mode_"),
            CallbackQueryHandler(admin_handlers.analytics_menu, pattern="^analytics_menu$")
        ],
        USER_BEHAVIOR_DETAILS: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.user_behavior_details, pattern="^ub_"),
            CallbackQueryHandler(admin_handlers.analytics_menu, pattern="^analytics_menu$")
        ],
        SEARCH_ATTACHMENT_DETAILS: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.handle_search_text),
            CallbackQueryHandler(admin_handlers.analytics_menu, pattern="^analytics_menu$"),
            MessageHandler(filters.ALL, admin_handlers.handle_invalid_input)
        ],
        
        # ========== Data Health ==========
        DATA_HEALTH_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.run_health_check, pattern="^run_health_check$"),
            CallbackQueryHandler(admin_handlers.view_full_report, pattern="^view_full_report$"),
            CallbackQueryHandler(admin_handlers.fix_issues_menu, pattern="^fix_issues_menu$"),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_cancel$")
        ],
        FIX_ISSUES_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.fix_missing_images, pattern="^fix_missing_images$"),
            CallbackQueryHandler(admin_handlers.fix_duplicate_codes, pattern="^fix_duplicate_codes$"),
            CallbackQueryHandler(admin_handlers.fix_orphaned, pattern="^fix_orphaned$"),
            CallbackQueryHandler(admin_handlers.data_health_menu, pattern="^data_health$")
        ],
        
        # ========== User Management ==========
        USER_MGMT_MENU: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.admin_menu_return, pattern="^admin_main$"),
            CallbackQueryHandler(admin_handlers.user_list, pattern="^um_list$"),
            CallbackQueryHandler(admin_handlers.user_search_start, pattern="^um_search$"),
            CallbackQueryHandler(admin_handlers.user_filter_banned, pattern="^um_filter_banned$"),
        ],
        USER_MGMT_LIST: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.user_list, pattern="^um_page_\\d+$"),
            CallbackQueryHandler(admin_handlers.user_detail, pattern="^um_detail_\\d+$"),
            CallbackQueryHandler(admin_handlers.user_search_start, pattern="^um_search$"),
            CallbackQueryHandler(admin_handlers.user_mgmt_menu, pattern="^admin_users$"),
            CallbackQueryHandler(admin_handlers.user_list, pattern="^um_noop$"),
        ],
        USER_MGMT_SEARCH: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.user_search_received),
            CallbackQueryHandler(admin_handlers.user_mgmt_menu, pattern="^admin_users$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input),
        ],
        USER_MGMT_DETAIL: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            CallbackQueryHandler(admin_handlers.user_ban_start, pattern="^um_ban_\\d+$"),
            CallbackQueryHandler(admin_handlers.user_unban, pattern="^um_unban_\\d+$"),
            CallbackQueryHandler(admin_handlers.user_list, pattern="^um_list$"),
            CallbackQueryHandler(admin_handlers.user_mgmt_menu, pattern="^admin_users$"),
        ],
        USER_MGMT_BAN: [
            MessageHandler(filters.Regex(build_regex_for_key('menu.buttons.admin')), admin_handlers.admin_menu_return),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.user_ban_confirm),
            CallbackQueryHandler(admin_handlers.user_mgmt_menu, pattern="^admin_users$"),
            MessageHandler(filters.ALL & ~filters.COMMAND, admin_handlers.handle_invalid_input),
        ],
    }
    return states_dict
