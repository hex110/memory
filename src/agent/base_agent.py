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
                    if tool_def.category == "database" or tool_def.category == "tasks":
                        class_instances[module_path] = class_(self.db)
                    elif tool_def.category == "context":
                        class_instances[module_path] = class_(
                            db=getattr(self, 'db', None),
                            activity_manager=getattr(self, 'activity_manager', None)
                        )
                    elif tool_def.category == "interaction":
                        class_instances[module_path] = class_(self.tts_engine)
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
        model: str = None,
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
            self.logger.debug(f"Prompt:\n{prompt}\n")
            # self.logger.debug(f"System prompt:\n{system_prompt}\n")

            if model is None:
                model = self.model
            
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
            # self.logger.debug(f"Tools: {tools}")
            
            # Remove tool-related kwargs
            config_kwargs = {k: v for k, v in kwargs.items() 
                           if k not in ['tools', 'tool_config', 'function_call']}

            config=types.GenerateContentConfig(
                temperature=temperature,
                tools=tools,
                **config_kwargs
            )

            # self.logger.debug("Calling LLM")

            # Always use streaming if TTS is enabled
            use_stream = streaming or tts

            if use_stream:
                full_response = []

                # Create the base stream
                base_stream = self.client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=config
                )

                async def process_stream():
                    async for chunk in base_stream:
                        # self.logger.debug(f"Chunk: {chunk}")
                        # Check if there's a function call and if it has the required attributes
                        if (hasattr(chunk.candidates[0].content.parts[0], 'function_call') and 
                            chunk.candidates[0].content.parts[0].function_call is not None and
                            hasattr(chunk.candidates[0].content.parts[0].function_call, 'name')):
                            # If we get a function call in streaming mode, fall back to non-streaming

                            contents.append(chunk.candidates[0].content)
                            response = await self._handle_tool_calls(
                                contents=contents,
                                tool_behavior=tool_behavior,
                                config=config,
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
                    model=model,
                    contents=contents,
                    config=config
                )

                # self.logger.debug(f"Response: {response}")
                
                text_response = response.candidates[0].content.parts[0].text

                if hasattr(response.candidates[0].content.parts[0], 'function_call') and response.candidates[0].content.parts[0].function_call is not None:
                    contents.append(response.candidates[0].content)
                    text_response = await self._handle_tool_calls(
                        contents=contents,
                        tool_behavior=tool_behavior,
                        config=config,
                        kwargs=kwargs
                    )
                    # self.logger.debug(f"RETURNING: {text_response}")
                    return text_response

                # Return the text response if no function calls were made
                return text_response
            
        except Exception as e:
            raise APIResponseError(f"Error calling LLM: {str(e)}") from e
    

    async def _handle_tool_calls(
        self,
        contents: List[types.Content],
        tool_behavior: ToolBehavior,
        config: types.GenerateContentConfig,
        kwargs: Dict[str, Any]
    ) -> str:
        """Handles tool calls, executes tools, manages tool behavior, and iterates for KEEP_USING_UNTIL_DONE."""
        self._ensure_tools_loaded()

        # Extract function calls from the LAST message in contents (which is the LLM's response)
        last_message_content = contents[-1]
        function_calls = [
            part.function_call
            for part in last_message_content.parts
            if hasattr(part, "function_call") and part.function_call is not None
        ]

        self.logger.debug(f"Function calls detected in _handle_tool_calls: {function_calls}")

        tool_responses_contents = []
        for function_call in function_calls:
            # Execute the tool
            function = self.tool_registry[function_call.name]
            function_response = await function(**function_call.args)

            # Convert function response to appropriate format - wrap in "result"
            function_response = {"result": function_response}

            serializable_response = {}
            binary_data = {}

            # Convert function response to appropriate format
            if isinstance(function_response['result'], dict): # Check if result is a dict
                for key, value in function_response['result'].items(): # Access items through 'result' key now
                    if isinstance(value, bytes):
                        if 'mime_type' in function_response['result'] and function_response['result']['mime_type']: # Check mime_type in result
                            binary_data[key] = (value, function_response['result']['mime_type']) # Get mime_type from result
                        else:
                            binary_data[key] = (value, 'application/octet-stream')
                    else:
                        serializable_response[key] = value
                serializable_response['result'] = serializable_response # Re-wrap serializable response
            else: # If result is not a dict, treat it as a string result
                serializable_response = {"result": str(function_response['result']) } # Ensure string conversion for non-dict result
                binary_data = {}


            function_response_part = types.Part.from_function_response(
                name=function_call.name,
                response=serializable_response
            )
            tool_response_content = types.Content(role="tool", parts=[function_response_part])

            # Add binary data parts if any
            if binary_data:
                for key, (data, mime_type) in binary_data.items():
                    tool_response_content.parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))

            tool_responses_contents.append(tool_response_content)


        contents.extend(tool_responses_contents) # Append ALL tool responses to contents


        if tool_behavior == ToolBehavior.USE_AND_DONE:
            self.logger.debug("Tool behavior: USE_AND_DONE. Returning tool results.")
            return json.dumps([tc.parts[0].function_response.response for tc in tool_responses_contents]) # Return tool results

        elif tool_behavior == ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE:
            self.logger.debug("Tool behavior: USE_AND_ANALYZE_OUTPUT_AND_DONE. Making final LLM call.")
            response = await self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
            return response.candidates[0].content.parts[0].text

        elif tool_behavior == ToolBehavior.KEEP_USING_UNTIL_DONE:
            self.logger.debug("Tool behavior: KEEP_USING_UNTIL_DONE. Making another LLM call with updated contents.")
            response = await self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )

            if hasattr(response.candidates[0].content.parts[0], 'function_call') and response.candidates[0].content.parts[0].function_call is not None:
                contents.append(response.candidates[0].content)
                return await self._handle_tool_calls(
                    contents=contents,
                    tool_behavior=tool_behavior,
                    config=config,
                    kwargs=kwargs
                )

            return response.candidates[0].content.parts[0].text