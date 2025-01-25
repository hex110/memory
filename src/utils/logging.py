"""Logging configuration and utilities."""

import logging
import sys
import threading
from typing import Optional
from pathlib import Path

class InteractiveHandler(logging.StreamHandler):
    """Handler that can be toggled for interactive viewing"""
    def __init__(self, stream=sys.stdout):
        super().__init__(stream)
        self.enabled = True
        self._lock = threading.Lock()
        
    def emit(self, record):
        with self._lock:
            if self.enabled:
                super().emit(record)

def configure_logging(development: bool = True, log_file: Optional[Path] = None) -> InteractiveHandler:
    """Configure logging with toggleable interactive output.
    
    Args:
        development: Whether to run in development mode (sets DEBUG level if True)
        log_file: Optional path to log file for persistent logging
        
    Returns:
        InteractiveHandler instance that can be used to toggle console output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if development else logging.INFO)
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # Create our toggleable interactive handler
    interactive_handler = InteractiveHandler()
    interactive_handler.setFormatter(formatter)
    root_logger.addHandler(interactive_handler)
    
    # Optional file handler for persistent logging
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return interactive_handler

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def disable_console_logging(handler: InteractiveHandler):
    """Disable console output.
    
    Args:
        handler: The InteractiveHandler instance to disable
    """
    handler.enabled = False

def enable_console_logging(handler: InteractiveHandler):
    """Enable console output.
    
    Args:
        handler: The InteractiveHandler instance to enable
    """
    handler.enabled = True