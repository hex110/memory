"""Window tracking functionality.

This module provides window tracking capabilities through the WindowManager class.
Currently implements Hyprland-specific window management, with architecture
supporting future window manager implementations.

Core features:
- Window state tracking
- Focus history tracking
- Window metadata parsing
- Window classification
- Error recovery
"""

import json
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Callable

from src.utils.exceptions import WindowTrackingError

# Set up logging
logger = logging.getLogger(__name__)

class WindowManager:
    """Window manager implementation for tracking and managing window state."""
    
    # Keeping the existing window classification mappings
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
        """Initialize window manager interface."""
        self.windows: List[Dict[str, Any]] = []
        self.running = False
        self._focus_callback: Optional[Callable[[Dict[str, str]], None]] = None
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

    async def update_windows(self) -> None:
        """Update the current window state."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "clients", "-j",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            window_list = json.loads(stdout.decode())
            self.windows = []  # Clear existing windows
            
            for window_info in window_list:
                # Get workspace ID, handling both dictionary and direct integer cases
                workspace = window_info.get('workspace', {})
                workspace_id = workspace.get('id') if isinstance(workspace, dict) else workspace
                
                window_data = {
                    'class': self._get_window_class_name(window_info.get('class', '')),
                    'title': window_info.get('title', ''),
                    'original_class': window_info.get('class', ''),
                    'position': window_info.get('at', [0, 0]),
                    'size': window_info.get('size', [0, 0]),
                    'workspace': workspace_id,
                    'visible': workspace_id in self.active_workspaces
                }
                self.windows.append(window_data)
                    
        except Exception as e:
            logger.error(f"Failed to update windows: {e}")
    
    async def get_windows(self) -> List[Dict[str, Any]]:
        """Get current window state.
        
        Returns:
            List of dictionaries containing window information
        """
        await self.update_windows()
        await self.update_active_workspaces()
        return self.windows
    
    async def setup_focus_tracking(self, callback: Callable[[Dict[str, str]], None]) -> None:
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
            # logger.debug("IPC socket listener started")
            
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
                            window_class, window_title = window_info.split(',', 1)
                            class_name = self._get_window_class_name(window_class)
                            
                            if self._focus_callback:
                                await self._focus_callback({
                                    "class": class_name,
                                    "title": window_title,
                                    "original_class": window_class
                                })
                            await self.update_active_workspaces()
                            await self.update_windows()
                        # Add workspace change event handling
                        elif any(line.startswith(event) for event in [
                            'workspace>>', 'workspacev2>>', 
                            'moveworkspace>>', 'moveworkspacev2>>',
                            'createworkspace>>', 'createworkspacev2>>',
                            'destroyworkspace>>', 'destroyworkspacev2>>'
                        ]):
                            await self.update_active_workspaces()
                            await self.update_windows()
                            
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
    
    async def get_active_window(self) -> Optional[Dict[str, str]]:
        """Get currently focused window info."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "activewindow",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            
            window_class = ""
            window_title = ""
            
            for line in output.split("\n"):
                line = line.strip()
                if ": " in line:
                    key, value = line.split(": ", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "class":
                        window_class = value
                    elif key == "title":
                        window_title = value
            
            if window_class:
                class_name = self._get_window_class_name(window_class)
                return {
                    "class": class_name,
                    "title": window_title,
                    "original_class": window_class
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
            return None
    
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
        # logger.debug("WindowManager cleaned up")
