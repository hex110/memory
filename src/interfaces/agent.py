"""Interface definition for agents.

This module defines the base interface that all agents must implement. The agent system
is designed around:

1. LLM Interaction:
   - Function calling for structured outputs
   - Tool registry for available functions
   - Response validation

2. Prompt Management:
   - Jinja2 templates for prompts
   - Context-based rendering
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable

class AgentInterface(ABC):
    """Base interface for all agents in the system."""
    
    @abstractmethod
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db: Any,
        ontology_manager: Any
    ):
        """Initialize the agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db: Database interface instance
            ontology_manager: Ontology manager instance
        """
        pass
    
    @abstractmethod
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template.
        
        Args:
            prompt_name: Name of the prompt template file
            context: Variables to pass to the template
            
        Returns:
            Rendered prompt string
        """
        pass
    
    @abstractmethod
    def call_llm(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Call the LLM with function calling support.
        
        Args:
            prompt: The prompt or message list
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            tool_behavior: How to handle tool usage and outputs
            **kwargs: Additional LLM arguments
            
        Returns:
            LLM response or tool output
        """
        pass
    
    @abstractmethod
    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the agent's primary function.
        
        Args:
            data: Optional input data
            
        Returns:
            Execution results
        """
        pass