import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from collections import deque

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.session import WindowSession
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from src.utils.activity.compositor.macosevent import EventType
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker

logger = logging.getLogger(__name__)

class MacOSInputTracker(BaseInputTracker):
    """Tracks keyboard and mouse activity using events from MacKeyServer."""

    def __init__(self, compositor: BaseCompositor, privacy_config: PrivacyConfig, hotkeys: Dict[HotkeyEventType, str]):
        """Initialize the input tracker."""
        super().__init__(compositor, privacy_config, hotkeys)
        self.event_system = EventSystem()
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        self.recent_sessions = deque(maxlen=30)
        self.should_persist = False
        self._tasks: List[asyncio.Task] = []

        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

        # Modifier keys mapping
        self.modifier_map = {
            "56": "alt",    # VK_LALT
            "58": "cmd",  # VK_LCOMMAND
            "55": "ctrl",   # VK_LCTRL
            "63": "fn",     # VK_FN
            "54": "cmd",     # VK_RCOMMAND
            "60": "shift",  # VK_RSHIFT
            "59": "ctrl",   # VK_RCTRL
            "57": "alt",    # VK_RALT
            "62": "ctrl",    # VK_FN_CTRL
            "56": "shift"   # VK_LSHIFT
        }

    async def _process_event(self, event_type: EventType, event_data: Dict[str, Any]):
        """Processes a single input event."""
        if not self.is_running:
            return

        timestamp = datetime.now()

        # Skip if no current session or if the current window is private
        if not self.current_session or self.privacy_config.is_private(self.current_session.window_info):
            return

        # logger.debug(f"Processing {event_type} event: {event_data}")
        try:
            if event_type == EventType.CHARACTER:
                await self._handle_key_event(event_data, timestamp)
            elif event_type == EventType.SPECIAL_KEY:
                await self._handle_special_key_event(event_data, timestamp)
            elif event_type == EventType.MOUSE:
                await self._handle_mouse_event(event_data, timestamp)
            elif event_type == EventType.SCROLL:
                await self._handle_scroll_event(event_data, timestamp)
            elif event_type == EventType.MODIFIER:
                await self._handle_modifier_event(event_data, timestamp)
        except Exception as e:
            logger.error(f"Error processing input event: {e}", exc_info=True)

    async def _handle_special_key_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles a special keyboard event."""
        key_name = event_data["key"]
        action = event_data["action"]
        modifiers = event_data.get("modifiers", "")

        if action == "DOWN":
            self._total_keys += 1
            # Update pressed_keys with parsed modifiers
            self.pressed_keys.update(self._parse_modifiers(modifiers))
            self.pressed_keys.add(key_name.lower())

            await self.current_session.add_event("key", {
                "type": "press",
                "key": self._standardize_key_name(key_name),  # Use special key name directly
                "timestamp": timestamp.isoformat()
            })
            await self._check_hotkeys()

        elif action == "UP":
            # Remove the key name from pressed_keys
            if key_name.lower() in self.pressed_keys:
                self.pressed_keys.discard(key_name.lower())

            # Update pressed_keys based on modifiers string
            self.pressed_keys = {
                key for key in self.pressed_keys
                if key not in self._parse_modifiers(modifiers)
            }

            await self.current_session.add_event("key", {
                "type": "release",
                "key": key_name,  # Use special key name directly
                "timestamp": timestamp.isoformat()
            })

    async def _handle_key_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles a keyboard event."""
        key_name = event_data["key"]
        action = event_data["action"]
        modifiers = event_data.get("modifiers", "")

        if action == "DOWN":
            self._total_keys += 1
            # Update pressed_keys with parsed modifiers
            self.pressed_keys.update(self._parse_modifiers(modifiers))
            self.pressed_keys.add(key_name.lower())

            await self.current_session.add_event("key", {
                "type": "press",
                "key": self._standardize_key_name(key_name),
                "timestamp": timestamp.isoformat()
            })
            await self._check_hotkeys()

        elif action == "UP":
            # Remove the standardized key name from pressed_keys
            standardized_key = self._standardize_key_name(key_name)
            if standardized_key in self.pressed_keys:
                self.pressed_keys.discard(standardized_key)

            # Update pressed_keys based on modifiers string
            self.pressed_keys = {
                key for key in self.pressed_keys
                if key not in self._parse_modifiers(modifiers)
            }

            await self.current_session.add_event("key", {
                "type": "release",
                "key": standardized_key,
                "timestamp": timestamp.isoformat()
            })

    async def _handle_modifier_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles modifier key events."""
        modifier_code = event_data.get("modifier")
        state = event_data.get("state")
        modifier = self.modifier_map.get(modifier_code, modifier_code)

        if state == "DOWN" and modifier:
            self.pressed_keys.add(modifier.lower())
        elif state == "UP" and modifier:
            self.pressed_keys.discard(modifier.lower())

    def _parse_modifiers(self, modifiers_string: str) -> List[str]:
        """Parses the modifiers string from the event data into a list of modifier keys."""
        if not modifiers_string:
            return []
        return [modifier.lower() for modifier in modifiers_string.split("+")]

    async def _handle_mouse_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles a mouse button event."""
        button = event_data.get("button")
        action = event_data.get("action")

        if action == "DOWN" and button is not None:
            button_name = self._standardize_mouse_button(str(button))
            self._total_clicks += 1
            await self.current_session.add_event("click", {
                "button": button_name,
                "timestamp": timestamp.isoformat()
            })

    async def _handle_scroll_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles a mouse scroll event."""
        scroll_delta = event_data.get("delta")
        if scroll_delta is not None:
            scroll_direction = "vertical" if scroll_delta > 0 else "horizontal"
            self._total_scrolls += abs(scroll_delta)
            await self.current_session.add_event("scroll", {
                "direction": scroll_direction,
                "amount": scroll_delta,
                "timestamp": timestamp.isoformat()
            })

    async def _handle_modifier_event(self, event_data: Dict[str, Any], timestamp: datetime):
        """Handles modifier key events."""
        modifier_code = event_data.get("modifier")
        state = event_data.get("state")
        modifier = self.modifier_map.get(modifier_code, modifier_code)

        if state == "DOWN" and modifier:
            self.pressed_keys.add(modifier.lower())
        elif state == "UP" and modifier:
            self.pressed_keys.discard(modifier.lower())
        # We don't need to add an event for modifiers, we only need to keep track of them

    async def enable_persistence(self) -> None:
        """Enable saving sessions to pending_sessions."""
        self.should_persist = True

    async def disable_persistence(self) -> None:
        """Disable saving sessions to pending_sessions."""
        self.should_persist = False

    async def start(self):
        """Start tracking keyboard and mouse events."""
        logger.info("Starting MacOSInputTracker")
        self.is_running = True

    async def stop(self):
        """Stop tracking keyboard and mouse events."""
        logger.info("Stopping MacOSInputTracker")
        self.is_running = False

        # End current session if it exists
        if self.current_session:
            await self.current_session.end_session(datetime.now())
            self.current_session = None

        # Cancel all listening tasks
        for task in self._tasks:
            task.cancel()
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.warning("Monitoring tasks were cancelled")

        self._tasks = []
        logger.info("MacOSInputTracker stopped")

    async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
        """Get recent sessions from buffer."""
        now = datetime.now()
        return [
            session for session in self.recent_sessions
            if (now - session.end_time).total_seconds() <= seconds
        ]

    async def _on_window_focus_change(self, window_info: Dict[str, Any]) -> None:
        """Handle window focus changes."""
        # logger.debug(f"Window focus change detected: {window_info}")

        now = datetime.now()

        # End the current session if it exists
        if self.current_session:
            await self.current_session.end_session(now)
            self.recent_sessions.append(self.current_session)

            # Persist the session if not private
            if self.should_persist and not self.privacy_config.is_private(self.current_session.window_info):
                self.pending_sessions.append(self.current_session)

        # Create new session with the new window info
        if window_info:
            window_info_for_session = {
                "class": window_info.get("ownerName"),
                "title": window_info.get("windowName"),
                "original_class": window_info.get("ownerName")
            }
        else:
            window_info_for_session = {}

        self.current_session = WindowSession(window_info_for_session, now)