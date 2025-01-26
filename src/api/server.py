"""FastAPI server implementation."""

import logging
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json_repair

from src.api.models import PersonalizationRequest, PersonalizationResponse, ReasoningDetails
from src.agent.curator_agent import CuratorAgent
from src.database.postgresql import PostgreSQLDatabase
from src.ontology.manager import OntologyManager
from src.utils.config import load_config

# Set up logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Personalization API",
    description="API for personalizing various services based on user traits",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for components
curator_agent: CuratorAgent = None
config: Dict[str, Any] = None

@app.on_event("startup")
async def startup_event():
    """Initialize components on server startup."""
    global curator_agent, config
    try:
        # Load configuration
        config = load_config("src/config.json")
        
        # Initialize database
        db = PostgreSQLDatabase(config["database"])
        
        # Initialize ontology manager
        ontology = OntologyManager()
        
        # Initialize curator agent
        curator_agent = CuratorAgent(
            config_path="src/config.json",
            prompt_folder="src/agent/prompts",
            db=db,
            ontology_manager=ontology
        )
        
        logger.info("Server initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise

def parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse and validate LLM response.
    
    Args:
        response: Raw response from LLM
        
    Returns:
        Parsed and validated response dictionary
        
    Raises:
        ValueError: If response cannot be parsed or is invalid
    """
    try:
        # Clean up the response - remove markdown if present
        cleaned = response.strip('`').strip()
        if cleaned.startswith('json'):
            cleaned = cleaned[4:]
            
        # Try to repair any JSON issues and load/parse it
        parsed_and_repaired = json_repair.loads(cleaned)
        
        # Basic validation
        required_fields = {"status", "service_type", "recommendations", "reasoning"}
        if not all(field in parsed_and_repaired for field in required_fields):
            raise ValueError("Missing required fields in response")
            
        return parsed_and_repaired
        
    except Exception as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.debug(f"Raw response: {response}")
        raise ValueError(f"Invalid response format: {str(e)}")

@app.post("/personalize", response_model=PersonalizationResponse)
async def personalize(request: PersonalizationRequest):
    """Generic endpoint for all personalization requests."""
    logger.info(f"Received personalization request for user {request.context.user_id}")
    logger.info(f"Request details: {json.dumps(request.dict(), indent=2)}")
    
    try:
        # Process request through curator agent
        logger.info("Processing request through curator agent...")
        raw_result = curator_agent.execute(request.dict())
        
        # Parse and validate the response
        logger.info("Parsing and validating response...")
        result = parse_llm_response(raw_result)
        
        # Transform into our response model
        response = PersonalizationResponse(
            status=result["status"],
            service_type=result["service_type"],
            recommendations=result["recommendations"],
            reasoning=ReasoningDetails(
                main_points=result["reasoning"]["main_points"],
                trait_based=result["reasoning"]["trait_based"],
                pattern_based=result["reasoning"]["pattern_based"],
                additional_notes=result["reasoning"].get("additional_notes", {})
            ),
            metadata={
                "request_type": request.context.request_type,
                "processed_at": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
        )
        
        logger.info("Successfully processed request")
        logger.info(f"Response: {json.dumps(response.dict(), indent=2)}")
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        logger.error(f"Raw response that failed validation: {raw_result}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid response format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing personalization request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    response = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
    logger.info(f"Health check response: {json.dumps(response, indent=2)}")
    return response 