"""Activity monitoring agent implementation."""

import time
import threading
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.activity.keys import ActivityTracker
from src.utils.activity.screen import ScreenCapture
from src.utils.activity.windows import HyprlandManager
from .base_agent import BaseAgent
from src.utils.events import ActivityEventSystem, ActivityEvent, ActivityEventType

class MonitorAgent(BaseAgent):
    """Agent for monitoring and recording user activity."""
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str
    ):
        """Initialize the monitoring agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            session_id: Session ID for the agent
        """
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db_interface=db_interface,
            ontology_manager=ontology_manager,
            role="monitor"
        )

        self.event_system = ActivityEventSystem()
        
        # Initialize window manager
        self.window_manager = HyprlandManager()
        
        # Initialize trackers
        self.keyboard_tracker = ActivityTracker(self.window_manager)
        self.screen_capture = ScreenCapture()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread = None
        self.collection_interval = self.config.get("activity_log_interval", 10)  # seconds
        self.session_id = session_id
    
    def start_monitoring(self):
        """Start the activity monitoring process."""
        if not self.is_monitoring:
            # Generate session ID only when starting monitoring
            if not self.session_id:
                self.session_id = str(uuid.uuid4())
            
            self.keyboard_tracker.start()
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
        self.keyboard_tracker.stop()
        self.screen_capture.cleanup()
        self.window_manager.cleanup()
        
        self.logger.info("Activity monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop that collects and stores data periodically."""
        # Wait for first interval before collecting data
        time.sleep(self.collection_interval)
        
        while self.is_monitoring:
            try:
                # Get data from keyboard and windows tracker
                activity_data = self.keyboard_tracker.get_events()

                # Capture screenshot
                screen_data = self.screen_capture.capture_and_encode()

                if screen_data:
                    activity_data["screenshot"] = screen_data
                
                # Store activity data
                self._store_activity_data(activity_data)
                
                # Wait for next collection interval
                time.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                # Don't break the loop on error, just continue
                time.sleep(1)
    
    def _store_activity_data(self, raw_activity_data: Dict[str, Any]):
        """Store raw activity data in the database.
        
        Args:
            raw_activity_data: Activity data to store
        """
        try:
            # Use timestamp as the unique ID for this log
            current_timestamp = datetime.now().isoformat()
            
            # Prepare data for storage
            storage_data = {
                # Basic fields
                "timestamp": current_timestamp,
                "session_id": self.session_id,
                "screenshot": raw_activity_data.get("screenshot"),
                "window_sessions": json.dumps(raw_activity_data.get("window_sessions", [])),
                
                # Counts
                "total_keys_pressed": raw_activity_data["counts"]["total_keys_pressed"],
                "total_clicks": raw_activity_data["counts"]["total_clicks"],
                "total_scrolls": raw_activity_data["counts"]["total_scrolls"]
            }
            
            # Store in activity_raw table
            try:
                self.db_tools.add_entity("activity_raw", current_timestamp, storage_data)

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
                    self.db_tools.update_entity("activity_raw", current_timestamp, storage_data)
                else:
                    raise
                    
        except Exception as e:
            self.logger.error(f"Error storing activity data: {e}")
    
    def execute(self) -> Dict[str, Any]:
        """Execute the monitoring agent.
        
        Returns:
            Status of the monitoring process
        """
        try:
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