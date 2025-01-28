"""Privacy configuration management.

This module provides the PrivacyConfig class for managing privacy settings
for window tracking and screenshot capture. It handles both persistent
and temporary privacy rules through a JSON configuration file.
"""

import json
import logging
from pathlib import Path
import re
from typing import Dict

# Set up logging
logger = logging.getLogger(__name__)

class PrivacyConfig:
    """Manages privacy settings for window tracking and screenshots."""
    
    def __init__(self, config_path: str = "src/utils/activity/privacy.json"):
        """Initialize privacy configuration.
        
        Args:
            config_path: Path to privacy config JSON file
        """
        self.config_path = Path(config_path).expanduser()
        
        # Default configuration
        self.config = {
            "always_private": [],      # Window titles that are always private
            "current_private": []      # Temporarily private windows
        }
        
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create default
        self.load_config()
    
    def load_config(self) -> None:
        """Load privacy configuration from file."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    loaded_config = json.load(f)
                    # Update config while preserving structure
                    for key in self.config:
                        if key in loaded_config:
                            self.config[key] = loaded_config[key]
            else:
                self.save_config()
                
        except Exception as e:
            logger.error(f"Error loading privacy config: {e}")
            self.save_config()
    
    def save_config(self) -> None:
        """Save current privacy configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.debug("Privacy config saved to file")
        except Exception as e:
            logger.error(f"Error saving privacy config: {e}")
    
    def is_private(self, window_info: Dict[str, str]) -> bool:
        """Check if a window should be private based on current config.
        
        Args:
            window_info: Dictionary containing window class and title
            
        Returns:
            True if window should be private, False otherwise
        """
        window_title = window_info.get('title', '')
        
        # Check privacy patterns using regex
        for pattern in self.config['always_private'] or self.config['current_private']:
            try:
                if re.search(pattern, window_title, re.IGNORECASE):
                    return True
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")
                # Fall back to simple case-insensitive substring match if regex is invalid
                if pattern.lower() in window_title.lower():
                    return True
            
        return False
    
    def add_temporary_private(self, window_title: str) -> None:
        """Add a window title to temporary privacy list.
        
        Args:
            window_title: Window title to make private
        """
        if window_title not in self.config['current_private']:
            self.config['current_private'].append(window_title)
            self.save_config()
            logger.debug(f"Added temporary privacy for: {window_title}")
    
    def remove_temporary_private(self, window_title: str) -> None:
        """Remove a window title from temporary privacy list.
        
        Args:
            window_title: Window title to remove privacy from
        """
        if window_title in self.config['current_private']:
            self.config['current_private'].remove(window_title)
            self.save_config()
            logger.debug(f"Removed temporary privacy for: {window_title}")
    
    def add_always_private(self, window_title: str) -> None:
        """Add a window title to always private list.
        
        Args:
            window_title: Window title to always make private
        """
        if window_title not in self.config['always_private']:
            self.config['always_private'].append(window_title)
            self.save_config()
            logger.debug(f"Added to always private: {window_title}")
    
    def remove_always_private(self, window_title: str) -> None:
        """Remove a window title from always private list.
        
        Args:
            window_title: Window title to remove from always private
        """
        if window_title in self.config['always_private']:
            self.config['always_private'].remove(window_title)
            self.save_config()
            logger.debug(f"Removed from always private: {window_title}")