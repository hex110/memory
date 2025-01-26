"""Agent for curating content based on personality insights."""

import logging
from typing import Dict, Any, List, Optional

from src.agent.base_agent import BaseAgent
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager

# Set up logging
logger = logging.getLogger(__name__)

class CuratorAgent(BaseAgent):
    """Agent that provides content customization recommendations based on personality analysis."""
    
    # Required tools for this agent - we only need read operations
    REQUIRED_TOOLS = ["get_entity", "get_entities"]
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        """Initialize the curator agent."""
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            role="curator"
        )
        
        # Register and validate required tools
        self._register_required_tools()
    
    def _register_required_tools(self):
        """Register and validate the tools required by this agent."""
        # Get all available tool schemas for our role
        tool_schemas = self.db_tools.get_tool_schemas()
        available_tools = {schema["name"]: schema for schema in tool_schemas}
        
        # Validate required tools are available
        missing_tools = [tool for tool in self.REQUIRED_TOOLS if tool not in available_tools]
        if missing_tools:
            raise ValueError(f"Missing required tools: {missing_tools}")
        
        # Register each required tool with its schema
        for tool_name in self.REQUIRED_TOOLS:
            if hasattr(self.db_tools, tool_name):
                tool_func = getattr(self.db_tools, tool_name)
                self.register_tool(tool_name, tool_func, available_tools[tool_name])
            else:
                raise ValueError(f"Tool {tool_name} not implemented in database interface")
    
    def _get_personality_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all relevant personality data from database.
        
        Returns:
            Dict containing traits and patterns
        """
        try:
            return {
                "traits": self.db_tools.get_entities("personality_trait"),
                "patterns": self.db_tools.get_entities("behavioral_pattern")
            }
        except Exception as e:
            logger.error(f"Error fetching personality data: {e}")
            return {"traits": [], "patterns": []}
    
    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a customization request.
        
        Args:
            request_data: The customization request data
            
        Returns:
            Dict containing customization recommendations
        """
        try:
            # Get personality data
            personality_data = self._get_personality_data()
            
            # Prepare context for LLM
            context = {
                "request": request_data,
                "personality_data": personality_data,
                "tools": self.tool_schemas
            }
            
            # Load prompts
            system_prompt = self.load_prompt("curator_system", context)
            query_prompt = self.load_prompt("curator_query", context)
            
            # Call LLM for recommendations
            response = self.call_llm(
                query_prompt,
                temperature=0.7,
                system_prompt=system_prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing curator request: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def execute(self, request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the curator's primary function."""
        if not request_data:
            raise ValueError("Request data is required")
        return self.process_request(request_data) 