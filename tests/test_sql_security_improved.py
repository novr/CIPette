"""Comprehensive tests for SQL security utilities."""

import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from cipette.sql_security import (
    SafeSQLExecutor,
    SafePragmaSet,
    SQLInjectionError,
    ValidateQueryParams,
)


class TestSafeSQLExecutorComprehensive:
    """Comprehensive tests for SafeSQLExecutor class."""

    def test_validate_pragma_value_edge_cases(self):
        """Test edge cases for PRAGMA value validation."""
        # Test unknown PRAGMA names
        assert not SafeSQLExecutor.validate_pragma_value('unknown_pragma', 'value')
        
        # Test boundary values
        assert SafeSQLExecutor.validate_pragma_value('busy_timeout', 0)
        assert SafeSQLExecutor.validate_pragma_value('busy_timeout', -1)
        assert SafeSQLExecutor.validate_pragma_value('cache_size', 0)
        
        # Test case sensitivity
        assert SafeSQLExecutor.validate_pragma_value('journal_mode', 'wal')  # lowercase
        assert SafeSQLExecutor.validate_pragma_value('journal_mode', 'WAL')  # uppercase

    def test_safe_execute_with_real_sqlite_errors(self):
        """Test safe_execute with real SQLite errors."""
        # Create a real in-memory database
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Test with invalid SQL
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_execute(cursor, 'INVALID SQL SYNTAX')
        
        conn.close()

    def test_safe_execute_with_sqlite_operational_error(self):
        """Test safe_execute with SQLite operational errors."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Test with table that doesn't exist
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_execute(cursor, 'SELECT * FROM non_existent_table')
        
        conn.close()

    def test_safe_executemany_with_empty_params(self):
        """Test safe_executemany with empty parameter list."""
        mock_cursor = Mock()
        SafeSQLExecutor.safe_executemany(mock_cursor, 'SELECT 1', [])
        mock_cursor.executemany.assert_called_once_with('SELECT 1', [])

    def test_safe_pragma_execute_with_sqlite_error(self):
        """Test safe_pragma_execute with SQLite errors."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Test with invalid PRAGMA value
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_pragma_execute(cursor, 'journal_mode', 'INVALID_VALUE')
        
        conn.close()


class TestValidateQueryParamsComprehensive:
    """Comprehensive tests for ValidateQueryParams class."""

    def test_is_safe_parameter_comprehensive(self):
        """Test _is_safe_parameter with various data types."""
        # Test safe parameters
        safe_params = [
            123,
            45.67,
            True,
            False,
            None,
            "normal_string",
            "string_with_numbers123",
            datetime.now(),
        ]
        
        for param in safe_params:
            assert ValidateQueryParams._is_safe_parameter(param), f"False negative for safe parameter: {param}"

    def test_is_safe_parameter_dangerous_strings(self):
        """Test _is_safe_parameter with dangerous strings."""
        dangerous_strings = [
            "value; DROP TABLE users",
            "value-- comment",
            "value/* block comment */",
            "value; DELETE FROM workflows",
            "value; INSERT INTO malicious_table",
            "value; UPDATE workflows SET name = 'hacked'",
            "value; ALTER TABLE workflows ADD COLUMN malicious",
            "value; CREATE TABLE malicious_table",
        ]
        
        for param in dangerous_strings:
            assert not ValidateQueryParams._is_safe_parameter(param), f"False negative for dangerous parameter: {param}"

    def test_is_safe_parameter_edge_cases(self):
        """Test _is_safe_parameter with edge cases."""
        # Test empty string
        assert ValidateQueryParams._is_safe_parameter("")
        
        # Test string with only spaces
        assert ValidateQueryParams._is_safe_parameter("   ")
        
        # Test string with newlines
        assert ValidateQueryParams._is_safe_parameter("value\nwith\nnewlines")
        
        # Test string with tabs
        assert ValidateQueryParams._is_safe_parameter("value\twith\ttabs")

    def test_validate_query_params_complex_structures(self):
        """Test validate_query_params with complex data structures."""
        # Test nested structures
        complex_params = {
            'workflow_id': 123,
            'metadata': {
                'name': 'test_workflow',
                'status': 'completed'
            },
            'timestamps': [datetime.now(), datetime.now()],
            'config': None
        }
        
        # This should fail because we don't handle nested dicts
        assert not ValidateQueryParams.validate_query_params(complex_params)

    def test_validate_query_params_mixed_types(self):
        """Test validate_query_params with mixed type parameters."""
        mixed_params = [
            123,
            "safe_string",
            datetime.now(),
            None,
            True,
            "dangerous; DROP TABLE users",
        ]
        
        assert not ValidateQueryParams.validate_query_params(mixed_params)

    def test_validate_query_params_empty_structures(self):
        """Test validate_query_params with empty data structures."""
        empty_structures = [
            [],
            (),
            {},
            None,
        ]
        
        for structure in empty_structures:
            assert ValidateQueryParams.validate_query_params(structure), f"Failed for empty structure: {structure}"


