"""Ontology management implementation.

Provides schema validation and tracking for database entities.
Uses the schema definitions from definitions.py as the source of truth.
"""

from typing import Dict, Any, Optional
from jsonschema import validate as json_validate
from src.interfaces.ontology import OntologyInterface
from src.utils.exceptions import ValidationError
from src.schemas.definitions import get_ontology_schema

class OntologyManager(OntologyInterface):
    """Schema validator and tracker for the database system."""
    
    def __init__(self):
        """Initialize basic configuration."""
        self._schemas = get_ontology_schema()
        
        # Validate the schema itself has the expected structure
        if not isinstance(self._schemas, dict):
            raise ValidationError("Schema must be a dictionary")
        if "concepts" not in self._schemas:
            raise ValidationError("Schema must have a 'concepts' section")
    
    @classmethod
    async def create(cls) -> 'OntologyManager':
        """Create and initialize a new ontology manager instance.
        
        Returns:
            Initialized ontology manager instance
        """
        return cls()
    
    @property
    def schemas(self) -> Dict[str, Any]:
        """Get all schema definitions."""
        return self._schemas
    
    def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Get schema for an entity type.
        
        Args:
            entity_type: Type of entity
            
        Returns:
            Schema definition for the entity type
            
        Raises:
            ValidationError: If entity type doesn't exist
        """
        if entity_type not in self._schemas.get("concepts", {}):
            raise ValidationError(f"Unknown entity type: {entity_type}")
        return self._schemas["concepts"][entity_type]
    
    async def validate_entity(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Validate an entity against its schema.
        
        Args:
            entity_type: Type of entity
            data: Entity data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            schema = self.get_schema(entity_type)
            
            # Build JSON schema for validation
            json_schema = {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": [
                    field for field, definition in schema.get("properties", {}).items()
                    if not definition.get("nullable", True) and "default" not in definition
                ]
            }
            
            # Validate against JSON schema
            json_validate(instance=data, schema=json_schema)
            return True
            
        except Exception:
            return False