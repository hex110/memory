"""Logging configuration and utilities."""

import logging
from pathlib import Path
from absl import logging as absl_logging
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
    """Configure logging to write to a file and redirect stderr."""
    if log_file.exists():
        log_file.unlink()
    
    absl_logging.set_stderrthreshold('FATAL')
    absl_logging.use_absl_handler()
    
    # Keep original stderr
    original_stderr = sys.stderr
    
    # Create file handler first
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(CustomFormatter())
    
    # Configure root logger to catch everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # Set root logger to catch warnings and above
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    
    # Configure app-specific logger
    app_logger = logging.getLogger('src')
    app_logger.setLevel(logging.DEBUG if development else logging.INFO)
    app_logger.propagate = False
    app_logger.handlers.clear()
    app_logger.addHandler(file_handler)

    # Capture warnings
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger('py.warnings')
    warnings_logger.handlers.clear()
    warnings_logger.addHandler(file_handler)
    
    # Redirect stderr while keeping original for GRPC
    class StderrToLogger:
        def __init__(self):
            self._original_stderr = original_stderr
            self._in_write = False  # Prevent recursion
        
        def write(self, buf):
            if not self._in_write and buf.rstrip():
                try:
                    self._in_write = True  # Set flag to prevent recursion
                    for line in buf.rstrip().splitlines():
                        root_logger.warning(line)
                    # Only write to original stderr if it's not a logging message
                    if not line.startswith('WARNING: Logging before flag parsing'):
                        self._original_stderr.write(buf)
                finally:
                    self._in_write = False  # Always reset flag
        
        def flush(self):
            self._original_stderr.flush()
    
    sys.stderr = StderrToLogger()

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        if str(exc_value).find('grpc_wait_for_shutdown_with_timeout') != -1:
            root_logger.warning(str(exc_value))
        else:
            original_excepthook(exc_type, exc_value, exc_traceback)
    
    original_excepthook = sys.excepthook
    sys.excepthook = custom_excepthook
    
    # Add session start markers
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
    # If the name starts with '__main__', replace it with 'src.main'
    if name == '__main__':
        return logging.getLogger('src.main')
    # Otherwise prepend 'src.' if it's not already there
    if not name.startswith('src.'):
        name = f'src.{name}'
    return logging.getLogger(name)