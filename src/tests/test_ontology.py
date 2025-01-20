import unittest
from typing import Dict, Any
from src.ontology.ontology_manager import OntologyManager

# Example initial schema with flexible entity types
INITIAL_SCHEMA = {
    "schemas": {
        "concept": {
            "required_fields": ["description"],
            "optional_fields": ["examples", "metadata"]
        },
        "relationship": {
            "required_fields": ["source_type", "target_type", "description"],
            "optional_fields": ["metadata", "constraints"]
        },
        "rule": {
            "required_fields": ["condition", "action"],
            "optional_fields": ["priority", "metadata"]
        }
    }
}

class TestOntologyManager(unittest.TestCase):
    def setUp(self):
        self.ontology = OntologyManager(INITIAL_SCHEMA)

    def test_get_schema(self):
        """Test retrieving schema for an entity type."""
        schema = self.ontology.get_schema("concept")
        self.assertIn("required_fields", schema)
        self.assertIn("description", schema["required_fields"])

    def test_update_schema(self):
        """Test updating schema for an entity type."""
        new_schema = {
            "required_fields": ["name", "description"],
            "optional_fields": ["metadata"]
        }
        self.ontology.update_schema("person", new_schema)
        retrieved = self.ontology.get_schema("person")
        self.assertEqual(retrieved, new_schema)

    def test_add_and_get_entity(self):
        """Test adding and retrieving an entity."""
        user_data = {
            "description": "A system administrator",
            "metadata": {"access_level": "admin"}
        }
        self.ontology.add_entity("concept", "admin_user", user_data)
        retrieved = self.ontology.get_entity("concept", "admin_user")
        self.assertEqual(retrieved, user_data)

    def test_get_entities(self):
        """Test retrieving all entities of a type."""
        # Add multiple entities
        entities = {
            "user": {"description": "Basic user"},
            "admin": {"description": "Administrator"},
            "guest": {"description": "Guest user"}
        }
        for entity_id, data in entities.items():
            self.ontology.add_entity("concept", entity_id, data)

        retrieved = self.ontology.get_entities("concept")
        self.assertEqual(len(retrieved), len(entities))
        for entity in retrieved:
            self.assertIn("description", entity)

    def test_update_entity(self):
        """Test updating an entity."""
        # Create initial entity
        initial_data = {"description": "Initial description"}
        self.ontology.add_entity("concept", "test_entity", initial_data)

        # Update it
        update_data = {"description": "Updated description"}
        self.ontology.update_entity("concept", "test_entity", update_data)

        # Verify update
        retrieved = self.ontology.get_entity("concept", "test_entity")
        self.assertEqual(retrieved["description"], "Updated description")

    def test_schema_validation(self):
        """Test that schema validation works."""
        # Should fail without required field
        invalid_data = {"metadata": {"some": "data"}}
        with self.assertRaises(ValueError):
            self.ontology.add_entity("concept", "invalid", invalid_data)

        # Should succeed with required field
        valid_data = {"description": "Valid entity", "metadata": {"some": "data"}}
        self.ontology.add_entity("concept", "valid", valid_data)
        retrieved = self.ontology.get_entity("concept", "valid")
        self.assertEqual(retrieved, valid_data)

    def test_nonexistent_entity_type(self):
        """Test handling of nonexistent entity types."""
        with self.assertRaises(ValueError):
            self.ontology.add_entity("nonexistent_type", "test", {"some": "data"})

    def test_entity_not_found(self):
        """Test handling of nonexistent entities."""
        result = self.ontology.get_entity("concept", "nonexistent")
        self.assertEqual(result, {})

    def test_complex_entity(self):
        """Test handling of complex entity structures."""
        complex_data = {
            "description": "Complex entity",
            "metadata": {
                "tags": ["test", "complex"],
                "nested": {
                    "field1": "value1",
                    "field2": ["a", "b", "c"]
                }
            },
            "examples": ["example1", "example2"]
        }
        self.ontology.add_entity("concept", "complex", complex_data)
        retrieved = self.ontology.get_entity("concept", "complex")
        self.assertEqual(retrieved, complex_data)


if __name__ == '__main__':
    unittest.main()
