import base64
from pathlib import Path
import time
import threading
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.agent.base_agent import ToolBehavior
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.events import ActivityEventType, ActivityEvent, EventSystem
from .base_agent import BaseAgent
from src.utils.tts import TTSEngine
class AnalysisAgent(BaseAgent):
    """Agent for analyzing user activity data at different time scales."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager,
        session_id: str,
        tts_engine: TTSEngine
    ):
        super().__init__(
            config=config,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            tts_engine=tts_engine
        )

        # self.logger.debug("Initializing AnalysisAgent", extra={
        #     "session_id": session_id,
        #     "config": config
        # })

        try:
            # Set available tools for this agent
            # self.available_tools = ["interaction.text_to_speech"]

            self.session_id = session_id
            self.event_system = EventSystem()
            self.is_running = False
            self.completed_analyses = 0

            self.collection_interval = self.config["tracking"].get("activity_log_interval", 30)  # seconds
            self.repeat_interval = 10
            
            # self.logger.debug("AnalysisAgent initialization complete", extra={
            #     "session_id": session_id,
            #     "collection_interval": self.collection_interval,
            #     "repeat_interval": self.repeat_interval
            # })
            
        except Exception as e:
            self.logger.error("Failed to initialize AnalysisAgent", extra={
                "error": str(e),
                "session_id": session_id
            })
            raise
        
    async def start_analysis_cycles(self):
        """Start both analysis cycles."""
        try:
            # self.logger.debug("Starting analysis cycles", extra={
            #     "session_id": self.session_id,
            #     "is_running": self.is_running
            # })
            
            if not self.is_running:
                self.is_running = True
                await self._subscribe_to_events()
                # self.logger.info("Analysis started", extra={
                #     "session_id": self.session_id
                # })
        except Exception as e:
            self.logger.error("Failed to start analysis cycles", extra={
                "error": str(e),
                "session_id": self.session_id
            })
            raise
    
    async def stop_analysis_cycles(self):
        """Stop all analysis cycles and perform final session analysis."""
        try:
            # self.logger.debug("Stopping analysis cycles", extra={
            #     "session_id": self.session_id,
            #     "is_running": self.is_running
            # })
            
            if self.is_running:
                self.is_running = False
                # self.logger.info("Analysis stopped", extra={
                #     "session_id": self.session_id
                # })
                
                # Perform final session analysis
                self.logger.debug("Starting final session analysis")
                final_analysis = await self.analyze_session(self.session_id)
                if final_analysis:
                    await self._store_analysis(final_analysis, "final")
                    await self.save_responses_to_files()
                    # self.logger.info("Final analysis completed", extra={
                    #     "session_id": self.session_id
                    # })
        except Exception as e:
            self.logger.error("Failed to stop analysis cycles", extra={
                "error": str(e),
                "session_id": self.session_id
            }, exc_info=True)
            raise
    
    async def _subscribe_to_events(self):
        """Subscribe to activity events."""
        try:
            # self.logger.debug("Subscribing to events", extra={
            #     "session_id": self.session_id
            # })
            
            await self.event_system.broadcaster.subscribe_activity(
                ActivityEventType.ACTIVITY_STORED,
                self._handle_activity_stored
            )
            await self.event_system.broadcaster.subscribe_activity(
                ActivityEventType.ANALYSIS_STORED,
                self._handle_analysis_interval
            )
            
            # self.logger.debug("Successfully subscribed to events")
        except Exception as e:
            self.logger.error("Failed to subscribe to events", extra={
                "error": str(e),
                "session_id": self.session_id
            })
            raise
    
    async def _handle_activity_stored(self, event: ActivityEvent):
        """Handle incoming activity stored events."""
        if not self.is_running or event.session_id != self.session_id:
            return

        try:
            # self.logger.debug("Handling activity stored event", extra={
            #     "session_id": self.session_id,
            #     "event_timestamp": event.timestamp
            # })

            # Always do regular analysis
            end_time = datetime.now()
            start_time = end_time - timedelta(seconds=self.collection_interval)
            
            # self.logger.debug("Fetching recent raw data", extra={
            #     "start_time": start_time,
            #     "end_time": end_time
            # })
            
            raw_data = await self._get_recent_raw_data(start_time, end_time)
            if raw_data:
                # self.logger.debug("Analyzing short term data", extra={
                #     "data_points": len(raw_data)
                # })
                
                analysis = await self._analyze_short_term(raw_data)
                await self._store_analysis(analysis, "regular")

                # Broadcast analysis stored event
                event = ActivityEvent(
                    session_id=self.session_id,
                    timestamp=analysis["start_time"],
                    data=analysis,
                    event_type=ActivityEventType.ANALYSIS_STORED
                )
                await self.event_system.broadcaster.broadcast_activity(event)
                
                self.logger.debug("Short term analysis completed and stored")

        except Exception as e:
            self.logger.error("Error handling activity stored event", extra={
                "error": str(e),
                "session_id": self.session_id
            }, exc_info=True)

    async def _handle_analysis_interval(self, event: ActivityEvent):
        if not self.is_running or event.session_id != self.session_id:
            return

        self.completed_analyses += 1

        try:
            if self.completed_analyses >= self.repeat_interval:
                end_time = datetime.now()
                start_time = end_time - timedelta(seconds=(self.collection_interval * self.repeat_interval))
                raw_data = await self._get_recent_raw_data(start_time, end_time)

                if raw_data:
                    analysis = await self._analyze_medium_term(raw_data)
                    await self._store_analysis(analysis, "special")

                    # Broadcast ANALYSIS_MEDIUM_TERM_AVAILABLE event here
                    if analysis: # Only broadcast if analysis was successful
                        medium_term_event = ActivityEvent(
                            session_id=self.session_id,
                            timestamp=analysis["start_time"], # Or event.timestamp if you prefer the event's timestamp
                            data=analysis, # You can pass the analysis data as event data
                            event_type=ActivityEventType.ANALYSIS_MEDIUM_TERM_AVAILABLE
                        )
                        await self.event_system.broadcaster.broadcast_activity(medium_term_event)
                        self.logger.debug("Medium term analysis event broadcasted")


                self.completed_analyses = 0

        except Exception as e:
            self.logger.error(f"Error handling analysis interval event: {e}")

    async def _get_recent_raw_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get raw activity data for a time period."""
        query = {
            "created_at": {
                ">=": start_time.isoformat(),
                "<=": end_time.isoformat()
            }
        }
        
        raw_data = await self.db.query_entities(
            "activity_raw",
            query,
            sort_by="created_at",
            sort_order="asc"
        )
        
        # Ensure window_sessions is a list
        for record in raw_data:
            if "window_sessions" in record:
                if isinstance(record["window_sessions"], str):
                    try:
                        record["window_sessions"] = json.loads(record["window_sessions"])
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse window sessions for record {record['id']}")
                        record["window_sessions"] = []
                elif record["window_sessions"] is None:
                    record["window_sessions"] = []

        return raw_data

    async def _get_recent_analyses(
        self, 
        end_time: datetime, 
        limit: Optional[int] = None,
        analysis_type: Optional[str] = "regular"
    ) -> List[Dict[str, Any]]:
        """Get recent analyses for a time period."""
        query = {
            "session_id": self.session_id,
            "start_timestamp": {
                "<=": end_time.isoformat()
            }
        }
        
        query["analysis_type"] = analysis_type

        logs = await self.db.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="desc",
            limit=limit
        )
        logs = logs[::-1]
        return logs

    def _format_window_summaries(self, window_sessions: List[Dict[str, Any]]) -> str:
        """Format window summaries for analysis."""
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

            if session.get('privacy_filtered'):
                action_string = "this activity was filtered for privacy"
            else:

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

    async def _store_analysis(self, analysis_data: Dict[str, Any], analysis_type: str):
        """Store analysis results in the database."""
        if not analysis_data:
            return
        
        try:
            # Convert UUID objects to strings
            source_ids = [str(uuid_obj) for uuid_obj in analysis_data["source_ids"]]

            storage_data = {
                "session_id": self.session_id,
                "start_timestamp": analysis_data["start_time"],
                "end_timestamp": analysis_data["end_time"],
                "analysis_type": analysis_type,
                "source_activities": source_ids,
                "llm_response": analysis_data["analysis"],
                "created_by": "agent"
            }

            self.logger.debug(f"Storing analysis. Time: {analysis_data['start_time']}. Type: {analysis_type}. Response:\n{analysis_data['analysis']}\n")

            try:
                await self.db.add_entity(
                    "activity_analysis",
                    storage_data
                )
            except Exception as e:
                if "duplicate key" in str(e):
                    storage_data["updated_by"] = "agent"
                    await self.db.update_entity(
                        "activity_analysis",
                        storage_data
                    )
                else:
                    raise
        except Exception as e:
            self.logger.error(f"Failed to store analysis: {e}")

    async def _analyze_short_term(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze 30 seconds of activity data.
        
        Args:
            raw_data: List of raw activity records
            
        Returns:
            Analysis results
        """
        if not raw_data:
            return None
            
        # Prepare data for analysis
        start_time = raw_data[0]["created_at"]
        end_time = raw_data[-1]["created_at"]
        source_ids = [str(record["id"]) for record in raw_data]
        
        # Get recent analyses
        recent_logs = await self._get_recent_analyses(
            end_time=start_time,
            limit=3,
            analysis_type="regular"
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

        # Handle screenshot
        images = []
        if raw_data[0]["screenshot"]:
            try:
                screenshot_bytes = base64.b64decode(raw_data[0]["screenshot"])
                images.append((screenshot_bytes, 'image/png'))
                screenshot_available = True
            except Exception as e:
                self.logger.error(f"Failed to decode screenshot: {e}")
                screenshot_available = False
        else:
            screenshot_available = False
        
        context = {
            "window_summaries": self._format_window_summaries(window_sessions),
            "total_keys": total_keys,
            "total_clicks": total_clicks,
            "total_scrolls": total_scrolls,
            "duration": int(self.collection_interval),
            "previous_logs": [log["llm_response"] for log in recent_logs] if recent_logs else None,
            "screenshot_available": screenshot_available
        }
        
        # Get LLM analysis
        system_prompt = self.load_prompt("analysis_system_30sec", context)
        analysis_prompt = self.load_prompt("analysis_30sec", context)

        # self.logger.debug(f"SYSTEM PROMPT:\n{system_prompt}\n")
        # self.logger.debug(f"ANALYSIS PROMPT:\n{analysis_prompt}\n")
        
        llm_response = await self.call_llm(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            images=images if images else None,
            tool_behavior=ToolBehavior.USE_AND_DONE
        )
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "source_ids": source_ids,
            "analysis": llm_response
        }

    async def _analyze_medium_term(
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
            
        start_time = raw_data[0]["created_at"]
        end_time = raw_data[-1]["created_at"]
        source_ids = [str(record["id"]) for record in raw_data]

        recent_logs = await self._get_recent_analyses(
            end_time=start_time,
            limit=self.repeat_interval,
            analysis_type="regular"
        )

        latest_special_log = await self._get_recent_analyses(
            end_time=start_time,
            limit=1,
            analysis_type="special"
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
            "latest_special_log": latest_special_log[0]["llm_response"] if latest_special_log else None,
            "full_duration": int(self.collection_interval * self.repeat_interval),
            "duration": int(self.collection_interval)
        }
        
        # Get LLM analysis
        system_prompt = self.load_prompt("analysis_system_5min", context)
        analysis_prompt = self.load_prompt("analysis_5min", context)
        
        llm_response = await self.call_llm(
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

    async def analyze_session(
        self,
        session_id: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze an entire session."""

        if not session_id:
            # Get the last session ID from the database
            last_sessions = await self.db.query_entities(
                "activity_raw",
                query={},
                sort_by="created_at",
                sort_order="desc",
                limit=1
            )
            if not last_sessions:
                return None
            session_id = last_sessions[0]["session_id"]
        
        # Get all analyses for the session
        query = {"session_id": session_id, "analysis_type": "special"}
        special_analyses = await self.db.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="asc"
        )

        duration = str(self.collection_interval * self.repeat_interval) + " minutes"
        
        all_analyses = special_analyses
        if len(special_analyses) < self.repeat_interval / 2:
            regular_query = {"session_id": session_id}
            all_analyses = await self.db.query_entities(
                "activity_analysis",
                regular_query,
                sort_by="start_timestamp",
                sort_order="asc"
            )
            duration = str(self.collection_interval) + " seconds"
        
        # Get raw data for timing information
        raw_query = {"session_id": session_id}
        raw_data = await self.db.query_entities(
            "activity_raw",
            raw_query,
            sort_by="created_at",
            sort_order="asc"
        )
        
        if not raw_data:
            return None

        start_dt = raw_data[0]["created_at"]
        end_dt = raw_data[-1]["created_at"]
        
        start_time = start_dt.timestamp()
        end_time = end_dt.timestamp()
        session_duration = end_time - start_time

        context = {
            "session_duration": session_duration,
            "duration": duration,
            # "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            # "end_time": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "analyses": [a["llm_response"] for a in all_analyses],
            "custom_prompt": custom_prompt
        }
        
        analysis_prompt = self.load_prompt("analysis_session", context)
        system_prompt = self.load_prompt("analysis_system_session", context)
        
        llm_response = await self.call_llm(
            prompt=analysis_prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        return {
            "start_time": raw_data[0]["created_at"],
            "end_time": raw_data[-1]["created_at"],
            "source_ids": [record["id"] for record in raw_data],
            "analysis": llm_response
        }
    
    async def save_responses_to_files(self):
        """Save all analyses for the session to separate files."""
        # Get all analyses for the session
        query = {"session_id": self.session_id}
        analyses = await self.db.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="asc"
        )
        
        # Check if session is ongoing
        latest_activity = await self.db.query_entities(
            "activity_raw",
            {"session_id": self.session_id},
            sort_by="created_at",
            sort_order="desc",
            limit=1
        )
        
        latest_time = latest_activity[0]["created_at"]
        is_ongoing = (datetime.now().timestamp() - latest_time.timestamp()) < 60 if latest_activity else False
        session_status = "[ONGOING SESSION]" if is_ongoing else "[COMPLETED SESSION]"
        
        # Prepare files
        responses_dir = Path("responses")
        responses_dir.mkdir(exist_ok=True)
        
        for analysis in analyses:
            analysis["end_timestamp"] = analysis["created_at"]
        analyses.sort(key=lambda x: x["end_timestamp"])

        files = {
            "all": responses_dir / "responses.txt",
            "regular": responses_dir / "regular_responses.txt",
            "special": responses_dir / "special_responses.txt",
            "final": responses_dir / "final_response.txt"
        }
        
        # Write to files
        for file_path in files.values():
            with open(file_path, "w") as f:
                f.write(f"{session_status}\nSession ID: {self.session_id}\n\n")
                
        for analysis in analyses:
            timestamp = analysis["end_timestamp"]
            analysis_type = analysis["analysis_type"]
            response = analysis["llm_response"]
            
            # Write to all responses file
            with open(files["all"], "a") as f:
                f.write(f"({analysis_type}) {timestamp}: {response}\n\n")
            
            # Write to type-specific file
            with open(files[analysis_type], "a") as f:
                f.write(f"{timestamp}: {response}\n\n")