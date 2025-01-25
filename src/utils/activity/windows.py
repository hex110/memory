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
import subprocess
import logging
import os
import socket
import threading
from datetime import datetime
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
        self.socket_thread: Optional[threading.Thread] = None
        self.running = False
        self._focus_callback: Optional[Callable[[Dict[str, str]], None]] = None
        self.update_active_workspaces()
        self.update_windows()  # Initial window state
        logger.debug("WindowManager initialized")
    
    def _get_window_class_name(self, window_class: str) -> str:
        """Get the classified window name based on the window class."""
        if not window_class:
            return "Unknown"
            
        window_class = window_class.lower()
        logger.debug(f"Classifying window class: {window_class}")
        
        for patterns, class_name in self.WINDOW_CLASS_MAPPINGS.items():
            if any(pattern in window_class for pattern in patterns):
                logger.debug(f"Matched {window_class} to {class_name}")
                return class_name
                
        logger.debug(f"No classification found for {window_class}")
        return window_class.title()
    
    def update_active_workspaces(self) -> None:
        """Update the set of active workspaces across all monitors."""
        try:
            result = subprocess.run(
                ["hyprctl", "monitors", "-j"],
                capture_output=True,
                text=True,
                check=True
            )
            monitors = json.loads(result.stdout)
            
            new_active_workspaces = set()
            for monitor in monitors:
                workspace_id = monitor.get('activeWorkspace', {}).get('id')
                if workspace_id is not None:
                    new_active_workspaces.add(workspace_id)
            
            self.active_workspaces = new_active_workspaces
            logger.debug(f"Active workspaces updated: {self.active_workspaces}")
            
        except subprocess.CalledProcessError:
            logger.error("Failed to execute hyprctl monitors")
        except Exception as e:
            logger.error(f"Failed to update active workspaces: {e}")

    def update_windows(self) -> None:
        """Update the current window state."""
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True,
                text=True,
                check=True
            )
            window_list = json.loads(result.stdout)
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
                    
        except subprocess.CalledProcessError:
            logger.error("Failed to execute hyprctl clients")
        except Exception as e:
            logger.error(f"Failed to update windows: {e}")
    
    def get_windows(self) -> List[Dict[str, Any]]:
        """Get current window state.
        
        Returns:
            List of dictionaries containing window information
        """
        return self.windows
    
    # Keeping all existing methods unchanged
    def setup_focus_tracking(self, callback: Callable[[Dict[str, str]], None]) -> None:
        """Set up focus change tracking using Hyprland's IPC socket."""
        self._focus_callback = callback
        try:
            his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
            if not his:
                logger.error("HYPRLAND_INSTANCE_SIGNATURE not found in environment")
                return

            runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
            self.socket_path = f"{runtime_dir}/hypr/{his}/.socket2.sock"
            
            self.running = True
            self.socket_thread = threading.Thread(target=self._listen_for_events)
            self.socket_thread.daemon = True
            self.socket_thread.start()
            logger.debug("IPC socket listener started")
            
        except Exception as e:
            logger.error(f"Failed to setup IPC socket: {e}")
    
    def _listen_for_events(self) -> None:
        """Listen for events from Hyprland's IPC socket."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            while self.running:
                data = sock.recv(1024).decode()
                if not data:
                    continue
                    
                for line in data.strip().split('\n'):
                    if line.startswith('activewindow>>'):
                        _, window_info = line.split('>>', 1)
                        window_class, window_title = window_info.split(',', 1)
                        class_name = self._get_window_class_name(window_class)
                        
                        if self._focus_callback:
                            self._focus_callback({
                                "class": class_name,
                                "title": window_title,
                                "original_class": window_class
                            })
                        self.update_active_workspaces()  # Update workspace state
                        self.update_windows()  # Update window state
                    # Add workspace change event handling
                    elif any(line.startswith(event) for event in [
                        'workspace>>', 'workspacev2>>', 
                        'moveworkspace>>', 'moveworkspacev2>>',
                        'createworkspace>>', 'createworkspacev2>>',
                        'destroyworkspace>>', 'destroyworkspacev2>>'
                    ]):
                        self.update_active_workspaces()
                        self.update_windows()
                        
        except Exception as e:
            logger.error(f"IPC socket error: {e}")
            self.running = False
        finally:
            sock.close()
    
    def get_active_window(self) -> Optional[Dict[str, str]]:
        """Get currently focused window info."""
        try:
            result = subprocess.run(
                ["hyprctl", "activewindow"],
                capture_output=True,
                text=True,
                check=True
            )
            
            window_class = ""
            window_title = ""
            
            for line in result.stdout.split("\n"):
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
            
        except subprocess.CalledProcessError:
            logger.error("Failed to execute hyprctl activewindow")
            return None
        except Exception as e:
            logger.error(f"Failed to get active window: {e}")
            return None
    
    def cleanup(self) -> None:
        """Clean up IPC socket connection."""
        self.running = False
        if self.socket_thread:
            self.socket_thread.join(timeout=1.0)
        logger.debug("WindowManager cleaned up")