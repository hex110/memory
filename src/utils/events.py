from dataclasses import dataclass
from typing import Dict, Any, Callable, List, Coroutine
from enum import Enum
import asyncio

class ActivityEventType(Enum):
    ACTIVITY_STORED = "activity_stored"
    ANALYSIS_STORED = "analysis_stored"

@dataclass
class ActivityEvent:
    session_id: str
    timestamp: str
    data: Dict[str, Any]
    event_type: ActivityEventType

class EventBroadcaster:
    def __init__(self):
        self._subscribers: Dict[ActivityEventType, List[Callable[..., Coroutine]]] = {}
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
    async def subscribe(self, event_type: ActivityEventType, callback: Callable[..., Coroutine]):
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            
    async def broadcast(self, event: ActivityEvent):
        async with self._lock:
            subscribers = self._subscribers.get(event.event_type, []).copy()

        for callback in subscribers:
            task = asyncio.create_task(self._safe_callback(callback, event))
            self._tasks.append(task)
            task.add_done_callback(self._tasks.remove)
    
    async def _safe_callback(self, callback: Callable[..., Coroutine], event: ActivityEvent):
        try:
            await callback(event)
        except Exception as e:
            print(f"Error in event callback: {str(e)}")
            
    async def cleanup(self):
        """Wait for all pending tasks to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

class ActivityEventSystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.broadcaster = EventBroadcaster()
        return cls._instance
        
    async def cleanup(self):
        await self.broadcaster.cleanup()