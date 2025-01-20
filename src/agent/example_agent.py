"""Example agent that explains schema methods and can interact with the ontology."""

from typing import Any, Dict
from src.agent.base_agent import BaseAgent

class SchemaExplainerAgent(BaseAgent):
    """An agent that explains the ontology schema methods and can interact with the ontology."""
    
    def __init__(self, **kwargs):
        """Initialize the SchemaExplainerAgent.
        
        Args:
            **kwargs: Arguments to pass to the BaseAgent constructor
        """
        # Remove role if it's in kwargs to avoid duplication
        kwargs.pop('role', None)
        super().__init__(role="curator", **kwargs)  # Use curator role for read-only access
    
    def format_schema_methods(self, methods: Dict[str, Any]) -> str:
        """Format schema methods into a readable string.
        
        Args:
            methods: Dictionary of method names to their details
            
        Returns:
            Formatted string explaining the methods
        """
        formatted = []
        for name, details in methods.items():
            formatted.append(f"Method: {name}")
            formatted.append(f"Description: {details.get('description', 'No description')}")
            
            params = details.get('parameters', {}).get('properties', {})
            if params:
                formatted.append("Parameters:")
                for param_name, param_details in params.items():
                    formatted.append(f"  - {param_name}: {param_details.get('description', 'No description')}")
            
            formatted.append("")  # Empty line between methods
        
        return "\n".join(formatted)
    
    def execute(self, method_name: str = None) -> str:
        """Execute the agent to explain schema methods.
        
        Args:
            method_name: Optional specific method to explain
            
        Returns:
            str: Natural language explanation of the requested methods
        """
        # Get schema information using database tools
        schema = self.db_tools.get_schema()
        
        # Format the prompt context
        context = {
            "methods": self.format_schema_methods(schema),
            "specific_method": method_name
        }
        
        # Load and render the prompt
        prompt = self.load_prompt("explain_methods", context)
        
        # Get explanation from LLM
        response = self.call_llm(
            prompt,
            temperature=0.7,  # Use moderate temperature for natural language
            system_prompt="You are an expert at explaining technical concepts clearly and concisely."
        )
        
        return self.parse_response(response)
    
    def parse_response(self, response: str) -> str:
        """Parse the LLM response.
        
        For this agent, we just return the response as is since it should
        already be in the desired format (natural language explanation).
        """
        return response 