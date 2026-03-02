import logging
import threading
from typing import Optional

from core.database.database_adapter import get_database_adapter
from core.events import event_bus
from core.monitoring.health_server import HealthServer
from core.monitoring.alerts import AlertSystem
from core.interfaces import IUserRepository, IAttachmentRepository, IAnalyticsRepository, ITicketRepository
from core.database.repositories import (
    UserRepository, AttachmentRepository, SettingsRepository,
    CMSRepository, AnalyticsRepository, SupportRepository
)

logger = logging.getLogger('core.container')

class ServiceContainer:
    """
    Centralized container for application services.
    Implements a thread-safe singleton pattern.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # Database & Repositories
        self.db = get_database_adapter()
        
        # Initialize repositories with db adapter
        self.users = UserRepository(self.db)
        self.attachments = AttachmentRepository(self.db)
        self.settings = SettingsRepository(self.db)
        self.cms = CMSRepository(self.db)
        self.analytics = AnalyticsRepository(self.db)
        self.support = SupportRepository(self.db)

        # Monitoring
        self.health_server = HealthServer(db=self.db)
        self.alert_system: Optional[AlertSystem] = None # Initialized in main.py with bot instance

        # Messaging & Events
        self.event_bus = event_bus
        
        # Managers & Schedulers (set after bot init)
        self.notification_scheduler = None
        self.backup_scheduler = None
        
        # Handlers (decoupled access)
        self.admin = None
        self.contact = None
        self.feedback_handler = None

        logger.info("ServiceContainer initialized")

    @classmethod
    def get_instance(cls) -> 'ServiceContainer':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ServiceContainer()
        return cls._instance

# Singleton helper
def get_container() -> ServiceContainer:
    return ServiceContainer.get_instance()
