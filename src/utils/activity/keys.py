import asyncio
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

import evdev
from evdev import InputDevice, categorize, ecodes

from src.utils.exceptions import KeyboardTrackingError
from src.utils.activity.windows import WindowManagerInterface
from src.utils.activity.session import WindowSession

# Set up logging
logger = logging.getLogger(__name__)

class ActivityTracker:
    """Tracks keyboard and mouse activity using evdev.
    
    This class handles input device monitoring with support for:
    - Event filtering through callbacks
    - Thread-safe event collection
    - Automatic device discovery
    - Window-based activity tracking
    - Error recovery
    """
    
    def __init__(self, window_manager: WindowManagerInterface) -> None:
        """Initialize the activity tracker.
        
        Args:
            window_manager: Window manager implementation to use
        """
        # Event storage
        self.current_session: Optional[WindowSession] = None
        self.pending_sessions: List[WindowSession] = []
        
        # Tracking state
        self.devices: List[InputDevice] = []
        self.is_running = False
        self.window_manager = window_manager
        
        # Event filtering
        self._should_track_callback: Optional[Callable[[], bool]] = None
        
        # Async management
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._tasks: List[asyncio.Task] = []
        
        # Event totals
        self._total_keys = 0
        self._total_clicks = 0
        self._total_scrolls = 0
        
        logger.debug("ActivityTracker initialized")
    
    def set_tracking_filter(self, callback: Callable[[], bool]) -> None:
        """Set a callback to determine if events should be tracked."""
        self._should_track_callback = callback
        logger.debug("Tracking filter set")
    
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
    
    def _on_window_focus_change(self, window_info: Dict[str, str]) -> None:
        """Handle window focus changes.
        
        Args:
            window_info: Information about the newly focused window
        """
        now = datetime.now()
        
        # End current session if exists and add it to the list of sessions
        if self.current_session:
            self.current_session.end_session(now)
            self.pending_sessions.append(self.current_session)

        # Start new session
        self.current_session = WindowSession(window_info, now)
        logger.debug(f"Started new session for {window_info['class']}")
    
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
            async for event in device.async_read_loop():
                if not self.is_running:
                    break
                    
                # Check if we should track this event
                if self._should_track_callback and not self._should_track_callback():
                    continue
                
                # Skip if no active window session
                if not self.current_session:
                    continue

                if event.type == evdev.ecodes.EV_KEY:
                    timestamp = datetime.now().isoformat()
                    
                    # Handle mouse buttons (BTN_LEFT to BTN_TASK)
                    if event.code in range(272, 280):
                        if event.value == 1:  # Press only
                            self._total_clicks += 1
                            self.current_session.add_event("click", {
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
                                
                                self.current_session.add_event("key", {
                                    "type": event_type,
                                    "key": key,
                                    "timestamp": timestamp
                                })
                            
                elif event.type == evdev.ecodes.EV_REL:
                    # Track both vertical and horizontal scroll
                    if event.code in [evdev.ecodes.REL_WHEEL, evdev.ecodes.REL_HWHEEL]:
                        self._total_scrolls += abs(event.value)
                        if self.current_session:
                            self.current_session.add_event("scroll", {
                                "direction": "vertical" if event.code == evdev.ecodes.REL_WHEEL else "horizontal",
                                "amount": event.value,
                                "timestamp": datetime.now().isoformat()
                            })
                            
        except Exception as e:
            logger.warning(f"Device monitoring error: {e}")
            if device in self.devices:
                self.devices.remove(device)
    
    async def _monitor_all_devices(self) -> None:
        """Monitor all discovered input devices."""
        try:
            self._tasks = [
                asyncio.create_task(self._monitor_device(device))
                for device in self.devices
            ]
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to monitor devices: {e}")
    
    def _run_event_loop(self) -> None:
        """Run the event loop in a separate thread."""
        try:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            self._event_loop.run_until_complete(self._monitor_all_devices())
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            if self._event_loop:
                self._event_loop.close()
    
    def start(self) -> None:
        """Start tracking keyboard and mouse events."""
        try:
            if not self.devices:
                self.find_input_devices()
            
            if not self.devices:
                raise KeyboardTrackingError("No input devices found")
            
            # Set up window focus tracking
            self.window_manager.setup_focus_tracking(self._on_window_focus_change)

            # Start with current window if any
            current_window = self.window_manager.get_active_window()
            if current_window:
                self._on_window_focus_change(current_window)
            
            self.is_running = True
            self._thread = threading.Thread(target=self._run_event_loop)
            self._thread.daemon = True
            self._thread.start()
            logger.info("Activity tracking started")
            
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to start tracking: {e}")
    
    def stop(self) -> None:
        """Stop tracking keyboard and mouse events."""
        try:
            logger.info("Stopping activity tracking...")
            self.is_running = False
            
            # End current session if exists
            if self.current_session:
                self.current_session.end_session(datetime.now())
                self.current_session = None
            
            # Cancel all tasks
            if self._event_loop and self._tasks:
                for task in self._tasks:
                    self._event_loop.call_soon_threadsafe(task.cancel)
            
            # Close devices
            for device in self.devices:
                try:
                    device.close()
                except Exception as e:
                    logger.warning(f"Error closing device: {e}")
            
            self.devices = []
            
            # Wait for thread to finish
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
                
        except Exception as e:
            raise KeyboardTrackingError(f"Failed to stop tracking: {e}")
    
    def get_events(self) -> Dict[str, Any]:
        """Get collected events and reset counters.
        
        Returns:
            Dict containing window sessions and event totals
        """
        
        # Get current window info
        current_window = self.window_manager.get_active_window()
        
        # End current session and get the data, if any
        session_data = None
        if self.current_session:
            self.current_session.end_session(datetime.now())
            session_data = self.current_session.to_dict()
            self.current_session = None
        
        sessions = []
        
        sessions.extend([s.to_dict() for s in self.pending_sessions])

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
            self._on_window_focus_change(current_window)
        
        return events