"""Unit tests for the schema explainer agent."""

import unittest
from unittest.mock import patch, MagicMock
from src.agent.example_agent import SchemaExplainerAgent
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager

class TestSchemaExplainerAgent(unittest.TestCase):
    """Test cases for SchemaExplainerAgent class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config
        self.mock_config = {
            "llm": {
                "api_key": "test-api-key",
                "model": "test-model",
                "base_url": "https://test.api/v1/chat"
            }
        }
        
        # Mock database and ontology
        self.mock_db = MagicMock(spec=DatabaseInterface)
        self.mock_ontology = MagicMock(spec=OntologyManager)
        
        # Set up test schema
        self.test_schema = {
            "get_entity": {
                "description": "Get an entity by ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity ID"
                        }
                    }
                }
            },
            "update_entity": {
                "description": "Update an entity",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity ID"
                        },
                        "data": {
                            "type": "object",
                            "description": "The update data"
                        }
                    }
                }
            }
        }
        
        # Configure mocks
        self.mock_ontology.schemas = self.test_schema
        
        # Create agent
        with patch('src.agent.base_agent.load_config', return_value=self.mock_config):
            self.agent = SchemaExplainerAgent(
                config_path="config.json",
                prompt_folder="prompts",
                db_interface=self.mock_db,
                ontology_manager=self.mock_ontology,
                role="curator"
            )
    
    def test_format_schema_methods(self):
        """Test formatting of schema methods."""
        formatted = self.agent.format_schema_methods(self.test_schema)
        
        # Check basic structure
        self.assertIsInstance(formatted, str)
        self.assertGreater(len(formatted), 0)
        
        # Check method names are included
        self.assertIn("Method: get_entity", formatted)
        self.assertIn("Method: update_entity", formatted)
        
        # Check descriptions are included
        self.assertIn("Get an entity by ID", formatted)
        self.assertIn("Update an entity", formatted)
        
        # Check parameters are formatted
        self.assertIn("Parameters:", formatted)
        self.assertIn("entity_id", formatted)
        self.assertIn("The entity ID", formatted)
    
    def test_format_schema_methods_empty(self):
        """Test formatting with empty schema."""
        formatted = self.agent.format_schema_methods({})
        self.assertEqual(formatted, "")
    
    def test_format_schema_methods_missing_fields(self):
        """Test formatting with missing optional fields."""
        incomplete_schema = {
            "test_method": {
                # Missing description
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
        
        formatted = self.agent.format_schema_methods(incomplete_schema)
        
        self.assertIn("Method: test_method", formatted)
        self.assertIn("No description", formatted)
    
    def test_parse_response(self):
        """Test response parsing."""
        test_response = "Test explanation"
        parsed = self.agent.parse_response(test_response)
        self.assertEqual(parsed, test_response)  # Should return as-is

if __name__ == '__main__':
    unittest.main() 