# tl_tasks.py
from datetime import datetime
from src.utils.logging import get_logger
import json
from src.database.postgresql import PostgreSQLDatabase
import uuid

logger = get_logger(__name__)

class TaskManager:
    def __init__(self, db: PostgreSQLDatabase):
        self.db = db

    async def add_task(self, title: str, project: str) -> str:
        """Adds a new task to the database."""
        try:
            task_id = uuid.uuid4()
            task_data = {
                "id": str(task_id),
                "project": project,
                "title": title,
                "status": "to_do",
                "created_by": "agent",
                "updated_by": "agent"
            }
            await self.db.add_entity("tasks", task_data)
            return f"Task '{title}' added to project '{project}' with id '{task_id}'."
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            return f"Failed to add task '{title}'. Please check logs for details."

    async def complete_task(self, task_id: str) -> str:
        """Marks a task as completed."""
        try:
            task_data = {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "updated_by": "agent"
            }
            existing_task = await self.db.get_entity("tasks", task_id)
            if not existing_task:
                return f"Task with id '{task_id}' not found."

            await self.db.update_entity("tasks", task_id, task_data)
            return f"Task with id '{task_id}' marked as completed."

        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return f"Failed to complete task '{task_id}'. Please check logs for details."

    async def start_task(self, task_id: str) -> str:
        """Marks a task as started."""
        try:
            task_data = {
                "status": "doing",
                "started_at": datetime.utcnow(),
                "updated_by": "agent"
            }

            existing_task = await self.db.get_entity("tasks", task_id)
            if not existing_task:
                return f"Task with id '{task_id}' not found."

            await self.db.update_entity("tasks", task_id, task_data)
            return f"Task with id '{task_id}' marked as started."

        except Exception as e:
            logger.error(f"Error starting task: {e}")
            return f"Failed to start task '{task_id}'. Please check logs for details."