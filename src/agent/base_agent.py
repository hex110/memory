import os
import json
import requests
import time
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader
from src.utils.exceptions import ConfigError, APIError, APIConnectionError, APIResponseError, APIAuthenticationError
from src.utils.config import (
    load_config, get_api_key, get_model,
    get_base_url, get_llm_config
)
from src.utils.logging import get_logger, log_info, log_error
from requests.exceptions import RequestException, Timeout, ConnectionError

from .agent_interface import AgentInterface

API_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

class BaseAgent(AgentInterface):
    def __init__(
        self,
        prompt_folder: str = "src/agent/prompts",
        config_path: str = "src/config.json",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2
    ):
        """Initialize the BaseAgent with prompt folder and configuration.
        
        Args:
            prompt_folder (str): Path to the folder containing prompt templates
            config_path (str): Path to the configuration file
            model (Optional[str]): Override default model from config
            api_key (Optional[str]): Override API key from config
            base_url (Optional[str]): Override base URL from config
            timeout (int): Request timeout in seconds
            max_retries (int): Number of retries for failed requests
            
        Raises:
            ConfigError: If configuration loading fails or required keys are missing
        """
        self.logger = get_logger(self.__class__.__name__)
        try:
            self.config = load_config(config_path)
            
            # Load API configuration with overrides
            self.api_key = get_api_key(self.config, api_key)
            self.model = get_model(self.config, model)
            self.base_url = get_base_url(self.config, base_url)
            self.timeout = timeout
            self.max_retries = max_retries
            
            # Setup prompt environment
            self.prompt_folder = prompt_folder
            self.env = Environment(loader=FileSystemLoader(self.prompt_folder))
            
        except KeyError as e:
            log_error(self.logger, "Configuration key missing", {"key": str(e)})
            raise ConfigError(f"Missing configuration key: {e}")
        except Exception as e:
            log_error(self.logger, "Failed to initialize BaseAgent", {"error": str(e)})
            raise ConfigError(f"Failed to load configuration: {e}")

    def load_prompt(self, prompt_name: str, context: Dict[str, Any]) -> str:
        """Load and render a prompt template with the given context.
        
        Args:
            prompt_name (str): Name of the prompt template to load
            context (Dict[str, Any]): Context variables to render in the template
            
        Returns:
            str: The rendered prompt string
            
        Raises:
            Exception: If prompt loading or rendering fails
        """
        try:
            template = self.env.get_template(f"{prompt_name}.txt")
            prompt = template.render(context)
            log_info(self.logger, "Prompt loaded successfully", {"prompt_name": prompt_name})
            return prompt
        except Exception as e:
            log_error(self.logger, "Failed to load prompt", {"prompt_name": prompt_name, "error": str(e)})
            raise

    def call_llm(self, prompt: str, temperature: float = 0.7, system_prompt: Optional[str] = None) -> str:
        """Call the LLM API with the given prompt and return the response.
        
        Args:
            prompt (str): The prompt to send to the LLM
            temperature (float): Sampling temperature (0-1)
            system_prompt (Optional[str]): Optional system prompt
            
        Returns:
            str: The LLM's response
            
        Raises:
            APIConnectionError: If there are network connectivity issues
            APIAuthenticationError: If the API key is invalid
            APIResponseError: If the API response is invalid
            APIError: For other API-related errors
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "Memory-Agent",  # For OpenRouter rankings
            "X-Title": "Memory-Agent"  # For OpenRouter rankings
        }
        
        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        first_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=self.timeout
                )
                
                # Handle HTTP errors
                if response.status_code == 401:
                    raise APIAuthenticationError(
                        "Invalid API key or unauthorized access",
                        status_code=response.status_code,
                        response=response.text
                    )
                response.raise_for_status()
                
                # Parse response
                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    raise APIResponseError(
                        f"Invalid JSON response: {e}",
                        status_code=response.status_code,
                        response=response.text
                    )
                
                if not result.get('choices') or not result['choices'][0].get('message', {}).get('content'):
                    raise APIResponseError(
                        "Invalid response format: missing required fields",
                        status_code=response.status_code,
                        response=response.text
                    )
                
                llm_output = result['choices'][0]['message']['content'].strip()
                log_info(self.logger, "LLM response received", {
                    "response_length": len(llm_output),
                    "model": self.model,
                    "total_tokens": result.get('usage', {}).get('total_tokens')
                })
                return llm_output
                
            except (ConnectionError, Timeout) as e:
                error = APIConnectionError(f"Connection error: {str(e)}")
                if first_error is None:
                    first_error = error
            except APIAuthenticationError as e:
                # Don't retry auth errors
                raise e
            except APIResponseError as e:
                # Don't retry response format errors
                raise e
            except RequestException as e:
                error = APIError(
                    f"Request failed: {str(e)}",
                    status_code=getattr(e.response, 'status_code', None),
                    response=getattr(e.response, 'text', None)
                )
                if first_error is None:
                    first_error = error
            except Exception as e:
                error = APIError(f"Unexpected error: {str(e)}")
                if first_error is None:
                    first_error = error
            
            # Log retry attempt
            if attempt < self.max_retries - 1:
                retry_delay = 2 ** attempt  # Exponential backoff
                log_info(self.logger, f"Retrying API call", {
                    "attempt": attempt + 1,
                    "max_retries": self.max_retries,
                    "delay": retry_delay
                })
                time.sleep(retry_delay)
        
        # If we've exhausted all retries, raise the first error we encountered
        log_error(self.logger, "API call failed after all retries", {
            "max_retries": self.max_retries,
            "error": str(first_error)
        })
        raise first_error or APIError("Maximum retries exceeded")

    def parse_response(self, response: str) -> Any:
        """Parse the LLM response to extract useful information.
        
        This is a basic implementation that can be overridden by subclasses
        to provide more sophisticated parsing.
        
        Args:
            response (str): The raw response from the LLM
            
        Returns:
            Any: The parsed response (in base implementation, returns the raw string)
        """
        log_info(self.logger, "Parsing LLM response", {"response_snippet": response[:50]})
        return response

    def execute(self) -> None:
        """Execute the agent's primary function.
        
        This method must be implemented by concrete agent classes to define
        their specific behavior and logic flow.
        
        Raises:
            NotImplementedError: This method must be overridden by subclasses
        """
        raise NotImplementedError("Execute method must be implemented by the agent.") 