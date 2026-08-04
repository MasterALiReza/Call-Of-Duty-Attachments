"""
هندلرهای مدیریت کانال‌های اجباری برای ادمین‌ها
"""

from core.audit import AuditLogger
from core.context import CustomContext
from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from handlers.admin.admin_handlers_modular import AdminHandlers
from utils.language import get_user_lang
from utils.i18n import t
from utils.telegram_safety import safe_edit_message_text
from handlers.channel.stats_handlers import (
    show_single_channel_stats_impl,
    show_channel_stats_impl,
    show_funnel_analysis_impl,
    show_period_report_impl,
    export_analytics_csv_impl,
    show_channel_history_impl,
)
from handlers.channel.diagnostics_handlers import test_channel_access_impl
from handlers.channel.reorder_handlers import (
    reorder_channels_menu_impl,
    handle_move_channel_impl,
)
from handlers.channel.details_handlers import (
    view_channel_details_impl,
    toggle_channel_status_impl,
)
from handlers.channel.management_actions import (
    clear_channels_impl,
)
from handlers.channel.add_handlers import (
    add_channel_start_impl,
    add_channel_id_impl,
    use_default_title_impl,
    add_channel_title_impl,
    add_channel_url_impl,
    save_channel_confirm_impl,
)
from handlers.channel.edit_handlers import (
    edit_channel_start_impl,
    edit_channel_select_impl,
    edit_channel_field_impl,
    edit_channel_value_impl,
)
from handlers.channel.delete_handlers import (
    delete_channel_start_impl,
    delete_channel_confirm_impl,
    delete_channel_execute_impl,
)
from handlers.channel.menu_helpers import (
    noop_cb_impl,
    handle_page_navigation_impl,
)
from handlers.channel.menu_handlers import channel_management_menu_impl
from handlers.channel.permissions import check_channel_management_permission_impl
from handlers.channel.navigation_handlers import (
    cancel_impl,
    return_to_admin_menu_impl,
)

# حالت‌های مدیریت کانال
CHANNEL_MENU = "CHANNEL_MENU"
ADD_CHANNEL_ID = "ADD_CHANNEL_ID"
ADD_CHANNEL_TITLE = "ADD_CHANNEL_TITLE"
ADD_CHANNEL_URL = "ADD_CHANNEL_URL"
ADD_CHANNEL_CONFIRM = "ADD_CHANNEL_CONFIRM"
EDIT_CHANNEL_SELECT = "EDIT_CHANNEL_SELECT"
EDIT_CHANNEL_FIELD = "EDIT_CHANNEL_FIELD"
EDIT_CHANNEL_VALUE = "EDIT_CHANNEL_VALUE"
DELETE_CHANNEL_CONFIRM = "DELETE_CHANNEL_CONFIRM"
REORDER_CHANNELS = "REORDER_CHANNELS"

audit_logger = AuditLogger()


async def check_channel_management_permission(
    user_id: int, context: CustomContext
) -> bool:
    """بررسی دسترسی مدیریت کانال‌ها با استفاده از RBAC."""
    return await check_channel_management_permission_impl(user_id, context)


# تنظیمات Pagination
async def audit_channel_permission_denied(user_id: int) -> None:
    """Record unauthorized channel-management access attempts."""
    await audit_logger.log_permission_decision(
        actor_id=user_id,
        permission="MANAGE_REQUIRED_CHANNELS",
        allowed=False,
        route="channel_management",
        reason="permission_denied",
        details={"source": "channel_management_menu"},
    )


CHANNELS_PER_PAGE = 8  # تعداد کانال در هر صفحه


async def noop_cb(update: Update, context: CustomContext):
    """پاسخ به دکمه‌های بدون عملیات برای جلوگیری از خطا."""
    return await noop_cb_impl(update, context)


async def cancel(update: Update, context: CustomContext):
    """بازگشت به منوی مدیریت کانال‌ها از هر وضعیت."""
    return await cancel_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        get_lang=get_user_lang,
        translate=t,
    )


async def channel_management_menu(
    update: Update, context: CustomContext, page: int = 1
):
    """منوی اصلی مدیریت کانال‌ها (با Pagination)."""
    return await channel_management_menu_impl(
        update=update,
        context=context,
        page=page,
        check_permission=check_channel_management_permission,
        audit_permission_denied=audit_channel_permission_denied,
        get_lang=get_user_lang,
        translate=t,
        safe_edit=safe_edit_message_text,
        channels_per_page=CHANNELS_PER_PAGE,
        channel_menu_state=CHANNEL_MENU,
    )


async def clear_channels(update: Update, context: CustomContext):
    """پاک‌کردن همه کانال‌های اجباری با تایید."""
    return await clear_channels_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        channel_menu_state=CHANNEL_MENU,
    )


