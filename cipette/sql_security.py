"""SQL security utilities for safe database operations."""

import logging
import re
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class SQLInjectionError(Exception):
    """Raised when potential SQL injection is detected."""
    pass


class SafeSQLExecutor:
    """Safe SQL executor with injection protection."""

    # Allowed PRAGMA values for SQLite configuration
    ALLOWED_PRAGMA_VALUES = {
        'journal_mode': {'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'WAL', 'OFF'},
        'synchronous': {'OFF', 'NORMAL', 'FULL', 'EXTRA'},
        'temp_store': {'DEFAULT', 'FILE', 'MEMORY'},
        'busy_timeout': None,  # Integer values
        'cache_size': None,    # Integer values
        'user_version': None,  # Integer values
    }

    # Allowed table names (alphanumeric and underscore only)
    TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    # Allowed column names (alphanumeric and underscore only)
    COLUMN_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

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
            logger.warning(f"Unknown PRAGMA name: {pragma_name}")
            return False

        allowed_values = cls.ALLOWED_PRAGMA_VALUES[pragma_name]

        if allowed_values is None:
            # Integer values
            try:
                int(value)
                return True
            except (ValueError, TypeError):
                return False
        else:
            # String values from allowed set
            return str(value).upper() in allowed_values

    @classmethod
    def validate_identifier(cls, identifier: str, identifier_type: str = "identifier") -> bool:
        """Validate SQL identifier (table name, column name, etc.).

        Args:
            identifier: Identifier to validate
            identifier_type: Type of identifier for error messages

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(identifier, str):
            return False

        if not cls.TABLE_NAME_PATTERN.match(identifier):
            logger.warning(f"Invalid {identifier_type}: {identifier}")
            return False

        return True

    @classmethod
    def safe_pragma_execute(cls, cursor: sqlite3.Cursor, pragma_name: str, value: Any) -> None:
        """Safely execute a PRAGMA statement.

        Args:
            cursor: Database cursor
            pragma_name: Name of the PRAGMA
            value: Value to set

        Raises:
            SQLInjectionError: If validation fails
        """
        if not cls.validate_pragma_value(pragma_name, value):
            raise SQLInjectionError(f"Invalid PRAGMA value: {pragma_name}={value}")

        # PRAGMA statements don't support parameterized queries, but we've validated the values
        cursor.execute(f"PRAGMA {pragma_name} = {value}")

    @classmethod
    def safe_identifier_query(cls, query_template: str, identifier: str, **params) -> str:
        """Safely construct a query with an identifier.

        Args:
            query_template: Query template with {identifier} placeholder
            identifier: Identifier to insert
            **params: Additional parameters for the query

        Returns:
            Safe query string

        Raises:
            SQLInjectionError: If identifier is invalid
        """
        if not cls.validate_identifier(identifier):
            raise SQLInjectionError(f"Invalid identifier: {identifier}")

        return query_template.format(identifier=identifier)

    @classmethod
    def validate_sql_string(cls, sql_string: str) -> bool:
        """Validate SQL string for potential injection patterns.

        Args:
            sql_string: SQL string to validate

        Returns:
            True if safe, False if potential injection detected
        """
        # Check for common injection patterns
        dangerous_patterns = [
            r';\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)',
            r'UNION\s+SELECT',
            r'--\s*$',
            r'/\*.*\*/',
            r'OR\s+1\s*=\s*1',
            r'AND\s+1\s*=\s*1',
            r'EXEC\s*\(',
            r'EXECUTE\s*\(',
            r'SCRIPT\s*',
        ]

        sql_upper = sql_string.upper()
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return False

        # Check for comment patterns that could hide malicious code
        comment_patterns = [
            r'--\s*DROP',
            r'--\s*DELETE',
            r'--\s*INSERT',
            r'--\s*UPDATE',
            r'--\s*ALTER',
            r'--\s*CREATE',
            r'/\*.*DROP.*\*/',
            r'/\*.*DELETE.*\*/',
            r'/\*.*INSERT.*\*/',
            r'/\*.*UPDATE.*\*/',
            r'/\*.*ALTER.*\*/',
            r'/\*.*CREATE.*\*/',
        ]

        for pattern in comment_patterns:
            if re.search(pattern, sql_string, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return False

        return True

    @classmethod
    def safe_execute(cls, cursor: sqlite3.Cursor, query: str, params: tuple = None) -> None:
        """Safely execute a SQL query with parameter validation.

        Args:
            cursor: Database cursor
            query: SQL query string
            params: Query parameters

        Raises:
            SQLInjectionError: If query is unsafe
        """
        if not cls.validate_sql_string(query):
            raise SQLInjectionError(f"Unsafe SQL query detected: {query}")

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)


def safe_pragma_set(cursor: sqlite3.Cursor, pragma_name: str, value: Any) -> None:
    """Safely set a PRAGMA value.

    Args:
        cursor: Database cursor
        pragma_name: Name of the PRAGMA
        value: Value to set

    Raises:
        SQLInjectionError: If validation fails
    """
    SafeSQLExecutor.safe_pragma_execute(cursor, pragma_name, value)


def safe_identifier_query(query_template: str, identifier: str, **params) -> str:
    """Safely construct a query with an identifier.

    Args:
        query_template: Query template with {identifier} placeholder
        identifier: Identifier to insert
        **params: Additional parameters for the query

    Returns:
        Safe query string

    Raises:
        SQLInjectionError: If identifier is invalid
    """
    return SafeSQLExecutor.safe_identifier_query(query_template, identifier, **params)


def validate_query_params(params: tuple | list | dict) -> bool:
    """Validate query parameters for safety.

    Args:
        params: Query parameters to validate

    Returns:
        True if safe, False if potential injection detected
    """
    if not params:
        return True

    if isinstance(params, (tuple, list)):
        for param in params:
            if isinstance(param, str) and not SafeSQLExecutor.validate_sql_string(param):
                # Check for SQL injection patterns in string parameters
                return False
    elif isinstance(params, dict):
        for key, value in params.items():
            if not SafeSQLExecutor.validate_identifier(key, "parameter name"):
                return False
            if isinstance(value, str) and not SafeSQLExecutor.validate_sql_string(value):
                return False

    return True
