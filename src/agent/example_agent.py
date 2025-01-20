import json
from typing import Any, Dict
from src.agent.base_agent import BaseAgent
from src.ontology.ontology_schema import ontology_schema

class SchemaExplainerAgent(BaseAgent):
    """An agent that explains the ontology schema methods in natural language."""
    
    def __init__(self, **kwargs):
        """Initialize the SchemaExplainerAgent.
        
        Args:
            **kwargs: Arguments to pass to the BaseAgent constructor
        """
        super().__init__(**kwargs)
        self.schema = ontology_schema
        
    def format_schema_methods(self) -> str:
        """Format the schema methods into a readable string.
        
        Returns:
            str: A formatted string containing the schema methods
        """
        formatted_methods = []
        
        # Format concepts
        formatted_methods.append("Concepts Methods:")
        for concept, details in self.schema["concepts"].items():
            formatted_methods.append(f"""
def get_{concept}_details() -> Dict[str, str]:
    \"\"\"Get details about the {concept} concept.
    
    Returns:
        Dict[str, str]: A dictionary containing:
            - description: {details['description']}
    \"\"\"
    return {json.dumps(details, indent=4)}
""")
        
        # Format relationships
        formatted_methods.append("\nRelationship Methods:")
        for rel, details in self.schema["relationships"].items():
            formatted_methods.append(f"""
def handle_{rel}_relationship(source: str, target: str) -> bool:
    \"\"\"Handle the {rel} relationship between {details['source_type']} and {details['target_type']}.
    
    Args:
        source (str): The source {details['source_type']} ID
        target (str): The target {details['target_type']} ID
        
    Returns:
        bool: True if the relationship was handled successfully
        
    Description:
        {details['description']}
    \"\"\"
    pass
""")
        
        return "\n".join(formatted_methods)
    
    def execute(self) -> str:
        """Execute the agent's primary function.
        
        Returns:
            str: Natural language explanation of the schema methods
        """
        # Format the methods
        methods_str = self.format_schema_methods()
        
        # Load and render the prompt
        prompt = self.load_prompt("explain_methods", {"methods": methods_str})
        
        # Call LLM with system context
        system_prompt = """You are an expert Python developer who excels at explaining code clearly.
        Focus on practical implications and use cases when explaining the methods."""
        
        # Get and parse the response
        response = self.call_llm(prompt, temperature=0.7, system_prompt=system_prompt)
        return self.parse_response(response)
    
    def parse_response(self, response: str) -> str:
        """Parse the LLM response.
        
        In this case, we just return the response as is since it's already
        in the format we want (natural language explanation).
        
        Args:
            response (str): The LLM's response
            
        Returns:
            str: The parsed response
        """
        return super().parse_response(response) 