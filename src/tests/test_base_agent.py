"""Unit tests for the base agent implementation."""

import unittest
from unittest.mock import patch, MagicMock, call
from requests.exceptions import ConnectionError, Timeout
from src.agent.base_agent import BaseAgent
from src.utils.exceptions import (
    ConfigError, APIError, APIConnectionError,
    APIResponseError, APIAuthenticationError
)

class TestBaseAgent(unittest.TestCase):
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
        self.agent = BaseAgent(
            config_path="config.json",
            prompt_folder="prompts",
            timeout=5,
            max_retries=2  # Increased to 2 for better retry testing
        )

    def test_initialization_with_overrides(self):
        """Test agent initialization with parameter overrides."""
        with patch('src.agent.base_agent.load_config') as mock_load:
            mock_load.return_value = self.mock_config
            agent = BaseAgent(
                api_key="override-key",
                model="override-model",
                base_url="override-url"
            )
            self.assertEqual(agent.api_key, "override-key")
            self.assertEqual(agent.model, "override-model")
            self.assertEqual(agent.base_url, "override-url")

    def test_initialization_missing_config(self):
        """Test agent initialization with missing configuration."""
        with patch('src.agent.base_agent.load_config') as mock_load:
            mock_load.return_value = {}
            with self.assertRaises(ConfigError):
                BaseAgent()

    def test_load_prompt_success(self):
        """Test successful prompt loading and rendering."""
        template = MagicMock()
        template.render.return_value = "Rendered Prompt"
        context = {"user_name": "Alice"}
        
        with patch.object(self.agent.env, 'get_template', return_value=template) as mock_get:
            prompt = self.agent.load_prompt("example_prompt", context)
            
            mock_get.assert_called_once_with("example_prompt.txt")
            template.render.assert_called_once_with(context)
            self.assertEqual(prompt, "Rendered Prompt")

    def test_load_prompt_failure(self):
        """Test prompt loading failure."""
        with patch.object(self.agent.env, 'get_template', side_effect=Exception("Template error")):
            with self.assertRaises(Exception):
                self.agent.load_prompt("missing_prompt", {})

    def test_call_llm_success(self):
        """Test successful LLM API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is a test response."
                }
            }],
            "usage": {
                "total_tokens": 10
            }
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            response = self.agent.call_llm(
                "Test prompt",
                temperature=0.5,
                system_prompt="System instruction"
            )
            
            self.assertEqual(response, "This is a test response.")
            mock_post.assert_called_once()
            
            # Verify request details
            call_args = mock_post.call_args
            self.assertEqual(call_args[0][0], self.agent.base_url)
            headers = call_args[1]['headers']
            self.assertEqual(headers['Authorization'], f"Bearer {self.agent.api_key}")
            data = call_args[1]['data']
            self.assertIn('"temperature": 0.5', data)
            self.assertIn('"model": "test-model"', data)

    def test_call_llm_connection_error(self):
        """Test handling of connection errors with retry."""
        with patch('requests.post') as mock_post, \
             patch('time.sleep') as mock_sleep:  # Mock sleep to speed up tests
            
            mock_post.side_effect = [ConnectionError("Network error"), ConnectionError("Still failed")]
            
            with self.assertRaises(APIConnectionError) as cm:
                self.agent.call_llm("Test prompt")
            
            self.assertEqual(str(cm.exception), "Connection error: Network error")
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_once_with(1)  # First retry delay

    def test_call_llm_authentication_error(self):
        """Test handling of authentication errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        
        with patch('requests.post', return_value=mock_response):
            with self.assertRaises(APIAuthenticationError) as cm:
                self.agent.call_llm("Test prompt")
            
            self.assertEqual(cm.exception.status_code, 401)
            self.assertEqual(cm.exception.response, "Invalid API key")

    def test_call_llm_invalid_response(self):
        """Test handling of invalid API responses."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "format"}
        
        with patch('requests.post', return_value=mock_response):
            with self.assertRaises(APIResponseError) as cm:
                self.agent.call_llm("Test prompt")
            
            self.assertIn("Invalid response format", str(cm.exception))

    def test_call_llm_retry_success(self):
        """Test successful retry after initial failure."""
        fail_response = ConnectionError("Network error")
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Success after retry"
                }
            }]
        }
        
        with patch('requests.post') as mock_post, \
             patch('time.sleep') as mock_sleep:  # Mock sleep to speed up tests
            
            mock_post.side_effect = [fail_response, success_response]
            response = self.agent.call_llm("Test prompt")
            
            self.assertEqual(response, "Success after retry")
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_once_with(1)  # Check retry delay

    def test_parse_response(self):
        """Test basic response parsing."""
        response = "Test response text."
        parsed = self.agent.parse_response(response)
        self.assertEqual(parsed, response)

    def test_execute_not_implemented(self):
        """Test that execute() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.agent.execute()

if __name__ == '__main__':
    unittest.main() 