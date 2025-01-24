"""Interface definition for database operations.

This module defines the contract for database implementations based on entity operations.
Features:
- Schema-driven through definitions.py
- Strong typing and validation
- Entity-based operations
- PostgreSQL-first but adaptable
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class DatabaseInterface(ABC):
    """Interface for database operations.
    
    This interface defines a schema-driven contract for database implementations.
    The schema is centrally defined in definitions.py and enforced through validation.
    Features:
    - Centralized schema management
    - Entity CRUD operations
    - Rich query capabilities
    - Transaction support via _execute_query
    """

    @abstractmethod
    def initialize_database(self) -> None:
        """Initialize database with schema from definitions.py.
        
        This method:
        1. Creates tables based on current schema
        2. Sets up indexes and constraints
        3. Creates triggers for timestamps
        
        Raises:
            DatabaseError: If initialization fails
        """
        pass

    @abstractmethod
    def add_entity(self, collection_name: str, data: Dict[str, Any]) -> str:
        """Add a new entity to a collection.
        
        Args:
            collection_name: Name of the collection to add to
            data: Entity data (must conform to schema)
            
        Returns:
            str: UUID of the created entity
            
        Raises:
            DatabaseError: If entity creation fails
            ValidationError: If data doesn't match schema
        """
        pass

    @abstractmethod
    def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID.
        
        Args:
            collection_name: Name of the collection
            entity_id: UUID of the entity to get
            
        Returns:
            Dict[str, Any]: Entity data or empty dict if not found
        """
        pass

    @abstractmethod
    def get_entities(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get all entities in a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            List[Dict[str, Any]]: List of entity data
        """
        pass

    @abstractmethod
    def update_entity(self, collection_name: str, entity_id: str, 
                     data: Dict[str, Any], upsert: bool = False) -> None:
        """Update an existing entity.
        
        Args:
            collection_name: Name of the collection
            entity_id: UUID of the entity to update
            data: Updated field values (must conform to schema)
            upsert: If True, create entity if it doesn't exist
            
        Raises:
            DatabaseError: If update fails
            ValidationError: If data doesn't match schema
        """
        pass

    @abstractmethod
    def delete_entity(self, collection_name: str, entity_id: str) -> None:
        """Delete an entity.
        
        Args:
            collection_name: Name of the collection
            entity_id: UUID of the entity to delete
            
        Raises:
            DatabaseError: If deletion fails
        """
        pass

    @abstractmethod
    def query_entities(
        self,
        collection_name: str,
        query: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters and sorting.
        
        Args:
            collection_name: Name of the collection
            query: Filter conditions (field: value or field: {operator: value})
            sort_by: Optional field to sort by
            sort_order: Sort direction ("asc" or "desc")
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: Matching entities
            
        Raises:
            DatabaseError: If query fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass