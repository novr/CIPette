"""Tests for SQL security utilities."""

import pytest
import sqlite3
from unittest.mock import Mock

from cipette.sql_security import (
    SafeSQLExecutor,
    SQLInjectionError,
    safe_pragma_set,
    safe_identifier_query,
    validate_query_params,
)


class TestSafeSQLExecutor:
    """Test SafeSQLExecutor class."""

    def test_validate_pragma_value_valid_string(self):
        """Test validation of valid string PRAGMA values."""
        assert SafeSQLExecutor.validate_pragma_value('journal_mode', 'WAL')
        assert SafeSQLExecutor.validate_pragma_value('synchronous', 'NORMAL')
        assert SafeSQLExecutor.validate_pragma_value('temp_store', 'MEMORY')

    def test_validate_pragma_value_invalid_string(self):
        """Test validation of invalid string PRAGMA values."""
        assert not SafeSQLExecutor.validate_pragma_value('journal_mode', 'INVALID')
        assert not SafeSQLExecutor.validate_pragma_value('synchronous', 'BAD_VALUE')

    def test_validate_pragma_value_valid_integer(self):
        """Test validation of valid integer PRAGMA values."""
        assert SafeSQLExecutor.validate_pragma_value('busy_timeout', 10000)
        assert SafeSQLExecutor.validate_pragma_value('cache_size', 1000)
        assert SafeSQLExecutor.validate_pragma_value('user_version', 1)

    def test_validate_pragma_value_invalid_integer(self):
        """Test validation of invalid integer PRAGMA values."""
        assert not SafeSQLExecutor.validate_pragma_value('busy_timeout', 'not_a_number')
        assert not SafeSQLExecutor.validate_pragma_value('cache_size', None)

    def test_validate_identifier_valid(self):
        """Test validation of valid identifiers."""
        assert SafeSQLExecutor.validate_identifier('workflows')
        assert SafeSQLExecutor.validate_identifier('runs')
        assert SafeSQLExecutor.validate_identifier('workflow_id')
        assert SafeSQLExecutor.validate_identifier('_private_table')

    def test_validate_identifier_invalid(self):
        """Test validation of invalid identifiers."""
        assert not SafeSQLExecutor.validate_identifier('workflows; DROP TABLE')
        assert not SafeSQLExecutor.validate_identifier('workflows--')
        assert not SafeSQLExecutor.validate_identifier('workflows/*')
        assert not SafeSQLExecutor.validate_identifier('123invalid')
        assert not SafeSQLExecutor.validate_identifier('')

    def test_validate_sql_string_safe(self):
        """Test validation of safe SQL strings."""
        assert SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows")
        assert SafeSQLExecutor.validate_sql_string("INSERT INTO runs VALUES (?, ?)")
        assert SafeSQLExecutor.validate_sql_string("UPDATE workflows SET name = ?")

    def test_validate_sql_string_dangerous(self):
        """Test validation of dangerous SQL strings."""
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows; DROP TABLE workflows")
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows UNION SELECT * FROM users")
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows OR 1=1")
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows AND 1=1")
        # Test comment patterns that could hide malicious code
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows -- DROP TABLE")
        assert not SafeSQLExecutor.validate_sql_string("SELECT * FROM workflows /* DROP TABLE */")

    def test_safe_pragma_execute_valid(self):
        """Test safe PRAGMA execution with valid values."""
        mock_cursor = Mock()
        SafeSQLExecutor.safe_pragma_execute(mock_cursor, 'journal_mode', 'WAL')
        mock_cursor.execute.assert_called_once_with("PRAGMA journal_mode = ?", ('WAL',))

    def test_safe_pragma_execute_invalid(self):
        """Test safe PRAGMA execution with invalid values."""
        mock_cursor = Mock()
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_pragma_execute(mock_cursor, 'journal_mode', 'INVALID')

    def test_safe_identifier_query_valid(self):
        """Test safe identifier query construction."""
        query = SafeSQLExecutor.safe_identifier_query(
            "SELECT * FROM {identifier}",
            "workflows"
        )
        assert query == "SELECT * FROM workflows"

    def test_safe_identifier_query_invalid(self):
        """Test safe identifier query construction with invalid identifier."""
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_identifier_query(
                "SELECT * FROM {identifier}",
                "workflows; DROP TABLE"
            )


class TestSafePragmaSet:
    """Test safe_pragma_set function."""

    def test_safe_pragma_set_valid(self):
        """Test safe PRAGMA setting with valid values."""
        mock_cursor = Mock()
        safe_pragma_set(mock_cursor, 'journal_mode', 'WAL')
        mock_cursor.execute.assert_called_once_with("PRAGMA journal_mode = ?", ('WAL',))

    def test_safe_pragma_set_invalid(self):
        """Test safe PRAGMA setting with invalid values."""
        mock_cursor = Mock()
        with pytest.raises(SQLInjectionError):
            safe_pragma_set(mock_cursor, 'journal_mode', 'INVALID')


class TestSafeIdentifierQuery:
    """Test safe_identifier_query function."""

    def test_safe_identifier_query_valid(self):
        """Test safe identifier query with valid identifier."""
        query = safe_identifier_query("SELECT * FROM {identifier}", "workflows")
        assert query == "SELECT * FROM workflows"

    def test_safe_identifier_query_invalid(self):
        """Test safe identifier query with invalid identifier."""
        with pytest.raises(SQLInjectionError):
            safe_identifier_query("SELECT * FROM {identifier}", "workflows; DROP TABLE")


class TestValidateQueryParams:
    """Test validate_query_params function."""

    def test_validate_query_params_safe_tuple(self):
        """Test validation of safe tuple parameters."""
        assert validate_query_params(('workflow_id', 'repository_name', 'workflow_name'))
        assert validate_query_params((1, 2, 3))
        assert validate_query_params(('workflow_id', None, 'workflow_name'))

    def test_validate_query_params_dangerous_tuple(self):
        """Test validation of dangerous tuple parameters."""
        assert not validate_query_params(('workflow_id; DROP TABLE', 'repository_name'))
        assert not validate_query_params(('workflow_id', 'repository_name-- DROP TABLE', 'workflow_name'))
        assert not validate_query_params(('workflow_id', 'repository_name/* DROP TABLE */', 'workflow_name'))

    def test_validate_query_params_safe_dict(self):
        """Test validation of safe dictionary parameters."""
        assert validate_query_params({'workflow_id': '123', 'repository': 'test/repo'})
        assert validate_query_params({'name': 'workflow_name', 'status': 'completed'})

    def test_validate_query_params_dangerous_dict(self):
        """Test validation of dangerous dictionary parameters."""
        assert not validate_query_params({'workflow_id; DROP TABLE': '123'})
        assert not validate_query_params({'workflow_id': '123; DROP TABLE'})
        assert not validate_query_params({'workflow_id--': '123'})

    def test_validate_query_params_none(self):
        """Test validation of None parameters."""
        assert validate_query_params(None)
        assert validate_query_params([])
        assert validate_query_params(())


class TestSQLInjectionError:
    """Test SQLInjectionError exception."""

    def test_sql_injection_error_creation(self):
        """Test SQLInjectionError creation."""
        error = SQLInjectionError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
