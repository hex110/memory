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
    """Exception raised for API-related errors.
    
    This exception is raised when there are issues with API calls,
    responses, or endpoint access.
    """
    pass


class ParsingError(Exception):
    """Exception raised for parsing-related errors.
    
    This exception is raised when there are issues with parsing data,
    such as invalid formats or missing required fields.
    """
    pass
