from dataclasses import dataclass
from typing import Dict, Any, Callable, List, Coroutine
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class ActivityEventType(Enum):
    ACTIVITY_STORED = "activity_stored"
    ANALYSIS_STORED = "analysis_stored"
    ANALYSIS_MEDIUM_TERM_AVAILABLE = "analysis_medium_term_available"

class HotkeyEventType(Enum):
    HOTKEY_SPEAK = "speak"

@dataclass
class ActivityEvent:
    session_id: str
    timestamp: str
    data: Dict[str, Any]
    event_type: ActivityEventType

@dataclass
class HotkeyEvent:
    timestamp: str
    hotkey_type: HotkeyEventType

class EventBroadcaster:
    def __init__(self):
        self._activity_subscribers: Dict[ActivityEventType, List[Callable[..., Coroutine]]] = {}
        self._hotkey_subscribers: Dict[HotkeyEventType, List[Callable[..., Coroutine]]] = {}
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
    async def subscribe_activity(self, event_type: ActivityEventType, callback: Callable[..., Coroutine]):
        async with self._lock:
            if event_type not in self._activity_subscribers:
                self._activity_subscribers[event_type] = []
            self._activity_subscribers[event_type].append(callback)

    async def subscribe_hotkey(self, event_type: HotkeyEventType, callback: Callable[..., Coroutine]):
        async with self._lock:
            if event_type not in self._hotkey_subscribers:
                self._hotkey_subscribers[event_type] = []
            self._hotkey_subscribers[event_type].append(callback)
            
    async def broadcast_activity(self, event: ActivityEvent):
        async with self._lock:
            subscribers = self._activity_subscribers.get(event.event_type, []).copy()

        for callback in subscribers:
            task = asyncio.create_task(self._safe_callback(callback, event))
            self._tasks.append(task)
            task.add_done_callback(self._tasks.remove)

    async def broadcast_hotkey(self, event: HotkeyEvent):
        async with self._lock:
            subscribers = self._hotkey_subscribers.get(event.hotkey_type, []).copy()

        for callback in subscribers:
            task = asyncio.create_task(self._safe_callback(callback, event))
            self._tasks.append(task)
            task.add_done_callback(self._tasks.remove)
    
    async def _safe_callback(self, callback: Callable[..., Coroutine], event: ActivityEvent | HotkeyEvent):
        try:
            await callback(event)
        except Exception as e:
            logger.error(f"Error in event callback: {str(e)}", exc_info=True)
            
    async def cleanup(self):
        """Wait for all pending tasks to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

class EventSystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.broadcaster = EventBroadcaster()
        return cls._instance
        
    async def cleanup(self):
        await self.broadcaster.cleanup()