from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

class DatabaseInterface(ABC):
    """Interface for flexible database operations.
    
    This interface defines a schema-agnostic contract for database implementations.
    It treats the database as a collection of entities with flexible schemas.
    Features:
    - Dynamic schema evolution
    - Flexible entity types
    - Schema-less or schema-full operation
    - JSON-like data storage
    - Generic query capabilities
    """

    @abstractmethod
    def create_collection(self, collection_name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        """Creates a new collection (table) with optional schema.
        
        Args:
            collection_name: Name of the collection to create
            schema: Optional schema definition for validation
                   If None, collection will be schema-less
            
        Raises:
            DatabaseError: If collection creation fails
        """
        pass

    @abstractmethod
    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Gets the schema for a collection if it exists.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dict[str, Any]: Schema definition or empty dict if no schema
        """
        pass

    @abstractmethod
    def update_collection_schema(self, collection_name: str, schema: Dict[str, Any]) -> None:
        """Updates the schema for a collection.
        
        Args:
            collection_name: Name of the collection
            schema: New schema definition
            
        Raises:
            DatabaseError: If schema update fails
        """
        pass

    @abstractmethod
    def add_entity(self, collection_name: str, entity_id: str, data: Dict[str, Any]) -> str:
        """Add a new entity to a collection.
        
        Args:
            collection_name: Name of the collection to add to
            entity_id: ID for the new entity
            data: Entity data
            
        Returns:
            str: ID of the created entity
            
        Raises:
            DatabaseError: If entity creation fails
        """
        pass

    @abstractmethod
    def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID.
        
        Args:
            collection_name: Name of the collection
            entity_id: ID of the entity to get
            
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
    def update(self, collection_name: str, entity_id: str, data: Dict[str, Any], 
               upsert: bool = False) -> None:
        """Update entity data with optional upsert.
        
        Args:
            collection_name: Name of the collection
            entity_id: ID of the entity to update
            data: New entity data (will be merged with existing)
            upsert: If True, insert if entity doesn't exist
            
        Raises:
            DatabaseError: If update fails
        """
        pass

    @abstractmethod
    def delete(self, collection_name: str, entity_id: str) -> None:
        """Deletes an entity.
        
        Args:
            collection_name: Name of the collection
            entity_id: ID of the entity to delete
            
        Raises:
            DatabaseError: If deletion fails
        """
        pass

    @abstractmethod
    def create_link(self, from_collection: str, from_id: str, 
                   to_collection: str, to_id: str,
                   link_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Creates a link between two entities.
        
        Args:
            from_collection: Source entity's collection
            from_id: Source entity's ID
            to_collection: Target entity's collection
            to_id: Target entity's ID
            link_type: Type of link
            metadata: Optional metadata for the link
            
        Returns:
            str: ID of the created link
            
        Raises:
            DatabaseError: If link creation fails
        """
        pass

    @abstractmethod
    def find_links(self, collection_name: str, entity_id: str, 
                  link_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Finds links for an entity.
        
        Args:
            collection_name: Entity's collection
            entity_id: Entity's ID
            link_type: Optional type to filter by
            
        Returns:
            List[Dict[str, Any]]: List of matching links
        """
        pass

    @abstractmethod
    def execute_query(self, query: Union[str, Dict[str, Any]], 
                     params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a native query.
        
        This method allows for database-specific queries when needed.
        
        Args:
            query: Query in native format (e.g., SQL string or MongoDB query)
            params: Optional parameters for the query
            
        Returns:
            List[Dict[str, Any]]: Query results
            
        Raises:
            DatabaseError: If query execution fails
        """
        pass

    @abstractmethod
    def begin_transaction(self) -> None:
        """Starts a new transaction."""
        pass

    @abstractmethod
    def commit_transaction(self) -> None:
        """Commits the current transaction."""
        pass

    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rolls back the current transaction."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes the database connection."""
        pass

    def update_entity(self, collection_name: str, entity_id: str, data: Dict[str, Any]) -> None:
        """DEPRECATED: Use update() instead.
        
        This method exists for backwards compatibility and will be removed in a future version.
        It calls update() with upsert=False.
        """
        return self.update(collection_name, entity_id, data, upsert=False)
