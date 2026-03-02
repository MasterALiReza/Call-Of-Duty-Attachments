from core.context import CustomContext
import logging
from telegram import User
from telegram.ext import ContextTypes

from core.events import event_bus, EventTypes
from utils.analytics_pg import AnalyticsPostgres as Analytics
from utils.logger import log_exception
from managers.admin_notifier import AdminNotifier
from core.database.database_adapter import get_database_adapter

logger = logging.getLogger("event_subscribers")

async def on_user_registered(user_id: int, user: User, is_new_user: bool, context: CustomContext, **kwargs):
    """
    Called when a user interacts with the bot via /start.
    Handles Analytics tracking and Admin notifications asynchronously.
    """
    logger.info(f"[Analytics] Event: USER_REGISTERED for user {user_id}")
    try:
        # 1. Analytics Tracking
        analytics = Analytics()
        # Await the tracking call which is now async
        await analytics.track_user_start(user_id)
        
        # 2. Admin Notification
        # Notify admin if it's a new user
        if is_new_user and user:
            db = get_database_adapter()
            admin_notifier = AdminNotifier(db)
            await admin_notifier.notify_user_start(context, user, is_new_user)
    except Exception as e:
        logger.error(f"Error in on_user_registered: {e}")
        log_exception(logger, e, "on_user_registered")

async def on_attachment_submitted(context: CustomContext, user_id: int, attachment_id: int, weapon: str, mode: str, category: str, **kwargs):
    """
    Called when a new user attachment is submitted.
    Queues a notification for admins/subscribers.
    """
    logger.info(f"[Notification] Event: ATTACHMENT_SUBMITTED for attachment {attachment_id}")
    try:
        from managers.notification_manager import NotificationManager
        from utils.subscribers_pg import SubscribersPostgres
        
        db = get_database_adapter()
        subscribers = SubscribersPostgres(db)
        notif_manager = NotificationManager(db, subscribers)
        
        payload = {
            'attachment_id': attachment_id,
            'weapon': weapon,
            'mode': mode,
            'category': category,
            'user_id': user_id,
            'name': kwargs.get('name', weapon) # Use weapon as fallback name
        }
        
        # Queue the notification for batching - using 'add_attachment' event type for settings check
        await notif_manager.queue_notification(context, 'add_attachment', payload)
        
    except Exception as e:
        logger.error(f"Error in on_attachment_submitted: {e}")
        log_exception(logger, e, "on_attachment_submitted")


def register_all_subscribers():
    """ثبت تمام توابع مشترک در Event Bus"""
    logger.info("Registering all global event subscribers...")
    
    event_bus.subscribe(EventTypes.USER_REGISTERED, on_user_registered)
    event_bus.subscribe(EventTypes.ATTACHMENT_SUBMITTED, on_attachment_submitted)
    
    logger.info("All event subscribers registered.")
