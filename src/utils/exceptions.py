class ConfigError(Exception):
    """Exception raised for configuration-related errors.
    
    This exception is raised when there are issues with loading, parsing,
    or accessing configuration data.
    """
    pass


class DatabaseError(Exception):
    """Exception raised for database-related errors.
    
    This exception is raised when there are issues with database operations,
    connections, or queries.
    """
    pass


class APIError(Exception):
    """Base exception for API-related errors.
    
    This exception is raised when there are issues with API calls,
    responses, or endpoint access.
    """
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class APIConnectionError(APIError):
    """Exception raised for API connection issues.
    
    This includes network errors, timeouts, and connection failures.
    """
    pass


class APIResponseError(APIError):
    """Exception raised for invalid API responses.
    
    This includes invalid JSON, missing required fields, and unexpected response formats.
    """
    pass


class APIAuthenticationError(APIError):
    """Exception raised for authentication failures.
    
    This includes invalid API keys and unauthorized access attempts.
    """
    pass


class ParsingError(Exception):
    """Exception raised for parsing-related errors.
    
    This exception is raised when there are issues with parsing data,
    such as invalid formats or missing required fields.
    """
    pass
