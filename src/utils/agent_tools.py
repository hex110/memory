"""Database and ontology access tools for agents."""

import json
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from functools import wraps
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager

# Set up logging
logger = logging.getLogger(__name__)

def track_operation(operation_type: str, method_name: str) -> Callable:
    """Decorator for tracking database operations.
    
    Args:
        operation_type: Type of operation (read/write)
        method_name: Name of the method being called
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start_time
                
                # Update stats
                self.operation_stats["total_operations"] += 1
                self.operation_stats[f"{operation_type}_operations"] += 1
                self.operation_stats["total_time"] += duration
                
                # Log operation
                logger.info(
                    f"DB Operation: {method_name} ({operation_type}) - "
                    f"Duration: {duration:.3f}s - "
                    f"Role: {self.role}"
                )
                return result
            except Exception as e:
                self.operation_stats["errors"] += 1
                logger.error(
                    f"DB Operation Failed: {method_name} ({operation_type}) - "
                    f"Error: {str(e)} - "
                    f"Role: {self.role}",
                    exc_info=True
                )
                raise
        return wrapper
    return decorator

def tool_schema(schema: Dict[str, Any]) -> Callable:
    """Decorator to attach a schema to a method."""
    def decorator(func: Callable) -> Callable:
        func.__schema__ = schema
        return func
    return decorator

class AgentDatabaseTools:
    """Provides safe, role-specific database access methods for agents.
    
    This class acts as a middleware between agents and the database/ontology,
    providing:
    1. Role-based access control
    2. Method validation and safety checks
    3. Automatic tool schema generation
    4. Logging and monitoring
    """
    
    # Role definitions with allowed methods
    ROLE_PERMISSIONS = {
        "analyzer": {
            "read_methods": ["get_entity", "get_entities", "get_schema", "query_entities"],
            "write_methods": ["add_entity", "update_entity", "remove_entity"]
        },
        "curator": {
            "read_methods": ["get_entity", "get_entities", "get_schema", "query_entities"],
            "write_methods": []  # Read-only role
        },
        "monitor": {
            "read_methods": ["get_entities", "query_entities", "get_entity"],
            "write_methods": ["add_entity", "update_entity"]  # Allow both add and update for activity logs
        }
    }
    
    # Tool Schemas
    TOOL_SCHEMAS = {
        "get_entity": {
            "name": "get_entity",
            "description": "Get a single entity by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to get"
                    },
                    "entity_id": {
                        "type": "string", 
                        "description": "ID of entity to get"
                    }
                },
                "required": ["entity_type", "entity_id"]
            }
        },
        "get_entities": {
            "name": "get_entities",
            "description": "Get all entities of a type",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entities to get"
                    }
                },
                "required": ["entity_type"]
            }
        },
        "get_schema": {
            "name": "get_schema",
            "description": "Get schema definition for an entity type or all schemas",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type to get schema for (optional)"
                    }
                }
            }
        },
        "add_entity": {
            "name": "add_entity",
            "description": "Add a new entity",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to add"
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "ID for the new entity"
                    },
                    "data": {
                        "type": "object",
                        "description": "Entity data",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Main content of the entity"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score between 0 and 1",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Additional metadata",
                                "properties": {
                                    "analysis": {
                                        "type": "string",
                                        "description": "Analysis of the entity"
                                    },
                                    "evidence": {
                                        "type": "string",
                                        "description": "Supporting evidence"
                                    },
                                    "manifestation": {
                                        "type": "string",
                                        "description": "How the trait manifests"
                                    },
                                    "impact": {
                                        "type": "string",
                                        "description": "Impact on behavior"
                                    },
                                    "relationships": {
                                        "type": "array",
                                        "description": "Related traits",
                                        "items": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "required": ["analysis", "evidence", "manifestation", "impact", "relationships"]
                            }
                        },
                        "required": ["content", "confidence", "metadata"]
                    }
                },
                "required": ["entity_type", "entity_id", "data"]
            }
        },
        "update_entity": {
            "name": "update_entity",
            "description": "Update an existing entity",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to update"
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "ID of entity to update"
                    },
                    "data": {
                        "type": "object",
                        "description": "Updated entity data",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Main content of the entity"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score between 0 and 1",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Additional metadata",
                                "properties": {
                                    "analysis": {
                                        "type": "string",
                                        "description": "Analysis of the entity"
                                    },
                                    "evidence": {
                                        "type": "string",
                                        "description": "Supporting evidence"
                                    },
                                    "manifestation": {
                                        "type": "string",
                                        "description": "How the trait manifests"
                                    },
                                    "impact": {
                                        "type": "string",
                                        "description": "Impact on behavior"
                                    },
                                    "relationships": {
                                        "type": "array",
                                        "description": "Related traits",
                                        "items": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "required": ["analysis", "evidence", "manifestation", "impact", "relationships"]
                            }
                        },
                        "required": ["content", "confidence", "metadata"]
                    }
                },
                "required": ["entity_type", "entity_id", "data"]
            }
        },
        "remove_entity": {
            "name": "remove_entity",
            "description": "Remove an entity by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to remove"
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "ID of entity to remove"
                    }
                },
                "required": ["entity_type", "entity_id"]
            }
        },
        "query_entities": {
            "name": "query_entities",
            "description": "Query entities with filters and sorting",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entities to query (activity_log, conversation, or personality_trait)"
                    },
                    "query": {
                        "type": "object",
                        "description": "Query filters for the entity fields",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Filter by entity ID"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Filter by session ID (for activity_log)"
                            },
                            "timestamp": {
                                "type": "string",
                                "description": "Filter by timestamp (ISO format, e.g. 2024-01-22T05:18:45)"
                            },
                            "content": {
                                "type": "string",
                                "description": "Filter by content text"
                            }
                        }
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by (e.g. timestamp, id)"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return"
                    }
                },
                "required": ["entity_type", "query"]
            }
        }
    }
    
    def __init__(self, db_interface: DatabaseInterface, 
                 ontology_manager: OntologyManager,
                 role: str):
        """Initialize the tools wrapper.
        
        Args:
            db_interface: Database interface to use
            ontology_manager: Ontology manager to use
            role: Role to determine available methods
            
        Raises:
            ValueError: If role is not recognized
        """
        if role not in self.ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role: {role}")
            
        self.db = db_interface
        self.ontology = ontology_manager
        self.role = role
        self.permissions = self.ROLE_PERMISSIONS[role]
        
        # Initialize operation tracking
        self.operation_stats = {
            "total_operations": 0,
            "read_operations": 0,
            "write_operations": 0,
            "errors": 0,
            "total_time": 0.0
        }
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get JSON schemas for tools available to this role."""
        schemas = []
        all_methods = (
            self.permissions["read_methods"] + 
            self.permissions["write_methods"]
        )
        
        for method_name in all_methods:
            if method_name in self.TOOL_SCHEMAS:
                schemas.append(self.TOOL_SCHEMAS[method_name])
        
        return schemas
    
    def _check_permission(self, method_name: str, operation_type: str) -> None:
        """Check if current role has permission for a method.
        
        Args:
            method_name: Name of the method to check
            operation_type: Type of operation (read/write)
            
        Raises:
            PermissionError: If role doesn't have permission
        """
        allowed_methods = self.permissions[f"{operation_type}_methods"]
        if method_name not in allowed_methods:
            raise PermissionError(
                f"Role '{self.role}' cannot {operation_type} using {method_name}"
            )
    
    def _normalize_entity_id(self, entity_id: str) -> str:
        """Normalize entity ID to a consistent format.
        
        Args:
            entity_id: Raw entity ID
            
        Returns:
            str: Normalized entity ID
        """
        # Convert to lowercase and replace spaces with underscores
        normalized = entity_id.lower().replace(' ', '_')
        # Remove any special characters except underscores
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        return normalized

    # Tool Implementations
    @track_operation("read", "get_entity")
    @tool_schema(TOOL_SCHEMAS["get_entity"])
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity from the database."""
        self._check_permission("get_entity", "read")
        normalized_id = self._normalize_entity_id(entity_id)
        return self.db.get_entity(entity_type, normalized_id)
    
    @track_operation("read", "get_entities")
    @tool_schema(TOOL_SCHEMAS["get_entities"])
    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a type."""
        self._check_permission("get_entities", "read")
        return self.db.get_entities(entity_type)
    
    @track_operation("read", "get_schema")
    @tool_schema(TOOL_SCHEMAS["get_schema"])
    def get_schema(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get schema for an entity type or all schemas."""
        self._check_permission("get_schema", "read")
        if entity_type:
            return self.ontology.get_schema(entity_type)
        return self.ontology.schemas
    
    @track_operation("write", "add_entity")
    @tool_schema(TOOL_SCHEMAS["add_entity"])
    def add_entity(self, entity_type: str, entity_id: str,
                  data: Dict[str, Any]) -> None:
        """Add a new entity to the database."""
        self._check_permission("add_entity", "write")
        normalized_id = self._normalize_entity_id(entity_id)
        return self.db.add_entity(entity_type, normalized_id, data)
    
    @track_operation("write", "update_entity")
    @tool_schema(TOOL_SCHEMAS["update_entity"])
    def update_entity(self, entity_type: str, entity_id: str,
                     data: Dict[str, Any]) -> None:
        """Update an existing entity."""
        self._check_permission("update_entity", "write")
        normalized_id = self._normalize_entity_id(entity_id)
        
        try:
            # Try to get existing entity first
            existing = self.get_entity(entity_type, normalized_id)
            if existing:
                # Merge new data with existing data
                merged_data = {**existing, **data}
                return self.db.update_entity(entity_type, normalized_id, merged_data)
        except Exception:
            pass
            
        # If entity doesn't exist or get failed, try to add it
        try:
            return self.db.add_entity(entity_type, normalized_id, data)
        except Exception as e:
            if "duplicate key" in str(e):
                # If add failed due to duplicate, try update again
                return self.db.update_entity(entity_type, normalized_id, data)
            raise

    @track_operation("write", "remove_entity")
    @tool_schema(TOOL_SCHEMAS["remove_entity"])
    def remove_entity(self, entity_type: str, entity_id: str) -> None:
        """Remove an entity from the database.
        
        Args:
            entity_type: Type of entity to remove
            entity_id: ID of entity to remove
        """
        self._check_permission("remove_entity", "write")
        entity_id = self._normalize_entity_id(entity_id)
        self.db.delete(entity_type, entity_id)

    @track_operation("read", "query_entities")
    @tool_schema(TOOL_SCHEMAS["query_entities"])
    def query_entities(
        self,
        entity_type: str,
        query: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters and sorting.
        
        Args:
            entity_type: Type of entities to query
            query: Query filters
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
            limit: Maximum number of results
            
        Returns:
            List of matching entities
        """
        self._check_permission("query_entities", "read")
        return self.db.query_entities(
            entity_type,
            query,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit
        ) 