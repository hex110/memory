"""Main entry point for the memory system."""

import os
import json
import logging
import psycopg2
import time
import threading
import argparse
from typing import Dict, Any, Optional
from pathlib import Path
import requests
import uvicorn

from src.database.postgresql import PostgreSQLDatabase
from src.ontology.manager import OntologyManager
from src.agent.analyzer_agent import AnalyzerAgent
from src.agent.curator_agent import CuratorAgent
from src.utils.config import load_config, ConfigError
from src.utils.exceptions import DatabaseError
from src.schemas.definitions import get_database_schema, get_ontology_schema

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set specific loggers to INFO level
logging.getLogger('src.agent.analyzer_agent').setLevel(logging.INFO)
logging.getLogger('src.agent.base_agent').setLevel(logging.INFO)
logging.getLogger('litellm').setLevel(logging.WARNING)
logging.getLogger('litellm.response').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)

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
    """Initialize the database with schema from definitions.py.
    
    This will:
    1. Verify PostgreSQL is running
    2. Create database if it doesn't exist
    3. Create tables based on current schema
    """
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

def run_server():
    """Run the uvicorn server."""
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable reload for development
        log_level="info"
    )

def analyze_test_conversation(config_path: str, db: PostgreSQLDatabase):
    """Analyze the test conversation file."""
    logger.info("Running analysis mode...")
    
    ontology = OntologyManager(initial_schema=get_ontology_schema())
    analyzer = AnalyzerAgent(
        config_path=config_path,
        prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
        db_interface=db,
        ontology_manager=ontology
    )

    try:
        with open("src/test_conversation.txt", "r") as f:
            conversation_content = f.read()

        conversation = {
            "id": "test_1",
            "content": conversation_content,
            "timestamp": "2024-01-20T14:00:00Z",
            "analyzed": False
        }

        result = analyzer.analyze_conversation(conversation)
        logger.info("Analysis complete. Result:")
        logger.info(json.dumps(result, indent=2))
        
    except FileNotFoundError:
        logger.error("test_conversation.txt not found in src directory")
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise

def main():
    """Main entry point."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Memory System CLI')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-server', action='store_true', help='Run the API server')
        group.add_argument('-analyze', action='store_true', help='Analyze test conversation')
        args = parser.parse_args()

        # Ensure config exists
        config_path = ensure_config_exists()
        
        # Load configuration
        config = load_config(config_path)
        
        # Initialize components
        db = init_database(config)
        
        if args.analyze:
            analyze_test_conversation(config_path, db)
        elif args.server:
            logger.info("Starting API server...")
            run_server()
        else:
            logger.info("No mode specified. Use -server to run the API server or -analyze to analyze test conversation")
            parser.print_help()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
# If I want to run tests in main, run server in different thread
# server_thread = threading.Thread(target=run_server)
#         server_thread.daemon = True  # Allow the thread to be killed when main 
#         exits
#         server_thread.start()

# Run API tests
# test_api_pipeline()

# ontology = OntologyManager(initial_schema=get_ontology_schema())
#         # Initialize analyzer agent
#         analyzer = AnalyzerAgent(
#             config_path=config_path,
#             prompt_folder=os.path.join(os.path.dirname(__file__), "agent", 
#             "prompts"),
#             db_interface=db,
#             ontology_manager=ontology
#         )

#         # Initialize curator agent
#         curator = CuratorAgent(
#             config_path=config_path,
#             prompt_folder=os.path.join(os.path.dirname(__file__), "agent", 
#             "prompts"),
#             db_interface=db,
#             ontology_manager=ontology
#         )
        
#         # Test conversations for analysis
#         test_conversations = [
#             {
#                 "id": "test_1",
#                 "content": """
#                 Assistant: Let's explore how you handle work and challenges. 
#                 What's your approach to solving complex problems?

#                 User: I love diving into complex problems! I usually start by 
#                 breaking them down into smaller pieces and creating a detailed 
#                 plan. I get really excited about finding innovative solutions, 
#                 even if it means taking some risks. Sometimes I can get so 
#                 absorbed that I lose track of time.

#                 Assistant: That's interesting! And how do you typically work with 
#                 others in a team setting?

#                 User: I'm actually quite energetic in team settings and enjoy 
#                 brainstorming sessions. I like to take initiative and propose new 
#                 ideas, though sometimes I might come across as too enthusiastic. 
#                 I do try to make sure everyone gets a chance to speak, but I 
#                 often find myself naturally taking the lead.

#                 Assistant: How do you handle setbacks or when things don't go 
#                 according to plan?

#                 User: I try to stay positive and see setbacks as learning 
#                 opportunities. Sure, it can be frustrating initially, but I 
#                 quickly start looking for alternative approaches. I'm pretty 
#                 adaptable and don't mind changing course if something isn't 
#                 working. That said, I can be a bit impatient sometimes when 
#                 things move too slowly.

