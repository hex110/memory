import json
import platform
import subprocess
from pathlib import Path
from InquirerPy import inquirer

from src.utils.config import get_default_config
from src.utils.logging import get_logger

logger = get_logger(__name__)

def is_postgres_running():
    """Checks if PostgreSQL is running."""
    try:
        if platform.system() == "Windows":
            # Windows command to check service status
            output = subprocess.check_output(["sc", "query", "postgresql"]).decode()
            return "STATE" in output and "RUNNING" in output
        else:
            # Linux/macOS command to check service status
            # Note: The service name might vary (e.g., postgresql, postgres)
            output = subprocess.check_output(["systemctl", "is-active", "postgresql"]).decode()
            return output.strip() == "active"
    except subprocess.CalledProcessError:
        return False
    
def get_postgres_installation_instructions():
    """Provides platform-specific instructions for installing PostgreSQL."""
    system = platform.system()

    if system == "Linux":
        return """
        \nPostgreSQL Installation (Linux):
        1. Arch Linux:
            sudo pacman -S postgresql
            sudo -u postgres initdb -D /var/lib/postgres/data  # Initialize (first time)
            sudo systemctl start postgresql
        2. Ubuntu/Debian:
            sudo apt install postgresql
            # Service usually starts automatically
        """
    elif system == "Darwin":  # macOS
        return """
        \nPostgreSQL Installation (macOS):
        1. Install Homebrew (if you don't have it):
           /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        2. Install PostgreSQL:
           brew install postgresql
        3. Start PostgreSQL:
           brew services start postgresql
        """
    elif system == "Windows":
        return """
        \nPostgreSQL Installation (Windows):
        1. Download the installer from: https://www.postgresql.org/download/windows/
        2. Run the installer and follow the instructions.
        3. The installer will typically set up PostgreSQL as a service.
        """
    else:
        return "Instructions for your operating system are not available. Please refer to the PostgreSQL documentation."

async def run_tutorial(config_path: Path):
    """Guides the user through the first-time setup."""

    config = {}
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return
    
    if not config.get("enable_tutorial", True):
        # logger.info("Tutorial is disabled. Skipping.")
        return
        
    logger.info("Starting first-time setup tutorial...")

    # --- PostgreSQL Setup ---
    if is_postgres_running():
        logger.info("PostgreSQL is already running.")
    else:
        logger.info(get_postgres_installation_instructions())

        install_postgres = inquirer.confirm(
            message="Do you want to try installing PostgreSQL now (if not installed)?",
            default=False
        ).execute()

        if install_postgres:
            # We could add basic installation scripts here for supported platforms
            # but it's generally safer to guide the user to do it manually.
            logger.info("Please follow the instructions above to install PostgreSQL.")

        setup_db = inquirer.confirm(
            message="Have you set up the 'memory_db' database and user (if not using peer authentication)?",
            default=False
        ).execute()

        if not setup_db:
            logger.info("""
            \nDatabase Setup:
            1. Create a PostgreSQL user matching your system user (for peer authentication):
               sudo -u postgres createuser -s $USER
            2. Create the database:
               sudo -u postgres createdb memory_db

            OR (if you want a custom user):
            1. Connect to PostgreSQL:
               sudo -u postgres psql
            2. In the PostgreSQL prompt:
               CREATE USER your_user WITH PASSWORD 'your_password';
               CREATE DATABASE memory_db OWNER your_user;
               \\q
            3. Update your .env file with the credentials.
            """)
            logger.info("Please set up the database and then restart the application.")
            return

    # --- Google Cloud TTS Setup ---
    setup_tts = await inquirer.confirm(
        message="Do you want to set up Google Cloud Text-to-Speech (TTS)?",
        default=False
    ).execute_async()

    if setup_tts:
        logger.info("""
        \nGoogle Cloud TTS Setup:
        1. Create a Google Cloud project: https://console.cloud.google.com/projectcreate
        2. Enable billing for your project.
        3. Enable the Text-to-Speech API: https://console.cloud.google.com/speech/text-to-speech
        4. Install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install
        5. Authenticate using:
           gcloud auth application-default login
        """)

        tts_configured = await inquirer.confirm(
            message="Have you completed the Google Cloud TTS setup?",
            default=False
        ).execute_async()

        config["tts_enabled"] = tts_configured
    else:
        config["tts_enabled"] = False

    # --- Finish ---
    config["enable_tutorial"] = False
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Tutorial completed. Restart the application.")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")