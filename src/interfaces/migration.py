"""Interface definition for schema management.

This module defines how database schemas are managed in the system.
The schema management system is designed around these key concepts:

1. Single Source of Truth:
   - All schema definitions live in src/schemas/definitions.py
   - This file defines all tables, fields, and their types
   - Used for both database initialization and validation

2. Schema Changes:
   When you need to change the database structure:
   1. Update the schema in definitions.py
   2. Run ./scripts/backup_db.sh --reset
   3. Restart the application

3. Database Operations:
   - Backup: ./scripts/backup_db.sh
     Creates a timestamped backup in backups/
   
   - Reset: ./scripts/backup_db.sh --reset
     1. Creates a backup
     2. Drops all tables
     3. On next application start:
        - Creates tables from definitions.py
        - Initializes indexes
        - Sets up validation

Example of changing the schema:

1. Update definitions.py:
```python
def get_database_schema():
    return {
        "users": {
            "description": "System users",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "preferences": {"type": "object"}
            }
        }
    }
```

2. Reset and initialize:
```bash
# Backup and reset database
./scripts/backup_db.sh --reset

# Start application to apply new schema
python -m src.main -server  # or -analyze
```

Note: This approach favors simplicity and reliability over version tracking.
For production systems that need versioned migrations, consider using a tool
like Alembic or Flyway.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class DatabaseSchema(ABC):
    """Interface for database schema management.
    
    This interface defines how database schemas should be structured and managed.
    The primary implementation is in src/schemas/definitions.py.
    """
    
    @abstractmethod
    def get_database_schema(self) -> Dict[str, Any]:
        """Get the complete database schema definition.
        
        Returns:
            Dict containing all table definitions and their properties
            
        Example:
            {
                "table_name": {
                    "description": "What this table stores",
                    "properties": {
                        "field_name": {"type": "string"},
                        ...
                    }
                }
            }
        """
        pass
    
    @abstractmethod
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Schema definition for the table or None if not found
        """
        pass
    
    @abstractmethod
    def validate_schema(self, schema: Dict[str, Any]) -> bool:
        """Validate a schema definition.
        
        Args:
            schema: Schema to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass 