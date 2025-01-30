import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from collections import deque

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.session import WindowSession
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker

logger = logging.getLogger(__name__)

class MacOSInputTracker(BaseInputTracker):
    """Tracks keyboard and mouse activity using events from MacKeyServer."""

    def __init__(self, process, compositor: BaseCompositor, privacy_config: PrivacyConfig, hotkeys: Dict[HotkeyEventType, str], event_queue: asyncio.Queue):
        """Initialize the input tracker."""
        super().__init__(compositor, privacy_config, hotkeys)
        self.process = process
        self.event_system = EventSystem()
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        self.recent_sessions = deque(maxlen=30)
        self.should_persist = False
        self._tasks: List[asyncio.Task] = []
        self._event_queue = event_queue

        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

    async def _process_event(self, event_data):
        """Processes a single input event."""
        try:
            if not self.is_running:
                return

            event_type = event_data["type"]
            timestamp = datetime.now().isoformat()

            # Skip if no current session or if the current window is private
            if not self.current_session or self.privacy_config.is_private(self.current_session.window_info):
                return

            if event_type == "KEYBOARD":
                key_event = event_data["event"]
                key_name = key_event["key"]
                action = key_event["action"]
                
                # Update pressed_keys for modifier keys
                if key_name.upper() in ["CMD", "SHIFT", "CTRL", "ALT", "FN"]:
                    if action == "DOWN":
                        self.pressed_keys.add(key_name.lower())
                    elif action == "UP":
                        self.pressed_keys.discard(key_name.lower())

                if action == "DOWN":
                    self._total_keys += 1
                    standardized_key = self._standardize_key_name(key_name)
                    
                    # Infer "hold" event
                    asyncio.create_task(self._handle_hold_event(standardized_key, timestamp))
                    
                    await self.current_session.add_event("key", {
                        "type": "press",
                        "key": standardized_key,
                        "timestamp": timestamp
                    })
                    await self._check_hotkeys()

            elif event_type == "MOUSE":
                mouse_event = event_data["event"]
                button = mouse_event["button"]
                action = mouse_event["action"]
                if action == "DOWN":
                    button_name = self._standardize_mouse_button(button)
                    self._total_clicks += 1
                    await self.current_session.add_event("click", {
                        "button": button_name,
                        "timestamp": timestamp
                    })

            elif event_type == "SCROLL":
                scroll_event = event_data["event"]
                scroll_delta = scroll_event["delta"]
                # Determine scroll direction based on delta
                scroll_direction = "vertical" if scroll_delta > 0 else "horizontal"
                # Update total scroll count
                self._total_scrolls += abs(scroll_delta)
                # Add scroll event to current session
                await self.current_session.add_event("scroll", {
                    "direction": scroll_direction,
                    "amount": scroll_delta,  # Use the delta value
                    "timestamp": timestamp
                })
                
            elif event_type == "MODIFIER":
                modifier_event = event_data["event"]
                modifier = modifier_event["modifier"]
                state = modifier_event["state"]  # "DOWN" or "UP"

                if state == "DOWN":
                    self.pressed_keys.add(modifier.lower())
                    logger.debug(f"Modifier {modifier} pressed. Pressed keys: {self.pressed_keys}")
                elif state == "UP":
                    self.pressed_keys.discard(modifier.lower())
                    logger.debug(f"Modifier {modifier} released. Pressed keys: {self.pressed_keys}")

        except Exception as e:
            logger.error(f"Error processing input event: {e}", exc_info=True)
            
    async def _handle_application_event(self, data):
        """Handles application change events from MacKeyServer."""
        app_name = data.get("name")
        if app_name:
            if self.current_session:
                await self.current_session.end_session(datetime.now())
                self.recent_sessions.append(self.current_session)
                if self.should_persist and not self.privacy_config.is_private(self.current_session.window_info):
                    self.pending_sessions.append(self.current_session)

            # Create new session with the new app name
            self.current_session = WindowSession({
                "class": app_name,
                "title": "",  # Window title not available
                "original_class": app_name,
            }, datetime.now())

    async def _handle_hold_event(self, key: str, timestamp: str):
        """Handles a potential 'hold' event for a key."""
        await asyncio.sleep(0.1)  # Adjust the delay as needed
        if key.lower() in self.pressed_keys:
            # Key is still pressed after the delay, consider it a hold event
            await self.current_session.add_event("key", {
                "type": "hold",
                "key": key,
                "timestamp": timestamp
            })

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
        
        if self.process and self.process.stdout:
            task = asyncio.create_task(self._listen_for_input_events())
            self._tasks.append(task)
        else:
            logger.error("Cannot start MacOSInputTracker: process or process.stdout is None.")

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

    async def _listen_for_input_events(self):
        """Listens for input events from the MacKeyServer's stdout."""
        while self.is_running:
            if self.process.stdout:
                try:
                    line = await self.process.stdout.readline()
                    if not line:
                        if self.process.poll() is not None:  # Check if the process has terminated
                            logger.info("MacKeyServer process has terminated. Stopping listener.")
                            break
                        else:
                            await asyncio.sleep(0.1)  # Wait a bit before trying again
                            continue
                    
                    line = line.decode("utf-8").strip()
                    parts = line.split(",", 1)

                    if parts[0] in ["KEYBOARD", "MOUSE", "SCROLL", "MODIFIER", "APPLICATION"]:
                        # Parse the rest of the line as JSON
                        try:
                            _, json_data, _ = line.split(",", 2)  # Split into 3 parts, discarding the last one
                            data = json.loads(json_data)
                            data["type"] = parts[0]  # Add the type to the data dict
                            
                            if parts[0] == "APPLICATION":
                                await self._handle_application_event(data)
                            else:
                                await self._event_queue.put((parts[0], data))
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode JSON for input event: {e}")
                            logger.error(f"Received line: {line}")

                except Exception as e:
                    logger.error(f"Error processing input event: {e}")
            else:
                logger.warning("Process stdout is None. Waiting before retrying...")
                await asyncio.sleep(1)  # Wait for a while before retrying

    async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
        """Get recent sessions from buffer."""
        now = datetime.now()
        return [
            session for session in self.recent_sessions
            if (now - session.end_time).total_seconds() <= seconds
        ]

    async def _on_window_focus_change(self, window_info: Dict[str, Any]) -> None:
        """Handle window focus changes."""
        if window_info:
            window_info_for_session = {
                "class": window_info.get("ownerName"),
                "title": window_info.get("windowName"),
                "original_class": window_info.get("ownerName")
            }
        else:
            window_info_for_session = {}
                    
        now = datetime.now()

        # End current session if exists and add it to the list of sessions
        if self.current_session:
            await self.current_session.end_session(now)
            self.recent_sessions.append(self.current_session)

            if self.should_persist and not self.privacy_config.is_private(window_info_for_session):
                self.pending_sessions.append(self.current_session)

        # Start new session
        self.current_session = WindowSession(window_info_for_session, now)