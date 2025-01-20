from typing import Any, Dict


def to_dict(obj: Any) -> Dict:
    """Converts a complex object to a dictionary representation.
    
    This function handles three cases:
    1. Objects with __dict__ attribute (classes, custom objects)
    2. Dictionary objects (returns as is)
    3. Basic data types (wraps in a dictionary with 'value' key)
    
    Args:
        obj (Any): The object to convert to a dictionary.
        
    Returns:
        Dict: A dictionary representation of the object.
        
    Examples:
        >>> class Person:
        ...     def __init__(self, name):
        ...         self.name = name
        >>> to_dict(Person("John"))
        {'name': 'John'}
        >>> to_dict({'key': 'value'})
        {'key': 'value'}
        >>> to_dict(42)
        {'value': 42}
    """
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    elif isinstance(obj, dict):
        return obj
    else:
        return {"value": obj}
