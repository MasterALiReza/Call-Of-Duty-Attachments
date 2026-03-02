import asyncio
import logging
from typing import Any, Callable, Dict, List, Coroutine

logger = logging.getLogger('events')

EventCallback = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """
    A lightweight asynchronous Event Bus for decoupling pub/sub mechanisms.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[EventCallback]] = {}

    def subscribe(self, event_type: str, callback: EventCallback):
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"[EventBus] Subscribed {callback.__name__} to '{event_type}'")

    def unsubscribe(self, event_type: str, callback: EventCallback):
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"[EventBus] Unsubscribed {callback.__name__} from '{event_type}'")

    async def emit(self, event_type: str, **kwargs):
        """
        Emit an event, executing all subscribers asynchronously.
        Args:
            event_type: The string name of the event to emit.
            kwargs: Data passed to the subscribed callbacks.
        """
        if event_type not in self._subscribers or not self._subscribers[event_type]:
            return

        logger.debug(f"[EventBus] Emitting '{event_type}' to {len(self._subscribers[event_type])} subscribers. Data: {kwargs}")
        
        # Fire off all callbacks concurrently without awaiting their completion here
        # to prevent blocking the emitter.
        tasks = []
        for callback in self._subscribers[event_type]:
            try:
                task = asyncio.create_task(self._safe_execute(callback, **kwargs))
                tasks.append(task)
            except Exception as e:
                logger.error(f"[EventBus] Failed to spawn task for {callback.__name__} on '{event_type}': {e}")
                
        # Optional: We don't await the tasks here as we want a true "fire-and-forget"
        # However, it's safe to let them run in the event loop.

    async def _safe_execute(self, callback: EventCallback, **kwargs):
        """Execute a callback and catch any exceptions to prevent breaking the loop."""
        try:
            await callback(**kwargs)
        except Exception as e:
            logger.error(f"[EventBus] Error in subscriber {callback.__name__}: {e}", exc_info=True)


# Global instance
event_bus = EventBus()

# Event Types Constants
class EventTypes:
    USER_REGISTERED = "USER_REGISTERED"
    USER_INTERACTION = "USER_INTERACTION"
    ADMIN_ACTION = "ADMIN_ACTION"
    SETTING_CHANGED = "SETTING_CHANGED"
    ATTACHMENT_SUBMITTED = "ATTACHMENT_SUBMITTED"
