"""Main entry point for the memory system."""

import asyncio
import signal
import uuid
import os
from pathlib import Path
import subprocess
import platform
from typing import Dict, Any, List
from InquirerPy import inquirer

from src.utils.config import load_config_and_logging
from src.database.postgresql import PostgreSQLDatabase
from src.utils.logging import get_logger
from src.agent.monitor_agent import MonitorAgent
from src.agent.analysis_agent import AnalysisAgent
from src.ontology.manager import OntologyManager
from uvicorn import Config, Server

class MemorySystemCLI:
    """Command line interface for the memory system."""
    
    def __init__(self, config: Dict[str, Any], db: PostgreSQLDatabase, ontology_manager: OntologyManager):
        """Initialize the CLI interface."""
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
        self.logger = get_logger(__name__)
        self.responses_dir = Path("responses")
        self.responses_dir.mkdir(exist_ok=True)
        self.config_path = Path("config.json")

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> 'MemorySystemCLI':
        """Create and initialize a new CLI instance."""
        db = await PostgreSQLDatabase.create(config["database"])
        ontology_manager = await OntologyManager.create()
        return cls(config, db, ontology_manager)

    async def _create_monitor_agent(self):
        return MonitorAgent(
            config=self.config,
            prompt_folder="prompts",
            db_interface=self.db,
            ontology_manager=self.ontology_manager,
            session_id=str(uuid.uuid4())
        )

    async def _create_analysis_agent(self, session_id: str):
        return AnalysisAgent(
            config=self.config,
            prompt_folder="prompts", 
            db_interface=self.db,
            ontology_manager=self.ontology_manager,
            session_id=session_id
        )

    async def _start_tracking(self):
        """Start activity tracking."""
        try:
            if not self.tracking_active:
                self.logger.info("Starting activity tracking")
                self.monitor_agent = await self._create_monitor_agent()
                self.analysis_agent = await self._create_analysis_agent(self.monitor_agent.session_id)
                
                await self.monitor_agent.start_monitoring()
                await self.analysis_agent.start_analysis_cycles()
                self.tracking_active = True
                self.logger.info("Activity tracking started successfully")
        except Exception as e:
            raise

    async def _stop_tracking(self):
        """Stop activity tracking."""
        try:
            if self.tracking_active:
                self.logger.info("Stopping activity tracking")
                await self.monitor_agent.stop_monitoring()
                await self.analysis_agent.stop_analysis_cycles()
                self.tracking_active = False
                self.logger.info("Activity tracking stopped successfully")
        except Exception as e:
            self.logger.error("Failed to stop tracking", extra={"error": str(e)})

    async def _start_server(self):
        """Start the API server."""
        try:
            if not self.server_active:
                self.logger.info("Starting server", extra={
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
                self.logger.info("Server started successfully")
                
        except Exception as e:
            self.logger.error("Failed to start server", extra={"error": str(e)})
            raise

    async def _stop_server(self):
        """Stop the API server."""
        try:
            if self.server_active and self.server_task:
                self.logger.info("Stopping server")
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
                self.server_task = None
                self.server_active = False
                self.logger.info("Server stopped successfully")
        except Exception as e:
            self.logger.error("Failed to stop server", extra={"error": str(e)})
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
            self.logger.error("Failed to open file", {"filepath": str(filepath), "error": str(e)})

    async def _analyze_session(self):
        """Handle session analysis workflow."""
        prompt = await inquirer.text(
            message="Enter your analysis prompt:"
        ).execute_async()
        
        if not prompt:
            return
            
        analysis_file = self.responses_dir / "analysis.txt"
        try:
            await analyze_session(
                self.config,
                self.db,
                custom_prompt=prompt,
                output_file=analysis_file
            )
            
            if analysis_file.exists():
                self.open_file(analysis_file)
        except Exception as e:
            self.logger.error("Analysis failed", {"error": str(e)})

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
            self.logger.error(f"Error handling choice: {e}")
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
                    self.logger.info("Received interrupt signal")
                    await self.cleanup()
                    break
        except asyncio.CancelledError:
            self.logger.info("Received cancellation signal")
            await self.cleanup()
        except Exception as e:
            self.logger.error("Error in CLI run", extra={"error": str(e)})
            await self.cleanup()
    
    async def cleanup(self):
        self.logger.info("Starting cleanup process")
        try:
            if self.tracking_active:
                self.logger.debug("Stopping tracking")
                await self._stop_tracking()
            if self.server_active:
                self.logger.debug("Stopping server")
                await self._stop_server()
            if self.db:
                self.logger.debug("Closing database connection")
                await self.db.close()
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

async def async_main():
    """Async main entry point."""
    try:
        config = load_config_and_logging()
        cli = await MemorySystemCLI.create(config)
        
        loop = asyncio.get_event_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(cli.cleanup())
            )
            
        await cli.run()
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Error in async_main", {"error": str(e)})
        raise

def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger = get_logger(__name__)
        logger.info("Shutting down")
    except Exception as e:
        logger.error("Fatal error", extra={"error": str(e)})
        raise

if __name__ == "__main__":
    main()