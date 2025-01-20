"""Main entry point for the memory system."""

import os
import json
import logging
import psycopg2
from typing import Dict, Any, Optional
from pathlib import Path

from src.database.relational_db import PostgreSQLDatabase
from src.ontology.ontology_manager import OntologyManager
from src.agent.analyzer_agent import AnalyzerAgent
from src.utils.config import load_config, ConfigError
from src.utils.exceptions import DatabaseError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_initial_schema() -> Dict[str, Any]:
    """Get initial schema for the ontology.
    
    This defines the structure of our knowledge base.
    """
    return {
        "conversation": {
            "description": "A conversation between user and assistant",
            "properties": {
                "id": {"type": "string"},
                "content": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "analyzed": {"type": "boolean", "default": False}
            }
        },
        "knowledge": {
            "description": "A piece of extracted knowledge",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "content": {"type": "string"},
                "source_conversation": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
        },
        "relationship": {
            "description": "A relationship between two pieces of knowledge",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "from_id": {"type": "string"},
                "to_id": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
        }
    }

def verify_postgres(config: Dict[str, Any]) -> None:
    """Verify PostgreSQL is running and database exists.
    
    Args:
        config: Database configuration
        
    Raises:
        DatabaseError: If PostgreSQL is not accessible or database cannot be created
    """
    db_config = config["database"]
    
    # First try to connect to PostgreSQL
    try:
        # Connect to default database to check PostgreSQL is running
        conn = psycopg2.connect(
            host=db_config["host"],
            database="postgres",
            user=db_config["user"],
            password=db_config["password"]
        )
        conn.autocommit = True
        
        # Check if our database exists
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", 
                       (db_config["database"],))
            exists = cur.fetchone()
            
            if not exists:
                logger.info(f"Creating database {db_config['database']}...")
                # Close existing connections to create database
                conn.close()
                
                # Reconnect and create database
                conn = psycopg2.connect(
                    host=db_config["host"],
                    database="postgres",
                    user=db_config["user"],
                    password=db_config["password"]
                )
                conn.autocommit = True
                
                with conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE {db_config['database']}")
                logger.info("Database created successfully")
        
        conn.close()
        
    except psycopg2.OperationalError as e:
        if "Connection refused" in str(e):
            raise DatabaseError(
                "\nPostgreSQL is not running. Please:\n"
                "1. Install PostgreSQL if not installed:\n"
                "   - Arch Linux: sudo pacman -S postgresql\n"
                "   - Ubuntu: sudo apt install postgresql\n"
                "2. Initialize the database (if first time):\n"
                "   - sudo -u postgres initdb -D /var/lib/postgres/data\n"
                "3. Start the service:\n"
                "   - sudo systemctl start postgresql\n"
                "4. Create a user (if needed):\n"
                "   - sudo -u postgres createuser -s $USER\n"
                "5. Update config.json with your credentials\n"
            ) from e
        raise DatabaseError(f"Database connection failed: {e}") from e

def ensure_config_exists() -> str:
    """Ensure config file exists and create default if not.
    
    Returns:
        Path to config file
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found at {config_path}")
        default_config = {
            "environment": "development",
            "llm": {
                "api_key": "YOUR_API_KEY_HERE",
                "model": "google/gemini-2.0-flash-exp:free",
                "base_url": "https://openrouter.ai/api/v1/chat/completions"
            },
            "database": {
                "host": "localhost",
                "database": "memory_db",
                "user": os.getenv("USER", "postgres"),
                "password": ""  # Empty for peer authentication
            }
        }
        
        # Create config directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Write default config
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        logger.info(f"Created default config at {config_path}")
        logger.info("Please update the config with your API key and database credentials")
        raise ConfigError("Please update the config file with your credentials")
    
    return config_path

def init_database(config: Dict[str, Any]) -> PostgreSQLDatabase:
    """Initialize the database with schema."""
    logger.info("Initializing database...")
    try:
        # Verify PostgreSQL is running and database exists
        verify_postgres(config)
        
        # Initialize database connection
        db = PostgreSQLDatabase(config["database"])
        
        # Create necessary collections
        collections = ["conversation", "knowledge", "relationship"]
        for collection in collections:
            db.create_collection(collection)
        
        return db
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def load_sample_data(db: PostgreSQLDatabase) -> None:
    """Load sample conversation data for testing."""
    logger.info("Loading sample data...")
    try:
        # Sample conversation
        conversation = {
            "id": "conv_001",
            "content": """
            User: What's the best way to handle errors in Python?
            Assistant: There are several best practices for error handling in Python:
            1. Use try/except blocks to catch specific exceptions
            2. Avoid bare except clauses
            3. Create custom exception classes for your application
            4. Use context managers (with statements) for resource management
            5. Always clean up resources in finally blocks
            
            Would you like me to explain any of these in more detail?
            
            User: Yes, could you explain custom exception classes?
            Assistant: Custom exception classes help you create application-specific errors.
            Here's an example:
            
            class DatabaseConnectionError(Exception):
                pass
            
            This helps make your error handling more specific and meaningful.
            """,
            "timestamp": "2024-01-20T12:00:00Z",
            "analyzed": False
        }
        
        db.add_entity("conversation", conversation["id"], conversation)
        logger.info("Sample data loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load sample data: {e}")
        raise

def main():
    """Main entry point."""
    try:
        # Ensure config exists
        config_path = ensure_config_exists()
        
        # Load configuration
        config = load_config(config_path)
        
        # Initialize components
        db = init_database(config)
        ontology = OntologyManager(initial_schema=get_initial_schema())
        
        # Load sample data
        load_sample_data(db)
        
        # Initialize analyzer agent
        analyzer = AnalyzerAgent(
            config_path=config_path,
            prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
            db_interface=db,
            ontology_manager=ontology
        )
        
        # Run analysis on unanalyzed conversations
        logger.info("Running analysis...")
        result = analyzer.execute()
        
        logger.info("Analysis complete:")
        logger.info(json.dumps(result, indent=2))
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
