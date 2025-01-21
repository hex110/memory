"""API Interface for the Memory System.

This module provides documentation and helper functions for interacting with the Memory System API.
It includes examples of how to structure requests and what responses to expect.

Example Usage:
    ```python
    import requests
    
    # Create a personalization request
    request = {
        "context": {
            "service_type": "blog",
            "request_type": "customize",
            "user_id": "user123",
            "parameters": {
                "content_type": "technical",
                "target_audience": "developers"
            }
        },
        "content": {
            "type": "technical_blog",
            "customization_aspects": ["content_style", "visual_preferences"]
        },
        "preferences": ["detailed", "code_examples"],
        "options": {
            "style": ["tutorial", "deep-dive"]
        }
    }
    
    # Send request to API
    response = requests.post(
        "http://localhost:8000/personalize",
        json=request
    )
    
    # Handle response
    if response.status_code == 200:
        result = response.json()
        print(f"Recommendations: {result['recommendations']}")
    ```
"""

from typing import Dict, List, Any, Optional
import json
import logging
import requests
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)

class APIEndpoint:
    """Base class for API endpoint documentation."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

class PersonalizationAPI(APIEndpoint):
    """Interface for the /personalize endpoint.
    
    This endpoint handles personalization requests for various services like:
    - Blog content customization
    - Task scheduling optimization
    - Learning path recommendations
    
    The endpoint processes user traits and patterns to provide personalized recommendations.
    """
    
    ENDPOINT = "/personalize"
    
    @staticmethod
    def create_request(
        service_type: str,
        request_type: str,
        user_id: str,
        content: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
        preferences: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a properly formatted personalization request.
        
        Args:
            service_type: Type of service (e.g., "blog", "scheduler", "learning")
            request_type: Type of request (e.g., "customize", "optimize", "recommend")
            user_id: Unique identifier for the user
            content: The content to be processed
            parameters: Additional service-specific parameters
            preferences: List of user preferences to consider
            options: Additional options for processing
            
        Returns:
            Dict containing the formatted request
            
        Example:
            ```python
            request = PersonalizationAPI.create_request(
                service_type="blog",
                request_type="customize",
                user_id="user123",
                content={
                    "type": "technical_blog",
                    "customization_aspects": ["content_style"]
                },
                parameters={
                    "target_audience": "developers"
                }
            )
            ```
        """
        request = {
            "context": {
                "service_type": service_type,
                "request_type": request_type,
                "user_id": user_id,
                "parameters": parameters or {}
            },
            "content": content,
            "preferences": preferences or [],
            "options": options or {}
        }
        
        logger.info(f"Created personalization request for user {user_id}:")
        logger.info(json.dumps(request, indent=2))
        
        return request
    
    def send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a personalization request to the API.
        
        Args:
            request_data: The request data created by create_request()
            
        Returns:
            Dict containing the API response
            
        Raises:
            requests.exceptions.RequestException: If the request fails
            
        Response Structure:
            {
                "status": "success" | "error",
                "service_type": str,
                "recommendations": {
                    // Service-specific recommendations
                },
                "reasoning": {
                    "main_points": List[str],
                    "trait_based": Dict[str, str],
                    "pattern_based": Dict[str, str],
                    "additional_notes": Dict[str, Any]
                },
                "metadata": {
                    "processed_at": str (ISO timestamp),
                    "version": str
                }
            }
        """
        logger.info(f"Sending request to {self.base_url}{self.ENDPOINT}")
        logger.debug(f"Request data: {json.dumps(request_data, indent=2)}")
        
        try:
            response = requests.post(
                f"{self.base_url}{self.ENDPOINT}",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info("Received successful response:")
            logger.info(json.dumps(result, indent=2))
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error response: {e.response.text}")
            raise

class HealthAPI(APIEndpoint):
    """Interface for the /health endpoint.
    
    This endpoint provides health check information about the API service.
    """
    
    ENDPOINT = "/health"
    
    def check_health(self) -> Dict[str, Any]:
        """Check the health status of the API.
        
        Returns:
            Dict containing health status information
            
        Response Structure:
            {
                "status": "healthy",
                "timestamp": str (ISO timestamp),
                "version": str
            }
        """
        logger.info(f"Checking health at {self.base_url}{self.ENDPOINT}")
        
        try:
            response = requests.get(f"{self.base_url}{self.ENDPOINT}")
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Health check result: {json.dumps(result, indent=2)}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Health check failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error response: {e.response.text}")
            raise

# Example Usage Documentation

EXAMPLE_BLOG_REQUEST = {
    "context": {
        "service_type": "blog",
        "request_type": "customize",
        "user_id": "user123",
        "parameters": {
            "content_type": "technical",
            "target_audience": "developers",
            "estimated_read_time": "15 minutes"
        }
    },
    "content": {
        "type": "technical_blog",
        "customization_aspects": [
            "content_style",
            "visual_preferences",
            "code_examples"
        ]
    },
    "preferences": [
        "Prefers detailed technical explanations",
        "Values code examples",
        "Interested in performance optimization"
    ],
    "options": {
        "style": ["tutorial", "deep-dive", "quick-tips"],
        "format": ["markdown", "jupyter"]
    }
}

EXAMPLE_SCHEDULER_REQUEST = {
    "context": {
        "service_type": "scheduler",
        "request_type": "optimize",
        "user_id": "user123",
        "parameters": {
            "timezone": "UTC+2",
            "work_hours": ["9:00", "17:00"]
        }
    },
    "content": {
        "tasks": [
            {
                "id": "task1",
                "title": "Code Review",
                "duration": "2h",
                "priority": "high"
            }
        ]
    },
    "preferences": [
        "Prefers focused work in the morning",
        "Needs regular breaks",
        "Most productive in 2-hour blocks"
    ],
    "options": {
        "scheduling_strategy": ["energy_based", "priority_based"],
        "break_preferences": ["pomodoro", "flexible"]
    }
}

EXAMPLE_LEARNING_REQUEST = {
    "context": {
        "service_type": "learning",
        "request_type": "path",
        "user_id": "user123",
        "parameters": {
            "subject": "Machine Learning",
            "current_level": "intermediate",
            "time_commitment": "10h_weekly"
        }
    },
    "content": {
        "goals": [
            "master_transformers",
            "deploy_models"
        ],
        "current_skills": [
            "python",
            "basic_ml",
            "deep_learning_fundamentals"
        ]
    },
    "preferences": [
        "Hands-on learning style",
        "Prefers project-based approach",
        "Interested in practical applications"
    ],
    "options": {
        "learning_style": ["project_based", "tutorial_based"],
        "resource_types": ["videos", "documentation", "exercises"]
    }
} 