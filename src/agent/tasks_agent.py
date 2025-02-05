# tasks_agent.py
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.agent.base_agent import BaseAgent, ToolBehavior
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.events import ActivityEventType, ActivityEvent, EventSystem
from src.utils.tts import TTSEngine

class TasksAgent(BaseAgent):
    """Agent for managing tasks based on activity analysis."""

    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager,
        tts_engine: TTSEngine,
        session_id: str
    ):
        super().__init__(
            config=config,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            tts_engine=tts_engine
        )
        self.session_id = session_id
        self.event_system = EventSystem()
        self.available_tools = [
            "tasks.add_task",
            "tasks.complete_task",
            "tasks.start_task",
        ]

    async def start(self):
        """Start the tasks agent."""
        await self._subscribe_to_events()

    async def _subscribe_to_events(self):
        """Subscribe to relevant events."""
        await self.event_system.broadcaster.subscribe_activity(
            ActivityEventType.ANALYSIS_MEDIUM_TERM_AVAILABLE,
            self._handle_event
        )

    async def _handle_event(self, event: ActivityEvent):
        """Handle an event."""
        await self.manage_tasks_based_on_analysis()

    async def manage_tasks_based_on_analysis(self): # Renamed method and updated in subscription
        """Manage tasks based on medium term analysis events."""
        self.logger.info(f"Managing tasks based on analysis.")

        try:
            analysis_data = await self._get_recent_analyses(1, analysis_type="special")
            recent_short_term_analyses = await self._get_recent_analyses(5, analysis_type="regular")

            # self.logger.debug(f"Analysis data: {analysis_data}")
            # self.logger.debug(f"Recent short term analyses: {recent_short_term_analyses}")

            to_do_tasks_list = await self.list_tasks_by_status("to_do") # Get to-do tasks
            doing_tasks_list = await self.list_tasks_by_status("doing") # Get doing tasks

            context = {
                "medium_term_analysis": analysis_data[0]["llm_response"],
                "short_term_analyses": [log["llm_response"] for log in recent_short_term_analyses] if recent_short_term_analyses else None,
                "to_do_tasks": to_do_tasks_list, # Add to-do tasks to context
                "doing_tasks": doing_tasks_list # Add doing tasks to context
            }

            prompt = self.load_prompt("tasks_analysis_prompt", context)

            llm_response = await self.call_llm(
                prompt=prompt,
                system_prompt="You are a helpful task management assistant. Analyze user activity and suggest task-related actions.",
                temperature=0.7,
                tool_behavior=ToolBehavior.KEEP_USING_UNTIL_DONE,
            )

            self.logger.info(f"LLM Task Management Response:\n{llm_response}")

        except Exception as e:
            self.logger.error(f"Error managing tasks based on analysis: {e}", exc_info=True)


    async def _get_recent_analyses(self, number_of_analyses: int, analysis_type: str = "regular") -> List[Dict[str, Any]]:
        """Helper method to get recent analyses within a time range."""
        query = {
            "analysis_type": analysis_type
        }
        logs = await self.db.query_entities(
            "activity_analysis",
            query,
            sort_by="start_timestamp",
            sort_order="desc",
            limit=number_of_analyses
        )
        return logs


    async def list_tasks_by_status(self, status: str) -> str:
        """Lists tasks filtered by status."""
        try:
            tasks = await self.db.query_entities( # Access db directly
                "tasks", query={"status": status}
            )
            if not tasks:
                return f"No tasks found with status '{status}'."

            task_list = "\n".join([
                f"- {task['title']} (ID: {task['id']}, Project: {task['project']})"
                for task in tasks
            ])
            return f"Tasks with status '{status}':\n{task_list}"
        except Exception as e:
            self.logger.error(f"Error listing tasks by status: {e}")
            return f"Failed to list tasks by status '{status}'. Please check logs."

    async def list_tasks_by_project(self, project: str) -> str:
        """Lists tasks filtered by project."""
        try:
            tasks = await self.db.query_entities( # Access db directly
                "tasks", query={"project": project}
            )
            if not tasks:
                return f"No tasks found for project '{project}'."

            task_list = "\n".join([
                f"- {task['title']} (ID: {task['id']}, Status: {task['status']})"
                for task in tasks
            ])
            return f"Tasks for project '{project}':\n{task_list}"
        except Exception as e:
            self.logger.error(f"Error listing tasks by project: {e}")
            return f"Failed to list tasks for project '{project}'. Please check logs."

    async def get_task_details(self, task_id: str) -> str:
        """Gets detailed information about a specific task."""
        try:
            task = await self.db.get_entity("tasks", task_id) # Access db directly
            if not task:
                return f"Task with id '{task_id}' not found."

            details = f"""
            Task Details:
            - ID: {task['id']}
            - Project: {task['project']}
            - Title: {task['title']}
            - Description: {task.get('description', 'N/A')}
            - Status: {task['status']}
            - Created At: {task['created_at']}
            - Started At: {task.get('started_at', 'N/A')}
            - Completed At: {task.get('completed_at', 'N/A')}
            - Priority: {task.get('priority', 'N/A')}
            """ # use .get to handle potential None values for optional fields
            return details.strip() # remove leading/trailing whitespace
        except Exception as e:
            self.logger.error(f"Error getting task details: {e}")
            return f"Failed to get details for task '{task_id}'. Please check logs."
    # --- End Task Listing Methods ---