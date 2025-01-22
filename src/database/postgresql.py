import psycopg2
from typing import Any, Dict, List, Optional, Union
from src.interfaces.postgresql import DatabaseInterface
from src.utils.exceptions import DatabaseError
from psycopg2 import pool
import json
import uuid
from src.schemas.definitions import get_database_schema

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
        except psycopg2.OperationalError as e:
            if "Connection refused" in str(e):
                raise DatabaseError(
                    "\nPostgreSQL connection failed. Please check:\n"
                    "1. Is PostgreSQL installed?\n"
                    "   - Arch Linux: sudo pacman -S postgresql\n"
                    "   - Ubuntu: sudo apt install postgresql\n"
                    "   - macOS: brew install postgresql\n"
                    "2. Is PostgreSQL service running?\n"
                    "   - Linux: sudo systemctl start postgresql\n"
                    "   - macOS: brew services start postgresql\n"
                    "3. Have you initialized the database? (First time setup)\n"
                    "   - Linux: sudo -u postgres initdb -D /var/lib/postgres/data\n"
                    "   - macOS: initdb /usr/local/var/postgres\n"
                    "4. Can your user access PostgreSQL?\n"
                    "   - Create user: sudo -u postgres createuser -s $USER\n"
                    "5. Check your database settings in config.json and .env\n"
                ) from e
            elif "database" in str(e) and "does not exist" in str(e):
                raise DatabaseError(
                    f"\nDatabase '{conn_params['database']}' does not exist. To create it:\n"
                    "1. Connect to PostgreSQL:\n"
                    "   sudo -u postgres psql\n"
                    f"2. Create database: CREATE DATABASE {conn_params['database']};\n"
                    "3. Exit psql: \\q\n"
                ) from e
            elif "password authentication failed" in str(e):
                raise DatabaseError(
                    "\nPostgreSQL authentication failed. Please check:\n"
                    "1. Your database password in .env is correct\n"
                    "2. Your pg_hba.conf is configured correctly\n"
                    "3. Your user has the correct permissions\n"
                ) from e
            else:
                raise DatabaseError(f"Database connection failed: {e}") from e
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

    def _get_pg_type(self, schema_type: str) -> str:
        """Convert schema type to PostgreSQL type."""
        type_mapping = {
            "string": "TEXT",
            "integer": "INTEGER",
            "number": "NUMERIC",
            "boolean": "BOOLEAN",
            "array": "TEXT[]",  # Simple array type
            "object": "JSONB",  # Complex objects stored as JSONB
        }
        return type_mapping.get(schema_type, "TEXT")

    def create_collection(self, collection_name: str, schema: Optional[Dict[str, Any]] = None) -> None:
        """Creates a new collection with columns based on schema."""
        try:
            if not schema or "properties" not in schema:
                # Create default table structure if no schema provided
                query = f"""
                CREATE TABLE IF NOT EXISTS {collection_name} (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )"""
            else:
                # Build column definitions from schema
                columns = ["id TEXT PRIMARY KEY"]
                for field_name, field_def in schema["properties"].items():
                    if field_name != "id":  # Skip id as it's already defined
                        field_type = self._get_pg_type(field_def.get("type", "string"))
                        default = f"DEFAULT {field_def.get('default')}" if "default" in field_def else ""
                        columns.append(f"{field_name} {field_type} {default}")
                
                # Add timestamps
                columns.extend([
                    "created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
                    "updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
                ])
                
                # Create table with schema-defined columns
                query = f"""
                CREATE TABLE IF NOT EXISTS {collection_name} (
                    {','.join(columns)}
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
            schema = self.schemas.get(collection_name)
            
            if not schema or "properties" not in schema:
                # Use old JSONB approach if no schema
                query = f"""
                INSERT INTO {collection_name} (id, data)
                VALUES (%s, %s)
                RETURNING id
                """
                result = self._execute_query(query, (entity_id, json.dumps(data)))
            else:
                # Build column list and values for schema-based table
                columns = ["id"]
                values = [entity_id]
                placeholders = ["%s"]
                
                for field_name in schema["properties"]:
                    if field_name != "id" and field_name in data:
                        columns.append(field_name)
                        field_def = schema["properties"][field_name]
                        
                        # Handle different field types
                        if field_def.get("type") == "array":
                            # Convert Python list to PostgreSQL array format
                            array_value = data[field_name]
                            if not isinstance(array_value, list):
                                array_value = []  # Ensure it's a list
                            # Convert to PostgreSQL array literal format
                            values.append(array_value)
                        elif field_def.get("type") == "object":
                            # Store objects as JSONB
                            values.append(json.dumps(data[field_name]))
                        else:
                            # Handle scalar values
                            values.append(data[field_name])
                        
                        placeholders.append("%s")
                
                query = f"""
                INSERT INTO {collection_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
                """
                result = self._execute_query(query, tuple(values))
            
            return str(result[0]["id"])
            
        except Exception as e:
            raise DatabaseError(f"Failed to add entity: {e}")

    def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID."""
        schema = self.schemas.get(collection_name)
        
        if not schema or "properties" not in schema:
            # Use old JSONB approach if no schema
            query = f"SELECT data FROM {collection_name} WHERE id = %s"
            result = self._execute_query(query, (entity_id,))
            return result[0]["data"] if result else {}
        else:
            # Get all columns for schema-based table
            query = f"SELECT * FROM {collection_name} WHERE id = %s"
            result = self._execute_query(query, (entity_id,))
            
            if not result:
                return {}
                
            # Convert row to dict, handling arrays and objects
            row = result[0]
            data = {}
            
            for field_name, field_def in schema["properties"].items():
                if field_name in row:
                    value = row[field_name]
                    if field_def.get("type") == "array":
                        # PostgreSQL arrays come back as lists already
                        data[field_name] = value if value is not None else []
                    elif field_def.get("type") == "object" and value:
                        try:
                            data[field_name] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            data[field_name] = value
                    else:
                        data[field_name] = value
                    
            return data

    def get_entities(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get all entities in a collection."""
        schema = self.schemas.get(collection_name)
        
        if not schema or "properties" not in schema:
            # Use old JSONB approach if no schema
            query = f"SELECT data FROM {collection_name}"
            return [row["data"] for row in self._execute_query(query)]
        else:
            # Get all columns for schema-based table
            query = f"SELECT * FROM {collection_name}"
            results = self._execute_query(query)
            
            # Convert rows to dicts, parsing JSON for array/object fields
            entities = []
            for row in results:
                data = {}
                for field_name, field_def in schema["properties"].items():
                    if field_name in row:
                        value = row[field_name]
                        if field_def.get("type") in ("array", "object") and value:
                            try:
                                value = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                pass  # Keep original value if not valid JSON
                        data[field_name] = value
                entities.append(data)
                
            return entities

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
            schema = self.schemas.get(collection_name)
            
            if not schema or "properties" not in schema:
                # Use old JSONB approach if no schema
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
            else:
                # Build SET clause for schema-based table
                set_items = []
                values = []
                
                for field_name, value in data.items():
                    if field_name in schema["properties"] and field_name != "id":
                        set_items.append(f"{field_name} = %s")
                        values.append(
                            json.dumps(value) if isinstance(value, (dict, list))
                            else value
                        )
                
                if set_items:
                    set_items.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(entity_id)  # For WHERE clause
                    
                    if upsert:
                        # Build INSERT with ON CONFLICT
                        columns = ["id"] + list(data.keys())
                        placeholders = ["%s"] * len(columns)
                        insert_values = [entity_id] + values[:-1]  # Remove the WHERE id value
                        
                        query = f"""
                        INSERT INTO {collection_name} ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                        ON CONFLICT (id) DO UPDATE
                        SET {', '.join(set_items)}
                        """
                        self._execute_query(query, tuple(insert_values + values))
                    else:
                        query = f"""
                        UPDATE {collection_name}
                        SET {', '.join(set_items)}
                        WHERE id = %s
                        """
                        self._execute_query(query, tuple(values))
                        
        except Exception as e:
            raise DatabaseError(f"Update failed: {e}")

    def initialize_database(self) -> None:
        """Initialize database with current schema from definitions.py.
        
        This method:
        1. Creates tables based on current schema definitions
        2. Creates necessary indexes
        3. Stores schema definitions in memory for validation
        """
        try:
            # Get schema definitions
            schema_defs = get_database_schema()
            
            # Create tables from schema
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
            
            # Create necessary indexes for links table
            self._execute_query("""
                CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_collection, from_id);
                CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_collection, to_id);
                CREATE INDEX IF NOT EXISTS idx_links_type ON links(link_type);
            """)
            
            # Store schemas in memory for validation
            self.schemas = schema_defs
            
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {e}")

    def query_entities(
        self,
        collection_name: str,
        query: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters and optional sorting.
        
        Args:
            collection_name: Name of collection to query
            query: Dict of field-value pairs to filter by
            sort_by: Field to sort results by
            sort_order: Sort direction ("asc" or "desc")
            limit: Maximum number of results to return
            
        Returns:
            List of matching entities
        """
        try:
            # Build WHERE clause from query
            where_clauses = []
            values = []
            for field, value in query.items():
                where_clauses.append(f"{field} = %s")
                values.append(value)
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            
            # Add sorting if specified
            order_sql = ""
            if sort_by:
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                order_sql = f" ORDER BY {sort_by} {direction}"
            
            # Add limit if specified
            limit_sql = f" LIMIT {limit}" if limit else ""
            
            # Build and execute query
            sql = f"""
                SELECT * FROM {collection_name}
                WHERE {where_sql}{order_sql}{limit_sql}
            """
            
            result = self._execute_query(sql, tuple(values))
            
            # Convert rows to dicts with proper types
            schema = self.schemas.get(collection_name, {})
            entities = []
            
            for row in result:
                entity = {}
                for field_name, value in row.items():
                    if schema and "properties" in schema:
                        field_def = schema["properties"].get(field_name, {})
                        if field_def.get("type") == "array" and value is not None:
                            # Handle array fields
                            entity[field_name] = value
                        elif field_def.get("type") == "object" and value:
                            # Handle JSON fields
                            try:
                                entity[field_name] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                entity[field_name] = value
                        else:
                            entity[field_name] = value
                    else:
                        entity[field_name] = value
                entities.append(entity)
            
            return entities
            
        except Exception as e:
            raise DatabaseError(f"Failed to query entities: {e}")
