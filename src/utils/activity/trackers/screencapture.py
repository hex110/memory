"""Screen capture functionality with video buffer support."""

import base64
from datetime import datetime
import logging
from io import BytesIO
from collections import deque
import asyncio
from typing import Optional
import cv2
import numpy as np
import pyscreenshot
from PIL import Image, ImageDraw, ImageFont

from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.privacy import PrivacyConfig

logger = logging.getLogger(__name__)

class ScreenCapture:
    """Handles screen capture and privacy filtering with video buffer support."""

    def __init__(self, compositor: BaseCompositor, privacy_config: PrivacyConfig, backend: str = "grim", buffer_duration_seconds: int = 15):
        """Initialize screen capture.
        
        Args:
            compositor: Compositor for getting window information
            privacy_config: Privacy configuration to use
            backend: Backend for pyscreenshot (e.g., "grim", "mss")
            buffer_duration_seconds: Duration of video buffer in seconds
        """
        self.compositor = compositor
        self.privacy_config = privacy_config
        self.backend = backend
        self.buffer_duration = buffer_duration_seconds
        
        # Initialize font at startup
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/OTF/SF-Pro-Rounded-Regular.otf", 128)
        except:
            self.font = ImageFont.load_default()
            
        # Video buffer setup
        self.frame_buffer = deque(maxlen=buffer_duration_seconds)
        self.recording = False
        self.recording_task = None

    async def start_recording(self):
        """Start the recording process."""
        if self.recording:
            return
            
        self.recording = True
        self.frame_buffer.clear()
        self.recording_task = asyncio.create_task(self._record_loop())

    async def stop_recording(self):
        """Stop the recording process."""
        if not self.recording:
            return
            
        self.recording = False
        if self.recording_task:
            await self.recording_task
            self.recording_task = None

    async def _record_loop(self):
        """Main recording loop capturing frames at 1fps."""
        while self.recording:
            try:
                frame = await self._capture_frame()
                if frame is not None:
                    self.frame_buffer.append(frame)
                await asyncio.sleep(1)  # 1fps interval
            except Exception as e:
                logger.error(f"Error in recording loop: {e}")
                await asyncio.sleep(1)  # Continue recording despite errors

    async def _capture_frame(self) -> Optional[Image.Image]:
        """Capture a single frame with privacy filtering."""
        try:
            # Run screenshot capture in a thread pool since it's CPU-bound
            screenshot = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pyscreenshot.grab(backend=self.backend)
            )
            
            # Convert to PIL Image for drawing
            img = screenshot if isinstance(screenshot, Image.Image) else Image.fromarray(screenshot)
            draw = ImageDraw.Draw(img)
            
            # Apply privacy filtering only for visible windows
            windows = await self.compositor.get_windows()
            for window in windows:
                if self.compositor.is_window_visible(window) and self.privacy_config.is_private(window):
                    # Draw black rectangle over private window
                    x, y = window['position']
                    width, height = window['size']
                    draw.rectangle([(x, y), (x + width, y + height)], fill='black')

                    # Add text
                    class_name = window.get('class', 'Unknown Window')
                    text = f"Window: {class_name}\nFiltered for privacy"
                    
                    # Center the text
                    bbox = draw.textbbox((0, 0), text, font=self.font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    text_y = y + (height - text_height) // 2
                    
                    draw.text((text_x, text_y), text, fill='white', font=self.font, align='center')

            return img
            
        except Exception as e:
            logger.error(f"Frame capture failed: {e}")
            return None

    async def get_video_buffer(self) -> Optional[bytes]:
        """Convert current frame buffer to MP4 video bytes."""
        if not self.frame_buffer:
            return None
            
        try:
            # Get frame dimensions from first frame
            first_frame = self.frame_buffer[0]
            height, width = first_frame.height, first_frame.width
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_buffer = BytesIO()
            out = cv2.VideoWriter('temp.mp4', fourcc, 1, (width, height))
            
            # Write frames
            for frame in self.frame_buffer:
                # Convert PIL to OpenCV format
                cv_frame = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
                out.write(cv_frame)
            
            out.release()
            
            # Read the temporary file and return bytes
            with open('temp.mp4', 'rb') as f:
                video_bytes = f.read()
                
            return video_bytes
            
        except Exception as e:
            logger.error(f"Failed to create video buffer: {e}")
            return None

    async def capture_and_encode(self) -> Optional[str]:
        """Capture single screenshot and encode to base64 (kept for compatibility)."""
        frame = await self._capture_frame()
        if frame is None:
            return None
            
        buffer = BytesIO()
        frame.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.stop_recording()