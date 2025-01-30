"""Main entry point for the memory system."""
import os
import asyncio
import logging
import signal
import sys
import uuid
from pathlib import Path
import subprocess
import platform
from typing import Dict, Any, List
from InquirerPy import inquirer

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic") # getting pydantic warning for a google-genai file, and I don't want to modify the library file, so suppressing it for now

from src.utils.config import load_config_and_logging
from src.database.postgresql import PostgreSQLDatabase
from src.utils.logging import get_logger, configure_logging
from src.agent.monitor_agent import MonitorAgent
from src.agent.analysis_agent import AnalysisAgent
from src.agent.assistant_agent import AssistantAgent
from src.ontology.manager import OntologyManager
from src.utils.activity.activity_manager import ActivityManager
from src.utils.tts import TTSEngine
from uvicorn import Config, Server

# Import tutorial from utils
from src.utils.tutorial import run_tutorial, is_postgres_running

configure_logging()

logger = get_logger(__name__)

class MemorySystemCLI:
    """Command line interface for the memory system."""
    
    def __init__(self, config: Dict[str, Any], db: PostgreSQLDatabase, ontology_manager: OntologyManager):
        """Initialize the CLI interface."""
        self.config = config
        self.db = db
        self.tracking_active = False  # Now means persistence is active
        self.server_active = False
        self.tracking_task = None
        self.server_task = None
        self._shutdown_event = asyncio.Event()
        self.monitor_agent = None
        self.analysis_agent = None
        self.ontology_manager = ontology_manager
        self.responses_dir = Path("responses")
        self.responses_dir.mkdir(exist_ok=True)
        self.config_path = Path("config.json")
        self.is_shutting_down = False

        # Add new field for activity manager
        self.activity_manager = None
        self.tts_engine = None

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> 'MemorySystemCLI':
        """Create and initialize a new CLI instance."""
        
        # Initialize database and ontology manager
        db = None
        ontology_manager = None
        if not config.get("enable_tutorial", True):  # Only connect if tutorial is completed
            try:
                db = await PostgreSQLDatabase.create(config["database"])
                ontology_manager = await OntologyManager.create()
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                if not is_postgres_running():
                    attempt_start_postgres()
                else:
                    logger.info("Please ensure PostgreSQL is installed and running.")
                # return  # Exit if database connection fails

        # Create instance
        cli = cls(config, db, ontology_manager)
        
        # Initialize activity manager
        cli.activity_manager = ActivityManager(config)
        
        # Start tracking, video, and audio
        await cli.activity_manager.start_recording()
        
        # Initialize TTS engine
        cli.tts_engine = await TTSEngine.create(config.get("tts_enabled", False))
        
        # Create agents with components
        cli.monitor_agent = MonitorAgent(
            config=config,
            prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
            db=db,
            ontology_manager=ontology_manager,
            session_id=str(uuid.uuid4()),
            tts_engine=cli.tts_engine,
            activity_manager=cli.activity_manager
        )
        
        cli.analysis_agent = AnalysisAgent(
            config=config,
            prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
            db=db,
            ontology_manager=ontology_manager,
            session_id=cli.monitor_agent.session_id,
            tts_engine=cli.tts_engine
        )
        
        cli.assistant_agent = AssistantAgent(
            config=config,
            prompt_folder=os.path.join(os.path.dirname(__file__), "agent", "prompts"),
            db=db,
            ontology_manager=ontology_manager,
            tts_engine=cli.tts_engine,
            activity_manager=cli.activity_manager,
        )

        await cli.assistant_agent.start()

        return cli

    async def _start_tracking(self):
        """Start activity tracking (enable persistence)."""
        try:
            if not self.tracking_active:
                logger.info("Starting activity tracking")
                await self.activity_manager.input_tracker.enable_persistence()
                await self.monitor_agent.start_monitoring()
                await self.analysis_agent.start_analysis_cycles()
                self.tracking_active = True
                logger.info("Activity tracking started successfully")
        except Exception as e:
            raise

    async def _stop_tracking(self):
        """Stop activity tracking (disable persistence)."""
        try:
            if self.tracking_active:
                logger.info("Stopping activity tracking")
                await self.monitor_agent.stop_monitoring()
                await self.analysis_agent.stop_analysis_cycles()
                await self.activity_manager.input_tracker.disable_persistence()
                self.tracking_active = False
                logger.info("Activity tracking stopped successfully")
        except Exception as e:
            logger.error("Failed to stop tracking", extra={"error": str(e)}, exc_info=True)

    async def _start_server(self):
        """Start the API server."""
        try:
            if not self.server_active:
                logger.info("Starting server", extra={
                    "host": self.config["server"]["host"],
                    "port": self.config["server"]["port"]
                })
                config = Config(
                    "src.api.server:app",
                    host=self.config["server"]["host"],
                    port=self.config["server"]["port"],
                    log_level="info"
                )
                server = Server(config)
                self.server_task = asyncio.create_task(server.serve())
                self.server_active = True
                logger.info("Server started successfully")
                
        except Exception as e:
            logger.error("Failed to start server", extra={"error": str(e)})
            raise

    async def _stop_server(self):
        """Stop the API server."""
        try:
            if self.server_active and self.server_task:
                logger.info("Stopping server")
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
                self.server_task = None
                self.server_active = False
                logger.info("Server stopped successfully")
        except Exception as e:
            logger.error("Failed to stop server", extra={"error": str(e)})
            raise

    def open_file(self, filepath: Path):
        """Open file with system's default application."""
        try:
            if platform.system() == 'Darwin':
                subprocess.run(['open', filepath])
            elif platform.system() == 'Windows':
                subprocess.run(['start', filepath], shell=True)
            else:
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.error("Failed to open file", {"filepath": str(filepath), "error": str(e)})

    async def _analyze_session(self):
        """Handle session analysis workflow."""
        prompt = await inquirer.text(
            message="Enter your analysis prompt (or press Enter for default analysis):"
        ).execute_async()
        
        analysis_file = self.responses_dir / "analysis.txt"
        try:
            if not self.analysis_agent:
                self.analysis_agent = await self._create_analysis_agent("")

            # Call analyze_session with optional custom prompt
            analysis_result = await self.analysis_agent.analyze_session(
                session_id = None,
                custom_prompt=prompt if prompt else None
            )
            
            if analysis_result:
                # Write analysis to file
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    f.write(analysis_result["analysis"])
                    
                # Open the file with system's default application
                self.open_file(analysis_file)
            else:
                print("No data available for analysis.")
        
        except Exception as e:
            logger.error("Analysis failed", {"error": str(e)})

    def get_choices(self) -> List[str]:
        """Dynamically generate choices based on current state."""
        choices = []
        if self.tracking_active:
            choices.append("Stop Tracking")
        else:
            choices.append("Start Tracking")
            
        if self.server_active:
            choices.append("Stop Server")
        else:
            choices.append("Start Server")

        choices.extend([
            "Analyze Session",
            "Open Observation Log",
            "Exit"
        ])
        return choices

    async def handle_choice(self, choice: str):
        """Handle user's choice."""
        try:
            message = ""
            if choice == "Start Tracking":
                message = "Starting activity tracking system..."
            elif choice == "Stop Tracking":
                message = "Finishing up tracking..."
            elif choice == "Start Server":
                message = "Starting server..."
            elif choice == "Stop Server":
                message = "Stopping server..."
            elif choice == "Analyze Session":
                message = "Analyzing session..."
            elif choice == "Open Observation Log":
                message = "Opening observation log..."
            
            if message:
                print(f"{message}")
                
            if choice == "Start Tracking":
                await self._start_tracking()
            elif choice == "Stop Tracking":
                await self._stop_tracking()
            elif choice == "Start Server":
                await self._start_server()
            elif choice == "Stop Server":
                await self._stop_server()
            elif choice == "Analyze Session":
                await self._analyze_session()
            elif choice == "Open Observation Log":
                self.open_file(Path("responses/responses.txt"))
                
            # Add a newline after operation completes
            if message:
                print()

        except Exception as e:
            logger.error(f"Error handling choice: {e}")
            raise

    async def run(self):
        """Run the interactive CLI."""
        try:
            while True:
                try:
                    choice = await inquirer.select(
                        message="Select action:",
                        choices=self.get_choices(),
                        default=None
                    ).execute_async()

                    # logger.info(f"Choice: {choice}")
                    if choice == "Exit":
                        # logger.info("Exiting")
                        if self.tracking_active or self.server_active:
                            confirm = await inquirer.confirm(
                                message="Active processes will be stopped. Continue?"
                            ).execute_async()
                            if not confirm:
                                continue
                        await self.cleanup()
                        break
                        
                    await self.handle_choice(choice)

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    await self.cleanup()
                    break
        except asyncio.CancelledError:
            logger.info("Received cancellation signal")
            await self.cleanup()
        except Exception as e:
            logger.error("Error in CLI run", extra={"error": str(e)})
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources."""

        if self.is_shutting_down:
            return  # Prevent multiple shutdown attempts
        
        self.is_shutting_down = True
        
        logger.info("Starting cleanup process")
        try:

            await self.assistant_agent.stop()

            if self.tracking_active:
                # logger.debug("Stopping tracking")
                await self._stop_tracking()
            if self.server_active:
                # logger.debug("Stopping server")
                await self._stop_server()
                
            # Cleanup activity manager
            await self.activity_manager.cleanup()
                
            if self.db:
                # logger.debug("Closing database connection")
                await self.db.close()
            
            if self.tts_engine:
                # logger.debug("Closing TTS engine")
                await self.tts_engine.cleanup()
                
            logger.info("Cleanup completed successfully")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def attempt_start_postgres():
    """Attempts to start the PostgreSQL service."""
    logger.info("Attempting to start PostgreSQL service...")
    print("Attempting to start PostgreSQL service...")
    try:
        if platform.system() == "Linux":
            subprocess.run(["sudo", "systemctl", "start", "postgresql"], check=True)
        elif platform.system() == "Darwin":
            subprocess.run(["brew", "services", "start", "postgresql"], check=True)
        else:
            logger.warning("Automatic start not supported for this platform. Please start PostgreSQL manually.")
            return

        logger.info("PostgreSQL service started successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start PostgreSQL: {e}")
        logger.info("Please start PostgreSQL manually and try again.")
    except Exception as e:
        logger.error(f"An unexpected error occurred when trying to start PostgreSQL: {e}")

async def async_main():
    """Async main entry point."""
    try:
        config = load_config_and_logging()
        
        # Run tutorial if enabled
        await run_tutorial(Path(__file__).parent / "config.json")

        # Create the CLI instance
        cli = None  # Initialize cli to None
        while cli is None:  # Keep trying until cli is successfully created
            try:
                # Create the CLI instance
                cli = await MemorySystemCLI.create(config)
                if cli is None:  # Check if create() still returned None
                    logger.error("Failed to create MemorySystemCLI instance. Retrying...")
                    await asyncio.sleep(1)  # Wait a bit before retrying
            except Exception as e:
                logger.error("Error in async_main", {"error": str(e)}, exc_info=True)
                await asyncio.sleep(1)
        
        loop = asyncio.get_event_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(cli.cleanup())
            )
            
        await cli.run()
        
    except Exception as e:
        logger.error("Error in async_main", {"error": str(e)}, exc_info=True)
        raise

def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error("Fatal error", extra={"error": str(e)})
        raise

if __name__ == "__main__":
    main()