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
import os
import tempfile
import shutil
from src.utils.activity.compositor.base_compositor import BaseCompositor
from src.utils.activity.trackers.privacy import PrivacyConfig

logger = logging.getLogger(__name__)

class ScreenCapture:
    """Handles screen capture and privacy filtering with video buffer support, saving frames to disk."""

    def __init__(self, compositor: BaseCompositor, privacy_config: PrivacyConfig, backend: str = "grim", video_duration: int = 30):
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
        self.video_duration = video_duration

        # Initialize font at startup
        try:
            self.font = ImageFont.truetype(
                "/usr/share/fonts/OTF/SF-Pro-Rounded-Regular.otf", 128
            )
        except:
            self.font = ImageFont.load_default()

        # Temporary directory for frames
        self.temp_dir = tempfile.mkdtemp()
        self.frame_filenames = deque(maxlen=video_duration)  # Keep track of filenames

        self.recording = False
        self.recording_task = None

    async def start_recording(self):
        """Start the recording process."""
        if self.recording:
            return

        self.recording = True
        # Clear the temporary directory on start
        self._clear_temp_dir()
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
                await self._capture_and_save_frame()
                await asyncio.sleep(1)  # 1fps interval
            except Exception as e:
                logger.error(f"Error in recording loop: {e}")
                await asyncio.sleep(1)  # Continue recording despite errors

    async def _capture_and_save_frame(self) -> None:
        """Capture a single frame, apply privacy filtering, and save it to disk asynchronously."""
        try:
            loop = asyncio.get_event_loop()

            # Capture screenshot asynchronously
            screenshot = await loop.run_in_executor(None, lambda: pyscreenshot.grab(backend=self.backend))

            # Convert to PIL Image for drawing
            img = screenshot if isinstance(screenshot, Image.Image) else Image.fromarray(screenshot)
            draw = ImageDraw.Draw(img)

            # Apply privacy filtering
            windows = await self.compositor.get_windows()
            for window in windows:
                if self.compositor.is_window_visible(window) and self.privacy_config.is_private(window):
                    x, y = window['position']
                    width, height = window['size']
                    draw.rectangle([(x, y), (x + width, y + height)], fill='black')

                    class_name = window.get('class', 'Unknown Window')
                    text = f"Window: {class_name}\nFiltered for privacy"
                    bbox = draw.textbbox((0, 0), text, font=self.font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    text_y = y + (height - text_height) // 2
                    draw.text((text_x, text_y), text, fill='white', font=self.font, align='center')

            # Save the frame to disk asynchronously
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.temp_dir, f"frame_{timestamp}.png")

            # Use run_in_executor to make the blocking save operation asynchronous
            await loop.run_in_executor(None, img.save, filename, "PNG")

            # Manage frame filenames (delete oldest if necessary) - this part can remain synchronous
            if len(self.frame_filenames) == self.video_duration:
                oldest_filename = self.frame_filenames.popleft()
                try:
                    os.remove(oldest_filename)
                except Exception as e:
                    logger.error(f"Failed to delete old frame: {e}")
            self.frame_filenames.append(filename)

        except Exception as e:
            logger.error(f"Frame capture or saving failed: {e}")

    async def get_video_buffer(self) -> Optional[bytes]:
        """Create MP4 video from saved frames."""
        if not self.frame_filenames:
            return None

        try:
            # Get frame dimensions from first frame
            first_frame = Image.open(self.frame_filenames[0])
            width, height = first_frame.width, first_frame.height

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            temp_video_file = os.path.join(self.temp_dir, "temp_video.mp4")
            out = cv2.VideoWriter(temp_video_file, fourcc, 1, (width, height))

            # Write frames to video in order
            for filename in self.frame_filenames:
                try:
                    img = Image.open(filename)
                    cv_frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    out.write(cv_frame)
                except Exception as e:
                    logger.error(f"Failed to read or write frame {filename}: {e}")

            out.release()

            # Read video file and return bytes
            with open(temp_video_file, "rb") as f:
                video_bytes = f.read()
                
            # Remove the temporary video file
            os.remove(temp_video_file)

            return video_bytes

        except Exception as e:
            logger.error(f"Failed to create video buffer: {e}")
            return None

    async def capture_and_encode(self) -> Optional[str]:
        """Capture single screenshot, apply privacy filtering, save to disk, and encode to base64."""
        try:
            # Run screenshot capture in a thread pool since it's CPU-bound
            screenshot = await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyscreenshot.grab(backend=self.backend)
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

            # Encode the image to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return encoded_image

        except Exception as e:
            logger.error(f"Frame capture or saving failed: {e}")
            return None
    
    def _clear_temp_dir(self):
        """Clears all files in the temporary directory."""
        for filename in os.listdir(self.temp_dir):
            file_path = os.path.join(self.temp_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}. Reason: {e}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.stop_recording()
        shutil.rmtree(self.temp_dir)  # Remove the temporary directory