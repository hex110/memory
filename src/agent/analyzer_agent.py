"""Agent for analyzing conversations and managing knowledge."""

from typing import Any, Dict, List, Optional
from src.agent.base_agent import BaseAgent
import json

class AnalyzerAgent(BaseAgent):
    """Agent that analyzes conversations and extracts/manages knowledge.
    
    This agent is responsible for:
    1. Analyzing conversation content
    2. Extracting key information
    3. Creating and updating knowledge entities
    4. Managing relationships between entities
    """
    
    def __init__(self, **kwargs):
        """Initialize the AnalyzerAgent.
        
        Args:
            **kwargs: Arguments to pass to the BaseAgent constructor
        """
        # Remove role if it's in kwargs to avoid duplication
        kwargs.pop('role', None)
        super().__init__(role="analyzer", **kwargs)  # Use analyzer role for read/write access
        
        # Initialize conversation state
        self.current_conversation = None
        self.extracted_entities = []
    
    def analyze_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Analyze a conversation and extract knowledge.
        
        Args:
            conversation_id: ID of the conversation to analyze
            
        Returns:
            Dict containing analysis results
        """
        # Get conversation from database
        conversation = self.db_tools.get_entity("conversation", conversation_id)
        self.current_conversation = conversation
        
        # Load and render the analysis prompt
        context = {
            "conversation": conversation,
            "existing_entities": self.db_tools.get_entities("knowledge"),
            "schema": self.db_tools.get_schema()
        }
        
        prompt = self.load_prompt("analyze_conversation", context)
        
        # Get analysis from LLM
        response = self.call_llm(
            prompt,
            temperature=0.7,
            system_prompt="You are an expert at analyzing conversations and extracting structured knowledge."
        )
        
        return self.parse_response(response)
    
    def execute(self, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the agent's primary analysis function.
        
        Args:
            conversation_id: Optional ID of conversation to analyze
            
        Returns:
            Analysis results
        """
        if conversation_id:
            return self.analyze_conversation(conversation_id)
        
        # If no conversation_id provided, get most recent unanalyzed conversation
        conversations = self.db_tools.get_entities("conversation")
        for conv in conversations:
            if not conv.get("analyzed", False):
                return self.analyze_conversation(conv["id"])
        
        return {"status": "no_unanalyzed_conversations"}
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM's analysis response.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Structured analysis results
        """
        try:
            # For now, assume response is JSON formatted
            # Later we can add more sophisticated parsing
            results = json.loads(response)
            
            # Store extracted entities
            self.extracted_entities = results.get("entities", [])
            
            # Update conversation as analyzed
            if self.current_conversation:
                self.db_tools.update_entity(
                    "conversation",
                    self.current_conversation["id"],
                    {"analyzed": True}
                )
            
            return results
        except json.JSONDecodeError:
            # If response isn't JSON, return as raw text for now
            return {"raw_analysis": response} 