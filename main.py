#!/usr/bin/env python3
"""
ربات تلگرام مدیریت اتچمنت‌های Call of Duty Mobile
نسخه 1.0
"""

import logging
import signal
import sys
import asyncio
import selectors
import os
import pathlib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Log Proxy Settings (helpful for debugging httpx.ConnectError)
import urllib.request
def log_proxies():
    # Check OS environment variables
    env_proxies = {k: v for k, v in os.environ.items() if 'proxy' in k.lower()}
    # Check system level proxies (Registry on Windows, etc.)
    system_proxies = urllib.request.getproxies()
    
    if env_proxies or system_proxies:
        print("🌐 [DEBUG] Proxy Settings Detected:")
        if env_proxies:
            print("   - Environment Variables:")
            for k, v in env_proxies.items():
                print(f"     * {k}: {v}")
        if system_proxies:
            print("   - System/Registry Proxies:")
            for k, v in system_proxies.items():
                print(f"     * {k}: {v}")
        print("💡 Hint: If connection fails, try setting BOT_PROXY_URL=NONE in .env to force direct connection.")
    else:
        print("🌐 [DEBUG] No proxy detected in environment or system settings.")

log_proxies()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

# Additional imports
from config.config import BOT_TOKEN, SUPER_ADMIN_ID, BACKUP_DIR, BOT_MODE, WEBHOOK_URL, WEBHOOK_PORT, WEBHOOK_PATH, WEBHOOK_SECRET_TOKEN, WEBHOOK_CERT_PATH, WEBHOOK_KEY_PATH
from core.database.database_adapter import get_database_adapter
from handlers.admin.admin_handlers_modular import AdminHandlers
from core.cache.cache_manager import cache_cleanup_task
from managers.notification_scheduler import NotificationScheduler
from managers.backup_scheduler import BackupScheduler
from handlers.contact.contact_handlers import ContactHandlers
from utils.subscribers_pg import SubscribersPostgres as Subscribers
from handlers.user.modules.feedback.feedback_handler import FeedbackHandler
from utils.error_handler import error_handler
from core.subscribers import register_all_subscribers
from core.monitoring.health_server import HealthServer
from core.monitoring.alerts import AlertSystem
from core.container import get_container

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



