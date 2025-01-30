import subprocess
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.compositor.macos import MacOSCompositor
from src.utils.activity.trackers.inputs.baseinput import BaseInputTracker
from src.utils.activity.trackers.inputs.macos import MacOSInputTracker
from src.utils.activity.trackers.privacy import PrivacyConfig
from src.utils.events import HotkeyEvent, HotkeyEventType
from src.utils.activity.compositor.macosevent import EventType

logger = logging.getLogger(__name__)

class MacOSCoordinator:
    def __init__(
        self,
        privacy_config: PrivacyConfig,
        hotkeys: Dict[HotkeyEventType, str],
        mackeyserver_path: str,
    ):
        self.mackeyserver_path = mackeyserver_path
        self.process: Optional[subprocess.Popen] = None
        self.privacy_config = privacy_config
        self.hotkeys = hotkeys
        self.stopping = False
        self.initial_session_created = False

        logger.info(
            f"Starting MacOSCoordinator with mackeyserver at {self.mackeyserver_path}"
        )
        try:
            self.process = subprocess.Popen(
                ["python", self.mackeyserver_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
            )
        except Exception as e:
            logger.error(f"Failed to start MacKeyServer: {e}", exc_info=True)
            return

        self.compositor = MacOSCompositor()
        self.input_tracker = MacOSInputTracker(
            self.compositor, self.privacy_config, self.hotkeys
        )

        self._stdout_reader = asyncio.StreamReader()
        self._stderr_reader = asyncio.StreamReader()

    async def start(self):
        """Starts the MacKeyServer and initializes the compositor and input tracker."""
        loop = asyncio.get_event_loop()

        # Create StreamReader instances for stdout and stderr
        loop.create_task(
            self._create_stream_reader(self.process.stdout, self._stdout_reader)
        )
        loop.create_task(
            self._create_stream_reader(self.process.stderr, self._stderr_reader)
        )

        # Setup focus tracking (make sure this is done before starting compositor)
        await self.compositor.setup_focus_tracking(
            self.input_tracker._on_window_focus_change
        )

        # Start the event processing task
        asyncio.create_task(self._process_events())

        # Start compositor and input tracker
        await self.compositor.start()
        await self.input_tracker.start()

    async def stop(self):
        """Stops the MacKeyServer, compositor, and input tracker."""
        self.stopping = True
        logger.info("Stopping MacOSCoordinator")
        if self.input_tracker:
            await self.input_tracker.stop()
        if self.compositor:
            await self.compositor.cleanup()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                logger.warning("MacKeyServer did not terminate gracefully, killing it")
                self.process.kill()
            finally:
                if self.process.returncode is None:
                    self.process.wait()

    async def _create_stream_reader(self, stream, reader):
        """Setup a StreamReader and start reading from a stream."""
        loop = asyncio.get_event_loop()
        loop.add_reader(stream.fileno(), self._read_from_stream, stream, reader)

    def _read_from_stream(self, stream, reader):
        """Callback to read data from a stream and feed it to a StreamReader."""
        data = stream.read1(4096)
        if data:
            reader.feed_data(data)
        else:
            reader.feed_eof()

    async def _process_events(self):
        """Processes events from the stdout of the MacKeyServer."""
        while not self.stopping:
            line = await self._stdout_reader.readline()
            if not line:
                if self.process.poll() is not None:
                    logger.info(
                        "MacKeyServer process has terminated. Stopping listener."
                    )
                    break
                else:
                    await asyncio.sleep(0.1)
                    continue
            try:
                event_type, data = self._parse_event_line(line.decode("utf-8").strip())
                # logger.debug(f"Received event: {event_type}, data: {data}")

                if event_type in [EventType.WINDOW_INFO, EventType.APPLICATION]:
                    await self._handle_window_or_application_event(event_type, data)
                else:
                    await self.input_tracker._process_event(event_type, data)

            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Error processing line: {line}. Error: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")

    def _parse_event_line(self, line: str) -> Tuple[EventType, Dict[str, Any]]:
        """Parses a line of event data from MacKeyServer."""
        parts = line.split(",", 1)
        if len(parts) == 2:
            event_type_str, rest = parts
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                raise ValueError(f"Unknown event type received: {event_type_str}")

            if event_type in [EventType.APPLICATION, EventType.WINDOW_INFO]:
                try:
                    json_data, event_id = rest.rsplit(",", 1)
                    data = json.loads(json_data)
                    data["event_id"] = int(event_id)
                    return event_type, data
                except (ValueError, json.JSONDecodeError) as e:
                    raise ValueError(
                        f"Error parsing JSON for event type {event_type_str}: {e}"
                    )
            else:
                data = self._parse_input_event(event_type_str, rest)
                return event_type, data
        else:
            raise ValueError(f"Invalid line format received: {line}")

    def _parse_input_event(self, event_type_str: str, rest: str) -> Dict[str, Any]:
        """Parses event data for input events (non-JSON)."""
        parts = rest.split(",")
        data = {}

        try:
            event_id = int(parts[-1])
            data["event_id"] = event_id
            parts = parts[:-1]  # Remove event_id from parts

            if event_type_str == "CHARACTER":
                # Format: CHARACTER,DOWN/UP,char,x,y,modifiers,event_id
                data["type"] = "CHARACTER"
                data["action"] = parts[0]
                data["key"] = parts[1]
                data["x"] = float(parts[2])
                data["y"] = float(parts[3])
                data["modifiers"] = parts[4]
            elif event_type_str == "SPECIAL_KEY":
                # Format: SPECIAL_KEY,DOWN/UP,key_name,x,y,modifiers,event_id
                data["type"] = "SPECIAL_KEY"
                data["action"] = parts[0]
                data["key"] = parts[1]
                data["x"] = float(parts[2])
                data["y"] = float(parts[3])
                data["modifiers"] = parts[4]
            elif event_type_str == "MODIFIER":
                # Format: MODIFIER,KeyCode,DOWN/UP,x,y,event_id,flags
                data["type"] = "MODIFIER"
                data["modifier"] = parts[0]
                data["state"] = parts[1]
                data["x"] = float(parts[2])
                data["y"] = float(parts[3])
                data["flags"] = parts[4] if len(parts) > 4 else ""
            elif event_type_str == "MOUSE":
                # Format: MOUSE,DOWN/UP/MOVE/SCROLL,button,x,y,event_id (button is 0 for left, 1 for right, 2 for middle, etc.)
                # Format: MOUSE,SCROLL,delta,x,y,event_id
                # Format: MOUSE,MOVE,x,y,event_id
                data["type"] = "MOUSE"
                data["action"] = parts[0]
                if parts[0] == "SCROLL":
                    data["delta"] = int(parts[1]) if parts[1].isdigit() else parts[1]
                    data["x"] = float(parts[2])
                    data["y"] = float(parts[3])
                elif parts[0] == "MOVE":
                    data["x"] = float(parts[1])
                    data["y"] = float(parts[2])
                else:
                    data["button"] = int(parts[1]) if parts[1].isdigit() else parts[1]
                    data["x"] = float(parts[2])
                    data["y"] = float(parts[3])
            else:
                logger.warning(
                    f"Unknown event type for CSV parsing: {event_type_str}"
                )

        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing CSV event data: {rest}. Error: {e}")
            return {}

        return data

    async def _handle_window_or_application_event(
        self, event_type: EventType, data: Dict[str, Any]
    ):
        """Handles window and application events."""
        if event_type == EventType.WINDOW_INFO:
            if data["kind"] == "ACTIVE":
                self.compositor.window_info["active"] = data
                if not self.initial_session_created:
                    await self.input_tracker._on_window_focus_change(data)
                    self.initial_session_created = True
                else:
                    await self.input_tracker._on_window_focus_change(data)
            elif data["kind"] == "ALL":
                self.compositor.window_info["all"] = data
        elif event_type == EventType.APPLICATION:
            # You might not need a separate application event handler if
            # window focus changes are handled correctly.
            pass

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Gets the active window information from the compositor."""
        return await self.compositor.get_active_window()

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Gets the list of all windows from the compositor."""
        return await self.compositor.get_windows()

    async def cleanup(self):
        """Cleans up resources."""
        await self.stop()