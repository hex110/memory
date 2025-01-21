"""Schema migration management.

This module handles schema migrations for both database and ontology schemas.
It provides:
1. Version tracking for schemas
2. Forward and backward migrations
3. Safe schema evolution
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from src.utils.exceptions import MigrationError
from src.schemas.validator import SchemaValidator

logger = logging.getLogger(__name__)

class Migration:
    """Represents a single schema migration."""
    
    def __init__(self, version: str, description: str):
        """Initialize a migration.
        
        Args:
            version: Version identifier (e.g., "001")
            description: Description of what this migration does
        """
        self.version = version
        self.description = description
        self.upgrade_steps: List[Callable] = []
        self.downgrade_steps: List[Callable] = []
        self.validate_steps: List[Callable] = []
    
    def upgrade(self, step: Callable) -> Callable:
        """Decorator to add an upgrade step.
        
        Args:
            step: Function that performs the upgrade
            
        Returns:
            The decorated function
        """
        self.upgrade_steps.append(step)
        return step
    
    def downgrade(self, step: Callable) -> Callable:
        """Decorator to add a downgrade step.
        
        Args:
            step: Function that performs the downgrade
            
        Returns:
            The decorated function
        """
        self.downgrade_steps.append(step)
        return step

    def validate(self, step: Callable) -> Callable:
        """Decorator to add a validation step.
        
        Args:
            step: Function that performs the validation
            
        Returns:
            The decorated function
        """
        self.validate_steps.append(step)
        return step

class MigrationManager:
    """Manages schema migrations."""
    
    def __init__(self, migrations_dir: str, validator: SchemaValidator):
        """Initialize the migration manager.
        
        Args:
            migrations_dir: Directory containing migration files
            validator: Schema validator instance
        """
        self.migrations_dir = Path(migrations_dir)
        self.validator = validator
        self.migrations: Dict[str, Migration] = {}
        self.current_version = "000"  # Initial version
        
        # Load existing migrations
        self._load_migrations()
        
        # Load current version
        version_file = self.migrations_dir / "version.json"
        if version_file.exists():
            with open(version_file) as f:
                self.current_version = json.load(f)["version"]
    
    def _load_migrations(self) -> None:
        """Load all migration files from the migrations directory."""
        if not self.migrations_dir.exists():
            return
            
        for file in sorted(self.migrations_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
                
            # Import migration module
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"migration_{file.stem}",
                str(file)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get migration instance
                if hasattr(module, "migration"):
                    self.migrations[module.migration.version] = module.migration
    
    def create_migration(self, description: str) -> str:
        """Create a new migration file.
        
        Args:
            description: Description of what this migration does
            
        Returns:
            Path to the created migration file
        """
        # Ensure migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate new version number
        versions = [m.version for m in self.migrations.values()]
        new_version = f"{int(max(versions or ['000'])) + 1:03d}"
        
        # Create migration file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{new_version}_{timestamp}_{description.lower().replace(' ', '_')}.py"
        file_path = self.migrations_dir / filename
        
        template = f'''"""Migration {new_version}: {description}"""

from src.schemas.migrator import Migration

migration = Migration("{new_version}", "{description}")

@migration.upgrade
def upgrade(db, ontology):
    """Upgrade to version {new_version}."""
    # TODO: Implement upgrade steps
    pass

@migration.downgrade
def downgrade(db, ontology):
    """Downgrade from version {new_version}."""
    # TODO: Implement downgrade steps
    pass
'''
        
        with open(file_path, "w") as f:
            f.write(template)
        
        return str(file_path)
    
    def get_migrations(self, target_version: Optional[str] = None) -> List[Migration]:
        """Get migrations needed to reach target version.
        
        Args:
            target_version: Version to migrate to (latest if None)
            
        Returns:
            List of migrations to apply
        """
        if target_version is None:
            target_version = max(self.migrations.keys())
            
        current = int(self.current_version)
        target = int(target_version)
        
        if current == target:
            return []
            
        versions = sorted(
            [v for v in self.migrations.keys()],
            key=lambda x: int(x)
        )
        
        if current < target:
            # Upgrading
            needed = [v for v in versions if current < int(v) <= target]
            return [self.migrations[v] for v in needed]
        else:
            # Downgrading
            needed = [v for v in versions if target < int(v) <= current]
            return [self.migrations[v] for v in reversed(needed)]
    
    def migrate(self, db: Any, ontology: Any, target_version: Optional[str] = None) -> None:
        """Apply migrations to reach target version.
        
        Args:
            db: Database instance
            ontology: Ontology instance
            target_version: Version to migrate to (latest if None)
            
        Raises:
            MigrationError: If migration fails
        """
        migrations = self.get_migrations(target_version)
        if not migrations:
            logger.info("No migrations needed")
            return
            
        current = int(self.current_version)
        for migration in migrations:
            target = int(migration.version)
            
            try:
                logger.info(f"Migrating from {current} to {target}")
                
                # Run validation steps first
                for step in migration.validate_steps:
                    step(db, ontology)
                
                if current < target:
                    # Upgrading
                    for step in migration.upgrade_steps:
                        step(db, ontology)
                else:
                    # Downgrading
                    for step in migration.downgrade_steps:
                        step(db, ontology)
                
                # Update version
                self.current_version = migration.version
                with open(self.migrations_dir / "version.json", "w") as f:
                    json.dump({"version": migration.version}, f)
                
                current = target
                
            except Exception as e:
                raise MigrationError(
                    f"Failed to migrate to version {target}: {str(e)}"
                ) from e
        
        logger.info("Migration complete") 