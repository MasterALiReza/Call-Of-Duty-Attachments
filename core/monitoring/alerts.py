import logging
import psutil
import asyncio
from datetime import datetime
from config.config import SUPER_ADMIN_ID
from utils.logger import get_logger

logger = get_logger('monitoring.alerts', 'admin.log')

class AlertSystem:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.thresholds = {
            "cpu_percent": 90.0,
            "memory_mb": 1024, # 1GB
            "db_latency_ms": 500
        }
        self.last_alerts = {}
        self.is_running = False

    async def check_and_alert(self):
        """Main monitoring loop."""
        self.is_running = True
        logger.info("Monitoring alert system started.")
        
        while self.is_running:
            try:
                # 1. CPU & Memory
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.Process().memory_info().rss / 1024 / 1024
                
                if cpu > self.thresholds["cpu_percent"]:
                    await self._send_alert("HIGH_CPU", f"⚠️ High CPU Usage: {cpu}%")
                
                if mem > self.thresholds["memory_mb"]:
                    await self._send_alert("HIGH_MEM", f"⚠️ High Memory Usage: {mem:.1f} MB")
                
                # 2. Database Health
                start_time = datetime.now()
                db_healthy = False
                last_error = ""
                
                # Check 3 times before alerting DB_DOWN
                for attempt in range(3):
                    try:
                        await self.db.execute_query("SELECT 1")
                        db_healthy = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        if attempt < 2:
                            await asyncio.sleep(2)
                
                if db_healthy:
                    latency = (datetime.now() - start_time).total_seconds() * 1000
                    if latency > self.thresholds["db_latency_ms"]:
                        await self._send_alert("HIGH_LATENCY", f"⚠️ High DB Latency: {latency:.1f}ms")
                else:
                    await self._send_alert("DB_DOWN", f"🚨 DATABASE DOWN: {last_error}")

            except Exception as e:
                logger.error(f"Alert check error: {e}")
            
            await asyncio.sleep(60) # Only check every 60 seconds to save resources

    async def _send_alert(self, alert_key: str, message: str):
        """Send alert to Super Admin with debouncing (max once per hour for same alert)."""
        now = datetime.now()
        last_sent = self.last_alerts.get(alert_key)
        
        if not last_sent or (now - last_sent).total_seconds() > 3600:
            logger.error(f"ALERT: {message}")
            try:
                # Send to Telegram
                await self.bot.send_message(
                    chat_id=SUPER_ADMIN_ID,
                    text=f"🚨 *SYSTEM ALERT*\n\n{message}\n\n📅 {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode='Markdown'
                )
                self.last_alerts[alert_key] = now
            except Exception as e:
                logger.error(f"Failed to send alert to admin: {e}")

    def stop(self):
        self.is_running = False
        logger.info("Monitoring alert system stopped.")
