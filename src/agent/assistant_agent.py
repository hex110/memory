"""Assistant agent implementation."""

import asyncio
from typing import Dict, Any, List
from datetime import datetime

from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.activity.activity_manager import ActivityManager
from src.utils.events import HotkeyEvent, HotkeyEventType, EventSystem
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
        tts_engine: TTSEngine,
        activity_manager: ActivityManager
    ):
        super().__init__(
            config=config,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            tts_engine=tts_engine
        )

        try:
            self.activity_manager = activity_manager
            self.available_tools = [
                # "spotify.spotify_control"
                "context.get_logs",
                "context.get_recent_video",
                "context.get_recent_inputs"
            ]

            self.event_system = EventSystem()
            
            self.is_running = False
            self.is_recording = False

            self.message_history = []  # Store conversation history
            self.last_interaction_time = None  # Track last interaction
            self.CONVERSATION_TIMEOUT = 30  # Seconds before conversation resets
            
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
                    HotkeyEventType.HOTKEY_SPEAK,
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
                    await self.activity_manager.stop_recording()
                
                # Unsubscribe from hotkey events (optional, for cleanup)
                # Note: You might need to modify your EventSystem to support unsubscription
                # await self.event_system.broadcaster.unsubscribe_hotkey(
                #     HotkeyEventType.SPEAK,
                #     self._handle_hotkey
                # )

                self.logger.info("AssistantAgent stopped successfully")
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
            await self.activity_manager.start_audio_recording()
            self.logger.debug("Recording started...")

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
            await self.activity_manager.stop_audio_recording()
            self.logger.debug("Recording stopped...")
            
        except Exception as e:
            self.logger.error("Failed to stop recording", extra={
                "error": str(e)
            })
            raise

    async def _get_recent_context(self) -> str:
        """Get formatted string of recent activity context."""
        try:
            recent_sessions = await self.activity_manager.get_recent_sessions(seconds=30)
            
            context = "For context, here is what I was doing before calling for assistance:\n\n"
            
            for session in recent_sessions:
                context += f"Window: {session['window_class']} - {session['window_title']}\n"
                context += f"From {session['start_time']} to {session['end_time']}\n"
                context += f"Activity: {session['key_count']} keys, {session['click_count']} clicks, {session['scroll_count']} scrolls\n\n"
            
            return context
            
        except Exception as e:
            self.logger.error("Failed to get recent context", extra={
                "error": str(e)
            })
            return "Could not retrieve recent activity context."

    def _should_continue_conversation(self) -> bool:
        """Check if we should continue existing conversation or start fresh."""
        if not self.last_interaction_time:
            return False
            
        elapsed = (datetime.now() - self.last_interaction_time).total_seconds()
        return elapsed <= self.CONVERSATION_TIMEOUT

    async def _process_request(self):
        """Process voice input and generate response."""
        
        # Retrieve audio from activity manager
        audio_filepath = self.activity_manager.get_audio_filepath()

        if not audio_filepath:
            self.logger.error("No recording available to process")
            return

        try:
            # Get audio data
            audios = []
            with open(audio_filepath, 'rb') as f:
                audio_bytes = f.read()
                audios.append((audio_bytes, 'audio/wav'))

            # Get system prompt
            system_prompt = self.load_prompt("assistant_system", context={})
            user_prompt = self.load_prompt("assistant", context={
                "previous_conversation": self.message_history
            })
            
            # Get recent context and video
            context = await self._get_recent_context()
            # videos = []
            # video_buffer = await self.activity_manager.get_video_buffer()
            # if video_buffer:
            #     videos.append((video_buffer, 'video/mp4'))
            
            # Check if we should continue conversation
            if not self._should_continue_conversation():
                self.message_history = []  # Reset history
                self.logger.debug("Starting new conversation")

            # Add context to user prompt
            user_prompt = f"{context}\n\n{user_prompt}"

            # Add user message to history
            self.message_history.append({
                "role": "user",
                "content": user_prompt
            })

            # self.logger.debug(f"User prompt: {user_prompt}")

            # Get LLM response
            response = await self.call_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                audios=audios,
                # videos=videos,
                message_history=self.message_history,
                tts=True
            )

            # Add assistant response to history
            self.message_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Update last interaction time
            self.last_interaction_time = datetime.now()

            self.logger.debug(f"LLM response: {response}")
            
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