class TestSQLInjectionErrorComprehensive:
    """Comprehensive tests for SQLInjectionError exception."""

    def test_sql_injection_error_with_details(self):
        """Test SQLInjectionError with detailed error information."""
        error = SQLInjectionError('Dangerous pattern detected: DROP TABLE')
        assert 'Dangerous pattern detected' in str(error)
        assert 'DROP TABLE' in str(error)

    def test_sql_injection_error_inheritance(self):
        """Test SQLInjectionError inheritance from Exception."""
        error = SQLInjectionError('Test error')
        assert isinstance(error, Exception)
        assert isinstance(error, SQLInjectionError)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_real_database_operations(self):
        """Test with real SQLite database operations."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Create a test table
        cursor.execute('CREATE TABLE test_workflows (id INTEGER PRIMARY KEY, name TEXT)')
        
        # Test safe operations
        SafeSQLExecutor.safe_execute(cursor, 'INSERT INTO test_workflows (name) VALUES (?)', ('test_workflow',))
        SafeSQLExecutor.safe_execute(cursor, 'SELECT * FROM test_workflows WHERE id = ?', (1,))
        
        # Test dangerous operations
        with pytest.raises(SQLInjectionError):
            SafeSQLExecutor.safe_execute(cursor, 'SELECT * FROM test_workflows; DROP TABLE test_workflows')
        
        conn.close()

    def test_parameter_validation_in_real_scenario(self):
        """Test parameter validation in a real scenario."""
        # Simulate real workflow data
        workflow_data = (
            12345,  # workflow_id
            'test/repo',  # repository
            'test_workflow',  # name
            '.github/workflows/test.yml',  # path
            'active',  # state
        )
        
        assert ValidateQueryParams.validate_query_params(workflow_data)
        
        # Test with malicious data
        malicious_data = (
            12345,
            'test/repo; DROP TABLE workflows',  # malicious repository name
            'test_workflow',
            '.github/workflows/test.yml',
            'active',
        )
        
        assert not ValidateQueryParams.validate_query_params(malicious_data)

    def test_pragma_operations_in_real_scenario(self):
        """Test PRAGMA operations in a real scenario."""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Test valid PRAGMA operations
        SafePragmaSet.safe_pragma_set(cursor, 'journal_mode', 'WAL')
        SafePragmaSet.safe_pragma_set(cursor, 'synchronous', 'NORMAL')
        SafePragmaSet.safe_pragma_set(cursor, 'busy_timeout', 5000)
        
        # Test invalid PRAGMA operations
        with pytest.raises(SQLInjectionError):
            SafePragmaSet.safe_pragma_set(cursor, 'journal_mode', 'INVALID')
        
        conn.close()


class TestPerformanceAndEdgeCases:
    """Performance and edge case tests."""

    def test_large_parameter_validation(self):
        """Test parameter validation with large datasets."""
        large_params = list(range(1000))  # 1000 integers
        assert ValidateQueryParams.validate_query_params(large_params)
        
        # Test with one dangerous parameter in large set
        large_params_with_danger = list(range(999)) + ['safe; DROP TABLE users']
        assert not ValidateQueryParams.validate_query_params(large_params_with_danger)

    def test_unicode_parameter_validation(self):
        """Test parameter validation with Unicode strings."""
        unicode_params = [
            '正常な文字列',
            '🚀 rocket emoji',
            'café',
            'naïve',
        ]
        
        for param in unicode_params:
            assert ValidateQueryParams._is_safe_parameter(param), f"Failed for Unicode parameter: {param}"

    def test_sql_injection_with_unicode(self):
        """Test SQL injection detection with Unicode strings."""
        unicode_dangerous = [
            '正常な文字列; DROP TABLE users',
            '🚀 rocket; DELETE FROM workflows',
        ]
        
        for param in unicode_dangerous:
            assert not ValidateQueryParams._is_safe_parameter(param), f"Failed to detect Unicode SQL injection: {param}"
