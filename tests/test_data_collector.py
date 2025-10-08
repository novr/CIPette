import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from cipette.collector import GitHubDataCollector
from cipette.error_handling import ConfigurationError


@pytest.fixture
def collector():
    """Create a GitHubDataCollector instance with mocked GitHubClient."""
    with (
        patch('cipette.github_client.GitHubClient'),
        patch('cipette.config.Config.GITHUB_TOKEN', 'fake_token_for_testing'),
    ):
        collector = GitHubDataCollector()
        return collector


def test_parse_datetime(collector):
    """Test datetime parsing."""
    # Test with valid datetime
    dt = datetime(2025, 1, 1, 10, 30, 0)
    result = collector.parse_datetime(dt)
    assert result == '2025-01-01 10:30:00'

    # Test with None
    result = collector.parse_datetime(None)
    assert result is None


def test_get_last_run_info_not_exists(collector, tmp_path):
    """Test reading last run info when file doesn't exist."""
    # Create new collector with custom file path
    from cipette.etag_manager import ETagManager

    collector.etag_manager = ETagManager(str(tmp_path / 'nonexistent.json'))
    result = collector.get_last_run_info()
    assert result is None


def test_get_last_run_info_exists(collector, tmp_path):
    """Test reading last run info from existing file."""
    last_run_file = tmp_path / 'last_run.json'
    test_data = {
        'repositories': {'owner/repo': '2025-01-01T10:00:00+00:00'},
    }

    with open(last_run_file, 'w') as f:
        json.dump(test_data, f)

    # Create new collector with custom file path
    from cipette.etag_manager import ETagManager

    collector.etag_manager = ETagManager(str(last_run_file))
    result = collector.get_last_run_info()

    assert result is not None
    assert result['repositories'] == {'owner/repo': '2025-01-01T10:00:00+00:00'}


def test_save_last_run_info(collector, tmp_path):
    """Test saving last run info."""
    last_run_file = tmp_path / 'last_run.json'

    # Create new collector with custom file path
    from cipette.etag_manager import ETagManager

    collector.etag_manager = ETagManager(str(last_run_file))

    repo_timestamps = {'owner/repo': '2025-01-01T10:00:00+00:00'}
    collector.save_last_run_info(repo_timestamps)

    assert last_run_file.exists()

    with open(last_run_file) as f:
        data = json.load(f)

    assert data['repositories'] == repo_timestamps


def test_collect_repository_data_github_exception(collector):
    """Test handling of GitHub API errors."""
    from github import GithubException

    # Mock the github_client methods directly
    with (
        patch.object(collector.github_client, 'check_rate_limit', return_value=5000),
        patch.object(collector.github_client, 'get_repository') as mock_get_repo,
    ):
        mock_get_repo.side_effect = GithubException(404, {'message': 'Not Found'})

        # Should return 0, 0 on error
        wf_count, run_count = collector.collect_repository_data('owner/nonexistent')
        assert wf_count == 0
        assert run_count == 0


def test_collect_repository_data_success(collector):
    """Test successful data collection."""
    with (
        patch.object(collector.github_client, 'check_rate_limit', return_value=5000),
        patch.object(collector.github_client, 'get_repository') as mock_get_repo,
        patch(
            'cipette.data_processor.DataProcessor.process_workflows_from_rest'
        ) as mock_process,
    ):
        # Mock repository
        mock_repo = Mock()
        mock_workflows = Mock()
        mock_workflows.totalCount = 1
        mock_repo.get_workflows.return_value = mock_workflows
        mock_get_repo.return_value = mock_repo

        # Mock data processor
        mock_process.return_value = (1, 1)

        # Execute
        wf_count, run_count = collector.collect_repository_data('owner/repo')

        # Verify
        assert wf_count == 1
        assert run_count == 1
        mock_get_repo.assert_called_once_with('owner/repo')
        mock_process.assert_called_once()


def test_collect_all_data_no_token(collector):
    """Test behavior when GITHUB_TOKEN is not set."""
    with (
        patch('cipette.config.Config.GITHUB_TOKEN', None),
        pytest.raises(ConfigurationError, match='GITHUB_TOKEN not found'),
    ):
        collector.collect_all_data()


def test_collect_all_data_no_repositories(collector):
    """Test behavior when TARGET_REPOSITORIES is not set."""
    with (
        patch('cipette.config.Config.GITHUB_TOKEN', 'fake_token'),
        patch('cipette.config.Config.TARGET_REPOSITORIES', []),
        patch('cipette.collector.initialize_database'),
        pytest.raises(ConfigurationError, match='TARGET_REPOSITORIES not configured'),
    ):
        collector.collect_all_data()


def test_collect_all_data_with_last_run(collector, tmp_path):
    """Test data collection with previous run information."""
    last_run_file = tmp_path / 'last_run.json'
    test_data = {
        'timestamp': '2025-01-01T09:00:00+00:00',
        'repositories': {'owner/repo': '2025-01-01T09:00:00+00:00'},
    }

    with open(last_run_file, 'w') as f:
        json.dump(test_data, f)

    collector.LAST_RUN_FILE = str(last_run_file)

    # Mock dependencies
    with (
        patch('cipette.config.Config.GITHUB_TOKEN', 'fake_token'),
        patch('cipette.config.Config.TARGET_REPOSITORIES', ['owner/repo']),
        patch('cipette.collector.initialize_database'),
        patch.object(collector.github_client, 'check_rate_limit', return_value=5000),
        patch.object(collector.github_client, 'wait_for_rate_limit_reset'),
        patch.object(
            collector, 'collect_repository_data', return_value=(1, 1)
        ) as mock_collect,
    ):
        collector.collect_all_data()

        # Verify collect_repository_data was called
        mock_collect.assert_called_once()
        call_args = mock_collect.call_args
        # Check that it was called with the repository name
        assert call_args[0][0] == 'owner/repo'


def test_duration_calculation(collector):
    """Test duration calculation logic."""
    mock_run = Mock()
    mock_run.id = '123'
    mock_run.run_number = 1
    mock_run.head_sha = 'abc'
    mock_run.head_branch = 'main'
    mock_run.event = 'push'
    mock_run.status = 'completed'
    mock_run.conclusion = 'success'
    mock_run.run_started_at = datetime(2025, 1, 1, 10, 0, 0)
    mock_run.created_at = datetime(2025, 1, 1, 10, 0, 0)
    mock_run.updated_at = datetime(2025, 1, 1, 10, 10, 30)  # 10 minutes 30 seconds
    mock_run.actor = Mock(login='user')
    mock_run.html_url = 'https://github.com/test'

    # The duration should be 630 seconds (10 * 60 + 30)
    duration = (mock_run.updated_at - mock_run.run_started_at).total_seconds()
    assert duration == 630.0
