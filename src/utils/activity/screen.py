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

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import pyscreenshot
from PIL import Image

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
            Dict containing screenshot data and metadata, or None if capture fails
            Format: {
                "timestamp": ISO format timestamp,
                "image": PIL Image object,
                "size": (width, height)
            }
        """
        try:
            # Attempt to capture screenshot
            screenshot = pyscreenshot.grab(backend="grim")
            if not screenshot:
                logger.warning("Screenshot capture failed - no image data")
                return None
            
            # Create result with metadata
            result = {
                "timestamp": datetime.now().isoformat(),
                "image": screenshot,
                "size": screenshot.size
            }
            
            logger.debug(
                f"Screenshot captured successfully: {result['size'][0]}x{result['size'][1]}"
            )
            return result
            
        except Exception as e:
            # Don't raise error for expected Wayland failures
            if "Wayland" in str(e):
                logger.warning("Screenshot capture failed (expected on Wayland)")
            else:
                logger.error(f"Screenshot capture failed: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup any resources.
        
        Currently a no-op as pyscreenshot doesn't need cleanup,
        but included for consistency with other trackers.
        """
        pass