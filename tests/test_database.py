import os
import sqlite3
import tempfile

import pytest

from cipette import config, database


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Use a temporary database for testing
    test_db_path = tempfile.mktemp(suffix='.db')

    # Temporarily override DATABASE_PATH
    original_path = config.DATABASE_PATH
    config.DATABASE_PATH = test_db_path
    database.DATABASE_PATH = test_db_path

    # Initialize test database
    database.initialize_database()

    yield test_db_path

    # Cleanup
    config.DATABASE_PATH = original_path
    database.DATABASE_PATH = original_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_initialize_database(test_db):
    """Test database initialization."""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Check workflows table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'")
    assert cursor.fetchone() is not None

    # Check runs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert cursor.fetchone() is not None

    # Check indexes exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_runs_conclusion'")
    assert cursor.fetchone() is not None

    conn.close()


def test_insert_and_get_workflow(test_db):
    """Test workflow insertion and retrieval."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Insert workflow
    database.insert_workflow('123', 'owner/repo', 'Test Workflow', '.github/workflows/test.yml', 'active')

    # Retrieve workflows
    workflows = database.get_workflows()
    assert len(workflows) == 1
    assert workflows[0]['id'] == '123'
    assert workflows[0]['repository'] == 'owner/repo'
    assert workflows[0]['name'] == 'Test Workflow'


def test_insert_and_get_runs(test_db):
    """Test run insertion and retrieval."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Insert workflow first
    database.insert_workflow('123', 'owner/repo', 'Test Workflow')

    # Insert run
    database.insert_run(
        '456', '123', 1, 'abc123', 'main', 'push',
        'completed', 'success', '2025-01-01 10:00:00',
        '2025-01-01 10:05:00', 300, 'testuser',
        'https://github.com/owner/repo/actions/runs/456'
    )

    # Retrieve runs
    runs = database.get_runs()
    assert len(runs) == 1
    assert runs[0]['id'] == '456'
    assert runs[0]['conclusion'] == 'success'
    assert runs[0]['duration_seconds'] == 300


def test_insert_runs_batch(test_db):
    """Test batch run insertion."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Insert workflow
    database.insert_workflow('123', 'owner/repo', 'Test Workflow')

    # Batch insert runs
    runs_data = [
        ('456', '123', 1, 'abc123', 'main', 'push', 'completed', 'success',
         '2025-01-01 10:00:00', '2025-01-01 10:05:00', 300, 'user1', 'https://github.com/test1'),
        ('457', '123', 2, 'def456', 'main', 'push', 'completed', 'failure',
         '2025-01-01 11:00:00', '2025-01-01 11:03:00', 180, 'user2', 'https://github.com/test2'),
    ]
    database.insert_runs_batch(runs_data)

    # Verify
    runs = database.get_runs()
    assert len(runs) == 2


def test_get_runs_with_filters(test_db):
    """Test run retrieval with various filters."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Setup test data
    database.insert_workflow('123', 'owner/repo1', 'Workflow 1')
    database.insert_workflow('124', 'owner/repo2', 'Workflow 2')

    runs_data = [
        ('456', '123', 1, 'abc', 'main', 'push', 'completed', 'success',
         '2025-01-01 10:00:00', '2025-01-01 10:05:00', 300, 'user1', 'url1'),
        ('457', '123', 2, 'def', 'main', 'push', 'completed', 'failure',
         '2025-01-01 11:00:00', '2025-01-01 11:03:00', 180, 'user2', 'url2'),
        ('458', '124', 1, 'ghi', 'dev', 'pull_request', 'completed', 'success',
         '2025-01-01 12:00:00', '2025-01-01 12:02:00', 120, 'user3', 'url3'),
    ]
    database.insert_runs_batch(runs_data)

    # Test workflow filter
    runs = database.get_runs(workflow_id='123')
    assert len(runs) == 2

    # Test conclusion filter
    runs = database.get_runs(conclusion='success')
    assert len(runs) == 2

    # Test repository filter
    runs = database.get_runs(repository='owner/repo1')
    assert len(runs) == 2

    # Test limit
    runs = database.get_runs(limit=1)
    assert len(runs) == 1


