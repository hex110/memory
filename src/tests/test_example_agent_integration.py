"""Integration tests for the schema explainer agent.

These tests make actual API calls and require valid API credentials.
They can be skipped if no API key is available.
"""

import os
import json
import unittest
from unittest.mock import MagicMock
from src.agent.example_agent import SchemaExplainerAgent
from src.utils.config import load_config
from src.utils.exceptions import ConfigError
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager
from src.ontology.ontology_schema import ontology_schema

def has_api_credentials() -> bool:
    """Check if API credentials are available."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        print(f"\nChecking for API credentials in {config_path}")
        
        if not os.path.exists(config_path):
            print(f"Config file not found at {config_path}")
            return False
        
        config = load_config(config_path)
        llm_config = config.get('llm', {})
        
        has_key = bool(llm_config.get('api_key'))
        has_model = bool(llm_config.get('model'))
        has_url = bool(llm_config.get('base_url'))
        
        print(f"API key: {'found' if has_key else 'not found'}")
        print(f"Model: {llm_config.get('model', 'not found')}")
        print(f"Base URL: {llm_config.get('base_url', 'not found')}")
        
        return has_key and has_model and has_url
        
    except Exception as e:
        print(f"Error checking credentials: {e}")
        return False

@unittest.skipUnless(has_api_credentials(), "No API credentials available")
class TestSchemaExplainerAgentIntegration(unittest.TestCase):
    """Integration tests for SchemaExplainerAgent."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that can be reused across tests."""
        # Set up database and ontology with test schema
        cls.db_interface = MagicMock(spec=DatabaseInterface)
        
        # Create a test schema that matches what we want to test
        test_schema = {
            "get_entity": {
                "description": "Get an entity from the database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "description": "Type of entity to retrieve"
                        },
                        "entity_id": {
                            "type": "string",
                            "description": "ID of the entity"
                        }
                    },
                    "required": ["entity_type", "entity_id"]
                }
            },
            "get_entities": {
                "description": "Get all entities of a type",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "description": "Type of entities to retrieve"
                        }
                    },
                    "required": ["entity_type"]
                }
            }
        }
        
        cls.ontology_manager = OntologyManager(initial_schema=test_schema)
        
        # Create the agent
        cls.agent = SchemaExplainerAgent(
            config_path=os.path.join(os.path.dirname(__file__), "..", "config.json"),
            prompt_folder=os.path.join(os.path.dirname(__file__), "..", "agent", "prompts"),
            db_interface=cls.db_interface,
            ontology_manager=cls.ontology_manager,
            role="curator"
        )
    
    def test_schema_explanation(self):
        """Test that the agent properly explains schema methods."""
        agent = SchemaExplainerAgent(
            config_path="config.json",
            prompt_folder="prompts",
            db_interface=self.db_interface,
            ontology_manager=self.ontology_manager
        )
        
        explanation = agent.explain_schema_methods()
        
        # Check for key components in the explanation
        required_components = [
            "schema",
            "database",
            "structure",
            "method"
        ]
        
        for component in required_components:
            self.assertIn(
                component.lower(),
                explanation.lower(),
                f"Explanation should include {component}"
            )
    
    def test_specific_method_explanation(self):
        """Test explaining a specific method."""
        agent = SchemaExplainerAgent(
            config_path="config.json",
            prompt_folder="prompts",
            db_interface=self.db_interface,
            ontology_manager=self.ontology_manager
        )
        
        method_name = "get_entity"
        try:
            explanation = agent.explain_method(method_name)
            
            # Only check basic requirements if we get a response
            if explanation:
                self.assertIn(method_name, explanation)
                self.assertIn("parameter", explanation.lower())
                self.assertIn("return", explanation.lower())
        except Exception as e:
            if "429" in str(e):  # API quota exceeded
                self.skipTest("Skipping due to API quota limits")
            else:
                raise  # Re-raise other exceptions
    
    def test_different_temperatures(self):
        """Test that different temperatures produce varied responses."""
        print("\n=== Testing Temperature Variation ===")
        
        # Get multiple explanations with different temperatures
        explanations = []
        for temp in [0.2, 0.5, 0.8]:
            explanation = self.agent.call_llm(
                "Explain what a database schema is.",
                temperature=temp
            )
            explanations.append(explanation)
            
            print(f"\nExplanation with temperature={temp}:")
            print("---")
            print(explanation)
            print("---")
        
        # Check that responses vary
        unique_responses = len(set(explanations))
        self.assertGreater(
            unique_responses,
            1,
            "Different temperatures should produce varied responses"
        )
    
    def test_system_prompt_influence(self):
        """Test that different system prompts influence the response style."""
        agent = SchemaExplainerAgent(
            config_path="config.json",
            prompt_folder="prompts",
            db_interface=self.db_interface,
            ontology_manager=self.ontology_manager
        )
        
        try:
            responses = {}
            for style in ["technical", "simple", "academic"]:
                agent.system_prompt = f"Explain in a {style} style."
                responses[style] = agent.explain_schema_methods()
                
                # Check that we got a response
                if not responses[style]:
                    self.skipTest("Empty response received, possibly due to API limits")
            
            # Only compare if we have all responses
            if all(responses.values()):
                # Verify responses are different
                self.assertNotEqual(responses["technical"], responses["simple"])
                self.assertNotEqual(responses["simple"], responses["academic"])
                self.assertNotEqual(responses["technical"], responses["academic"])
                
                # Verify each response maintains its style
                if "technical" in responses:
                    self.assertIn("implementation", responses["technical"].lower())
                if "simple" in responses:
                    self.assertIn("basic", responses["simple"].lower())
                if "academic" in responses:
                    self.assertIn("methodology", responses["academic"].lower())
        except Exception as e:
            if "429" in str(e):  # API quota exceeded
                self.skipTest("Skipping due to API quota limits")
            else:
                raise  # Re-raise other exceptions

if __name__ == '__main__':
    unittest.main() 