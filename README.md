Okay, I've updated the `README.md` with a "For Mac Users" section at the top, providing the necessary instructions. I've also made some minor adjustments to the existing sections for clarity and consistency.

Here's the updated `README.md`:

```markdown
# Memory Project

A Python-based project for managing and analyzing conversations using Language Learning Models (LLMs).

## For Mac Users

**Important:** If you are on macOS, follow these additional steps to ensure the application can track keyboard and mouse inputs:

1. **Compile `mackeyserver`:**
    *   Open Terminal and navigate to the `src/utils/activity/compositor` directory:
        ```bash
        cd src/utils/activity/compositor
        ```
    *   Compile the Swift code:
        ```bash
        swiftc mackeyserver.swift -o mackeyserver
        ```
    *   This will create an executable file named `mackeyserver` in the same directory.

2. **Grant Accessibility Permissions:**
    *   Open **System Settings**.
    *   Go to **Privacy & Security**.
    *   Scroll down and select **Accessibility**.
    *   Click the **+** button.
    *   Navigate to the `src/utils/activity/compositor` directory in your project and select the compiled `mackeyserver` executable.
    *   **Enable** the toggle switch next to `mackeyserver`.
    *   You may need to restart your application or computer for the changes to take effect.

    **Note:** The application will log an error and exit if it fails to create an event tap due to missing Accessibility permissions.

## Setup

1. **Clone the repository:**

    ```bash
    git clone [your-repo-url]
    cd Memory
    ```

2. **Create and activate a virtual environment:**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On macOS/Linux
    .venv\Scripts\activate    # On Windows
    ```

3. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Rename `.env.example` and get your API key:**

    *   Rename the `.env.example` file to `.env`.
    *   Obtain your free Gemini API key from [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) and paste it into your `.env` file like this:

    ```
    GEMINI_API_KEY=your_api_key_here
    ```

5. **Run the application for the first time:**

    ```bash
    python -m src.main
    ```

    This will start the application and guide you through a first-time setup tutorial for PostgreSQL and optionally Google Cloud Text-to-Speech.

## First-Time Setup Tutorial

The first time you run the application, a tutorial will guide you through setting up the necessary components.

### PostgreSQL Setup

The application uses PostgreSQL as its database. The tutorial will provide instructions based on your operating system:

-   **Linux (Arch):**
    ```bash
    sudo pacman -S postgresql
    sudo -u postgres initdb -D /var/lib/postgres/data  # Initialize (first time)
    sudo systemctl start postgresql
    ```
-   **Linux (Ubuntu/Debian):**
    ```bash
    sudo apt install postgresql
    # Service usually starts automatically
    ```
-   **macOS:**
    ```bash
    brew install postgresql
    brew services start postgresql
    ```
-   **Windows:**
    -   Download the installer from: [https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)
    -   Run the installer and follow the instructions.

After installing, you need to create the database and potentially a user:

1. Create a PostgreSQL user matching your system user (for peer authentication):

    ```bash
    sudo -u postgres createuser -s $USER
    ```

2. Create the database:

    ```bash
    sudo -u postgres createdb memory_db
    ```

    **OR (if you want a custom user):**

    1. Connect to PostgreSQL:

        ```bash
        sudo -u postgres psql
        ```

    2. In the PostgreSQL prompt:

        ```sql
        CREATE USER your_user WITH PASSWORD 'your_password';
        CREATE DATABASE memory_db OWNER your_user;
        \q
        ```

    3. Update your `.env` file with the credentials:

        ```
        DB_HOST=localhost
        DB_NAME=memory_db
        DB_USER=your_user
        DB_PASSWORD=your_password
        ```

### Google Cloud Text-to-Speech (Optional)

If you want to use speech features, you can set up Google Cloud Text-to-Speech for free (up to 4 million characters a month (plenty)):

1. **Create a Google Cloud project:** [https://console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate)
2. **Enable billing** for your project.
3. **Enable the Text-to-Speech API:** [https://console.cloud.google.com/speech/text-to-speech](https://console.cloud.google.com/speech/text-to-speech)
4. **Install the Google Cloud SDK:** [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
5. **Authenticate:**
    ```bash
    gcloud auth application-default login
    ```
    Select your project during this step.

The tutorial will ask if you want to configure TTS. You can skip it and enable it later by editing `config.json`.

## Running the Project

The application has two main modes:

1. **Start Tracking**:

    ```bash
    python -m src.main
    ```
    And then choose "Start Tracking"

2. **Start the API server:**
    ```bash
    python -m src.main
    ```
    And then choose "Start Server"

3. **Run conversation analysis:**

    ```bash
    python -m src.main
    ```

    And then choose "Analyze Session"

The API will be available at `http://localhost:8000`.

**Monitoring Logs:**

Open a separate terminal and run:

```bash
tail -F Memory/memory_system.log
```

Keep this terminal side-by-side with the main application terminal to view logs in real time.

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

    -   Create a backup
    -   Drop the existing database
    -   Create a fresh database

    *Note:* Restart the application to initialize the new schema.

## Schema Management

The project uses a simple, direct schema management approach:

1. **Schema Definition**:
    -   All database schemas are defined in `src/schemas/definitions.py`
    -   This file is the single source of truth for database structure
    -   Used by both database initialization and agent validation

2. **Making Schema Changes**:

    ```bash
    # 1. Update schema in src/schemas/definitions.py
    # 2. Backup and reset the database:
    ./scripts/backup_db.sh --reset
    # 3. Restart the application to apply new schema
    ```

3. **Database Reset**:
    -   Creates a backup of current data
    -   Drops all tables
    -   Recreates tables using current schema from definitions.py
    -   Fast and reliable way to update database structure

This approach favors simplicity and maintainability over version tracking, making it ideal for active development.

## License

This project is licensed under the European Union Public License 1.2 (EUPL-1.2). This license applies to all files in this repository and all previous commits, regardless of their date. The EUPL is a copyleft license that is compatible with several other open-source licenses, including the GPLv2, GPLv3, AGPLv3, and others (see the Appendix of the license for the full list of compatible licenses).