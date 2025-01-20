"""Main entry point for running the schema explainer agent."""

import os
import json
from dotenv import load_dotenv
from pathlib import Path
from src.agent.example_agent import SchemaExplainerAgent

def setup_config():
    """Set up the config file using environment variables."""
    # Load environment variables from .env
    load_dotenv()
    
    # Get required environment variables
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    # Create config structure
    config = {
        "environment": "development",
        "llm": {
            "api_key": api_key,
            "model": "google/gemini-2.0-flash-exp:free",
            "base_url": "https://openrouter.ai/api/v1/chat/completions"
        },
        "database": {
            "host": "localhost",
            "database": "memory_db",
            "user": "postgres",
            "password": "postgres"
        }
    }
    
    # Ensure config directory exists
    config_path = Path("src/config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write config to file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"Config file created at {config_path}")
    return str(config_path)

def main():
    """Main function to run the schema explainer agent."""
    try:
        # Setup config
        config_path = setup_config()
        print("\nInitializing SchemaExplainerAgent...")
        
        # Create and run agent
        agent = SchemaExplainerAgent(
            config_path=config_path,
            prompt_folder="src/agent/prompts"
        )
        
        print("\nExecuting agent to explain schema methods...")
        explanation = agent.execute()
        
        print("\nSchema Method Explanations:")
        print("=" * 80)
        print(explanation)
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        raise

if __name__ == "__main__":
    main()
