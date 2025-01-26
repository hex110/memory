"""Tool definitions and schemas for the system."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from google.genai import types

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Dict[str, Any]]
    required_params: List[str]
    category: str
    implementation: str
    implementation_type: str = "function"
    class_name: Optional[str] = None
    prompt_hint: Optional[str] = None

# Common object schemas
ENTITY_DATA_SCHEMA = {
    "type": "OBJECT",
    "description": "Entity data fields",
    "properties": {
        "session_id": {"type": "STRING", "description": "UUID of the session"},
        "created_at": {"type": "STRING", "description": "ISO timestamp"},
        "updated_at": {"type": "STRING", "description": "ISO timestamp"},
        "created_by": {"type": "STRING", "description": "Creator identifier"},
        "updated_by": {"type": "STRING", "description": "Updater identifier"},
    }
}

QUERY_FILTERS_SCHEMA = {
    "type": "OBJECT",
    "description": "Query filter conditions",
    "properties": {
        "session_id": {"type": "STRING", "description": "Filter by session ID"},
        "created_at": {
            "type": "OBJECT",
            "description": "Timestamp filters",
            "properties": {
                ">=": {"type": "STRING", "description": "After timestamp (inclusive)"},
                "<=": {"type": "STRING", "description": "Before timestamp (inclusive)"},
                ">": {"type": "STRING", "description": "After timestamp (exclusive)"},
                "<": {"type": "STRING", "description": "Before timestamp (exclusive)"}
            }
        },
        "analysis_type": {"type": "STRING", "description": "Type of analysis"},
    }
}

TOOL_REGISTRY = {
    "database.query_entities": ToolDefinition(
        name="query_entities",
        description="Query and filter entities from the database with sorting options",
        parameters={
            "entity_type": {
                "type": "STRING",
                "description": "Type of entities to query"
            },
            "query": QUERY_FILTERS_SCHEMA,
            "sort_by": {
                "type": "STRING",
                "description": "Field to sort results by"
            },
            "sort_order": {
                "type": "STRING",
                "description": "Sort order (asc/desc)"
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of results"
            }
        },
        required_params=["entity_type", "query"],
        category="database",
        implementation="database.query_entities",
        implementation_type="method",
        class_name="DatabaseTools",
        prompt_hint=(
            "Use query_entities for retrieving and filtering data. Supports comparison operators "
            "(>=, <=, >, <, =, !=) in query filters. Always sort by timestamp fields when "
            "order matters. The response will be a list of matching entities."
        )
    ),
    
    "database.add_entity": ToolDefinition(
        name="add_entity",
        description="Create a new entity in the database",
        parameters={
            "entity_type": {
                "type": "STRING",
                "description": "Type of entity to add"
            },
            "data": ENTITY_DATA_SCHEMA
        },
        required_params=["entity_type", "data"],
        category="database",
        implementation="database.add_entity",
        implementation_type="method",
        class_name="DatabaseTools",
        prompt_hint=(
            "Use add_entity to create new records. Timestamps and IDs are auto-generated if not provided. "
            "Ensure data matches the entity type's schema requirements."
        )
    ),
    
    "database.update_entity": ToolDefinition(
        name="update_entity",
        description="Update an existing entity in the database",
        parameters={
            "entity_type": {
                "type": "STRING",
                "description": "Type of entity to update"
            },
            "entity_id": {
                "type": "STRING",
                "description": "UUID of entity"
            },
            "data": ENTITY_DATA_SCHEMA
        },
        required_params=["entity_type", "entity_id", "data"],
        category="database",
        implementation="database.update_entity",
        implementation_type="method",
        class_name="DatabaseTools",
        prompt_hint=(
            "Use update_entity to modify existing records. Only provided fields will be updated. "
            "The entity must exist and data must conform to schema requirements."
        )
    ),

    "spotify.spotify_control": ToolDefinition(
        name="spotify_control",
        description="Control Spotify playback and manage your library",
        parameters={
            "action": {
                "type": "STRING",
                "description": "The action to perform",
                "enum": [
                    "play", "pause", "next", "previous", "like", 
                    "unlike", "like_current", "unlike_current",
                    "play_saved_tracks", "get_playlists", "play_playlist"
                ]
            },
            "track_id": {
                "type": "STRING", 
                "description": "The Spotify ID of the track (required for 'like' and 'unlike')"
            },
            "playlist_id": {
                "type": "STRING",
                "description": "The Spotify ID of the playlist (required for 'play_playlist')"
            }
        },
        required_params=["action"],
        category="spotify",
        implementation="spotify.handle_spotify_action",
        implementation_type="function",
        prompt_hint=(
            "You can control Spotify playback and manage the user's library. "
        "Available actions: 'play', 'pause', 'next', 'previous', 'like_current', 'unlike_current', 'play_saved_tracks', 'get_playlists', 'play_playlist'. "
        "For 'like' and 'unlike', provide a 'track_id'. "
        "For 'play_playlist', provide a 'playlist_id'. "
        "Use 'get_playlists' to get a list of playlists first. "
            "Use 'like_current' or 'unlike_current' to like or unlike the currently playing song, respectively."
        )
    )
}

def get_tool_declarations(tool_names: List[str]) -> List[types.Tool]:
    declarations = []
    for name in tool_names:
        if name in TOOL_REGISTRY:
            tool = TOOL_REGISTRY[name]
            schema_params = {}
            for name, params in tool.parameters.items():
                schema_params[name] = {
                    "type": params["type"],
                    "description": params["description"]
                }
                if "properties" in params:
                    schema_params[name]["properties"] = params["properties"]
                    
            function = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=types.Schema(
                    type="OBJECT",
                    properties=schema_params,
                    required=tool.required_params
                )
            )
            declarations.append(types.Tool(function_declarations=[function]))
    return declarations

def get_tool_implementations(tool_names: List[str]) -> Dict[str, ToolDefinition]:
    return {
        name: TOOL_REGISTRY[name]
        for name in tool_names
        if name in TOOL_REGISTRY
    }

def get_tool_prompts(tool_names: List[str]) -> str:
    prompts = []
    for name in tool_names:
        if name in TOOL_REGISTRY and TOOL_REGISTRY[name].prompt_hint:
            prompts.append(TOOL_REGISTRY[name].prompt_hint)
    return "\n\n".join(prompts)