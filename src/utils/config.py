import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from src.utils.exceptions import ConfigError
from src.utils.logging import configure_logging, get_logger

def get_default_config() -> Dict[str, Any]:
    """Returns default configuration settings."""
    return {
        "development": True,  # Enable debug logging and development features
        "server": {
            "host": "0.0.0.0",
            "port": 8000
        },
        "database": {
            "host": "localhost",
            "database": "memory_db",
            "user": os.getenv("USER", "postgres"),
            "password": ""  # Empty for peer authentication
        },
        "llm": {
            "model": "gemini-2.0-flash-exp"
        },
        "tracking": {
            "activity_log_interval": 30,
            "video_duration": 30
        },
        "hotkeys": {
            "hotkey_speak": ["leftctrl", "x"]
        },
        "enable_tutorial": True,
        "tts_enabled": False
    }

def load_env_vars():
    """Load environment variables from .env file if it exists."""
    env_path = Path.cwd() / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        logger = get_logger(__name__)
        logger.warning("\nNo .env file found. You can create one by copying .env.example:")
        logger.warning("cp .env.example .env\n")

def replace_env_vars(config: Dict) -> Dict:
    """Recursively replace environment variables in config values."""
    result = {}
    missing_vars = []
    
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = replace_env_vars(value)
        elif isinstance(value, str):
            # Handle ${VAR} syntax
            if value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                if env_var not in os.environ:
                    missing_vars.append(env_var)
                else:
                    result[key] = os.environ[env_var]
            # Handle $VAR syntax
            elif value.startswith('$'):
                env_var = value[1:]
                if env_var not in os.environ:
                    missing_vars.append(env_var)
                else:
                    result[key] = os.environ[env_var]
            else:
                result[key] = value
        else:
            result[key] = value
            
    if missing_vars:
        error_msg = "\nMissing required environment variables:\n"
        for var in missing_vars:
            error_msg += f"- {var}\n"
        error_msg += "\nPlease set these in your .env file."
        raise ConfigError(error_msg)
        
    return result

def ensure_config_exists() -> Path:
    """Create default config if it doesn't exist. Returns config path."""
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        logger = get_logger(__name__)
        logger.warning(f"Config file not found at {config_path}")
        config = get_default_config()
        
        # Create config directory if it doesn't exist
        config_path.parent.mkdir(exist_ok=True)
        
        # Write default config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Created default config at {config_path}")
        
    return config_path

def load_config_and_logging() -> Dict[str, Any]:
    """Loads configuration from a JSON file and replaces environment variables."""
    try:
        config_path = ensure_config_exists()
        load_env_vars()
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # configure_logging(development=config.get("development", True))
            
        # Replace environment variables in config
        return replace_env_vars(config)
    
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found at {config_path}")
    except json.JSONDecodeError:
        raise ConfigError(f"Error decoding json at file: {config_path}")
    except Exception as e:
        raise ConfigError(f"Error loading configuration: {str(e)}")