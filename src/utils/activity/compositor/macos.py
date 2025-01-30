import json
import logging
from typing import Dict, List, Any, Optional, Callable
import asyncio

from src.utils.activity.compositor.base_compositor import BaseCompositor

logger = logging.getLogger(__name__)

class MacOSCompositor(BaseCompositor):
    def __init__(self, process, event_queue: asyncio.Queue):
        self.process = process
        self._event_queue = event_queue
        self.window_info: Dict[str, Any] = {}  # Use a dictionary to store window information
        self._tasks: List[asyncio.Task] = []

    async def start(self):
        """Starts listening for window events from the MacKeyServer."""
        if self.process.stdout:
            task = asyncio.create_task(self._listen_for_window_events())
            self._tasks.append(task)
        else:
            logger.error("Cannot start MacOSCompositor: process.stdout is None.")

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Retrieves information about the currently active window."""
        active_window = self.window_info.get("active")
        if active_window:
            return active_window
        else:
            logger.debug("No active window found.")
            return None

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Retrieves a list of all open windows and their properties."""
        all_windows = self.window_info.get("all", [])
        logger.debug(f"All windows: {all_windows}")
        return all_windows

    async def setup_focus_tracking(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Sets up focus change tracking (not directly used for Mac, handled in _listen_for_window_events)."""
        logger.info("Setting up focus tracking. Callback: {callback}")
        # Focus tracking is handled by the event listener, but we still need the callback for hotkeys and such
        self._focus_callback = callback

    def is_window_visible(self, window_info: Dict[str, Any]) -> bool:
        """Determine if a given window is currently visible on the screen."""
        # Simple check for now: if a window is in the "all" list, consider it visible.
        all_windows = self.window_info.get("all", [])
        return any(window == window_info for window in all_windows)

    async def _listen_for_window_events(self):
        """Listens for window events from the MacKeyServer's stdout."""
        while True:
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
                    logger.debug(f"Received line: {line}")
                    parts = line.split(",", 2)

                    if parts[0] == "WINDOW_INFO":
                        _, kind, json_data, _ = line.split(",", 3)  # Assuming 4 parts
                        data = json.loads(json_data)
                        logger.debug(f"Received window event: {kind}, Data: {data}")

                        if kind == "ACTIVE":
                            self.window_info["active"] = data
                            await self._event_queue.put(("WINDOW_INFO", data))

                        elif kind == "ALL":
                            self.window_info["all"] = data

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON for window event: {e}")
                    logger.error(f"Received line: {line}")
                except Exception as e:
                    logger.error(f"Error processing window event: {e}")
            else:
                logger.warning("Process stdout is None.")
                await asyncio.sleep(1)

    async def _on_window_focus_change(self, window_data: Dict[str, Any]) -> None:
        """Handle window focus changes."""
        # Call the callback with the new active window information
        if self._focus_callback:
            await self._focus_callback(window_data)

    async def cleanup(self):
        """Cleans up resources."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.window_info = {}