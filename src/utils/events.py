from dataclasses import dataclass
from typing import Dict, Any, Callable, List
from enum import Enum
import threading

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
        self._subscribers: Dict[ActivityEventType, List[Callable]] = {}
        self._lock = threading.Lock()
        
    def subscribe(self, event_type: ActivityEventType, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            
    def broadcast(self, event: ActivityEvent):
        with self._lock:
            subscribers = self._subscribers.get(event.event_type, []).copy()

        # Launch each callback in its own thread
        for callback in subscribers:
            threading.Thread(target=self._safe_callback, args=(callback, event)).start()
    
    def _safe_callback(self, callback: Callable, event: ActivityEvent):
        try:
            callback(event)
        except Exception as e:
            print(f"Error in event callback: {str(e)}")

class ActivityEventSystem:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.broadcaster = EventBroadcaster()
        return cls._instance