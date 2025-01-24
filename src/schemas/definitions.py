"""Schema definitions for the system.

This module is the single source of truth for database schema definitions.
To change the database structure:
1. Update the schemas in this file
2. Run ./scripts/backup_db.sh --reset
3. Restart the application
"""

from typing import Dict, Any

def get_database_schema() -> Dict[str, Any]:
    """Get the database schema that defines table structures.
    
    This schema defines:
    - What tables/collections exist
    - What fields each table has
    - The types and constraints for each field
    
    Returns:
        Dict[str, Any]: The database schema definition
    """
    return {
        "conversation": {
            "description": "A conversation between user and assistant",
            "properties": {
                "id": {"type": "string"},
                "content": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "analyzed": {"type": "boolean", "default": False}
            }
        },
        "personality_trait": {
            "description": "A personality trait or characteristic",
            "properties": {
                "id": {
                    "type": "string",
                    "maxLength": 30,
                    "pattern": "^[a-z0-9_]+$",
                    "description": "Short, descriptive identifier using lowercase letters, numbers, and underscores"
                },
                "content": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "analysis": {"type": "string"},
                        "evidence": {"type": "string"},
                        "manifestation": {"type": "string"},
                        "impact": {"type": "string"},
                        "relationships": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            }
        },
        "activity_raw": {
            "description": "Raw logs of user activities including window sessions, screenshots, and input events",
            "properties": {
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp of the activity log"
                },
                "session_id": {
                    "type": "string",
                    "description": "UUID of the monitoring session this log belongs to"
                },
                "screenshot": {
                    "type": "string",
                    "description": "Base64 encoded screenshot image"
                },
                "window_sessions": {
                    "type": "string",
                    "description": "JSON string containing list of window activity sessions in this time period"
                },
                "total_keys_pressed": {
                    "type": "integer",
                    "description": "Total number of keys pressed across all windows",
                    "default": 0
                },
                "total_clicks": {
                    "type": "integer",
                    "description": "Total number of mouse clicks across all windows",
                    "default": 0
                },
                "total_scrolls": {
                    "type": "integer",
                    "description": "Total number of scroll events across all windows",
                    "default": 0
                }
            },
            "required": ["timestamp", "session_id"]
        },

        "activity_analysis": {
            "description": "Analysis of user activities at various time scales",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session this analysis belongs to"
                },
                "start_timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Start time of the period being analyzed"
                },
                "end_timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "End time of the period being analyzed"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["regular", "special", "final"],
                    "description": "Type of analysis performed"
                },
                "source_activities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of activity_ids this analysis is based on"
                },
                "llm_response": {
                    "type": "string",
                    "description": "LLM's analysis of the activity"
                }
            },
            "required": ["session_id", "start_timestamp", "end_timestamp", "analysis_type"]
        },

        "tasks": {
            "description": "Task tracking and management",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project or activity category this task belongs to"
                },
                "title": {
                    "type": "string",
                    "description": "Short task description"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description"
                },
                "status": {
                    "type": "string",
                    "enum": ["to_do", "doing", "paused", "abandoned", "completed"],
                    "description": "Current status of the task"
                },
                "created_by": {
                    "type": "string",
                    "enum": ["human", "agent"],
                    "description": "Who created this task"
                },
                "last_modified_by": {
                    "type": "string",
                    "enum": ["human", "agent"],
                    "description": "Who last modified this task"
                },
                "started_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When work on the task began"
                },
                "completed_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When the task reached its final state (completed/abandoned)"
                },
                "priority": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Task priority (1-5)"
                },
                "parent_task": {
                    "type": "string",
                    "description": "ID of parent task if this is a subtask"
                }
            },
            "required": ["project", "title", "status", "created_by"]
        }
    }

def get_ontology_schema() -> Dict[str, Any]:
    """Get the ontology schema that defines semantic relationships.
    
    This schema defines:
    - What concepts exist in the system
    - How concepts can relate to each other
    - What data types are supported
    
    Returns:
        Dict[str, Any]: The ontology schema definition
    """
    return {
        "concepts": {
            "user": {"description": "A person using the system"},
            "conversation": {"description": "A text-based interaction"},
            "personality_trait": {"description": "A characteristic or behavior pattern"},
            "activity": {"description": "A logged user activity"}
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
            "demonstrates": {
                "description": "Shows a trait through activity",
                "source_type": "activity",
                "target_type": "personality_trait"
            }
        },
        "data_types": {
            "uuid": {"description": "Unique id for all database objects"},
            "text": {"description": "Text value"},
            "json": {"description": "JSON object"},
            "timestamp": {"description": "Date and time value"},
            "image": {"description": "Base64 encoded image"}
        }
    }
