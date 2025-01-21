"""Type definitions for analyzer agent structured output."""

from typing import Dict, Any, List
from pydantic import BaseModel, Field

class TraitMetadataModel(BaseModel):
    """Pydantic model for trait metadata."""
    analysis: str = Field(description="Analysis of why this trait is relevant")
    evidence: str = Field(description="Evidence from the conversation supporting this trait")
    manifestation: str = Field(description="How this trait manifests in behavior")
    impact: str = Field(description="The impact of this trait on behavior and relationships")
    relationships: List[str] = Field(description="Related traits or connections")

class TraitModel(BaseModel):
    """Pydantic model for a personality trait."""
    id: str = Field(description="Unique identifier for the trait")
    content: str = Field(description="Description of the trait")
    confidence: float = Field(description="Confidence score between 0 and 1", ge=0, le=1)
    metadata: TraitMetadataModel = Field(description="Additional metadata about the trait")

class AnalysisPlanModel(BaseModel):
    """Pydantic model for the analysis plan."""
    traits_to_update: List[TraitModel] = Field(description="Traits that need to be updated")
    traits_to_add: List[TraitModel] = Field(description="New traits to be added")
    traits_to_remove: List[str] = Field(description="IDs of traits to be removed")

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
                            "description": "Unique identifier for the trait"
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
                            },
                            "required": ["analysis", "evidence", "manifestation", "impact", "relationships"]
                        }
                    },
                    "required": ["id", "content", "confidence", "metadata"]
                }
            },
            "traits_to_add": {
                "type": "array",
                "description": "New traits discovered in this conversation",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the trait"
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
                            },
                            "required": ["analysis", "evidence", "manifestation", "impact", "relationships"]
                        }
                    },
                    "required": ["id", "content", "confidence", "metadata"]
                }
            },
            "traits_to_remove": {
                "type": "array",
                "description": "IDs of traits that are no longer relevant or accurate",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["traits_to_update", "traits_to_add", "traits_to_remove"]
    }
} 