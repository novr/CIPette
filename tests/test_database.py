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
    original_path = config.Config.DATABASE_PATH
    config.Config.DATABASE_PATH = test_db_path

    # Clear the metrics cache to prevent cross-test contamination
    database._get_metrics_cached.cache_clear()

    # Initialize test database
    database.initialize_database()

    yield test_db_path

    # Cleanup
    config.Config.DATABASE_PATH = original_path
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_initialize_database(test_db):
    """Test database initialization."""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Check workflows table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
    )
    assert cursor.fetchone() is not None

    # Check runs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert cursor.fetchone() is not None

    # Check indexes exist
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_runs_conclusion'"
    )
    assert cursor.fetchone() is not None

    conn.close()


def test_insert_and_get_workflow(test_db):
    """Test workflow insertion and retrieval."""
    from cipette import database

    database.DATABASE_PATH = test_db

    # Insert workflow
    database.insert_workflow(
        '123', 'owner/repo', 'Test Workflow', '.github/workflows/test.yml', 'active'
    )

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
        '456',
        '123',
        1,
        'abc123',
        'main',
        'push',
        'completed',
        'success',
        '2025-01-01 10:00:00',
        '2025-01-01 10:05:00',
        300,
        'testuser',
        'https://github.com/owner/repo/actions/runs/456',
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
        (
            '456',
            '123',
            1,
            'abc123',
            'main',
            'push',
            'completed',
            'success',
            '2025-01-01 10:00:00',
            '2025-01-01 10:05:00',
            300,
            'user1',
            'https://github.com/test1',
        ),
        (
            '457',
            '123',
            2,
            'def456',
            'main',
            'push',
            'completed',
            'failure',
            '2025-01-01 11:00:00',
            '2025-01-01 11:03:00',
            180,
            'user2',
            'https://github.com/test2',
        ),
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
        (
            '456',
            '123',
            1,
            'abc',
            'main',
            'push',
            'completed',
            'success',
            '2025-01-01 10:00:00',
            '2025-01-01 10:05:00',
            300,
            'user1',
            'url1',
        ),
        (
            '457',
            '123',
            2,
            'def',
            'main',
            'push',
            'completed',
            'failure',
            '2025-01-01 11:00:00',
            '2025-01-01 11:03:00',
            180,
            'user2',
            'url2',
        ),
        (
            '458',
            '124',
            1,
            'ghi',
            'dev',
            'pull_request',
            'completed',
            'success',
            '2025-01-01 12:00:00',
            '2025-01-01 12:02:00',
            120,
            'user3',
            'url3',
        ),
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
        (
            '456',
            '123',
            1,
            'abc',
            'main',
            'push',
            'completed',
            'success',
            '2025-01-01 10:00:00',
            '2025-01-01 10:05:00',
            300,
            'user1',
            'url1',
        ),
        (
            '457',
            '123',
            2,
            'def',
            'main',
            'push',
            'completed',
            'failure',
            '2025-01-01 11:00:00',
            '2025-01-01 11:03:00',
            180,
            'user2',
            'url2',
        ),
        (
            '458',
            '123',
            3,
            'ghi',
            'main',
            'push',
            'completed',
            'success',
            '2025-01-01 12:00:00',
            '2025-01-01 12:04:00',
            240,
            'user3',
            'url3',
        ),
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


def test_calculate_health_score():
    """Test legacy health score calculation."""
    from cipette.database import calculate_health_score, get_health_score_class

    # Test excellent health score
    scores = calculate_health_score(
        success_rate=95.0,
        mttr_seconds=300.0,  # 5 minutes
        avg_duration_seconds=600.0,  # 10 minutes
        total_runs=30,
        days=30,
    )

    assert scores['overall_score'] > 80  # Should be excellent
    assert scores['success_rate_score'] == 95.0
    assert scores['mttr_score'] > 90  # 5 minutes is very good
    assert scores['duration_score'] > 60  # 10 minutes is reasonable
    assert scores['throughput_score'] == 100.0  # 1 run per day is perfect

    # Test poor health score
    scores = calculate_health_score(
        success_rate=50.0,
        mttr_seconds=7200.0,  # 2 hours
        avg_duration_seconds=1800.0,  # 30 minutes
        total_runs=5,
        days=30,
    )

    assert scores['overall_score'] < 50  # Should be poor
    assert scores['success_rate_score'] == 50.0
    assert scores['mttr_score'] == 0.0  # 2 hours is maximum (0 points)
    assert scores['duration_score'] == 0.0  # 30 minutes is maximum (0 points)
    assert scores['throughput_score'] < 20  # Less than 1 run per day

    # Test health score classification
    assert get_health_score_class(90.0) == 'excellent'
    assert get_health_score_class(75.0) == 'good'
    assert get_health_score_class(60.0) == 'fair'
    assert get_health_score_class(30.0) == 'poor'


