# Memory Project

A Python-based project for managing and analyzing conversations using Language Learning Models (LLMs).

## Setup

1. **Clone the repository:**

    ```bash
    git clone [your-repo-url]
    cd Memory
    ```

2. **Create and activate a virtual environment:**

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Configure environment variables:**

    - Copy `.env.example` to `.env`:

        ```bash
        cp .env.example .env
        ```

    - Fill in your API keys and database credentials in the `.env` file.

5. **Set up the database:**

    First, ensure PostgreSQL is installed and running:

    - **Arch Linux:**
        ```bash
        # Install PostgreSQL
        sudo pacman -S postgresql

        # Initialize the database (first time only)
        sudo -u postgres initdb -D /var/lib/postgres/data

        # Start PostgreSQL service
        sudo systemctl start postgresql
        ```

    - **Ubuntu/Debian:**
        ```bash
        # Install PostgreSQL
        sudo apt install postgresql

        # PostgreSQL service starts automatically
        # Check status if needed:
        sudo systemctl status postgresql
        ```

    - **macOS:**
        ```bash
        # Install PostgreSQL
        brew install postgresql

        # Start PostgreSQL service
        brew services start postgresql
        ```

    Then, set up the database and user:

    ```bash
    # Create a PostgreSQL user matching your system user
    sudo -u postgres createuser -s $USER

    # Create the database
    createdb memory_db
    ```

    If you prefer to use different credentials:
    1. Create a custom user and database:
        ```bash
        # Connect to PostgreSQL
        sudo -u postgres psql

        # In the PostgreSQL prompt:
        CREATE USER your_user WITH PASSWORD 'your_password';
        CREATE DATABASE memory_db OWNER your_user;
        \q
        ```
    2. Update the credentials in your `.env` file:
        ```
        DB_HOST=localhost
        DB_NAME=memory_db
        DB_USER=your_user
        DB_PASSWORD=your_password
        ```

    Common issues:
    - If you get "peer authentication failed", you may need to edit `pg_hba.conf`
    - If you get "database does not exist", run `createdb memory_db`
    - If you get "permission denied", ensure your user has the correct privileges

## Project Structure

- **src/**: Main source code directory
    - **agent/**: Contains LLM agent implementations
        - **prompts/**: System and query prompts for different agents
    - **api/**: FastAPI server implementation
    - **database/**: Database connection and operations
    - **interfaces/**: API interface definitions
    - **schemas/**: Data model definitions
        - **definitions.py**: Single source of truth for database schema
    - **tests/**: Unit and integration tests
- **scripts/**: Utility scripts
    - `backup_db.sh`: Database backup and reset utility
- **backups/**: Database backup files
- `.gitignore`: Files and directories to ignore in git
- `README.md`: Project documentation
- `requirements.txt`: Project dependencies

## Running the Project

The application has two main modes:

1. **Start the API server:**

    ```bash
    python -m src.main -server
    ```

2. **Run conversation analysis:**

    ```bash
    python -m src.main -analyze
    ```

The API will be available at `http://localhost:8000`.

## Database Management

Use `scripts/backup_db.sh` for database backups and resets:

1. **Create a backup:**

    ```bash
    ./scripts/backup_db.sh
    ```

    Creates a timestamped backup in the `backups/` directory.

2. **Create a backup and reset the database:**

    ```bash
    ./scripts/backup_db.sh --reset
    ```

    This will:
    - Create a backup
    - Drop the existing database
    - Create a fresh database

    *Note:* Restart the application to initialize the new schema.

## Schema Management

The project uses a simple, direct schema management approach:

1. **Schema Definition**:
   - All database schemas are defined in `src/schemas/definitions.py`
   - This file is the single source of truth for database structure
   - Used by both database initialization and agent validation

2. **Making Schema Changes**:
   ```bash
   # 1. Update schema in src/schemas/definitions.py
   # 2. Backup and reset the database:
   ./scripts/backup_db.sh --reset
   # 3. Restart the application to apply new schema
   ```

3. **Database Reset**:
   - Creates a backup of current data
   - Drops all tables
   - Recreates tables using current schema from definitions.py
   - Fast and reliable way to update database structure

This approach favors simplicity and maintainability over version tracking, making it ideal for active development.

## License

This project is licensed under the European Union Public License 1.2 (EUPL-1.2). This license applies to all files in this repository and all previous commits, regardless of their date. The EUPL is a copyleft license that is compatible with several other open-source licenses, including the GPLv2, GPLv3, AGPLv3, and others (see the Appendix of the license for the full list of compatible licenses).
