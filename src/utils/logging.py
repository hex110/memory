"""Logging configuration and utilities."""

import logging
from pathlib import Path
import sys

class CustomFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
        # Format for DEBUG, WARNING, and ERROR
        self.detailed_fmt = '%(asctime)s [%(pathname)s:%(lineno)d] %(levelname)s: %(message)s'
        self.detailed_formatter = logging.Formatter(self.detailed_fmt, datefmt='%H:%M:%S,%f'[:-3])
        
        # Simpler format for INFO
        self.info_fmt = '%(asctime)s %(message)s'
        self.info_formatter = logging.Formatter(self.info_fmt, datefmt='%H:%M:%S,%f'[:-3])

    def format(self, record):
        if record.levelno == logging.INFO:
            return self.info_formatter.format(record)
        return self.detailed_formatter.format(record)

def configure_logging(development: bool = True, log_file: Path = Path("memory_system.log")) -> None:
    """Configure logging to write to a file only."""
    if log_file.exists():
        log_file.unlink()
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.handlers.clear()
    
    app_logger = logging.getLogger('src')
    app_logger.setLevel(logging.DEBUG if development else logging.INFO)
    app_logger.propagate = False

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(CustomFormatter())
    app_logger.addHandler(file_handler)

    logging.captureWarnings(True)
    warnings_logger = logging.getLogger('py.warnings')
    warnings_logger.addHandler(file_handler)
    
    app_logger.info("\n" * 2)
    app_logger.info("=" * 80)
    app_logger.info("Starting new logging session")
    app_logger.info("=" * 80)
    app_logger.info("\n")

    # No stderr redirection needed
    
    # Print instructions for opening logs in new terminal
    # print(f"\nTo view logs in real-time:")
    # print(f"1. Open a new terminal in VSCode (Ctrl+Shift+` or cmd+shift+`)")
    # print(f"2. Run: tail -f {log_file.absolute()}\n")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)