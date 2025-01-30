import subprocess
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.compositor.macos import MacOSCompositor
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker
from src.utils.activity.trackers.inputs.macos import MacOSInputTracker
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType

logger = logging.getLogger(__name__)

class MacOSCoordinator:
    def __init__(self, privacy_config: PrivacyConfig, hotkeys: Dict[HotkeyEventType, str], mackeyserver_path: str):
        self.mackeyserver_path = mackeyserver_path
        self.process: Optional[subprocess.Popen] = None
        self.compositor: Optional[MacOSCompositor] = None
        self.input_tracker: Optional[MacOSInputTracker] = None
        self.privacy_config = privacy_config
        self.hotkeys = hotkeys
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def start(self):
        """Starts the Electron app and initializes the compositor and input tracker."""
        logger.info(f"Starting MacOSCoordinator with mackeyserver at {self.mackeyserver_path}")
        try:
            self.process = subprocess.Popen(
                [self.mackeyserver_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False,
            )
        except Exception as e:
            logger.error(f"Failed to start Electron app: {e}")
            return

        self.compositor = MacOSCompositor(self.process, self._event_queue)
        self.input_tracker = MacOSInputTracker(self.process, self.compositor, self.privacy_config, self.hotkeys, self._event_queue)

        # Start the event processing task
        asyncio.create_task(self._process_events())
        
        # Start listening for events in both compositor and input tracker
        await self.compositor.start()
        await self.input_tracker.start()

    async def stop(self):
        """Stops the Electron app, compositor, and input tracker."""
        logger.info("Stopping MacOSCoordinator")
        if self.input_tracker:
            await self.input_tracker.stop()
        if self.compositor:
            await self.compositor.cleanup()
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)  # Wait for process to terminate with a timeout
            except asyncio.TimeoutError:
                logger.warning("Electron app did not terminate gracefully, killing it")
                self.process.kill()
                
    async def _process_events(self):
        """Processes events from the queue."""
        while True:
            try:
                event_type, event_data = await self._event_queue.get()
                logger.debug(f"Processing event: {event_type}, Data: {event_data}")
                if event_type == "WINDOW_INFO":
                    if event_data["kind"] == "ACTIVE":
                        await self.compositor._on_window_focus_change(event_data)
                    # You might need to handle other WINDOW_INFO types here
                elif event_type in ["KEYBOARD", "MOUSE", "SCROLL", "MODIFIER"]:
                    await self.input_tracker._process_event(event_data)
                elif event_type == "APPLICATION":
                    await self.input_tracker._handle_application_event(event_data)
                else:
                    logger.warning(f"Unknown event type received: {event_type}")
            except Exception as e:
                logger.error(f"Error processing event: {e}")
            finally:
                self._event_queue.task_done()

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Gets the active window information from the compositor."""
        if self.compositor:
            return await self.compositor.get_active_window()
        return None

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Gets the list of all windows from the compositor."""
        if self.compositor:
            return await self.compositor.get_windows()
        return None

    async def cleanup(self):
        """Cleans up resources."""
        await self.stop()