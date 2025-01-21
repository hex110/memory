"""Type definitions for analyzer agent structured output."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class TraitMetadataModel(BaseModel):
    """Pydantic model for trait metadata."""
    analysis: Optional[str] = Field(None, description="Analysis of why this trait is relevant")
    evidence: Optional[str] = Field(None, description="Evidence from the conversation supporting this trait")
    manifestation: Optional[str] = Field(None, description="How this trait manifests in behavior")
    impact: Optional[str] = Field(None, description="The impact of this trait on behavior and relationships")
    relationships: Optional[List[str]] = Field(None, description="Related traits or connections")

class TraitModel(BaseModel):
    """Pydantic model for a personality trait."""
    id: Optional[str] = Field(None, description="Unique identifier for the trait", maxLength=30, pattern="^[a-z0-9_]+$")
    content: str = Field(description="Description of the trait")
    confidence: Optional[float] = Field(0.8, description="Confidence score between 0 and 1", ge=0, le=1)
    metadata: Optional[TraitMetadataModel] = Field(None, description="Additional metadata about the trait")

class BehavioralPatternMetadataModel(BaseModel):
    """Pydantic model for behavioral pattern metadata."""
    context: Optional[str] = Field(None, description="Context in which the pattern occurs")
    frequency: Optional[str] = Field(None, description="How often the pattern occurs")
    triggers: Optional[str] = Field(None, description="What triggers this behavioral pattern")
    analysis: Optional[str] = Field(None, description="Analysis of why this pattern is relevant")
    impact: Optional[str] = Field(None, description="The impact of this pattern on behavior")
    evidence: Optional[str] = Field(None, description="Evidence supporting this pattern")

class BehavioralPatternModel(BaseModel):
    """Pydantic model for a behavioral pattern."""
    id: Optional[str] = Field(None, description="Unique identifier for the pattern", maxLength=30, pattern="^[a-z0-9_]+$")
    type: str = Field(description="Type of behavioral pattern")
    content: str = Field(description="Description of the pattern")
    confidence: Optional[float] = Field(0.8, description="Confidence score between 0 and 1", ge=0, le=1)
    metadata: Optional[BehavioralPatternMetadataModel] = Field(None, description="Additional metadata about the pattern")

class RelationshipMetadataModel(BaseModel):
    """Pydantic model for relationship metadata."""
    nature: Optional[str] = Field(None, description="Nature of the relationship")
    strength: Optional[float] = Field(None, description="Strength of the relationship", ge=0, le=1)
    evidence: Optional[str] = Field(None, description="Evidence supporting this relationship")

class RelationshipModel(BaseModel):
    """Pydantic model for a relationship between entities."""
    id: Optional[str] = Field(None, description="Unique identifier for the relationship", maxLength=30, pattern="^[a-z0-9_]+$")
    type: str = Field(description="Type of relationship")
    from_id: str = Field(description="ID of the source entity")
    to_id: str = Field(description="ID of the target entity")
    confidence: Optional[float] = Field(0.8, description="Confidence score between 0 and 1", ge=0, le=1)
    metadata: Optional[RelationshipMetadataModel] = Field(None, description="Additional metadata about the relationship")

class AnalysisPlanModel(BaseModel):
    """Pydantic model for the analysis plan."""
    traits_to_update: List[TraitModel] = Field(default_factory=list, description="Traits that need to be updated")
    traits_to_add: List[TraitModel] = Field(default_factory=list, description="New traits to be added")
    traits_to_remove: List[str] = Field(default_factory=list, description="IDs of traits to be removed")

# Function schemas for LLM
ANALYSIS_FUNCTION_SCHEMA = {
    "name": "analyze_conversation",
    "description": "Analyze a conversation to identify personality traits and behavioral patterns",
    "parameters": {
        "type": "object",
        "properties": {
            "traits_to_update": {
                "type": "array",
                "description": "Existing traits that need updating with new evidence",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the trait",
                            "maxLength": 30,
                            "pattern": "^[a-z0-9_]+$"
                        },
                        "content": {
                            "type": "string",
                            "description": "Description of the trait"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score between 0 and 1",
                            "minimum": 0,
                            "maximum": 1
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata about the trait",
                            "properties": {
                                "analysis": {
                                    "type": "string",
                                    "description": "Analysis of why this trait is relevant"
                                },
                                "evidence": {
                                    "type": "string",
                                    "description": "Evidence from the conversation supporting this trait"
                                },
                                "manifestation": {
                                    "type": "string",
                                    "description": "How this trait manifests in behavior"
                                },
                                "impact": {
                                    "type": "string",
                                    "description": "The impact on behavior and relationships"
                                },
                                "relationships": {
                                    "type": "array",
                                    "description": "Related traits or connections",
                                    "items": {
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    },
                    "required": ["content"]
                }
            },
            "traits_to_add": {
                "type": "array",
                "description": "New traits discovered in this conversation",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Description of the trait"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata about the trait",
                            "properties": {
                                "analysis": {
                                    "type": "string",
                                    "description": "Analysis of why this trait is relevant"
                                },
                                "evidence": {
                                    "type": "string",
                                    "description": "Evidence from the conversation supporting this trait"
                                },
                                "manifestation": {
                                    "type": "string",
                                    "description": "How this trait manifests in behavior"
                                },
                                "impact": {
                                    "type": "string",
                                    "description": "The impact on behavior and relationships"
                                },
                                "relationships": {
                                    "type": "array",
                                    "description": "Related traits or connections",
                                    "items": {
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    },
                    "required": ["content"]
                }
            },
            "traits_to_remove": {
                "type": "array",
                "description": "IDs of traits that are no longer relevant or accurate",
                "items": {
                    "type": "string"
                }
            }
        }
    }
} 