"""Custom exceptions for the system."""

class ConfigError(Exception):
    """Raised when there is a configuration error."""
    pass


class DatabaseError(Exception):
    """Raised when a database operation fails."""
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


class ValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class MigrationError(Exception):
    """Raised when a schema migration fails."""
    pass


class ActivityTrackingError(Exception):
    """Base exception for activity tracking related errors.
    
    This exception is raised when there are issues with activity tracking,
    such as device access, permissions, or data collection failures.
    """
    pass


class KeyboardTrackingError(ActivityTrackingError):
    """Exception raised for keyboard tracking issues.
    
    This includes evdev device access failures and event tracking errors.
    """
    pass


class ScreenCaptureError(ActivityTrackingError):
    """Exception raised for screen capture issues.
    
    This includes screenshot failures, Wayland/X11 issues, and image processing errors.
    """
    pass


class WindowTrackingError(ActivityTrackingError):
    """Exception raised for window tracking issues.
    
    This includes window manager access failures and window state tracking errors.
    """
    pass
