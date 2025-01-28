import logging
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import asyncio
import platform

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.compositor.hyprland import HyprlandCompositor
from src.utils.activity.trackers.screencapture import ScreenCapture
from src.utils.activity.trackers.audio_recorder import AudioRecorder
from src.utils.activity.trackers.inputs.base import BaseInputTracker
from src.utils.activity.trackers.inputs.evdev import EvdevInputTracker
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType

logger = logging.getLogger(__name__)

class ActivityManager:
    """Manages screen capture, audio recording, and input tracking."""

    def __init__(self, privacy_config_path: str = "src/utils/activity/privacy.json"):
        """Initialize ActivityManager.

        Args:
            privacy_config_path: Path to the privacy configuration file.
        """
        self.privacy_config = PrivacyConfig(privacy_config_path)
        self.compositor = self._get_compositor()
        self.input_tracker = self._get_input_tracker()
        self.screen_capture = self._get_screen_capture()
        self.audio_recorder = AudioRecorder()
        self.hotkey_actions: Dict[str, Dict[str, Callable]] = {}

    def _get_compositor(self) -> BaseCompositor:
        """Detect and return the appropriate compositor instance."""
        system = platform.system()
        if system == "Linux":
            if "HYPRLAND_INSTANCE_SIGNATURE" in platform.os.environ:
                return HyprlandCompositor()

        raise NotImplementedError(
            f"Compositor detection for {system} is not yet supported."
        )

    def _get_input_tracker(self) -> BaseInputTracker:
        """Detect and return the appropriate compositor instance."""
        system = platform.system()
        if system == "Linux":
            return EvdevInputTracker(self.compositor, self.privacy_config, hotkeys={})
        
        raise NotImplementedError(
            f"Input tracker detection for {system} is not yet supported."
        )
    
    def _get_screen_capture(self, backend: str = "grim") -> ScreenCapture:
        """Get the screen capture instance."""
        return ScreenCapture(self.compositor, self.privacy_config, backend=backend)

    async def start_recording(self):
        """Start video, audio recording, and input tracking."""
        await self.screen_capture.start_recording()
        await self.audio_recorder.start_recording()
        if not self.input_tracker.is_running:
            asyncio.create_task(self.input_tracker.start())
            # self.input_tracker.event_system.broadcaster.on_hotkey(self.handle_hotkey_event)

    async def stop_recording(self):
        """Stop video, audio recording, and input tracking.

        Returns:
            A dictionary containing the audio filepath, video buffer, and window sessions.
        """
        
        if self.input_tracker.is_running:
            await self.input_tracker.stop()
            
        audio_filepath = await self.audio_recorder.stop_recording()
        video_buffer = await self.screen_capture.get_video_buffer()
        window_sessions = await self.input_tracker.get_events()

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
        return await self.compositor.get_active_window()

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Get a list of all windows."""
        return await self.compositor.get_windows()

    async def get_recent_sessions(self, seconds: int = 60) -> List[Dict[str, Any]]:
        """Get recent window sessions from the InputTracker."""
        return await self.input_tracker.get_recent_sessions(seconds)

    def get_audio_filepath(self) -> Optional[Path]:
        """Get the filepath of the last recorded audio file."""
        return self.audio_recorder.filepath if hasattr(self.audio_recorder, "filepath") else None

    def get_video_buffer(self) -> Optional[bytes]:
        """Get the video buffer from the ScreenCapture."""
        return self.screen_capture.get_video_buffer()
    
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
        await self.compositor.cleanup()
        await self.screen_capture.cleanup()
        await self.audio_recorder.cleanup()
        if self.input_tracker.is_running:
            await self.input_tracker.stop()