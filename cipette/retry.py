"""Retry utilities for CIPette application."""

import logging
import sqlite3
import time
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator to retry a function on specific exceptions.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry on
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f'Function {func.__name__} failed after {max_retries} retries: {e}'
                        )
                        raise e

                    logger.warning(
                        f'Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}'
                    )
                    logger.info(f'Retrying in {current_delay:.1f} seconds...')

                    time.sleep(current_delay)
                    current_delay *= backoff_factor

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


def retry_database_operation(max_retries: int = 3) -> Callable:
    """Decorator specifically for database operations with database lock handling."""
    return retry_on_exception(
        max_retries=max_retries,
        delay=0.5,
        backoff_factor=1.5,
        exceptions=(sqlite3.OperationalError,),
    )


def retry_api_call(max_retries: int = 3) -> Callable:
    """Decorator specifically for API calls with rate limit handling."""
    return retry_on_exception(
        max_retries=max_retries, delay=2.0, backoff_factor=2.0, exceptions=(Exception,)
    )
