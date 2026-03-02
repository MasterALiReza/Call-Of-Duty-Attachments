import asyncio
import logging
from aiohttp import web
from datetime import datetime

logger = logging.getLogger('monitoring.health_server')

class HealthServer:
    def __init__(self, host='0.0.0.0', port=8080, db=None, schedulers=None):
        self.host = host
        self.port = port
        self.db = db
        self.schedulers = schedulers or [] # List of scheduler objects
        self.app = web.Application()
        self.app.add_routes([
            web.get('/health', self.health_check),
            web.get('/metrics', self.metrics),
            web.get('/', self.index)
        ])
        self.runner = None
        self.started_successfully = False  # Track if health server started

    async def index(self, request):
        return web.Response(text="CODM Bot Monitoring Server is running.", content_type='text/plain')

    async def health_check(self, request):
        """Standard health check endpoint."""
        health = {
            "status": "pass",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "unknown",
                "telegram": "unknown"
            }
        }
        
        # Check Database
        if self.db:
            try:
                await self.db.execute_query("SELECT 1")
                health["services"]["database"] = "ok"
            except Exception as e:
                health["status"] = "fail"
                health["services"]["database"] = f"error: {str(e)}"
        
        # Check Schedulers
        health["services"]["schedulers"] = {}
        for sched in self.schedulers:
            name = sched.__class__.__name__
            is_alive = False
            if hasattr(sched, '_running'):
                is_alive = sched._running
            elif hasattr(sched, '_task'):
                is_alive = sched._task is not None and not sched._task.done()
            
            health["services"]["schedulers"][name] = "alive" if is_alive else "dead"
            if not is_alive:
                health["status"] = "degraded" if health["status"] == "pass" else health["status"]
        
        # System Info
        try:
            import psutil
            health["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_usage_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 2)
            }
        except ImportError:
            pass
        
        return web.json_response(health, status=200 if health["status"] == "pass" else 503)

    async def metrics(self, request):
        """Basic Prometheus-compatible metrics."""
        from utils.metrics import get_metrics
        m = get_metrics()
        stats = m.get_all_stats()
        
        lines = [
            f"# HELP bot_uptime_hours Hours since bot started",
            f"# TYPE bot_uptime_hours gauge",
            f"bot_uptime_hours {stats['uptime_hours']}",
            f"# HELP cache_hits_total Total cache hits",
            f"# TYPE cache_hits_total counter",
            f"cache_hits_total {stats['cache']['hits']}",
            f"# HELP cache_misses_total Total cache misses",
            f"# TYPE cache_misses_total counter",
            f"cache_misses_total {stats['cache']['misses']}",
            f"# HELP db_queries_total Total database queries",
            f"# TYPE db_queries_total counter",
            f"db_queries_total {stats['queries']['total_queries']}",
            f"# HELP db_slow_queries_total Total slow queries",
            f"# TYPE db_slow_queries_total counter",
            f"db_slow_queries_total {stats['queries']['slow_queries']}"
        ]
        return web.Response(text="\n".join(lines) + "\n", content_type='text/plain')

    async def start(self):
        """
        Start the health server with port fallback logic.
        
        Returns:
            bool: True if server started successfully, False otherwise
        """
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Try the configured port first
        ports_to_try = [self.port] + list(range(8081, 8090))  # 8080, then 8081-8089
        
        for port in ports_to_try:
            try:
                site = web.TCPSite(self.runner, self.host, port)
                await site.start()
                
                if port != self.port:
                    logger.warning(
                        f"Health server could not bind to port {self.port}, "
                        f"using fallback port {port} instead"
                    )
                else:
                    logger.info(f"Health check server started at http://{self.host}:{port}")
                
                self.port = port  # Update to the actual port being used
                self.started_successfully = True
                return True
                
            except (OSError, PermissionError) as e:
                if port == ports_to_try[-1]:
                    # Last port failed, log error and allow bot to continue
                    logger.error(
                        f"Health server failed to bind to any port (tried {self.port}, 8081-8089). "
                        f"Bot will continue without health monitoring. Error: {e}"
                    )
                    self.started_successfully = False
                    return False
                # Try next port
                continue
        
        return False

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped.")
