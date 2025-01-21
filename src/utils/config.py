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
    else:
        print("\nNo .env file found. You can create one by copying .env.example:")
        print("cp .env.example .env\n")


def replace_env_vars(config: Dict) -> Dict:
    """Recursively replace environment variables in config values.
    
    Args:
        config (Dict): Configuration dictionary
        
    Returns:
        Dict: Configuration with environment variables replaced
    """
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
            # Also handle $VAR syntax
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


def get_provider_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get provider-specific configuration.
    
    Args:
        config: The configuration dictionary
        
    Returns:
        Dict containing provider-specific configuration
        
    Raises:
        ConfigError: If provider is not supported
    """
    if "llm" not in config:
        raise ConfigError("\nMissing 'llm' section in config.json. Please check your configuration.")
        
    provider = config["llm"].get("provider", "gemini").lower()
    
    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ConfigError(
                "\nGEMINI_API_KEY not found in environment variables.\n"
                "1. Get an API key from: https://makersuite.google.com/app/apikey\n"
                "2. Add it to your .env file:\n"
                "GEMINI_API_KEY=your_key_here"
            )
        return {
            "base_url": "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
            "api_key": api_key,
            "model": "gemini-pro"
        }
    elif provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ConfigError(
                "\nOPENROUTER_API_KEY not found in environment variables.\n"
                "1. Get an API key from: https://openrouter.ai/keys\n"
                "2. Add it to your .env file:\n"
                "OPENROUTER_API_KEY=your_key_here"
            )
        return {
            "base_url": "https://openrouter.ai/api/v1/chat/completions",
            "api_key": api_key,
            "model": config["llm"].get("model", "google/gemini-2.0-flash-exp:free")
        }
    else:
        raise ConfigError(f"\nUnsupported provider: {provider}\nSupported providers are: gemini, openrouter")


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
    provider_config = get_provider_config(config)
    api_key = override_key or provider_config['api_key']
    if not api_key:
        raise ConfigError("API key not found in config, override, or environment")
    return api_key


def get_model(config: Dict, override_model: Optional[str] = None) -> str:
    """Gets the model name from config or override.
    
    Args:
        config (Dict): Configuration dictionary.
        override_model (Optional[str]): Optional override model name.
        
    Returns:
        str: The model name to use.
    """
    provider_config = get_provider_config(config)
    return override_model or provider_config['model']


def get_base_url(config: Dict, override_url: Optional[str] = None) -> str:
    """Gets the base URL from config or override.
    
    Args:
        config (Dict): Configuration dictionary.
        override_url (Optional[str]): Optional override base URL.
        
    Returns:
        str: The base URL to use.
    """
    provider_config = get_provider_config(config)
    return override_url or provider_config['base_url']


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
