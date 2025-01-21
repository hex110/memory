"""Schema definitions for the system.

This module contains both:
1. Database Schema: Defines the structural schema (tables, fields, types)
2. Ontology Schema: Defines the semantic schema (concepts, relationships)
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
        "behavioral_pattern": {
            "description": "A recurring pattern of behavior",
            "properties": {
                "id": {
                    "type": "string",
                    "maxLength": 30,
                    "pattern": "^[a-z0-9_]+$",
                    "description": "Short, descriptive identifier using lowercase letters, numbers, and underscores"
                },
                "type": {"type": "string"},
                "content": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "context": {"type": "string"},
                        "frequency": {"type": "string"},
                        "triggers": {"type": "string"},
                        "analysis": {"type": "string"},
                        "impact": {"type": "string"},
                        "evidence": {"type": "string"}
                    }
                }
            }
        },
        "relationship": {
            "description": "A relationship between two entities",
            "properties": {
                "id": {
                    "type": "string",
                    "maxLength": 30,
                    "pattern": "^[a-z0-9_]+$",
                    "description": "Short, descriptive identifier using lowercase letters, numbers, and underscores"
                },
                "type": {"type": "string"},
                "from_id": {"type": "string"},
                "to_id": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "nature": {"type": "string"},
                        "strength": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence": {"type": "string"}
                    }
                }
            }
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
            "relationship": {"description": "A link between two things"},
            "tag": {"description": "A label to categorize data"}
        },
        "relationships": {
            "related_to": {
                "description": "Represents some relationship between two items",
                "source_type": "user",
                "target_type": "conversation"
            },
            "tagged_with": {
                "description": "Marks which items are tagged with which labels",
                "source_type": "conversation",
                "target_type": "tag"
            }
        },
        "data_types": {
            "uuid": {"description": "Unique id for all database objects"},
            "text": {"description": "Text value"},
            "json": {"description": "JSON object"},
            "timestamp": {"description": "Date and time value"},
        }
    }
