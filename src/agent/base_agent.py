"""Base implementation of the agent interface."""

import os
import json
import time
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from jinja2 import Environment, FileSystemLoader

from google import genai
from google.genai import types
from json_repair import repair_json
from src.utils.config import (
    ConfigError
)
from src.utils.exceptions import (
    APIError, APIConnectionError, APIResponseError,
    APIAuthenticationError
)
from src.interfaces.agent import AgentInterface
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.utils.logging import get_logger

class ToolBehavior(Enum):
    """Controls how tools are used and their outputs handled."""
    USE_AND_DONE = "use_and_done"  # Use tool and return its output
    USE_AND_ANALYZE_OUTPUT_AND_DONE = "use_and_analyze_output_and_done"  # Use tool, analyze output, return analysis
    KEEP_USING_UNTIL_DONE = "keep_using_until_done"  # Keep using tools until task complete

class BaseAgent(AgentInterface):
    """Base class implementing common agent functionality."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        """Initialize the agent.
        
        Args:
            config: Configuration dictionary
            prompt_folder: Path to prompt templates folder
            db: Database interface instance
            ontology_manager: Ontology manager instance
            
        Raises:
            ConfigError: If required config values are missing
        """
        # Set up logging
        self.logger = get_logger(f"src.agent.{self.__class__.__name__.lower()}")
        
        self.config = config
        
        # Validate required config
        if not self.config.get("llm"):
            raise ConfigError("Missing 'llm' section in config")
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = self.config["llm"].get("model", "gemini-2.0-flash-exp")
        
        self.env = Environment(loader=FileSystemLoader(prompt_folder))
        
        self.db = db
        self.ontology_manager = ontology_manager

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
                    class_instances[module_path] = class_(self.db)
                    
                instance = class_instances[module_path]
                self.tool_registry[tool_name] = getattr(instance, func_name)
    
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template."""
        template = self.env.get_template(f"{prompt_name}.txt")
        return template.render(**context)
    
    async def call_llm(
        self,
        prompt: Union[str, List[Dict[str, Any]]],
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tool_behavior: ToolBehavior = ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE,
        specific_tools: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        try:
            messages = []
            
            if isinstance(prompt, str):
                messages.append({"role": "user", "content": prompt})
            else:
                messages.extend(prompt)
                
            # Convert messages to Gemini format
            contents = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages]
            
            # Configure tools - either use specific_tools or self.available_tools
            tools = None
            if specific_tools or self.available_tools:
                from src.schemas.tools_definitions import get_tool_declarations
                tools = get_tool_declarations(specific_tools or self.available_tools)
            
            # Remove tool-related kwargs
            config_kwargs = {k: v for k, v in kwargs.items() 
                           if k not in ['tools', 'tool_config', 'function_call']}
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_prompt if system_prompt else None,
                    tools=tools,
                    **config_kwargs
                )
            )
            
            # Check for function calls
            if hasattr(response, 'candidates') and response.candidates[0].content.parts[0].function_call:
                return await self._handle_tool_calls(
                    message=response.candidates[0].content,
                    messages=messages,
                    tool_behavior=tool_behavior,
                    kwargs=kwargs
                )
                
            return response.text
            
        except Exception as e:
            raise APIResponseError(f"Error calling LLM: {str(e)}") from e
    
    async def _handle_tool_calls(
        self,
        message: Any,
        messages: List[Dict[str, Any]],
        tool_behavior: ToolBehavior,
        kwargs: Dict[str, Any]
    ) -> str:
        # Extract the function call details
        function_call = message.parts[0].function_call
        
        # Add assistant message with function call to message history
        messages.append({
            "role": "assistant",
            "content": message.parts[0].text if hasattr(message.parts[0], 'text') else None,
            "function_call": {
                "name": function_call.name,
                "arguments": function_call.args
            }
        })
        
        try:
            # Get and call the tool implementation
            function = self.tool_registry[function_call.name]
            function_response = await function(**function_call.args)
            
            # Convert function response to string if needed
            if not isinstance(function_response, str):
                function_response = json.dumps(function_response)
                
            # Create tool response content
            function_response_part = types.Part.from_function_response(
                name=function_call.name,
                response={"result": function_response}
            )
            tool_content = types.Content(role="tool", parts=[function_response_part])
            
            if tool_behavior == ToolBehavior.USE_AND_DONE:
                return function_response
                
            # Add tool response to messages and convert all to Gemini format
            messages.append({"role": "tool", "content": function_response})
            contents = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages]
            
            if tool_behavior == ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE:
                response = await self.client.models.generate_content(
                    model=self.model,
                    contents=contents
                )
                return response.text
                
            else:  # KEEP_USING_UNTIL_DONE
                response = await self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        tools=kwargs.get("tools")
                    )
                )
                
                # Check if there's another function call
                if hasattr(response.candidates[0].content.parts[0], 'function_call'):
                    return await self._handle_tool_calls(
                        message=response.candidates[0].content,
                        messages=messages,
                        tool_behavior=tool_behavior,
                        kwargs=kwargs
                    )
                    
                return response.text
                
        except Exception as e:
            self.logger.error(f"Tool call failed: {str(e)}", exc_info=True)
            return json.dumps({"error": str(e)})
    
    def validate_function_response(self, response: str, model_class: Any) -> Any:
        """Validate and parse a function response using a Pydantic model."""
        try:
            if isinstance(response, str):
                data = json.loads(repair_json(response))
            else:
                data = response
            return model_class.model_validate(data)
        except Exception as e:
            raise ValueError(f"Failed to validate function response: {str(e)}")
    
    async def execute(self) -> Any:
        """Execute the agent's primary function.
        
        This should be implemented by subclasses.
        """
        raise NotImplementedError
    
    def parse_response(self, response: str) -> Any:
        """Parse the LLM's response.
        
        This can be overridden by subclasses for specific parsing.
        """
        return response