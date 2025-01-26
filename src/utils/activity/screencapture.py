"""Screen capture functionality."""

import base64
from datetime import datetime
from io import BytesIO
import logging
import os
import aiofiles
import asyncio
from typing import Optional, Dict, Any

import pyscreenshot
from PIL import Image, ImageDraw, ImageFont

from src.utils.activity.windows import WindowManager
from src.utils.activity.privacy import PrivacyConfig

# Set up logging
logger = logging.getLogger(__name__)

class ScreenCapture:
    """Handles screen capture and privacy filtering."""

    def __init__(self, window_manager: WindowManager, privacy_config: PrivacyConfig):
        """Initialize screen capture.
        
        Args:
            window_manager: Window manager for getting window positions
            privacy_config: Privacy configuration to use
        """
        self.window_manager = window_manager
        self.privacy_config = privacy_config

    async def capture_and_encode(self) -> Optional[str]:
        """Capture screen, apply privacy filtering, and encode to base64."""
        try:
            # Run screenshot capture in a thread pool since it's CPU-bound
            screenshot = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pyscreenshot.grab(backend="grim")
            )
            
            # Convert to PIL Image for drawing
            img = screenshot if isinstance(screenshot, Image.Image) else Image.fromarray(screenshot)
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("/usr/share/fonts/OTF/SF-Pro-Rounded-Regular.otf", 128)  # Adjust size as needed
            except:
                font = ImageFont.load_default()  # Fallback to default font if unable to load
            
            # Apply privacy filtering only for visible windows
            windows = await self.window_manager.get_windows()
            for window in windows:
                if window['visible'] and self.privacy_config.is_private(window):
                    # Draw black rectangle over private window
                    x, y = window['position']
                    width, height = window['size']
                    draw.rectangle([(x, y), (x + width, y + height)], fill='black')

                    # Prepare the text
                    class_name = window.get('class', 'Unknown Window')
                    text = f"Window: {class_name}\nFiltered for privacy"
                    
                    # Calculate text size to center it
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Calculate center position
                    text_x = x + (width - text_width) // 2
                    text_y = y + (height - text_height) // 2
                    
                    # Draw white text
                    draw.text((text_x, text_y), text, fill='white', font=font, align='center')
                    
                    # logger.debug(f"Applied privacy filter to visible window: {window['class']}")

            # Save debug image
            try:
                debug_path = "debug_screenshots"
                os.makedirs(debug_path, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = os.path.join(debug_path, f"screenshot_{timestamp}.png")
                
                # Save image in a buffer
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                buffer.seek(0)
                
                # Write buffer to file asynchronously
                async with aiofiles.open(debug_file, 'wb') as f:
                    await f.write(buffer.getvalue())
                # logger.debug(f"Saved debug screenshot to {debug_file}")
            except Exception as e:
                logger.warning(f"Failed to save debug screenshot: {e}")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return encoded
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def cleanup(self) -> None:
        """Clean up any resources."""
        pass