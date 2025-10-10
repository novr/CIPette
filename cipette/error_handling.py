"""Error handling utilities for CIPette application."""

import logging
import sqlite3
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class CIPetteError(Exception):
    """Base exception for CIPette application."""

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize CIPette error with detailed context.

        Args:
            message: Human-readable error message
            context: Additional context information
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.context = context or {}
        self.cause = cause
        # Only capture traceback if there's an actual exception
        self.timestamp = traceback.format_exc() if cause else None

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization.

        Returns:
            Dictionary representation of the error
        """
        return {
            'error_type': self.__class__.__name__,
            'message': str(self),
            'context': self.context,
            'cause': str(self.cause) if self.cause else None,
            'timestamp': self.timestamp,
        }


class DatabaseError(CIPetteError):
    """Database-related errors."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        query: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize database error with operation context.

        Args:
            message: Error message
            operation: Database operation being performed
            query: SQL query that failed (if applicable)
            context: Additional context
            cause: Original exception
        """
        db_context = {'operation': operation, 'query': query, **(context or {})}
        super().__init__(message, db_context, cause)


class GitHubAPIError(CIPetteError):
    """GitHub API-related errors."""

    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        status_code: int | None = None,
        rate_limit_remaining: int | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize GitHub API error with API context.

        Args:
            message: Error message
            endpoint: API endpoint that failed
            status_code: HTTP status code
            rate_limit_remaining: Remaining API calls
            context: Additional context
            cause: Original exception
        """
        api_context = {
            'endpoint': endpoint,
            'status_code': status_code,
            'rate_limit_remaining': rate_limit_remaining,
            **(context or {}),
        }
        super().__init__(message, api_context, cause)


class ConfigurationError(CIPetteError):
    """Configuration-related errors."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        expected_type: str | None = None,
        actual_value: Any = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize configuration error with config context.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            expected_type: Expected data type
            actual_value: Actual value received
            context: Additional context
            cause: Original exception
        """
        config_context = {
            'config_key': config_key,
            'expected_type': expected_type,
            'actual_value': actual_value,
            **(context or {}),
        }
        super().__init__(message, config_context, cause)


class DataProcessingError(CIPetteError):
    """Data processing errors."""

    def __init__(
        self,
        message: str,
        data_type: str | None = None,
        processing_stage: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize data processing error with processing context.

        Args:
            message: Error message
            data_type: Type of data being processed
            processing_stage: Stage of processing that failed
            context: Additional context
            cause: Original exception
        """
        processing_context = {
            'data_type': data_type,
            'processing_stage': processing_stage,
            **(context or {}),
        }
        super().__init__(message, processing_context, cause)


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
            if 'database is locked' in str(e):
                logger.warning(f'Database locked in {func.__name__}: {e}')
                return None
            else:
                error = DatabaseError(
                    f'Database operation failed: {e}',
                    operation=func.__name__,
                    context={'error_code': 'OPERATIONAL_ERROR', 'sqlite_error': str(e)},
                    cause=e,
                )
                logger.error(f'Database operational error: {error.to_dict()}')
                raise error from e
        except sqlite3.DatabaseError as e:
            error = DatabaseError(
                f'Database error: {e}',
                operation=func.__name__,
                context={'error_code': 'DATABASE_ERROR', 'sqlite_error': str(e)},
                cause=e,
            )
            logger.error(f'Database error: {error.to_dict()}')
            raise error from e
        except sqlite3.Error as e:
            error = DatabaseError(
                f'SQLite error: {e}',
                operation=func.__name__,
                context={'error_code': 'SQLITE_ERROR', 'sqlite_error': str(e)},
                cause=e,
            )
            logger.error(f'SQLite error: {error.to_dict()}')
            raise error from e

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
            error = GitHubAPIError(
                f'API operation failed: {e}',
                endpoint=getattr(e, 'url', None),
                status_code=getattr(e, 'status', None),
                context={'function': func.__name__, 'error_type': type(e).__name__},
                cause=e,
            )
            logger.error(f'API error: {error.to_dict()}')
            raise error from e

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
            error = DataProcessingError(
                f'Data processing error: {e}',
                data_type=type(args[0]).__name__ if args else 'unknown',
                processing_stage=func.__name__,
                context={'error_type': type(e).__name__, 'error_details': str(e)},
                cause=e,
            )
            logger.warning(f'Data processing error: {error.to_dict()}')
            return None
        except Exception as e:
            error = DataProcessingError(
                f'Unexpected data processing error: {e}',
                data_type=type(args[0]).__name__ if args else 'unknown',
                processing_stage=func.__name__,
                context={'error_type': type(e).__name__, 'error_details': str(e)},
                cause=e,
            )
            logger.error(f'Unexpected error: {error.to_dict()}')
            raise error from e

    return wrapper


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    **kwargs,
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
            logger.error(f'Error in {func.__name__}: {e}')

        if reraise:
            raise

        return default


def log_and_continue(
    message: str, exception: Exception | None = None, level: int = logging.WARNING
) -> None:
    """Log an error message and continue execution.

    Args:
        message: Error message to log
        exception: Optional exception to include in log
        level: Log level (default: WARNING)
    """
    if exception:
        logger.log(level, f'{message}: {exception}', exc_info=True)
    else:
        logger.log(level, message)


def log_and_raise(
    message: str, exception: Exception, custom_exception: type[Exception] | None = None
) -> None:
    """Log an error message and raise a custom exception.

    Args:
        message: Error message to log
        exception: Original exception
        custom_exception: Custom exception type to raise (default: CIPetteError)
    """
    if custom_exception is None:
        custom_exception = CIPetteError

    logger.error(f'{message}: {exception}', exc_info=True)
    raise custom_exception(f'{message}: {exception}') from exception


def validate_not_none(value: Any, name: str) -> None:
    """Validate that a value is not None.

    Args:
        value: Value to validate
        name: Name of the value for error message

    Raises:
        ConfigurationError: If value is None
    """
    if value is None:
        raise ConfigurationError(f'{name} cannot be None')


def validate_positive(value: int | float, name: str) -> None:
    """Validate that a value is positive.

    Args:
        value: Value to validate
        name: Name of the value for error message

    Raises:
        ConfigurationError: If value is not positive
    """
    if value <= 0:
        raise ConfigurationError(f'{name} must be positive, got {value}')
