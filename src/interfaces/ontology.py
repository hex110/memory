"""Interface definition for ontology management."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any

class OntologyInterface(ABC):
    """Interface for managing a flexible ontology system.
    
    This interface defines a generic contract for ontology management.
    It treats the ontology as a collection of entities and their relationships,
    without imposing strict schema requirements. This allows for:
    - Dynamic schema evolution
    - Custom entity types
    - Flexible relationship definitions
    - Schema validation rules
    """

    @abstractmethod
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Gets an entity by its type and ID.
        
        Args:
            entity_type: The type of entity (e.g., 'concept', 'rule', 'tag')
            entity_id: The identifier of the entity
            
        Returns:
            Dict[str, Any]: Entity data, structure depends on entity type
                           Returns empty dict if not found
        """
        pass

    @abstractmethod
    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Gets all entities of a specific type.
        
        Args:
            entity_type: The type of entities to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of entities of the specified type
        """
        pass

    @abstractmethod
    def add_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """Adds a new entity.
        
        Args:
            entity_type: The type of entity to add
            entity_id: The identifier for the new entity
            data: The entity data
            
        Raises:
            ValueError: If entity data is invalid according to type's schema
        """
        pass

    @abstractmethod
    def update_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """Updates an existing entity.
        
        Args:
            entity_type: The type of entity to update
            entity_id: The identifier of the entity
            data: New entity data
            
        Raises:
            ValueError: If entity doesn't exist or data is invalid
        """
        pass

    @abstractmethod
    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Gets the schema definition for an entity type.
        
        Args:
            entity_type: The type to get schema for
            
        Returns:
            Dict[str, Any]: Schema definition for the entity type
                           Returns empty dict if type not found
        """
        pass

    @abstractmethod
    def update_schema(self, entity_type: str, schema: Dict[str, Any]) -> None:
        """Updates the schema for an entity type.
        
        Args:
            entity_type: The type to update schema for
            schema: New schema definition
            
        Raises:
            ValueError: If schema is invalid
        """
        pass 