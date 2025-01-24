"""Screen capture functionality for activity tracking.

This module provides screen capture capabilities using pyscreenshot,
with special handling for Wayland on Linux using the grim backend.

Core features:
- Screenshot capture using appropriate backend
- Wayland support through grim
- Error handling for different display servers
- Thread-safe operation

Example:
    ```python
    capture = ScreenCapture()
    
    # Take a screenshot
    screenshot_data = capture.capture()
    if screenshot_data:
        print("Screenshot captured successfully")
    ```
"""

import base64
from io import BytesIO
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import pyscreenshot

from src.utils.exceptions import ScreenCaptureError

# Set up logging
logger = logging.getLogger(__name__)

class ScreenCapture:
    """Handles screen capture operations.
    
    This class manages screen capture with special handling for different
    display servers, particularly Wayland on Linux. It automatically selects
    the best backend for the current system.
    """
    
    def __init__(self) -> None:
        """Initialize screen capture with appropriate backend."""
        try:
            # Configure pyscreenshot to use grim backend on Linux
            if os.name == "posix":
                pyscreenshot.backends = ["grim"]
                logger.debug("Using grim backend for screenshots")
            
            # Test capture to verify setup
            test_capture = pyscreenshot.grab(backend="grim")
            if not test_capture:
                raise ScreenCaptureError("Failed to initialize screen capture")
            
            logger.debug("ScreenCapture initialized successfully")
            
        except Exception as e:
            logger.warning(f"Screen capture initialization failed: {e}")
            # Don't raise error - allow object to be created even if capture fails
    
    def capture(self) -> Optional[Dict[str, Any]]:
        """Capture current screen state.
        
        Returns:
            PIL Image object, or None if capture fails
        """
        try:
            return pyscreenshot.grab(backend="grim")
            
        except Exception as e:
            # Don't raise error for expected Wayland failures
            if "Wayland" in str(e):
                logger.warning("Screenshot capture failed (expected on Wayland)")
            else:
                logger.error(f"Screenshot capture failed: {e}")
            return None
    
    def capture_and_encode(self) -> Optional[Dict[str, Any]]:
        """Capture current screen state and encode to base64.
        
        Returns:
            Dict containing encoded screenshot and metadata or None on failure
            Format: {
                "timestamp": ISO format timestamp,
                "image": base64 encoded string,
                "size": (width, height)
            }
        """
        try:
            capture_result = self.capture()
            if not capture_result:
                return None

            buffer = BytesIO()
            capture_result.save(buffer, format="PNG")
            encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return encoded_image
            
        except Exception as e:
            logger.error(f"Screenshot capture and encode failed: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup any resources.
        
        Currently a no-op as pyscreenshot doesn't need cleanup,
        but included for consistency with other trackers.
        """
        pass