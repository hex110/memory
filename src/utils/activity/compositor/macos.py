import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable

from src.utils.activity.compositor.base_compositor import BaseCompositor

logger = logging.getLogger(__name__)

class MacOSCompositor(BaseCompositor):
    def __init__(self):
        self.window_info: Dict[str, Any] = {"active": None, "all": []}
        self._tasks: List[asyncio.Task] = []
        self._focus_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    async def start(self):
        """Starts listening for window events."""
        pass

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Retrieves information about the currently active window."""
        return self.window_info["active"]

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Retrieves a list of all open windows and their properties."""
        return self.window_info["all"]

    async def setup_focus_tracking(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Sets up focus change tracking."""
        self._focus_callback = callback

    def is_window_visible(self, window_info: Dict[str, Any]) -> bool:
        """Determine if a given window is currently visible on the screen."""
        all_windows = self.window_info.get("all", [])
        return any(window == window_info for window in all_windows)

    async def cleanup(self):
        """Cleans up resources."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.window_info = {"active": None, "all": []}