"""Unit tests for the base agent implementation."""

import unittest
from unittest.mock import patch, MagicMock
from requests.exceptions import ConnectionError, Timeout
from src.agent.base_agent import BaseAgent
from src.utils.exceptions import (
    ConfigError, APIError, APIConnectionError,
    APIResponseError, APIAuthenticationError
)
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager

class TestBaseAgent(unittest.TestCase):
    """Test cases for BaseAgent class."""
    
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
        
        # Create agent
        with patch('src.agent.base_agent.load_config', return_value=self.mock_config):
            self.agent = BaseAgent(
                config_path="config.json",
                prompt_folder="prompts",
                db_interface=self.mock_db,
                ontology_manager=self.mock_ontology,
                role="curator"
            )
    
    def test_initialization(self):
        """Test agent initialization with valid config."""
        self.assertEqual(self.agent.config, self.mock_config)
        self.assertIsNotNone(self.agent.db_tools)
        self.assertEqual(self.agent.db_tools.role, "curator")
    
    def test_initialization_missing_config(self):
        """Test initialization with missing config."""
        with patch('src.agent.base_agent.load_config', return_value={"llm": {}}):
            with self.assertRaises(ConfigError):
                BaseAgent(
                    config_path="config.json",
                    prompt_folder="prompts",
                    db_interface=self.mock_db,
                    ontology_manager=self.mock_ontology,
                    role="curator"
                )
    
    def test_tool_registration(self):
        """Test registering and accessing tools."""
        test_tool = MagicMock()
        test_schema = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
        
        self.agent.register_tool("test_tool", test_tool, test_schema)
        
        self.assertIn("test_tool", self.agent.available_tools)
        self.assertEqual(self.agent.available_tools["test_tool"], test_tool)
        self.assertIn(test_schema, self.agent.tool_schemas)
    
    def test_prompt_loading(self):
        """Test loading and rendering prompts."""
        test_context = {"test": "value"}
        mock_template = MagicMock()
        mock_template.render.return_value = "rendered prompt"
        
        with patch.object(self.agent.env, 'get_template', return_value=mock_template) as mock_get:
            result = self.agent.load_prompt("test_prompt", test_context)
            
            mock_get.assert_called_once_with("test_prompt.txt")
            mock_template.render.assert_called_once_with(**test_context)
            self.assertEqual(result, "rendered prompt")
    
    @patch('requests.post')
    def test_llm_call_success(self, mock_post):
        """Test successful LLM API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_post.return_value = mock_response
        
        response = self.agent.call_llm("test prompt")
        self.assertEqual(response, "test response")
        
        # Verify request
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["headers"]["Authorization"], f"Bearer {self.mock_config['llm']['api_key']}")
        self.assertEqual(call_args["json"]["model"], self.mock_config["llm"]["model"])
        self.assertEqual(call_args["json"]["messages"][0]["content"], "test prompt")
    
    @patch('requests.post')
    def test_llm_call_retry(self, mock_post):
        """Test retry on connection failure."""
        mock_post.side_effect = [
            ConnectionError("Network error"),
            MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "test response"}}]}
            )
        ]
        
        with patch('time.sleep'):  # Don't actually sleep in tests
            response = self.agent.call_llm("test prompt")
            self.assertEqual(response, "test response")
            self.assertEqual(mock_post.call_count, 2)
    
    @patch('requests.post')
    def test_llm_call_auth_error(self, mock_post):
        """Test handling of authentication errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        with self.assertRaises(APIAuthenticationError):
            self.agent.call_llm("test prompt")
    
    @patch('requests.post')
    def test_llm_call_with_tools(self, mock_post):
        """Test LLM call with available tools."""
        # Create a fresh agent without database tools
        with patch('src.agent.base_agent.load_config', return_value=self.mock_config):
            agent = BaseAgent(
                config_path="config.json",
                prompt_folder="prompts",
                db_interface=self.mock_db,
                ontology_manager=self.mock_ontology,
                role="curator"
            )
        
        # Register a single test tool
        agent.register_tool(
            "test_tool",
            lambda: None,
            {"name": "test_tool", "description": "test", "parameters": {}}
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_post.return_value = mock_response
        
        response = agent.call_llm("test prompt")
        
        # Verify tools were included
        call_args = mock_post.call_args[1]
        self.assertIn("tools", call_args["json"])
        
        # Count tools with our test tool name
        test_tools = [
            tool for tool in call_args["json"]["tools"]
            if tool["function"]["name"] == "test_tool"
        ]
        self.assertEqual(len(test_tools), 1, "Should find exactly one test tool")
    
    def test_execute_not_implemented(self):
        """Test that execute() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.agent.execute()

if __name__ == '__main__':
    unittest.main() 