#                 Assistant: What about your learning style? How do you approach 
#                 new skills or knowledge?

#                 User: I'm a very hands-on learner. I prefer jumping in and 
#                 experimenting rather than reading long manuals. I get excited 
#                 about learning new things and often have multiple projects or 
#                 courses going at once. Sometimes I might start too many things at 
#                 once, but I'm always eager to expand my knowledge and try new 
#                 approaches.
#                 """,
#                 "timestamp": "2024-01-20T14:00:00Z",
#                 "analyzed": False
#             },
#             {
#                 "id": "test_2",
#                 "content": """
#                 Assistant: I'd like to understand how you navigate social 
#                 situations and relationships. Could you tell me about how you 
#                 typically interact in social gatherings?

#                 User: Well, it's interesting... I tend to observe first before 
#                 fully engaging. I enjoy social gatherings, but I need to get a 
#                 feel for the dynamics. Sometimes I find myself playing different 
#                 roles - like being the mediator when there's tension, or the one 
#                 who draws out quieter people. But I also notice I need breaks to 
#                 recharge, especially after intense social interactions.

#                 Assistant: That's fascinating. How do you handle emotional 
#                 situations, whether your own emotions or others'?

#                 User: I've learned to be more mindful about emotions over time. I 
#                 used to try to fix everything immediately, but now I recognize 
#                 sometimes people just need someone to listen. I'm pretty good at 
#                 reading subtle cues in others' behavior, though this sensitivity 
#                 can sometimes be overwhelming. I process my own emotions by 
#                 writing or going for long walks - it helps me understand what I'm 
#                 really feeling and why.

#                 Assistant: Could you share how you approach personal goals and 
#                 growth?

#                 User: I'm quite methodical about personal development, actually. 
#                 I like to set structured goals but keep them flexible enough to 
#                 adapt. I've noticed I'm most successful when I balance pushing 
#                 myself with being realistic. The interesting part is that I often 
#                 find myself achieving goals in unexpected ways - like starting a 
#                 project for one reason and discovering it fulfills a completely 
#                 different personal goal.

#                 Assistant: How do you deal with conflicts or disagreements in 
#                 your relationships?

#                 User: That's evolved a lot for me. I used to avoid conflicts 
#                 entirely, but I've learned that addressing issues early prevents 
#                 bigger problems. I try to understand the other person's 
#                 perspective first, though sometimes I catch myself preparing my 
#                 response before they finish speaking - it's something I'm working 
#                 on. I value harmony but not at the expense of authenticity. 
#                 Sometimes I surprise myself by being quite firm on my boundaries, 
#                 especially when it comes to core values.

#                 Assistant: What about your approach to making important decisions?

#                 User: It's a bit of a paradox, really. I gather lots of 
#                 information and analyze thoroughly, but I also trust my intuition 
#                 strongly. Sometimes I find myself making lists and weighing pros 
#                 and cons, only to realize I knew the answer instinctively from 
#                 the start. I tend to consider how my decisions might affect 
#                 others, maybe sometimes too much. I've noticed I'm more confident 
#                 with professional decisions than personal ones - there's an 
#                 interesting disconnect there that I'm trying to understand better.

#                 Assistant: How do you handle unexpected changes or disruptions to 
#                 your plans?

#                 User: *laughs* That's been a journey of growth! I used to get 
#                 really thrown off by unexpected changes, but I've developed this 
#                 sort of... flexible resilience, I guess you could call it. I 
#                 still like having backup plans - actually, usually backup plans 
#                 for my backup plans - but I've learned to find opportunities in 
#                 chaos. Though I have to admit, I still sometimes catch myself 
#                 trying to control things that really aren't controllable. It's 
#                 interesting how often the unexpected detours end up leading to 
#                 better outcomes than my original plans.
#                 """,
#                 "timestamp": "2024-01-21T15:30:00Z",
#                 "analyzed": False
#             }
#         ]
        
        # Comment out previous tests
        # """
        # # Comment out analysis for now
        # for conversation in test_conversations:
        #     logger.info(f"Running analysis on conversation {conversation['id']}...
        #     ")
        #     result = analyzer.analyze_conversation(conversation)
        #     logger.info(f"Analysis complete for {conversation['id']}:")
        #     logger.info(json.dumps(result, indent=2))

        # # Test blog customization request
        # test_request = {
        #     "user_id": "user123",
        #     "content_type": "technical_blog",
        #     "customization_aspects": [
        #         "content_style",
        #         "visual_preferences",
        #         "reading_level"
        #     ],
        #     "context": {
        #         "article_topic": "Machine Learning Architecture Patterns",
        #         "target_audience": "Software Engineers",
        #         "estimated_read_time": "15 minutes"
        #     }
        # }
        
        # logger.info("Testing blog customization...")
        # customization_result = curator.execute(test_request)
        # """
