"""Main entry point for the memory system."""

from datetime import datetime
import os
import json
import logging
import uuid
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
from src.agent.analysis_agent import AnalysisAgent
from src.agent.monitor_agent import MonitorAgent
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

def run_monitoring(config_path: str, db: PostgreSQLDatabase):
    """Start activity monitoring."""
    logger.info("Starting activity monitoring...")
    
    ontology = OntologyManager(initial_schema=get_ontology_schema())

    session_id = str(uuid.uuid4())

    # Initialize the agents
    monitor = MonitorAgent(
        config_path=config_path,
        prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
        db_interface=db,
        ontology_manager=ontology,
        session_id=session_id
    )

    analyzer = AnalysisAgent(
        config_path=config_path,
        prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
        db_interface=db,
        ontology_manager=ontology,
        session_id=session_id
    )
    
    try:
        # Start monitoring
        monitor_result = monitor.execute()
        logger.info("Monitoring started successfully")
        logger.info(json.dumps(monitor_result, indent=2))

        
        
        # Start analysis
        analyzer_result = analyzer.execute()
        logger.info("Analysis started successfully")
        logger.info(json.dumps(analyzer_result, indent=2))
        
        # Keep the main thread alive while both run in background
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping monitoring and analysis...")
            monitor.stop_monitoring()
            analyzer.stop_analysis_cycles()
            
    except Exception as e:
        logger.error(f"Monitoring/Analysis failed: {e}")
        raise

def save_analyses_to_files(db: PostgreSQLDatabase, session_id: str):
    """Save all analyses for a session to separate files based on type.
    
    Args:
        db: Database interface
        session_id: Session ID to get analyses for
    """
    # Get all analyses for the session
    query = {"session_id": session_id}
    analyses = db.query_entities(
        "activity_analysis",
        query,
        sort_by="start_timestamp",
        sort_order="asc"
    )
    
    # Check if session is ongoing
    latest_activity = db.query_entities(
        "activity_raw",
        {"session_id": session_id},
        sort_by="timestamp",
        sort_order="desc",
        limit=1
    )
    # print latest activity without screenshot
    latest_time = latest_activity[0]["timestamp"]
    latest_time_float = datetime.fromisoformat(latest_time).timestamp()
    is_ongoing = (time.time() - latest_time_float) < 60 if latest_activity else False
    session_status = "[ONGOING SESSION]" if is_ongoing else "[COMPLETED SESSION]"
    
    # Prepare files
    with open("responses.txt", "w") as all_file, \
         open("regular_responses.txt", "w") as regular_file, \
         open("special_responses.txt", "w") as special_file, \
         open("final_response.txt", "w") as final_file:
        
        # Write session status to each file
        for f in [all_file, regular_file, special_file, final_file]:
            f.write(f"{session_status}\nSession ID: {session_id}\n\n")
        
        # Write analyses to appropriate files
        for analysis in analyses:
            timestamp = analysis["start_timestamp"]
            analysis_type = analysis["analysis_type"]
            response = analysis["llm_response"]
            
            # Write to all responses file
            all_file.write(f"({analysis_type}) {timestamp}: {response}\n\n")
            
            # Write to type-specific file
            if analysis_type == "regular":
                regular_file.write(f"{timestamp}: {response}\n\n")
            elif analysis_type == "special":
                special_file.write(f"{timestamp}: {response}\n\n")
            elif analysis_type == "final":
                final_file.write(f"{timestamp}: {response}\n\n")

def get_last_session_id(db: PostgreSQLDatabase) -> str:
    """Get the ID of the last/current session.
    
    Args:
        db: Database interface
        
    Returns:
        Last session ID
    """
    sessions = db.query_entities(
        "activity_raw",
        {},
        sort_by="timestamp",
        sort_order="desc",
        limit=1
    )
    if not sessions:
        raise ValueError("No sessions found")
    return sessions[0]["session_id"]

def has_final_analysis(db: PostgreSQLDatabase, session_id: str) -> Optional[Dict[str, Any]]:
    """Check if a session has a final analysis.
    
    Args:
        db: Database interface
        session_id: Session ID to check
        
    Returns:
        Final analysis if exists, None otherwise
    """
    query = {
        "session_id": session_id,
        "analysis_type": "final"
    }
    analyses = db.query_entities(
        "activity_analysis",
        query,
        limit=1
    )
    return analyses[0] if analyses else None

