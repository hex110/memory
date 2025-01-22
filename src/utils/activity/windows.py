"""Window tracking functionality for Hyprland.

This module provides window tracking capabilities for the Hyprland
window manager. It captures window state and metadata using hyprctl.

Core features:
- Window state capture using hyprctl
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
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.utils.exceptions import WindowTrackingError

# Set up logging
logger = logging.getLogger(__name__)

class WindowTracker:
    """Tracks active windows and their metadata using hyprctl.
    
    This class manages window state tracking for Hyprland:
    - Captures window metadata using hyprctl
    - Tracks window focus history
    - Maintains window ordering
    - Classifies windows based on application type
    
    The tracker uses the hyprctl command-line tool to gather
    window information and maintains the window order based
    on focus history.
    """
    
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
        """Initialize window tracker."""
        self.windows: List[Dict[str, Any]] = []
        logger.debug("WindowTracker initialized")
    
    def _get_window_class_name(self, window_class: str) -> str:
        """Get the classified window name based on the window class.
        
        Args:
            window_class: The original window class from hyprctl
            
        Returns:
            The classified window name or the original class if no match
        """
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
    
    def _parse_hyprctl_output(self, output: str) -> None:
        """Parse the output of hyprctl clients command.
        
        Args:
            output: Raw output string from hyprctl clients
        """
        try:
            windows = []
            current_window = {}
            
            for line in output.split("\n"):
                line = line.strip()
                
                if line.startswith("Window ") and " -> " in line:
                    if current_window:  # Save previous window if exists
                        # Get the classified window name
                        window_class = current_window.get("class", "")
                        class_name = self._get_window_class_name(window_class)
                        
                        windows.append({
                            "title": current_window.get("title", ""),
                            "class": class_name,
                            "original_class": window_class,  # Keep original for debugging
                            "focusHistoryID": int(current_window.get("focusHistoryID", 999))
                        })
                        logger.debug(f"Parsed window: {class_name} - {current_window.get('title', '')}")
                    
                    current_window = {}
                    current_window["title"] = line.split(" -> ")[1].strip(":")
                    
                elif ": " in line:
                    key, value = line.split(": ", 1)
                    key = key.strip()
                    value = value.strip()
                    current_window[key] = value
            
            # Don't forget the last window
            if current_window:
                window_class = current_window.get("class", "")
                class_name = self._get_window_class_name(window_class)
                
                windows.append({
                    "title": current_window.get("title", ""),
                    "class": class_name,
                    "original_class": window_class,  # Keep original for debugging
                    "focusHistoryID": int(current_window.get("focusHistoryID", 999))
                })
                logger.debug(f"Parsed window: {class_name} - {current_window.get('title', '')}")
            
            # Sort windows by focusHistoryID
            self.windows = sorted(windows, key=lambda x: x["focusHistoryID"])
            
            # Remove focusHistoryID and original_class from final output
            for window in self.windows:
                del window["focusHistoryID"]
                del window["original_class"]
            
            logger.debug(f"Parsed {len(self.windows)} windows")
            
        except Exception as e:
            logger.error(f"Failed to parse window data: {e}")
            raise WindowTrackingError(f"Failed to parse window data: {e}")
    
    def get_window_state(self) -> Optional[Dict[str, Any]]:
        """Get current window state.
        
        Returns:
            Dict containing window state data and metadata, or None if capture fails
            Format: {
                "timestamp": ISO format timestamp,
                "windows": List of window data with class and title,
                "active_window": Currently focused window (if any)
            }
        """
        try:
            # Capture current window state
            result = subprocess.run(
                ["hyprctl", "clients"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse the output
            self._parse_hyprctl_output(result.stdout)
            
            # Create result with metadata
            window_state = {
                "timestamp": datetime.now().isoformat(),
                "windows": self.windows,
                "active_window": self.windows[0] if self.windows else None
            }
            
            logger.debug(f"Captured window state: {len(self.windows)} windows")
            return window_state
            
        except subprocess.CalledProcessError as e:
            logger.error("Failed to execute hyprctl clients")
            return None
        except Exception as e:
            logger.error(f"Failed to capture window state: {e}")
            return None
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get currently focused window.
        
        Returns:
            Dict containing active window data, or None if no active window
        """
        state = self.get_window_state()
        return state["active_window"] if state else None
    
    def cleanup(self) -> None:
        """Cleanup any resources.
        
        Currently a no-op as window tracking doesn't need cleanup,
        but included for consistency with other trackers.
        """
        pass