import abc
from typing import Dict, List, Any, Callable
from src.utils.activity.trackers.session import WindowSession

class BaseInputTracker(abc.ABC):
    """Abstract base class for input tracker implementations."""

    @abc.abstractmethod
    async def start(self):
        """Starts input tracking."""
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self):
        """Stops input tracking."""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_events(self) -> Dict[str, Any]:
        """Gets collected input events (same format as the current InputTracker)."""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
        """Gets recent window sessions."""
        raise NotImplementedError
    
    @abc.abstractmethod
    async def enable_persistence(self) -> None:
        """Enable saving sessions to pending_sessions."""
        raise NotImplementedError

    @abc.abstractmethod
    async def disable_persistence(self) -> None:
        """Disable saving sessions to pending_sessions."""
        raise NotImplementedError