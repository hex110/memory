"""Activity monitoring agent implementation."""

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
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str
    ):
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db_interface=db_interface,
            ontology_manager=ontology_manager
        )

        # Set available tools for this agent
        self.available_tools = [
            "database.add_entity",
            "database.update_entity"
        ]

        self.event_system = ActivityEventSystem()
        
        # Initialize core services
        self.window_manager = WindowManager()
        self.privacy_config = PrivacyConfig()
        
        # Initialize trackers with dependencies
        self.input_tracker = InputTracker(self.window_manager, self.privacy_config)
        self.screen_capture = ScreenCapture(self.window_manager, self.privacy_config)
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread = None
        self.collection_interval = self.config.get("activity_log_interval", 10)
        self.session_id = session_id
    
    def start_monitoring(self):
        """Start the activity monitoring process."""
        if not self.is_monitoring:
            self.input_tracker.start()
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            self.logger.info(f"Activity monitoring started with session ID: {self.session_id}")
    
    def stop_monitoring(self):
        """Stop the activity monitoring process."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
            self.monitor_thread = None
        
        # Cleanup trackers
        self.input_tracker.stop()
        self.screen_capture.cleanup()
        self.window_manager.cleanup()
        
        self.logger.info("Activity monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop that collects and stores data periodically."""
        time.sleep(self.collection_interval)
        
        while self.is_monitoring:
            try:
                # Get data from input tracker
                activity_data = self.input_tracker.get_events()

                # Capture screenshot
                screen_data = self.screen_capture.capture_and_encode()
                if screen_data:
                    activity_data["screenshot"] = screen_data
                
                # Store activity data using tool
                self._store_activity_data(activity_data)
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)
    
    def _store_activity_data(self, raw_activity_data: Dict[str, Any]):
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
                self.db_interface.add_entity(
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
                self.event_system.broadcaster.broadcast(event)

            except Exception as e:
                if "duplicate key" in str(e):
                    storage_data["updated_at"] = current_timestamp
                    storage_data["updated_by"] = "agent"

                    # Update entity using database interface
                    self.db_interface.update_entity(
                        "activity_raw",
                        current_timestamp,
                        storage_data
                    )
                else:
                    raise
                    
        except Exception as e:
            self.logger.error(f"Error storing activity data: {e}")

    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the monitoring agent.
        
        Args:
            data: Optional configuration data
            
        Returns:
            Status of the monitoring process
        """
        try:
            if data:
                # Update configuration if provided
                self.session_id = data.get("session_id", self.session_id)
                self.collection_interval = data.get("interval", self.collection_interval)
            
            self.start_monitoring()
            return {
                "status": "success",
                "message": f"Activity monitoring started with session ID: {self.session_id}"
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to start monitoring: {str(e)}"
            }