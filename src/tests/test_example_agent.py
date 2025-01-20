"""Unit tests for the example schema explainer agent."""

import unittest
from unittest.mock import patch, MagicMock
from src.agent.example_agent import SchemaExplainerAgent

class TestSchemaExplainerAgent(unittest.TestCase):
    @patch('src.agent.base_agent.load_config')
    @patch('src.agent.base_agent.Environment')
    def setUp(self, mock_env, mock_load_config):
        """Set up test fixtures before each test method."""
        self.mock_config = {
            "llm": {
                "api_key": "test-api-key",
                "model": "test-model",
                "base_url": "https://test.api/v1/chat"
            }
        }
        mock_load_config.return_value = self.mock_config
        self.agent = SchemaExplainerAgent(
            config_path="config.json",
            prompt_folder="prompts"
        )

    def test_format_schema_methods(self):
        """Test the formatting of schema methods."""
        formatted = self.agent.format_schema_methods()
        
        # Check that both sections are present
        self.assertIn("Concepts Methods:", formatted)
        self.assertIn("Relationship Methods:", formatted)
        
        # Check for specific method signatures
        self.assertIn("def get_user_details()", formatted)
        self.assertIn("def handle_related_to_relationship(", formatted)
        
        # Check for docstrings
        self.assertIn("Get details about the user concept", formatted)
        self.assertIn("Handle the related_to relationship", formatted)

    def test_execute_flow(self):
        """Test the complete execution flow."""
        # Mock the prompt loading
        mock_prompt = "Explain these methods: {{ methods }}"
        with patch.object(self.agent, 'load_prompt', return_value=mock_prompt) as mock_load:
            # Mock the LLM call
            mock_response = "Here's the explanation of the methods..."
            with patch.object(self.agent, 'call_llm', return_value=mock_response) as mock_call:
                result = self.agent.execute()
                
                # Verify the flow
                mock_load.assert_called_once()
                args = mock_load.call_args.args
                self.assertEqual(args[0], "explain_methods")  # First arg is prompt name
                self.assertIn("methods", args[1])  # Second arg is the context dict
                
                mock_call.assert_called_once()
                call_args = mock_call.call_args
                self.assertEqual(call_args[0][0], mock_prompt)  # First positional arg is prompt
                self.assertEqual(call_args[1]["temperature"], 0.7)
                self.assertIsNotNone(call_args[1]["system_prompt"])
                
                # Check result
                self.assertEqual(result, mock_response)

    def test_parse_response(self):
        """Test response parsing."""
        test_response = "Test explanation"
        parsed = self.agent.parse_response(test_response)
        self.assertEqual(parsed, test_response)

if __name__ == '__main__':
    unittest.main() 