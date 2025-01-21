import psycopg2
from typing import Any, Dict, List, Optional, Union
from src.interfaces.postgresql import DatabaseInterface
from src.utils.exceptions import DatabaseError
from src.utils.config import get_config, load_config
from src.utils.api import generate_id
from psycopg2 import pool
import json
import uuid
from src.schemas.definitions import get_database_schema
from src.schemas.migrator import MigrationManager
from src.schemas.validator import SchemaValidator

class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL implementation of the flexible database interface."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL connection pool and schema registry."""
        self.config = config
        self.schemas = {}  # Store collection schemas
        
        # Build connection parameters, omitting empty values for peer auth
        conn_params = {
            "host": config.get("host"),
            "database": config.get("database"),
            "user": config.get("user"),
        }
        if config.get("password"):  # Only include password if provided
            conn_params["password"] = config["password"]
        
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                1,  # Minimum connections
                10,  # Maximum connections
                **conn_params
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
                conn.commit()  # Ensure changes are committed
                if cur.description:
                    cols = [col.name for col in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
                return []
        except Exception as e:
            if conn:
                conn.rollback()  # Rollback on error
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
                id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )"""
            self._execute_query(query)
            
            # Store schema if provided
            if schema:
                self.schemas[collection_name] = schema
                
        except Exception as e:
            raise DatabaseError(f"Failed to create collection {collection_name}: {e}")

    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """Get schema for collection."""
        return self.schemas.get(collection_name, {})

    def update_collection_schema(self, collection_name: str, schema: Dict[str, Any]) -> None:
        """Update schema for collection."""
        self.schemas[collection_name] = schema
        # Could update DB triggers for new schema validation

    def add_entity(self, collection_name: str, entity_id: str, data: Dict[str, Any]) -> str:
        """Add a new entity to a collection."""
        try:
            query = f"""
            INSERT INTO {collection_name} (id, data)
            VALUES (%s, %s)
            RETURNING id
            """
            result = self._execute_query(query, (entity_id, json.dumps(data)))
            return str(result[0]["id"])
        except Exception as e:
            raise DatabaseError(f"Failed to add entity: {e}")

    def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID."""
        query = f"SELECT data FROM {collection_name} WHERE id = %s"
        result = self._execute_query(query, (entity_id,))
        return result[0]["data"] if result else {}

    def get_entities(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get all entities in a collection."""
        query = f"SELECT data FROM {collection_name}"
        return [row["data"] for row in self._execute_query(query)]

    def find(self, collection_name: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find entities matching query criteria."""
        conditions = []
        params = []
        for key, value in query.items():
            conditions.append(f"data @> %s")
            params.append(json.dumps({key: value}))
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        sql = f"SELECT data FROM {collection_name} WHERE {where_clause}"
        
        return [row["data"] for row in self._execute_query(sql, tuple(params))]

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

    def update(self, collection_name: str, entity_id: str, data: Dict[str, Any], 
               upsert: bool = False) -> None:
        """Update entity data with optional upsert."""
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

    def initialize_database(self) -> None:
        """Initialize database tables and schemas.
        
        This method:
        1. Creates tables based on schema definitions
        2. Applies any pending migrations
        3. Initializes schema tracking
        """
        try:
            # Get schema definitions
            schema_defs = get_database_schema()
            
            # Create base tables from schema
            for collection_name, schema in schema_defs.items():
                self.create_collection(collection_name, schema)
            
            # Create links table for relationships
            self._execute_query("""
                CREATE TABLE IF NOT EXISTS links (
                    id TEXT PRIMARY KEY,
                    from_collection TEXT NOT NULL,
                    from_id TEXT NOT NULL,
                    to_collection TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create necessary indexes
            self._execute_query("""
                CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_collection, from_id);
                CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_collection, to_id);
                CREATE INDEX IF NOT EXISTS idx_links_type ON links(link_type);
            """)
            
            # Initialize migration tracking
            self._execute_query("""
                CREATE TABLE IF NOT EXISTS schema_versions (
                    id TEXT PRIMARY KEY DEFAULT 'current',
                    version TEXT NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Store schemas in database registry
            for collection_name, schema in schema_defs.items():
                self.schemas[collection_name] = schema
            
            # Apply any pending migrations
            validator = SchemaValidator()
            migration_manager = MigrationManager("src/schemas/migrations", validator)
            migration_manager.migrate(self, None)  # Migrate to latest version
            
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {e}")
            
    def get_current_schema_version(self) -> str:
        """Get the current schema version from the database."""
        try:
            result = self._execute_query(
                "SELECT version FROM schema_versions WHERE id = 'current'"
            )
            return result[0]["version"] if result else "000"
        except Exception:
            return "000"  # Return initial version if table doesn't exist
