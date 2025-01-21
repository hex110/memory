"""Interface definition for ontology management.

This module defines the interface for managing the system's semantic schema (ontology).
The ontology system is designed around these key concepts:

1. Schema Management:
   - Define valid entity types and their properties
   - Specify relationships between entities
   - Validate data against schemas

2. Semantic Relationships:
   - Track how different concepts relate
   - Support inference and reasoning
   - Maintain relationship metadata

3. Validation:
   - Ensure data matches schema definitions
   - Validate relationship constraints
   - Check semantic consistency

Example of using the ontology manager:

```python
from src.ontology.manager import OntologyManager

# Initialize with schema
manager = OntologyManager(initial_schema={
    "concepts": {
        "user": {
            "description": "A system user",
            "properties": {
                "name": {"type": "string"},
                "preferences": {"type": "object"}
            }
        }
    },
    "relationships": {
        "follows": {
            "description": "User follows another user",
            "source_type": "user",
            "target_type": "user",
            "properties": {
                "since": {"type": "string", "format": "date-time"}
            }
        }
    }
})

# Validate entity
user = {
    "type": "user",
    "name": "Alice",
    "preferences": {"theme": "dark"}
}
is_valid = manager.validate_entity("user", user)

# Check relationship
can_follow = manager.can_relate("user", "follows", "user")
```

Required components:
1. Schema definitions for entity types
2. Relationship type definitions
3. Validation rules and constraints
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set

class OntologyInterface(ABC):
    """Interface for ontology management.
    
    This interface defines how the system's semantic schema should be managed.
    Most implementations should use the OntologyManager class rather than
    implementing this directly, as it provides:
    - Schema validation
    - Relationship management
    - Type checking
    - Error handling
    """
    
    @abstractmethod
    def __init__(self, initial_schema: Optional[Dict[str, Any]] = None):
        """Initialize the ontology manager.
        
        Args:
            initial_schema: Initial schema definitions
            
        The schema should define:
        1. Entity types and their properties
        2. Relationship types and constraints
        3. Validation rules
        
        Example schema:
            {
                "concepts": {
                    "user": {
                        "description": "A system user",
                        "properties": {...}
                    }
                },
                "relationships": {
                    "follows": {
                        "description": "User follows user",
                        "source_type": "user",
                        "target_type": "user"
                    }
                }
            }
        """
        pass
    
    @property
    @abstractmethod
    def schemas(self) -> Dict[str, Any]:
        """Get all schema definitions.
        
        Returns:
            Dict containing all entity and relationship schemas
            
        Example:
            schemas = manager.schemas
            user_schema = schemas["concepts"]["user"]
        """
        pass
    
    @abstractmethod
    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Get schema for an entity type.
        
        Args:
            entity_type: Type of entity to get schema for
            
        Returns:
            Schema definition for the entity type
            
        Example:
            user_schema = manager.get_schema("user")
            required_fields = user_schema["properties"]["required"]
        """
        pass
    
    @abstractmethod
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity against its schema.
        
        Args:
            entity_type: Type of entity to validate
            data: Entity data to validate
            
        Returns:
            True if valid, False otherwise
            
        Example:
            user = {"name": "Alice", "email": "alice@example.com"}
            is_valid = manager.validate_entity("user", user)
        """
        pass
    
    @abstractmethod
    def can_relate(
        self,
        source_type: str,
        relationship_type: str,
        target_type: str
    ) -> bool:
        """Check if two types can have a relationship.
        
        Args:
            source_type: Type of source entity
            relationship_type: Type of relationship
            target_type: Type of target entity
            
        Returns:
            True if relationship is valid, False otherwise
            
        Example:
            # Check if users can follow each other
            can_follow = manager.can_relate("user", "follows", "user")
        """
        pass
    
    @abstractmethod
    def get_valid_relationships(
        self,
        source_type: str,
        target_type: str
    ) -> Set[str]:
        """Get valid relationship types between entities.
        
        Args:
            source_type: Type of source entity
            target_type: Type of target entity
            
        Returns:
            Set of valid relationship type names
            
        Example:
            # Get all valid relationships between users
            relationships = manager.get_valid_relationships("user", "user")
        """
        pass
    
    @abstractmethod
    def validate_relationship(
        self,
        source_type: str,
        relationship_type: str,
        target_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Validate a relationship instance.
        
        Args:
            source_type: Type of source entity
            relationship_type: Type of relationship
            target_type: Type of target entity
            metadata: Optional relationship metadata
            
        Returns:
            True if valid, False otherwise
            
        Example:
            # Validate a follow relationship
            metadata = {"since": "2024-01-20T12:00:00Z"}
            is_valid = manager.validate_relationship(
                "user", "follows", "user", metadata
            )
        """
        pass
    
    @abstractmethod
    def update_schema(
        self,
        entity_type: str,
        schema_update: Dict[str, Any]
    ) -> None:
        """Update schema for an entity type.
        
        Args:
            entity_type: Type to update schema for
            schema_update: New/updated schema properties
            
        Example:
            # Add new property to user schema
            manager.update_schema("user", {
                "properties": {
                    "avatar_url": {
                        "type": "string",
                        "format": "uri"
                    }
                }
            })
        """
        pass 