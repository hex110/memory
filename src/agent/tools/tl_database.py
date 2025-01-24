"""Database tool implementations.

This module provides the actual implementations of database-related tools,
handling database operations, tracking, and error management.
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from functools import wraps
from uuid import UUID

from src.interfaces.postgresql import DatabaseInterface
from src.utils.exceptions import DatabaseError, ValidationError

# Set up logging
logger = logging.getLogger(__name__)

def track_operation(operation_name: str) -> Callable:
    """Decorator for tracking database operations.
    
    Args:
        operation_name: Name of the operation being tracked
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"DB Operation: {operation_name} - "
                    f"Duration: {duration:.3f}s - "
                    f"Args: {args} - "
                    f"Kwargs: {kwargs}"
                )
                return result
            except Exception as e:
                logger.error(
                    f"DB Operation Failed: {operation_name} - "
                    f"Error: {str(e)} - "
                    f"Args: {args} - "
                    f"Kwargs: {kwargs}",
                    exc_info=True
                )
                raise
        return wrapper
    return decorator

class DatabaseTools:
    """Implementation of database operation tools."""
    
    def __init__(self, db_interface: DatabaseInterface):
        """Initialize database tools.
        
        Args:
            db_interface: Database interface to use for operations
        """
        self.db = db_interface
    
    def _format_response(self, data: Any) -> Any:
        """Format database response for JSON serialization.
        
        Args:
            data: Data to format
            
        Returns:
            JSON-serializable data
        """
        if isinstance(data, dict):
            return {k: self._format_response(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._format_response(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, UUID):
            return str(data)
        return data

    @track_operation("get_entity")
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get a single entity by ID.
        
        Args:
            entity_type: Type of entity to get
            entity_id: ID of entity to get
            
        Returns:
            Entity data or empty dict if not found
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            result = self.db.get_entity(entity_type, entity_id)
            return self._format_response(result)
        except Exception as e:
            raise DatabaseError(f"Failed to get entity: {str(e)}") from e

    @track_operation("get_entities")
    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a type.
        
        Args:
            entity_type: Type of entities to get
            
        Returns:
            List of entity data
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            results = self.db.get_entities(entity_type)
            return self._format_response(results)
        except Exception as e:
            raise DatabaseError(f"Failed to get entities: {str(e)}") from e

    @track_operation("add_entity")
    def add_entity(self, entity_type: str, data: Dict[str, Any]) -> str:
        """Add a new entity.
        
        Args:
            entity_type: Type of entity to add
            data: Entity data
            
        Returns:
            ID of created entity
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If data validation fails
        """
        try:
            entity_id = self.db.add_entity(entity_type, data)
            return str(entity_id)
        except Exception as e:
            if "validation" in str(e).lower():
                raise ValidationError(f"Invalid entity data: {str(e)}") from e
            raise DatabaseError(f"Failed to add entity: {str(e)}") from e

    @track_operation("update_entity")
    def update_entity(
        self,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any]
    ) -> None:
        """Update an existing entity.
        
        Args:
            entity_type: Type of entity to update
            entity_id: ID of entity to update
            data: Updated entity data
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If data validation fails
        """
        try:
            self.db.update_entity(entity_type, entity_id, data)
        except Exception as e:
            if "validation" in str(e).lower():
                raise ValidationError(f"Invalid entity data: {str(e)}") from e
            raise DatabaseError(f"Failed to update entity: {str(e)}") from e

    @track_operation("query_entities")
    def query_entities(
        self,
        entity_type: str,
        query: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters and sorting.
        
        Args:
            entity_type: Type of entities to query
            query: Query filters
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
            limit: Maximum number of results
            
        Returns:
            List of matching entities
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If query validation fails
        """
        try:
            results = self.db.query_entities(
                entity_type,
                query,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit
            )
            return self._format_response(results)
        except Exception as e:
            if "validation" in str(e).lower():
                raise ValidationError(f"Invalid query: {str(e)}") from e
            raise DatabaseError(f"Failed to query entities: {str(e)}") from e