"""
Application Factory Pattern

⚠️ این فایل setup_handlers() را از main.py به ساختار modular تبدیل می‌کند
⚠️ هیچ logic تغییر نکرده - فقط ساختار بهتر شده است
"""

import os
import logging
from telegram.ext import Application, ApplicationBuilder

from config.config import BOT_TOKEN, SUPER_ADMIN_ID
from core.database.database_adapter import get_database_adapter

# Import registries
from .registry.user_registry import UserHandlerRegistry
from .registry.admin_registry import AdminHandlerRegistry
from .registry.contact_registry import ContactHandlerRegistry
from .registry.other_handlers_registry import OtherHandlersRegistry
from .registry.inline_registry import InlineHandlerRegistry


logger = logging.getLogger(__name__)


class BotApplicationFactory:
    """
    Factory برای ساخت و راه‌اندازی Telegram Application
    
    ⚠️ این کلاس setup_handlers() را از CODMAttachmentsBot جدا می‌کند
    ⚠️ منطق دقیقاً یکسان است، فقط سازماندهی بهتر شده
    """
    
    def __init__(self, bot_instance):
        """
        Args:
            bot_instance: Instance of CODMAttachmentsBot
        """
        self.bot = bot_instance
        self.application = None
        self.db = bot_instance.db
    

    def setup_handlers(self):
        """
        راه‌اندازی تمام handlers - جایگزین setup_handlers() در main.py
        
        ⚠️ این تابع دقیقاً همان کار setup_handlers() قدیمی را انجام می‌دهد
        ⚠️ فقط از registries استفاده می‌کند به جای کد inline
        """
        if not self.application:
            raise RuntimeError("Application must be created first. Call create_application()")
        
        logger.info("Setting up handlers...")
        
        # ثبت User handlers - کپی از main.py خط 121-176
        logger.info("Registering user handlers...")
        self.bot.user_registry = UserHandlerRegistry(self.application, self.db)
        self.bot.user_registry.register()
        
        # ثبت Admin handlers - کپی از main.py خط 178-676
        logger.info("Registering admin handlers...")
        self.bot.admin_registry = AdminHandlerRegistry(self.application, self.db)
        self.bot.admin_registry.register()
        
        # ثبت Contact handlers - کپی از main.py خط 678-729
        logger.info("Registering contact handlers...")
        self.bot.contact_registry = ContactHandlerRegistry(self.application, self.db)
        self.bot.contact_registry.register()
        
        # ثبت Other handlers (channel, user_attachments, tracking, error) - main.py خط 731-848
        logger.info("Registering other handlers (channel, attachments, tracking)...")
        other_registry = OtherHandlersRegistry(self.application, self.db, self.bot)
        other_registry.register()
        inline_registry = InlineHandlerRegistry(self.application, self.db, self.bot)
        inline_registry.register()

        logger.info(" All handlers registered successfully")
    
