"""Interface definition for agents.

This module defines the base interface that all agents must implement. The agent system
is designed around a few key concepts:

1. Function Calling:
   - Agents use LLM function calling for structured interactions
   - Each agent registers tools that the LLM can call
   - Tools are validated against JSON schemas

2. Two-Phase Operations:
   - Phase 1: Analysis and planning
   - Phase 2: Execution of the plan
   
3. Prompt Management:
   - Agents use Jinja2 templates for prompts
   - Prompts are organized by phase
   - Context is passed to prompts for rendering

Example of creating a new agent:

```python
class MyAgent(BaseAgent):
    # Required tools this agent needs
    REQUIRED_TOOLS = ["get_entity", "update_entity"]
    
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: DatabaseInterface,
        ontology_manager: OntologyManager
    ):
        # Initialize with role
        super().__init__(
            config_path=config_path,
            prompt_folder=prompt_folder,
            db_interface=db_interface,
            ontology_manager=ontology_manager,
            role="my_role"
        )
        
        # Register any additional tools beyond database tools
        self.register_tool(
            "my_custom_tool",
            self._my_tool_impl,
            MY_TOOL_SCHEMA
        )
    
    def _analyze_phase1(self, data: Dict[str, Any]) -> PydanticModel:
        '''First phase: Analysis and planning'''
        # 1. Load prompts
        system_prompt = self.load_prompt("system", {"context": data})
        analysis_prompt = self.load_prompt("phase1", {"context": data})
        
        # 2. Call LLM with function calling
        response = self.call_llm(
            analysis_prompt,
            temperature=0.7,
            system_prompt=system_prompt
        )
        
        # 3. Validate response with Pydantic
        return self.validate_function_response(response, MyPlanModel)
    
    def _execute_phase2(self, data: Dict[str, Any], plan: PydanticModel) -> Dict[str, Any]:
        '''Second phase: Execute the plan'''
        try:
            # Execute plan using registered tools
            for action in plan.actions:
                self.available_tools[action.tool](**action.parameters)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        '''Main execution flow'''
        if not data:
            raise ValueError("Data is required")
            
        # Run two-phase execution
        plan = self._analyze_phase1(data)
        return self._execute_phase2(data, plan)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable

# Type aliases
ToolSchema = Dict[str, Any]

class AgentInterface(ABC):
    """Base interface for all agents in the system.
    
    This interface defines the core functionality that all agents must implement.
    Most agents should inherit from BaseAgent rather than implementing this directly,
    as BaseAgent provides common functionality for:
    - LLM interaction with function calling
    - Tool registration and management
    - Prompt loading and rendering
    - Response validation
    - Error handling
    """
    
    @abstractmethod
    def __init__(
        self,
        config_path: str,
        prompt_folder: str,
        db_interface: Any,
        ontology_manager: Any,
        role: str
    ):
        """Initialize the agent.
        
        Args:
            config_path: Path to config file with LLM and database settings
            prompt_folder: Path to folder containing prompt templates
            db_interface: Database interface instance
            ontology_manager: Ontology manager instance
            role: Agent role for determining available tools
            
        Required prompt files in prompt_folder:
            - system.txt: System prompt defining agent's role
            - phase1.txt: Analysis phase prompt
            - phase2.txt: Execution phase prompt (if using two-phase approach)
        """
        pass
    
    @property
    @abstractmethod
    def available_tools(self) -> Dict[str, Callable]:
        """Get available tools that can be called by the LLM.
        
        Returns:
            Dict mapping tool names to their implementations
            
        Example:
            {
                "get_entity": self.db_tools.get_entity,
                "my_custom_tool": self._my_tool_impl
            }
        """
        pass
    
    @property
    @abstractmethod
    def tool_schemas(self) -> List[ToolSchema]:
        """Get JSON schemas for available tools.
        
        These schemas define the interface for LLM function calling.
        
        Returns:
            List of tool schemas in OpenAPI format
            
        Example schema:
            {
                "name": "get_entity",
                "description": "Get entity by ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "description": "Type of entity"
                        },
                        "entity_id": {
                            "type": "string",
                            "description": "Entity ID"
                        }
                    },
                    "required": ["entity_type", "entity_id"]
                }
            }
        """
        pass
    
    @abstractmethod
    def register_tool(self, name: str, func: Callable, schema: ToolSchema) -> None:
        """Register a new tool for LLM function calling.
        
        Args:
            name: Name of the tool (used by LLM to call it)
            func: The tool's implementation
            schema: JSON schema defining the tool's interface
            
        The schema must follow OpenAPI format and define:
        - Tool name and description
        - Parameters and their types
        - Required parameters
        
        Example:
            agent.register_tool(
                "my_tool",
                self._my_tool_impl,
                {
                    "name": "my_tool",
                    "description": "Does something useful",
                    "parameters": {...}
                }
            )
        """
        pass
    
    @abstractmethod
    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template.
        
        Args:
            prompt_name: Name of the prompt template file (without .txt)
            context: Variables to pass to the template
            
        Returns:
            Rendered prompt string
            
        Example:
            prompt = agent.load_prompt(
                "phase1",
                {
                    "data": input_data,
                    "tools": self.tool_schemas
                }
            )
        """
        pass
    
    @abstractmethod
    def call_llm(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Call the LLM with function calling support.
        
        Args:
            prompt: The main prompt to send
            temperature: Sampling temperature (0.0-1.0)
            system_prompt: Optional system prompt
            **kwargs: Additional arguments for the LLM
            
        Returns:
            The LLM's response, either:
            - Function call result if tools were used
            - Direct response if no tools were used
            
        The response will be validated if a Pydantic model is provided
        in kwargs["response_format"].
        
        Example:
            response = agent.call_llm(
                prompt="Analyze this data...",
                temperature=0.7,
                system_prompt=system_prompt
            )
        """
        pass
    
    @abstractmethod
    def execute(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the agent's primary function.
        
        This is the main entry point for agent execution. It should:
        1. Validate input data
        2. Run the analysis phase
        3. Execute the resulting plan
        4. Return results
        
        Args:
            data: Input data needed for execution
            
        Returns:
            Results of the execution
            
        Example:
            result = agent.execute({"id": "123", "content": "..."})
        """
        pass
