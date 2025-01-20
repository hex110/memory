"""Database and ontology access tools for agents."""

import json
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from functools import wraps
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager

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
            "read_methods": ["get_entity", "get_entities", "get_schema"],
            "write_methods": ["add_entity", "update_entity"]
        },
        "curator": {
            "read_methods": ["get_entity", "get_entities", "get_schema"],
            "write_methods": []  # Read-only role
        }
    }
    
    def __init__(self, db_interface: DatabaseInterface, 
                 ontology_manager: OntologyManager,
                 role: str):
        """Initialize the tools manager.
        
        Args:
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            role: Agent role determining available methods
        
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
            [(name, "read") for name in self.permissions["read_methods"]] +
            [(name, "write") for name in self.permissions["write_methods"]]
        )
        
        for method_name, op_type in all_methods:
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                if hasattr(method, "__schema__"):
                    schemas.append(method.__schema__)
        
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
    
    # Tool Implementations
    @track_operation("read", "get_entity")
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity from the database."""
        self._check_permission("get_entity", "read")
        return self.db.get_entity(entity_type, entity_id)
    
    @track_operation("read", "get_entities")
    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a type."""
        self._check_permission("get_entities", "read")
        return self.db.get_entities(entity_type)
    
    @track_operation("read", "get_schema")
    def get_schema(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get schema for an entity type or all schemas."""
        self._check_permission("get_schema", "read")
        if entity_type:
            return self.ontology.get_schema(entity_type)
        return self.ontology.schemas
    
    @track_operation("write", "add_entity")
    def add_entity(self, entity_type: str, entity_id: str,
                  data: Dict[str, Any]) -> None:
        """Add a new entity to the database."""
        self._check_permission("add_entity", "write")
        return self.db.add_entity(entity_type, entity_id, data)
    
    @track_operation("write", "update_entity")
    def update_entity(self, entity_type: str, entity_id: str,
                     data: Dict[str, Any]) -> None:
        """Update an existing entity."""
        self._check_permission("update_entity", "write")
        return self.db.update_entity(entity_type, entity_id, data)
    
    # Tool Schemas
    _schema_get_entity = {
        "name": "get_entity",
        "description": "Get an entity from the database by type and ID",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entity to retrieve"
                },
                "entity_id": {
                    "type": "string",
                    "description": "ID of the entity"
                }
            },
            "required": ["entity_type", "entity_id"]
        }
    }
    
    _schema_get_entities = {
        "name": "get_entities",
        "description": "Get all entities of a specific type",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entities to retrieve"
                }
            },
            "required": ["entity_type"]
        }
    }
    
    _schema_get_schema = {
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
    }
    
    _schema_add_entity = {
        "name": "add_entity",
        "description": "Add a new entity to the database",
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
                    "description": "Entity data matching the schema"
                }
            },
            "required": ["entity_type", "entity_id", "data"]
        }
    }
    
    _schema_update_entity = {
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
                    "description": "ID of the entity"
                },
                "data": {
                    "type": "object",
                    "description": "New entity data"
                }
            },
            "required": ["entity_type", "entity_id", "data"]
        }
    } 