class CODMAttachmentsBot:
    """کلاس اصلی ربات مدیریت اتچمنت‌های CODM"""
    
    def __init__(self):
        """راه‌اندازی اولیه ربات"""
        # Register global event subscribers
        register_all_subscribers()
        
        self.container = get_container()
        self.db = self.container.db
        
        self.admin_handlers = AdminHandlers(self.db)
        self.contact_handlers = ContactHandlers(self.db)
        self.feedback_handler = FeedbackHandler(self.db)
        
        # Populate handlers in container for decoupled access
        container = get_container()
        container.admin = self.admin_handlers
        container.contact = self.contact_handlers
        container.feedback_handler = self.feedback_handler
        self.notification_scheduler = NotificationScheduler(self.db)
        self.backup_scheduler = BackupScheduler(self.db)
        
        # Link schedulers to container for global access
        self.container.notification_scheduler = self.notification_scheduler
        self.container.backup_scheduler = self.backup_scheduler
        
        self.health_server = self.container.health_server
        self.alert_system = None # Will be initialized in post_init once application is ready
        self.application = None
        self.is_shutting_down = False
        logger.info("CODMAttachmentsBot initialized with ServiceContainer")
    
    def setup_handlers(self):
        """
        راه‌اندازی هندلرهای ربات
        
        این تابع الان از Factory Pattern استفاده می‌کند
        تمام handler registrations به app/registry/ منتقل شده‌اند
        منطق دقیقاً یکسان است - فقط ساختار بهتر شده
        
        قبل: 730+ خط handler registration در این تابع
        بعد: 5 خط - استفاده از Factory و Registries
        """
        from app.factory import BotApplicationFactory
        
        factory = BotApplicationFactory(self)
        factory.application = self.application  # استفاده از application موجود
        factory.setup_handlers()  # تمام registrations را انجام می‌دهد (کپی دقیق از کد قبلی)
    
    async def handle_error(self, update: Update, context):
        """مدیریت خطاها با سیستم جدید"""
        await error_handler.handle_telegram_error(update, context, context.error)

    async def track_user_interaction(self, update: Update, context):
        """
        رهگیری تعامل کاربر برای به‌روزرسانی last_seen
        این متد برای تمام پیام‌ها و callbackها فراخوانی می‌شود
        """
        if not update.effective_user:
            return
        
        # Guard against recursion
        if context.user_data.get('_tracking'):
            return
        context.user_data['_tracking'] = True
            
        user = update.effective_user
        try:
            if hasattr(self.db, 'upsert_user'):
                await self.db.upsert_user(user.id, user.username, user.first_name)
        except Exception as e:
            logger.debug(f"Failed to track user interaction: {e}")
        finally:
            context.user_data.pop('_tracking', None)
    
    async def post_init(self, application):
        """اجرا بعد از راه‌اندازی ربات"""
        logger.info("CODM Attachments Bot started successfully!")
        
        # Start async database pool
        try:
            await self.db.initialize()
            # Ensure audit logs table is constructed
            from core.audit import AuditLogger
            await AuditLogger().create_table_if_not_exists()
            
            # Initialize RoleManager
            if hasattr(self.admin_handlers, 'role_manager'):
                await self.admin_handlers.role_manager.initialize()
                
            # Initialize Analytics (Postgres)
            try:
                from utils.analytics_pg import AnalyticsPostgres
                await AnalyticsPostgres(db_adapter=self.db).initialize()
                logger.info("✅ Analytics schema verified in post_init")
            except Exception as e:
                logger.error(f"❌ Failed to initialize analytics: {e}")
            
            # Initialize Subscribers (Postgres)
            try:
                from utils.subscribers_pg import SubscribersPostgres
                await SubscribersPostgres(db_adapter=self.db).initialize()
                logger.info("✅ Subscribers schema verified in post_init")
            except Exception as e:
                logger.error(f"❌ Failed to initialize subscribers: {e}")
                
            logger.info("✅ Async Database Connection Pool & RoleManager Opened")
        except Exception as e:
            logger.error(f"Failed to start Postgres Database Async Pool: {e}")
        if hasattr(self, 'user_registry') and self.user_registry and hasattr(self.user_registry, 'initialize'):
            await self.user_registry.initialize()
            
        # Start notification scheduler
        try:
            await self.notification_scheduler.start(application)
            self.health_server.schedulers.append(self.notification_scheduler)
            logger.info("Notification scheduler started in post_init")
        except Exception as e:
            logger.error(f"Failed to start notification scheduler: {e}")
        # Start backup scheduler
        try:
            await self.backup_scheduler.start(application)
            self.health_server.schedulers.append(self.backup_scheduler)
            # Store scheduler in bot_data for handlers
            application.bot_data['backup_scheduler'] = self.backup_scheduler
            logger.info("Backup scheduler started in post_init")
        except Exception as e:
            logger.error(f"Failed to start backup scheduler: {e}")
        # Start Cache Cleanup Task for periodic cache expiration cleanup
        try:
            asyncio.create_task(cache_cleanup_task())
            logger.info("Cache cleanup task started in post_init")
        except Exception as e:
            logger.warning(f"Failed to start cache cleanup task: {e}")

        # Start Health Server
        try:
            await self.health_server.start()
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")

        # Start Alert System
        try:
            from core.monitoring.alerts import AlertSystem
            self.alert_system = AlertSystem(application.bot, self.db)
            self.container.alert_system = self.alert_system # Map to container
            asyncio.create_task(self.alert_system.check_and_alert())
            logger.info("Monitoring alert system started in post_init")
        except Exception as e:
            logger.error(f"Failed to start alert system: {e}")
    
    async def cleanup(self):
        """
        پاکسازی منابع و بستن کانکشن‌ها
        این متد باید idempotent باشد (چند بار صدا زدنش مشکلی ایجاد نکند)
        """
        if self.is_shutting_down:
            return
            
        self.is_shutting_down = True
        logger.info("🛑 Initiating graceful cleanup...")
        
        try:
            # 1. Stop scheduler
            if hasattr(self, 'notification_scheduler') and self.notification_scheduler:
                try:
                    await self.notification_scheduler.stop()
                    logger.info("✅ Notification scheduler stopped")
                except Exception as e:
                    logger.warning(f"Failed to stop notification scheduler: {e}")

            # 1.5. Stop backup scheduler
            if hasattr(self, 'backup_scheduler') and self.backup_scheduler:
                try:
                    if hasattr(self.application, 'job_queue'):
                        await self.backup_scheduler.stop(self.application)
                        logger.info("✅ Backup scheduler stopped")
                except Exception as e:
                    logger.warning(f"Failed to stop backup scheduler: {e}")

            # 2. Flush pending notifications
            if hasattr(self, 'notification_manager') and self.notification_manager:
                try:
                    logger.info("📤 Flushing pending notifications...")
                    await asyncio.wait_for(
                        self.notification_manager.process_pending_notifications(),
                        timeout=5.0
                    )
                    logger.info("✅ Notifications flushed")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Notification flush timed out")
                except Exception as e:
                    logger.error(f"❌ Error flushing notifications: {e}")
            
            # 2.5 Stop Monitoring
            if hasattr(self, 'health_server') and self.health_server:
                await self.health_server.stop()
            if hasattr(self, 'alert_system') and self.alert_system:
                self.alert_system.stop()

            # 3. Close database connections
            if hasattr(self, 'db') and self.db:
                try:
                    if hasattr(self.db, 'close'):
                        await self.db.close()
                        logger.info("✅ Database pool closed")
                except Exception as e:
                    logger.error(f"❌ Error closing database: {e}")
            
            # 4. Stop the application if running
            if self.application and self.application.running:
                try:
                    logger.info("🛑 Stopping application...")
                    await self.application.stop()
                    logger.info("✅ Application stopped")
                except Exception as e:
                    logger.error(f"❌ Error stopping application: {e}")
            
            logger.info("✅ Cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

    async def post_shutdown(self, application):
        """تابع اجرایی بعد از shutdown application"""
        logger.info("Application shutdown hook called")
        await self.cleanup()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"🛑 Received {signal_name} signal")
        
        if self.application:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.cleanup())
            else:
                loop.run_until_complete(self.cleanup())
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        # Windows supports SIGINT and SIGBREAK
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # SIGTERM is available on Windows but less common
        try:
            signal.signal(signal.SIGTERM, self.signal_handler)
        except AttributeError:
            pass  # SIGTERM not available on this platform
        
        logger.info("✅ Signal handlers configured")
    
    def run(self):
        """اجرای ربات با پشتیبانی از Polling و Webhook"""
        logger.info("Starting bot...")
        
        # Set a new event loop for Windows compatibility with psycopg and general robustness
        if sys.platform == 'win32':
            # Use SelectorEventLoop on Windows because ProactorEventLoop is incompatible with psycopg3 async mode
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger.info("Windows SelectorEventLoop set")
        
        # Setup signal handlers
        self.setup_signal_handlers()
        
        # ساخت Application با تنظیمات شبکه هوشمند
        from telegram.ext import ApplicationBuilder
        from telegram.request import HTTPXRequest
        
        # دریافت تنظیمات شبکه از محیط
        proxy_url = os.getenv("BOT_PROXY_URL")
        if not proxy_url:
             # Fallback to standard env vars
             proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        
        request_timeout = int(os.getenv("BOT_REQUEST_TIMEOUT", "60"))
        connect_timeout = int(os.getenv("BOT_CONNECT_TIMEOUT", "30"))
        
        if proxy_url and proxy_url.upper() == "NONE":
            logger.info("🌐 Forced DIRECT connection (ignoring system proxies)")
            request_obj = HTTPXRequest(
                proxy_url=None, # Explicitly no proxy
                read_timeout=request_timeout,
                connect_timeout=connect_timeout
            )
        elif proxy_url:
            logger.info(f"🌐 Configuring Telegram Request with Proxy: {proxy_url}")
            request_obj = HTTPXRequest(
                proxy_url=proxy_url,
                read_timeout=request_timeout,
                connect_timeout=connect_timeout,
                connection_pool_size=100,
                pool_timeout=40.0
            )
        else:
            logger.info("🌐 Using default connection settings (may auto-detect system proxies)")
            request_obj = HTTPXRequest(
                read_timeout=request_timeout,
                connect_timeout=connect_timeout,
                connection_pool_size=100,
                pool_timeout=40.0
            )

        self.application = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .request(request_obj)  # تزریق تنظیمات شبکه
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )
        
        # ذخیره container در bot_data برای دسترسی متمرکز در هندلرها
        self.application.bot_data['container'] = self.container
        self.application.bot_data['database'] = self.db
        self.application.bot_data['admin_handlers'] = self.admin_handlers
        if hasattr(self.admin_handlers, 'role_manager'):
            self.application.bot_data['role_manager'] = self.admin_handlers.role_manager
        
        # setup handlers
        self.setup_handlers()
        
        # تشخیص و اجرای حالت مناسب
        logger.info(f"🤖 Bot mode: {BOT_MODE.upper()}")
        
        if BOT_MODE == "webhook":
            try:
                self._run_webhook()
            except Exception as e:
                logger.error(f"🔄 Webhook failed, falling back to POLLING: {e}")
                # Reset application state to allow running again
                if self.application.running:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self.application.stop())
                self._run_polling()
        else:
            self._run_polling()

    def _run_polling(self):
        """اجرا با Polling Mode"""
        logger.info("🔄 Starting bot in POLLING mode...")
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except KeyboardInterrupt:
            logger.info("🛑 KeyboardInterrupt received")

    def _run_webhook(self):
        """اجرا با Webhook Mode"""
        import secrets

        webhook_url = WEBHOOK_URL
        if webhook_url and not webhook_url.startswith("http"):
            webhook_url = f"https://{webhook_url}"
        webhook_port = WEBHOOK_PORT
        webhook_path = WEBHOOK_PATH
        # NOTE: Telegram will send back the secret token in header
        # `X-Telegram-Bot-Api-Secret-Token`.
        # If we generate a new token on every restart, debugging gets harder and
        # some setups may appear flaky. Persist a generated token locally.
        webhook_secret = WEBHOOK_SECRET_TOKEN
        if not webhook_secret:
            try:
                secret_file = pathlib.Path(os.getenv("WEBHOOK_SECRET_FILE", ".webhook_secret_token")).expanduser()
                if secret_file.exists():
                    webhook_secret = secret_file.read_text(encoding="utf-8").strip()
                if not webhook_secret:
                    webhook_secret = secrets.token_urlsafe(32)
                    secret_file.write_text(webhook_secret, encoding="utf-8")
                    # Best-effort permission hardening on Linux
                    try:
                        os.chmod(secret_file, 0o600)
                    except Exception:
                        pass
                logger.info(f"🔐 Webhook secret token loaded from: {secret_file}")
            except Exception as e:
                logger.warning(f"⚠️  Could not persist webhook secret token, generating a temporary one. Error: {e}")
                webhook_secret = secrets.token_urlsafe(32)

        # SSL Certificate (optional - for self-signed certificates)
        cert_path = WEBHOOK_CERT_PATH or None
        key_path = WEBHOOK_KEY_PATH or None

        if not webhook_url:
            logger.error("❌ WEBHOOK_URL is required for webhook mode!")
            raise ValueError("WEBHOOK_URL is required for webhook mode")

        # اطمینان از شروع webhook_path با /
        if not webhook_path.startswith("/"):
            webhook_path = "/" + webhook_path

        full_webhook_url = f"{webhook_url}{webhook_path}"

        logger.info(f"🌐 Starting bot in WEBHOOK mode")
        logger.info(f"   URL: {full_webhook_url}")
        logger.info(f"   Port: {webhook_port}")
        logger.info(f"   SSL: {'Custom cert' if cert_path else 'Reverse proxy / built-in'}")
        if not cert_path and not key_path:
            logger.info("   SSL Note: If you don't provide cert/key, you MUST terminate HTTPS via a reverse proxy (e.g., Nginx) in front of this port.")
            logger.info("             Telegram does not deliver webhooks over plain HTTP.")

        try:
            webhook_kwargs = {
                "listen": "0.0.0.0",
                "port": webhook_port,
                "url_path": webhook_path.lstrip("/"),
                "webhook_url": full_webhook_url,
                "allowed_updates": Update.ALL_TYPES,
                "drop_pending_updates": True,
                "secret_token": webhook_secret,
            }

            # اضافه کردن SSL certificate در صورت تنظیم
            if cert_path and key_path:
                webhook_kwargs["cert"] = cert_path
                webhook_kwargs["key"] = key_path
                logger.info(f"   SSL Cert: {cert_path}")
            elif cert_path or key_path:
                logger.warning("⚠️  Both WEBHOOK_CERT_PATH and WEBHOOK_KEY_PATH must be set together. Ignoring SSL config.")

            self.application.run_webhook(**webhook_kwargs)

        except Exception as e:
            logger.error(f"❌ Webhook failed: {e}")
            logger.info("⬅️  Falling back to polling mode...")
            self._run_polling()

def main():
    """تابع اصلی"""
    try:
        bot = CODMAttachmentsBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()