def test_get_metrics_by_repository(test_db):
    """Test metrics calculation."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Setup test data
    database.insert_workflow('123', 'owner/repo', 'Test Workflow')

    runs_data = [
        ('456', '123', 1, 'abc', 'main', 'push', 'completed', 'success',
         '2025-01-01 10:00:00', '2025-01-01 10:05:00', 300, 'user1', 'url1'),
        ('457', '123', 2, 'def', 'main', 'push', 'completed', 'failure',
         '2025-01-01 11:00:00', '2025-01-01 11:03:00', 180, 'user2', 'url2'),
        ('458', '123', 3, 'ghi', 'main', 'push', 'completed', 'success',
         '2025-01-01 12:00:00', '2025-01-01 12:04:00', 240, 'user3', 'url3'),
    ]
    database.insert_runs_batch(runs_data)

    # Calculate metrics
    metrics = database.get_metrics_by_repository()

    assert len(metrics) == 1
    assert metrics[0]['repository'] == 'owner/repo'
    assert metrics[0]['total_runs'] == 3
    assert metrics[0]['success_count'] == 2
    assert metrics[0]['failure_count'] == 1
    assert metrics[0]['success_rate'] == 66.67  # 2/3 * 100
    assert metrics[0]['avg_duration_seconds'] == 240.0  # (300 + 180 + 240) / 3


def test_calculate_mttr(test_db):
    """Test MTTR calculation."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Setup test data: failure followed by success
    database.insert_workflow('123', 'owner/repo', 'Test Workflow')

    runs_data = [
        ('456', '123', 1, 'abc', 'main', 'push', 'completed', 'failure',
         '2025-01-01 10:00:00', '2025-01-01 10:03:00', 180, 'user1', 'url1'),
        ('457', '123', 2, 'def', 'main', 'push', 'completed', 'success',
         '2025-01-01 10:10:00', '2025-01-01 10:15:00', 300, 'user2', 'url2'),
    ]
    database.insert_runs_batch(runs_data)

    # Calculate MTTR
    mttr = database.calculate_mttr(repository='owner/repo')

    # MTTR should be from failure completed (10:03) to success completed (10:15) = 12 minutes = 720 seconds
    assert mttr == 720.0


def test_idempotency(test_db):
    """Test that reinserting same data doesn't create duplicates."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Insert workflow twice
    database.insert_workflow('123', 'owner/repo', 'Test Workflow', 'path1', 'active')
    database.insert_workflow('123', 'owner/repo', 'Test Workflow Updated', 'path2', 'inactive')

    workflows = database.get_workflows()
    assert len(workflows) == 1
    assert workflows[0]['name'] == 'Test Workflow Updated'
    assert workflows[0]['path'] == 'path2'

    # Insert run twice
    database.insert_run(
        '456', '123', 1, 'abc123', 'main', 'push',
        'completed', 'success', '2025-01-01 10:00:00',
        '2025-01-01 10:05:00', 300, 'user1', 'url1'
    )
    database.insert_run(
        '456', '123', 1, 'abc123', 'main', 'push',
        'completed', 'failure', '2025-01-01 10:00:00',
        '2025-01-01 10:06:00', 360, 'user1', 'url1'
    )

    runs = database.get_runs()
    assert len(runs) == 1
    assert runs[0]['conclusion'] == 'failure'
    assert runs[0]['duration_seconds'] == 360


def test_sql_injection_protection(test_db):
    """Test that SQL injection attempts are safely handled."""
    from cipette import database
    database.DATABASE_PATH = test_db

    database.insert_workflow('123', 'owner/repo', 'Test Workflow')
    database.insert_run(
        '456', '123', 1, 'abc', 'main', 'push', 'completed', 'success',
        '2025-01-01 10:00:00', '2025-01-01 10:05:00', 300, 'user1', 'url1'
    )

    # Attempt SQL injection via limit parameter
    # Should raise ValueError when trying to convert malicious string to int
    with pytest.raises(ValueError):
        runs = database.get_runs(limit="1; DROP TABLE runs; --")

    # Verify table still exists (injection was prevented)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert cursor.fetchone() is not None
    conn.close()

    # Normal usage should work
    runs = database.get_runs(limit=1)
    assert len(runs) == 1


def test_metrics_cache_table_creation(test_db):
    """Test that metrics_cache table is created during initialization."""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Check metrics_cache table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics_cache'")
    assert cursor.fetchone() is not None

    # Check index exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_metrics_cache_lookup'")
    assert cursor.fetchone() is not None

    conn.close()


def test_save_and_get_cached_metrics(test_db):
    """Test saving and retrieving cached metrics."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Save metrics cache
    database.save_metrics_cache(
        repository='owner/repo',
        workflow_id=None,
        period_days=7,
        mttr_seconds=1200.5,
        success_rate=85.5,
        avg_duration_seconds=300.0,
        total_runs=10,
        success_count=8,
        failure_count=2
    )

    # Retrieve cached metrics
    cached = database.get_cached_metrics(repository='owner/repo', workflow_id=None, period_days=7)

    assert cached is not None
    assert len(cached) == 1
    assert cached[0]['repository'] == 'owner/repo'
    assert cached[0]['workflow_id'] is None
    assert cached[0]['period_days'] == 7
    assert cached[0]['mttr_seconds'] == 1200.5
    assert cached[0]['success_rate'] == 85.5
    assert cached[0]['avg_duration_seconds'] == 300.0
    assert cached[0]['total_runs'] == 10
    assert cached[0]['success_count'] == 8
    assert cached[0]['failure_count'] == 2


