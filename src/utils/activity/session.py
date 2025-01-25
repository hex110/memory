"""Window session tracking functionality.

This module provides the WindowSession class for tracking activity
within a specific window focus period. It maintains information about
keyboard/mouse events and timing for a single window session.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Set up logging
logger = logging.getLogger(__name__)

class WindowSession:
    """Tracks activity data for a single window focus period."""
    
    def __init__(self, window_info: Dict[str, str], start_time: datetime):
        """Initialize a new window session.
        
        Args:
            window_info: Dict containing window class and title
            start_time: When this window gained focus
        """
        self.window_info = window_info
        self.start_time = start_time
        self.end_time: Optional[datetime] = None
        
        # Event tracking
        self.key_events: List[Dict[str, Any]] = []
        self.click_count = 0
        self.scroll_count = 0
        self.key_count = 0
        
        logger.debug(
            f"Started window session for {window_info['class']} at {start_time}"
        )
    
    async def add_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Add an input event to this session.
        
        Args:
            event_type: Type of event (key, click, scroll)
            event_data: Event details
        """
        if event_type == "key":
            self.key_events.append(event_data)
            self.key_count += 1
        elif event_type == "click":
            self.click_count += 1
        elif event_type == "scroll":
            self.scroll_count += 1
    
    async def end_session(self, end_time: datetime) -> None:
        """End this window session.
        
        Args:
            end_time: When this window lost focus
        """
        self.end_time = end_time
        logger.debug(
            f"Ended window session for {self.window_info['class']} "
            f"after {self.duration:.2f} seconds"
        )
    
    @property
    def duration(self) -> float:
        """Get session duration in seconds."""
        if not self.end_time:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()
    
    async def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary format for storage.
        
        Returns:
            Dict containing all session data
        """
        return {
            "window_class": self.window_info["class"],
            "window_title": self.window_info["title"],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "key_events": self.key_events,
            "click_count": self.click_count,
            "scroll_count": self.scroll_count,
            "key_count": self.key_count
        }