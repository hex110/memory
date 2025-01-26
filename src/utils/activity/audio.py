"""Audio recording utility."""

import asyncio
from io import BytesIO
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import aiofiles
from src.utils.logging import get_logger

logger = get_logger(__name__)

class AudioRecorder:
    """Handles audio recording functionality."""
    
    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        """Initialize audio recorder.
        
        Args:
            sample_rate: Recording sample rate (Hz)
            channels: Number of audio channels (1 for mono, 2 for stereo)
        """
        self.logger = get_logger(__name__)
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = None
        self.is_recording = False
        self.stream = None
        self._recorded_frames = []

    async def start_recording(self):
        """Start recording audio."""
        if self.is_recording:
            return

        try:
            self._recorded_frames = []
            self.is_recording = True

            # Create and start the stream
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback
            )
            self.stream.start()

        except Exception as e:
            self.is_recording = False
            raise RuntimeError(f"Failed to start recording: {str(e)}")

    async def stop_recording(self) -> Optional[Path]:
        """Stop recording and save audio file.
        
        Returns:
            Path to saved audio file or None if recording failed
        """
        if not self.is_recording:
            return None

        try:
            self.is_recording = False
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if not self._recorded_frames:
                return None

            # Convert recorded frames to numpy array
            recording = np.concatenate(self._recorded_frames, axis=0)
            
            # Create recordings directory if it doesn't exist
            recordings_dir = Path("recordings")
            recordings_dir.mkdir(exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = recordings_dir / f"recording_{timestamp}.wav"
            
            # Save recording
            sf.write(
                file=str(filepath),
                data=recording,
                samplerate=self.sample_rate
            )
            
            return filepath

        except Exception as e:
            raise RuntimeError(f"Failed to stop recording: {str(e)}")
        finally:
            self._recorded_frames = []

    def _audio_callback(self, indata, frames, time, status):
        """Callback function for audio stream."""
        if status:
            print(f'Audio callback status: {status}')
        if self.is_recording:
            self._recorded_frames.append(indata.copy())

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.is_recording:
                await self.stop_recording()
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
                
        except Exception as e:
            raise RuntimeError(f"Failed to cleanup audio recorder: {str(e)}")