"""Structured logging configuration for Zorix Agent."""

import json
import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from structlog.stdlib import LoggerFactory

from agent.config import get_settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "getMessage", "exc_info",
                "exc_text", "stack_info"
            }:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """Configure structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ('json' or 'text')
        log_file: Optional log file path
        context: Additional context to include in all logs
    """
    settings = get_settings()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if format_type == "json" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if format_type == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    if context:
        console_handler.addFilter(ContextFilter(context))
    
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(JSONFormatter())
        
        if context:
            file_handler.addFilter(ContextFilter(context))
        
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True
    )
    
    # Set specific logger levels
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Add application context
    app_context = {
        "service": "zorix-agent",
        "version": "1.0.0",
        "workspace": settings.workspace_root,
    }
    
    if context:
        app_context.update(context)
    
    # Configure application loggers with context
    for logger_name in [
        "agent",
        "agent.llm",
        "agent.memory",
        "agent.orchestrator",
        "agent.planning",
        "agent.tools",
        "agent.vector",
        "agent.web",
        "agent.security",
    ]:
        logger = logging.getLogger(logger_name)
        logger.addFilter(ContextFilter(app_context))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class."""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)


def log_function_call(func):
    """Decorator to log function calls with parameters and results."""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.info(
            "Function called",
            function=func.__name__,
            args=str(args)[:200],  # Truncate long args
            kwargs={k: str(v)[:100] for k, v in kwargs.items()},
        )
        
        try:
            result = func(*args, **kwargs)
            
            # Log successful completion
            logger.info(
                "Function completed",
                function=func.__name__,
                result_type=type(result).__name__,
            )
            
            return result
            
        except Exception as e:
            # Log exception
            logger.error(
                "Function failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise
    
    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls with parameters and results."""
    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.info(
            "Async function called",
            function=func.__name__,
            args=str(args)[:200],
            kwargs={k: str(v)[:100] for k, v in kwargs.items()},
        )
        
        try:
            result = await func(*args, **kwargs)
            
            # Log successful completion
            logger.info(
                "Async function completed",
                function=func.__name__,
                result_type=type(result).__name__,
            )
            
            return result
            
        except Exception as e:
            # Log exception
            logger.error(
                "Async function failed",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise
    
    return wrapper


class LogContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger, **context):
        self.logger = logger
        self.context = context
        self.bound_logger = None
    
    def __enter__(self):
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.bound_logger.error(
                "Context exited with exception",
                exc_type=exc_type.__name__,
                exc_value=str(exc_val),
                exc_info=True,
            )


def setup_error_logging():
    """Setup enhanced error logging with context."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger = get_logger("agent.error")
        logger.critical(
            "Uncaught exception",
            exc_type=exc_type.__name__,
            exc_value=str(exc_value),
            exc_info=(exc_type, exc_value, exc_traceback),
        )
    
    sys.excepthook = handle_exception