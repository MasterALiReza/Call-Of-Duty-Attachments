
"""
Typed Custom Context for python-telegram-bot
این فایل برای حل مشکل service locator در bot_data ایجاد شده است.
"""
from typing import TypedDict, Any, Optional
from telegram.ext import CallbackContext, ExtBot

class BotData(TypedDict, total=False):
    """
    مخزن نوع‌دهی شده برای `application.bot_data`
    جلوگیری از اشتباهات تایپی در کلیدها هنگام فراخوانی service locator.
    """
    database: Any  # core.database.database_pg.DatabasePostgres
    admin_handlers: Any  # handlers.admin.admin_handlers_modular.AdminHandlers
    role_manager: Any  # core.security.role_manager.RoleManager
    backup_scheduler: Any  # managers.backup_manager.BackupScheduler

class CustomContext(CallbackContext[ExtBot, dict, BotData, dict]):
    """
    شناسه Custom Context برای استفاده در تمام handler ها
    به جای CustomContext می‌توانید از این کلاس استفاده کنید 
    تا linting کامل روی bot_data داشته باشید.
    """
    pass
