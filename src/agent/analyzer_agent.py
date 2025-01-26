"""Agent for analyzing conversations and extracting insights."""

import json
import logging
from typing import Dict, Any, List, Optional

from src.agent.base_agent import BaseAgent
from src.interfaces.postgresql import DatabaseInterface
from src.ontology.manager import OntologyManager
from src.agent.prompts.type_definitions import (
    AnalysisPlanModel,
    ANALYSIS_FUNCTION_SCHEMA
)

# Set up logging
logger = logging.getLogger(__name__)

class AnalyzerAgent(BaseAgent):
    """Agent that analyzes conversations to extract personality traits and patterns."""
    
    # Required tools for this agent
    REQUIRED_TOOLS = ["add_entity", "update_entity", "get_entity", "get_entities", "remove_entity"]
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        """Initialize the analyzer agent."""
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db=db,
            ontology_manager=ontology_manager,
            role="analyzer"
        )
        
        # Register analysis function
        self.register_tool(
            "analyze_conversation",
            self._analyze_conversation_impl,
            ANALYSIS_FUNCTION_SCHEMA
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
    
    def _get_existing_traits(self) -> List[Dict[str, Any]]:
        """Get existing personality traits from database.
        
        Returns:
            List of existing traits with their metadata
        """
        try:
            return self.db_tools.get_entities("personality_trait")
        except Exception as e:
            logger.error(f"Error fetching existing traits: {e}")
            return []
    
    def _analyze_conversation_impl(self, **kwargs) -> Dict[str, Any]:
        """Implementation of the analyze_conversation function.
        
        This is called by the LLM through function calling.
        The response will be validated against AnalysisPlanModel.
        
        Returns:
            Dict containing the analysis plan
        """
        return kwargs
    
    def _generate_trait_id(self, content: str) -> str:
        """Generate a short, consistent ID from trait content.
        
        Args:
            content: The trait content to generate ID from
            
        Returns:
            A short, consistent ID string
        """
        # Take first 3-4 significant words
        words = content.lower().split()[:4]
        # Remove common words and punctuation
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [w for w in words if w not in stop_words]
        # Create base ID from first 2-3 meaningful words
        base_id = '_'.join(words[:3])
        # Clean up any remaining punctuation and normalize
        base_id = ''.join(c if c.isalnum() or c == '_' else '' for c in base_id)
        return base_id[:30]  # Limit length
    
    def _analyze_phase1(self, conv_data: Dict[str, Any]) -> AnalysisPlanModel:
        """First phase: Analyze conversation and create a plan.
        
        Args:
            conv_data: Conversation data including id and content
            
        Returns:
            AnalysisPlanModel containing the analysis plan
            
        Raises:
            ValueError: If analysis fails
        """
        logger.debug("=== Starting Analysis Phase 1 ===")
        
        # Prepare context for analysis
        context = {
            "conversation": conv_data,
            "existing_traits": self._get_existing_traits(),
            "tools": self.tool_schemas
        }
        
        # Load prompts
        system_prompt = self.load_prompt("analyzer_system", context)
        analysis_prompt = self.load_prompt("analyzer_phase1", context)
        
        # Call LLM with function calling
        logger.debug("Requesting analysis with function calling...")
        response = self.call_llm(
            analysis_prompt,
            temperature=0.7,
            system_prompt=system_prompt
        )
        
        # Log the LLM response
        logger.info(f"LLM Analysis Response: {response}")
        
        # Parse and validate response
        try:
            return self.validate_function_response(response, AnalysisPlanModel)
        except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")
            raise ValueError(f"Failed to parse analysis response: {str(e)}")
    
    def _execute_phase2(self, conv_data: Dict[str, Any], analysis_plan: AnalysisPlanModel) -> Dict[str, Any]:
        """Second phase: Execute the analysis plan.
        
        Args:
            conv_data: Original conversation data
            analysis_plan: Plan from phase 1
            
        Returns:
            Dict with execution status
        """
        logger.debug("=== Starting Analysis Phase 2 ===")
        
        try:
            # Prepare context for execution
            context = {
                "conversation": conv_data,
                "analysis_plan": analysis_plan,
                "tools": self.tool_schemas
            }
            
            # Load prompts
            system_prompt = self.load_prompt("analyzer_system", context)
            execution_prompt = self.load_prompt("analyzer_phase2", context)
            
            # Call LLM to execute plan with function calling
            logger.debug("Executing analysis plan with LLM...")
            response = self.call_llm(
                execution_prompt,
                temperature=0.3,  # Lower temperature for more precise execution
                system_prompt=system_prompt
            )
            
            # Log the LLM response
            logger.info(f"LLM Execution Response: {response}")
            
            # Execute the analysis plan
            
            # 1. Process removals
            for trait_id in analysis_plan.traits_to_remove:
                try:
                    self.db_tools.remove_entity("personality_trait", trait_id)
                    logger.info(f"Removed trait: {trait_id}")
                except Exception as e:
                    logger.error(f"Failed to remove trait {trait_id}: {e}")
            
            # 2. Process updates
            for trait in analysis_plan.traits_to_update:
                try:
                    data = {
                        "id": trait.id,
                        "content": trait.content,
                        "confidence": trait.confidence or 0.8,
                        "metadata": trait.metadata.dict() if trait.metadata else {}
                    }
                    self.db_tools.update_entity("personality_trait", trait.id, data)
                    logger.info(f"Updated trait: {trait.id}")
                except Exception as e:
                    logger.error(f"Failed to update trait {trait.id}: {e}")
            
            # 3. Process additions
            for trait in analysis_plan.traits_to_add:
                try:
                    # Generate a unique ID for new traits
                    trait_id = self._generate_trait_id(trait.content)
                    data = {
                        "id": trait_id,
                        "content": trait.content,
                        "confidence": trait.confidence or 0.8,
                        "metadata": trait.metadata.dict() if trait.metadata else {}
                    }
                    self.db_tools.add_entity("personality_trait", trait_id, data)
                    logger.info(f"Added trait: {trait_id}")
                except Exception as e:
                    logger.error(f"Failed to add trait: {e}")
            
            # After execution, mark conversation as analyzed
            try:
                conv_data["analyzed"] = True
                self.db_tools.update_entity("conversation", conv_data["id"], conv_data)
            except Exception as e:
                logger.error(f"Failed to mark conversation as analyzed: {e}")
            
            return {
                "status": "success",
                "conversation_id": conv_data.get("id")
            }
            
        except Exception as e:
            logger.error(f"Error during execution phase: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def analyze_conversation(self, conv_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a conversation using the two-phase approach.
        
        Args:
            conv_data: Conversation data including id and content
            
        Returns:
            Dict with status and conversation id
        """
        try:
            # Phase 1: Analysis
            analysis_plan = self._analyze_phase1(conv_data)
            
            # Phase 2: Execution
            return self._execute_phase2(conv_data, analysis_plan)
                
        except Exception as e:
            logger.error(f"Error during conversation analysis: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def execute(self, conv_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the analyzer's primary function."""
        if not conv_data:
            raise ValueError("Conversation data is required")
        return self.analyze_conversation(conv_data) 