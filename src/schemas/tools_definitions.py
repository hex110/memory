"""Tool definitions and schemas for the system.

This module serves as the central registry for all available tools,
defining their parameters, descriptions, and implementation paths.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class ToolDefinition:
    """Definition of a tool including its parameters and description."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format
    category: str
    implementation: str  # Path to implementation, e.g., "database.get_entity"
    implementation_type: str = "function"  # "function" or "method"
    class_name: Optional[str] = None  # e.g., "DatabaseTools" if method

# Central registry of all available tools
TOOL_REGISTRY = {
    "database.get_entity": ToolDefinition(
        name="get_entity",
        description=(
            "Get a single entity by ID from the database. Returns a dictionary containing "
            "the entity's data if found, or an empty dictionary if not found. "
            "The response will include all fields defined in the entity's schema."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entity to get (e.g., 'activity_raw', 'conversation', 'personality_trait')"
                },
                "entity_id": {
                    "type": "string", 
                    "description": "UUID of the entity to retrieve"
                }
            },
            "required": ["entity_type", "entity_id"]
        },
        category="database",
        implementation="database.get_entity",
        implementation_type="method",
        class_name="DatabaseTools"
    ),
    
    "database.get_entities": ToolDefinition(
        name="get_entities",
        description=(
            "Get all entities of a specific type from the database. Returns a list of "
            "entity dictionaries. Each entity contains all fields defined in its schema. "
            "Use this when you need to analyze patterns across multiple entities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entities to get (e.g., 'activity_raw', 'conversation', 'personality_trait')"
                }
            },
            "required": ["entity_type"]
        },
        category="database",
        implementation="database.get_entities",
        implementation_type="method",
        class_name="DatabaseTools"
    ),
    
    "database.add_entity": ToolDefinition(
        name="add_entity",
        description=(
            "Add a new entity to the database. Returns the UUID of the created entity. "
            "The data must conform to the entity type's schema. Timestamps and IDs are "
            "automatically generated if not provided."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entity to add"
                },
                "data": {
                    "type": "object",
                    "description": "Entity data conforming to the type's schema"
                }
            },
            "required": ["entity_type", "data"]
        },
        category="database",
        implementation="database.add_entity",
        implementation_type="method",
        class_name="DatabaseTools"
    ),
    
    "database.update_entity": ToolDefinition(
        name="update_entity",
        description=(
            "Update an existing entity in the database. The entity must exist. "
            "Only provided fields will be updated. Returns None on success. "
            "The updated data must conform to the entity type's schema."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entity to update"
                },
                "entity_id": {
                    "type": "string",
                    "description": "UUID of the entity to update"
                },
                "data": {
                    "type": "object",
                    "description": "Updated field values conforming to the type's schema"
                }
            },
            "required": ["entity_type", "entity_id", "data"]
        },
        category="database",
        implementation="database.update_entity",
        implementation_type="method",
        class_name="DatabaseTools"
    ),
    
    "database.query_entities": ToolDefinition(
        name="query_entities",
        description=(
            "Query entities with filters and sorting. Returns a list of matching entities. "
            "The query can filter on any field in the entity's schema. "
            "Supports comparison operators (>=, <=, >, <, =, !=) in the query. "
            "Results can be sorted by any field and limited to a maximum count."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Type of entities to query"
                },
                "query": {
                    "type": "object",
                    "description": "Query filters for entity fields"
                },
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort results by"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "Sort order (ascending or descending)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return"
                }
            },
            "required": ["entity_type", "query"]
        },
        category="database",
        implementation="database.query_entities",
        implementation_type="method",
        class_name="DatabaseTools"
    )
}

def get_tool_schemas(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Get function schemas for specified tools in LiteLLM format.
    
    Args:
        tool_names: List of tool names to get schemas for
        
    Returns:
        List of tool schemas in LiteLLM format
    """
    schemas = []
    for name in tool_names:
        if name in TOOL_REGISTRY:
            tool = TOOL_REGISTRY[name]
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
    return schemas

def get_tool_implementations(tool_names: List[str]) -> Dict[str, ToolDefinition]:
    """Get implementation info for specified tools.
    
    Args:
        tool_names: List of tool names to get implementations for
        
    Returns:
        Dict mapping tool names to their ToolDefinition objects
    """
    return {
        name: TOOL_REGISTRY[name]
        for name in tool_names
        if name in TOOL_REGISTRY
    }