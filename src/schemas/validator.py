"""Schema validation utilities.

This module provides validation for both database and ontology schemas.
It ensures that:
1. Schemas follow the correct format
2. Data matches schema definitions
3. Relationships between schemas are valid
4. Types are properly converted and validated
"""

from datetime import datetime
import uuid
import json
from typing import Dict, Any, List, Optional, Union
import jsonschema
from src.utils.exceptions import ValidationError
from src.schemas.definitions import get_database_schema, get_ontology_schema

class SchemaValidator:
    """Validates schemas and data against schemas."""
    
    # PostgreSQL type definitions
    PG_TYPES = {
        "text": str,
        "integer": int,
        "numeric": float,
        "boolean": bool,
        "jsonb": (dict, list),
        "uuid": uuid.UUID,
        "timestamp with time zone": datetime,
        "bytea": bytes
    }
    
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
                            "description": {"type": "string"},
                            "nullable": {"type": "boolean"},
                            "primary_key": {"type": "boolean"},
                            "default": {},
                            "enum": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "foreign_key": {
                                "type": "object",
                                "properties": {
                                    "table": {"type": "string"},
                                    "column": {"type": "string"}
                                },
                                "required": ["table", "column"]
                            },
                            "minimum": {"type": "number"},
                            "maximum": {"type": "number"},
                            "pattern": {"type": "string"},
                            "maxLength": {"type": "integer"}
                        },
                        "required": ["type", "description"]
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

    def _convert_type(self, value: Any, field_type: str) -> Any:
        """Convert a value to the appropriate Python type.
        
        Args:
            value: Value to convert
            field_type: Target type name
            
        Returns:
            Converted value
            
        Raises:
            ValidationError: If conversion fails
        """
        if value is None:
            return None
            
        # Handle array types
        if field_type.endswith("[]"):
            base_type = field_type[:-2]
            if not isinstance(value, list):
                value = [value]
            return [self._convert_type(item, base_type) for item in value]
            
        pg_type = self.PG_TYPES.get(field_type)
        if not pg_type:
            return value
            
        try:
            if field_type == "uuid":
                return uuid.UUID(str(value))
            elif field_type == "timestamp with time zone":
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
                return value
            elif field_type == "jsonb":
                if isinstance(value, str):
                    return json.loads(value)
                return value
            elif isinstance(pg_type, tuple):
                if not isinstance(value, pg_type):
                    raise ValidationError(f"Expected {pg_type}, got {type(value)}")
                return value
            else:
                return pg_type(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Failed to convert {value} to {field_type}: {str(e)}")

    def validate_database_schema(self, schema: Dict[str, Any]) -> None:
        """Validate a database schema definition.
        
        Args:
            schema: The schema to validate
            
        Raises:
            ValidationError: If schema is invalid
        """
        try:
            jsonschema.validate(schema, self.database_meta_schema)
            
            # Additional validation for field types
            for field_def in schema["properties"].values():
                field_type = field_def["type"]
                if field_type.endswith("[]"):
                    base_type = field_type[:-2]
                    if base_type not in self.PG_TYPES:
                        raise ValidationError(f"Invalid array base type: {base_type}")
                elif field_type not in self.PG_TYPES:
                    raise ValidationError(f"Invalid field type: {field_type}")
                    
                # Validate foreign keys
                if "foreign_key" in field_def:
                    ref_table = field_def["foreign_key"]["table"]
                    ref_col = field_def["foreign_key"]["column"]
                    if ref_table not in self.database_schema:
                        raise ValidationError(f"Foreign key references unknown table: {ref_table}")
                    if ref_col not in self.database_schema[ref_table]["properties"]:
                        raise ValidationError(f"Foreign key references unknown column: {ref_col}")
                        
                # Validate enum values
                if "enum" in field_def and not isinstance(field_def["enum"], list):
                    raise ValidationError(f"Enum values must be a list")
                    
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
            
            # Validate relationship references
            for rel in schema["relationships"].values():
                if rel["source_type"] not in schema["concepts"]:
                    raise ValidationError(f"Unknown source type in relationship: {rel['source_type']}")
                if rel["target_type"] not in schema["concepts"]:
                    raise ValidationError(f"Unknown target type in relationship: {rel['target_type']}")
                    
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
        try:
            # Build JSON Schema for validation
            json_schema = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            # Process each field
            for field_name, field_def in schema["properties"].items():
                # Skip if field is not in data and has a default value
                if field_name not in data and "default" in field_def:
                    continue
                    
                # Add to required fields if not nullable and no default
                if not field_def.get("nullable", True) and "default" not in field_def:
                    json_schema["required"].append(field_name)
                
                # Build field schema
                field_schema: Dict[str, Any] = {}
                
                # Handle different types
                field_type = field_def["type"]
                if field_type.endswith("[]"):
                    field_schema["type"] = "array"
                    field_schema["items"] = {"type": "string"}  # Base validation, detailed check later
                elif field_type == "jsonb":
                    field_schema["type"] = ["object", "array"]
                else:
                    field_schema["type"] = ["string", "number", "boolean", "null"]
                
                # Add constraints
                if "enum" in field_def:
                    field_schema["enum"] = field_def["enum"]
                if "pattern" in field_def:
                    field_schema["pattern"] = field_def["pattern"]
                if "minimum" in field_def:
                    field_schema["minimum"] = field_def["minimum"]
                if "maximum" in field_def:
                    field_schema["maximum"] = field_def["maximum"]
                if "maxLength" in field_def:
                    field_schema["maxLength"] = field_def["maxLength"]
                
                json_schema["properties"][field_name] = field_schema
            
            # Validate basic structure
            jsonschema.validate(data, json_schema)
            
            # Detailed type validation and conversion
            for field_name, field_def in schema["properties"].items():
                if field_name in data:
                    # Convert and validate type
                    converted_value = self._convert_type(data[field_name], field_def["type"])
                    data[field_name] = converted_value
                    
                    # Check foreign key constraints
                    if "foreign_key" in field_def:
                        ref = field_def["foreign_key"]
                        ref_table = self.database_schema[ref["table"]]
                        ref_field = ref_table["properties"][ref["column"]]
                        self._convert_type(converted_value, ref_field["type"])
            
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Invalid data: {e.message}")
        except Exception as e:
            raise ValidationError(f"Validation failed: {str(e)}")
    
    def validate_schema_compatibility(self, database_schema: Dict[str, Any], 
                                   ontology_schema: Dict[str, Any]) -> None:
        """Validate that database and ontology schemas are compatible.
        
        Args:
            database_schema: The database schema
            ontology_schema: The ontology schema
            
        Raises:
            ValidationError: If schemas are incompatible
        """
        try:
            # Validate individual schemas first
            self.validate_database_schema(database_schema)
            self.validate_ontology_schema(ontology_schema)
            
            # Check concepts have corresponding tables
            for concept in ontology_schema["concepts"]:
                if concept not in database_schema:
                    raise ValidationError(
                        f"Concept '{concept}' has no corresponding database table"
                    )
                    
                # Check required fields
                table_schema = database_schema[concept]
                for field_name, field_def in table_schema["properties"].items():
                    if not field_def.get("nullable", True) and "default" not in field_def:
                        raise ValidationError(
                            f"Non-nullable field '{field_name}' in '{concept}' "
                            "must have a default value"
                        )
            
            # Check relationship validity
            for rel_type, rel_def in ontology_schema["relationships"].items():
                source_type = rel_def["source_type"]
                target_type = rel_def["target_type"]
                
                # Check tables exist
                if source_type not in database_schema:
                    raise ValidationError(
                        f"Relationship source '{source_type}' has no database table"
                    )
                if target_type not in database_schema:
                    raise ValidationError(
                        f"Relationship target '{target_type}' has no database table"
                    )
                    
                # Check foreign key constraints exist
                source_table = database_schema[source_type]
                has_foreign_key = False
                for field_def in source_table["properties"].values():
                    if "foreign_key" in field_def:
                        if (field_def["foreign_key"]["table"] == target_type and
                            field_def["foreign_key"]["column"] == "id"):
                            has_foreign_key = True
                            break
                
                if not has_foreign_key:
                    raise ValidationError(
                        f"Relationship '{rel_type}' has no corresponding foreign key"
                    )
                    
        except Exception as e:
            raise ValidationError(f"Schema compatibility validation failed: {str(e)}")