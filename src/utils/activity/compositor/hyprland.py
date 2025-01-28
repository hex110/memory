# src/utils/activity/compositor/hyprland.py
import json
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Callable

from src.utils.activity.compositor.base_compositor import BaseCompositor

logger = logging.getLogger(__name__)

class HyprlandCompositor(BaseCompositor):
    """Compositor implementation for Hyprland."""

    WINDOW_CLASS_MAPPINGS = {
        # IDEs and editors
        ("cursor", "codium", "code"): "VSCode - IDE",
        ("intellij", "pycharm", "webstorm"): "JetBrains - IDE",
        ("sublime_text",): "Sublime - Editor",
        ("xed",): "Text Editor",
        
        # Browsers
        ("firefox", "zen"): "Firefox - Browser",
        ("chromium", "chrome"): "Chrome - Browser",
        ("brave",): "Brave - Browser",
        
        # Terminals
        ("kitty", "alacritty", "wezterm", "floating_term"): "Terminal",
        
        # Communication
        ("discord",): "Discord - Chat",
        ("telegram",): "Telegram - Chat",
        ("signal",): "Signal - Chat",
        
        # Media
        ("spotify",): "Spotify - Music",
        ("vlc", "mpv"): "Media Player",
        
        # Other common applications
        ("obsidian",): "Obsidian - Notes",
        ("zathura",): "Zathura - PDF Viewer",
    }

    def __init__(self) -> None:
        """Initialize Hyprland compositor interface."""
        self.running = False
        self._focus_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._socket_task: Optional[asyncio.Task] = None
        self._socket_reader: Optional[asyncio.StreamReader] = None
        self._socket_writer: Optional[asyncio.StreamWriter] = None
        self.active_workspaces = set()

    def _get_window_class_name(self, window_class: str) -> str:
        """Get the classified window name based on the window class."""
        if not window_class:
            return "Unknown"
            
        window_class = window_class.lower()
        
        for patterns, class_name in self.WINDOW_CLASS_MAPPINGS.items():
            if any(pattern in window_class for pattern in patterns):
                return class_name

        return window_class.title()

    async def update_active_workspaces(self) -> None:
        """Update the set of active workspaces across all monitors."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "monitors", "-j",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            monitors = json.loads(stdout.decode())
            
            new_active_workspaces = set()
            for monitor in monitors:
                workspace_id = monitor.get('activeWorkspace', {}).get('id')
                if workspace_id is not None:
                    new_active_workspaces.add(workspace_id)
            
            self.active_workspaces = new_active_workspaces
            
        except Exception as e:
            logger.error(f"Failed to update active workspaces: {e}")

    async def get_windows(self) -> List[Dict[str, Any]]:
        """Update the current window state."""
        await self.update_active_workspaces()
        windows: List[Dict[str, Any]] = []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "clients", "-j",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            window_list = json.loads(stdout.decode())
            
            for window_info in window_list:
                workspace = window_info.get('workspace', {})
                workspace_id = workspace.get('id') if isinstance(workspace, dict) else workspace

                window_data = {
                    'class': self._get_window_class_name(window_info.get('class', '')),
                    'title': window_info.get('title', ''),
                    'original_class': window_info.get('class', ''),
                    'position': window_info.get('at', [0, 0]),
                    'size': window_info.get('size', [0, 0]),
                    'workspace': workspace_id,
                }
                windows.append(window_data)
                    
        except Exception as e:
            logger.error(f"Failed to update windows: {e}")
            
        return windows

    async def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get currently focused window info."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "activewindow", "-j",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if not stdout:
                return None
            
            window_data = json.loads(stdout.decode())
            
            if not window_data:
                return None

            return {
                "class": self._get_window_class_name(window_data.get("class", "")),
                "title": window_data.get("title", ""),
                "original_class": window_data.get("class", "")
            }

        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
            return None

    async def setup_focus_tracking(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set up focus change tracking using Hyprland's IPC socket."""
        self._focus_callback = callback
        try:
            his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
            if not his:
                logger.error("HYPRLAND_INSTANCE_SIGNATURE not found in environment")
                return

            runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
            socket_path = f"{runtime_dir}/hypr/{his}/.socket2.sock"

            self.running = True
            self._socket_task = asyncio.create_task(self._listen_for_events(socket_path))

        except Exception as e:
            logger.error(f"Failed to setup IPC socket: {e}")

    async def _listen_for_events(self, socket_path: str) -> None:
        """Listen for events from Hyprland's IPC socket."""
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            self._socket_reader = reader
            self._socket_writer = writer

            while self.running:
                try:
                    data = await reader.read(1024)
                    if not data:
                        continue

                    decoded = data.decode()
                    for line in decoded.strip().split('\n'):
                        if line.startswith('activewindow>>'):
                            _, window_info = line.split('>>', 1)
                            if ',' in window_info:
                                window_class, window_title = window_info.split(',', 1)
                            else:
                                window_class = window_info
                                window_title = ""

                            class_name = self._get_window_class_name(window_class)

                            if self._focus_callback:
                                await self._focus_callback({
                                    "class": class_name,
                                    "title": window_title,
                                    "original_class": window_class
                                })
                            await self.update_active_workspaces()
                        elif any(line.startswith(event) for event in [
                            'workspace>>', 'workspacev2>>', 
                            'moveworkspace>>', 'moveworkspacev2>>',
                            'createworkspace>>', 'createworkspacev2>>',
                            'destroyworkspace>>', 'destroyworkspacev2>>'
                        ]):
                            await self.update_active_workspaces()

                except Exception as e:
                    logger.error(f"Error processing socket data: {e}")
                    if not self.running:
                        break
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"IPC socket error: {e}")
            self.running = False
        finally:
            if self._socket_writer:
                self._socket_writer.close()
                await self._socket_writer.wait_closed()

    def is_window_visible(self, window_info: Dict[str, Any]) -> bool:
        """Determine if a given window is currently visible on the screen."""
        return window_info.get('workspace') in self.active_workspaces

    async def cleanup(self) -> None:
        """Clean up IPC socket connection."""
        self.running = False
        if self._socket_task:
            self._socket_task.cancel()
            try:
                await self._socket_task
            except asyncio.CancelledError:
                pass
        if self._socket_writer:
            self._socket_writer.close()
            await self._socket_writer.wait_closed()