"""SQL security utilities for safe database operations using prepared statements."""

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class SQLInjectionError(Exception):
    """Raised when potential SQL injection is detected."""

    pass


class SafeSQLExecutor:
    """Safe SQL executor using prepared statements for injection protection."""

    # Allowed PRAGMA values for SQLite configuration
    ALLOWED_PRAGMA_VALUES = {
        'journal_mode': {'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'WAL', 'OFF'},
        'synchronous': {'OFF', 'NORMAL', 'FULL', 'EXTRA'},
        'temp_store': {'DEFAULT', 'FILE', 'MEMORY'},
        'busy_timeout': None,  # Integer values
        'cache_size': None,  # Integer values
        'user_version': None,  # Integer values
    }

    @classmethod
    def validate_pragma_value(cls, pragma_name: str, value: Any) -> bool:
        """Validate PRAGMA value to prevent injection.

        Args:
            pragma_name: Name of the PRAGMA
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        if pragma_name not in cls.ALLOWED_PRAGMA_VALUES:
            logger.warning(f'Unknown PRAGMA name: {pragma_name}')
            return False

        allowed_values = cls.ALLOWED_PRAGMA_VALUES[pragma_name]
        if allowed_values is None:
            # Integer values
            return isinstance(value, int)
        else:
            # String values
            return isinstance(value, str) and value.upper() in allowed_values

    @classmethod
    def safe_pragma_execute(
        cls, cursor: sqlite3.Cursor, pragma_name: str, value: Any
    ) -> None:
        """Safely execute PRAGMA statement with validation.

        Args:
            cursor: Database cursor
            pragma_name: Name of the PRAGMA
            value: Value to set

        Raises:
            SQLInjectionError: If pragma name or value is invalid
        """
        if not cls.validate_pragma_value(pragma_name, value):
            raise SQLInjectionError(f'Invalid PRAGMA: {pragma_name} = {value}')

        # PRAGMA statements don't support prepared statements in SQLite
        # Use string formatting with validation instead
        cursor.execute(f'PRAGMA {pragma_name} = {value}')

    @classmethod
    def safe_execute(
        cls, cursor: sqlite3.Cursor, query: str, params: tuple | dict | None = None
    ) -> sqlite3.Cursor:
        """Safely execute SQL query using prepared statements.

        Args:
            cursor: Database cursor
            query: SQL query with placeholders
            params: Parameters for the query

        Returns:
            Cursor with executed query

        Raises:
            SQLInjectionError: If SQL execution fails
        """
        try:
            if params is None:
                return cursor.execute(query)
            else:
                return cursor.execute(query, params)
        except sqlite3.Error as e:
            logger.error(f'SQL execution error: {e}')
            raise SQLInjectionError(f'SQL execution failed: {e}') from e

    @classmethod
    def safe_executemany(
        cls, cursor: sqlite3.Cursor, query: str, params_list: list[tuple | dict]
    ) -> sqlite3.Cursor:
        """Safely execute SQL query multiple times using prepared statements.

        Args:
            cursor: Database cursor
            query: SQL query with placeholders
            params_list: List of parameter sets

        Returns:
            Cursor with executed query

        Raises:
            SQLInjectionError: If SQL execution fails
        """
        try:
            return cursor.executemany(query, params_list)
        except sqlite3.Error as e:
            logger.error(f'SQL execution error: {e}')
            raise SQLInjectionError(f'SQL execution failed: {e}') from e


class SafePragmaSet:
    """Safe PRAGMA setter with validation."""

    @classmethod
    def safe_pragma_set(
        cls, cursor: sqlite3.Cursor, pragma_name: str, value: Any
    ) -> None:
        """Safely set PRAGMA value with validation.

        Args:
            cursor: Database cursor
            pragma_name: Name of the PRAGMA
            value: Value to set

        Raises:
            SQLInjectionError: If pragma name or value is invalid
        """
        SafeSQLExecutor.safe_pragma_execute(cursor, pragma_name, value)


class ValidateQueryParams:
    """Query parameter validation utilities."""

    @classmethod
    def validate_query_params(cls, params: tuple | dict | None) -> bool:
        """Validate query parameters for safety.

        Args:
            params: Query parameters

        Returns:
            True if parameters are safe, False otherwise
        """
        if params is None:
            return True

        if isinstance(params, (tuple, list)):
            for param in params:
                if not cls._is_safe_parameter(param):
                    return False
        elif isinstance(params, dict):
            for key, value in params.items():
                if not cls._is_safe_parameter(key) or not cls._is_safe_parameter(value):
                    return False

        return True

    @classmethod
    def _is_safe_parameter(cls, param: Any) -> bool:
        """Check if a single parameter is safe.

        Args:
            param: Parameter to check

        Returns:
            True if parameter is safe, False otherwise
        """
        if isinstance(param, str):
            # Check for SQL injection patterns in string parameters
            # Only flag patterns that are clearly malicious, not legitimate SQL keywords
            dangerous_patterns = [';', '--', '/*', '*/', '; DROP', '; DELETE', '; INSERT', '; UPDATE', '; ALTER', '; CREATE']
            param_upper = param.upper()
            for pattern in dangerous_patterns:
                if pattern in param_upper:
                    logger.warning(f'Potentially dangerous parameter detected: {pattern}')
                    return False
        elif isinstance(param, (int, float, bool, type(None))):
            # Numeric and boolean values are generally safe
            return True
        elif hasattr(param, 'isoformat'):
            # datetime objects are safe
            return True
        else:
            # Other types might be unsafe
            logger.warning(f'Unknown parameter type: {type(param)}')
            return False

        return True
