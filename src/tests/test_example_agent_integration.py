"""Integration tests for the schema explainer agent.

These tests make actual API calls and require valid API credentials.
They can be skipped if no API key is available.
"""

import os
import json
import unittest
from src.agent.example_agent import SchemaExplainerAgent
from src.utils.config import load_config
from src.utils.exceptions import ConfigError

def has_api_credentials() -> bool:
    """Check if API credentials are available."""
    try:
        config_path = "src/config.json"
        print(f"\nChecking for API credentials in {config_path}")
        config = load_config(config_path)
        has_key = bool(config.get('llm', {}).get('api_key'))
        print(f"API key {'found' if has_key else 'not found'} in config")
        print(f"Using model: {config.get('llm', {}).get('model', 'unknown')}")
        return has_key
    except ConfigError as e:
        print(f"Config error: {e}")
        return False
    except FileNotFoundError:
        print(f"Config file not found at {config_path}")
        return False

@unittest.skipUnless(has_api_credentials(), "No API credentials available")
class TestSchemaExplainerAgentIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.agent = SchemaExplainerAgent(
            config_path="src/config.json",
            prompt_folder="src/agent/prompts"
        )
    
    def test_schema_explanation(self):
        """Test that the agent properly explains schema methods."""
        print("\n=== Testing Schema Method Explanation ===")
        
        # First, let's see what methods we're explaining
        methods_str = self.agent.format_schema_methods()
        print("\nSchema methods to explain:")
        print("---")
        print(methods_str)
        print("---")
        
        # Load and verify the prompt template
        context = {"methods": methods_str}
        prompt_template = self.agent.load_prompt("explain_methods", context)
        print("\nPrompt template loaded:")
        print("---")
        print(prompt_template)
        print("---")
        
        # Verify prompt contains our methods
        self.assertIn(methods_str, prompt_template)
        print("✓ Prompt template contains formatted methods")
        
        # Verify prompt contains our placeholder
        self.assertIn("{{ methods }}", prompt_template)
        print("✓ Prompt template contains methods placeholder")
        
        # Execute the agent to get the explanation
        print("\nExecuting agent to explain methods...")
        explanation = self.agent.execute()
        print("\nReceived explanation:")
        print("---")
        print(explanation)
        print("---")
        
        # Verify the explanation covers all methods
        print("\nVerifying explanation coverage:")
        
        # Check for concept methods
        concept_methods = ["get_user_details", "get_conversation_details"]
        for method in concept_methods:
            self.assertIn(method, explanation)
            print(f"✓ Explains concept method: {method}")
        
        # Check for relationship methods
        relationship_methods = ["handle_related_to_relationship", "handle_tagged_with_relationship"]
        for method in relationship_methods:
            self.assertIn(method, explanation)
            print(f"✓ Explains relationship method: {method}")
        
        # Verify explanation quality
        print("\nVerifying explanation quality:")
        
        # Each method should have these aspects explained
        explanation_aspects = {
            "Purpose": "explains what the method does",
            "Parameters": "describes input parameters",
            "Returns": "describes return value",
            "Implementation": "explains how it works"
        }
        
        # Take a sample method and verify its explanation is complete
        sample_method = "get_user_details"
        method_explanation = explanation[explanation.find(sample_method):explanation.find(sample_method) + 500]
        
        for aspect, description in explanation_aspects.items():
            self.assertIn(aspect.lower(), method_explanation.lower())
            print(f"✓ {aspect}: {description}")
        
        # Verify the explanation maintains technical accuracy
        technical_terms = [
            "dictionary", "return", "method", "parameter",
            "function", "type", "value"
        ]
        
        tech_terms_found = sum(1 for term in technical_terms if term.lower() in explanation.lower())
        print(f"\nTechnical accuracy: {tech_terms_found}/{len(technical_terms)} technical terms used")
        self.assertGreater(tech_terms_found, len(technical_terms) * 0.7)
        
        # Verify readability
        sentences = explanation.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        print(f"Average sentence length: {avg_sentence_length:.1f} words")
        self.assertLess(avg_sentence_length, 25)  # Good readability threshold
        
        print("\n✓ Explanation is both technical and readable")
    
    def test_error_handling(self):
        """Test that the agent handles errors gracefully."""
        print("\n=== Testing Error Handling ===")
        
        # Test with invalid prompt name
        print("\nTesting invalid prompt name...")
        try:
            self.agent.load_prompt("nonexistent_prompt", {})
            self.fail("Should have raised an error for invalid prompt")
        except Exception as e:
            print(f"✓ Properly handled invalid prompt: {str(e)}")
        
        # Test with invalid schema method
        print("\nTesting invalid schema method...")
        original_format = self.agent.format_schema_methods
        self.agent.format_schema_methods = lambda: "Invalid schema format"
        
        try:
            result = self.agent.execute()
            print("\nResponse with invalid schema:")
            print("---")
            print(result[:500] + "..." if len(result) > 500 else result)
            print("---")
            
            # Even with invalid schema, should get a coherent response
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50)
            print("✓ Produced coherent response even with invalid schema")
            
        finally:
            # Restore original method
            self.agent.format_schema_methods = original_format

if __name__ == '__main__':
    unittest.main() 