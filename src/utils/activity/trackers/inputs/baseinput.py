import abc
from typing import Dict, List, Any, Callable, Optional
from src.utils.activity.trackers.session import WindowSession
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from datetime import datetime
from collections import deque
from src.utils.logging import get_logger

logger = get_logger(__name__)

class BaseInputTracker(abc.ABC):
    """Abstract base class for input tracker implementations."""

    def __init__(self, compositor, privacy_config, hotkeys: Dict[str, List[str]]):
        self.compositor = compositor
        self.privacy_config = privacy_config
        self.hotkeys = {
            hotkey_type: [key.lower() for key in keys]
            for hotkey_type, keys in hotkeys.items()
        }
        # logger.debug(f"Hotkeys: {self.hotkeys}")
        self.pressed_keys = set()
        self.is_running = False
        self.event_system = EventSystem()
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        self.recent_sessions = deque(maxlen=30)
        self.should_persist = False

        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

        # Key mapping (example, you might want to move this to a separate utility file)
        self.KEY_MAP = {
            "space": [" ", " "],
            "backspace": ["⌫", "⌫"],
            "enter": ["[enter]", "[enter]"], #"enter": ["\n", "\n"],
            "tab": ["↹", "↹"],
            "left": ["←", "←"],
            "right": ["→", "→"],
            "up": ["↑", "↑"],
            "down": ["↓", "↓"],
            #"esc": ["⎋", "⎋"],
            "1": ["1", "!"],
            "2": ["2", "@"],
            "3": ["3", "#"],
            "4": ["4", "$"],
            "5": ["5", "%"],
            "6": ["6", "^"],
            "7": ["7", "&"],
            "8": ["8", "*"],
            "9": ["9", "("],
            "0": ["0", ")"],
            "-": ["-", "_"],
            "=": ["=", "+"],
            "[": ["[", "{"],
            "]": ["]", "}"],
            "\\": ["\\", "|"],
            ";": [";", ":"],
            "'": ["'", '"'],
            ",": [",", "<"],
            ".": [".", ">"],
            "/": ["/", "?"],
            "`": ["`", "~"],
        }

        # Mouse button mapping (example)
        self.MOUSE_BUTTON_MAP = {
            "Button.left": "mouse_left",
            "Button.right": "mouse_right",
            "Button.middle": "mouse_middle",
            "BTN_LEFT": "mouse_left",
            "BTN_RIGHT": "mouse_right",
            "BTN_MIDDLE": "mouse_middle",
            # ... add more mappings as needed ...
        }

    @abc.abstractmethod
    async def start(self):
        """Starts input tracking."""
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self):
        """Stops input tracking."""
        raise NotImplementedError

    async def get_events(self) -> Dict[str, Any]:
        """Gets collected input events in a standardized format.
           This method also handles ending the current session.
        """
        # Get current window info
        current_window = await self.compositor.get_active_window()

        # End current session and get the data
        session_data = None
        if self.current_session:
            await self.current_session.end_session(datetime.now())
            session_data = await self.current_session.to_dict()
            self.current_session = None

        # Process pending sessions
        sessions = []
        for session in self.pending_sessions:
            if self.privacy_config.is_private(session.window_info):
                # Keep metadata but replace events with privacy filter
                sessions.append({
                    'window_class': session.window_info['class'],
                    'window_title': session.window_info['title'],
                    'duration': session.duration,
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat(),
                    'privacy_filtered': True,
                    'key_count': session.key_count,
                    'click_count': session.click_count,
                    'scroll_count': session.scroll_count,
                    'key_events': [],  # Empty events list
                    'click_events': [],
                    'scroll_events': []
                })
            else:
                sessions.append(await session.to_dict())

        if session_data:
            sessions.append(session_data)

        events = {
            "window_sessions": sessions,
            "counts": {
                "total_keys_pressed": self._total_keys,
                "total_clicks": self._total_clicks,
                "total_scrolls": self._total_scrolls
            },
            "timestamp": datetime.now().isoformat()
        }

        # Clear pending sessions and reset counters
        self.pending_sessions = []
        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

        # Create new session with the active window
        if current_window:
            await self._on_window_focus_change(current_window)

        return events

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

    async def _on_window_focus_change(self, window_info: Dict[str, str]) -> None:
        """Handle window focus changes."""
        now = datetime.now()

        # End current session if exists and add it to the list of sessions
        if self.current_session:
            await self.current_session.end_session(now)
            self.recent_sessions.append(self.current_session)

            if self.should_persist and not self.privacy_config.is_private(window_info):
                self.pending_sessions.append(self.current_session)

        # Start new session
        self.current_session = WindowSession(window_info, now)

    async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
        """Get recent sessions from buffer.
        
        Args:
            seconds: Number of seconds of history to return
            
        Returns:
            List of recent WindowSession objects
        """
        now = datetime.now()
        return [
            session for session in self.recent_sessions
            if (now - session.end_time).total_seconds() <= seconds
        ]

    async def _check_hotkeys(self):
        """Checks if a hotkey combination has been pressed."""
        # logger.debug(f"Checking hotkeys: {self.pressed_keys}")
        for hotkey_type, hotkey in self.hotkeys.items():
            required_keys = set(hotkey)
            if required_keys.issubset(self.pressed_keys):
                # Hotkey detected, broadcast the event
                await self.event_system.broadcaster.broadcast_hotkey(
                    HotkeyEvent(
                        timestamp=datetime.now().isoformat(),
                        hotkey_type=HotkeyEventType[hotkey_type.upper()] # Convert string to enum
                    )
                )

    def _standardize_key_name(self, key_name: str) -> str:
        """Standardizes a key name using the KEY_MAP, considering shift keys, and smartly handling uppercase letters."""
        key_name = key_name.lower()

        # Determine if shift is pressed
        shift_pressed = "leftshift" in self.pressed_keys or "rightshift" in self.pressed_keys

        # Handle uppercase letters smartly
        if shift_pressed and 'a' <= key_name <= 'z':
            standardized_key = key_name.upper()
        else:
            # Get the mapping from KEY_MAP, default to [key_name, key_name] if not found
            mapping = self.KEY_MAP.get(key_name, [key_name, key_name])
            # Select the appropriate version based on whether shift is pressed
            standardized_key = mapping[1] if shift_pressed else mapping[0]

        # logger.debug(f"Standardizing key name: {key_name} to {standardized_key} (shift pressed: {shift_pressed})")
        return standardized_key

    def _standardize_mouse_button(self, button: str) -> str:
        """Standardizes a mouse button name using the MOUSE_BUTTON_MAP."""
        # logger.debug(f"Standardizing mouse button: {button} to {self.MOUSE_BUTTON_MAP.get(button, button)}")
        return self.MOUSE_BUTTON_MAP.get(button, button)