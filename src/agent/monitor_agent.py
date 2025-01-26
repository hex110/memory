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
from src.utils.activity.inputs import InputTracker
from src.utils.activity.screencapture import ScreenCapture
from src.utils.activity.windows import WindowManager
from src.utils.activity.privacy import PrivacyConfig
from .base_agent import BaseAgent
from src.utils.events import ActivityEventSystem, ActivityEvent, ActivityEventType

class MonitorAgent(BaseAgent):
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str
    ):
            
        super().__init__(
            config=config,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager
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

        self.event_system = ActivityEventSystem()
        
        try:
            # Initialize core services
            self.window_manager = WindowManager()
            
            self.privacy_config = PrivacyConfig()
            
            # Initialize trackers with dependencies
            self.input_tracker = InputTracker(self.window_manager, self.privacy_config)
            # Set up the interrupt callback
            self.input_tracker.set_interrupt_callback(lambda: asyncio.create_task(self.stop_monitoring()))
            
            self.screen_capture = ScreenCapture(self.window_manager, self.privacy_config)
            
            # Monitoring state
            self.is_monitoring = False
            self.monitor_thread = None
            self.collection_interval = self.config["tracking"].get("activity_log_interval", 10)
            self.session_id = session_id
            
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
        """Start the activity monitoring process."""
        try:
            # self.logger.debug("Starting activity monitoring")
            
            if not self.is_monitoring:
                # self.logger.debug("Starting input tracker")
                await self.input_tracker.start()
                
                self.is_monitoring = True
                # Store the task reference
                self.monitor_task = asyncio.create_task(self._monitoring_loop())
                
                self.logger.info("Activity monitoring started")
        except Exception as e:
            self.logger.error("Failed to start monitoring")
            raise
    
    async def stop_monitoring(self):
        """Stop the activity monitoring process."""
        try:
            # self.logger.debug("Stopping activity monitoring")
            
            self.is_monitoring = False
            
            # Cancel the monitoring task if it exists
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
                self.monitor_task = None
            
            # Cleanup trackers
            # self.logger.debug("Cleaning up trackers")
            await self.input_tracker.stop()
            await self.screen_capture.cleanup()
            await self.window_manager.cleanup()
            
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
                # Get data from input tracker
                activity_data = await self.input_tracker.get_events()

                # Capture screenshot
                screen_data = await self.screen_capture.capture_and_encode()
                if screen_data:
                    activity_data["screenshot"] = screen_data
                
                # Store activity data
                await self._store_activity_data(activity_data)
                
                # Make this cancellable by checking for CancelledError
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
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
                await self.event_system.broadcaster.broadcast(event)

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