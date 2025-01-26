"""PostgreSQL implementation of the database interface."""

import time
import asyncpg
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from asyncpg import pool
from src.interfaces.postgresql import DatabaseInterface
from src.utils.exceptions import DatabaseError
from src.schemas.validator import SchemaValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)

class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL implementation of the database interface with schema validation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize basic configuration.
       
        Args:
            config: Database configuration
        """
        self.config = config
        self.validator = SchemaValidator()
        self.pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> 'PostgreSQLDatabase':
        """Create and initialize a new database instance.
        
        Args:
            config: Database configuration
            
        Returns:
            Initialized database instance
            
        Raises:
            DatabaseError: If database connection fails
        """
        db = cls(config)
        await db.initialize()
        return db
        
    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        # Build connection parameters
        conn_params = {
            "host": self.config.get("host", "localhost"),
            "database": self.config.get("database"),
            "user": self.config.get("user"),
            "password": self.config.get("password"),
            # "min_size": 1,
            # "max_size": 10,
            "command_timeout": 60,
            "server_settings": {
                "application_name": "memory_system"
            }
        }

        try:
            # First try to establish a single connection to check if the database exists
            try:
                conn = await asyncpg.connect(**conn_params)
                await conn.close()
            except asyncpg.InvalidCatalogNameError:
                # Database doesn't exist, try to create it
                sys_conn_params = conn_params.copy()
                sys_conn_params["database"] = "postgres"  # Connect to default db
                sys_conn = await asyncpg.connect(**sys_conn_params)
                
                try:
                    await sys_conn.execute(
                        f"CREATE DATABASE {conn_params['database']}"
                    )
                finally:
                    await sys_conn.close()
            
            # Now create the connection pool
            self.pool = await asyncpg.create_pool(
                **conn_params,
                setup=self._setup_connection
            )

            # logger.debug("Database pool created")
        except asyncpg.PostgresError as e:
            if "Connection refused" in str(e):
                raise DatabaseError(
                    "\nPostgreSQL connection failed. Please check:\n"
                    "1. Is PostgreSQL installed?\n"
                    "2. Is PostgreSQL service running? Try: systemctl status postgresql\n"
                    "3. Is PostgreSQL accepting connections? Check pg_hba.conf\n"
                    "4. Can your user access PostgreSQL?\n"
                    "5. Check your database settings in config.json\n"
                    f"\nOriginal error: {e}"
                ) from e
            else:
                raise DatabaseError(f"Database connection failed: {e}") from e
        except Exception as e:
            raise DatabaseError(f"Unexpected error connecting to database: {e}") from e

    async def _setup_connection(self, connection: asyncpg.Connection) -> None:
        """Set up a new database connection with custom types and settings."""
        # Set up custom type codecs
        await connection.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        # Set up any other connection-specific settings
        await connection.execute("SET TIME ZONE 'UTC'")

    def _convert_to_pg(self, value: Any, field_type: str) -> Any:
        """Convert Python value to PostgreSQL format."""
        if value is None:
            return None
            
        if field_type == "jsonb":
            return json.dumps(value)
            
        if field_type == "uuid" and isinstance(value, str):
            return uuid.UUID(value)
        
        if field_type == "timestamp with time zone":
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value
        
        return value
 
    def _convert_from_pg(self, value: Any, field_type: str) -> Any:
        """Convert PostgreSQL value to Python format."""
        if value is None:
            return None
            
        if field_type == "uuid":
            return str(value)
        elif field_type == "timestamp with time zone":
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value
        elif field_type == "jsonb":
            if isinstance(value, (dict, list)):
                return value
            return json.loads(value) if value is not None else None
        elif field_type.endswith("[]"):
            return list(value) if value else []
        return value
 
    async def _execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        async with self.pool.acquire() as conn:
            try:
                if params:
                    result = await conn.fetch(query, *params)
                else:
                    result = await conn.fetch(query)
                return [dict(row) for row in result]
            except Exception as e:
                raise DatabaseError(f"Query execution failed: {e}")
 
    def _get_pg_type(self, schema_type: str) -> str:
        """Convert schema type to PostgreSQL type."""
        type_mapping = {
            "text": "TEXT",
            "integer": "INTEGER",
            "numeric": "NUMERIC",
            "boolean": "BOOLEAN",
            "jsonb": "JSONB",
            "uuid": "UUID",
            "timestamp with time zone": "TIMESTAMP WITH TIME ZONE",
            "bytea": "BYTEA"
        }
        
        # Handle array types
        if schema_type.endswith("[]"):
            base_type = schema_type[:-2]
            pg_base_type = type_mapping.get(base_type, "TEXT")
            return f"{pg_base_type}[]"
            
        return type_mapping.get(schema_type, "TEXT")
 
    async def initialize_database(self) -> None:
        """Initialize database with current schema."""
        try:
            schema_defs = self.validator.database_schema
            
            # Create updated_at trigger function
            await self._execute_query("""
                CREATE OR REPLACE FUNCTION update_timestamp()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            # Create tables from schema
            for table_name, schema in schema_defs.items():
                columns = []
                
                for field_name, field_def in schema["properties"].items():
                    pg_type = self._get_pg_type(field_def["type"])
                    nullable = "NULL" if field_def.get("nullable", True) else "NOT NULL"
                    default = ""
                    if "default" in field_def:
                        if pg_type == "JSONB":
                           default_value = field_def['default']
                           if isinstance(default_value,dict):
                             default = f"DEFAULT '{json.dumps(default_value)}'::jsonb"
                           else:
                             default = f"DEFAULT '{default_value}'::jsonb"
                        else:
                            default = f"DEFAULT {field_def['default']}" 
                    
                    if field_name == "id":
                        columns.append(f"id UUID PRIMARY KEY DEFAULT gen_random_uuid()")
                    else:
                        columns.append(f"{field_name} {pg_type} {nullable} {default}")
                
                create_table = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {', '.join(columns)}
                )
                """
                await self._execute_query(create_table)
                
                # Add updated_at trigger
                await self._execute_query(f"""
                    DROP TRIGGER IF EXISTS update_timestamp_trigger ON {table_name};
                    CREATE TRIGGER update_timestamp_trigger
                    BEFORE UPDATE ON {table_name}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_timestamp();
                """)
                
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {e}")

    def _get_cast_type(self, field_type: str) -> Optional[str]:
        """Get SQL cast type if needed for field type."""
        if field_type.endswith("[]"):
            base_type = field_type[:-2]
            pg_type = self._get_pg_type(base_type)
            return f"::{pg_type}[]"
        cast_mapping = {
            "uuid": "::uuid",
            "jsonb": "::jsonb",
            "timestamp with time zone": "::timestamp with time zone",
            "bytea": "::bytea"
        }
        return cast_mapping.get(field_type)

    async def add_entity(self, collection_name: str, data: Dict[str, Any]) -> str:
        """Add a new entity to a collection."""
        try:
            schema = self.validator.database_schema[collection_name]
            self.validator.validate_data(data, schema)
            
            fields = []
            values = []
            placeholders = []
            
            for field_name, field_def in schema["properties"].items():
                if field_name in data:
                    # if field_name != "screenshot":
                    #     logger.debug(f"Field name: {field_name}, field type: {field_def['type']}, value: {data[field_name]}")
                    fields.append(field_name)
                    values.append(self._convert_to_pg(data[field_name], field_def["type"]))
                    cast_type = self._get_cast_type(field_def["type"])
                    placeholders.append(f"${len(values)}{cast_type if cast_type else ''}")
            
            query = f"""
            INSERT INTO {collection_name} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING id
            """

            result = await self._execute_query(query, tuple(values))
            return str(result[0]["id"])
            
        except Exception as e:
            raise DatabaseError(f"Failed to add entity: {e}")

    async def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
        """Get an entity by ID."""
        try:
            schema = self.validator.database_schema[collection_name]
            query = f"SELECT * FROM {collection_name} WHERE id = $1"
            result = await self._execute_query(query, (uuid.UUID(entity_id),))
            
            if not result:
                return {}
                
            # Convert types
            entity = {}
            for field_name, field_def in schema["properties"].items():
                if field_name in result[0]:
                    entity[field_name] = self._convert_from_pg(
                        result[0][field_name],
                        field_def["type"]
                    )
            return entity
            
        except Exception as e:
            raise DatabaseError(f"Failed to get entity: {e}")

    async def get_entities(self, collection_name: str) -> List[Dict[str, Any]]:
        """Get all entities in a collection."""
        try:
            schema = self.validator.database_schema[collection_name]
            query = f"SELECT * FROM {collection_name}"
            results = await self._execute_query(query)
            
            entities = []
            for row in results:
                entity = {}
                for field_name, field_def in schema["properties"].items():
                    if field_name in row:
                        entity[field_name] = self._convert_from_pg(
                            row[field_name],
                            field_def["type"]
                        )
                entities.append(entity)
            return entities
            
        except Exception as e:
            raise DatabaseError(f"Failed to get entities: {e}")

    async def update_entity(self, collection_name: str, entity_id: str,
                     data: Dict[str, Any], upsert: bool = False) -> None:
        """Update an entity."""
        try:
            schema = self.validator.database_schema[collection_name]
            self.validator.validate_data(data, schema)
            
            set_items = []
            values = []
            param_count = 1
            
            for field_name, value in data.items():
                if field_name in schema["properties"]:
                    cast_type = self._get_cast_type(schema["properties"][field_name]["type"])
                    set_items.append(f"{field_name} = ${param_count}{cast_type if cast_type else ''}")
                    values.append(self._convert_to_pg(
                        value,
                        schema["properties"][field_name]["type"]
                    ))
                    param_count += 1
                    
            values.append(uuid.UUID(entity_id))  # For WHERE clause
            
            if upsert:
                fields = list(data.keys())
                placeholders = []
                for field_name in fields:
                    cast_type = self._get_cast_type(schema["properties"][field_name]["type"])
                    placeholders.append(f"${len(placeholders)+1}{cast_type if cast_type else ''}")
                
                query = f"""
                INSERT INTO {collection_name} (id, {', '.join(fields)})
                VALUES ($1, {', '.join(placeholders)})
                ON CONFLICT (id) DO UPDATE
                SET {', '.join(set_items)}
                """
                await self._execute_query(query, (uuid.UUID(entity_id), *values[:-1]))
            else:
                query = f"""
                UPDATE {collection_name}
                SET {', '.join(set_items)}
                WHERE id = ${param_count}
                """
                await self._execute_query(query, tuple(values))
                
        except Exception as e:
            raise DatabaseError(f"Update failed: {e}")

    async def delete_entity(self, collection_name: str, entity_id: str) -> None:
        """Delete an entity."""
        try:
            query = f"DELETE FROM {collection_name} WHERE id = $1"
            await self._execute_query(query, (uuid.UUID(entity_id),))
        except Exception as e:
            raise DatabaseError(f"Delete failed: {e}")

    async def query_entities(
        self,
        collection_name: str,
        query: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters and sorting."""
        try:
            schema = self.validator.database_schema[collection_name]
            where_clauses = []
            values = []
            param_count = 1
            
            for field, value in query.items():
                if field in schema["properties"]:
                    field_type = schema["properties"][field]["type"]
                    cast_type = self._get_cast_type(field_type)
                    
                    if isinstance(value, dict):
                        # Handle comparison operators
                        for op, op_value in value.items():
                            operator = {
                                ">=": ">=", "<=": "<=", ">": ">",
                                "<": "<", "=": "=", "!=": "!="
                            }.get(op)
                            if operator:
                                where_clauses.append(
                                    f"{field} {operator} ${param_count}{cast_type if cast_type else ''}"
                                )
                                values.append(self._convert_to_pg(
                                    op_value,
                                    field_type
                                ))
                                param_count += 1
                    else:
                        # Handle direct value comparison
                        where_clauses.append(
                            f"{field} = ${param_count}{cast_type if cast_type else ''}"
                        )
                        values.append(self._convert_to_pg(
                            value,
                            field_type
                        ))
                        param_count += 1
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
            order_sql = ""
            if sort_by and sort_by in schema["properties"]:
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                order_sql = f" ORDER BY {sort_by} {direction}"
            
            limit_sql = f" LIMIT {limit}" if limit else ""
            
            query = f"""
            SELECT * FROM {collection_name}
            WHERE {where_sql}{order_sql}{limit_sql}
            """
            
            results = await self._execute_query(query, tuple(values))
            
            entities = []
            for row in results:
                entity = {}
                for field_name, field_def in schema["properties"].items():
                    if field_name in row:
                        entity[field_name] = self._convert_from_pg(
                            row[field_name],
                            field_def["type"]
                        )
                entities.append(entity)
            
            return entities
            
        except Exception as e:
            raise DatabaseError(f"Query failed: {e}")

    async def close(self) -> None:
        """Close all database connections."""
        await self.pool.close()