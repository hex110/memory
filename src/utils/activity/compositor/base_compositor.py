# src/utils/activity/compositor/base_compositor.py
import abc
from typing import Dict, List, Any, Callable, Optional

class BaseCompositor(abc.ABC):
    """Abstract base class for compositor implementations."""

    @abc.abstractmethod
    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently focused window.

        Returns:
            A dictionary containing information about the active window,
            or None if no window is active.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_windows(self) -> List[Dict[str, Any]]:
        """Get a list of all open windows and their properties.

        Returns:
            A list of dictionaries, where each dictionary represents a window
            and contains its properties.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def setup_focus_tracking(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set up a mechanism to receive notifications when the active window changes.

        Args:
            callback: A callable that will be invoked with a dictionary containing
                      information about the newly focused window when the active
                      window changes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def is_window_visible(self, window_info: Dict[str, Any]) -> bool:
        """Determine if a given window is currently visible on the screen.

        Args:
            window_info: A dictionary containing information about the window.

        Returns:
            True if the window is visible, False otherwise.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the compositor."""
        raise NotImplementedError