def test_metrics_cache_upsert(test_db):
    """Test that metrics cache properly updates on conflict (UPSERT)."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Initial save
    database.save_metrics_cache(
        repository='owner/repo',
        workflow_id=None,
        period_days=30,
        mttr_seconds=1000.0,
        success_rate=80.0,
        avg_duration_seconds=250.0,
        total_runs=5,
        success_count=4,
        failure_count=1
    )

    # Update with same key (repository + workflow_id + period_days)
    database.save_metrics_cache(
        repository='owner/repo',
        workflow_id=None,
        period_days=30,
        mttr_seconds=1500.0,
        success_rate=90.0,
        avg_duration_seconds=280.0,
        total_runs=10,
        success_count=9,
        failure_count=1
    )

    # Verify only one record exists with updated values
    cached = database.get_cached_metrics(repository='owner/repo', workflow_id=None, period_days=30)

    assert cached is not None
    assert len(cached) == 1
    assert cached[0]['mttr_seconds'] == 1500.0
    assert cached[0]['success_rate'] == 90.0
    assert cached[0]['total_runs'] == 10


def test_calculate_and_cache_all_metrics(test_db):
    """Test calculating and caching metrics for all repositories and periods."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Setup test data
    database.insert_workflow('123', 'owner/repo1', 'Workflow 1')
    database.insert_workflow('124', 'owner/repo2', 'Workflow 2')

    runs_data = [
        # repo1: 2 successes, 1 failure
        ('456', '123', 1, 'abc', 'main', 'push', 'completed', 'success',
         '2025-01-01 10:00:00', '2025-01-01 10:05:00', 300, 'user1', 'url1'),
        ('457', '123', 2, 'def', 'main', 'push', 'completed', 'failure',
         '2025-01-05 10:00:00', '2025-01-05 10:03:00', 180, 'user2', 'url2'),
        ('458', '123', 3, 'ghi', 'main', 'push', 'completed', 'success',
         '2025-01-05 10:10:00', '2025-01-05 10:14:00', 240, 'user3', 'url3'),
        # repo2: 1 success
        ('459', '124', 1, 'jkl', 'main', 'push', 'completed', 'success',
         '2025-01-02 12:00:00', '2025-01-02 12:05:00', 300, 'user4', 'url4'),
    ]
    database.insert_runs_batch(runs_data)

    # Calculate and cache all metrics
    cached_count = database.calculate_and_cache_all_metrics()

    # Verify caching worked
    assert cached_count > 0

    # Check repository-level cache for repo1 (all time)
    cached = database.get_cached_metrics(repository='owner/repo1', workflow_id=None, period_days=None)
    assert cached is not None
    assert len(cached) == 1
    assert cached[0]['total_runs'] == 3
    assert cached[0]['success_count'] == 2
    assert cached[0]['failure_count'] == 1
    # MTTR: failure at 10:03 → success at 10:14 = 11 minutes = 660 seconds
    assert cached[0]['mttr_seconds'] == 660.0

    # Check workflow-level cache exists
    cached_wf = database.get_cached_metrics(repository='owner/repo1', workflow_id='123', period_days=None)
    assert cached_wf is not None
    assert len(cached_wf) == 1

    # Note: Period-specific cache (7, 30, 90 days) won't be created
    # because test data is from 2025-01-01, which is outside these periods
    # The calculate_and_cache_all_metrics() only creates cache when there's data


def test_get_cached_metrics_filters(test_db):
    """Test getting cached metrics with various filters."""
    from cipette import database
    database.DATABASE_PATH = test_db

    # Setup multiple cache entries
    database.save_metrics_cache(
        repository='owner/repo1', workflow_id=None, period_days=7,
        mttr_seconds=1000.0, success_rate=80.0, avg_duration_seconds=250.0,
        total_runs=5, success_count=4, failure_count=1
    )
    database.save_metrics_cache(
        repository='owner/repo1', workflow_id=None, period_days=30,
        mttr_seconds=1100.0, success_rate=85.0, avg_duration_seconds=260.0,
        total_runs=10, success_count=8, failure_count=2
    )
    database.save_metrics_cache(
        repository='owner/repo1', workflow_id='123', period_days=7,
        mttr_seconds=1200.0, success_rate=90.0, avg_duration_seconds=270.0,
        total_runs=3, success_count=3, failure_count=0
    )
    database.save_metrics_cache(
        repository='owner/repo2', workflow_id=None, period_days=7,
        mttr_seconds=1300.0, success_rate=70.0, avg_duration_seconds=280.0,
        total_runs=8, success_count=5, failure_count=3
    )

    # Test: Get all cached metrics (no filters)
    all_cached = database.get_cached_metrics()
    assert all_cached is not None
    assert len(all_cached) == 4

    # Test: Filter by repository only
    repo1_cached = database.get_cached_metrics(repository='owner/repo1')
    assert len(repo1_cached) == 3

    # Test: Filter by repository and workflow_id=None (repository-level)
    repo1_repo_level = database.get_cached_metrics(repository='owner/repo1', workflow_id=None)
    assert len(repo1_repo_level) == 2  # 7 and 30 days

    # Test: Filter by repository and specific workflow_id
    repo1_wf123 = database.get_cached_metrics(repository='owner/repo1', workflow_id='123')
    assert len(repo1_wf123) == 1
    assert repo1_wf123[0]['workflow_id'] == '123'

    # Test: Filter by period_days
    all_7day = database.get_cached_metrics(period_days=7)
    assert len(all_7day) == 3  # repo1 (repo-level), repo1 (wf123), repo2 (repo-level)
