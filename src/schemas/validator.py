"""Schema validation utilities.

This module provides validation for both database and ontology schemas.
It ensures that:
1. Schemas follow the correct format
2. Data matches schema definitions
3. Relationships between schemas are valid
"""

from typing import Dict, Any, List, Optional
import jsonschema
from src.utils.exceptions import ValidationError
from src.schemas.definitions import get_database_schema, get_ontology_schema

class SchemaValidator:
    """Validates schemas and data against schemas."""
    
    def __init__(self):
        """Initialize the validator with base schemas."""
        self.database_schema = get_database_schema()
        self.ontology_schema = get_ontology_schema()
        
        # Meta-schema for validating database schema definitions
        self.database_meta_schema = {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "properties": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "format": {"type": "string"},
                            "minimum": {"type": "number"},
                            "maximum": {"type": "number"},
                            "default": {},
                        },
                        "required": ["type"]
                    }
                }
            },
            "required": ["description", "properties"]
        }
        
        # Meta-schema for validating ontology schema definitions
        self.ontology_meta_schema = {
            "type": "object",
            "properties": {
                "concepts": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"}
                        },
                        "required": ["description"]
                    }
                },
                "relationships": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "source_type": {"type": "string"},
                            "target_type": {"type": "string"}
                        },
                        "required": ["description", "source_type", "target_type"]
                    }
                },
                "data_types": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"}
                        },
                        "required": ["description"]
                    }
                }
            },
            "required": ["concepts", "relationships", "data_types"]
        }
    
    def validate_database_schema(self, schema: Dict[str, Any]) -> None:
        """Validate a database schema definition.
        
        Args:
            schema: The schema to validate
            
        Raises:
            ValidationError: If schema is invalid
        """
        try:
            jsonschema.validate(schema, self.database_meta_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Invalid database schema: {e.message}")
    
    def validate_ontology_schema(self, schema: Dict[str, Any]) -> None:
        """Validate an ontology schema definition.
        
        Args:
            schema: The schema to validate
            
        Raises:
            ValidationError: If schema is invalid
        """
        try:
            jsonschema.validate(schema, self.ontology_meta_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Invalid ontology schema: {e.message}")
    
    def validate_data(self, data: Dict[str, Any], schema: Dict[str, Any]) -> None:
        """Validate data against a schema.
        
        Args:
            data: The data to validate
            schema: The schema to validate against
            
        Raises:
            ValidationError: If data doesn't match schema
        """
        # Convert our schema format to JSON Schema format
        json_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for field, field_schema in schema["properties"].items():
            json_schema["properties"][field] = {
                "type": field_schema["type"]
            }
            
            # Add format if specified
            if "format" in field_schema:
                json_schema["properties"][field]["format"] = field_schema["format"]
            
            # Add numeric constraints if specified
            if "minimum" in field_schema:
                json_schema["properties"][field]["minimum"] = field_schema["minimum"]
            if "maximum" in field_schema:
                json_schema["properties"][field]["maximum"] = field_schema["maximum"]
            
            # Add field to required list if no default value
            if "default" not in field_schema:
                json_schema["required"].append(field)
        
        try:
            jsonschema.validate(data, json_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Invalid data: {e.message}")
    
    def validate_relationship(self, source_type: str, target_type: str, relationship_type: str) -> None:
        """Validate a relationship between entities.
        
        Args:
            source_type: Type of the source entity
            target_type: Type of the target entity
            relationship_type: Type of relationship
            
        Raises:
            ValidationError: If relationship is invalid
        """
        relationship = self.ontology_schema["relationships"].get(relationship_type)
        if not relationship:
            raise ValidationError(f"Unknown relationship type: {relationship_type}")
        
        if relationship["source_type"] != source_type:
            raise ValidationError(
                f"Invalid source type for relationship '{relationship_type}': "
                f"expected {relationship['source_type']}, got {source_type}"
            )
        
        if relationship["target_type"] != target_type:
            raise ValidationError(
                f"Invalid target type for relationship '{relationship_type}': "
                f"expected {relationship['target_type']}, got {target_type}"
            )
    
    def validate_schema_compatibility(self, database_schema: Dict[str, Any], 
                                   ontology_schema: Dict[str, Any]) -> None:
        """Validate that database and ontology schemas are compatible.
        
        Args:
            database_schema: The database schema
            ontology_schema: The ontology schema
            
        Raises:
            ValidationError: If schemas are incompatible
        """
        # Validate individual schemas first
        self.validate_database_schema(database_schema)
        self.validate_ontology_schema(ontology_schema)
        
        # Check that all concept types have corresponding database tables
        for concept in ontology_schema["concepts"]:
            if concept not in database_schema:
                raise ValidationError(
                    f"Concept '{concept}' in ontology has no corresponding database table"
                )
        
        # Check that relationship types reference valid concept types
        for rel_type, rel_schema in ontology_schema["relationships"].items():
            source_type = rel_schema["source_type"]
            target_type = rel_schema["target_type"]
            
            if source_type not in ontology_schema["concepts"]:
                raise ValidationError(
                    f"Relationship '{rel_type}' references unknown source type '{source_type}'"
                )
            
            if target_type not in ontology_schema["concepts"]:
                raise ValidationError(
                    f"Relationship '{rel_type}' references unknown target type '{target_type}'"
                ) 