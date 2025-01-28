# src/utils/activity/trackers/input/pynput.py
"""Input tracking using pynput."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from collections import deque

from pynput import keyboard, mouse

from src.utils.activity.trackers.session import WindowSession
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker

logger = logging.getLogger(__name__)

class PynputInputTracker(BaseInputTracker):
    """Tracks keyboard and mouse activity using pynput."""

    def __init__(self, compositor: BaseCompositor, privacy_config: PrivacyConfig, hotkeys: Dict[HotkeyEventType, str]):
        super().__init__(compositor, privacy_config, hotkeys)
        self.listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        self.recent_sessions = deque(maxlen=30)
        self.should_persist = False
        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

    async def start(self):
        """Start tracking keyboard and mouse events."""
        if self.is_running:
            return

        try:
            # Setup window focus tracking if not already setup
            await self.compositor.setup_focus_tracking(self._on_window_focus_change)
            current_window = await self.compositor.get_active_window()
            if current_window:
                await self._on_window_focus_change(current_window)

            self.is_running = True
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.mouse_listener = mouse.Listener(
                on_click=self._on_click,
                on_scroll=self._on_scroll
            )
            self.listener.start()
            self.mouse_listener.start()

            logger.debug("PynputInputTracker started")

        except Exception as e:
            logger.error(f"Failed to start PynputInputTracker: {e}")
            await self.stop()

    async def stop(self):
        """Stop tracking keyboard and mouse events."""
        self.is_running = False

        # End current session if exists
        if self.current_session:
            await self.current_session.end_session(datetime.now())
            self.current_session = None

        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

        logger.debug("PynputInputTracker stopped")

    def _on_press(self, key):
        """Handle key press events."""
        try:
            # Check for hotkey combinations
            try:
                key_name = key.char
            except AttributeError:
                key_name = key.name
            
            self.pressed_keys.add(key_name)
            asyncio.run(self._check_hotkeys()) # Check hotkeys on press

            # Skip if no active window session
            if not self.current_session:
                return

            # Skip if current window is private
            if self.privacy_config.is_private(self.current_session.window_info):
                return

            self._total_keys += 1

            # Convert key names to more readable format
            if hasattr(key, 'char'):
                key_name = key.char
            elif hasattr(key, 'name'):
                key_name = key.name
            else:
                key_name = str(key)
                
            # Standardize the key name
            standardized_key = self._standardize_key_name(key_name)

            asyncio.run(self.current_session.add_event("key", {
                "type": "press",
                "key": standardized_key,
                "timestamp": datetime.now().isoformat()
            }))

        except Exception as e:
            logger.error(f"Error in _on_press: {e}")

    def _on_release(self, key):
        """Handle key release events."""
        try:
            # Remove the key from pressed_keys when it's released
            try:
                key_name = key.char
            except AttributeError:
                key_name = key.name
            
            if key_name in self.pressed_keys:
                self.pressed_keys.remove(key_name)
                
        except Exception as e:
            logger.error(f"Error in _on_release: {e}")
            
    def _on_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        try:
            # Skip if no active window session
            if not self.current_session:
                return

            # Skip if current window is private
            if self.privacy_config.is_private(self.current_session.window_info):
                return

            if pressed:
                self._total_clicks += 1
                asyncio.run(self.current_session.add_event("click", {
                    "button": self._standardize_mouse_button(str(button)),
                    "timestamp": datetime.now().isoformat()
                }))
        except Exception as e:
            logger.error(f"Error in _on_click: {e}")

    def _on_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events."""
        try:
            # Skip if no active window session
            if not self.current_session:
                return

            # Skip if current window is private
            if self.privacy_config.is_private(self.current_session.window_info):
                return

            self._total_scrolls += abs(dy)
            asyncio.run(self.current_session.add_event("scroll", {
                "direction": "vertical",
                "amount": dy,
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error in _on_scroll: {e}")

    # async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
    #     """Get recent sessions from buffer."""
    #     now = datetime.now()
    #     return [
    #         session for session in self.recent_sessions
    #         if (now - session.end_time).total_seconds() <= seconds
    #     ]
    
    async def enable_persistence(self) -> None:
        """Enable saving sessions to pending_sessions."""
        self.should_persist = True

    async def disable_persistence(self) -> None:
        """Disable saving sessions to pending_sessions."""
        self.should_persist = False