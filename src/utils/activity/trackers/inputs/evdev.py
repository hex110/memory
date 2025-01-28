import asyncio
import errno
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from collections import deque

import evdev
from evdev import InputDevice, categorize, ecodes

from src.utils.exceptions import KeyboardTrackingError
from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.session import WindowSession
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker

logger = logging.getLogger(__name__)

class EvdevInputTracker(BaseInputTracker):
    """Tracks keyboard and mouse activity using evdev."""
    
    def __init__(self, compositor: BaseCompositor, privacy_config: PrivacyConfig, hotkeys: Dict[HotkeyEventType, str]):
        """Initialize the input tracker."""
        super().__init__(compositor, privacy_config, hotkeys)
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        self.recent_sessions = deque(maxlen=30)
        self.should_persist = False
        self.devices: List[InputDevice] = []
        self._device_tasks: List[asyncio.Task] = []
        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0

    async def enable_persistence(self) -> None:
        """Enable saving sessions to pending_sessions."""
        self.should_persist = True

    async def disable_persistence(self) -> None:
        """Disable saving sessions to pending_sessions."""
        self.should_persist = False
    
    def find_input_devices(self) -> None:
        """Find all keyboard and mouse input devices."""
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            found_devices: List[InputDevice] = []
            
            for device in devices:
                caps = device.capabilities()
                
                if evdev.ecodes.EV_KEY in caps:
                    # Check for keyboard keys
                    if any(code in range(evdev.ecodes.KEY_ESC, evdev.ecodes.KEY_MICMUTE + 1)
                           for code in caps[evdev.ecodes.EV_KEY]):
                        found_devices.append(device)
                    # Check for mouse buttons
                    elif any(code in range(evdev.ecodes.BTN_MOUSE, evdev.ecodes.BTN_TASK + 1)
                            for code in caps[evdev.ecodes.EV_KEY]):
                        found_devices.append(device)
            
            self.devices = found_devices
            
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to find input devices: {e}")

    async def _monitor_device(self, device: InputDevice) -> None:
        """Monitor a single input device for events."""
        try:
            async for event in device.async_read_loop():
                if not self.is_running:
                    break

                # Skip if no current session or if the current window is private
                if not self.current_session or self.privacy_config.is_private(self.current_session.window_info):
                    continue

                if event.type == evdev.ecodes.EV_KEY:
                    
                    key_name = evdev.ecodes.keys.get(event.code)
                    if isinstance(key_name, list):
                        key_name = key_name[0]
                    # logger.debug(f"Key name: {key_name}, event value: {event.value}")

                    # Simplify handling mouse button and keyboard keys
                    if key_name:
                        
                        event_type = "press" if event.value == 1 else "release" if event.value == 0 else "hold"
                        timestamp = datetime.now().isoformat()
                        
                        if key_name.startswith("BTN_"):
                            # Handle mouse button event
                            if event_type == "press":
                                button_name = self._standardize_mouse_button(key_name)
                                self._total_clicks += 1
                                # logger.debug(f"Mouse button pressed: {button_name}")
                                await self.current_session.add_event("click", {
                                    "button": button_name,
                                    "timestamp": timestamp
                                })
                        elif key_name.startswith("KEY_"):
                            # Handle keyboard key event
                            key = key_name[4:] # Remove the KEY_ prefix

                            # Update pressed_keys for modifier keys
                            # if key in ["LEFTSHIFT", "RIGHTSHIFT"]:
                            if event_type == "press":
                                self.pressed_keys.add(key.lower())
                            elif event_type == "release":
                                self.pressed_keys.discard(key.lower())
                            
                            # logger.debug(f"Pressed keys: {self.pressed_keys}")
                            if event_type == "press":
                                self._total_keys += 1
                                standardized_key = self._standardize_key_name(key)
                                # logger.debug(f"Key pressed: {standardized_key}")
                                await self.current_session.add_event("key", {
                                        "type": event_type,
                                        "key": standardized_key,
                                        "timestamp": timestamp
                                    })
                                
                                # Check for hotkeys
                                # logger.debug(f"Checking hotkeys: {self.pressed_keys}")
                                await self._check_hotkeys()

                elif event.type == evdev.ecodes.EV_REL:
                    # Track both vertical and horizontal scroll
                    if event.code in [evdev.ecodes.REL_WHEEL, evdev.ecodes.REL_HWHEEL]:
                        self._total_scrolls += abs(event.value)
                        # Log the scroll event
                        scroll_direction = "vertical" if event.code == evdev.ecodes.REL_WHEEL else "horizontal"
                        scroll_amount = event.value
                        # logger.debug(f"Mouse scrolled: {scroll_direction}, amount: {scroll_amount}")
                        
                        if self.current_session:
                            await self.current_session.add_event("scroll", {
                                "direction": scroll_direction,
                                "amount": scroll_amount,
                                "timestamp": datetime.now().isoformat()
                            })

        except (OSError, IOError) as e:
            if e.errno == errno.ENODEV:
                logger.warning(f"Device {device} disconnected")
                if device in self.devices:
                    self.devices.remove(device)
            else:
                logger.warning(f"Device error: {e}, retrying...")
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # logger.debug("Stopping monitoring task")
            raise
        except Exception as e:
            logger.error(f"Error in input monitoring: {e}", exc_info=True)
            await asyncio.sleep(1)

    async def _monitor_all_devices(self) -> None:
        """Monitor all discovered input devices."""
        self._device_tasks = [
            asyncio.create_task(self._monitor_device(device))
            for device in self.devices
        ]
        if self._device_tasks:
            await asyncio.wait(self._device_tasks, return_when=asyncio.FIRST_COMPLETED)
    
    async def start(self) -> None:
        """Start tracking keyboard and mouse events."""
        if self.is_running:
            return
        
        try:
            self.find_input_devices()
            if not self.devices:
                raise KeyboardTrackingError("No input devices found")
            
            await self.compositor.setup_focus_tracking(self._on_window_focus_change)

            current_window = await self.compositor.get_active_window()
            if current_window:
                await self._on_window_focus_change(current_window)
            
            self.is_running = True
            await self._monitor_all_devices()
            
        except Exception as e:
            logger.error(f"Failed to start tracking: {e}")
    
    async def stop(self) -> None:
        """Stop tracking keyboard and mouse events."""
        self.is_running = False

        # End current session if exists
        if self.current_session:
            await self.current_session.end_session(datetime.now())
            self.current_session = None

        # Cancel all monitoring tasks
        for task in self._device_tasks:
            task.cancel()
        
        # Close all devices
        for device in self.devices:
            try:
                device.close()
            except Exception as e:
                logger.warning(f"Error closing device: {e}")

        self.devices = []
        self._device_tasks = []

    # async def get_recent_sessions(self, seconds: int = 60) -> List[WindowSession]:
    #     """Get recent sessions from buffer.
        
    #     Args:
    #         seconds: Number of seconds of history to return
            
    #     Returns:
    #         List of recent WindowSession objects
    #     """
    #     now = datetime.now()
    #     return [
    #         session for session in self.recent_sessions
    #         if (now - session.end_time).total_seconds() <= seconds
    #     ]