import time
import threading
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.events import ActivityEventType, ActivityEvent, ActivityEventSystem
from .base_agent import BaseAgent

class AnalysisAgent(BaseAgent):
    """Agent for analyzing user activity data at different time scales."""
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str
    ):
        """Initialize the analysis agent.
        
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
            role="analysis",
        )

        self.session_id = session_id
        self.event_system = ActivityEventSystem()
        self.is_running = False
        self.completed_analyses = 0

        self.collection_interval = self.config.get("activity_log_interval", 30)  # seconds
        self.repeat_interval = 10
        
    def start_analysis_cycles(self):
        """Start both analysis cycles."""
        if not self.is_running:
            self.is_running = True
            self._subscribe_to_events()

            self.logger.info("Analysis started")
    
    def stop_analysis_cycles(self):
        """Stop all analysis cycles and perform final session analysis."""
        if self.is_running:
            self.is_running = False
            self.logger.info("Analysis stopped")
            
            # Perform final session analysis
            final_analysis = self.analyze_session(self.session_id)
            if final_analysis:
                self._store_analysis(final_analysis, "final")
    
    def _subscribe_to_events(self):
        """Subscribe to activity events."""
        self.event_system.broadcaster.subscribe(
            ActivityEventType.ACTIVITY_STORED,
            self._handle_activity_stored
        )
        self.event_system.broadcaster.subscribe(
            ActivityEventType.ANALYSIS_STORED,
            self._handle_analysis_interval
        )
    
    def _handle_activity_stored(self, event: ActivityEvent):
        """Handle incoming activity stored events."""
        if not self.is_running or event.session_id != self.session_id:
            return

        try:
            # Always do regular analysis
            end_time = datetime.now()
            start_time = end_time - timedelta(seconds=self.collection_interval)
            raw_data = self._get_recent_raw_data(start_time, end_time)
            if raw_data:
                analysis = self._analyze_short_term(raw_data)
                self._store_analysis(analysis, "regular")

                # Broadcast analysis stored event
                event = ActivityEvent(
                    session_id=self.session_id,
                    timestamp=analysis["start_time"],
                    data=analysis,
                    event_type=ActivityEventType.ANALYSIS_STORED
                )
                self.event_system.broadcaster.broadcast(event)

        except Exception as e:
            self.logger.error(f"Error handling activity stored event: {e}")

    def _handle_analysis_interval(self, event: ActivityEvent):
        if not self.is_running or event.session_id != self.session_id:
            return

        self.completed_analyses += 1

        try:
            if self.completed_analyses >= self.repeat_interval:
                end_time = datetime.now()
                start_time = end_time - timedelta(seconds=(self.collection_interval * self.repeat_interval))
                raw_data = self._get_recent_raw_data(start_time, end_time)
                
                if raw_data:
                    analysis = self._analyze_medium_term(raw_data)
                    self._store_analysis(analysis, "special")
                
                self.completed_analyses = 0

        except Exception as e:
            self.logger.error(f"Error handling analysis interval event: {e}")

    def _get_recent_raw_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get raw activity data for a time period.
        
        Args:
            start_time: Start of the time period
            end_time: End of the time period
            
        Returns:
            List of raw activity data records
        """
        query = {
            "timestamp": {
                ">=": start_time.isoformat(),
                "<=": end_time.isoformat()
            }
        }
        
        raw_data = self.db_tools.query_entities(
            "activity_raw",
            query,
            sort_by="timestamp",
            sort_order="asc"
        )
        
        # Parse JSON strings in window_sessions
        for record in raw_data:
            if "window_sessions" in record:
                try:
                    if isinstance(record["window_sessions"], str):
                        record["window_sessions"] = json.loads(record["window_sessions"])
                    elif not isinstance(record["window_sessions"], list):
                        record["window_sessions"] = []
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse window sessions for record {record['id']}")
                    record["window_sessions"] = []
        return raw_data

    def _get_recent_analyses(
        self, 
        end_time: datetime, 
        start_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent analyses for a time period.
        
        Args:
            end_time: End of the time period
            start_time: Start of the time period (optional)
            limit: Maximum number of records to return (optional)
            analysis_type: Type of analysis to filter by (optional)
                
        Returns:
            List of analysis records
        """
        query = {
            "start_timestamp": {
                "<=": end_time.isoformat()
            }
        }
        
        if start_time:
            query["start_timestamp"][">="] = start_time.isoformat()
        
        if analysis_type:
            query["analysis_type"] = analysis_type
        
        return self.db_tools.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="desc",
            limit=limit
        )

    def _format_window_summaries(self, window_sessions: List[Dict[str, Any]]) -> str:
        """Format window summaries for analysis.

        Args:
            window_sessions: List of window sessions

        Returns:
            Formatted window summaries
        """
        summary_parts = []
        merged_sessions = []
        last_session = None

        for session in window_sessions:
            duration = session.get('duration', 0)
            if duration < 0.5:  # Skip very short sessions
                continue
            if (
                last_session
                and session.get('window_class') == last_session.get('window_class')
                and session.get('window_title') == last_session.get('window_title')
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
            window_class = session.get('window_class', 'Unknown')
            window_title = session.get('window_title', 'Unknown')
            duration = session.get('duration', 0)
            key_count = session.get('key_count', 0)
            click_count = session.get('click_count', 0)
            scroll_count = session.get('scroll_count', 0)

            actions = []
            if key_count > 0:
                typed_chars = "".join(
                    [event['key'] for event in session.get('key_events', []) if event['type'] == 'press']
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
                summary_parts.append(f"The user was on window class '{window_class}' with title '{window_title}' for {duration:.1f} seconds and {action_string}.")
            else:
                summary_parts.append(f"The user switched to window class '{window_class}' with title '{window_title}' for {duration:.1f} seconds and {action_string}.")

        return " ".join(summary_parts).replace("  "," ")

    def _analyze_short_term(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze 30 seconds of activity data.
        
        Args:
            raw_data: List of raw activity records
            
        Returns:
            Analysis results
        """
        if not raw_data:
            return None
            
        # Prepare data for analysis
        start_time = raw_data[0]["timestamp"]
        end_time = raw_data[-1]["timestamp"]
        source_ids = [record["id"] for record in raw_data]
        
        # Get recent analyses
        recent_logs = self._get_recent_analyses(
            end_time=datetime.fromisoformat(start_time),
            limit=3
        )

        # Format data for LLM
        window_sessions = []
        total_keys = 0
        total_clicks = 0
        total_scrolls = 0
        
        for record in raw_data:
            window_sessions.extend(record["window_sessions"])
            total_keys += record["total_keys_pressed"]
            total_clicks += record["total_clicks"]
            total_scrolls += record["total_scrolls"]
        
        context = {
            "window_summaries": self._format_window_summaries(window_sessions),
            "total_keys": total_keys,
            "total_clicks": total_clicks,
            "total_scrolls": total_scrolls,
            "duration": self.collection_interval,
            "previous_logs": [log["llm_response"] for log in recent_logs] if recent_logs else None
        }
        
        # Get LLM analysis
        system_prompt = self.load_prompt("analysis_system_30sec", context)
        analysis_prompt = self.load_prompt("analysis_30sec", context)
        
        llm_response = self.call_llm(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "source_ids": source_ids,
            "analysis": llm_response
        }

    def _analyze_medium_term(
        self,
        raw_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze 5 minutes of activity data.
        
        Args:
            raw_data: List of raw activity records
            recent_analyses: List of recent 30-second analyses
            
        Returns:
            Analysis results
        """
        if not raw_data:
            return None
            
        start_time = raw_data[0]["timestamp"]
        end_time = raw_data[-1]["timestamp"]
        source_ids = [record["id"] for record in raw_data]

        recent_logs = self._get_recent_analyses(
            end_time=datetime.fromisoformat(start_time),
            limit=10
        )
        
        # Prepare context with both raw data and recent analyses
        context = {
            "window_summaries": self._format_window_summaries([
                session for record in raw_data 
                for session in record["window_sessions"]
            ]),
            "total_keys": sum(r["total_keys_pressed"] for r in raw_data),
            "total_clicks": sum(r["total_clicks"] for r in raw_data),
            "total_scrolls": sum(r["total_scrolls"] for r in raw_data),
            "recent_analyses": [log["llm_response"] for log in recent_logs] if recent_logs else None,
            "duration": self.collection_interval * self.repeat_interval
        }
        
        # Get LLM analysis
        system_prompt = self.load_prompt("analysis_system_5min", context)
        analysis_prompt = self.load_prompt("analysis_5min", context)
        
        llm_response = self.call_llm(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "source_ids": source_ids,
            "analysis": llm_response
        }

    def _store_analysis(self, analysis_data: Dict[str, Any], analysis_type: str):
        """Store analysis results in the database.
        
        Args:
            analysis_data: Analysis results to store
            analysis_type: Type of analysis ('30sec' or '5min')
        """
        if not analysis_data:
            return
        
        try:
            storage_data = {
                "session_id": self.session_id,
                "start_timestamp": analysis_data["start_time"],
                "end_timestamp": analysis_data["end_time"],
                "analysis_type": analysis_type,
                "source_activities": analysis_data["source_ids"],
                "llm_response": analysis_data["analysis"]
            }

            entity_id = str(uuid.uuid4())
            try:
                self.db_tools.add_entity("activity_analysis", entity_id, storage_data)
            except Exception as e:
                if "duplicate key" in str(e):
                    self.db_tools.update_entity("activity_analysis", entity_id, storage_data)
                else:
                    raise
        except Exception as e:
            self.logger.error(f"Failed to store analysis: {e}")

    def analyze_session(
        self,
        session_id: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze an entire session.
        
        Args:
            session_id: ID of the session to analyze
            custom_prompt: Optional custom prompt for analysis
            from_cli: Whether this is called from CLI (determines storage behavior)
            
        Returns:
            Session analysis results
        """
        # Get all raw data and analyses for the session
        query = {"session_id": session_id, "analysis_type": "special"}
        special_analyses = self.db_tools.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="asc"
        )
        
        all_analyses = special_analyses
        if len(special_analyses) < self.repeat_interval:
            regular_query = {"session_id": session_id}
            all_analyses = self.db_tools.query_entities(
                "activity_analysis",
                regular_query,
                sort_by="start_timestamp",
                sort_order="asc"
            )
        
        # Get raw data for timing information only
        raw_query = {"session_id": session_id}
        raw_data = self.db_tools.query_entities(
            "activity_raw",
            raw_query,
            sort_by="timestamp",
            sort_order="asc"
        )
        
        if not raw_data:
            return None
            
        # Original context (commented out but preserved)
        # original_context = {
        #     "session_id": session_id,
        #     "duration": "session",
        #     "start_time": raw_data[0]["timestamp"],
        #     "end_time": raw_data[-1]["timestamp"],
        #     "raw_data": raw_data,
        #     "analyses": analyses,
        #     "total_keys": sum(r["total_keys_pressed"] for r in raw_data),
        #     "total_clicks": sum(r["total_clicks"] for r in raw_data),
        #     "total_scrolls": sum(r["total_scrolls"] for r in raw_data)
        # }

        start_dt = datetime.fromisoformat(raw_data[0]["timestamp"])
        end_dt = datetime.fromisoformat(raw_data[-1]["timestamp"])

        start_time = start_dt.timestamp()
        end_time = end_dt.timestamp()

        duration = end_time - start_time

        # New simplified context
        context = {
            "session_id": session_id,
            "duration": duration,  # Now a number
            "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),  # Consistent ISO format
            "end_time": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),    # Consistent ISO format
            "analyses": [a["llm_response"] for a in all_analyses],
            "custom_prompt": custom_prompt
        }
        
        analysis_prompt = self.load_prompt("analysis_session", context)
            
        system_prompt = self.load_prompt("analysis_system_session", context)
        
        llm_response = self.call_llm(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        return {
            "start_time": raw_data[0]["timestamp"],
            "end_time": raw_data[-1]["timestamp"],
            "source_ids": [record["id"] for record in raw_data],
            "analysis": llm_response
        }

    def execute(self) -> Dict[str, Any]:
        """Execute the analysis agent.
        
        Returns:
            Status of the analysis process
        """
        try:
            self.start_analysis_cycles()
            return {
                "status": "success",
                "message": "Analysis cycles started successfully"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to start analysis: {str(e)}"
            }