"""Base implementation of the agent interface."""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from jinja2 import Environment, FileSystemLoader

import litellm
from litellm import completion
from json_repair import repair_json
from src.utils.config import (
    load_config, get_provider_config, ConfigError
)
from src.utils.exceptions import (
    APIError, APIConnectionError, APIResponseError,
    APIAuthenticationError
)
from src.interfaces.agent import AgentInterface, ToolSchema
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.agent_tools import AgentDatabaseTools

class BaseAgent(AgentInterface):
    """Base class implementing common agent functionality."""
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager,
        role: str
    ):
        """Initialize the agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            role: Agent role for determining available tools
            
        Raises:
            ConfigError: If required config values are missing
        """
        # Enable verbose logging for LiteLLM
        litellm.set_verbose = True
        
        # Enable JSON schema validation for Gemini
        litellm.enable_json_schema_validation = True
        
        self.config = load_config(config_path)
        
        # Validate required config
        if not self.config.get("llm"):
            raise ConfigError("Missing 'llm' section in config")
        
        # Get provider-specific configuration
        provider_config = get_provider_config(self.config)
        
        # Set up environment variables for LiteLLM
        provider = self.config["llm"].get("provider", "gemini").lower()
        if provider == "gemini":
            os.environ["GEMINI_API_KEY"] = provider_config["api_key"]
            # Add gemini/ prefix for LiteLLM
            self.model = "gemini/gemini-2.0-flash-exp"
        else:
            # For OpenRouter
            os.environ["OPENROUTER_API_KEY"] = provider_config["api_key"]
            self.model = provider_config["model"]
        
        self.env = Environment(loader=FileSystemLoader(prompt_folder))
        
        # Initialize database tools with role-specific access
        self.db_tools = AgentDatabaseTools(db_interface, ontology_manager, role)
        
        # Initialize tool registries
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: List[ToolSchema] = []
        
        # Register all database tools available for this role
        for schema in self.db_tools.get_tool_schemas():
            self.register_tool(
                schema["name"],
                getattr(self.db_tools, schema["name"]),
                schema
            )
    
    @property
    def available_tools(self) -> Dict[str, Callable]:
        """Get available tools. Override in subclass to add tools."""
        return self._tools
    
    @property
    def tool_schemas(self) -> List[ToolSchema]:
        """Get tool schemas. Override in subclass to add schemas."""
        return self._tool_schemas
    
    def register_tool(self, name: str, func: Callable, schema: ToolSchema) -> None:
        """Register a new tool.
        
        Args:
            name: Name of the tool
            func: The tool's implementation
            schema: The tool's schema
        """
        self._tools[name] = func
        self._tool_schemas.append(schema)
    
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template."""
        template = self.env.get_template(f"{prompt_name}.txt")
        return template.render(**context)
    
    def call_llm(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Call the LLM API with retries and tool support."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Configure function calling
            if self.tool_schemas:
                # Format tools according to Gemini's spec
                tools = []
                for schema in self.tool_schemas:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": schema["name"],
                            "description": schema.get("description", ""),
                            "parameters": schema["parameters"]
                        }
                    })
                
                # Set up tool configuration for Gemini
                kwargs["tools"] = tools
                kwargs["tool_config"] = {
                    "function_calling_config": {
                        "mode": "ANY"  # Force function calling
                    }
                }
            
            response = completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                **kwargs
            )
            
            # Handle tool calls if present
            message = response.choices[0].message
            if message.tool_calls and self.available_tools:
                return self._handle_tool_calls(message, messages)
            
            return message.content or ""
            
        except Exception as e:
            raise APIResponseError(f"Error calling LLM: {str(e)}") from e
    
    def _handle_tool_calls(
        self,
        message: Dict[str, Any],
        messages: List[Dict[str, Any]]
    ) -> str:
        """Handle tool calls from the LLM.
        
        Args:
            message: The message containing the tool calls
            messages: The current message history
            
        Returns:
            str: The final response after tool calling
        """
        # Add assistant's message with tool calls
        messages.append({
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": message.tool_calls
        })
        
        # Handle each tool call
        tool_responses = []
        for tool_call in message.tool_calls:
            try:
                func_name = tool_call.function.name
                # Use json-repair to handle malformed JSON
                func_args = json.loads(repair_json(tool_call.function.arguments))
                
                # Call the function
                function = self.available_tools[func_name]
                function_response = function(**func_args)
                
                # Add tool response to messages
                tool_response = {
                    "role": "tool",
                    "name": func_name,
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response)
                }
                messages.append(tool_response)
                tool_responses.append(function_response)
                
            except Exception as e:
                print(f"Error handling tool call: {str(e)}")
                error_response = {
                    "role": "tool",
                    "name": func_name if 'func_name' in locals() else "unknown",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": str(e)})
                }
                messages.append(error_response)
                tool_responses.append({"error": str(e)})
        
        # If only one tool call, return its response directly
        if len(tool_responses) == 1:
            return json.dumps(tool_responses[0])
        
        # Get final response from LLM for multiple tool calls
        response = completion(
            model=self.model,
            messages=messages
        )
        
        return response.choices[0].message.content or ""
    
    def validate_function_response(self, response: str, model_class: Any) -> Any:
        """Validate and parse a function response using a Pydantic model.
        
        Args:
            response: JSON string from function call
            model_class: Pydantic model class to validate against
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            ValueError: If validation fails
        """
        try:
            # Use json-repair to fix potentially malformed JSON
            if isinstance(response, str):
                data = json.loads(repair_json(response))
            else:
                data = response
                
            # Validate with Pydantic
            return model_class.model_validate(data)
            
        except Exception as e:
            raise ValueError(f"Failed to validate function response: {str(e)}")
    
    def execute(self) -> Any:
        """Execute the agent's primary function.
        
        This should be implemented by subclasses.
        """
        raise NotImplementedError
    
    def parse_response(self, response: str) -> Any:
        """Parse the LLM's response.
        
        This can be overridden by subclasses for specific parsing.
        """
        return response 