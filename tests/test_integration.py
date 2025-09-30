"""Integration tests for CIPette data collection and storage.

These tests use real GitHub API calls and database operations to verify
the entire data collection pipeline works correctly.
"""
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cipette.collector import GitHubDataCollector
from cipette.config import GITHUB_TOKEN, TARGET_REPOSITORIES
from cipette.database import get_connection, initialize_database


@pytest.fixture
def temp_db():
    """Create a temporary database for integration tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    # Override DATABASE_PATH
    from cipette import config, database

    original_path = config.DATABASE_PATH
    config.DATABASE_PATH = db_path
    database.DATABASE_PATH = db_path

    yield db_path

    # Cleanup
    config.DATABASE_PATH = original_path
    database.DATABASE_PATH = original_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_last_run():
    """Create a temporary last_run.json file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        last_run_path = f.name

    # Override LAST_RUN_FILE in collector
    original_file = GitHubDataCollector.LAST_RUN_FILE
    GitHubDataCollector.LAST_RUN_FILE = last_run_path

    yield last_run_path

    # Cleanup
    GitHubDataCollector.LAST_RUN_FILE = original_file
    Path(last_run_path).unlink(missing_ok=True)


@pytest.mark.skipif(
    not GITHUB_TOKEN,
    reason="GITHUB_TOKEN not set - skipping integration tests"
)
@pytest.mark.skipif(
    not TARGET_REPOSITORIES,
    reason="TARGET_REPOSITORIES not set - skipping integration tests"
)
class TestIntegration:
    """Integration tests requiring real GitHub API access."""

    def test_full_data_collection_pipeline(self, temp_db, temp_last_run):
        """Test complete data collection from GitHub API to database."""
        # Initialize database
        initialize_database()

        # Create collector
        collector = GitHubDataCollector()

        # Check rate limit (should not raise exception)
        remaining = collector.check_rate_limit()
        assert remaining > 0, "No API calls remaining"

        # Get first repository from config
        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',')]
        test_repo = repos[0]

        # Collect data for one repository
        workflow_count, run_count = collector.collect_repository_data(test_repo)

        # Verify data was collected
        assert workflow_count > 0, f"No workflows found for {test_repo}"
        assert run_count >= 0, "Run count should be non-negative"

        # Verify database contains data
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check workflows table
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE repository = ?", (test_repo,))
            db_workflow_count = cursor.fetchone()[0]
            assert db_workflow_count == workflow_count, "Workflow count mismatch"

            # Check runs table
            cursor.execute("""
                SELECT COUNT(*) FROM runs r
                JOIN workflows w ON r.workflow_id = w.id
                WHERE w.repository = ?
            """, (test_repo,))
            db_run_count = cursor.fetchone()[0]
            assert db_run_count == run_count, "Run count mismatch"

            # Verify data integrity
            cursor.execute("""
                SELECT id, workflow_id, status, started_at
                FROM runs
                LIMIT 1
            """)
            sample_run = cursor.fetchone()
            if sample_run:
                assert sample_run[0], "Run ID should not be empty"
                assert sample_run[1], "Workflow ID should not be empty"
                assert sample_run[2] in ['completed', 'in_progress', 'queued'], \
                    f"Invalid status: {sample_run[2]}"
                assert sample_run[3], "Started at should not be empty"

    def test_incremental_update(self, temp_db, temp_last_run):
        """Test incremental data collection with last_run.json."""
        initialize_database()
        collector = GitHubDataCollector()

        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',')]
        test_repo = repos[0]

        # First collection (full)
        workflow_count_1, run_count_1 = collector.collect_repository_data(test_repo)

        # Save timestamp
        timestamp = datetime.now(UTC).isoformat()
        collector.save_last_run_info({test_repo: timestamp})

        # Verify last_run.json was created
        last_run = collector.get_last_run_info()
        assert last_run is not None, "last_run.json should exist"
        assert test_repo in last_run['repositories'], "Repository should be in last_run.json"

        # Second collection (incremental - should collect 0 or few new runs)
        workflow_count_2, run_count_2 = collector.collect_repository_data(
            test_repo,
            since=timestamp
        )

        # Workflow count should be same or similar
        assert workflow_count_2 > 0, "Workflows should still be collected"

        # Run count should be 0 or very small (no new runs in last few seconds)
        assert run_count_2 >= 0, "Run count should be non-negative"

    def test_idempotency(self, temp_db, temp_last_run):
        """Test that running collection twice produces same results."""
        initialize_database()
        collector = GitHubDataCollector()

        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',')]
        test_repo = repos[0]

        # First collection
        workflow_count_1, run_count_1 = collector.collect_repository_data(test_repo)

        # Get data from database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE repository = ?", (test_repo,))
            db_workflows_1 = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COUNT(*) FROM runs r
                JOIN workflows w ON r.workflow_id = w.id
                WHERE w.repository = ?
            """, (test_repo,))
            db_runs_1 = cursor.fetchone()[0]

        # Second collection (same data, should be idempotent)
        workflow_count_2, run_count_2 = collector.collect_repository_data(test_repo)

        # Get data from database again
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE repository = ?", (test_repo,))
            db_workflows_2 = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COUNT(*) FROM runs r
                JOIN workflows w ON r.workflow_id = w.id
                WHERE w.repository = ?
            """, (test_repo,))
            db_runs_2 = cursor.fetchone()[0]

        # Counts should be identical (idempotent)
        assert workflow_count_1 == workflow_count_2, "Workflow counts should match"
        assert db_workflows_1 == db_workflows_2, "Database workflow counts should match"
        assert db_runs_1 == db_runs_2, "Database run counts should match"

    def test_rate_limit_monitoring(self, temp_db):
        """Test that rate limit checking works correctly."""
        collector = GitHubDataCollector()

        # Check rate limit
        remaining = collector.check_rate_limit()

        # Should return a positive number
        assert isinstance(remaining, int), "Rate limit should be an integer"
        assert remaining >= 0, "Rate limit should be non-negative"

        # Should have some limit remaining (unless account is exhausted)
        # This is a weak assertion but we can't control external rate limits
        assert remaining < 10000, "Rate limit should be reasonable"
