"""Schema definitions for the system.

This module is the single source of truth for database schema definitions.
To change the database structure:
1. Update the schemas in this file
2. Run ./scripts/backup_db.sh --reset 
3. Restart the application
"""

from typing import Dict, Any

# Common field definitions
COMMON_FIELDS = {
   "id": {
       "type": "uuid",
       "primary_key": True,
       "description": "Unique identifier for the record"
   },
   "created_at": {
       "type": "timestamp with time zone",
       "default": "CURRENT_TIMESTAMP",
       "description": "When this record was created"
   },
   "updated_at": {
       "type": "timestamp with time zone", 
       "default": "CURRENT_TIMESTAMP",
       "description": "When this record was last modified"
   },
   "created_by": {
       "type": "text",
       "enum": ["human", "agent"],
       "description": "Whether a human or agent created this record"
   },
   "updated_by": {
       "type": "text",
       "enum": ["human", "agent"],
       "description": "Whether a human or agent last modified this record"
   }
}

def get_database_schema() -> Dict[str, Any]:
   """Get the database schema that defines table structures.
   
   Returns:
       Dict[str, Any]: The database schema definition
   """
   return {
       # Activity Monitoring
       "activity_raw": {
           "description": "Raw logs of user activities including window sessions and input events",
           "properties": {
               **COMMON_FIELDS,
               "session_id": {
                   "type": "uuid",
                   "description": "UUID of the monitoring session this log belongs to"
               },
               "screenshot": {
                   "type": "text",
                   "nullable": True,
                   "description": "Base64 encoded screenshot image data"
               },
               "window_sessions": {
                   "type": "jsonb",
                   "description": "Window activity sessions in this time period"
               },
               "total_keys_pressed": {
                   "type": "integer",
                   "default": 0,
                   "description": "Total number of keys pressed across all windows"
               },
               "total_clicks": {
                   "type": "integer", 
                   "default": 0,
                   "description": "Total number of mouse clicks across all windows"
               },
               "total_scrolls": {
                   "type": "integer",
                   "default": 0, 
                   "description": "Total number of scroll events across all windows"
               }
           },
           "required": ["session_id", "created_at"]
       },

       "activity_analysis": {
           "description": "Analysis of user activities at various time scales",
           "properties": {
               **COMMON_FIELDS,
               "session_id": {
                   "type": "uuid",
                   "description": "Session this analysis belongs to"
               },
               "start_timestamp": {
                   "type": "timestamp with time zone",
                   "description": "Start time of the period being analyzed"
               },
               "end_timestamp": {
                   "type": "timestamp with time zone",
                   "description": "End time of the period being analyzed"
               },
               "analysis_type": {
                   "type": "text",
                   "enum": ["regular", "special", "final"],
                   "description": "Type of analysis performed"
               },
               "source_activities": {
                   "type": "uuid[]",
                   "description": "Array of activity_raw IDs this analysis is based on",
                   "foreign_key": {
                       "table": "activity_raw",
                       "column": "id"
                   }
               },
               "llm_response": {
                   "type": "text",
                   "description": "LLM's analysis of the activity"
               }
           },
           "required": ["session_id", "start_timestamp", "end_timestamp", "analysis_type"]
       },

       # Task Management
       "tasks": {
           "description": "Task tracking and management",
           "properties": {
               **COMMON_FIELDS,
               "project": {
                   "type": "text",
                   "description": "Project or activity category this task belongs to"
               },
               "title": {
                   "type": "text",
                   "description": "Short task description"
               },
               "description": {
                   "type": "text",
                   "nullable": True,
                   "description": "Detailed task description"
               },
               "status": {
                   "type": "text",
                   "enum": ["to_do", "doing", "paused", "abandoned", "completed"],
                   "description": "Current status of the task"
               },
               "started_at": {
                   "type": "timestamp with time zone",
                   "nullable": True,
                   "description": "When work on the task began"
               },
               "completed_at": {
                   "type": "timestamp with time zone",
                   "nullable": True,
                   "description": "When the task reached its final state"
               },
               "priority": {
                   "type": "integer",
                   "minimum": 1,
                   "maximum": 5,
                   "default": 3,
                   "description": "Task priority (1-5)"
               },
               "parent_task_id": {
                   "type": "uuid",
                   "nullable": True,
                   "description": "ID of parent task if this is a subtask",
                   "foreign_key": {
                       "table": "tasks",
                       "column": "id"
                   }
               },
               "session_id": {
                   "type": "uuid",
                   "nullable": True,
                   "description": "Session ID when this task was worked on",
                   "foreign_key": {
                       "table": "activity_analysis",
                       "column": "session_id"
                   }
               }
           },
           "required": ["project", "title", "status"]
       },

       # Conversation Tracking
       "conversation": {
           "description": "A conversation between user and assistant",
           "properties": {
               **COMMON_FIELDS,
               "content": {
                   "type": "text",
                   "description": "The conversation content"
               },
               "analyzed": {
                   "type": "boolean",
                   "default": False,
                   "description": "Whether this conversation has been analyzed"
               },
               "metadata": {
                   "type": "jsonb",
                   "default": "{}",
                   "description": "Additional metadata about the conversation"
               }
           },
           "required": ["content"]
       },

       # Personality Analysis
       "personality_trait": {
           "description": "A personality trait or characteristic",
           "properties": {
               **COMMON_FIELDS,
               "trait_id": {
                   "type": "text",
                   "maxLength": 30,
                   "pattern": "^[a-z0-9_]+$",
                   "description": "Short, descriptive identifier using lowercase letters, numbers, and underscores"
               },
               "content": {
                   "type": "text",
                   "description": "Description of the trait"
               },
               "confidence": {
                   "type": "numeric",
                   "minimum": 0,
                   "maximum": 1,
                   "description": "Confidence score for this trait"
               },
               "metadata": {
                   "type": "jsonb",
                   "description": "Additional metadata",
                   "properties": {
                       "analysis": {"type": "text"},
                       "evidence": {"type": "text"},
                       "manifestation": {"type": "text"},
                       "impact": {"type": "text"},
                       "relationships": {"type": "text[]"}
                   }
               }
           },
           "required": ["trait_id", "content", "confidence", "metadata"]
       }
   }

def get_ontology_schema() -> Dict[str, Any]:
   """Get the ontology schema that defines semantic relationships.
   
   Returns:
       Dict[str, Any]: The ontology schema definition
   """
   return {
       "concepts": {
           "user": {"description": "A person using the system"},
           "conversation": {"description": "A text-based interaction"},
           "personality_trait": {"description": "A characteristic or behavior pattern"},
           "activity": {"description": "A logged user activity"},
           "task": {"description": "A tracked work item"}
       },
       "relationships": {
           "exhibits": {
               "description": "Shows a personality trait in conversation",
               "source_type": "conversation",
               "target_type": "personality_trait"
           },
           "correlates_with": {
               "description": "Related to another trait",
               "source_type": "personality_trait", 
               "target_type": "personality_trait"
           },
           "part_of": {
               "description": "Task is part of another task",
               "source_type": "task",
               "target_type": "task"
           }
       },
       "data_types": {
           "uuid": {"description": "Unique identifier"},
           "text": {"description": "Text value"},
           "jsonb": {"description": "JSON object"},
           "timestamp": {"description": "Date and time value"},
           "bytea": {"description": "Binary data"}
       }
   }