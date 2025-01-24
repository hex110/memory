"""Base implementation of the agent interface."""

import os
import json
import time
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
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
from src.interfaces.agent import AgentInterface
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager

class ToolBehavior(Enum):
    """Controls how tools are used and their outputs handled."""
    USE_AND_DONE = "use_and_done"  # Use tool and return its output
    USE_AND_ANALYZE_OUTPUT_AND_DONE = "use_and_analyze_output_and_done"  # Use tool, analyze output, return analysis
    KEEP_USING_UNTIL_DONE = "keep_using_until_done"  # Keep using tools until task complete

class BaseAgent(AgentInterface):
    """Base class implementing common agent functionality."""
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        """Initialize the agent.
        
        Args:
            config_path: Path to config file
            prompt_folder: Path to prompt templates folder
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            
        Raises:
            ConfigError: If required config values are missing
        """
        # Set up logging
        self.logger = logging.getLogger(f"src.agent.{self.__class__.__name__.lower()}")
        
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
            self.model = "gemini/gemini-2.0-flash-exp"
            
            # Verify vision support
            if not litellm.supports_vision(self.model):
                raise ConfigError(f"Model {self.model} does not support vision")
        else:
            # For OpenRouter
            os.environ["OPENROUTER_API_KEY"] = provider_config["api_key"]
            self.model = provider_config["model"]
        
        self.env = Environment(loader=FileSystemLoader(prompt_folder))
        
        # Initialize tool registry
        self.tool_registry = {}
        self.available_tools = []  # List of tool names this agent can use
        
        # Load tool implementations
        self._load_tool_implementations()
    
    def _load_tool_implementations(self):
        """Load implementations for available tools."""
        from src.schemas.tools_definitions import get_tool_implementations
        
        implementations = get_tool_implementations(self.available_tools)
        class_instances = {}  # Cache for class instances
        
        for tool_name, tool_def in implementations.items():
            module_name, func_name = tool_def.implementation.split(".")
            module_path = f"src.agent.tools.tl_{module_name}"
            
            if tool_def.implementation_type == "function":
                # Load function directly from module
                module = __import__(module_path, fromlist=[func_name])
                self.tool_registry[tool_name] = getattr(module, func_name)
                
            elif tool_def.implementation_type == "method":
                # Load method from class instance
                if module_path not in class_instances:
                    module = __import__(module_path, fromlist=[tool_def.class_name])
                    class_ = getattr(module, tool_def.class_name)
                    # Initialize class with any required dependencies
                    class_instances[module_path] = class_(self.db_interface)
                    
                instance = class_instances[module_path]
                self.tool_registry[tool_name] = getattr(instance, func_name)
    
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template."""
        template = self.env.get_template(f"{prompt_name}.txt")
        return template.render(**context)
    
    def call_llm(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tool_behavior: ToolBehavior = ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE,
        **kwargs
    ) -> str:
        """Call the LLM API with tools support and specified behavior.
        
        Args:
            prompt: The prompt or message list
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            tool_behavior: How to handle tool usage and outputs
            **kwargs: Additional arguments for the LLM
            
        Returns:
            The LLM's response or tool output based on tool_behavior
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if isinstance(prompt, str):
                messages.append({"role": "user", "content": prompt})
            else:
                messages.extend(prompt)
            
            # Configure function calling if agent has tools
            if self.available_tools:
                from src.schemas.tools_definitions import get_tool_schemas
                tools = get_tool_schemas(self.available_tools)
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
            
            message = response.choices[0].message
            
            # Handle tool calls if present
            if message.tool_calls and self.available_tools:
                return self._handle_tool_calls(
                    message=message,
                    messages=messages,
                    tool_behavior=tool_behavior,
                    kwargs=kwargs
                )
            
            return message.content or ""
            
        except Exception as e:
            raise APIResponseError(f"Error calling LLM: {str(e)}") from e
    
    def _handle_tool_calls(
        self,
        message: Dict[str, Any],
        messages: List[Dict[str, Any]],
        tool_behavior: ToolBehavior,
        kwargs: Dict[str, Any]
    ) -> str:
        """Handle tool calls based on specified behavior.
        
        Args:
            message: The message containing tool calls
            messages: Current message history
            tool_behavior: How to handle tool usage
            kwargs: Additional LLM arguments
            
        Returns:
            Response based on tool behavior
        """
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
                func_args = json.loads(repair_json(tool_call.function.arguments))
                
                # Get and call the tool implementation
                function = self.tool_registry[func_name]
                function_response = function(**func_args)
                
                tool_response = {
                    "role": "tool",
                    "name": func_name,
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response)
                }
                messages.append(tool_response)
                tool_responses.append(function_response)
                
            except Exception as e:
                self.logger.error(f"Tool call failed: {str(e)}", exc_info=True)
                error_response = {
                    "role": "tool",
                    "name": func_name if 'func_name' in locals() else "unknown",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": str(e)})
                }
                messages.append(error_response)
                tool_responses.append({"error": str(e)})
        
        if tool_behavior == ToolBehavior.USE_AND_DONE:
            # Return the tool output directly
            return json.dumps(tool_responses[0] if len(tool_responses) == 1 else tool_responses)
        
        elif tool_behavior == ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE:
            # Get LLM analysis of the tool output
            response = completion(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content or ""
        
        else:  # KEEP_USING_UNTIL_DONE
            # Let LLM decide if it needs more tool calls
            response = completion(
                model=self.model,
                messages=messages,
                tools=kwargs.get("tools")  # Keep tools available
            )
            
            next_message = response.choices[0].message
            if next_message.tool_calls:
                # Recursive call for chained tool usage
                return self._handle_tool_calls(
                    message=next_message,
                    messages=messages,
                    tool_behavior=tool_behavior,
                    kwargs=kwargs
                )
            
            return next_message.content or ""
    
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
            if isinstance(response, str):
                data = json.loads(repair_json(response))
            else:
                data = response
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