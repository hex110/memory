"""Activity monitoring agent implementation.

This agent is responsible for:
1. Initializing activity trackers (keyboard, mouse, window)
2. Periodically collecting activity data
3. Storing activity data in the database

The agent runs in the background and collects data every 30 seconds.
Data is organized by sessions, with each session having a unique ID.
"""

import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import base64
from pathlib import Path
from io import BytesIO

from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.activity.keys import ActivityTracker
from src.utils.activity.screen import ScreenCapture
from src.utils.activity.windows import WindowTracker
from .base_agent import BaseAgent

class MonitorAgent(BaseAgent):
    """Agent for monitoring and recording user activity."""
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        """Initialize the monitoring agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
        """
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db_interface=db_interface,
            ontology_manager=ontology_manager,
            role="monitor"  # Role for database access
        )
        
        # Initialize trackers
        self.keyboard_tracker = ActivityTracker()
        self.screen_capture = ScreenCapture()
        self.window_tracker = WindowTracker()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread = None
        self.collection_interval = 10  # seconds
        self.session_id = None
        
    def _init_trackers(self):
        """Initialize activity trackers."""
        try:
            # Set up window-based filtering for keyboard events
            def should_track_keys() -> bool:
                active_window = self.window_tracker.get_active_window()
                if not active_window:
                    return True
                # Don't track keys in messaging apps (example)
                ignored_apps = ["Signal", "Telegram", "Discord"]
                return active_window.get("class") not in ignored_apps
            
            # Start keyboard/mouse tracking with filter
            self.keyboard_tracker.set_tracking_filter(should_track_keys)
            self.keyboard_tracker.start()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trackers: {e}")
            raise
    
    def _collect_activity_data(self) -> Dict[str, Any]:
        """Collect current activity data from all trackers.
        
        Returns:
            Dict containing the collected activity data
        """
        # Get data from each tracker
        key_data = self.keyboard_tracker.get_events()
        window_data = self.window_tracker.get_window_state()
        screen_data = self.screen_capture.capture()
        
        # Build activity record
        activity_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),  # Local time
            "screenshot": None,  # Will be populated if capture succeeds
            "key_clicks": [event["key"] for event in key_data.get("keyboard_events", []) if event["type"] == "press"],
            "open_windows": [
                f"{window.get('class', 'Unknown')}: {window.get('title', 'No Title')}"
                for window in (window_data.get("windows", []) if window_data else [])
            ],
            "keys_pressed_count": key_data["counts"]["keys_pressed"] if key_data else 0,
            "clicks_count": key_data["counts"]["clicks"] if key_data else 0,
            "scrolls_count": key_data["counts"]["scrolls"] if key_data else 0
        }
        
        # Convert screenshot to base64 if captured successfully
        if screen_data and screen_data.get("image"):
            try:
                # Convert PIL image to base64
                buffer = BytesIO()
                screen_data["image"].save(buffer, format="PNG")
                activity_data["screenshot"] = base64.b64encode(buffer.getvalue()).decode('utf-8')
                self.logger.info("Successfully encoded screenshot")
            except Exception as e:
                self.logger.warning(f"Failed to encode screenshot: {e}")
        
        return activity_data
    
    def _get_llm_analysis(self, activity_data: Dict[str, Any]) -> str:
        """Get LLM analysis of the activity data.
        
        Args:
            activity_data: Activity data including screenshot and metrics
            
        Returns:
            LLM's analysis of the activity
        """
        try:
            # Prepare the prompt with activity context
            prompt_text = f"""Analyze this activity snapshot and describe what the user is doing.
            
            Activity Context:
            - Open Windows: {', '.join(activity_data['open_windows'])}
            - Keys Pressed: {activity_data['keys_pressed_count']}
            - Mouse Clicks: {activity_data['clicks_count']}
            - Scroll Events: {activity_data['scrolls_count']}
            - Recent Keys: {', '.join(activity_data['key_clicks'][-10:]) if activity_data['key_clicks'] else 'None'}
            
            The screenshot is attached. Please describe the user's activity as specifically as possible.
            """
            
            # Create the content structure
            content = [
                {
                    "type": "text",
                    "text": prompt_text
                }
            ]
            
            # Add screenshot if present
            if activity_data.get("screenshot"):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{activity_data['screenshot']}"
                    }
                })
            
            # Call LLM with the content structure as the prompt
            response = self.call_llm(
                prompt=content,
                temperature=0.7
            )
            
            return response if response else "No analysis available"
            
        except Exception as e:
            self.logger.error(f"Error getting LLM analysis: {e}")
            return "No analysis available"
    
    def _store_activity_data(self, data: Dict[str, Any]):
        """Store activity data in the database.
        
        Args:
            data: Activity data to store
        """
        try:
            # Ensure session_id is set
            if not self.session_id:
                self.session_id = str(uuid.uuid4())
            
            # Use timestamp as the unique ID for this log
            timestamp = datetime.now().isoformat()
            
            # Create a copy of data for storage to avoid modifying the original
            storage_data = data.copy()
            storage_data["session_id"] = self.session_id
            
            # Get LLM analysis first
            try:
                llm_response = self._get_llm_analysis(data)
                storage_data["llm_response"] = llm_response
            except Exception as e:
                self.logger.error(f"Error getting LLM analysis: {e}")
                storage_data["llm_response"] = f"Analysis failed: {str(e)}"
            
            # Store the complete activity log
            try:
                self.db_tools.add_entity("activity_log", timestamp, storage_data)
            except Exception as e:
                if "duplicate key" in str(e):
                    # If the entry already exists, update it
                    self.db_tools.update_entity("activity_log", timestamp, storage_data)
                else:
                    raise
            
        except Exception as e:
            self.logger.error(f"Error storing activity data: {e}")
    
    def get_recent_logs(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent activity logs from the current session.
        
        Args:
            count: Number of recent logs to retrieve (default: 5)
            
        Returns:
            List of recent activity logs, ordered by timestamp (newest first)
        """
        try:
            if not self.session_id:
                return []
                
            # Query logs from current session, ordered by timestamp
            query = {
                "id": self.session_id
            }
            logs = self.db_tools.query_entities(
                "activity_log",
                query,
                sort_by="timestamp",
                sort_order="desc",
                limit=count
            )
            return logs if logs else []
        except Exception as e:
            self.logger.error(f"Error retrieving recent logs: {e}")
            return []
    
    def _monitoring_loop(self):
        """Main monitoring loop that collects and stores data periodically."""
        # Wait for first interval before collecting data
        time.sleep(self.collection_interval)
        
        while self.is_monitoring:
            try:
                # Collect and store activity data
                activity_data = self._collect_activity_data()
                self._store_activity_data(activity_data)
                
                # Wait for next collection interval
                time.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                # Don't break the loop on error, just continue
                time.sleep(1)
    
    def start_monitoring(self):
        """Start the activity monitoring process."""
        if not self.is_monitoring:
            # Generate session ID only when starting monitoring
            if not self.session_id:
                self.session_id = str(uuid.uuid4())
            
            self._init_trackers()
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop)
            self.monitor_thread.daemon = True  # Allow the thread to be killed when main exits
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
        self.window_tracker.cleanup()
        
        # Don't clear session_id so we can still query logs after stopping
        self.logger.info("Activity monitoring stopped")
    
    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the monitoring agent.
        
        This implementation starts the monitoring process and returns status.
        
        Args:
            data: Optional configuration data
            
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