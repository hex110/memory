import json
from typing import Dict, Any
from src.utils.exceptions import ConfigError


def load_config(path: str) -> Dict:
    """Loads configuration from a JSON file.
    
    Args:
        path (str): Path to the JSON configuration file.
        
    Returns:
        Dict: Dictionary containing the configuration data.
        
    Raises:
        ConfigError: If file is not found or JSON is invalid.
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found at {path}")
    except json.JSONDecodeError:
        raise ConfigError(f"Error decoding json at file: {path}")


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
