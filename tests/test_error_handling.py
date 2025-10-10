"""Tests for improved error handling functionality."""

import pytest

from cipette.error_handling import (
    CIPetteError,
    ConfigurationError,
    DatabaseError,
    DataProcessingError,
    GitHubAPIError,
    handle_api_errors,
    handle_data_processing_errors,
    handle_database_errors,
)


class TestCIPetteError:
    """Test base CIPette error class."""

    def test_error_with_context(self):
        """Test error with context information."""
        context = {'operation': 'test', 'value': 123}
        cause = ValueError('Original error')

        error = CIPetteError('Test error', context=context, cause=cause)

        assert str(error) == 'Test error'
        assert error.context == context
        assert error.cause == cause
        assert error.timestamp is not None

    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        context = {'operation': 'test'}
        cause = ValueError('Original error')

        error = CIPetteError('Test error', context=context, cause=cause)
        error_dict = error.to_dict()

        assert error_dict['error_type'] == 'CIPetteError'
        assert error_dict['message'] == 'Test error'
        assert error_dict['context'] == context
        assert error_dict['cause'] == 'Original error'
        assert 'timestamp' in error_dict


class TestDatabaseError:
    """Test database error class."""

    def test_database_error_with_operation(self):
        """Test database error with operation context."""
        error = DatabaseError(
            'Query failed',
            operation='SELECT',
            query='SELECT * FROM test',
            context={'table': 'test'},
            cause=ValueError('SQL error'),
        )

        assert str(error) == 'Query failed'
        assert error.context['operation'] == 'SELECT'
        assert error.context['query'] == 'SELECT * FROM test'
        assert error.context['table'] == 'test'
        assert error.cause is not None


class TestGitHubAPIError:
    """Test GitHub API error class."""

    def test_github_api_error_with_endpoint(self):
        """Test GitHub API error with endpoint context."""
        error = GitHubAPIError(
            'API request failed',
            endpoint='/repos/test/repo',
            status_code=404,
            rate_limit_remaining=100,
            context={'method': 'GET'},
            cause=ValueError('HTTP error'),
        )

        assert str(error) == 'API request failed'
        assert error.context['endpoint'] == '/repos/test/repo'
        assert error.context['status_code'] == 404
        assert error.context['rate_limit_remaining'] == 100
        assert error.context['method'] == 'GET'


class TestConfigurationError:
    """Test configuration error class."""

    def test_configuration_error_with_key(self):
        """Test configuration error with config key context."""
        error = ConfigurationError(
            'Invalid configuration value',
            config_key='database.timeout',
            expected_type='int',
            actual_value='invalid',
            context={'file': 'config.toml'},
            cause=TypeError('Type error'),
        )

        assert str(error) == 'Invalid configuration value'
        assert error.context['config_key'] == 'database.timeout'
        assert error.context['expected_type'] == 'int'
        assert error.context['actual_value'] == 'invalid'
        assert error.context['file'] == 'config.toml'


class TestDataProcessingError:
    """Test data processing error class."""

    def test_data_processing_error_with_stage(self):
        """Test data processing error with processing stage context."""
        error = DataProcessingError(
            'Data processing failed',
            data_type='workflow_run',
            processing_stage='health_score_calculation',
            context={'input_size': 1000},
            cause=ValueError('Processing error'),
        )

        assert str(error) == 'Data processing failed'
        assert error.context['data_type'] == 'workflow_run'
        assert error.context['processing_stage'] == 'health_score_calculation'
        assert error.context['input_size'] == 1000


class TestErrorHandlingDecorators:
    """Test error handling decorators."""

    def test_handle_database_errors_success(self):
        """Test database error handler with successful operation."""

        @handle_database_errors
        def test_func():
            return 'success'

        result = test_func()
        assert result == 'success'

    def test_handle_database_errors_operational_error(self):
        """Test database error handler with operational error."""

        @handle_database_errors
        def test_func():
            import sqlite3

            raise sqlite3.OperationalError('database is locked')

        result = test_func()
        assert result is None

    def test_handle_database_errors_database_error(self):
        """Test database error handler with database error."""

        @handle_database_errors
        def test_func():
            import sqlite3

            raise sqlite3.DatabaseError('Database error')

        with pytest.raises(DatabaseError) as exc_info:
            test_func()

        error = exc_info.value
        assert 'Database error' in str(error)
        assert error.context['error_code'] == 'DATABASE_ERROR'

    def test_handle_api_errors_success(self):
        """Test API error handler with successful operation."""

        @handle_api_errors
        def test_func():
            return 'success'

        result = test_func()
        assert result == 'success'

    def test_handle_api_errors_exception(self):
        """Test API error handler with exception."""

        @handle_api_errors
        def test_func():
            raise ValueError('API error')

        with pytest.raises(GitHubAPIError) as exc_info:
            test_func()

        error = exc_info.value
        assert 'API operation failed' in str(error)
        assert error.context['function'] == 'test_func'

    def test_handle_data_processing_errors_key_error(self):
        """Test data processing error handler with KeyError."""

        @handle_data_processing_errors
        def test_func(data):
            raise KeyError('Missing key')

        result = test_func({'test': 'data'})
        assert result is None

    def test_handle_data_processing_errors_value_error(self):
        """Test data processing error handler with ValueError."""

        @handle_data_processing_errors
        def test_func(data):
            raise ValueError('Invalid value')

        result = test_func({'test': 'data'})
        assert result is None

    def test_handle_data_processing_errors_unexpected_error(self):
        """Test data processing error handler with unexpected error."""

        @handle_data_processing_errors
        def test_func(data):
            raise RuntimeError('Unexpected error')

        with pytest.raises(DataProcessingError) as exc_info:
            test_func({'test': 'data'})

        error = exc_info.value
        assert 'Unexpected data processing error' in str(error)
        assert error.context['data_type'] == 'dict'
        assert error.context['processing_stage'] == 'test_func'
