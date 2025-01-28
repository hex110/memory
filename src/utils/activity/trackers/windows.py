"""Window tracking functionality.

This module provides window tracking capabilities through the WindowManager class.
Currently implements Hyprland-specific window management, with architecture
supporting future window manager implementations.

Core features:
- Window state tracking
- Focus history tracking
- Window metadata parsing
- Window classification
- Error recovery
"""

import json
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Callable

from src.utils.exceptions import WindowTrackingError
from src.utils.activity.compositor.base_compositor import BaseCompositor

# Set up logging
logger = logging.getLogger(__name__)

class WindowManager:
    """Window manager implementation for tracking and managing window state."""

    def __init__(self, compositor: BaseCompositor) -> None:
        """Initialize window manager interface."""
        self.windows: List[Dict[str, Any]] = []
        self.compositor = compositor
        
    async def get_windows(self) -> List[Dict[str, Any]]:
        """Get current window state.
        
        Returns:
            List of dictionaries containing window information
        """
        return await self.compositor.get_windows()
    
    async def setup_focus_tracking(self, callback: Callable[[Dict[str, str]], None]) -> None:
        """Set up focus change tracking using Hyprland's IPC socket."""
        await self.compositor.setup_focus_tracking(callback)
    
    async def get_active_window(self) -> Optional[Dict[str, str]]:
        """Get currently focused window info."""
        return await self.compositor.get_active_window()
    
    async def cleanup(self) -> None:
        """Clean up IPC socket connection."""
        await self.compositor.cleanup()