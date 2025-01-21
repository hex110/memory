"""Interface definition for schema migrations.

This module defines how schema migrations should be implemented.
A migration represents a change to either the database schema,
ontology schema, or both, while maintaining data integrity.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol
from datetime import datetime

class MigrationStep(Protocol):
    """Protocol for migration steps (both upgrade and downgrade)."""
    
    def __call__(self, db: Any, ontology: Any) -> None:
        """Execute the migration step.
        
        Args:
            db: Database instance that implements DatabaseInterface
            ontology: Ontology instance that implements OntologyInterface
            
        The step should:
        1. Make schema changes (e.g., ALTER TABLE, ADD COLUMN)
        2. Transform existing data if needed
        3. Update ontology definitions if needed
        4. Maintain referential integrity
        5. Be idempotent (safe to run multiple times)
        """
        ...

class MigrationInterface(ABC):
    """Interface for schema migrations.
    
    A migration represents a single atomic change to the system's schemas.
    It must provide both upgrade (forward) and downgrade (rollback) capabilities.
    """
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Get the migration version.
        
        Returns:
            str: Version identifier (e.g., "001", "002", etc.)
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the migration description.
        
        Returns:
            str: Human-readable description of what this migration does
        """
        pass
    
    @property
    @abstractmethod
    def created_at(self) -> datetime:
        """Get migration creation timestamp.
        
        Returns:
            datetime: When this migration was created
        """
        pass
    
    @abstractmethod
    def upgrade(self, db: Any, ontology: Any) -> None:
        """Upgrade the schemas to this version.
        
        Args:
            db: Database instance
            ontology: Ontology instance
            
        This method should:
        1. Make all necessary schema changes
        2. Transform existing data to match new schema
        3. Maintain data integrity
        4. Be transactional (all or nothing)
        5. Be reversible via downgrade()
        
        Raises:
            MigrationError: If upgrade fails
        """
        pass
    
    @abstractmethod
    def downgrade(self, db: Any, ontology: Any) -> None:
        """Downgrade the schemas from this version.
        
        Args:
            db: Database instance
            ontology: Ontology instance
            
        This method should:
        1. Revert all schema changes made in upgrade()
        2. Transform data back to previous format
        3. Maintain data integrity
        4. Be transactional (all or nothing)
        
        Raises:
            MigrationError: If downgrade fails
        """
        pass
    
    @abstractmethod
    def validate(self, db: Any, ontology: Any) -> None:
        """Validate that the migration can be applied.
        
        Args:
            db: Database instance
            ontology: Ontology instance
            
        This method should check:
        1. Required tables/columns exist
        2. Data is in expected format
        3. No conflicts with existing schema
        4. Dependencies are satisfied
        
        Raises:
            ValidationError: If validation fails
        """
        pass

class MigrationManagerInterface(ABC):
    """Interface for managing schema migrations.
    
    The migration manager handles:
    1. Tracking current schema version
    2. Loading and organizing migrations
    3. Executing migrations in correct order
    4. Ensuring data integrity during migrations
    """
    
    @abstractmethod
    def create_migration(self, description: str) -> str:
        """Create a new migration file.
        
        Args:
            description: What this migration does
            
        Returns:
            str: Path to created migration file
            
        The created file should:
        1. Have a unique version number
        2. Include upgrade() and downgrade() methods
        3. Include proper documentation
        4. Follow naming convention: {version}_{timestamp}_{description}.py
        """
        pass
    
    @abstractmethod
    def get_current_version(self) -> str:
        """Get current schema version.
        
        Returns:
            str: Current version identifier
        """
        pass
    
    @abstractmethod
    def get_available_versions(self) -> List[str]:
        """Get all available migration versions.
        
        Returns:
            List[str]: Available version identifiers, sorted
        """
        pass
    
    @abstractmethod
    def migrate(self, target_version: Optional[str] = None) -> None:
        """Migrate schemas to target version.
        
        Args:
            target_version: Version to migrate to (latest if None)
            
        This method should:
        1. Determine required migrations
        2. Validate migrations can be applied
        3. Execute migrations in transaction
        4. Update version tracking
        5. Handle errors and rollback if needed
        
        Raises:
            MigrationError: If migration fails
        """
        pass 