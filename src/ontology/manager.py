"""Ontology management implementation."""

from typing import Dict, List, Any, Set, Optional
from src.interfaces.ontology import OntologyInterface

class OntologyManager(OntologyInterface):
    """Flexible implementation of the OntologyInterface."""
    
    def __init__(self, initial_schema: Optional[Dict[str, Any]] = None):
        """Initialize the OntologyManager with an initial schema.
        
        Args:
            initial_schema: Dictionary containing initial schema definitions
                         for different entity types
        """
        self._schemas = initial_schema or {}
        self.entities = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
        
        # Initialize entity storage for each type
        for entity_type in self._schemas.get("concepts", {}):
            self.entities[entity_type] = {}
    
    @property
    def schemas(self) -> Dict[str, Any]:
        """Get all schema definitions."""
        return self._schemas
    
    def _validate_against_schema(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validates entity data against its schema.
        
        This is a basic implementation. In practice, you might want to use
        a schema validation library like jsonschema.
        
        Args:
            entity_type: Type of entity to validate
            data: Entity data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if entity_type not in self._schemas.get("concepts", {}):
            return False
            
        schema = self._schemas["concepts"][entity_type]
        properties = schema.get("properties", {})
        
        # Check all required properties exist
        for prop_name, prop_def in properties.items():
            if prop_def.get("required", False) and prop_name not in data:
                return False
        
        return True
    
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by type and ID."""
        return self.entities.get(entity_type, {}).get(entity_id, {})
    
    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a type."""
        return list(self.entities.get(entity_type, {}).values())
    
    def add_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """Add a new entity."""
        if not self.validate_entity(entity_type, data):
            raise ValueError(f"Invalid data for entity type: {entity_type}")
            
        if entity_type not in self.entities:
            self.entities[entity_type] = {}
        self.entities[entity_type][entity_id] = data
    
    def update_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """Update an existing entity."""
        if not self.validate_entity(entity_type, data):
            raise ValueError(f"Invalid data for entity type: {entity_type}")
            
        if entity_id not in self.entities.get(entity_type, {}):
            raise ValueError(f"Entity {entity_id} of type {entity_type} does not exist")
            
        self.entities[entity_type][entity_id].update(data)
    
    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Get schema for an entity type."""
        return self._schemas.get("concepts", {}).get(entity_type, {})
    
    def update_schema(self, entity_type: str, schema_update: Dict[str, Any]) -> None:
        """Update schema for an entity type."""
        if "concepts" not in self._schemas:
            self._schemas["concepts"] = {}
        
        # Update existing schema or add new one
        if entity_type in self._schemas["concepts"]:
            self._schemas["concepts"][entity_type].update(schema_update)
        else:
            self._schemas["concepts"][entity_type] = schema_update
            self.entities[entity_type] = {}
    
    def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity against its schema."""
        return self._validate_against_schema(entity_type, data)
    
    def can_relate(self, source_type: str, relationship_type: str, target_type: str) -> bool:
        """Check if two types can have a relationship."""
        relationships = self._schemas.get("relationships", {})
        if relationship_type not in relationships:
            return False
            
        rel_def = relationships[relationship_type]
        return (
            rel_def.get("source_type") == source_type and
            rel_def.get("target_type") == target_type
        )
    
    def get_valid_relationships(self, source_type: str, target_type: str) -> Set[str]:
        """Get valid relationship types between entities."""
        valid_relationships = set()
        
        for rel_name, rel_def in self._schemas.get("relationships", {}).items():
            if (rel_def.get("source_type") == source_type and 
                rel_def.get("target_type") == target_type):
                valid_relationships.add(rel_name)
        
        return valid_relationships
    
    def validate_relationship(
        self,
        source_type: str,
        relationship_type: str,
        target_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Validate a relationship instance."""
        # First check if the relationship type is valid
        if not self.can_relate(source_type, relationship_type, target_type):
            return False
        
        # If there's metadata, validate it against the relationship schema
        if metadata:
            rel_schema = self._schemas.get("relationships", {}).get(relationship_type, {})
            properties = rel_schema.get("properties", {})
            
            # Check required properties
            for prop_name, prop_def in properties.items():
                if prop_def.get("required", False) and prop_name not in metadata:
                    return False
        
        return True
