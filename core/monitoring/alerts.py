import psutil
import asyncio
from datetime import datetime
from config.config import SUPER_ADMIN_ID
from utils.logger import get_logger

logger = get_logger("monitoring.alerts", "admin.log")


class AlertSystem:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.thresholds = {
            "cpu_percent": 90.0,
            "memory_mb": 1024,  # 1GB
            "db_latency_ms": 500,
        }
        self.last_alerts = {}
        self.is_running = False

    async def _sample_cpu(self, interval: float = 1.0) -> float:
        """Measure CPU asynchronously in a worker thread to prevent blocking event loop."""
        return await asyncio.to_thread(psutil.cpu_percent, interval)

    async def _verify_sustained_high_cpu(self, initial_cpu: float) -> tuple[bool, list[float]]:
        """
        Verify if high CPU usage is sustained or just a transient 1-second burst/spike.
        Returns (is_sustained, samples_list).
        Takes additional samples over ~15 seconds. If CPU drops back to normal,
        it's treated as a momentary spike and skipped without triggering false alerts.
        """
        samples = [initial_cpu]
        for _ in range(2):
            await asyncio.sleep(5)
            if not self.is_running:
                return False, samples
            cpu_sample = await self._sample_cpu(interval=1.0)
            samples.append(cpu_sample)

        avg_cpu = sum(samples) / len(samples)
        # Sustained only if average exceeds threshold and latest reading didn't drop below threshold
        is_sustained = (avg_cpu >= self.thresholds["cpu_percent"]) and (samples[-1] >= (self.thresholds["cpu_percent"] - 5.0))
        return is_sustained, samples

    async def check_and_alert(self):
        """Main monitoring loop."""
        self.is_running = True
        logger.info("Monitoring alert system started.")

        while self.is_running:
            try:
                # 1. CPU & Memory (Non-blocking sampling)
                cpu = await self._sample_cpu(interval=1.0)
                process = psutil.Process()
                mem = process.memory_info().rss / 1024 / 1024

                # High CPU Check: Filter out 1-second transient bursts
                if cpu > self.thresholds["cpu_percent"]:
                    is_sustained, samples = await self._verify_sustained_high_cpu(cpu)
                    if is_sustained:
                        avg_cpu = sum(samples) / len(samples)
                        max_cpu = max(samples)
                        samples_str = ", ".join(f"{s:.1f}%" for s in samples)
                        alert_msg = (
                            f"⚠️ *Sustained High CPU Usage*\n"
                            f"• Average: `{avg_cpu:.1f}%` (over 15s)\n"
                            f"• Peak: `{max_cpu:.1f}%`\n"
                            f"• Samples: `{samples_str}`"
                        )
                        await self._send_alert("HIGH_CPU", alert_msg)
                    else:
                        logger.debug(
                            f"Transient CPU spike ({cpu}%) returned to normal {samples}. Alert suppressed."
                        )

                # High Memory Check: Verify if sustained
                if mem > self.thresholds["memory_mb"]:
                    await asyncio.sleep(3)
                    mem_verify = process.memory_info().rss / 1024 / 1024
                    if mem_verify > self.thresholds["memory_mb"]:
                        await self._send_alert(
                            "HIGH_MEM", f"⚠️ High Memory Usage: {mem_verify:.1f} MB"
                        )

                # 2. Database Health
                db_healthy = False
                last_error = ""
                latency = 0

                # Check 3 times before alerting DB_DOWN
                for attempt in range(3):
                    try:
                        async with self.db.get_connection() as conn:
                            async with conn.cursor() as cursor:
                                import time

                                start_time = time.perf_counter()
                                await cursor.execute("SELECT 1")
                                latency = (time.perf_counter() - start_time) * 1000
                        db_healthy = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        if attempt < 2:
                            await asyncio.sleep(2)

                if db_healthy:
                    if latency > self.thresholds["db_latency_ms"]:
                        await self._send_alert(
                            "HIGH_LATENCY", f"⚠️ High DB Latency: {latency:.1f}ms"
                        )
                else:
                    await self._send_alert("DB_DOWN", f"🚨 DATABASE DOWN: {last_error}")

            except Exception as e:
                logger.error(f"Alert check error: {e}")

            await asyncio.sleep(60)  # Only check every 60 seconds to save resources

    async def _send_alert(self, alert_key: str, message: str):
        """Send alert to Super Admin with debouncing (max once per hour for same alert)."""
        now = datetime.now()
        last_sent = self.last_alerts.get(alert_key)

        if not last_sent or (now - last_sent).total_seconds() > 3600:
            logger.error(f"ALERT: {message}")
            self.last_alerts[alert_key] = now

            async def _send():
                if not SUPER_ADMIN_ID:
                    logger.warning(
                        "SUPER_ADMIN_ID is not configured in settings. Skipping Telegram alert dispatch."
                    )
                    return
                try:
                    # Send to Telegram
                    await self.bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"🚨 *SYSTEM ALERT*\n\n{message}\n\n📅 {now.strftime('%Y-%m-%d %H:%M:%S')}",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert to admin: {e}")

            asyncio.create_task(_send())

    def stop(self):
        self.is_running = False
        logger.info("Monitoring alert system stopped.")
