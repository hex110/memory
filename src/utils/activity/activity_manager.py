import logging
import os
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import asyncio
import platform

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.compositor.hyprland import HyprlandCompositor
from src.utils.activity.trackers.screencapture import ScreenCapture
from src.utils.activity.trackers.audio_recorder import AudioRecorder
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker
from src.utils.activity.trackers.inputs.evdev import EvdevInputTracker
from src.utils.activity.trackers.inputs.pynput import PynputInputTracker
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType
from .macos_coordinator import MacOSCoordinator

logger = logging.getLogger(__name__)

class ActivityManager:
    """Manages screen capture, audio recording, and input tracking."""

    def __init__(self, config: Dict[str, Any], privacy_config_path: str = "src/utils/activity/privacy.json"):
        """Initialize ActivityManager."""
        self.video_duration = config["tracking"].get("video_duration", 30)
        self.hotkeys = config["hotkeys"]

        self.privacy_config = PrivacyConfig(privacy_config_path)
        
        # Mac OS integration
        self.system = platform.system()
        # self.system = "Darwin" # testing
        if self.system == "Darwin":  # macOS
            self.coordinator = MacOSCoordinator(self.privacy_config, self.hotkeys, "src/utils/activity/compositor/mackeyserver")
            self.compositor = self.coordinator.compositor
            self.input_tracker = self.coordinator.input_tracker
        else:
            self.coordinator = None
            self.compositor = self._get_compositor()
            self.input_tracker = self._get_input_tracker()

        self.hotkey_actions: Dict[HotkeyEventType, List[Callable]] = {}
        self.screen_capture = self._get_screen_capture()
        self.audio_recorder = AudioRecorder()

    def _get_compositor(self) -> BaseCompositor:
        """Detect and return the appropriate compositor instance."""
        if self.system == "Linux":
            if "HYPRLAND_INSTANCE_SIGNATURE" in platform.os.environ:
                return HyprlandCompositor()
        elif self.system == "Darwin":
            return self.coordinator.compositor if self.coordinator else None
        
        raise NotImplementedError(
            f"Compositor detection for {self.system} is not yet supported."
        )

    def _get_input_tracker(self) -> BaseInputTracker:
        """Detect and return the appropriate compositor instance."""
        if self.system == "Linux":
            # Check if it's Wayland or X11, you might need a better detection method
            if "WAYLAND_DISPLAY" in os.environ:
                return EvdevInputTracker(self.compositor, self.privacy_config, self.hotkeys)
            else:
                return PynputInputTracker(self.compositor, self.privacy_config, self.hotkeys)
        elif self.system == "Windows":
            return PynputInputTracker(self.compositor, self.privacy_config, self.hotkeys)
        elif self.system == "Darwin":  # macOS
            return self.coordinator.input_tracker if self.coordinator else None
        else:
            raise NotImplementedError(f"Input tracker not supported on {self.system}")
    
    def _get_screen_capture(self, backend: Optional[str] = None) -> ScreenCapture:
        """Get the screen capture instance."""
        if backend is None:
            if self.system == "Linux":
                # Check if it's Wayland or X11, you might need a better detection method
                if "WAYLAND_DISPLAY" in os.environ:
                    backend = "grim"  # Default for Wayland
                else:
                    backend = "mss"  # Fallback for X11 or if detection fails
            elif self.system == "Windows":
                backend = "mss"
            elif self.system == "Darwin":  # macOS
                backend = "mss"
            else:
                raise NotImplementedError(f"Screen capture backend not specified for {self.system}")

        return ScreenCapture(self.compositor, self.privacy_config, backend=backend, video_duration=self.video_duration)

    async def start_recording(self):
        """Start video, audio recording, and input tracking."""
        if self.system == "Darwin" and self.coordinator:
            await self.coordinator.start()
        await self.screen_capture.start_recording()
        await self.audio_recorder.start_recording()
        if self.input_tracker and not self.input_tracker.is_running:
            asyncio.create_task(self.input_tracker.start())

    async def stop_recording(self):
        """Stop video, audio recording, and input tracking.

        Returns:
            A dictionary containing the audio filepath, video buffer, and window sessions.
        """
        if self.input_tracker and self.input_tracker.is_running:
            await self.input_tracker.stop()
            
        audio_filepath = await self.audio_recorder.stop_recording()
        video_buffer = await self.screen_capture.get_video_buffer()
        window_sessions = await self.input_tracker.get_events()

        # Stop the coordinator if it's a macOS system
        if self.system == "Darwin" and self.coordinator:
            await self.coordinator.stop()

        return {
            "audio_filepath": audio_filepath,
            "video_buffer": video_buffer,
            "window_sessions": window_sessions,
        }
    
    async def handle_hotkey_event(self, event: HotkeyEvent):
        """Handle hotkey events triggered by the InputTracker."""
        if event.hotkey_type == HotkeyEventType.SPEAK:
            if not self.audio_recorder.is_recording:
                await self.start_recording()
            else:
                await self.stop_recording()
        elif event.hotkey_type in self.hotkey_actions:
            # Execute all actions associated with the hotkey type
            for action in self.hotkey_actions[event.hotkey_type]:
                await action() # Assuming actions are async functions

    async def capture_screenshot(self) -> Optional[str]:
        """Capture a single screenshot and return the base64 encoded image."""
        return await self.screen_capture.capture_and_encode()

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get information about the active window."""
        # Use the appropriate compositor based on the OS
        if self.system == "Darwin" and self.coordinator:
            return await self.coordinator.get_active_window()
        elif self.compositor:
            return await self.compositor.get_active_window()
        else:
            logger.warning("Compositor is not available.")
            return None

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Get a list of all windows."""
        # Use the appropriate compositor based on the OS
        if self.system == "Darwin" and self.coordinator:
            return await self.coordinator.get_windows()
        elif self.compositor:
            return await self.compositor.get_windows()
        else:
            logger.warning("Compositor is not available.")
            return []

    async def get_recent_sessions(self, seconds: int = 60) -> List[Dict[str, Any]]:
        """Get recent window sessions from the InputTracker."""
        return await self.input_tracker.get_recent_sessions(seconds)

    def get_audio_filepath(self) -> Optional[Path]:
        """Get the filepath of the last recorded audio file."""
        return self.audio_recorder.filepath if hasattr(self.audio_recorder, "filepath") else None

    def get_video_buffer(self) -> Optional[bytes]:
        """Get the video buffer from the ScreenCapture."""
        return self.screen_capture.get_video_buffer()
    
    async def start_audio_recording(self):
        """Start audio recording."""
        await self.audio_recorder.start_recording()
    
    async def stop_audio_recording(self):
        """Stop audio recording."""
        await self.audio_recorder.stop_recording()
    
    def register_hotkey(self, hotkey: str, hotkey_type: HotkeyEventType, callback: Callable):
        """Registers a hotkey action with the InputTracker.
        Hotkeys are registered to the input tracker when it is started.
        """
        if hotkey_type not in self.hotkey_actions:
            self.hotkey_actions[hotkey_type] = []
        self.hotkey_actions[hotkey_type].append(callback)

        # Update input tracker's hotkeys
        self.input_tracker.hotkeys[hotkey_type] = hotkey

    async def cleanup(self):
        """Clean up all resources."""
        if self.coordinator:
            await self.coordinator.cleanup()
        else:
            if self.compositor:
                await self.compositor.cleanup()
            if self.input_tracker and self.input_tracker.is_running:
                await self.input_tracker.stop()
        await self.screen_capture.cleanup()
        await self.audio_recorder.cleanup()