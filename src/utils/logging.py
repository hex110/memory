import logging
import sys
from typing import Optional
from functools import partialmethod

class CustomLogger(logging.Logger):
    def error(self, msg, *args, **kwargs):
        """Override error to always include exc_info"""
        kwargs['exc_info'] = True
        super().error(msg, *args, **kwargs)

# Register our custom logger class
logging.setLoggerClass(CustomLogger)

# Global flag to track if logging has been configured
_logging_configured = False

def configure_logging(development: bool = True) -> None:
    """Configure logging for the entire application. Should be called only once at startup."""
    global _logging_configured
    if _logging_configured:
        return
        
    # Base configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if development else logging.INFO)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set levels for third-party loggers in production
    if not development:
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    _logging_configured = True

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance. Will configure logging if not already done."""
    if not _logging_configured:
        configure_logging()
    return logging.getLogger(name)