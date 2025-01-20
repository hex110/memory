from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, List, Callable, TypedDict

# Generic type for the agent's execution result
T = TypeVar('T')

class ToolParameter(TypedDict):
    """Type definition for a tool parameter."""
    type: str
    description: str
    required: bool

class ToolSchema(TypedDict):
    """Type definition for a tool's schema."""
    name: str
    description: str
    parameters: Dict[str, ToolParameter]

class AgentInterface(ABC):
    """Interface for implementing agent classes.
    
    This interface defines the contract that all agent implementations must follow.
    The typical execution flow is:
    1. Agent is initialized with configuration
    2. execute() is called, which typically:
       a. Prepares the input (e.g., formatting data)
       b. Loads and renders a prompt template
       c. Calls the LLM with the prompt
       d. Parses and returns the response
    """
    
    @property
    @abstractmethod
    def available_tools(self) -> Dict[str, Callable]:
        """Get the tools available to this agent.
        
        Returns:
            Dict[str, Callable]: Mapping of tool names to their implementations
        """
        pass
    
    @property
    @abstractmethod
    def tool_schemas(self) -> List[ToolSchema]:
        """Get the schemas for all available tools.
        
        Returns:
            List[ToolSchema]: List of tool schemas in the OpenAI function calling format
        """
        pass
    
    @abstractmethod
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template with the given context.
        
        Args:
            prompt_name (str): Name of the prompt template to load (without extension)
            context (Dict[str, Any]): Variables to render in the template
            
        Returns:
            str: The rendered prompt string
            
        Raises:
            Exception: If prompt loading or rendering fails
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
        """Call the LLM API with the given prompt and return the response.
        
        Args:
            prompt (str): The prompt to send to the LLM
            temperature (float): Sampling temperature (0-1)
            system_prompt (Optional[str]): Optional system instructions
            **kwargs: Additional arguments for the LLM
            
        Returns:
            str: The LLM's response
            
        Raises:
            APIConnectionError: If there are network connectivity issues
            APIAuthenticationError: If the API key is invalid
            APIResponseError: If the API response is invalid
            APIError: For other API-related errors
        """
        pass

    @abstractmethod
    def parse_response(self, response: str) -> Any:
        """Parse the LLM response to extract useful information.
        
        Args:
            response (str): The raw response from the LLM
            
        Returns:
            Any: The parsed and structured information from the response
        """
        pass

    @abstractmethod
    def execute(self) -> T:
        """Execute the agent's primary function.
        
        This method implements the main logic flow of the agent:
        1. Prepare any necessary input data
        2. Load and render appropriate prompts
        3. Make LLM calls as needed
        4. Parse and process responses
        5. Return the final result
        
        Returns:
            T: The result of the agent's execution, type depends on the specific agent
            
        Raises:
            NotImplementedError: This method must be overridden by subclasses
        """
        pass
