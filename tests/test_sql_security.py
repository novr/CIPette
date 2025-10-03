"""Tests for SQL security utilities."""

from unittest.mock import Mock

import pytest

from cipette.sql_security import (
    SafePragmaSet,
    SafeSQLExecutor,
    SQLInjectionError,
    ValidateQueryParams,
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
        assert not SafeSQLExecutor.validate_pragma_value('synchronous', 'WRONG')

    def test_validate_pragma_value_valid_integer(self):
        """Test validation of valid integer PRAGMA values."""
        assert SafeSQLExecutor.validate_pragma_value('busy_timeout', 5000)
        assert SafeSQLExecutor.validate_pragma_value('cache_size', -2000)
        assert SafeSQLExecutor.validate_pragma_value('user_version', 1)

    def test_validate_pragma_value_invalid_integer(self):
        """Test validation of invalid integer PRAGMA values."""
        assert not SafeSQLExecutor.validate_pragma_value('busy_timeout', 'not_a_number')
        assert not SafeSQLExecutor.validate_pragma_value('cache_size', None)

    def test_safe_pragma_execute_valid(self):
        """Test safe PRAGMA execution with valid values."""
        mock_cursor = Mock()
        SafeSQLExecutor.safe_pragma_execute(mock_cursor, 'journal_mode', 'WAL')
        mock_cursor.execute.assert_called_once_with('PRAGMA journal_mode = WAL')

    def test_safe_pragma_execute_invalid(self):
        """Test safe PRAGMA execution with invalid values."""
        mock_cursor = Mock()
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_pragma_execute(mock_cursor, 'journal_mode', 'INVALID')

    def test_safe_execute_with_params(self):
        """Test safe SQL execution with parameters."""
        mock_cursor = Mock()
        SafeSQLExecutor.safe_execute(mock_cursor, 'SELECT * FROM workflows WHERE id = ?', (1,))
        mock_cursor.execute.assert_called_once_with('SELECT * FROM workflows WHERE id = ?', (1,))

    def test_safe_execute_without_params(self):
        """Test safe SQL execution without parameters."""
        mock_cursor = Mock()
        SafeSQLExecutor.safe_execute(mock_cursor, 'SELECT * FROM workflows')
        mock_cursor.execute.assert_called_once_with('SELECT * FROM workflows')

    def test_safe_executemany(self):
        """Test safe SQL execution with multiple parameter sets."""
        mock_cursor = Mock()
        params_list = [(1, 'workflow1'), (2, 'workflow2')]
        SafeSQLExecutor.safe_executemany(mock_cursor, 'INSERT INTO workflows (id, name) VALUES (?, ?)', params_list)
        mock_cursor.executemany.assert_called_once_with('INSERT INTO workflows (id, name) VALUES (?, ?)', params_list)

    def test_safe_execute_with_sqlite_error(self):
        """Test safe_execute with actual SQLite errors."""
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Test with invalid SQL that causes SQLite error
        with pytest.raises(SQLInjectionError, match='SQL execution failed'):
            SafeSQLExecutor.safe_execute(cursor, 'INVALID SQL SYNTAX')

        conn.close()


class TestSafePragmaSet:
    """Test SafePragmaSet class."""

    def test_safe_pragma_set_valid(self):
        """Test safe PRAGMA setting with valid values."""
        mock_cursor = Mock()
        SafePragmaSet.safe_pragma_set(mock_cursor, 'journal_mode', 'WAL')
        mock_cursor.execute.assert_called_once_with('PRAGMA journal_mode = WAL')

    def test_safe_pragma_set_invalid(self):
        """Test safe PRAGMA setting with invalid values."""
        mock_cursor = Mock()
        with pytest.raises(SQLInjectionError):
            SafePragmaSet.safe_pragma_set(mock_cursor, 'journal_mode', 'INVALID')


class TestValidateQueryParams:
    """Test ValidateQueryParams class."""

    def test_validate_query_params_safe_tuple(self):
        """Test validation of safe tuple parameters."""
        assert ValidateQueryParams.validate_query_params(
            ('workflow_id', 'repository_name', 'workflow_name')
        )
        assert ValidateQueryParams.validate_query_params((1, 2, 3))
        assert ValidateQueryParams.validate_query_params(('workflow_id', None, 'workflow_name'))

    def test_validate_query_params_dangerous_tuple(self):
        """Test validation of dangerous tuple parameters."""
        assert not ValidateQueryParams.validate_query_params(('workflow_id; DROP TABLE', 'repository_name'))
        assert not ValidateQueryParams.validate_query_params(
            ('workflow_id', 'repository_name--', 'workflow_name')
        )
        assert not ValidateQueryParams.validate_query_params(
            ('workflow_id', 'repository_name/*', 'workflow_name')
        )

    def test_validate_query_params_safe_dict(self):
        """Test validation of safe dictionary parameters."""
        assert ValidateQueryParams.validate_query_params({'workflow_id': '123', 'repository': 'test/repo'})
        assert ValidateQueryParams.validate_query_params({'name': 'workflow_name', 'status': 'completed'})

    def test_validate_query_params_dangerous_dict(self):
        """Test validation of dangerous dictionary parameters."""
        assert not ValidateQueryParams.validate_query_params({'workflow_id; DROP TABLE': '123'})
        assert not ValidateQueryParams.validate_query_params({'workflow_id': '123; DROP TABLE'})
        assert not ValidateQueryParams.validate_query_params({'workflow_id--': '123'})

    def test_validate_query_params_none(self):
        """Test validation of None parameters."""
        assert ValidateQueryParams.validate_query_params(None)
        assert ValidateQueryParams.validate_query_params([])
        assert ValidateQueryParams.validate_query_params(())

    def test_validate_query_params_datetime(self):
        """Test validation of datetime parameters."""
        from datetime import datetime
        now = datetime.now()
        assert ValidateQueryParams.validate_query_params((now, 'test'))
        assert ValidateQueryParams.validate_query_params({'timestamp': now})

    def test_validate_query_params_edge_cases(self):
        """Test validation of edge cases."""
        # Test empty string
        assert ValidateQueryParams.validate_query_params(('', 'test'))

        # Test string with only spaces
        assert ValidateQueryParams.validate_query_params(('   ', 'test'))

        # Test mixed safe and dangerous
        assert not ValidateQueryParams.validate_query_params(('safe', 'dangerous; DROP TABLE'))

    def test_validate_query_params_complex_structures(self):
        """Test validation of complex data structures."""
        # Test nested dict (should fail)
        complex_dict = {
            'workflow_id': 123,
            'metadata': {'name': 'test', 'status': 'completed'}
        }
        assert not ValidateQueryParams.validate_query_params(complex_dict)


class TestSQLInjectionError:
    """Test SQLInjectionError exception."""

    def test_sql_injection_error_creation(self):
        """Test SQLInjectionError creation."""
        error = SQLInjectionError('Test error message')
        assert str(error) == 'Test error message'
