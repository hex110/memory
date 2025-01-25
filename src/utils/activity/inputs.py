"""Input tracking functionality.

This module provides input device monitoring with support for:
- Event filtering through privacy settings
- Thread-safe event collection
- Automatic device discovery
- Window-based activity tracking
- Error recovery
"""

import asyncio
import errno
import logging
from datetime import datetime
import select
from typing import Dict, List, Optional, Any, Callable

import evdev
from evdev import InputDevice, categorize, ecodes

from src.utils.exceptions import KeyboardTrackingError
from src.utils.activity.windows import WindowManager
from src.utils.activity.session import WindowSession
from src.utils.activity.privacy import PrivacyConfig

# Set up logging
logger = logging.getLogger(__name__)

class InputTracker:
    """Tracks keyboard and mouse activity using evdev."""
    
    def __init__(self, window_manager: WindowManager, privacy_config: PrivacyConfig) -> None:
        """Initialize the input tracker.
        
        Args:
            window_manager: Window manager implementation to use
            privacy_config: Privacy configuration to use
        """
        # Event storage
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        
        # Tracking state
        self.devices: List[InputDevice] = []
        self.is_running = False
        self.window_manager = window_manager
        self.privacy_config = privacy_config
        
        # Event filtering
        self._should_track_callback: Optional[Callable[[], bool]] = None
        
        # Add callback for Ctrl+C detection
        self._on_interrupt_callback: Optional[Callable[[], None]] = None

        # Async management
        self._device_tasks: List[asyncio.Task] = []
        
        # Event totals
        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0
        
        logger.debug("InputTracker initialized")
    
    def set_interrupt_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when Ctrl+C is detected."""
        self._on_interrupt_callback = callback

    def _get_button_name(self, code: int) -> str:
        """Convert button codes to human-readable names."""
        button_map = {
            272: "Button.left",
            273: "Button.right",
            274: "Button.middle",
            275: "Button.side",
            276: "Button.extra",
            277: "Button.forward",
            278: "Button.back",
            279: "Button.task",
        }
        return button_map.get(code, f"Button.{code}")
    
    async def _on_window_focus_change(self, window_info: Dict[str, str]) -> None:
        """Handle window focus changes.
        
        Args:
            window_info: Information about the newly focused window
        """
        now = datetime.now()
        
        # End current session if exists and add it to the list of sessions
        if self.current_session:
            await self.current_session.end_session(now)
            
            # Only add non-private sessions to pending
            if not self.privacy_config.is_private(window_info):
                self.pending_sessions.append(self.current_session)
            else:
                logger.debug(f"Skipping private session for {window_info['class']}")

        # Start new session
        self.current_session = WindowSession(window_info, now)
    
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
            logger.info(f"Found {len(self.devices)} input devices")
            
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to find input devices: {e}")

    async def _monitor_device(self, device: InputDevice) -> None:
        """Monitor a single input device for events."""
        try:
            while self.is_running:
                try:
                    async for event in device.async_read_loop():
                        if not self.is_running:
                            break
                    
                        # Allow other coroutines to run
                        await asyncio.sleep(0)

                        # Check for Ctrl+C
                        if (event.type == evdev.ecodes.EV_KEY and 
                            event.code == evdev.ecodes.KEY_C and 
                            event.value == 1):  # Key press
                            
                            # Check if Ctrl is held down
                            active_keys = device.active_keys()
                            if evdev.ecodes.KEY_LEFTCTRL in active_keys or evdev.ecodes.KEY_RIGHTCTRL in active_keys:
                                logger.info("Ctrl+C detected, stopping monitoring...")
                                self.is_running = False
                                asyncio.create_task(self.stop())
                                break
                        
                        # Check if we should track this event
                        if self._should_track_callback and not self._should_track_callback():
                            continue

                        # Skip if no active window session
                        if not self.current_session:
                            continue

                        # Skip if current window is private
                        if self.privacy_config.is_private(self.current_session.window_info):
                            continue

                        if event.type == evdev.ecodes.EV_KEY:
                            timestamp = datetime.now().isoformat()
                            
                            # Handle mouse buttons (BTN_LEFT to BTN_TASK)
                            if event.code in range(272, 280):
                                if event.value == 1:  # Press only
                                    self._total_clicks += 1
                                    await self.current_session.add_event("click", {
                                        "button": self._get_button_name(event.code),
                                        "timestamp": timestamp
                                    })
                            
                            # Handle keyboard keys
                            elif event.code in evdev.ecodes.keys:
                                key_name = evdev.ecodes.keys[event.code]
                                # Only track actual keyboard keys
                                if key_name.startswith("KEY_"):
                                    event_type = ("press" if event.value == 1 else 
                                                "release" if event.value == 0 else "hold")
                                    
                                    if event_type == "press":
                                        self._total_keys += 1
                                        # Convert key names to more readable format
                                        key = key_name[4:]  # Remove KEY_ prefix
                                        if len(key) == 1:
                                            key = key.lower()
                                        elif key in ["LEFTSHIFT", "RIGHTSHIFT", "LEFTCTRL", 
                                                "RIGHTCTRL", "LEFTALT", "RIGHTALT", 
                                                "LEFTMETA", "RIGHTMETA"]:
                                            continue  # Skip modifier keys
                                        
                                        await self.current_session.add_event("key", {
                                            "type": event_type,
                                            "key": key,
                                            "timestamp": timestamp
                                        })
                                    
                        elif event.type == evdev.ecodes.EV_REL:
                            # Track both vertical and horizontal scroll
                            if event.code in [evdev.ecodes.REL_WHEEL, evdev.ecodes.REL_HWHEEL]:
                                self._total_scrolls += abs(event.value)
                                if self.current_session:
                                    await self.current_session.add_event("scroll", {
                                        "direction": "vertical" if event.code == evdev.ecodes.REL_WHEEL else "horizontal",
                                        "amount": event.value,
                                        "timestamp": datetime.now().isoformat()
                                    })
                
                except (OSError, IOError) as e:
                    if e.errno == errno.ENODEV:  # Device has been removed
                        break
                    logger.warning(f"Device error: {e}, retrying...")
                    await asyncio.sleep(1)
                    continue
        
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Device monitoring error: {e}")
            if device in self.devices:
                self.devices.remove(device)
        finally:
            try:
                device.close()
            except Exception as e:
                logger.warning(f"Error closing device: {e}")
    
    async def _monitor_all_devices(self) -> None:
        """Monitor all discovered input devices."""
        try:
            self._device_tasks = [
                asyncio.create_task(self._monitor_device(device))
                for device in self.devices
            ]
            # if self._device_tasks:
            #     await asyncio.gather(*self._device_tasks, return_exceptions=True)
                
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to monitor devices: {e}")
    
    async def start(self) -> None:
        """Start tracking keyboard and mouse events."""
        try:
            if not self.devices:
                self.find_input_devices()
            
            if not self.devices:
                raise KeyboardTrackingError("No input devices found")
            
            # Set up window focus tracking
            await self.window_manager.setup_focus_tracking(self._on_window_focus_change)

            # Start with current window if any
            current_window = await self.window_manager.get_active_window()
            if current_window:
                await self._on_window_focus_change(current_window)
            
            self.is_running = True
            await self._monitor_all_devices()
            logger.info("Input tracking started")
            
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to start tracking: {e}")
    
    async def stop(self) -> None:
        """Stop tracking keyboard and mouse events."""
        try:
            logger.info("Stopping input tracking...")
            self.is_running = False
            
            # End current session if exists
            if self.current_session:
                await self.current_session.end_session(datetime.now())
                self.current_session = None
            
            # Cancel all tasks
            for task in self._device_tasks:
                task.cancel()
            
            # Close devices
            for device in self.devices:
                try:
                    device.close()
                except Exception as e:
                    logger.warning(f"Error closing device: {e}")
            
            self.devices = []
            
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to stop tracking: {e}")
    
    async def get_events(self) -> Dict[str, Any]:
        """Get collected events and reset counters.

        Returns:
            Dict containing window sessions and event totals
        """
        # Get current window info
        current_window = await self.window_manager.get_active_window()

        # End current session and get the data
        session_data = None
        if self.current_session:
            await self.current_session.end_session(datetime.now())
            if self.privacy_config.is_private(self.current_session.window_info):
                # Keep metadata but replace events with privacy filter
                session_data = {
                    'window_class': self.current_session.window_info['class'],
                    'window_title': self.current_session.window_info['title'],
                    'duration': self.current_session.duration,
                    'start_time': self.current_session.start_time.isoformat(),
                    'end_time': self.current_session.end_time.isoformat(),
                    'privacy_filtered': True,
                    'key_count': self.current_session.key_count,
                    'click_count': self.current_session.click_count,
                    'scroll_count': self.current_session.scroll_count,
                    'key_events': [],  # Empty events list
                    'click_events': [],
                    'scroll_events': []
                }
            else:
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