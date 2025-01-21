"""API request and response models."""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field

class ServiceContext(BaseModel):
    """Generic context for any service request."""
    service_type: str = Field(..., description="Type of service making the request (e.g., 'blog', 'scheduler', 'task')")
    request_type: str = Field(..., description="Type of request (e.g., 'customize', 'analyze', 'schedule')")
    user_id: str = Field(..., description="Unique identifier for the user")
    
    # Flexible additional context
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Service-specific parameters"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the request"
    )

class PersonalizationRequest(BaseModel):
    """Generic request model for any personalization service."""
    context: ServiceContext
    content: Dict[str, Any] = Field(
        ...,
        description="The actual content/data to be processed"
    )
    preferences: Optional[List[str]] = Field(
        default_factory=list,
        description="Specific aspects or preferences to consider"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional options for processing"
    )

class ReasoningDetails(BaseModel):
    """Explanation of personalization decisions."""
    main_points: List[str] = Field(..., description="Key points about the decisions made")
    trait_based: Dict[str, str] = Field(
        default_factory=dict,
        description="Decisions based on personality traits"
    )
    pattern_based: Dict[str, str] = Field(
        default_factory=dict,
        description="Decisions based on behavioral patterns"
    )
    additional_notes: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Any additional explanations or notes"
    )

class PersonalizationResponse(BaseModel):
    """Generic response model for any personalization service."""
    status: Literal["success", "error"] = Field(..., description="Status of the request")
    service_type: str = Field(..., description="Type of service that processed the request")
    recommendations: Dict[str, Any] = Field(
        ...,
        description="The personalized recommendations/results"
    )
    reasoning: ReasoningDetails = Field(
        ...,
        description="Explanation of the personalization decisions"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response"
    )

# Example usage for different services:
"""
# Blog Customization:
request = PersonalizationRequest(
    context=ServiceContext(
        service_type="blog",
        request_type="customize",
        user_id="user123",
        parameters={
            "article_topic": "ML Architecture",
            "target_audience": "Software Engineers",
            "estimated_read_time": "15 minutes"
        }
    ),
    content={
        "type": "technical_blog",
        "customization_aspects": ["content_style", "visual_preferences"]
    }
)

# Task Scheduling:
request = PersonalizationRequest(
    context=ServiceContext(
        service_type="scheduler",
        request_type="optimize",
        user_id="user123",
        parameters={
            "timezone": "UTC+2",
            "work_hours": ["9:00", "17:00"]
        }
    ),
    content={
        "tasks": [{"id": "task1", "duration": "2h", "priority": "high"}],
        "preferences": ["focus_time", "break_patterns"]
    }
)

# Learning Path:
request = PersonalizationRequest(
    context=ServiceContext(
        service_type="learning",
        request_type="path",
        user_id="user123",
        parameters={
            "subject": "Machine Learning",
            "current_level": "intermediate"
        }
    ),
    content={
        "goals": ["master_transformers", "deploy_models"],
        "time_commitment": "10h_weekly"
    }
)
""" 