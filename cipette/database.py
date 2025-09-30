import logging
import sqlite3
from datetime import datetime

from cipette.config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection():
    """Create and return a database connection with context manager support.

    Returns:
        sqlite3.Connection: Database connection that can be used as context manager

    Example:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workflows")
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def initialize_database():
    """Create database tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Workflows table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            repository TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT,
            state TEXT
        )
    ''')

    # Workflow runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            run_number INTEGER,
            commit_sha TEXT,
            branch TEXT,
            event TEXT,
            status TEXT NOT NULL,
            conclusion TEXT,
            started_at DATETIME,
            completed_at DATETIME,
            duration_seconds INTEGER,
            actor TEXT,
            url TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows (id)
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_workflow_id
        ON runs (workflow_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_status
        ON runs (status)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_completed_at
        ON runs (completed_at)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_repository
        ON runs (workflow_id, started_at)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_conclusion
        ON runs (conclusion)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_branch
        ON runs (branch)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_runs_event
        ON runs (event)
    ''')

    # Metrics cache table for pre-calculated metrics (MTTR, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            workflow_id TEXT,
            period_days INTEGER,
            calculated_at DATETIME NOT NULL,
            mttr_seconds REAL,
            success_rate REAL,
            avg_duration_seconds REAL,
            total_runs INTEGER,
            success_count INTEGER,
            failure_count INTEGER,
            UNIQUE(repository, workflow_id, period_days)
        )
    ''')

    # Index for fast lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_metrics_cache_lookup
        ON metrics_cache (repository, workflow_id, period_days)
    ''')

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")


