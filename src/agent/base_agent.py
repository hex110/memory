"""Base implementation of the agent interface."""

import asyncio
from collections.abc import AsyncIterable
import os
import json
import time
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
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
from src.schemas.tools_definitions import get_tool_implementations
from src.utils.tts import TTSEngine, tee_stream

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
        ontology_manager: OntologyManager,
        tts_engine: Optional[TTSEngine] = None
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
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")).aio
        self.model = self.config["llm"].get("model", "gemini-2.0-flash-exp")
        
        self.env = Environment(loader=FileSystemLoader(prompt_folder))
        
        self.db = db
        self.ontology_manager = ontology_manager
        self.tts_engine = tts_engine

        # Initialize tool registry
        self.tool_registry = {}
        self.available_tools = []  # List of tool names this agent can use
        
        self._tools_loaded = False
    
    def _ensure_tools_loaded(self):
        """Ensures tools are loaded before they're accessed."""
        if not self._tools_loaded:
            self._load_tool_implementations()
            self._tools_loaded = True

    def _load_tool_implementations(self):
        """Load implementations for available tools."""
        
        
        # self.logger.debug(f"Available tools: {self.available_tools}")
        implementations = get_tool_implementations(self.available_tools)
        class_instances = {}  # Cache for class instances
        

        # self.logger.debug(f"Implementations: {implementations}")
        for tool_name, tool_def in implementations.items():
            # Strip module prefix when registering the tool
            simple_name = tool_name.split('.')[-1]
            module_name, func_name = tool_def.implementation.split(".")
            module_path = f"src.agent.tools.tl_{module_name}"
            
            # self.logger.debug(f"Module path: {module_path}")
            # self.logger.debug(f"Function name: {func_name}")
            
            if tool_def.implementation_type == "function":
                # Load function directly from module
                module = __import__(module_path, fromlist=[func_name])
                self.tool_registry[simple_name] = getattr(module, func_name)
                
            elif tool_def.implementation_type == "method":
                # Only initialize class with db if it's a database tool
                if module_path not in class_instances:
                    module = __import__(module_path, fromlist=[tool_def.class_name])
                    class_ = getattr(module, tool_def.class_name)
                    # Initialize with db only for database tools
                    if tool_def.category == "database":
                        class_instances[module_path] = class_(self.db)
                    else:
                        class_instances[module_path] = class_()
                        
                instance = class_instances[module_path]
                self.tool_registry[simple_name] = getattr(instance, func_name)
    
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
        message_history: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[tuple[bytes, str]]] = None,  # List of (bytes, mime_type)
        videos: Optional[List[tuple[bytes, str]]] = None,  # List of (bytes, mime_type)
        audios: Optional[List[tuple[bytes, str]]] = None,  # List of (bytes, mime_type)
        streaming: bool = False,
        tts: bool = False,
        **kwargs
    ) -> Union[str, AsyncIterable[str]]:
        try:
            contents = []
        
            # Add message history if provided
            if message_history:
                for msg in message_history:
                    contents.append(types.Content(
                        role=msg["role"],
                        parts=[types.Part.from_text(msg["content"])]
                    ))

            # Build parts list
            parts = []
            
            # Add system prompt if provided
            if system_prompt:
                parts.append(types.Part.from_text(system_prompt))
            
            # Add media files
            if images:
                for image_data, mime_type in images:
                    parts.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
            
            if videos:
                for video_data, mime_type in videos:
                    parts.append(types.Part.from_bytes(data=video_data, mime_type=mime_type))
                
            if audios:
                for audio_data, mime_type in audios:
                    parts.append(types.Part.from_bytes(data=audio_data, mime_type=mime_type))
            
           # Add the new prompt
            if isinstance(prompt, str):
                parts.append(types.Part.from_text(prompt))
                messages = [{"role": "user", "content": prompt}]
            else:
                for message in prompt:
                    parts.append(types.Part.from_text(message["content"]))
                messages = prompt
            
            # Create content
            contents.append(types.Content(role="user", parts=parts))
            
            # Configure tools
            tools = None
            if specific_tools or self.available_tools:
                from src.schemas.tools_definitions import get_tool_declarations
                tools = get_tool_declarations(specific_tools or self.available_tools)
            
            # Remove tool-related kwargs
            config_kwargs = {k: v for k, v in kwargs.items() 
                           if k not in ['tools', 'tool_config', 'function_call']}

            self.logger.debug("Calling LLM")

            # Always use streaming if TTS is enabled
            use_stream = streaming or tts

            if use_stream:
                full_response = []

                # Create the base stream
                base_stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        tools=tools,
                        **config_kwargs
                    )
                )

                async def process_stream():
                    async for chunk in base_stream:
                        # Check if there's a function call and if it has the required attributes
                        if (hasattr(chunk.candidates[0].content.parts[0], 'function_call') and 
                            chunk.candidates[0].content.parts[0].function_call is not None and
                            hasattr(chunk.candidates[0].content.parts[0].function_call, 'name')):
                            # If we get a function call in streaming mode, fall back to non-streaming
                            response = await self._handle_tool_calls(
                                message=chunk.candidates[0].content,
                                messages=messages,
                                tool_behavior=tool_behavior,
                                kwargs=kwargs
                            )
                            yield response
                            return
                        
                        # self.logger.debug(f"Yielding chunk: {chunk.text}")
                        yield chunk.text

                # Create the processed stream
                processed_stream = process_stream()

                if tts and streaming:
                    # If both TTS and streaming are needed, create two separate streams
                    tts_stream, response_stream = await tee_stream(processed_stream)
                    # Start TTS processing
                    asyncio.create_task(self.tts_engine.play_stream(tts_stream))
                    # Return the response stream
                    return response_stream
                elif tts:
                    # If only TTS is needed, but we still want to process chunks as they arrive
                    tts_stream, collection_stream, fill_task = await tee_stream(processed_stream)
                    
                    # Start TTS processing with the streaming chunks
                    tts_task = asyncio.create_task(self.tts_engine.play_stream(tts_stream))
                    
                    # Collect the full response while waiting for both tasks
                    async for chunk in collection_stream:
                        full_response.append(chunk)
                        
                    # Wait for both tasks to complete
                    await asyncio.gather(fill_task, tts_task)
                    
                    return ''.join(full_response)
                elif streaming:
                    # If only streaming is needed
                    return processed_stream
                else:
                    # If neither is needed, collect full response
                    async for chunk in processed_stream:
                        full_response.append(chunk)
                    return ''.join(full_response)
            
            else:
                response = await self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        tools=tools,
                        **config_kwargs
                    )
                )

                self.logger.debug(f"Response: {response.text}")
                
                # Check if there's a function call and if it has the required attributes
                if (hasattr(response.candidates[0].content.parts[0], 'function_call') and 
                    response.candidates[0].content.parts[0].function_call is not None and
                    hasattr(response.candidates[0].content.parts[0].function_call, 'name')):
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
        self._ensure_tools_loaded()
        
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
            # self.logger.debug(f"Calling tool: {function_call.name}")
            # self.logger.debug(f"Tool registry: {self.tool_registry[function_call.name]}")
            function = self.tool_registry[function_call.name]
            function_response = await function(**function_call.args)
            
            # Convert function response to string if needed
            if not isinstance(function_response, str):
                function_response = json.dumps(function_response)
            
            if tool_behavior == ToolBehavior.USE_AND_DONE:
                return function_response
        
            # Add tool response to message history
            messages.append({"role": "tool", "content": function_response})

            contents = []
            for m in messages[:-2]:  # Convert previous messages
                contents.append(types.Content(
                    role=m["role"],
                    parts=[types.Part.from_text(m["content"])]
                ))
                
            # Add function call and response in the format expected by Gemini
            contents.append(message)  # Function call content
            function_response_part = types.Part.from_function_response(
                name=function_call.name,
                response={"result": function_response}
            )
            contents.append(types.Content(
                role="tool", 
                parts=[function_response_part]
            ))
            
            if tool_behavior == ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents
                )
                # return response.text
                return response
            
            else:  # KEEP_USING_UNTIL_DONE
                response = self.client.models.generate_content(
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