"""Interface definition for schema migrations.

This module defines the interface for managing database and ontology schema migrations.
The migration system is designed around these key concepts:

1. Versioned Migrations:
   - Each migration has a unique version number (e.g. "001")
   - Migrations can be applied forward (upgrade) or backward (downgrade)
   - Version history is tracked in the database

2. Validation:
   - Each migration can include validation steps
   - Validates if migration can be safely applied
   - Checks database state and constraints

3. Atomic Operations:
   - Migrations use transactions where possible
   - Rollback on failure to maintain consistency
   - Version tracking is updated atomically

Example of creating a new migration:

```python
from src.schemas.migrator import Migration

# Create migration with version and description
migration = Migration("002", "Add user preferences")

@migration.upgrade
def upgrade(db, ontology):
    '''Upgrade to version 002'''
    # Create new table
    db._execute_query('''
        CREATE TABLE user_preferences (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            preferences JSONB NOT NULL DEFAULT '{}'
        )
    ''')
    
    # Update version
    db._execute_query(
        "UPDATE schema_versions SET version = %s WHERE id = 'current'",
        ("002",)
    )

@migration.downgrade
def downgrade(db, ontology):
    '''Downgrade from version 002'''
    # Remove table
    db._execute_query("DROP TABLE IF EXISTS user_preferences")
    
    # Revert version
    db._execute_query(
        "UPDATE schema_versions SET version = %s WHERE id = 'current'",
        ("001",)
    )

@migration.validate
def validate(db, ontology):
    '''Validate migration can be applied'''
    # Check if users table exists
    db._execute_query(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')"
    )
```

Required files for migrations:
1. Migration file in migrations folder (e.g. 002_add_user_preferences.py)
2. version.json to track current version
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable

class MigrationInterface(ABC):
    """Interface for database schema migrations.
    
    This interface defines how migrations should be structured and executed.
    Most migrations should use the Migration class rather than implementing
    this directly, as it provides:
    - Version tracking
    - Validation support
    - Transaction management
    - Error handling
    """
    
    @abstractmethod
    def __init__(self, version: str, description: str):
        """Initialize a new migration.
        
        Args:
            version: Version number (e.g. "001", "002")
            description: Description of what this migration does
        """
        pass
    
    @abstractmethod
    def upgrade(self, step: Callable) -> Callable:
        """Decorator to add an upgrade step.
        
        The decorated function should:
        1. Make schema changes
        2. Migrate any necessary data
        3. Update version number
        
        Args:
            step: Function that performs the upgrade
            
        Returns:
            The decorated function
            
        Example:
            @migration.upgrade
            def upgrade(db, ontology):
                # Make schema changes
                db._execute_query("CREATE TABLE ...")
                # Update version
                db._execute_query("UPDATE schema_versions ...")
        """
        pass
    
    @abstractmethod
    def downgrade(self, step: Callable) -> Callable:
        """Decorator to add a downgrade step.
        
        The decorated function should:
        1. Revert schema changes
        2. Restore data if needed
        3. Update version number
        
        Args:
            step: Function that performs the downgrade
            
        Returns:
            The decorated function
            
        Example:
            @migration.downgrade
            def downgrade(db, ontology):
                # Revert schema changes
                db._execute_query("DROP TABLE ...")
                # Update version
                db._execute_query("UPDATE schema_versions ...")
        """
        pass
    
    @abstractmethod
    def validate(self, step: Callable) -> Callable:
        """Decorator to add a validation step.
        
        The decorated function should:
        1. Check if migration can be applied
        2. Verify database state
        3. Check constraints
        
        Args:
            step: Function that performs validation
            
        Returns:
            The decorated function
            
        Example:
            @migration.validate
            def validate(db, ontology):
                # Check prerequisites
                db._execute_query("SELECT EXISTS ...")
        """
        pass

class MigrationManagerInterface(ABC):
    """Interface for managing schema migrations.
    
    This interface defines how migrations should be managed and executed.
    It handles:
    - Loading migrations
    - Tracking versions
    - Executing migrations
    - Validation
    """
    
    @abstractmethod
    def __init__(self, migrations_dir: str, validator: Any):
        """Initialize the migration manager.
        
        Args:
            migrations_dir: Directory containing migration files
            validator: Schema validator instance
        """
        pass
    
    @abstractmethod
    def create_migration(self, description: str) -> str:
        """Create a new migration file.
        
        Args:
            description: Description of what this migration does
            
        Returns:
            Path to the created migration file
            
        Example:
            path = manager.create_migration("Add user preferences")
        """
        pass
    
    @abstractmethod
    def get_migrations(self, target_version: Optional[str] = None) -> List[Any]:
        """Get migrations needed to reach target version.
        
        Args:
            target_version: Version to migrate to (latest if None)
            
        Returns:
            List of migrations to apply
            
        Example:
            migrations = manager.get_migrations("002")
        """
        pass
    
    @abstractmethod
    def migrate(self, db: Any, ontology: Any, target_version: Optional[str] = None) -> None:
        """Apply migrations to reach target version.
        
        Args:
            db: Database instance
            ontology: Ontology instance
            target_version: Version to migrate to (latest if None)
            
        Example:
            manager.migrate(db, ontology, "002")
        """
        pass 