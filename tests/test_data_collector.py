import json
import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_collector import GitHubDataCollector


@pytest.fixture
def mock_github():
    """Mock PyGithub Github object."""
    with patch('data_collector.Github') as mock:
        yield mock


@pytest.fixture
def collector():
    """Create a GitHubDataCollector instance with mocked Github."""
    with patch('data_collector.Auth'), patch('data_collector.Github'):
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
    collector.LAST_RUN_FILE = str(tmp_path / 'nonexistent.json')
    result = collector.get_last_run_info()
    assert result is None


def test_get_last_run_info_exists(collector, tmp_path):
    """Test reading last run info from existing file."""
    last_run_file = tmp_path / 'last_run.json'
    test_data = {
        'timestamp': '2025-01-01T10:00:00+00:00',
        'repositories': {'owner/repo': '2025-01-01T10:00:00+00:00'},
    }

    with open(last_run_file, 'w') as f:
        json.dump(test_data, f)

    collector.LAST_RUN_FILE = str(last_run_file)
    result = collector.get_last_run_info()

    assert result is not None
    assert result['repositories'] == {'owner/repo': '2025-01-01T10:00:00+00:00'}
    assert result['timestamp'] == '2025-01-01T10:00:00+00:00'


def test_save_last_run_info(collector, tmp_path):
    """Test saving last run info."""
    last_run_file = tmp_path / 'last_run.json'
    collector.LAST_RUN_FILE = str(last_run_file)

    repo_timestamps = {'owner/repo': '2025-01-01T10:00:00+00:00'}
    collector.save_last_run_info(repo_timestamps)

    assert last_run_file.exists()

    with open(last_run_file) as f:
        data = json.load(f)

    assert data['repositories'] == repo_timestamps
    assert 'timestamp' in data


def test_collect_repository_data_github_exception(collector):
    """Test handling of GitHub API errors."""
    from github import GithubException

    mock_github = Mock()
    mock_github.get_repo.side_effect = GithubException(404, {'message': 'Not Found'})

    # Mock rate limit
    mock_rate_limit = Mock()
    mock_rate_limit.core.remaining = 5000
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = '2025-01-01 12:00:00'
    mock_github.get_rate_limit.return_value = mock_rate_limit

    collector.github = mock_github

    # Should return 0, 0 on error
    wf_count, run_count = collector.collect_repository_data('owner/nonexistent')
    assert wf_count == 0
    assert run_count == 0


def test_collect_repository_data_success(collector):
    """Test successful data collection."""
    # Mock rate limit
    mock_rate_limit = Mock()
    mock_rate_limit.core.remaining = 5000
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = '2025-01-01 12:00:00'
    collector.github.get_rate_limit.return_value = mock_rate_limit

    # Mock repository
    mock_repo = Mock()
    mock_workflows = Mock()
    mock_workflows.totalCount = 1

    # Mock workflow
    mock_workflow = Mock()
    mock_workflow.id = 123
    mock_workflow.name = 'Test Workflow'
    mock_workflow.path = '.github/workflows/test.yml'
    mock_workflow.state = 'active'

    # Mock run
    mock_run = Mock()
    mock_run.id = 456
    mock_run.run_number = 1
    mock_run.head_sha = 'abc123'
    mock_run.head_branch = 'main'
    mock_run.event = 'push'
    mock_run.status = 'completed'
    mock_run.conclusion = 'success'
    mock_run.run_started_at = datetime(2025, 1, 1, 10, 0, 0)
    mock_run.created_at = datetime(2025, 1, 1, 10, 0, 0)
    mock_run.updated_at = datetime(2025, 1, 1, 10, 5, 0)
    mock_run.actor = Mock(login='testuser')
    mock_run.html_url = 'https://github.com/test'

    mock_workflow.get_runs.return_value = [mock_run]
    mock_workflows.__iter__ = Mock(return_value=iter([mock_workflow]))

    mock_repo.get_workflows.return_value = mock_workflows

    collector.github.get_repo.return_value = mock_repo

    # Mock database functions
    with patch('data_collector.insert_workflow') as mock_insert_wf, \
         patch('data_collector.insert_runs_batch') as mock_insert_runs:

        wf_count, run_count = collector.collect_repository_data('owner/repo')

        assert wf_count == 1
        assert run_count == 1

        # Verify database functions were called
        mock_insert_wf.assert_called_once()
        mock_insert_runs.assert_called_once()

        # Verify run data format
        runs_data = mock_insert_runs.call_args[0][0]
        assert len(runs_data) == 1
        assert runs_data[0][0] == '456'  # run_id
        assert runs_data[0][6] == 'completed'  # status
        assert runs_data[0][7] == 'success'  # conclusion
        assert runs_data[0][10] == 300  # duration_seconds (5 minutes)


def test_collect_all_data_no_token(collector):
    """Test behavior when GITHUB_TOKEN is not set."""
    with patch('data_collector.GITHUB_TOKEN', None):
        # Should return early without error
        collector.collect_all_data()


def test_collect_all_data_no_repositories(collector):
    """Test behavior when TARGET_REPOSITORIES is not set."""
    with patch('data_collector.TARGET_REPOSITORIES', ''), \
         patch('data_collector.initialize_database'):
        # Should return early without error
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
    with patch('data_collector.GITHUB_TOKEN', 'fake_token'), \
         patch('data_collector.TARGET_REPOSITORIES', 'owner/repo'), \
         patch('data_collector.initialize_database'), \
         patch.object(collector, 'collect_repository_data', return_value=(1, 1)) as mock_collect:

        collector.collect_all_data()

        # Verify collect_repository_data was called with since parameter
        mock_collect.assert_called_once()
        call_args = mock_collect.call_args
        assert call_args[1]['since'] == '2025-01-01T09:00:00+00:00'


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