async def handle_page_navigation(update: Update, context: CustomContext):
    """هندلر برای navigation بین صفحات کانال‌ها."""
    return await handle_page_navigation_impl(
        update, context, channel_management_menu=channel_management_menu
    )


async def view_channel_details(
    update: Update, context: CustomContext, channel_id: str = None
):
    """نمایش جزئیات یک کانال."""
    return await view_channel_details_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        channel_menu_state=CHANNEL_MENU,
        channel_id=channel_id,
    )


async def add_channel_start(update: Update, context: CustomContext):
    """شروع فرآیند افزودن کانال جدید."""
    return await add_channel_start_impl(
        update, context, add_channel_id_state=ADD_CHANNEL_ID
    )


async def add_channel_id(update: Update, context: CustomContext):
    """دریافت آیدی کانال."""
    return await add_channel_id_impl(
        update,
        context,
        add_channel_id_state=ADD_CHANNEL_ID,
        add_channel_title_state=ADD_CHANNEL_TITLE,
    )


async def use_default_title(update: Update, context: CustomContext):
    """استفاده از نام پیش‌فرض کانال."""
    return await use_default_title_impl(
        update, context, add_channel_url_state=ADD_CHANNEL_URL
    )


async def add_channel_title(update: Update, context: CustomContext):
    """دریافت عنوان نمایشی کانال."""
    return await add_channel_title_impl(
        update,
        context,
        add_channel_title_state=ADD_CHANNEL_TITLE,
        add_channel_url_state=ADD_CHANNEL_URL,
    )


async def add_channel_url(update: Update, context: CustomContext):
    """دریافت لینک کانال و ذخیره."""
    return await add_channel_url_impl(
        update,
        context,
        add_channel_url_state=ADD_CHANNEL_URL,
        add_channel_confirm_state=ADD_CHANNEL_CONFIRM,
    )


async def save_channel_confirm(update: Update, context: CustomContext):
    """ذخیره نهایی کانال پس از تایید."""
    return await save_channel_confirm_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def edit_channel_start(update: Update, context: CustomContext):
    """شروع ویرایش کانال."""
    return await edit_channel_start_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        edit_select_state=EDIT_CHANNEL_SELECT,
    )


async def edit_channel_select(update: Update, context: CustomContext):
    """انتخاب فیلد برای ویرایش."""
    return await edit_channel_select_impl(
        update, context, edit_field_state=EDIT_CHANNEL_FIELD
    )


async def edit_channel_field(update: Update, context: CustomContext):
    """دریافت فیلد برای ویرایش."""
    return await edit_channel_field_impl(
        update, context, edit_value_state=EDIT_CHANNEL_VALUE
    )


async def edit_channel_value(update: Update, context: CustomContext):
    """ذخیره مقدار جدید."""
    return await edit_channel_value_impl(
        update,
        context,
        edit_value_state=EDIT_CHANNEL_VALUE,
        channel_menu_state=CHANNEL_MENU,
    )


async def delete_channel_start(update: Update, context: CustomContext):
    """شروع حذف کانال."""
    return await delete_channel_start_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        delete_state=DELETE_CHANNEL_CONFIRM,
    )


async def delete_channel_confirm(update: Update, context: CustomContext):
    """تایید حذف کانال."""
    return await delete_channel_confirm_impl(
        update, context, delete_state=DELETE_CHANNEL_CONFIRM
    )


async def delete_channel_execute(update: Update, context: CustomContext):
    """اجرای حذف کانال."""
    return await delete_channel_execute_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def toggle_channel_status(update: Update, context: CustomContext):
    """تغییر وضعیت فعال/غیرفعال کانال."""
    return await toggle_channel_status_impl(
        update,
        context,
        view_channel_details=view_channel_details,
        channel_menu_state=CHANNEL_MENU,
    )


async def show_single_channel_stats(update: Update, context: CustomContext):
    """نمایش آمار یک کانال خاص."""
    return await show_single_channel_stats_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        channel_menu_state=CHANNEL_MENU,
    )


async def show_channel_stats(update: Update, context: CustomContext):
    """نمایش آمار همه کانال‌های اجباری (dashboard کلی)."""
    return await show_channel_stats_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def show_funnel_analysis(update: Update, context: CustomContext):
    """نمایش تحلیل قیف تبدیل."""
    return await show_funnel_analysis_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def show_period_report(update: Update, context: CustomContext):
    """نمایش گزارش دوره‌ای (7 روز گذشته)."""
    return await show_period_report_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def export_analytics_csv(update: Update, context: CustomContext):
    """Export آمار به CSV و ارسال فایل‌ها."""
    return await export_analytics_csv_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def test_channel_access(update: Update, context: CustomContext):
    """تست دسترسی ربات به کانال."""
    return await test_channel_access_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        channel_menu_state=CHANNEL_MENU,
    )


