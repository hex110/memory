"""Text-to-speech utilities using Google Cloud TTS."""
import subprocess
from typing import Optional, AsyncIterator, Tuple
from pathlib import Path
import itertools
import asyncio
from collections.abc import AsyncIterable

from google.cloud import texttospeech

from src.utils.logging import get_logger

logger = get_logger(__name__)

class TTSEngine:
    """Wrapper for Google Cloud Text-to-Speech."""
    
    def __init__(self, tts_enabled: bool):
        """Initialize basic attributes synchronously."""
        self.client : texttospeech.TextToSpeechAsyncClient = None
        self.standard_voice = None
        self.journey_voice = None
        self.audio_config = None
        self.audio_player : AudioPlayer = None
        self.tts_enabled = tts_enabled

        # if self.tts_enabled:
        #     logger.info("TTS is enabled. Initializing TTSEngine...")
        # else:
        #     logger.info("TTS is disabled. TTSEngine will be a no-op.")

    @classmethod
    async def create(cls, tts_enabled: bool):
        """Async factory method to properly initialize the TTSEngine."""
        instance = cls(tts_enabled)
        if tts_enabled:
            try:
                # instance.client = texttospeech.TextToSpeechAsyncClient() # gives error
                # instance.client = texttospeech.TextToSpeechAsyncClient(transport="rest") # doesn't work
                instance.client = texttospeech.TextToSpeechClient(transport="rest") # somehow works? we have to use sync client instead of async, and while we're waiting for the response, the cli is blocked, but it works, and it can be fixed probably
                instance.standard_voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    name="en-US-Standard-H",  # Standard voice
                    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
                )
                instance.journey_voice = texttospeech.VoiceSelectionParams(
                    language_code="en-US",
                    name="en-US-Journey-F", # Journey voice for streaming
                    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
                )
                instance.audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                # Add AudioPlayer instance
                instance.audio_player = AudioPlayer()
                await instance.audio_player.start()

                # logger.info("TTSEngine initialized successfully")
                
            except Exception as e:
                logger.error("Failed to initialize TTSEngine", extra={"error": str(e)})
                raise
        
        return instance

    async def cleanup(self):
        """Cleanup TTS engine resources."""
        try:
            if self.tts_enabled:
                # Stop the audio player
                await self.audio_player.stop()
                
        except Exception as e:
            logger.error("Failed to cleanup TTSEngine", extra={"error": str(e)}, exc_info=True)

    async def play_text(self, text: str):
        """Play complete text through TTS."""
        if not self.tts_enabled:
            logger.info("TTS is disabled. Skipping playback.")
            return
            
        try:
            audio_data = await self._synthesize_speech(text)
            if audio_data:
                async with self.audio_semaphore:
                    await self.audio_player.play_audio(audio_data)
        except Exception as e:
            logger.error("Failed to play text", extra={"error": str(e)})

    async def play_stream(self, text_stream: AsyncIterable[str]):
        """Play streaming text through TTS.
        
        Handles receiving text chunks, forming complete sentences,
        and playing them as they become available.
        """
        if not self.tts_enabled:
            logger.info("TTS is disabled. Skipping playback.")
            return
            
        try:
            buffer = TextBuffer()
            
            async for chunk in text_stream:
                sentences = buffer.add_chunk(chunk)

                # Process each sentence sequentially
                for sentence in sentences:
                    audio_data = await self._synthesize_speech(sentence)
                    if audio_data:
                        # Queue the audio and wait for it to finish playing
                        await self.audio_player.queue_audio(audio_data)
                        await self.audio_player.playback_queue.join()  # Wait for this audio to finish
            
            # Handle remaining text
            final_text = buffer.get_remaining()
            if final_text:
                audio_data = await self._synthesize_speech(final_text)
                if audio_data:
                    await self.audio_player.queue_audio(audio_data)
                    await self.audio_player.playback_queue.join()
                
        except Exception as e:
            logger.error("Failed to play stream", extra={"error": str(e)}, exc_info=True)

    async def _synthesize_speech(self, text: str) -> Optional[Path]:
        """
        Synthesize speech from text and return path to audio file.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Path to the generated audio file or None if synthesis failed
        """
        if not self.tts_enabled:
            logger.info("TTS is disabled. Skipping synthesis.")
            return None
            
        try:
            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Generate speech
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.standard_voice,
                audio_config=self.audio_config
            )
            # logger.debug(f"Synthesis response received: {response}")
            # logger.debug(f"Audio content generated for text: {text[:50]}...")
            return response.audio_content

        except Exception as e:
            logger.error("Failed to synthesize speech", extra={"error": str(e)}, exc_info=True)
            return None
    
    async def _streaming_synthesize_speech(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesize speech using bidirectional streaming.

        Args:
            text: The text to synthesize
            
        Returns:
            Async iterator of audio bytes chunks.
        """
        if not self.tts_enabled:
            logger.info("TTS is disabled. Skipping synthesis.")
            return
            
        try:
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=self.journey_voice,
                streaming_audio_config=texttospeech.StreamingAudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.PCM,
                    sample_rate_hertz=44100
                )
            )

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
            streaming_responses = await self.client.streaming_synthesize(streaming_requests)

            async for response in streaming_responses:
                yield response.audio_content

        except Exception as e:
            logger.error("Failed to stream speech", extra={"error": str(e)}, exc_info=True)
            # return None



class TextBuffer:
    """Manages text accumulation and sentence detection."""
    
    def __init__(self):
        self.buffer = ""
        self.sentence_endings = {'.', '!', '?'}
        self.quote_chars = {'"', "'"}
        self.ellipsis = "..."
    
    def add_chunk(self, chunk: str) -> list[str]:
        """Add a new chunk of text and return any complete sentences."""
        self.buffer += chunk
        return self._extract_sentences()
    
    def get_remaining(self) -> str:
        """Get any remaining text in the buffer."""
        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining
    
    def _extract_sentences(self) -> list[str]:
        """Extract complete sentences from the buffer, respecting quotes and ellipsis."""
        sentences = []
        in_quote = None  # Tracks which quote character we're inside, if any
        
        while True:
            if not self.buffer.strip():
                break
                
            # Find all possible sentence endings
            end_positions = []
            i = 0
            while i < len(self.buffer):
                if not in_quote:
                    # Check for quotes starting
                    for quote in self.quote_chars:
                        if self.buffer[i:].startswith(quote):
                            in_quote = quote
                            break
                            
                    # Check for sentence endings
                    for ending in self.sentence_endings:
                        if self.buffer[i:].startswith(ending):
                            # Check if it's part of an ellipsis
                            if ending == '.' and i + 3 <= len(self.buffer):
                                if self.buffer[i:i+3] == self.ellipsis:
                                    i += 2  # Skip the rest of ellipsis
                                    continue
                            end_positions.append(i)
                            
                else:  # We're in a quote
                    if self.buffer[i:].startswith(in_quote):
                        in_quote = None  # End quote
                        
                i += 1
            
            if not end_positions:
                break
                
            # Process all sentence endings found
            last_pos = 0
            for pos in end_positions:
                sentence = self.buffer[last_pos:pos + 1].strip()
                if sentence:
                    sentences.append(sentence)
                last_pos = pos + 1
                
            # Update buffer to remove processed sentences
            self.buffer = self.buffer[last_pos:].strip()
        
        return sentences



class AudioPlayer:
    def __init__(self):
        self.device = 'pipewire'
        self.current_process = None
        self._stop_requested = False
        self.playback_queue = asyncio.Queue()
        self.playback_task = None
        self._skip_current = False
        
    async def start(self):
        """Start a single long-running ffplay process and the background playback task."""
        if not self.playback_task or self.playback_task.done():
            self._stop_requested = False
            
            # Start a single long-running ffplay process
            self.current_process = subprocess.Popen(
                ['ffplay',
                 '-f', 'mp3',     # Using MP3 encoding
                 '-nodisp',       # No video display
                 '-i', 'pipe:0',  # Read from stdin
                 '-loglevel', 'error'  # Only show errors
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0  # Disable buffering
            )
            
            # Give process time to initialize
            await asyncio.sleep(0.1)
            
            # Start the playback worker
            self.playback_task = asyncio.create_task(self._playback_worker())

    async def stop(self):
        """Stop the playback task and cleanup."""
        self._stop_requested = True
        if self.current_process:
            if self.current_process.stdin:
                self.current_process.stdin.close()
            self.current_process.terminate()
            self.current_process = None
        if self.playback_task:
            await self.skip_current()

    async def skip_current(self):
        """Skip current audio."""
        self._skip_current = True
        # Clear the queue
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
                self.playback_queue.task_done()
            except asyncio.QueueEmpty:
                self._skip_current = False
                break
        self._skip_current = False

    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        await self.playback_queue.put(audio_data)

    async def _playback_worker(self):
        """Background task that handles audio playback."""
        while not self._stop_requested:
            try:
                # Get the next audio segment
                audio_data = await self.playback_queue.get()

                try:
                    # Write to the process if it exists and skip not requested
                    if self.current_process and not self._skip_current:
                        self.current_process.stdin.write(audio_data)
                        self.current_process.stdin.flush()
                except BrokenPipeError:
                    logger.debug("Broken pipe error occurred, restarting ffplay process")
                    # Attempt to restart the process
                    if self.current_process:
                        self.current_process.terminate()
                    self.current_process = subprocess.Popen(
                        ['ffplay',
                         '-f', 'mp3',
                         '-nodisp',
                         '-i', 'pipe:0',
                         '-loglevel', 'error'
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        bufsize=0
                    )
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.debug(f"Error in playback worker: {e}")
                finally:
                    self._skip_current = False
                    self.playback_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Unexpected error in playback worker: {e}")

    async def play_stream(self, audio_iterator: AsyncIterable[bytes]):
        """Play streaming PCM audio chunks as they arrive."""
        try:
            # For streaming PCM audio, we need different ffplay parameters
            streaming_process = subprocess.Popen(
                ['ffplay',
                 '-f', 's16le',        # 16-bit little-endian PCM format
                 '-ar', '44100',       # sample rate
                 '-nodisp',            # no video display
                 '-i', 'pipe:0',       # read from stdin
                 '-loglevel', 'error'  # only show errors
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            await asyncio.sleep(0.1)  # Give process time to initialize
            
            async for chunk in audio_iterator:
                if streaming_process and not self._stop_requested:
                    try:
                        streaming_process.stdin.write(chunk)
                        streaming_process.stdin.flush()
                    except BrokenPipeError:
                        logger.debug("Broken pipe error occurred in stream playback")
                        break
                        
            if streaming_process and streaming_process.stdin:
                streaming_process.stdin.close()
                streaming_process.terminate()

        except Exception as e:
            logger.debug(f"Error in play_stream: {e}")

async def tee_stream(stream: AsyncIterable[str]) -> tuple[AsyncIterable[str], AsyncIterable[str]]:
    """Split an async stream into two independent streams that process data as it arrives."""
    queue1, queue2 = asyncio.Queue(maxsize=1), asyncio.Queue(maxsize=1)
    
    async def create_generator(queue: asyncio.Queue):
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def fill_queues():
        try:
            async for item in stream:
                # Use wait() to ensure both queues get the item before continuing
                await asyncio.gather(
                    queue1.put(item),
                    queue2.put(item)
                )
            # Signal end of stream
            await asyncio.gather(
                queue1.put(None),
                queue2.put(None)
            )
        except Exception as e:
            await asyncio.gather(
                queue1.put(e),
                queue2.put(e)
            )

    # Start the fill_queues task but don't immediately return
    fill_task = asyncio.create_task(fill_queues())
    
    # Create the generators
    gen1 = create_generator(queue1)
    gen2 = create_generator(queue2)
    
    # Return both generators and the fill task
    return gen1, gen2, fill_task