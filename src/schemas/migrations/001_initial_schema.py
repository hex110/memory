"""Migration 001: Initial schema setup"""

from src.schemas.migrator import Migration
from src.schemas.definitions import get_database_schema

migration = Migration("001", "Initial schema setup")

@migration.upgrade
def upgrade(db, ontology):
    """Create initial schema."""
    schema = get_database_schema()
    
    # Create each collection with its schema
    for collection_name, collection_schema in schema.items():
        db.create_collection(collection_name, collection_schema)
    
    # Set initial version
    db._execute_query(
        "INSERT INTO schema_versions (version) VALUES (%s) "
        "ON CONFLICT (id) DO UPDATE SET version = EXCLUDED.version",
        ("001",)
    )

@migration.downgrade
def downgrade(db, ontology):
    """Remove all tables (dangerous!)."""
    schema = get_database_schema()
    
    # Drop all collections
    for collection_name in schema.keys():
        db._execute_query(f"DROP TABLE IF EXISTS {collection_name}")
    
    # Reset version
    db._execute_query(
        "UPDATE schema_versions SET version = %s WHERE id = 'current'",
        ("000",)
    )

@migration.validate
def validate(db, ontology):
    """Validate migration can be applied."""
    # For initial migration, we just need to ensure we can connect to the DB
    db._execute_query("SELECT 1") 