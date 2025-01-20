"""Base implementation of the agent interface."""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import requests
from jinja2 import Environment, FileSystemLoader
from src.utils.config import load_config
from src.utils.exceptions import (
    APIError, APIConnectionError, APIResponseError,
    APIAuthenticationError, ConfigError
)
from src.agent.agent_interface import AgentInterface, ToolSchema
from src.database.database_interface import DatabaseInterface
from src.ontology.ontology_manager import OntologyManager
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
        self.config = load_config(config_path)
        
        # Validate required config
        if not self.config.get("llm"):
            raise ConfigError("Missing 'llm' section in config")
        
        llm_config = self.config["llm"]
        required_fields = ["api_key", "model", "base_url"]
        missing_fields = [f for f in required_fields if not llm_config.get(f)]
        if missing_fields:
            raise ConfigError(f"Missing required LLM config fields: {', '.join(missing_fields)}")
        
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
        max_retries = 2
        first_error = None
        base_url = self.config["llm"]["base_url"]
        headers = {
            "Authorization": f"Bearer {self.config['llm']['api_key']}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Add tool calling if tools are available
        if self.tool_schemas:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": schema
                }
                for schema in self.tool_schemas
            ]
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    base_url,
                    headers=headers,
                    json={
                        "model": self.config["llm"]["model"],
                        "messages": messages,
                        "temperature": temperature,
                        **kwargs
                    },
                    timeout=30
                )
                
                if response.status_code == 401:
                    raise APIAuthenticationError("Invalid API key")
                
                response.raise_for_status()
                response_data = response.json()
                
                # Print response for debugging
                print("\nAPI Response:", json.dumps(response_data, indent=2))
                
                # Handle tool calls
                message = response_data.get("choices", [{}])[0].get("message", {})
                if message.get("tool_calls") and self.available_tools:
                    return self._handle_tool_calls(message, messages)
                
                return message.get("content", "")
                
            except requests.exceptions.Timeout as e:
                first_error = first_error or e
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.exceptions.ConnectionError as e:
                first_error = first_error or e
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                if response.status_code == 401:
                    raise APIAuthenticationError("Invalid API key")
                first_error = first_error or e
                time.sleep(2 ** attempt)
        
        if isinstance(first_error, requests.exceptions.Timeout):
            raise APIConnectionError("API request timed out") from first_error
        elif isinstance(first_error, requests.exceptions.ConnectionError):
            raise APIConnectionError("Failed to connect to API") from first_error
        else:
            raise APIResponseError("API request failed") from first_error
    
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
        while message.get("tool_calls"):
            # Add assistant's message with tool calls
            messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": message["tool_calls"]
            })
            
            # Handle each tool call
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = json.loads(tool_call["function"]["arguments"])
                
                # Call the function
                function = self.available_tools[func_name]
                function_response = function(**func_args)
                
                # Add tool response to messages
                messages.append({
                    "role": "tool",
                    "name": func_name,
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(function_response)
                })
            
            # Get next action from LLM
            response = requests.post(
                self.config["llm"]["base_url"],
                headers={
                    "Authorization": f"Bearer {self.config['llm']['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.config["llm"]["model"],
                    "messages": messages,
                    "tools": [{"type": "function", "function": schema} for schema in self.tool_schemas]
                }
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
        
        return message.get("content", "")
    
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