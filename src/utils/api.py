import uuid
from typing import Any, Dict


def generate_id() -> str:
    """Generates a unique identifier using UUID4.
    
    Returns:
        str: A unique string identifier in UUID4 format.
        
    Example:
        >>> generate_id()
        '123e4567-e89b-12d3-a456-426614174000'
    """
    return str(uuid.uuid4())


def build_response(data: Any, code: int = 200, message: str = "Success") -> Dict[str, Any]:
    """Builds a standardized API response dictionary.
    
    Creates a consistent response format for API endpoints with status code,
    message, and data payload.
    
    Args:
        data (Any): The payload to include in the response.
        code (int, optional): HTTP status code. Defaults to 200.
        message (str, optional): Response message. Defaults to "Success".
        
    Returns:
        Dict[str, Any]: A dictionary containing the formatted response with
            code, message, and data fields.
            
    Example:
        >>> build_response({"user": "John"}, 200, "User found")
        {
            'code': 200,
            'message': 'User found',
            'data': {'user': 'John'}
        }
    """
    return {
        "code": code,
        "message": message,
        "data": data
    }
