"""Text-to-speech utilities using Google Cloud TTS."""

import logging
from typing import Optional, AsyncIterator
from pathlib import Path
import tempfile
import os
import itertools
import asyncio

from google.cloud import texttospeech
import grpc

class TTSEngine:
    """Wrapper for Google Cloud Text-to-Speech."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        try:
            self.client = texttospeech.TextToSpeechAsyncClient()
            # We are now using Standard-C for non-streaming, and Journey-D for streaming.
            self.standard_voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Standard-C",  # Standard voice
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            self.journey_voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Journey-D" # Journey voice for streaming
            )
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            self.logger.info("TTSEngine initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize TTSEngine", extra={"error": str(e)})
            raise

    async def cleanup(self):
        """Cleanup TTS engine resources."""
        try:
            # self.logger.debug(self.client)
            if hasattr(self, 'client'):
                pass
                # Close the gRPC channel
                # await asyncio.sleep(0.1) # Give other async tasks time to complete.
                
                # #Get the underlying transport
                # transport = self.client.transport

                # #Get the grpc channel
                # grpc_channel = transport._channel

                # # Use a blocking shutdown with a timeout
                # grpc_channel.close()
                
        except Exception as e:
            self.logger.error("Failed to cleanup TTSEngine", extra={"error": str(e)})

    async def synthesize_speech(self, text: str) -> Optional[Path]:
        """
        Synthesize speech from text and return path to audio file.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Path to the generated audio file or None if synthesis failed
        """
        try:
            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Generate speech
            response = await self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.standard_voice,
                audio_config=self.audio_config
            )

            # Create temporary file
            temp_dir = Path(tempfile.gettempdir())
            output_path = temp_dir / f"tts_output_{os.urandom(4).hex()}.mp3"

            # Write response to file
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
                
            self.logger.debug(f"Audio content written to {output_path}")
            return output_path

        except Exception as e:
            self.logger.error("Failed to synthesize speech", extra={"error": str(e)})
            return None
    
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesize speech using bidirectional streaming.

        Args:
            text: The text to synthesize
            
        Returns:
            Async iterator of audio bytes chunks.
        """
        try:
            streaming_config = texttospeech.StreamingSynthesizeConfig(voice=self.journey_voice, audio_config=self.audio_config)

            # Set the config for your stream. The first request must contain your config, and then each subsequent request must contain text.
            config_request = texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)

            def request_generator():
                # Split text into chunks (you can customize this)
                chunk_size = 100
                for i in range(0, len(text), chunk_size):
                    chunk = text[i:i+chunk_size]
                    yield texttospeech.StreamingSynthesizeRequest(input=texttospeech.StreamingSynthesisInput(text=chunk))

            #chain the config to the beginning of the request
            streaming_requests = itertools.chain([config_request], request_generator())
            streaming_responses = self.client.streaming_synthesize(streaming_requests)

            async for response in streaming_responses:
                yield response.audio_content

        except Exception as e:
            self.logger.error("Failed to stream speech", extra={"error": str(e)})
            # return None