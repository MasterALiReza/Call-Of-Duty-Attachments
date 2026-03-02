from core.context import CustomContext
"""
System Monitoring Module
Provides health check and basic metrics tools for Super Admin tracking.
"""

from telegram import Update
from telegram.ext import ContextTypes
import time
import psutil
from datetime import datetime

from handlers.admin.modules.base_handler import BaseAdminHandler
from core.database.database_adapter import get_database_adapter
from utils.logger import get_logger
from config.config import SUPER_ADMIN_ID

logger = get_logger('monitor', 'admin.log')

# Capture boot time when module is loaded
BOOT_TIME = time.time()


class SystemMonitoringHandler(BaseAdminHandler):
    """
    Handler for monitoring system health and resources.
    Requires SUPER_ADMIN privileges.
    """
    def __init__(self, db_adapter=None, role_manager=None):
        super().__init__(db_adapter or get_database_adapter(), role_manager)

    async def health_check(self, update: Update, context: CustomContext):
        """Generates a detailed system /health report with visuals."""
        user_id = update.effective_user.id
        
        # Verify Super Admin
        if user_id != SUPER_ADMIN_ID:
            logger.warning(f"Unauthorized /health command attempt by user {user_id}")
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("⛔ شما دسترسی لازم برای این دستور را ندارید.")
            return

        status_msg = await update.message.reply_text("🔍 *در حال تحلیل وضعیت سیستم...*", parse_mode='Markdown')

        # ✅ DB Audit Logging
        await self.audit.log_action(
            admin_id=user_id,
            action="VIEW_SYSTEM_HEALTH",
            target_id="health",
            details={"target_type": "system"}
        )

        try:
            # 1. Uptime
            uptime_seconds = int(time.time() - BOOT_TIME)
            upt_d = uptime_seconds // 86400
            upt_h = (uptime_seconds % 86400) // 3600
            upt_m = (uptime_seconds % 3600) // 60
            uptime_str = f"{upt_d}d {upt_h}h {upt_m}m"

            # 2. Memory & CPU
            process = psutil.Process()
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            cpu_percent = psutil.cpu_percent(interval=0.5)
            
            # Progress bar for CPU/RAM
            def get_progress_bar(percent, length=10):
                filled = int(length * percent / 100)
                return "■" * filled + "□" * (length - filled)

            # 3. Database Health
            db_status = "🟢 Connected"
            db_latency = 0
            try:
                start = time.time()
                await self.db.execute_query("SELECT 1")
                db_latency = (time.time() - start) * 1000
            except Exception as e:
                db_status = f"🔴 Error: {str(e)[:40]}..."

            # 4. Redis Cache Health
            redis_status = "⚪ Missing"
            try:
                from core.cache.cache_manager import get_cache
                cache = get_cache()
                if cache.use_redis:
                    redis_status = "🟢 Active"
                else:
                    redis_status = "🟡 In-Memory"
            except Exception:
                pass
            
            # 5. Metrics Subsystem
            metrics_details = ""
            try:
                from utils.metrics import get_metrics
                m = get_metrics()
                s = m.get_all_stats()
                h, ms = s['cache']['hits'], s['cache']['misses']
                rate = s['cache']['hit_rate_percent']
                metrics_details = (
                    f"📦 *Cache Stats:*\n"
                    f"└ Hits: `{h:,}` | Misses: `{ms:,}`\n"
                    f"└ Success Rate: `{rate:.1f}%` {get_progress_bar(rate)}\n\n"
                    f"🗃 *Query Stats:*\n"
                    f"└ Total: `{s['queries']['total_queries']:,}`\n"
                    f"└ Slow: `{s['queries']['slow_queries']:,}` (`{s['queries']['slow_query_rate']*100:.1f}%`)\n"
                    f"└ Avg Latency: `{s['queries']['average_duration_ms']:.1f}ms`"
                )
            except Exception:
                pass

            report = (
                "🛡 *DASHBOARD MONITORING* 🛡\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
                f"⏱ *Uptime:* `{uptime_str}`\n"
                f"📟 *CPU:* `{cpu_percent}%` {get_progress_bar(cpu_percent)}\n"
                f"💾 *RAM:* `{mem_mb:.1f} MB` {get_progress_bar(min(100, mem_mb/1024*100))}\n\n"
                f"🗄 *PostgreSQL:* {db_status} (`{db_latency:.1f}ms`)\n"
                f"⚡ *Cache Layer:* {redis_status}\n\n"
                f"{metrics_details}\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"📡 *Health Server:* `http://0.0.0.0:8080`\n"
                f"📅 *Generated:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
            )

            await status_msg.edit_text(report, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            await status_msg.edit_text(f"❌ *خطا در مانیتورینگ:*\n`{str(e)}`", parse_mode='Markdown')