def insert_workflow(workflow_id, repository, name, path=None, state=None, conn=None):
    """Insert or update a workflow record with idempotency.

    Args:
        workflow_id: Workflow ID
        repository: Repository name
        name: Workflow name
        path: Workflow file path
        state: Workflow state
        conn: Optional database connection (for batch operations)
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO workflows (id, repository, name, path, state)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            repository = excluded.repository,
            name = excluded.name,
            path = excluded.path,
            state = excluded.state
    ''', (workflow_id, repository, name, path, state))

    if should_close:
        conn.commit()
        conn.close()


def insert_run(run_id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
               started_at, completed_at, duration_seconds, actor, url):
    """Insert or update a workflow run record with idempotency."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO runs
        (id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
         started_at, completed_at, duration_seconds, actor, url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            workflow_id = excluded.workflow_id,
            run_number = excluded.run_number,
            commit_sha = excluded.commit_sha,
            branch = excluded.branch,
            event = excluded.event,
            status = excluded.status,
            conclusion = excluded.conclusion,
            started_at = excluded.started_at,
            completed_at = excluded.completed_at,
            duration_seconds = excluded.duration_seconds,
            actor = excluded.actor,
            url = excluded.url
    ''', (run_id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
          started_at, completed_at, duration_seconds, actor, url))

    conn.commit()
    conn.close()


def insert_runs_batch(runs_data, conn=None):
    """Insert or update multiple workflow run records in a single transaction with idempotency.

    Args:
        runs_data: List of tuples with format:
            (id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
             started_at, completed_at, duration_seconds, actor, url)
        conn: Optional database connection (for batch operations)

    Raises:
        sqlite3.Error: If database operation fails
    """
    if not runs_data:
        return

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()

    try:
        # Use executemany for better performance with ON CONFLICT for upsert
        cursor.executemany('''
            INSERT INTO runs
            (id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
             started_at, completed_at, duration_seconds, actor, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                workflow_id = excluded.workflow_id,
                run_number = excluded.run_number,
                commit_sha = excluded.commit_sha,
                branch = excluded.branch,
                event = excluded.event,
                status = excluded.status,
                conclusion = excluded.conclusion,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                duration_seconds = excluded.duration_seconds,
                actor = excluded.actor,
                url = excluded.url
        ''', runs_data)

        if should_close:
            conn.commit()
    except Exception:
        if should_close:
            conn.rollback()
        # Re-raise exception to notify caller
        raise
    finally:
        if should_close:
            conn.close()


def get_workflows():
    """Retrieve all workflows."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM workflows ORDER BY repository, name')
    workflows = cursor.fetchall()

    conn.close()
    return workflows


def get_runs(workflow_id=None, limit=None, repository=None, status=None, conclusion=None):
    """Retrieve workflow runs with various filters.

    Args:
        workflow_id: Filter by workflow ID
        limit: Maximum number of results
        repository: Filter by repository name
        status: Filter by status (completed, in_progress, etc.)
        conclusion: Filter by conclusion (success, failure, etc.)
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT r.* FROM runs r'
    conditions = []
    params = []

    # Join with workflows if filtering by repository
    if repository:
        query += ' JOIN workflows w ON r.workflow_id = w.id'
        conditions.append('w.repository = ?')
        params.append(repository)

    if workflow_id:
        conditions.append('r.workflow_id = ?')
        params.append(workflow_id)

    if status:
        conditions.append('r.status = ?')
        params.append(status)

    if conclusion:
        conditions.append('r.conclusion = ?')
        params.append(conclusion)

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    query += ' ORDER BY r.started_at DESC'

    if limit:
        query += ' LIMIT ?'
        params.append(int(limit))

    cursor.execute(query, params)
    runs = cursor.fetchall()

    conn.close()
    return runs


def get_metrics_by_repository(repository=None, days=None):
    """Calculate CI/CD metrics for repositories.

    Args:
        repository: Filter by specific repository (None for all)
        days: Only include runs from last N days (None for all time)

    Returns:
        List of dicts with metrics for each repository/workflow combination
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Build query with parameterized filters
    conditions = ["r.status = 'completed'"]
    params = []

    if days:
        conditions.append("r.started_at >= datetime('now', '-' || ? || ' days')")
        params.append(int(days))

    if repository:
        conditions.append("w.repository = ?")
        params.append(repository)

    where_clause = " AND ".join(conditions)

    query = f'''
        SELECT
            w.repository,
            w.name as workflow_name,
            w.id as workflow_id,
            COUNT(*) as total_runs,
            COUNT(CASE WHEN r.conclusion = 'success' THEN 1 END) as success_count,
            COUNT(CASE WHEN r.conclusion = 'failure' THEN 1 END) as failure_count,
            ROUND(AVG(r.duration_seconds), 2) as avg_duration_seconds,
            ROUND(
                CAST(COUNT(CASE WHEN r.conclusion = 'success' THEN 1 END) AS FLOAT) /
                NULLIF(COUNT(CASE WHEN r.conclusion IN ('success', 'failure') THEN 1 END), 0) * 100,
                2
            ) as success_rate,
            MIN(r.started_at) as first_run,
            MAX(r.started_at) as last_run
        FROM workflows w
        LEFT JOIN runs r ON w.id = r.workflow_id
        WHERE {where_clause}
        GROUP BY w.repository, w.name, w.id
        ORDER BY w.repository, w.name
    '''

    cursor.execute(query, params)
    rows = cursor.fetchall()

    metrics = []
    for row in rows:
        metrics.append({
            'repository': row['repository'],
            'workflow_name': row['workflow_name'],
            'workflow_id': row['workflow_id'],
            'total_runs': row['total_runs'],
            'success_count': row['success_count'],
            'failure_count': row['failure_count'],
            'avg_duration_seconds': row['avg_duration_seconds'],
            'success_rate': row['success_rate'],
            'first_run': row['first_run'],
            'last_run': row['last_run']
        })

    conn.close()
    return metrics


def calculate_mttr(workflow_id=None, repository=None, days=None):
    """Calculate Mean Time To Recovery (MTTR).

    MTTR = Average time from a failure completion to the next success completion.

    Args:
        workflow_id: Filter by workflow ID
        repository: Filter by repository
        days: Only include runs from last N days

    Returns:
        Average MTTR in seconds, or None if no data
    """
    conn = get_connection()
    cursor = conn.cursor()

    filters = ["r1.conclusion IN ('success', 'failure')", "r1.status = 'completed'", "r1.completed_at IS NOT NULL"]
    params = []

    if workflow_id:
        filters.append("r1.workflow_id = ?")
        params.append(workflow_id)

    if repository:
        filters.append("w.repository = ?")
        params.append(repository)

    if days:
        filters.append("r1.completed_at >= datetime('now', '-' || ? || ' days')")
        params.append(int(days))

    where_clause = " AND ".join(filters)

    # Need to join workflows for repository filter
    if repository:
        from_clause = "FROM runs r1 JOIN workflows w ON r1.workflow_id = w.id"
    else:
        from_clause = "FROM runs r1"

    query = f'''
        SELECT
            r1.id,
            r1.completed_at as failure_time,
            MIN(r2.completed_at) as recovery_time
        {from_clause}
        LEFT JOIN runs r2 ON
            r2.workflow_id = r1.workflow_id AND
            r2.completed_at > r1.completed_at AND
            r2.conclusion = 'success' AND
            r2.status = 'completed'
        WHERE {where_clause} AND r1.conclusion = 'failure'
        GROUP BY r1.id, r1.completed_at
        HAVING recovery_time IS NOT NULL
    '''

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return None

    # Calculate average time to recovery
    total_seconds = 0
    count = 0

    for row in rows:
        failure_time = datetime.strptime(row['failure_time'], '%Y-%m-%d %H:%M:%S')
        recovery_time = datetime.strptime(row['recovery_time'], '%Y-%m-%d %H:%M:%S')
        delta = (recovery_time - failure_time).total_seconds()
        total_seconds += delta
        count += 1

    conn.close()
    return round(total_seconds / count, 2) if count > 0 else None


def save_metrics_cache(repository, workflow_id, period_days, mttr_seconds, success_rate,
                       avg_duration_seconds, total_runs, success_count, failure_count):
    """Save or update metrics cache.

    Args:
        repository: Repository name
        workflow_id: Workflow ID (None for repository-level metrics)
        period_days: Number of days (None for all time)
        mttr_seconds: Mean Time To Recovery in seconds
        success_rate: Success rate percentage
        avg_duration_seconds: Average duration in seconds
        total_runs: Total number of runs
        success_count: Number of successful runs
        failure_count: Number of failed runs
    """
    conn = get_connection()
    cursor = conn.cursor()

    # SQLite's ON CONFLICT doesn't work well with NULL in UNIQUE constraints
    # Use explicit DELETE + INSERT instead
    # Delete existing record with same keys (handling NULL properly)
    if workflow_id is None and period_days is None:
        cursor.execute('''
            DELETE FROM metrics_cache
            WHERE repository = ? AND workflow_id IS NULL AND period_days IS NULL
        ''', (repository,))
    elif workflow_id is None:
        cursor.execute('''
            DELETE FROM metrics_cache
            WHERE repository = ? AND workflow_id IS NULL AND period_days = ?
        ''', (repository, period_days))
    elif period_days is None:
        cursor.execute('''
            DELETE FROM metrics_cache
            WHERE repository = ? AND workflow_id = ? AND period_days IS NULL
        ''', (repository, workflow_id))
    else:
        cursor.execute('''
            DELETE FROM metrics_cache
            WHERE repository = ? AND workflow_id = ? AND period_days = ?
        ''', (repository, workflow_id, period_days))

    # Insert new record
    cursor.execute('''
        INSERT INTO metrics_cache
        (repository, workflow_id, period_days, calculated_at,
         mttr_seconds, success_rate, avg_duration_seconds,
         total_runs, success_count, failure_count)
        VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?)
    ''', (repository, workflow_id, period_days, mttr_seconds, success_rate,
          avg_duration_seconds, total_runs, success_count, failure_count))

    conn.commit()
    conn.close()


# Sentinel value to distinguish between "not provided" and "None"
_UNSET = object()


def get_cached_metrics(repository=None, workflow_id=_UNSET, period_days=_UNSET):
    """Retrieve cached metrics.

    Args:
        repository: Repository name (None for all repositories)
        workflow_id: Workflow ID, or None for repository-level metrics, or omit to get all
        period_days: Number of days, or None for all time, or omit to get all periods

    Returns:
        List of cached metrics dictionaries, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if repository:
        conditions.append('repository = ?')
        params.append(repository)

    # Only filter by workflow_id if explicitly provided (including None)
    if workflow_id is not _UNSET:
        if workflow_id is None:
            conditions.append('workflow_id IS NULL')
        else:
            conditions.append('workflow_id = ?')
            params.append(workflow_id)

    # Only filter by period_days if explicitly provided (including None)
    if period_days is not _UNSET:
        if period_days is None:
            conditions.append('period_days IS NULL')
        else:
            conditions.append('period_days = ?')
            params.append(period_days)

    query = 'SELECT * FROM metrics_cache'
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY repository, workflow_id, period_days'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    metrics = []
    for row in rows:
        metrics.append({
            'repository': row['repository'],
            'workflow_id': row['workflow_id'],
            'period_days': row['period_days'],
            'calculated_at': row['calculated_at'],
            'mttr_seconds': row['mttr_seconds'],
            'success_rate': row['success_rate'],
            'avg_duration_seconds': row['avg_duration_seconds'],
            'total_runs': row['total_runs'],
            'success_count': row['success_count'],
            'failure_count': row['failure_count']
        })

    conn.close()
    return metrics if metrics else None


def calculate_and_cache_all_metrics():
    """Calculate and cache metrics for all repositories and time periods.

    This function calculates metrics for:
    - All time (period_days=None)
    - Last 7 days (period_days=7)
    - Last 30 days (period_days=30)
    - Last 90 days (period_days=90)

    Both repository-level and workflow-level metrics are calculated.
    """
    logger.info("Starting metrics calculation and caching...")

    # Get all repositories
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT repository FROM workflows')
    repositories = [row['repository'] for row in cursor.fetchall()]
    conn.close()

    periods = [None, 7, 30, 90]
    total_cached = 0

    for repo in repositories:
        logger.info(f"Processing repository: {repo}")

        for period in periods:
            period_label = f"{period} days" if period else "all time"

            # Repository-level metrics (aggregated across all workflows)
            metrics_list = get_metrics_by_repository(repository=repo, days=period)
            if metrics_list:
                # Aggregate metrics across workflows
                total_runs = sum(m['total_runs'] for m in metrics_list)
                success_count = sum(m['success_count'] for m in metrics_list)
                failure_count = sum(m['failure_count'] for m in metrics_list)

                # Calculate success rate
                if success_count + failure_count > 0:
                    success_rate = round((success_count / (success_count + failure_count)) * 100, 2)
                else:
                    success_rate = None

                # Calculate average duration (weighted by number of runs)
                total_duration = sum(m['avg_duration_seconds'] * m['total_runs'] for m in metrics_list
                                     if m['avg_duration_seconds'] is not None)
                avg_duration = round(total_duration / total_runs, 2) if total_runs > 0 else None

                # Calculate MTTR for repository
                mttr = calculate_mttr(repository=repo, days=period)

                # Save repository-level cache
                save_metrics_cache(
                    repository=repo,
                    workflow_id=None,
                    period_days=period,
                    mttr_seconds=mttr,
                    success_rate=success_rate,
                    avg_duration_seconds=avg_duration,
                    total_runs=total_runs,
                    success_count=success_count,
                    failure_count=failure_count
                )
                total_cached += 1
                logger.info(f"  Cached repository-level metrics for {period_label}")

                # Workflow-level metrics
                for workflow_metrics in metrics_list:
                    workflow_id = workflow_metrics['workflow_id']
                    mttr_wf = calculate_mttr(workflow_id=workflow_id, days=period)

                    save_metrics_cache(
                        repository=repo,
                        workflow_id=workflow_id,
                        period_days=period,
                        mttr_seconds=mttr_wf,
                        success_rate=workflow_metrics['success_rate'],
                        avg_duration_seconds=workflow_metrics['avg_duration_seconds'],
                        total_runs=workflow_metrics['total_runs'],
                        success_count=workflow_metrics['success_count'],
                        failure_count=workflow_metrics['failure_count']
                    )
                    total_cached += 1

                logger.info(f"  Cached {len(metrics_list)} workflow-level metrics for {period_label}")

    logger.info(f"Metrics caching complete. Total entries cached: {total_cached}")
    return total_cached


if __name__ == '__main__':
    # Initialize database when run directly
    initialize_database()
