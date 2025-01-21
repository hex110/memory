import logging
from typing import Dict, Any


def get_logger(name: str) -> logging.Logger:
    """Gets a named logger with configured handlers and formatters.
    
    Args:
        name (str): Name of the logger.
        
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set minimum log level to INFO
    
    # Only add handler if the logger doesn't already have handlers
    if not logger.handlers:
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    
    return logger


def log_info(logger: logging.Logger, message: str, data: Dict[str, Any]) -> None:
    """Logs an information message with associated data.
    
    Args:
        logger (logging.Logger): Logger instance to use.
        message (str): Main log message.
        data (Dict[str, Any]): Additional data to include in the log.
    """
    logger.info(f"{message} - Data: {data}")


def log_warning(logger: logging.Logger, message: str, data: Dict[str, Any]) -> None:
    """Logs a warning message with associated data.
    
    Args:
        logger (logging.Logger): Logger instance to use.
        message (str): Warning message.
        data (Dict[str, Any]): Additional data to include in the log.
    """
    logger.warning(f"{message} - Data: {data}")


def log_error(logger: logging.Logger, message: str, data: Dict[str, Any]) -> None:
    """Logs an error message with associated data.
    
    Args:
        logger (logging.Logger): Logger instance to use.
        message (str): Error message.
        data (Dict[str, Any]): Additional data to include in the log.
    """
    logger.error(f"{message} - Data: {data}")


def log_debug(logger: logging.Logger, message: str, data: Dict[str, Any]) -> None:
    """Logs a debug message with associated data.
    
    Args:
        logger (logging.Logger): Logger instance to use.
        message (str): Debug message.
        data (Dict[str, Any]): Additional data to include in the log.
    """
    logger.debug(f"{message} - Data: {data}")
