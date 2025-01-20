from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

class OntologyManagerInterface(ABC):
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


class OntologyManager(OntologyManagerInterface):
    """Flexible implementation of the OntologyManager interface."""
    
    def __init__(self, initial_schema: Dict[str, Any]):
        """Initialize the OntologyManager with an initial schema.
        
        Args:
            initial_schema: Dictionary containing initial schema definitions
                          for different entity types
        """
        self.schemas = initial_schema.get("schemas", {})
        self.entities = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
        
        # Initialize entity storage for each type
        for entity_type in self.schemas:
            self.entities[entity_type] = {}

    def _validate_against_schema(self, entity_type: str, data: Dict[str, Any]) -> None:
        """Validates entity data against its schema.
        
        This is a basic implementation. In practice, you might want to use
        a schema validation library like jsonschema.
        """
        schema = self.schemas.get(entity_type, {})
        required_fields = schema.get("required_fields", [])
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' for entity type '{entity_type}'")

    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        return self.entities.get(entity_type, {}).get(entity_id, {})

    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        return list(self.entities.get(entity_type, {}).values())

    def add_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        if entity_type not in self.schemas:
            raise ValueError(f"Unknown entity type: {entity_type}")
            
        self._validate_against_schema(entity_type, data)
        
        if entity_type not in self.entities:
            self.entities[entity_type] = {}
        self.entities[entity_type][entity_id] = data

    def update_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        if entity_type not in self.schemas:
            raise ValueError(f"Unknown entity type: {entity_type}")
            
        if entity_id not in self.entities.get(entity_type, {}):
            raise ValueError(f"Entity {entity_id} of type {entity_type} does not exist")
            
        self._validate_against_schema(entity_type, data)
        self.entities[entity_type][entity_id].update(data)

    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        return self.schemas.get(entity_type, {})

    def update_schema(self, entity_type: str, schema: Dict[str, Any]) -> None:
        # Here you might want to add schema validation logic
        self.schemas[entity_type] = schema
        
        # Initialize entity storage if it's a new type
        if entity_type not in self.entities:
            self.entities[entity_type] = {}
