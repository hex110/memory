"""Main entry point for the memory system."""

import os
import json
import logging
import psycopg2
from typing import Dict, Any, Optional
from pathlib import Path

from src.database.postgresql import PostgreSQLDatabase
from src.ontology.manager import OntologyManager
from src.agent.analyzer_agent import AnalyzerAgent
from src.utils.config import load_config, ConfigError
from src.utils.exceptions import DatabaseError
from src.schemas.definitions import get_database_schema, get_ontology_schema

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set specific loggers to DEBUG level
logging.getLogger('src.agent.analyzer_agent').setLevel(logging.INFO)
logging.getLogger('src.agent.base_agent').setLevel(logging.INFO)

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
                "provider": "gemini",  # or "openrouter"
                "api_key": "${GEMINI_API_KEY}",  # Will be replaced with env var
                "model": "gemini-2.0-flash-exp",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
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
        
        # Initialize database schema and tables
        db.initialize_database()
        
        return db
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
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
        ontology = OntologyManager(initial_schema=get_ontology_schema())
        
        # Initialize analyzer agent
        analyzer = AnalyzerAgent(
            config_path=config_path,
            prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
            db_interface=db,
            ontology_manager=ontology
        )
        
        # Test conversation for analysis
        test_conversation = {
            "id": "test_2",
            "content": """
            Assistant: Let's explore how you handle work and challenges. What's your approach to solving complex problems?

            User: I love diving into complex problems! I usually start by breaking them down into smaller pieces and creating a detailed plan. I get really excited about finding innovative solutions, even if it means taking some risks. Sometimes I can get so absorbed that I lose track of time.

            Assistant: That's interesting! And how do you typically work with others in a team setting?

            User: I'm actually quite energetic in team settings and enjoy brainstorming sessions. I like to take initiative and propose new ideas, though sometimes I might come across as too enthusiastic. I do try to make sure everyone gets a chance to speak, but I often find myself naturally taking the lead.

            Assistant: How do you handle setbacks or when things don't go according to plan?

            User: I try to stay positive and see setbacks as learning opportunities. Sure, it can be frustrating initially, but I quickly start looking for alternative approaches. I'm pretty adaptable and don't mind changing course if something isn't working. That said, I can be a bit impatient sometimes when things move too slowly.

            Assistant: What about your learning style? How do you approach new skills or knowledge?

            User: I'm a very hands-on learner. I prefer jumping in and experimenting rather than reading long manuals. I get excited about learning new things and often have multiple projects or courses going at once. Sometimes I might start too many things at once, but I'm always eager to expand my knowledge and try new approaches.
            """,
            "timestamp": "2024-01-20T14:00:00Z",
            "analyzed": False
        }
        
        # Run analysis on test conversation
        logger.info("Running analysis on test conversation...")
        result = analyzer.analyze_conversation(test_conversation)
        
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
