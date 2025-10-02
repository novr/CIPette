import logging
import sqlite3
import time
from datetime import datetime
from functools import lru_cache

from cipette.config import DATABASE_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('data/database.log'),
        logging.StreamHandler()
    ]
)

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
    conn = sqlite3.connect(DATABASE_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30秒のビジータイムアウト
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=10000")
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

    # Metrics view for real-time calculation
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS workflow_metrics_view AS
        SELECT
            w.repository,
            w.id as workflow_id,
            w.name as workflow_name,
            COUNT(*) as total_runs,
            SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN r.conclusion = 'failure' THEN 1 ELSE 0 END) as failure_count,
            ROUND(AVG(r.duration_seconds), 2) as avg_duration_seconds,
            ROUND(
                CAST(SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) AS FLOAT) /
                NULLIF(SUM(CASE WHEN r.conclusion IN ('success', 'failure') THEN 1 ELSE 0 END), 0) * 100,
                2
            ) as success_rate,
            MIN(r.started_at) as first_run,
            MAX(r.started_at) as last_run
        FROM workflows w
        LEFT JOIN runs r ON w.id = r.workflow_id
        WHERE r.status = 'completed'
        GROUP BY w.repository, w.id, w.name
    ''')

    # MTTR view for real-time calculation
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS mttr_view AS
        SELECT
            r1.workflow_id,
            ROUND(AVG(
                (julianday(r2.completed_at) - julianday(r1.completed_at)) * 86400
            ), 2) as mttr_seconds
        FROM runs r1
        LEFT JOIN runs r2 ON
            r2.workflow_id = r1.workflow_id AND
            r2.completed_at > r1.completed_at AND
            r2.conclusion = 'success' AND
            r2.status = 'completed'
        WHERE r1.conclusion = 'failure'
            AND r1.status = 'completed'
            AND r2.completed_at IS NOT NULL
        GROUP BY r1.workflow_id
    ''')

    # MTTR cache table for background job computation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mttr_cache (
            workflow_id TEXT PRIMARY KEY,
            mttr_seconds REAL,
            sample_size INTEGER,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows (id)
        )
    ''')

    # Index for cache staleness checks
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_mttr_cache_calculated
        ON mttr_cache (calculated_at)
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
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
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying in {2 ** attempt} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                if should_close:
                    conn.rollback()
                raise
        except Exception as e:
            if should_close:
                conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()
    
    return False


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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
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
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying in {2 ** attempt} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                if should_close:
                    conn.rollback()
                raise
        except Exception as e:
            if should_close:
                conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()
    
    return False


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


def _build_metrics_query(repository=None, days=None):
    """Build unified metrics query with optional filters.

    Args:
        repository: Filter by repository name (None for all)
        days: Filter by last N days (None for all time)

    Returns:
        Tuple of (query_string, params_list)
    """
    # Common metric aggregations (avoid duplication)
    metrics_select = '''
        COUNT(*) as total_runs,
        SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN r.conclusion = 'failure' THEN 1 ELSE 0 END) as failure_count,
        ROUND(AVG(r.duration_seconds), 2) as avg_duration_seconds,
        ROUND(
            CAST(SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) AS FLOAT) /
            NULLIF(SUM(CASE WHEN r.conclusion IN ('success', 'failure') THEN 1 ELSE 0 END), 0) * 100,
            2
        ) as success_rate,
        MIN(r.started_at) as first_run,
        MAX(r.started_at) as last_run
    '''

    # MTTR: Use cache for all-time, compute for period-filtered queries
    if days:
        # Period-filtered: Compute MTTR with subquery (slower but accurate)
        mttr_select = '''
            (
                SELECT ROUND(AVG((julianday(r2.completed_at) - julianday(r1.completed_at)) * 86400), 2)
                FROM runs r1
                LEFT JOIN runs r2 ON
                    r2.workflow_id = r1.workflow_id AND
                    r2.completed_at > r1.completed_at AND
                    r2.conclusion = 'success' AND
                    r2.status = 'completed'
                WHERE r1.workflow_id = w.id
                    AND r1.conclusion = 'failure'
                    AND r1.status = 'completed'
                    AND r2.completed_at IS NOT NULL
                    AND r1.started_at >= datetime('now', '-' || ? || ' days')
            ) as mttr_seconds
        '''
    else:
        # All-time: Use pre-computed cache (fast)
        mttr_select = 'c.mttr_seconds'

    # Build WHERE conditions
    where_conditions = ["r.status = 'completed'"]
    params = []

    if days:
        where_conditions.append("r.started_at >= datetime('now', '-' || ? || ' days')")
        params.append(days)
        params.append(days)  # For MTTR subquery

    if repository:
        where_conditions.append("w.repository = ?")
        params.append(repository)

    where_clause = " AND ".join(where_conditions)

    # Build JOIN clause (add mttr_cache for all-time queries)
    if days:
        # Period-filtered: No cache join needed
        joins = 'LEFT JOIN runs r ON w.id = r.workflow_id'
    else:
        # All-time: Join with cache table
        joins = '''
            LEFT JOIN runs r ON w.id = r.workflow_id
            LEFT JOIN mttr_cache c ON w.id = c.workflow_id
        '''

    # Unified query for all cases
    query = f'''
        SELECT
            w.repository,
            w.name as workflow_name,
            w.id as workflow_id,
            {metrics_select},
            {mttr_select}
        FROM workflows w
        {joins}
        WHERE {where_clause}
        GROUP BY w.repository, w.id, w.name
        ORDER BY w.repository, w.name
    '''

    return query, params


# Internal function with TTL-based caching
@lru_cache(maxsize=128)
def _get_metrics_cached(repository, days, cache_key):
    """Internal cached version of metrics retrieval.

    Args:
        repository: Repository name (or None)
        days: Number of days (or None)
        cache_key: Timestamp for cache invalidation (minutes)

    Returns:
        Tuple of metric dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Build unified query (eliminates code duplication)
    query, params = _build_metrics_query(repository=repository, days=days)

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
            'last_run': row['last_run'],
            'mttr_seconds': row['mttr_seconds']
        })

    conn.close()
    # Return as tuple for lru_cache (lists are not hashable)
    return tuple(tuple(m.items()) for m in metrics)


def get_metrics_by_repository(repository=None, days=None):
    """Get CI/CD metrics from view with MTTR (cached for 1 minute).

    Args:
        repository: Filter by specific repository (None for all)
        days: Only include runs from last N days (None for all time)

    Returns:
        List of dicts with metrics for each repository/workflow combination
    """
    # Calculate cache key (invalidates every minute)
    cache_key = int(time.time() / 60)

    # Get cached results
    cached_tuples = _get_metrics_cached(repository, days, cache_key)

    # Convert back to list of dicts
    return [dict(items) for items in cached_tuples]


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


def refresh_mttr_cache():
    """Refresh MTTR cache for all workflows (background job).

    This function:
    1. Retrieves all workflows from the database
    2. Calculates MTTR for each workflow
    3. Stores/updates results in mttr_cache table

    Designed to be called by background worker thread.
    """
    logger.info("Starting MTTR cache refresh...")
    start_time = time.time()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get all workflows
        cursor.execute('SELECT id FROM workflows')
        workflows = cursor.fetchall()

        success_count = 0
        error_count = 0

        for workflow in workflows:
            workflow_id = workflow['id']

            try:
                # Calculate MTTR using existing function
                mttr = calculate_mttr(workflow_id=workflow_id)

                if mttr is not None:
                    # Count sample size (number of failures)
                    cursor.execute('''
                        SELECT COUNT(*) as count
                        FROM runs
                        WHERE workflow_id = ?
                            AND conclusion = 'failure'
                            AND status = 'completed'
                    ''', (workflow_id,))
                    sample_size = cursor.fetchone()['count']

                    # Insert or update cache
                    cursor.execute('''
                        INSERT INTO mttr_cache (workflow_id, mttr_seconds, sample_size, calculated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(workflow_id) DO UPDATE SET
                            mttr_seconds = excluded.mttr_seconds,
                            sample_size = excluded.sample_size,
                            calculated_at = excluded.calculated_at
                    ''', (workflow_id, mttr, sample_size))
                    success_count += 1
                else:
                    # No MTTR data (no failures or no recovery) - clear cache entry
                    cursor.execute('DELETE FROM mttr_cache WHERE workflow_id = ?', (workflow_id,))

            except Exception as e:
                logger.error(f"Error calculating MTTR for workflow {workflow_id}: {e}")
                error_count += 1
                continue

        conn.commit()
        elapsed = time.time() - start_time
        logger.info(f"MTTR cache refresh completed: {success_count} updated, {error_count} errors, {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"MTTR cache refresh failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def clear_mttr_cache():
    """Clear all MTTR cache entries.

    Useful for:
    - Manual cache invalidation
    - Testing
    - Forcing full recalculation
    """
    logger.info("Clearing MTTR cache...")
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM mttr_cache')
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(f"MTTR cache cleared: {deleted_count} entries removed")

    finally:
        conn.close()


if __name__ == '__main__':
    # Initialize database when run directly
    initialize_database()
