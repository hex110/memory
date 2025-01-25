"""Main entry point for the memory system."""

import asyncio
import signal
import uuid
from pathlib import Path
import subprocess
import platform
from typing import Dict, Any, List
from InquirerPy import inquirer

from src.utils.config import (
    ensure_config_exists,
    load_config,
)
from src.database.postgresql import PostgreSQLDatabase
from src.utils.logging import get_logger, configure_logging
from src.agent.monitor_agent import MonitorAgent
from src.agent.analysis_agent import AnalysisAgent
from src.ontology.manager import OntologyManager
from uvicorn import Config, Server

logger = get_logger(__name__)

class MemorySystemCLI:
    """Command line interface for the memory system."""
    
    def __init__(self, config: Dict[str, Any], db: PostgreSQLDatabase, ontology_manager: OntologyManager):
        """Initialize the CLI interface.
        
        Args:
            config: System configuration
            db: Initialized database interface
            ontology_manager: Initialized ontology manager
        """
        self.config = config
        self.db = db
        self.tracking_active = False
        self.server_active = False
        self.tracking_task = None
        self.server_task = None
        self._shutdown_event = asyncio.Event()
        self.monitor_agent = None
        self.analysis_agent = None
        self.ontology_manager = ontology_manager
        
        # Create responses directory if it doesn't exist
        self.responses_dir = Path("responses")
        self.responses_dir.mkdir(exist_ok=True)
        
        # Store config path for analysis
        self.config_path = Path("config.json")  # We might want to pass this from main

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> 'MemorySystemCLI':
        """Create and initialize a new CLI instance.
        
        Args:
            config: System configuration
            
        Returns:
            Initialized CLI instance
        """
        db = await PostgreSQLDatabase.create(config["database"])
        ontology_manager = await OntologyManager.create()
        return cls(config, db, ontology_manager)


    async def _create_monitor_agent(self):
        return MonitorAgent(
            config_path=self.config_path,
            prompt_folder="prompts",
            db_interface=self.db,
            ontology_manager=self.ontology_manager,
            session_id=str(uuid.uuid4())  # Generate new session ID
        )

    async def _create_analysis_agent(self, session_id: str):
        return AnalysisAgent(
            config_path=self.config_path,
            prompt_folder="prompts", 
            db_interface=self.db,
            ontology_manager=self.ontology_manager,
            session_id=session_id
        )

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
            "Exit"
        ])
        return choices

    async def handle_choice(self, choice: str):
        """Handle user's choice."""
        try:
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
        except Exception as e:
            logger.error("Error handling choice", extra={"choice": choice, "error": str(e)})
            raise  # Re-raise to see the full error during development

    async def _start_tracking(self):
        """Start activity tracking."""
        try:
            if not self.tracking_active:
                logger.info("Starting activity tracking")
                self.monitor_agent = await self._create_monitor_agent()
                self.analysis_agent = await self._create_analysis_agent(self.monitor_agent.session_id)
                
                # Start both agents
                await self.monitor_agent.start_monitoring()
                await self.analysis_agent.start_analysis_cycles()
                self.tracking_active = True
                logger.info("Activity tracking started successfully")
        except Exception as e:
            logger.error("Failed to start tracking", extra={"error": str(e)}, exc_info=True)
            raise

    async def _stop_tracking(self):
        """Stop activity tracking."""
        try:
            if self.tracking_active:
                logger.info("Stopping activity tracking")
                await self.monitor_agent.stop_monitoring()
                await self.analysis_agent.stop_analysis_cycles()
                self.tracking_active = False
                logger.info("Activity tracking stopped successfully")
        except Exception as e:
            logger.error("Failed to stop tracking", extra={"error": str(e)})
            raise

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
            if platform.system() == 'Darwin':       # macOS
                subprocess.run(['open', filepath])
            elif platform.system() == 'Windows':    # Windows
                subprocess.run(['start', filepath], shell=True)
            else:                                   # Linux
                subprocess.run(['xdg-open', filepath])
        except Exception as e:
            logger.error("Failed to open file", {"filepath": str(filepath), "error": str(e)})

    async def _analyze_session(self):
        """Handle session analysis workflow."""
        prompt = await inquirer.text(
            message="Enter your analysis prompt:"
        ).execute_async()
        
        if not prompt:
            return
            
        # Run analysis
        analysis_file = self.responses_dir / "analysis.txt"
        try:
            await analyze_session(
                self.config,
                self.db,
                custom_prompt=prompt,
                output_file=analysis_file
            )
            
            # Open resulting file
            if analysis_file.exists():
                self.open_file(analysis_file)
        except Exception as e:
            logger.error("Analysis failed", {"error": str(e)})

    async def cleanup(self):
        """Clean up all running processes."""
        logger.info("Cleaning up processes")
        await self._stop_tracking()
        await self._stop_server()
        if self.db:
            await self.db.close()

    async def run(self):
        """Run the interactive CLI."""
        try:
            while True:
                try:
                    # Use async version of inquirer
                    choice = await inquirer.select(
                        message="Select action:",
                        choices=self.get_choices(),
                        default=None
                    ).execute_async()
                    
                    if choice == "Exit":
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
                    # Handle Ctrl+C during inquirer
                    logger.info("Received interrupt signal")
                    await self.cleanup()
                    break
        except asyncio.CancelledError:
            logger.info("Received cancellation signal")
            await self.cleanup()
        except Exception as e:
            logger.error("Error in CLI run", extra={"error": str(e)})
            await self.cleanup()

async def async_main():
    """Async main entry point."""
    try:
        config_path = ensure_config_exists()
        config = load_config(config_path)

        # Configure logging once at startup
        configure_logging(development=config.get("development", True))
        logger = get_logger(__name__)
        
        # Initialize CLI with database
        cli = await MemorySystemCLI.create(config)
        
        # Handle graceful shutdown
        loop = asyncio.get_event_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(cli.cleanup())
            )
            
        await cli.run()
        
    except Exception as e:
        logger.error("Error in async_main", {"error": str(e)})
        raise

def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down")  # Remove empty dict
    except Exception as e:
        logger.error("Fatal error", extra={"error": str(e)})
        raise

if __name__ == "__main__":
    main()