"""Interface definition for agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable

# Type aliases
ToolSchema = Dict[str, Any]

class AgentInterface(ABC):
    """Base interface for all agents in the system."""
    
    @abstractmethod
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: Any,
        ontology_manager: Any,
        role: str
    ):
        """Initialize the agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            role: Agent role for determining available tools
        """
        pass
    
    @property
    @abstractmethod
    def available_tools(self) -> Dict[str, Callable]:
        """Get available tools.
        
        Returns:
            Dict mapping tool names to their implementations
        """
        pass
    
    @property
    @abstractmethod
    def tool_schemas(self) -> List[ToolSchema]:
        """Get tool schemas.
        
        Returns:
            List of tool schemas defining their parameters and usage
        """
        pass
    
    @abstractmethod
    def register_tool(self, name: str, func: Callable, schema: ToolSchema) -> None:
        """Register a new tool.
        
        Args:
            name: Name of the tool
            func: The tool's implementation
            schema: The tool's schema
        """
        pass
    
    @abstractmethod
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template.
        
        Args:
            prompt_name: Name of the prompt template file
            context: Context variables for template rendering
            
        Returns:
            Rendered prompt string
        """
        pass
    
    @abstractmethod
    def call_llm(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Call the LLM API.
        
        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0-1.0)
            system_prompt: Optional system prompt
            **kwargs: Additional arguments for the API call
            
        Returns:
            The LLM's response
        """
        pass
    
    @abstractmethod
    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the agent's primary function.
        
        Args:
            data: Optional data needed for execution
            
        Returns:
            Results of the execution
        """
        pass
