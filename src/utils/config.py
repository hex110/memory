import json
import os
from typing import Dict, Any, Optional
from src.utils.exceptions import ConfigError


def load_env_vars():
    """Load environment variables from .env file if it exists."""
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


def replace_env_vars(config: Dict) -> Dict:
    """Recursively replace environment variables in config values.
    
    Args:
        config (Dict): Configuration dictionary
        
    Returns:
        Dict: Configuration with environment variables replaced
    """
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = replace_env_vars(value)
        elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            if env_var not in os.environ:
                raise ConfigError(f"Environment variable {env_var} not found")
            result[key] = os.environ[env_var]
        else:
            result[key] = value
    return result


def load_config(path: str) -> Dict:
    """Loads configuration from a JSON file and replaces environment variables.
    
    Args:
        path (str): Path to the JSON configuration file.
        
    Returns:
        Dict: Dictionary containing the configuration data.
        
    Raises:
        ConfigError: If file is not found or JSON is invalid.
    """
    try:
        # Load environment variables first
        load_env_vars()
        
        with open(path, 'r') as f:
            config = json.load(f)
            
        # Replace environment variables in config
        return replace_env_vars(config)
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found at {path}")
    except json.JSONDecodeError:
        raise ConfigError(f"Error decoding json at file: {path}")
    except Exception as e:
        raise ConfigError(f"Error loading configuration: {str(e)}")


def get_config(config: Dict, key: str) -> Any:
    """Gets a configuration value given a key.
    
    Args:
        config (Dict): Configuration dictionary.
        key (str): Key to look up in the configuration.
        
    Returns:
        Any: The value associated with the key, or None if not found.
    """
    return config.get(key)


def set_config(config: Dict, key: str, value: Any) -> None:
    """Sets a configuration value given a key and a value.
    
    Args:
        config (Dict): Configuration dictionary.
        key (str): Key to set in the configuration.
        value (Any): Value to set for the given key.
    """
    config[key] = value


def get_llm_config(config: Dict) -> Dict[str, Any]:
    """Gets the LLM configuration section.
    
    Args:
        config (Dict): Configuration dictionary.
        
    Returns:
        Dict[str, Any]: LLM configuration dictionary.
        
    Raises:
        ConfigError: If LLM configuration is missing.
    """
    llm_config = config.get('llm')
    if not llm_config:
        raise ConfigError("LLM configuration section missing")
    return llm_config


def get_api_key(config: Dict, override_key: Optional[str] = None) -> str:
    """Gets the API key from config or override.
    
    Args:
        config (Dict): Configuration dictionary.
        override_key (Optional[str]): Optional override API key.
        
    Returns:
        str: The API key to use.
        
    Raises:
        ConfigError: If no API key is found.
    """
    api_key = override_key or get_llm_config(config).get('api_key')
    if not api_key:
        raise ConfigError("API key not found in config or override")
    return api_key


def get_model(config: Dict, override_model: Optional[str] = None) -> str:
    """Gets the model name from config or override.
    
    Args:
        config (Dict): Configuration dictionary.
        override_model (Optional[str]): Optional override model name.
        
    Returns:
        str: The model name to use.
    """
    return override_model or get_llm_config(config).get('model', 'google/gemini-2.0-flash-exp:free')


def get_base_url(config: Dict, override_url: Optional[str] = None) -> str:
    """Gets the base URL from config or override.
    
    Args:
        config (Dict): Configuration dictionary.
        override_url (Optional[str]): Optional override base URL.
        
    Returns:
        str: The base URL to use.
    """
    return override_url or get_llm_config(config).get('base_url', 'https://openrouter.ai/api/v1/chat/completions')


def is_dev_mode(config: Dict) -> bool:
    """Checks if the config is in development mode.
    
    Args:
        config (Dict): Configuration dictionary.
        
    Returns:
        bool: True if in development mode, False otherwise.
    """
    return get_config(config, "environment") == "development"


def is_prod_mode(config: Dict) -> bool:
    """Checks if the config is in production mode.
    
    Args:
        config (Dict): Configuration dictionary.
        
    Returns:
        bool: True if in production mode, False otherwise.
    """
    return get_config(config, "environment") == "production"
