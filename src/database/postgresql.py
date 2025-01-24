"""PostgreSQL implementation of the database interface."""

import time
import psycopg2
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from psycopg2 import pool
from psycopg2.extras import Json, register_uuid
from src.interfaces.postgresql import DatabaseInterface
from src.utils.exceptions import DatabaseError
from src.schemas.validator import SchemaValidator

class PostgreSQLDatabase(DatabaseInterface):
   """PostgreSQL implementation of the database interface with schema validation."""

   def __init__(self, config: Dict[str, Any]):
       """Initialize PostgreSQL connection and schemas.
       
       Args:
           config: Database configuration
       """
       self.config = config
       self.validator = SchemaValidator()
       
       # Build connection parameters
       conn_params = {
           "host": config.get("host"),
           "database": config.get("database"),
           "user": config.get("user"),
       }
       if config.get("password"):
           conn_params["password"] = config["password"]
       
       try:
           self.connection_pool = pool.ThreadedConnectionPool(
               1,  # Minimum connections
               10, # Maximum connections
               **conn_params
           )
           # Register UUID type with psycopg2
           register_uuid()
           
       except psycopg2.OperationalError as e:
           if "Connection refused" in str(e):
               raise DatabaseError(
                   "\nPostgreSQL connection failed. Please check:\n"
                   "1. Is PostgreSQL installed?\n"
                   "2. Is PostgreSQL service running?\n"
                   "3. Have you initialized the database?\n"
                   "4. Can your user access PostgreSQL?\n"
                   "5. Check your database settings in config.json and .env\n"
               ) from e
           elif "database" in str(e) and "does not exist" in str(e):
               raise DatabaseError(
                   f"\nDatabase '{conn_params['database']}' does not exist. To create it:\n"
                   "1. Connect to PostgreSQL:\n"
                   "   sudo -u postgres psql\n"
                   f"2. Create database: CREATE DATABASE {conn_params['database']};\n"
               ) from e
           else:
               raise DatabaseError(f"Database connection failed: {e}") from e

   def _convert_to_pg(self, value: Any, field_type: str) -> Any:
       """Convert Python value to PostgreSQL format."""
       if value is None:
           return None
           
       if field_type == "uuid":
           return str(value) if isinstance(value, uuid.UUID) else value
       elif field_type == "timestamp with time zone":
           if isinstance(value, str):
               return value
           elif isinstance(value, datetime):
               return value.isoformat()
           return value
       elif field_type == "jsonb":
           return Json(value)
       elif field_type.endswith("[]"):
           if not isinstance(value, list):
               return [value]
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
           return value if isinstance(value, dict) else json.loads(value)
       elif field_type.endswith("[]"):
           return list(value) if value else []
       return value

   def _execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
       """Execute a query and return results."""
       conn = None
       for attempt in range(3):  # Try 3 times
        try:
            conn = self.connection_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    conn.commit()
                    if cur.description:
                        cols = [col.name for col in cur.description]
                        return [dict(zip(cols, row)) for row in cur.fetchall()]
                    return []
            except Exception as e:
                conn.rollback()
                raise
            finally:
                self.connection_pool.putconn(conn)
        except pool.PoolError:
            if attempt == 2:  # Last attempt
                raise DatabaseError("Database connection pool exhausted")
            time.sleep(0.1 * (attempt + 1))  # Progressive backoff

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

   def initialize_database(self) -> None:
       """Initialize database with current schema.
       
       Creates tables and sets up triggers for timestamp management.
       """
       try:
           schema_defs = self.validator.database_schema
           
           # Create updated_at trigger function
           self._execute_query("""
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
               self._execute_query(create_table)
               
               # Add updated_at trigger
               self._execute_query(f"""
                   DROP TRIGGER IF EXISTS update_timestamp_trigger ON {table_name};
                   CREATE TRIGGER update_timestamp_trigger
                   BEFORE UPDATE ON {table_name}
                   FOR EACH ROW
                   EXECUTE FUNCTION update_timestamp();
               """)
               
       except Exception as e:
           raise DatabaseError(f"Database initialization failed: {e}")

   def add_entity(self, collection_name: str, data: Dict[str, Any]) -> str:
       """Add a new entity to a collection."""
       try:
           schema = self.validator.database_schema[collection_name]
           self.validator.validate_data(data, schema)
           
           fields = []
           values = []
           placeholders = []
           count = 1
           
           for field_name, field_def in schema["properties"].items():
               if field_name in data:
                   fields.append(field_name)
                   values.append(self._convert_to_pg(data[field_name], field_def["type"]))
                   placeholders.append(f"${count}")
                   count += 1
           
           query = f"""
           INSERT INTO {collection_name} ({', '.join(fields)})
           VALUES ({', '.join(placeholders)})
           RETURNING id
           """
           
           result = self._execute_query(query, tuple(values))
           return str(result[0]["id"])
           
       except Exception as e:
           raise DatabaseError(f"Failed to add entity: {e}")

   def get_entity(self, collection_name: str, entity_id: str) -> Dict[str, Any]:
       """Get an entity by ID."""
       try:
           schema = self.validator.database_schema[collection_name]
           query = f"SELECT * FROM {collection_name} WHERE id = %s"
           result = self._execute_query(query, (entity_id,))
           
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

   def get_entities(self, collection_name: str) -> List[Dict[str, Any]]:
       """Get all entities in a collection."""
       try:
           schema = self.validator.database_schema[collection_name]
           query = f"SELECT * FROM {collection_name}"
           results = self._execute_query(query)
           
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

   def update_entity(self, collection_name: str, entity_id: str,
                    data: Dict[str, Any], upsert: bool = False) -> None:
       """Update an entity."""
       try:
           schema = self.validator.database_schema[collection_name]
           self.validator.validate_data(data, schema)
           
           set_items = []
           values = []
           count = 1
           
           for field_name, value in data.items():
               if field_name in schema["properties"]:
                   set_items.append(f"{field_name} = ${count}")
                   values.append(self._convert_to_pg(
                       value,
                       schema["properties"][field_name]["type"]
                   ))
                   count += 1
                   
           values.append(entity_id)  # For WHERE clause
           
           if upsert:
               fields = list(data.keys())
               placeholders = [f"${i+1}" for i in range(len(fields))]
               
               query = f"""
               INSERT INTO {collection_name} (id, {', '.join(fields)})
               VALUES ($1, {', '.join(placeholders)})
               ON CONFLICT (id) DO UPDATE
               SET {', '.join(set_items)}
               """
               self._execute_query(query, (entity_id, *values[:-1]))
           else:
               query = f"""
               UPDATE {collection_name}
               SET {', '.join(set_items)}
               WHERE id = ${count}
               """
               self._execute_query(query, tuple(values))
               
       except Exception as e:
           raise DatabaseError(f"Update failed: {e}")

   def delete_entity(self, collection_name: str, entity_id: str) -> None:
       """Delete an entity."""
       try:
           query = f"DELETE FROM {collection_name} WHERE id = %s"
           self._execute_query(query, (entity_id,))
       except Exception as e:
           raise DatabaseError(f"Delete failed: {e}")

   def query_entities(
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
           count = 1
           
           for field, value in query.items():
               if field in schema["properties"]:
                   if isinstance(value, dict):
                       # Handle comparison operators
                       for op, op_value in value.items():
                           operator = {
                               ">=": ">=", "<=": "<=", ">": ">",
                               "<": "<", "=": "=", "!=": "!="
                           }.get(op)
                           if operator:
                               where_clauses.append(f"{field} {operator} ${count}")
                               values.append(self._convert_to_pg(
                                   op_value,
                                   schema["properties"][field]["type"]
                               ))
                               count += 1
                   else:
                       where_clauses.append(f"{field} = ${count}")
                       values.append(self._convert_to_pg(
                           value,
                           schema["properties"][field]["type"]
                       ))
                       count += 1
           
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
           
           results = self._execute_query(query, tuple(values))
           
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

   def close(self) -> None:
       """Close all database connections."""
       self.connection_pool.closeall()