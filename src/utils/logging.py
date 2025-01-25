"""Logging configuration and utilities."""

import logging
from pathlib import Path
import sys

def configure_logging(development: bool = True, log_file: Path = Path("memory_system.log")) -> None:
    """Configure logging to write to a file.
    
    Args:
        development: Whether to run in development mode (sets DEBUG level if True)
        log_file: Path to log file for persistent logging
    """
    # Delete the old log file if it exists
    if log_file.exists():
        log_file.unlink()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if development else logging.INFO)
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # File handler for persistent logging
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Add visual separator when starting new log file
    root_logger.info("\n" * 10)
    root_logger.info("=" * 80)
    root_logger.info("Starting new logging session")
    root_logger.info("=" * 80)
    root_logger.info("\n" * 5)

    logging.captureWarnings(True)

    class StderrToLogger:
        def __init__(self, logger):
            self.logger = logger
        
        def write(self, buf):
            for line in buf.rstrip().splitlines():
                self.logger.error(line.rstrip())
        
        def flush(self):
            pass
    
    stderr_logger = logging.getLogger('STDERR')
    sys.stderr = StderrToLogger(stderr_logger)
    
    # Print instructions for opening logs in new terminal
    # print(f"\nTo view logs in real-time:")
    # print(f"1. Open a new terminal in VSCode (Ctrl+Shift+` or cmd+shift+`)")
    # print(f"2. Run: tail -f {log_file.absolute()}\n")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)