"""Assistant agent implementation."""

import asyncio
from typing import Dict, Any, List
from datetime import datetime


from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
from src.utils.activity.audio import AudioRecorder
from src.utils.activity.inputs import InputTracker
from src.utils.activity.screencapture import ScreenCapture
from src.utils.tts import TTSEngine
from .base_agent import BaseAgent

class AssistantAgent(BaseAgent):
    """Agent for handling voice interactions and providing responses."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager,
        input_tracker: InputTracker,
        screen_capture: ScreenCapture,
        tts_engine: TTSEngine
    ):
        super().__init__(
            config=config,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            tts_engine=tts_engine
        )

        try:
            # Add references to trackers
            self.input_tracker = input_tracker
            self.screen_capture = screen_capture

            self.available_tools = [
                "spotify.spotify_control"
            ]

            self.event_system = EventSystem()
            
            self.is_running = False
            self.is_recording = False
            
            self.audio_recorder = AudioRecorder()
            self.current_recording_path = None
            
            # self.logger.info("AssistantAgent initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize AssistantAgent", extra={
                "error": str(e)
            })
            raise

    async def start(self):
        """Start the assistant agent."""
        try:
            if not self.is_running:
                # self.logger.debug("Starting AssistantAgent")
                self.is_running = True

                # Subscribe to hotkey events
                await self.event_system.broadcaster.subscribe_hotkey(
                    HotkeyEventType.SPEAK,
                    self._handle_hotkey
                )
                
                self.logger.info("AssistantAgent started successfully")
        except Exception as e:
            self.logger.error("Failed to start AssistantAgent", extra={
                "error": str(e)
            })
            raise

    async def stop(self):
        """Stop the assistant agent."""
        try:
            if self.is_running:
                # self.logger.debug("Stopping AssistantAgent")
                self.is_running = False
                
                # Stop recording if active
                if self.is_recording:
                    await self.tts_engine.audio_player.skip_current()
                
                # Cleanup audio recorder
                await self.audio_recorder.cleanup()
                
                # self.logger.info("AssistantAgent stopped successfully")
        except Exception as e:
            self.logger.error("Failed to stop AssistantAgent", extra={
                "error": str(e)
            })
            raise

    async def _handle_hotkey(self, event: HotkeyEvent):
        """Handle incoming hotkey events."""
        if not self.is_running:
            return

        try:
            if self.is_recording:
                # Stop recording and process
                await self._stop_recording()
                asyncio.create_task(self._process_request())
            else:
                # Start new recording
                await self._start_recording()
                
        except Exception as e:
            self.logger.error("Error handling hotkey event", extra={
                "error": str(e)
            }, exc_info=True)

    async def _start_recording(self):
        """Start audio recording."""
        try:
            self.is_recording = True
            await self.audio_recorder.start_recording()
            self.logger.debug("Recording started...")  # User feedback

            if self.tts_engine:
                await self.tts_engine.audio_player.skip_current()
            
        except Exception as e:
            self.logger.error("Failed to start recording", extra={
                "error": str(e)
            })
            self.is_recording = False
            raise

    async def _stop_recording(self):
        """Stop audio recording."""
        try:
            self.is_recording = False
            
            # Stop recording and get file path
            self.current_recording_path = await self.audio_recorder.stop_recording()
            self.logger.debug("Recording stopped...")  # User feedback
            
        except Exception as e:
            self.logger.error("Failed to stop recording", extra={
                "error": str(e)
            })
            raise

    async def _get_recent_context(self) -> str:
        """Get formatted string of recent activity context."""
        try:
            recent_sessions = await self.input_tracker.get_recent_sessions(seconds=30)
            
            context = "For context, here is what I was doing before calling for assistance:\n\n"
            
            for session in recent_sessions:
                context += f"Window: {session.window_info['class']} - {session.window_info['title']}\n"
                context += f"From {session.start_time.strftime('%H:%M:%S')} to {session.end_time.strftime('%H:%M:%S')}\n"
                context += f"Activity: {session.key_count} keys, {session.click_count} clicks, {session.scroll_count} scrolls\n\n"
            
            return context
            
        except Exception as e:
            self.logger.error("Failed to get recent context", extra={
                "error": str(e)
            })
            return "Could not retrieve recent activity context."

    async def _process_request(self):
        """Process voice input and generate response."""
        if not self.current_recording_path:
            self.logger.error("No recording available to process")
            return

        try:
            # Get audio data
            audios = []
            with open(self.current_recording_path, 'rb') as f:
                audio_bytes = f.read()
                audios.append((audio_bytes, 'audio/wav'))

            # Get system prompt
            system_prompt = self.load_prompt("assistant_system", context={})
            
            # Get recent context and video
            context = await self._get_recent_context()
            videos = []
            video_buffer = await self.screen_capture.get_video_buffer()
            if video_buffer:
                videos.append((video_buffer, 'video/mp4'))

            # Build user prompt with context
            user_prompt = f"{context}\n\nMy request is in the audio message."

            self.logger.debug(f"User prompt: {user_prompt}")

            # Get LLM response
            response_stream = await self.call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                audios=audios,
                videos=videos,
                # streaming=True,
                tts=True
            )

            # Clear current recording path
            self.current_recording_path = None
            
        except Exception as e:
            self.logger.error("Failed to process voice input", extra={
                "error": str(e)
            }, exc_info=True)
            raise

    async def _get_recent_responses(self, limit: int = 5) -> List[str]:
        """Get recent assistant responses from database."""
        try:
            # query = {
            #     "session_id": self.session_id
            # }
            
            responses = await self.db.query_entities(
                "activity_analysis",
                query={},
                sort_by="timestamp",
                sort_order="desc",
                limit=limit
            )
            
            return [r["llm_response"] for r in responses]
            
        except Exception as e:
            self.logger.error("Failed to get recent responses", extra={
                "error": str(e)
            })
            return []

    async def _store_response(self, response: str):
        """Store assistant response in database."""
        try:
            storage_data = {
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "response": response,
                "created_by": "agent"
            }
            
            await self.db.add_entity(
                "assistant_responses",
                storage_data
            )
            
        except Exception as e:
            self.logger.error("Failed to store response", extra={
                "error": str(e)
            })
            raise