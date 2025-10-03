"""Tests for database security measures."""

from unittest.mock import Mock, patch

import pytest

from cipette.database import insert_run, insert_runs_batch, insert_workflow


class TestDatabaseSecurity:
    """Test database security measures."""

    def test_insert_workflow_safe_parameters(self):
        """Test insert_workflow with safe parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = [1]  # Mock repository ID
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Should not raise any exception
            result = insert_workflow('workflow_123', 'test/repo', 'Test Workflow')
            assert result is True

    def test_insert_workflow_dangerous_parameters(self):
        """Test insert_workflow with dangerous parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Should raise ValueError for dangerous parameters
            with pytest.raises(ValueError, match="Invalid parameters detected"):
                insert_workflow('workflow_123; DROP TABLE', 'test/repo', 'Test Workflow')

    def test_insert_run_safe_parameters(self):
        """Test insert_run with safe parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = [1]  # Mock ID for normalized entities
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Should not raise any exception
            insert_run(
                'run_123', 'workflow_123', 1, 'commit_sha', 'main', 'push',
                'completed', 'success', '2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z',
                3600, 'user', 'https://github.com/test/repo/actions/runs/123'
            )

    def test_insert_run_dangerous_parameters(self):
        """Test insert_run with dangerous parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Should raise ValueError for dangerous parameters
            with pytest.raises(ValueError, match="Invalid parameters detected"):
                insert_run(
                    'run_123; DROP TABLE', 'workflow_123', 1, 'commit_sha', 'main', 'push',
                    'completed', 'success', '2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z',
                    3600, 'user', 'https://github.com/test/repo/actions/runs/123'
                )

    def test_insert_runs_batch_safe_parameters(self):
        """Test insert_runs_batch with safe parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = [1]  # Mock ID for normalized entities
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            safe_data = [
                ('run_123', 'workflow_123', 1, 'commit_sha', 'main', 'push',
                 'completed', 'success', '2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z',
                 3600, 'user', 'https://github.com/test/repo/actions/runs/123')
            ]

            # Should not raise any exception
            result = insert_runs_batch(safe_data)
            assert result is True

    def test_insert_runs_batch_dangerous_parameters(self):
        """Test insert_runs_batch with dangerous parameters."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            dangerous_data = [
                ('run_123; DROP TABLE', 'workflow_123', 1, 'commit_sha', 'main', 'push',
                 'completed', 'success', '2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z',
                 3600, 'user', 'https://github.com/test/repo/actions/runs/123')
            ]

            # Should raise ValueError for dangerous parameters
            with pytest.raises(ValueError, match="Invalid batch data detected"):
                insert_runs_batch(dangerous_data)

    def test_insert_runs_batch_empty_data(self):
        """Test insert_runs_batch with empty data."""
        with patch('cipette.database.get_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Should return early without error
            result = insert_runs_batch([])
            assert result is None

    def test_build_metrics_query_safe_parameters(self):
        """Test _build_metrics_query with safe parameters."""
        from cipette.database import _build_metrics_query

        # Should not raise any exception
        query, params = _build_metrics_query(repository='test/repo', days=30)
        assert isinstance(query, str)
        assert isinstance(params, list)

    def test_build_metrics_query_dangerous_parameters(self):
        """Test _build_metrics_query with dangerous parameters."""
        from cipette.database import _build_metrics_query

        # Should raise ValueError for dangerous repository parameter
        with pytest.raises(ValueError, match="Invalid repository parameter"):
            _build_metrics_query(repository='test/repo; DROP TABLE')

        # Should raise ValueError for invalid days parameter
        with pytest.raises(ValueError, match="Invalid days parameter"):
            _build_metrics_query(days=-1)

        with pytest.raises(ValueError, match="Invalid days parameter"):
            _build_metrics_query(days='not_a_number')

    def test_build_metrics_query_none_parameters(self):
        """Test _build_metrics_query with None parameters."""
        from cipette.database import _build_metrics_query

        # Should not raise any exception
        query, params = _build_metrics_query()
        assert isinstance(query, str)
        assert isinstance(params, list)
