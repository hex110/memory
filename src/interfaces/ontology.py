"""Interface definition for ontology management.

This module defines the interface for managing the system's semantic schema (ontology).
The ontology system primarily handles:

1. Schema Validation:
   - Validate entity data against schemas
   - Track schema definitions
   - Ensure data consistency
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class OntologyInterface(ABC):
    """Interface for ontology management."""
    
    @abstractmethod
    def __init__(self, initial_schema: Optional[Dict[str, Any]] = None):
        """Initialize the ontology manager.
        
        Args:
            initial_schema: Initial schema definitions
        """
        pass
    
    @abstractmethod
    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Get schema for an entity type.
        
        Args:
            entity_type: Type of entity
            
        Returns:
            Schema definition
        """
        pass
    
    @abstractmethod
    async def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity against its schema.
        
        Args:
            entity_type: Type of entity
            data: Entity data
            
        Returns:
            True if valid
        """
        pass
    
    @property
    @abstractmethod
    def schemas(self) -> Dict[str, Any]:
        """Get all schema definitions.
        
        Returns:
            All entity schemas
        """
        pass