async def reorder_channels_menu(update: Update, context: CustomContext):
    """منوی ترتیب دادن کانال‌ها."""
    return await reorder_channels_menu_impl(
        update,
        context,
        channel_management_menu=channel_management_menu,
        reorder_state=REORDER_CHANNELS,
    )


async def handle_move_channel(update: Update, context: CustomContext):
    """جابجایی کانال به بالا یا پایین."""
    return await handle_move_channel_impl(
        update,
        context,
        reorder_channels_menu=reorder_channels_menu,
        reorder_state=REORDER_CHANNELS,
    )


async def show_channel_history(update: Update, context: CustomContext):
    """نمایش تاریخچه کانال‌های حذف شده."""
    return await show_channel_history_impl(
        update, context, channel_menu_state=CHANNEL_MENU
    )


async def return_to_admin_menu(update: Update, context: CustomContext):
    """بازگشت به منوی اصلی ادمین."""
    return await return_to_admin_menu_impl(
        update,
        context,
        admin_handlers_cls=AdminHandlers,
        get_lang=get_user_lang,
        translate=t,
    )


def get_channel_management_handler():
    """ایجاد ConversationHandler برای مدیریت کانال‌ها"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                channel_management_menu, pattern="^channel_management$"
            ),
            CallbackQueryHandler(channel_management_menu, pattern="^channel_menu$"),
        ],
        states={
            CHANNEL_MENU: [
                CallbackQueryHandler(noop_cb, pattern="^noop$"),
                CallbackQueryHandler(handle_page_navigation, pattern="^ch_page_"),
                CallbackQueryHandler(view_channel_details, pattern="^view_channel_"),
                CallbackQueryHandler(toggle_channel_status, pattern="^toggle_channel_"),
                CallbackQueryHandler(
                    show_single_channel_stats, pattern="^channel_stat_"
                ),
                CallbackQueryHandler(test_channel_access, pattern="^test_channel_"),
                CallbackQueryHandler(add_channel_start, pattern="^add_channel$"),
                CallbackQueryHandler(edit_channel_start, pattern="^edit_channel$"),
                CallbackQueryHandler(delete_channel_start, pattern="^delete_channel$"),
                CallbackQueryHandler(
                    reorder_channels_menu, pattern="^reorder_channels$"
                ),
                CallbackQueryHandler(clear_channels, pattern="^clear_channels$"),
                CallbackQueryHandler(clear_channels, pattern="^clear_yes$"),
                CallbackQueryHandler(show_channel_stats, pattern="^channel_stats$"),
                CallbackQueryHandler(show_channel_history, pattern="^channel_history$"),
                # Phase 2 handlers
                CallbackQueryHandler(show_funnel_analysis, pattern="^channel_funnel$"),
                CallbackQueryHandler(
                    show_period_report, pattern="^channel_period_report$"
                ),
                CallbackQueryHandler(
                    export_analytics_csv, pattern="^channel_export_csv$"
                ),
            ],
            REORDER_CHANNELS: [
                CallbackQueryHandler(noop_cb, pattern="^noop$"),
                CallbackQueryHandler(handle_move_channel, pattern="^move_(up|down)_"),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            ADD_CHANNEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_id),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            ADD_CHANNEL_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_title),
                CallbackQueryHandler(use_default_title, pattern="^use_default_title$"),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            ADD_CHANNEL_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_url),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            ADD_CHANNEL_CONFIRM: [
                CallbackQueryHandler(save_channel_confirm, pattern="^save_channel$"),
                CallbackQueryHandler(
                    add_channel_start, pattern="^add_channel$"
                ),  # Restart
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            EDIT_CHANNEL_SELECT: [
                CallbackQueryHandler(edit_channel_select, pattern="^edit_select_"),
                CallbackQueryHandler(edit_channel_start, pattern="^edit_channel$"),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            EDIT_CHANNEL_FIELD: [
                CallbackQueryHandler(edit_channel_field, pattern="^edit_field_"),
                CallbackQueryHandler(edit_channel_start, pattern="^edit_channel$"),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            EDIT_CHANNEL_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_channel_value),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
            DELETE_CHANNEL_CONFIRM: [
                CallbackQueryHandler(delete_channel_confirm, pattern="^del_confirm_"),
                CallbackQueryHandler(delete_channel_execute, pattern="^del_yes$"),
                CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                channel_management_menu, pattern="^channel_management$"
            ),
            CallbackQueryHandler(cancel, pattern="^channel_menu$"),
            # بازگشت به منوی ادمین و پایان این مکالمه
            CallbackQueryHandler(return_to_admin_menu, pattern="^ch_admin_return$"),
            CommandHandler("cancel", cancel),
        ],
        per_message=False,
    )