def analyze_session(config_path: str, db: PostgreSQLDatabase, session_id: Optional[str] = None, custom_prompt_path: Optional[str] = None):
    """Analyze a specific session or the last completed session."""
    logger.info("Starting session analysis...")
    
    ontology = OntologyManager(initial_schema=get_ontology_schema())
    analyzer = AnalysisAgent(
        config_path=config_path,
        prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
        db_interface=db,
        ontology_manager=ontology,
        session_id=session_id
    )

    try:
        # If no session_id provided, get the last completed session
        if not session_id:
            # Query the last session from activity_raw
            query = {}
            sessions = db.query_entities(
                "activity_raw",
                query,
                sort_by="timestamp",
                sort_order="desc",
                limit=1
            )
            if not sessions:
                raise ValueError("No completed sessions found")
            session_id = sessions[0]["session_id"]
            
        # Load custom prompt if provided
        custom_prompt = None
        if custom_prompt_path:
            try:
                with open(custom_prompt_path, 'r') as f:
                    custom_prompt = f.read()
            except Exception as e:
                logger.error(f"Failed to load custom prompt: {e}")
                raise

        # Run the analysis with from_cli=True
        result = analyzer.analyze_session(session_id, custom_prompt)
        
        logger.info(f"Analysis complete for session {session_id}:")
        logger.info(json.dumps(result, indent=2))
        
    except Exception as e:
        logger.error(f"Session analysis failed: {e}")
        raise

def main():
    """Main entry point."""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Memory System CLI')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-server', action='store_true', help='Run the API server')
        group.add_argument('-analyze', action='store_true', help='Analyze test conversation')
        group.add_argument('-track', action='store_true', help='Start activity monitoring')
        group.add_argument('-analyze-session', action='store_true', help='Analyze the last completed session')
        group.add_argument('-log', action='store_true', help='Log analyses to files')

        # Add session analysis arguments
        parser.add_argument('-session-id', type=str, help='Specific session ID to analyze')
        parser.add_argument('-custom-prompt', type=str, help='Path to custom analysis prompt file')

        args = parser.parse_args()

        # Ensure config exists
        config_path = ensure_config_exists()
        
        # Load configuration
        config = load_config(config_path)
        
        # Initialize components
        db = init_database(config)
        
        if args.analyze_session:
            session_id = args.session_id
            if not session_id:
                session_id = get_last_session_id(db)
                
            # Check for existing final analysis
            final_analysis = has_final_analysis(db, session_id)
            if final_analysis and not args.custom_prompt:
                # Save existing final analysis
                with open("analysis.txt", "w") as f:
                    f.write(f"Session ID: {session_id}\n\n")
                    f.write(final_analysis["llm_response"])
            else:
                # Generate new analysis
                analyzer = AnalysisAgent(
                    config_path=config_path,
                    prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
                    db_interface=db,
                    ontology_manager=OntologyManager(initial_schema=get_ontology_schema()),
                    session_id=session_id
                )
                
                custom_prompt = None
                if args.custom_prompt:
                    with open(args.custom_prompt, 'r') as f:
                        custom_prompt = f.read()
                
                result = analyzer.analyze_session(session_id, custom_prompt)
                
                with open("analysis.txt", "w") as f:
                    f.write(f"Session ID: {session_id}\n\n")
                    f.write(result["analysis"])
                    
        elif args.log:
            session_id = args.session_id
            if not session_id:
                session_id = get_last_session_id(db)
            save_analyses_to_files(db, session_id)
            
        elif args.analyze:
            analyze_test_conversation(config_path, db)
        elif args.server:
            logger.info("Starting API server...")
            run_server()
        elif args.track:
            run_monitoring(config_path, db)
        else:
            logger.info("No mode specified. Use -server to run the API server, -analyze to analyze test conversation, -track to start monitoring, -analyze-session to analyze a work session, or -log to save analyses to files")
            parser.print_help()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
