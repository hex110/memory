from datetime import datetime
from src.utils.logging import get_logger
import json
from src.utils.activity.activity_manager import ActivityManager
from src.database.postgresql import PostgreSQLDatabase
logger = get_logger(__name__)

class ContextTools:
    def __init__(self, db: PostgreSQLDatabase, activity_manager: ActivityManager = None):
        self.db = db
        self.activity_manager = activity_manager
        
    async def get_logs(self, count: int):
        """Get recent user observation logs."""
        logs = await self.db.query_entities(
            "activity_analysis",
            query={},
            sort_by="created_at",
            sort_order="desc",
            limit=count
        )
        
        # Format the response with ISO format strings for timestamps
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                "timestamp": log["created_at"].isoformat(),  # Convert datetime to string
                "analysis": log["llm_response"]
            })
            
        # logger.debug(f"Formatted logs: {formatted_logs}")
            
        # Return a dictionary containing the logs array
        return {
            "logs": formatted_logs
        }
        
    async def bookmark_moment(self):
        """Save current moment as a bookmark."""
        timestamp = datetime.now().isoformat()
        
        bookmark_data = {
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": "user",
            "updated_by": "user"
        }
        
        await self.db.add_entity("bookmarks", bookmark_data)
        
        return {
            "status": "success",
            "timestamp": timestamp,
            "message": "Moment bookmarked successfully"
        }

    async def get_recent_video(self):
        """Get recent screen recording buffer."""
        if not self.activity_manager:
            return {"error": "Activity manager not available"}
            
        video_buffer = await self.activity_manager.get_video_buffer()
        if video_buffer:
            return {
                "status": "success",
                "video_data": video_buffer,
                "mime_type": "video/mp4"
            }
        return {"error": "No recent video available"}
        
    async def get_recent_inputs(self, seconds: int = 30):
        """Get recent input activity."""
        if not self.input_tracker:
            return {"error": "Input tracker not available"}
            
        recent_sessions = await self.activity_manager.get_recent_sessions(seconds=seconds)
        
        formatted_sessions = []
        for session in recent_sessions:
            formatted_sessions.append({
                "window": {
                    "class": session.window_info['class'],
                    "title": session.window_info['title']
                },
                "timing": {
                    "start": session.start_time.strftime('%H:%M:%S'),
                    "end": session.end_time.strftime('%H:%M:%S')
                },
                "activity": {
                    "keys": session.key_count,
                    "clicks": session.click_count,
                    "scrolls": session.scroll_count
                }
            })
            
        return formatted_sessions