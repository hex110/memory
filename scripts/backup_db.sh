#!/bin/bash

# Load database configuration from config.json
DB_NAME=$(jq -r '.database.database' src/config.json)
DB_USER=$(jq -r '.database.user' src/config.json)
DB_HOST=$(jq -r '.database.host' src/config.json)

# Create backups directory if it doesn't exist
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql"

echo "Creating backup of database $DB_NAME..."
pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup created successfully at $BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi

# If --reset flag is provided, drop and recreate the database
if [ "$1" == "--reset" ]; then
    echo "Dropping database $DB_NAME..."
    dropdb -h "$DB_HOST" -U "$DB_USER" "$DB_NAME"
    
    echo "Creating fresh database $DB_NAME..."
    createdb -h "$DB_HOST" -U "$DB_USER" "$DB_NAME"
    
    echo "Database reset complete. Run the application to initialize the new schema."
fi 