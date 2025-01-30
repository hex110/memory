"""Activity monitoring agent implementation."""

import asyncio
import time
import threading
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.activity.activity_manager import ActivityManager
from .base_agent import BaseAgent
from src.utils.tts import TTSEngine
from src.utils.events import ActivityEvent, ActivityEventType, EventSystem

class MonitorAgent(BaseAgent):
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str,
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

        # self.logger.debug("Initializing MonitorAgent", extra={
        #     "session_id": session_id,
        #     "config": config
        # })

        # Set available tools for this agent
        self.available_tools = [
            "database.add_entity",
            "database.update_entity"
        ]

        self.event_system = EventSystem()
        
        try:
            
            # Monitoring state
            self.is_monitoring = False
            self.monitor_thread = None
            self.collection_interval = self.config["tracking"].get("activity_log_interval", 30)
            self.session_id = session_id
            self.activity_manager = activity_manager
            
            # self.logger.debug("MonitorAgent initialization complete", extra={
            #     "collection_interval": self.collection_interval,
            #     "session_id": self.session_id
            # })
            
        except Exception as e:
            self.logger.error("Failed to initialize MonitorAgent", extra={
                "error": str(e),
                "session_id": session_id
            })
            raise
    
    async def start_monitoring(self):
        """Start activity tracking."""
        try:
            if not self.is_monitoring:
                # Enable persistence in the input tracker
                await self.activity_manager.input_tracker.enable_persistence()
                activity_data = await self.activity_manager.input_tracker.get_events()
                
                self.is_monitoring = True
                self.monitor_task = asyncio.create_task(self._monitoring_loop())
                
                self.logger.info("Activity monitoring started")
        except Exception as e:
            self.logger.error("Failed to start monitoring")
            raise
    
    async def stop_monitoring(self):
        """Stop activity tracking."""
        try:
            if self.is_monitoring:
                self.is_monitoring = False
                
                # Cancel the monitoring task if it exists
                if self.monitor_task:
                    self.monitor_task.cancel()
                    try:
                        await self.monitor_task
                    except asyncio.CancelledError:
                        pass
                    self.monitor_task = None
                
                # Disable persistence in the input tracker
                await self.activity_manager.input_tracker.disable_persistence()
                
                self.logger.info("Activity monitoring stopped")
        except Exception as e:
            self.logger.error(f"Failed to stop monitoring: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Async monitoring loop that collects and stores data periodically."""
        # try:
        await asyncio.sleep(self.collection_interval)
        while self.is_monitoring:
            try:
                # Get data from activity manager
                activity_data = await self.activity_manager.input_tracker.get_events()

                # self.logger.debug(f"Activity data: {activity_data}")

                # Capture screenshot
                screen_data = await self.activity_manager.capture_screenshot()
                if screen_data:
                    activity_data["screenshot"] = screen_data
                
                # Store activity data
                await self._store_activity_data(activity_data)
                
                # Make this cancellable by checking for CancelledError
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(1)
        # finally:
            # self.logger.debug("Monitoring loop ended")
    
    async def _store_activity_data(self, raw_activity_data: Dict[str, Any]):
        """Store raw activity data in the database."""
        try:
            current_timestamp = datetime.now()
            entity_id = str(uuid.uuid4())
            
            storage_data = {
                "id": entity_id,
                "created_at": current_timestamp,
                "created_by": "agent",
                "session_id": self.session_id,
                "screenshot": raw_activity_data.get("screenshot"),
                "window_sessions": raw_activity_data.get("window_sessions", []),
                "total_keys_pressed": raw_activity_data["counts"]["total_keys_pressed"],
                "total_clicks": raw_activity_data["counts"]["total_clicks"],
                "total_scrolls": raw_activity_data["counts"]["total_scrolls"]
            }
            
            storage_data_copy = storage_data.copy()
            storage_data_copy["screenshot"] = "screenshot"
            # self.logger.debug(f"Storing activity data: {storage_data_copy}")
            
            try:
                # Directly add entity using database interface
                result = await self.db.add_entity(
                    "activity_raw", 
                    storage_data,
                )

                # Broadcast activity stored event
                event = ActivityEvent(
                    session_id=self.session_id,
                    timestamp=current_timestamp,
                    data=storage_data,
                    event_type=ActivityEventType.ACTIVITY_STORED
                )
                await self.event_system.broadcaster.broadcast_activity(event)

            except Exception as e:
                if "duplicate key" in str(e):
                    storage_data["updated_at"] = current_timestamp
                    storage_data["updated_by"] = "agent"

                    self.logger.debug("Calling update_entity...")
                    # Update entity using database interface
                    await self.db.update_entity(
                        "activity_raw",
                        entity_id,
                        storage_data
                    )
                else:
                    raise
                    
        except Exception as e:
            self.logger.error(f"Error storing activity data: {e}")