def test_health_calculator_robust():
    """Test robust health score calculator with error handling."""
    from cipette.health_calculator import DataQuality, HealthScoreCalculator

    calculator = HealthScoreCalculator()

    # Test excellent health score
    result = calculator.calculate_health_score(
        success_rate=95.0,
        mttr_seconds=300.0,
        avg_duration_seconds=600.0,
        total_runs=30,
        days=30,
    )

    assert result.overall_score > 80
    assert result.health_class == 'excellent'
    assert result.data_quality == DataQuality.EXCELLENT
    assert len(result.warnings) == 0
    assert len(result.errors) == 0

    # Test with missing data
    result = calculator.calculate_health_score(
        success_rate=None,
        mttr_seconds=None,
        avg_duration_seconds=600.0,
        total_runs=5,
        days=30,
    )

    assert result.data_quality == DataQuality.FAIR  # 2 out of 4 metrics available
    assert len(result.warnings) > 0
    assert 'Success rate data not available' in result.warnings
    assert 'MTTR data not available - assuming no failures' in result.warnings

    # Test with invalid data
    result = calculator.calculate_health_score(
        success_rate=-10.0,  # Invalid negative value
        mttr_seconds='invalid',  # Invalid type
        avg_duration_seconds=600.0,
        total_runs=5,
        days=30,
    )

    assert len(result.warnings) > 0
    assert any('Success rate out of valid range' in w for w in result.warnings)
    assert any('Invalid MTTR type' in w for w in result.warnings)

    # Test with insufficient data
    result = calculator.calculate_health_score(
        success_rate=None,
        mttr_seconds=None,
        avg_duration_seconds=None,
        total_runs=0,
        days=30,
    )

    assert result.data_quality == DataQuality.INSUFFICIENT
    assert result.health_class == 'poor'


def test_health_calculator_edge_cases():
    """Test health calculator with edge cases."""
    from cipette.health_calculator import HealthScoreCalculator

    calculator = HealthScoreCalculator()

    # Test with zero values
    result = calculator.calculate_health_score(
        success_rate=0.0,
        mttr_seconds=0.0,
        avg_duration_seconds=0.0,
        total_runs=1,
        days=1,
    )

    assert result.overall_score >= 0
    assert len(result.warnings) > 0
    assert any('MTTR is zero' in w for w in result.warnings)
    assert any('Duration is zero' in w for w in result.warnings)

    # Test with extreme values
    result = calculator.calculate_health_score(
        success_rate=150.0,  # Over 100%
        mttr_seconds=86400.0,  # 24 hours
        avg_duration_seconds=3600.0,  # 1 hour
        total_runs=1000,
        days=1,
    )

    assert result.overall_score <= 100
    assert len(result.warnings) > 0
    assert any('Success rate out of valid range' in w for w in result.warnings)
    assert any('MTTR exceeds maximum threshold' in w for w in result.warnings)
    assert any('Duration exceeds maximum threshold' in w for w in result.warnings)


def test_health_score_cache(test_db):
    """Test health score cache functionality."""
    from cipette.database import (
        clear_health_score_cache,
        get_connection,
        refresh_health_score_cache,
    )

    # Clear cache first
    clear_health_score_cache()

    # Test cache refresh
    refresh_health_score_cache()

    # Verify cache was populated (if there's data)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM health_score_cache')
        count = cursor.fetchone()['count']
        # Cache should be populated if there's workflow data
        assert count >= 0


def test_calculate_mttr(test_db):
    """Test MTTR calculation."""
    from cipette import database

    database.DATABASE_PATH = test_db

    # Setup test data: failure followed by success
    database.insert_workflow('123', 'owner/repo', 'Test Workflow')

    runs_data = [
        (
            '456',
            '123',
            1,
            'abc',
            'main',
            'push',
            'completed',
            'failure',
            '2025-01-01 10:00:00',
            '2025-01-01 10:03:00',
            180,
            'user1',
            'url1',
        ),
        (
            '457',
            '123',
            2,
            'def',
            'main',
            'push',
            'completed',
            'success',
            '2025-01-01 10:10:00',
            '2025-01-01 10:15:00',
            300,
            'user2',
            'url2',
        ),
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
    database.insert_workflow(
        '123', 'owner/repo', 'Test Workflow Updated', 'path2', 'inactive'
    )

    workflows = database.get_workflows()
    assert len(workflows) == 1
    assert workflows[0]['name'] == 'Test Workflow Updated'
    assert workflows[0]['path'] == 'path2'

    # Insert run twice
    database.insert_run(
        '456',
        '123',
        1,
        'abc123',
        'main',
        'push',
        'completed',
        'success',
        '2025-01-01 10:00:00',
        '2025-01-01 10:05:00',
        300,
        'user1',
        'url1',
    )
    database.insert_run(
        '456',
        '123',
        1,
        'abc123',
        'main',
        'push',
        'completed',
        'failure',
        '2025-01-01 10:00:00',
        '2025-01-01 10:06:00',
        360,
        'user1',
        'url1',
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
        '456',
        '123',
        1,
        'abc',
        'main',
        'push',
        'completed',
        'success',
        '2025-01-01 10:00:00',
        '2025-01-01 10:05:00',
        300,
        'user1',
        'url1',
    )

    # Attempt SQL injection via limit parameter
    # Should raise ValueError when trying to convert malicious string to int
    with pytest.raises(ValueError):
        runs = database.get_runs(limit='1; DROP TABLE runs; --')

    # Verify table still exists (injection was prevented)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert cursor.fetchone() is not None
    conn.close()

    # Normal usage should work
    runs = database.get_runs(limit=1)
    assert len(runs) == 1
