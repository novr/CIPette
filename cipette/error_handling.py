"""Error handling utilities for CIPette application."""

import logging
import sqlite3
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class CIPetteError(Exception):
    """Base exception for CIPette application."""
    pass


class DatabaseError(CIPetteError):
    """Database-related errors."""
    pass


class GitHubAPIError(CIPetteError):
    """GitHub API-related errors."""
    pass


class ConfigurationError(CIPetteError):
    """Configuration-related errors."""
    pass


class DataProcessingError(CIPetteError):
    """Data processing errors."""
    pass


def handle_database_errors(func: Callable) -> Callable:
    """Decorator to handle database-related errors consistently.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with consistent error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning(f"Database locked in {func.__name__}: {e}")
                return None
            else:
                logger.error(f"Database operational error in {func.__name__}: {e}")
                raise DatabaseError(f"Database operation failed: {e}") from e
        except sqlite3.DatabaseError as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError(f"Database error: {e}") from e
        except sqlite3.Error as e:
            logger.error(f"SQLite error in {func.__name__}: {e}")
            raise DatabaseError(f"SQLite error: {e}") from e

    return wrapper


def handle_api_errors(func: Callable) -> Callable:
    """Decorator to handle API-related errors consistently.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with consistent error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API error in {func.__name__}: {e}")
            raise GitHubAPIError(f"API operation failed: {e}") from e

    return wrapper


def handle_data_processing_errors(func: Callable) -> Callable:
    """Decorator to handle data processing errors consistently.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with consistent error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Data processing error in {func.__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise DataProcessingError(f"Data processing failed: {e}") from e

    return wrapper


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    **kwargs
) -> Any:
    """Safely execute a function with consistent error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        default: Default value to return on error
        log_errors: Whether to log errors
        reraise: Whether to reraise exceptions
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(f"Error in {func.__name__}: {e}")

        if reraise:
            raise

        return default


def log_and_continue(
    message: str,
    exception: Exception | None = None,
    level: int = logging.WARNING
) -> None:
    """Log an error message and continue execution.

    Args:
        message: Error message to log
        exception: Optional exception to include in log
        level: Log level (default: WARNING)
    """
    if exception:
        logger.log(level, f"{message}: {exception}", exc_info=True)
    else:
        logger.log(level, message)


def log_and_raise(
    message: str,
    exception: Exception,
    custom_exception: type[Exception] | None = None
) -> None:
    """Log an error message and raise a custom exception.

    Args:
        message: Error message to log
        exception: Original exception
        custom_exception: Custom exception type to raise (default: CIPetteError)
    """
    if custom_exception is None:
        custom_exception = CIPetteError

    logger.error(f"{message}: {exception}", exc_info=True)
    raise custom_exception(f"{message}: {exception}") from exception


def validate_not_none(value: Any, name: str) -> None:
    """Validate that a value is not None.

    Args:
        value: Value to validate
        name: Name of the value for error message

    Raises:
        ConfigurationError: If value is None
    """
    if value is None:
        raise ConfigurationError(f"{name} cannot be None")


def validate_positive(value: int | float, name: str) -> None:
    """Validate that a value is positive.

    Args:
        value: Value to validate
        name: Name of the value for error message

    Raises:
        ConfigurationError: If value is not positive
    """
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive, got {value}")
