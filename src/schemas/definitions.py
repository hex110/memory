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
        "activity_log": {
            "description": "Logs of user activities including screenshots, key/mouse clicks, and open windows",
            "properties": {
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp of the activity log (serves as primary key)"
                },
                "session_id": {
                    "type": "string",
                    "description": "UUID of the monitoring session this log belongs to"
                },
                "screenshot": {
                    "type": "string",
                    "description": "Base64 encoded screenshot image"
                },
                "key_clicks": {
                    "type": "array",
                    "description": "List of keys pressed",
                    "items": {"type": "string"}
                },
                "open_windows": {
                    "type": "array",
                    "description": "List of currently open windows",
                    "items": {"type": "string"}
                },
                "keys_pressed_count": {
                    "type": "integer",
                    "description": "Total number of keys pressed",
                    "default": 0
                },
                "clicks_count": {
                    "type": "integer",
                    "description": "Total number of mouse clicks",
                    "default": 0
                },
                "scrolls_count": {
                    "type": "integer",
                    "description": "Total number of scroll events",
                    "default": 0
                },
                "llm_response": {
                    "type": "string",
                    "description": "LLM's analysis of the activity based on screenshot and log data"
                }
            },
            "required": ["timestamp", "session_id"]
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
