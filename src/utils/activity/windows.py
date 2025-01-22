"""Window tracking functionality.

This module provides window tracking capabilities for different window managers.
The base WindowManagerInterface allows for easy addition of new window managers,
while the HyprlandManager provides specific implementation for Hyprland.

Core features:
- Abstract interface for window managers
- Focus history tracking
- Window metadata parsing
- Window classification
- Error recovery

Example:
    ```python
    tracker = WindowTracker()
    
    # Get current window state
    window_data = tracker.get_window_state()
    if window_data:
        print(f"Active windows: {len(window_data['windows'])}")
    ```
"""

import subprocess
import logging
import os
import socket
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from abc import ABC, abstractmethod

from src.utils.exceptions import WindowTrackingError

# Set up logging
logger = logging.getLogger(__name__)

class WindowManagerInterface(ABC):
    """Abstract interface for window manager implementations.
    
    This interface defines the required methods that any window manager
    implementation must provide for window tracking functionality.
    """
    
    @abstractmethod
    def get_active_window(self) -> Optional[Dict[str, str]]:
        """Get currently focused window info.
        
        Returns:
            Dict with window info (class, title) or None if no active window
        """
        pass
    
    @abstractmethod
    def setup_focus_tracking(self, callback: Callable[[Dict[str, str]], None]) -> None:
        """Set up focus change tracking.
        
        Args:
            callback: Function to call when window focus changes
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up any resources used by the window manager."""
        pass

class HyprlandManager(WindowManagerInterface):
    """Hyprland-specific window manager implementation."""
    
    # Window classification mappings
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
        """Initialize Hyprland window manager interface."""
        self.windows: List[Dict[str, Any]] = []
        self.socket_thread: Optional[threading.Thread] = None
        self.running = False
        self._focus_callback: Optional[Callable[[Dict[str, str]], None]] = None
        logger.debug("HyprlandManager initialized")
    
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
    
    def setup_focus_tracking(self, callback: Callable[[Dict[str, str]], None]) -> None:
        """Set up focus change tracking using Hyprland's IPC socket."""
        self._focus_callback = callback
        try:
            # Get Hyprland instance signature
            his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
            if not his:
                logger.error("HYPRLAND_INSTANCE_SIGNATURE not found in environment")
                return

            # Construct socket path
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
            self.socket_path = f"{runtime_dir}/hypr/{his}/.socket2.sock"
            
            # Start socket listening thread
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
                        # Format: activewindow>>WINDOWCLASS,WINDOWTITLE
                        _, window_info = line.split('>>', 1)
                        window_class, window_title = window_info.split(',', 1)
                        class_name = self._get_window_class_name(window_class)
                        
                        if self._focus_callback:
                            self._focus_callback({
                                "class": class_name,
                                "title": window_title,
                                "original_class": window_class
                            })
                        
        except Exception as e:
            logger.error(f"IPC socket error: {e}")
            self.running = False
        finally:
            sock.close()
    
    def get_active_window(self) -> Optional[Dict[str, str]]:
        """Get currently focused window info."""
        try:
            # Capture current window state
            result = subprocess.run(
                ["hyprctl", "activewindow"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse the output
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
        logger.debug("HyprlandManager cleaned up")