import psycopg2
from typing import Any, Dict, List, Optional, Union
from src.database.database_interface import DatabaseInterface
from src.utils.exceptions import DatabaseError
from src.utils.config import get_config, load_config
from src.utils.api import generate_id
from psycopg2 import pool
import json
import uuid

class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL implementation of the flexible database interface."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL connection pool and schema registry."""
        self.config = config
        self.schemas = {}  # Store collection schemas
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                1,  # Minimum connections
                10,  # Maximum connections
                host=config.get("host"),
                database=config.get("database"),
                user=config.get("user"),
                password=config.get("password")
            )
        except Exception as e:
            raise DatabaseError(f"Error setting up database pool: {e}")

    def _execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    cols = [col.name for col in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
                return []
        except Exception as e:
            raise DatabaseError(f"Query execution failed: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def create_collection(self, collection_name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        """Creates a new collection with JSONB storage."""
        try:
            # Create table with JSONB data column for flexibility
            query = f"""
            CREATE TABLE IF NOT EXISTS {collection_name} (
                id UUID PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )"""
            self._execute_query(query)
            
            if schema:
                self.schemas[collection_name] = schema
                # Could add DB triggers for schema validation
        except Exception as e:
            raise DatabaseError(f"Failed to create collection {collection_name}: {e}")

    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Get schema for collection."""
        return self.schemas.get(collection_name, {})

    def update_collection_schema(self, collection_name: str, schema: Dict[str, Any]) -> None:
        """Update schema for collection."""
        self.schemas[collection_name] = schema
        # Could update DB triggers for new schema validation

    def insert(self, collection_name: str, data: Dict[str, Any], entity_id: Optional[str] = None) -> str:
        """Insert entity into collection."""
        try:
            if entity_id is None:
                entity_id = str(uuid.uuid4())
            
            query = f"""
            INSERT INTO {collection_name} (id, data)
            VALUES (%s, %s)
            RETURNING id
            """
            result = self._execute_query(query, (entity_id, json.dumps(data)))
            return str(result[0]["id"])
        except Exception as e:
            raise DatabaseError(f"Insert failed: {e}")

    def find_by_id(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Find entity by ID."""
        query = f"SELECT data FROM {collection_name} WHERE id = %s"
        result = self._execute_query(query, (entity_id,))
        return result[0]["data"] if result else {}

    def find(self, collection_name: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find entities matching query criteria."""
        # Convert dict query to JSONB query conditions
        conditions = []
        params = []
        for key, value in query.items():
            conditions.append(f"data @> %s")
            params.append(json.dumps({key: value}))
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        sql = f"SELECT data FROM {collection_name} WHERE {where_clause}"
        
        return [row["data"] for row in self._execute_query(sql, tuple(params))]

    def update(self, collection_name: str, entity_id: str, data: Dict[str, Any], 
               upsert: bool = False) -> None:
        """Update entity data."""
        try:
            if upsert:
                query = f"""
                INSERT INTO {collection_name} (id, data)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE
                SET data = {collection_name}.data || %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                """
                self._execute_query(query, (entity_id, json.dumps(data), json.dumps(data)))
            else:
                query = f"""
                UPDATE {collection_name}
                SET data = data || %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """
                self._execute_query(query, (json.dumps(data), entity_id))
        except Exception as e:
            raise DatabaseError(f"Update failed: {e}")

    def delete(self, collection_name: str, entity_id: str) -> None:
        """Delete entity."""
        query = f"DELETE FROM {collection_name} WHERE id = %s"
        self._execute_query(query, (entity_id,))

    def create_link(self, from_collection: str, from_id: str,
                   to_collection: str, to_id: str,
                   link_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create link between entities."""
        try:
            link_id = str(uuid.uuid4())
            query = """
            INSERT INTO links (id, from_collection, from_id, to_collection, to_id, link_type, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            result = self._execute_query(
                query,
                (link_id, from_collection, from_id, to_collection, to_id, link_type, 
                 json.dumps(metadata or {}))
            )
            return str(result[0]["id"])
        except Exception as e:
            raise DatabaseError(f"Link creation failed: {e}")

    def find_links(self, collection_name: str, entity_id: str,
                  link_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find links for entity."""
        conditions = ["(from_collection = %s AND from_id = %s) OR (to_collection = %s AND to_id = %s)"]
        params = [collection_name, entity_id, collection_name, entity_id]
        
        if link_type:
            conditions.append("link_type = %s")
            params.append(link_type)
        
        query = f"""
        SELECT * FROM links WHERE {' AND '.join(conditions)}
        """
        return self._execute_query(query, tuple(params))

    def execute_query(self, query: Union[str, Dict[str, Any]],
                     params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute native query."""
        if isinstance(query, dict):
            raise DatabaseError("Dict queries not supported in PostgreSQL implementation")
        return self._execute_query(query, tuple(params.values()) if params else None)

    def begin_transaction(self) -> None:
        """Begin transaction."""
        conn = self.connection_pool.getconn()
        conn.autocommit = False

    def commit_transaction(self) -> None:
        """Commit transaction."""
        conn = self.connection_pool.getconn()
        conn.commit()
        conn.autocommit = True
        self.connection_pool.putconn(conn)

    def rollback_transaction(self) -> None:
        """Rollback transaction."""
        conn = self.connection_pool.getconn()
        conn.rollback()
        conn.autocommit = True
        self.connection_pool.putconn(conn)

    def close(self) -> None:
        """Close all connections."""
        self.connection_pool.closeall()
