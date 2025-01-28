"""Interface definition for agents.

This module defines the base interface that all agents must implement. The agent system 
supports:

1. LLM Interaction:
   - Multi-modal inputs (text, images, audio, video)
   - Function calling with configurable tool behaviors
   - Conversation history management
   - Temperature control for response generation

2. Tool Integration:
   - Registry of available tools
   - Three tool usage modes:
     * USE_AND_DONE: Execute tool and return raw output
     * USE_AND_ANALYZE_OUTPUT_AND_DONE: Execute tool and have LLM analyze result
     * KEEP_USING_UNTIL_DONE: Allow multiple tool calls to complete task

3. Prompt Management:
   - Jinja2 templates for prompts
   - Context-based rendering
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable
from collections.abc import AsyncIterable
from enum import Enum

class ToolBehavior(Enum):
    """Controls how tools are used and their outputs handled."""
    USE_AND_DONE = "use_and_done"  # Use tool and return its output
    USE_AND_ANALYZE_OUTPUT_AND_DONE = "use_and_analyze_output_and_done"  # Use tool, analyze output, return analysis
    KEEP_USING_UNTIL_DONE = "keep_using_until_done"  # Keep using tools until task complete

class AgentInterface(ABC):
    """Base interface for all agents in the system.
    
    Usage Examples:
    ```python
    # Basic text interaction
    response = await agent.call_llm("What's the weather like?")
    
    # With conversation history
    history = [
        {"role": "user", "content": "Hi!"},
        {"role": "assistant", "content": "Hello! How can I help?"}
    ]
    response = await agent.call_llm("What were we talking about?", message_history=history)
    
    # With images
    with open('image.jpg', 'rb') as f:
        image_data = f.read()
    response = await agent.call_llm(
        "What's in this image?",
        images=[(image_data, 'image/jpeg')]
    )
    
    # Using tools with different behaviors
    # 1. Just execute tool
    response = await agent.call_llm(
        "Play the next song",
        tool_behavior=ToolBehavior.USE_AND_DONE
    )
    
    # 2. Execute and analyze
    response = await agent.call_llm(
        "What's currently playing?",
        tool_behavior=ToolBehavior.USE_AND_ANALYZE_OUTPUT_AND_DONE
    )
    
    # 3. Multiple tool calls
    response = await agent.call_llm(
        "Play my liked songs and skip to the third track",
        tool_behavior=ToolBehavior.KEEP_USING_UNTIL_DONE
    )
    ```
    """
    
    @abstractmethod
    def __init__(
        self,
        config: Dict[str, Any],
        prompt_folder: str,
        db: Any,
        ontology_manager: Any,
        tts_engine: Optional[Any] = None
    ):
        """Initialize the agent.
        
        Args:
            config: Configuration dictionary
            prompt_folder: Path to prompt templates folder
            db: Database interface instance
            ontology_manager: Ontology manager instance
            tts_engine: Optional text-to-speech engine instance
        """
        pass
    
    @abstractmethod
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template.
        
        Args:
            prompt_name: Name of the prompt template file (without .txt extension)
            context: Variables to pass to the template
            
        Returns:
            Rendered prompt string
        """
        pass
    
    @abstractmethod
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
        """Call the LLM with comprehensive support for different interaction modes.
        
        Args:
            prompt: Either a string prompt or a list of message dictionaries
            temperature: Sampling temperature (0.0 to 1.0)
            system_prompt: Optional system prompt to guide the LLM's behavior
            tool_behavior: How to handle tool usage and outputs
            specific_tools: List of specific tools to make available for this call
            message_history: Previous conversation messages for context
            images: List of (image_data, mime_type) tuples
            videos: List of (video_data, mime_type) tuples
            audios: List of (audio_data, mime_type) tuples
            streaming: Whether to stream the response as it's generated
            tts: Whether to enable text-to-speech for the response
            **kwargs: Additional arguments passed to the LLM
            
        Returns:
            If streaming=True: AsyncIterable[str] yielding response chunks
            If streaming=False: str containing complete response
            
        Message Format:
            Messages should be dictionaries with 'role' and 'content' keys:
            {
                'role': 'user' | 'assistant' | 'system' | 'tool',
                'content': str
            }
        
        Media Support:
            - Images: Common formats like JPEG, PNG, GIF
            - Videos: Common formats like MP4, WebM
            - Audio: Common formats like MP3, WAV
            
        Tool Behaviors:
            - USE_AND_DONE: Returns raw tool output
            - USE_AND_ANALYZE_OUTPUT_AND_DONE: Returns LLM's analysis of tool output
            - KEEP_USING_UNTIL_DONE: Allows multiple tool calls to complete task
            
        Streaming:
            When streaming=True, returns an AsyncIterable that yields response chunks
            as they become available. This enables real-time display of responses.
            
        Text-to-Speech:
            When tts=True, the response will be converted to speech using the configured
            TTS engine. Can be combined with streaming for real-time speech output.
        """
        pass