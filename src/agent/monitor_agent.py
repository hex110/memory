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
import json
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
from src.utils.activity.windows import HyprlandManager
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
        
        # Initialize window manager (can be swapped for other implementations)
        self.window_manager = HyprlandManager()
        
        # Initialize trackers
        self.keyboard_tracker = ActivityTracker(self.window_manager)
        self.screen_capture = ScreenCapture()
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread = None
        self.collection_interval = 10  # seconds
        self.session_id = None
        
    def _collect_activity_data(self) -> Dict[str, Any]:
        """Collect current activity data from all trackers.
        
        Returns:
            Dict containing the collected activity data
        """
        # Get data from each tracker
        activity_data = self.keyboard_tracker.get_events()
        screen_data = self.screen_capture.capture()
        
        # Add screenshot if captured
        if screen_data and screen_data.get("image"):
            try:
                buffer = BytesIO()
                screen_data["image"].save(buffer, format="PNG")
                activity_data["screenshot"] = base64.b64encode(buffer.getvalue()).decode('utf-8')
                self.logger.info("Successfully encoded screenshot")
            except Exception as e:
                self.logger.warning(f"Failed to encode screenshot: {e}")
        
        # Add session ID and timestamp
        activity_data["session_id"] = self.session_id
        activity_data["timestamp"] = datetime.now().isoformat()
        
        return activity_data
    
    def _format_window_summaries(self, window_sessions: List[Dict[str, Any]]) -> str:
        """Format window summaries for LLM analysis.

        Args:
            window_sessions: List of window sessions

        Returns:
            Formatted window summaries
        """
        summary_parts = ["The user"]
        merged_sessions = []
        last_session = None
        last_window = None

        for session in window_sessions:
            duration = session['duration']
            if duration < 1:
                continue
            if (
                last_session
                and session['window_class'] == last_session['window_class']
                and session['window_title'] == last_session['window_title']
                
            ):
                # Merge sessions
                merged_sessions[-1]['duration'] += duration
                merged_sessions[-1]['key_events'].extend(session.get('key_events',[]))
                merged_sessions[-1]['key_count'] += session.get('key_count',0)
                merged_sessions[-1]['click_count'] += session.get('click_count',0)
                merged_sessions[-1]['scroll_count'] += session.get('scroll_count',0)
                last_session = merged_sessions[-1]
            else:
                # Add new session
                merged_sessions.append(session)
                last_session = session

        for i, session in enumerate(merged_sessions):
            window_class = session['window_class']
            window_title = session['window_title']
            duration = session['duration']
            key_count = session['key_count']
            click_count = session['click_count']
            scroll_count = session['scroll_count']

            actions = []
            if key_count > 0:
                typed_chars = "".join(
                    [event['key'] for event in session['key_events'] if event['type'] == 'press']
                )
                actions.append(f"typed '{typed_chars}'")
            if click_count > 0:
                actions.append(f"clicked {click_count} time{'s' if click_count > 1 else ''}")
            if scroll_count > 0:
                actions.append(f"scrolled {scroll_count} time{'s' if scroll_count > 1 else ''}")

            action_string = ""
            if actions:
                if len(actions) == 1:
                    action_string = actions[0]
                elif len(actions) > 1:
                    action_string = ", and ".join([", ".join(actions[:-1]), actions[-1]])
            else:
                action_string = "did nothing"

            if i == 0:
                summary_parts.append(f" was on window class '{window_class}' with title '{window_title}' for {duration:.1f} seconds and {action_string}.")
            else:
                summary_parts.append(f" switched to window class '{window_class}' with title '{window_title}' for {duration:.1f} seconds and {action_string}.")
            

            if i < len(merged_sessions) - 1:
                next_session = merged_sessions[i+1]
                next_window_class = next_session['window_class']
                next_window_title = next_session['window_title']
                last_window = (window_class, window_title)

        return " ".join(summary_parts).replace("  "," ")
    
    def _get_llm_analysis(self, activity_data: Dict[str, Any]) -> str:
        """Get LLM analysis of the activity data.
        
        Args:
            activity_data: Activity data including screenshot and metrics
            
        Returns:
            LLM's analysis of the activity
        """
        try:
            print(f"Activity data without screenshot: {activity_data.get('window_sessions')}")

            # Prepare window activity summary
            window_summaries = self._format_window_summaries(activity_data.get("window_sessions", []))
            
            print(f"Window summaries: {window_summaries}")

            # Calculate time since last observation
            has_previous_logs = False
            previous_logs = []
            try:
                # Get up to 3 most recent logs from this session
                recent_logs = self.get_recent_logs(3)
                if recent_logs:
                    # Get the last log for duration calculation
                    last_log = recent_logs[0]
                    last_time = datetime.fromisoformat(last_log["timestamp"])
                    current_time = datetime.fromisoformat(activity_data["timestamp"])
                    duration = (current_time - last_time).total_seconds()
                    has_previous_logs = True
                    
                    # Extract LLM responses from recent logs
                    previous_logs = [log.get("llm_response", "") for log in recent_logs if log.get("llm_response")]
                else:
                    duration = self.collection_interval
            except Exception:
                duration = self.collection_interval

            # Prepare context for prompts
            context = {
                "timestamp": activity_data["timestamp"],
                "duration": f"{duration:.1f}",
                "window_summaries": "\n".join(window_summaries),
                "total_keys": activity_data["counts"]["total_keys_pressed"],
                "total_clicks": activity_data["counts"]["total_clicks"],
                "total_scrolls": activity_data["counts"]["total_scrolls"],
                "screenshot_available": "screenshot" in activity_data,
                "has_previous_logs": has_previous_logs,
                "previous_logs": previous_logs
            }
            
            # Load prompts
            system_prompt = self.load_prompt("monitor_system", context)
            analysis_prompt = self.load_prompt("monitor_analysis", context)
            
            # Create the content structure
            content = [
                {
                    "type": "text",
                    "text": analysis_prompt
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
            # response = self.call_llm(
            #     prompt=content,
            #     temperature=0.7,
            #     system_prompt=system_prompt
            # )
            return "Test"
            
            return response if response else "No analysis available"
            
        except Exception as e:
            self.logger.error(f"Error getting LLM analysis: {e}")
            return f"Analysis failed: {str(e)}"
    
    def _store_activity_data(self, data: Dict[str, Any]):
        """Store activity data in the database.
        
        Args:
            data: Activity data to store
        """
        try:
            # Ensure session_id is set
            if not self.session_id:
                self.session_id = str(uuid.uuid4())
                data["session_id"] = self.session_id
            
            # Use timestamp as the unique ID for this log
            timestamp = data["timestamp"]
            
            # Prepare and store the initial data immediately
            storage_data = self._prepare_data_for_storage(data)
            try:
                self.db_tools.add_entity("activity_log", timestamp, storage_data)
            except Exception as e:
                if "duplicate key" in str(e):
                    self.db_tools.update_entity("activity_log", timestamp, storage_data)
                else:
                    raise
            
            # Get LLM analysis asynchronously
            try:
                data_copy = data.copy()
                data_copy.pop("screenshot")
                print(f"data: {data_copy}")
                llm_response = self._get_llm_analysis(data_copy)
                # Update the stored data with LLM response
                self.db_tools.update_entity(
                    "activity_log",
                    timestamp,
                    {"llm_response": llm_response}
                )
            except Exception as e:
                self.logger.error(f"Error getting LLM analysis: {e}")
                # Update with error message
                self.db_tools.update_entity(
                    "activity_log",
                    timestamp,
                    {"llm_response": f"Analysis failed: {str(e)}"}
                )
            
        except Exception as e:
            self.logger.error(f"Error storing activity data: {e}")
    
    def _prepare_data_for_storage(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare activity data for database storage by serializing complex structures.
        
        Args:
            data: Raw activity data
            
        Returns:
            Dict with complex structures serialized for storage
        """
        try:
            storage_data = {
                # Basic fields
                "timestamp": data["timestamp"],  # Use as ID
                "session_id": data["session_id"],
                "screenshot": data.get("screenshot"),
                
                # Counts
                "total_keys_pressed": data["counts"]["total_keys_pressed"],
                "total_clicks": data["counts"]["total_clicks"],
                "total_scrolls": data["counts"]["total_scrolls"],
            }
            
            # Ensure window sessions are properly serialized
            if "window_sessions" in data:
                # Validate each session has required fields
                for session in data["window_sessions"]:
                    if not all(k in session for k in ["window_class", "window_title", "duration"]):
                        self.logger.warning(f"Skipping invalid window session: {session}")
                        continue
                
                # Convert to JSON string
                storage_data["window_sessions"] = json.dumps(data["window_sessions"])
            else:
                storage_data["window_sessions"] = "[]"  # Empty array as string
            
            return storage_data
            
        except Exception as e:
            self.logger.error(f"Error preparing data for storage: {e}")
            # Return minimal valid data
            return {
                "timestamp": data["timestamp"],
                "session_id": data["session_id"],
                "window_sessions": "[]",
                "total_keys_pressed": 0,
                "total_clicks": 0,
                "total_scrolls": 0
            }
    
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
                "session_id": self.session_id
            }
            logs = self.db_tools.query_entities(
                "activity_log",
                query,
                sort_by="timestamp",
                sort_order="desc",
                limit=count
            )
            
            # Parse stored JSON data back into Python objects
            for log in logs:
                if "window_sessions" in log:
                    try:
                        log["window_sessions"] = json.loads(log["window_sessions"])
                    except Exception as e:
                        self.logger.error(f"Failed to parse window sessions: {e}")
                        log["window_sessions"] = []
            
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

                print(f"Stored now. Collection interval: {self.collection_interval}")
                
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