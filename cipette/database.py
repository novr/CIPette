import logging
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache

from cipette.config import Config
from cipette.retry import retry_database_operation

logger = logging.getLogger(__name__)

# Create Config instance for property access
config = Config()


class DatabaseConnection:
    """Database connection wrapper with proper context manager support."""

    def __init__(self, path: str, timeout: float | None = None):
        """Initialize database connection.

        Args:
            path: Database file path
            timeout: Connection timeout in seconds
        """
        self.path = path
        self.timeout = timeout or config.DATABASE_DEFAULT_TIMEOUT
        self.conn = None

    def __enter__(self) -> sqlite3.Connection:
        """Enter context manager and return connection."""
        self.conn = sqlite3.connect(self.path, timeout=self.timeout)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Configure SQLite for better performance and concurrency
        cursor = self.conn.cursor()
        cursor.execute(f'PRAGMA journal_mode = {config.SQLITE_JOURNAL_MODE}')
        cursor.execute(f'PRAGMA synchronous = {config.SQLITE_SYNCHRONOUS}')
        cursor.execute(f'PRAGMA busy_timeout = {config.DATABASE_BUSY_TIMEOUT}')
        cursor.execute(f'PRAGMA temp_store = {config.SQLITE_TEMP_STORE}')
        cursor.execute(f'PRAGMA cache_size = {config.DATABASE_CACHE_SIZE}')

        return self.conn

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit context manager and handle connection cleanup."""
        if self.conn:
            if exc_type is not None:
                # Exception occurred, rollback transaction
                self.conn.rollback()
                logger.error(
                    f'Database transaction rolled back due to {exc_type.__name__}: {exc_val}'
                )
            else:
                # No exception, commit transaction
                self.conn.commit()

            self.conn.close()
            self.conn = None


@contextmanager
def get_connection() -> Generator[sqlite3.Connection]:
    """Create and return a database connection with proper context manager support.

    Yields:
        sqlite3.Connection: Database connection with proper cleanup

    Example:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workflows")
    """
    with DatabaseConnection(config.DATABASE_PATH, config.DATABASE_TIMEOUT) as conn:
        yield conn


def initialize_database() -> None:
    """Create database tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        logger.info(f'Database connection established: {config.DATABASE_PATH}')

        # Repositories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Actors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Branches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Workflows table (normalized)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                repository_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                path TEXT,
                state TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (repository_id) REFERENCES repositories (id)
            )
        """)

        # Workflow runs table (normalized)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                run_number INTEGER,
                commit_sha TEXT,
                branch_id INTEGER,
                event_id INTEGER,
                status TEXT NOT NULL,
                conclusion TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                duration_seconds INTEGER,
                actor_id INTEGER,
                url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workflow_id) REFERENCES workflows (id),
                FOREIGN KEY (branch_id) REFERENCES branches (id),
                FOREIGN KEY (event_id) REFERENCES events (id),
                FOREIGN KEY (actor_id) REFERENCES actors (id)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_workflows_repository
            ON workflows (repository_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_workflow_id
            ON runs (workflow_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_status
            ON runs (status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_completed_at
            ON runs (completed_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_conclusion
            ON runs (conclusion)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_branch
            ON runs (branch_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_event
            ON runs (event_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_actor
            ON runs (actor_id)
        """)

        # Metrics view for real-time calculation (normalized)
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS workflow_metrics_view AS
            SELECT
                repo.name as repository,
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
            JOIN repositories repo ON w.repository_id = repo.id
            LEFT JOIN runs r ON w.id = r.workflow_id
            WHERE r.status = 'completed'
            GROUP BY repo.name, w.id, w.name
        """)

        # MTTR view for real-time calculation
        cursor.execute("""
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
        """)

        # MTTR cache table for background job computation
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mttr_cache (
            workflow_id TEXT PRIMARY KEY,
            mttr_seconds REAL,
            sample_size INTEGER,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows (id)
        )
        """)

        # Health score cache table for background job computation
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_score_cache (
            workflow_id TEXT PRIMARY KEY,
            overall_score REAL,
            health_class TEXT,
            data_quality TEXT,
            success_rate_score REAL,
            mttr_score REAL,
            duration_score REAL,
            throughput_score REAL,
            sample_size INTEGER,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows (id)
        )
        """)

        # Index for cache staleness checks
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mttr_cache_calculated
            ON mttr_cache (calculated_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_health_score_cache_calculated
            ON health_score_cache (calculated_at)
        """)

        conn.commit()
    logger.info('Database initialized successfully.')


@retry_database_operation(max_retries=3)
def insert_workflow(
    workflow_id: str,
    repository: str,
    name: str,
    path: str | None = None,
    state: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Insert or update a workflow record with idempotency.

    Args:
        workflow_id: Workflow ID
        repository: Repository name
        name: Workflow name
        path: Workflow file path
        state: Workflow state
        conn: Optional database connection (for batch operations)
    """
    if conn is not None:
        # Use provided connection (for batch operations)
        try:
            cursor = conn.cursor()
            # Insert repository if not exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO repositories (name) VALUES (?)
            """,
                (repository,),
            )

            # Get repository ID
            cursor.execute('SELECT id FROM repositories WHERE name = ?', (repository,))
            repo_id = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO workflows (id, repository_id, name, path, state)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repository_id = excluded.repository_id,
                    name = excluded.name,
                    path = excluded.path,
                    state = excluded.state,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (workflow_id, repo_id, name, path, state),
            )
            return True
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                logger.warning(
                    f'Database locked for workflow {workflow_id}, skipping...'
                )
                return False
            raise
    else:
        # Create new connection with context manager
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Insert repository if not exists
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO repositories (name) VALUES (?)
                """,
                    (repository,),
                )

                # Get repository ID
                cursor.execute(
                    'SELECT id FROM repositories WHERE name = ?', (repository,)
                )
                repo_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO workflows (id, repository_id, name, path, state)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        repository_id = excluded.repository_id,
                        name = excluded.name,
                        path = excluded.path,
                        state = excluded.state,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (workflow_id, repo_id, name, path, state),
                )
                return True
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                logger.warning(
                    f'Database locked for workflow {workflow_id}, skipping...'
                )
                return False
            raise


def insert_run(
    run_id: str,
    workflow_id: str,
    run_number: int,
    commit_sha: str | None,
    branch: str | None,
    event: str | None,
    status: str,
    conclusion: str | None,
    started_at: str | None,
    completed_at: str | None,
    duration_seconds: int | None,
    actor: str | None,
    url: str | None,
) -> None:
    """Insert or update a workflow run record with idempotency."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Insert normalized entities if they don't exist
        branch_id = None
        if branch:
            cursor.execute(
                'INSERT OR IGNORE INTO branches (name) VALUES (?)', (branch,)
            )
            cursor.execute('SELECT id FROM branches WHERE name = ?', (branch,))
            result = cursor.fetchone()
            if result:
                branch_id = result[0]

        event_id = None
        if event:
            cursor.execute('INSERT OR IGNORE INTO events (name) VALUES (?)', (event,))
            cursor.execute('SELECT id FROM events WHERE name = ?', (event,))
            result = cursor.fetchone()
            if result:
                event_id = result[0]

        actor_id = None
        if actor:
            cursor.execute('INSERT OR IGNORE INTO actors (login) VALUES (?)', (actor,))
            cursor.execute('SELECT id FROM actors WHERE login = ?', (actor,))
            result = cursor.fetchone()
            if result:
                actor_id = result[0]

        cursor.execute(
            """
            INSERT INTO runs
            (id, workflow_id, run_number, commit_sha, branch_id, event_id, status, conclusion,
             started_at, completed_at, duration_seconds, actor_id, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                workflow_id = excluded.workflow_id,
                run_number = excluded.run_number,
                commit_sha = excluded.commit_sha,
                branch_id = excluded.branch_id,
                event_id = excluded.event_id,
                status = excluded.status,
                conclusion = excluded.conclusion,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                duration_seconds = excluded.duration_seconds,
                actor_id = excluded.actor_id,
                url = excluded.url,
                updated_at = CURRENT_TIMESTAMP
        """,
            (
                run_id,
                workflow_id,
                run_number,
                commit_sha,
                branch_id,
                event_id,
                status,
                conclusion,
                started_at,
                completed_at,
                duration_seconds,
                actor_id,
                url,
            ),
        )


@retry_database_operation(max_retries=3)
def insert_runs_batch(
    runs_data: list[tuple], conn: sqlite3.Connection | None = None
) -> bool:
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

    if conn is not None:
        # Use provided connection (for batch operations)
        try:
            cursor = conn.cursor()
            # Process each run individually to handle normalized entities
            for run_data in runs_data:
                (
                    run_id,
                    workflow_id,
                    run_number,
                    commit_sha,
                    branch,
                    event,
                    status,
                    conclusion,
                    started_at,
                    completed_at,
                    duration_seconds,
                    actor,
                    url,
                ) = run_data

                # Insert normalized entities
                branch_id = None
                if branch:
                    cursor.execute(
                        'INSERT OR IGNORE INTO branches (name) VALUES (?)', (branch,)
                    )
                    cursor.execute('SELECT id FROM branches WHERE name = ?', (branch,))
                    result = cursor.fetchone()
                    if result:
                        branch_id = result[0]

                event_id = None
                if event:
                    cursor.execute(
                        'INSERT OR IGNORE INTO events (name) VALUES (?)', (event,)
                    )
                    cursor.execute('SELECT id FROM events WHERE name = ?', (event,))
                    result = cursor.fetchone()
                    if result:
                        event_id = result[0]

                actor_id = None
                if actor:
                    cursor.execute(
                        'INSERT OR IGNORE INTO actors (login) VALUES (?)', (actor,)
                    )
                    cursor.execute('SELECT id FROM actors WHERE login = ?', (actor,))
                    result = cursor.fetchone()
                    if result:
                        actor_id = result[0]

                cursor.execute(
                    """
                    INSERT INTO runs
                    (id, workflow_id, run_number, commit_sha, branch_id, event_id, status, conclusion,
                     started_at, completed_at, duration_seconds, actor_id, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        workflow_id = excluded.workflow_id,
                        run_number = excluded.run_number,
                        commit_sha = excluded.commit_sha,
                        branch_id = excluded.branch_id,
                        event_id = excluded.event_id,
                        status = excluded.status,
                        conclusion = excluded.conclusion,
                        started_at = excluded.started_at,
                        completed_at = excluded.completed_at,
                        duration_seconds = excluded.duration_seconds,
                        actor_id = excluded.actor_id,
                        url = excluded.url,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        run_id,
                        workflow_id,
                        run_number,
                        commit_sha,
                        branch_id,
                        event_id,
                        status,
                        conclusion,
                        started_at,
                        completed_at,
                        duration_seconds,
                        actor_id,
                        url,
                    ),
                )
            return True
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                logger.warning(
                    f'Database locked for batch insert, skipping {len(runs_data)} runs...'
                )
                return False
            raise
    else:
        # Create new connection with context manager
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Process each run individually to handle normalized entities
                for run_data in runs_data:
                    (
                        run_id,
                        workflow_id,
                        run_number,
                        commit_sha,
                        branch,
                        event,
                        status,
                        conclusion,
                        started_at,
                        completed_at,
                        duration_seconds,
                        actor,
                        url,
                    ) = run_data

                    # Insert normalized entities
                    branch_id = None
                    if branch:
                        cursor.execute(
                            'INSERT OR IGNORE INTO branches (name) VALUES (?)',
                            (branch,),
                        )
                        cursor.execute(
                            'SELECT id FROM branches WHERE name = ?', (branch,)
                        )
                        result = cursor.fetchone()
                        if result:
                            branch_id = result[0]

                    event_id = None
                    if event:
                        cursor.execute(
                            'INSERT OR IGNORE INTO events (name) VALUES (?)', (event,)
                        )
                        cursor.execute('SELECT id FROM events WHERE name = ?', (event,))
                        result = cursor.fetchone()
                        if result:
                            event_id = result[0]

                    actor_id = None
                    if actor:
                        cursor.execute(
                            'INSERT OR IGNORE INTO actors (login) VALUES (?)', (actor,)
                        )
                        cursor.execute(
                            'SELECT id FROM actors WHERE login = ?', (actor,)
                        )
                        result = cursor.fetchone()
                        if result:
                            actor_id = result[0]

                    cursor.execute(
                        """
                        INSERT INTO runs
                        (id, workflow_id, run_number, commit_sha, branch_id, event_id, status, conclusion,
                         started_at, completed_at, duration_seconds, actor_id, url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            workflow_id = excluded.workflow_id,
                            run_number = excluded.run_number,
                            commit_sha = excluded.commit_sha,
                            branch_id = excluded.branch_id,
                            event_id = excluded.event_id,
                            status = excluded.status,
                            conclusion = excluded.conclusion,
                            started_at = excluded.started_at,
                            completed_at = excluded.completed_at,
                            duration_seconds = excluded.duration_seconds,
                            actor_id = excluded.actor_id,
                            url = excluded.url,
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (
                            run_id,
                            workflow_id,
                            run_number,
                            commit_sha,
                            branch_id,
                            event_id,
                            status,
                            conclusion,
                            started_at,
                            completed_at,
                            duration_seconds,
                            actor_id,
                            url,
                        ),
                    )
                return True
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                logger.warning(
                    f'Database locked for batch insert, skipping {len(runs_data)} runs...'
                )
                return False
            raise


def get_workflows() -> list[sqlite3.Row]:
    """Retrieve all workflows."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT w.*, r.name as repository
            FROM workflows w
            JOIN repositories r ON w.repository_id = r.id
            ORDER BY r.name, w.name
        """)
        workflows = cursor.fetchall()
        return workflows


def get_runs(
    workflow_id: str | None = None,
    limit: int | None = None,
    repository: str | None = None,
    status: str | None = None,
    conclusion: str | None = None,
) -> list[sqlite3.Row]:
    """Retrieve workflow runs with various filters.

    Args:
        workflow_id: Filter by workflow ID
        limit: Maximum number of results
        repository: Filter by repository name
        status: Filter by status (completed, in_progress, etc.)
        conclusion: Filter by conclusion (success, failure, etc.)
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = 'SELECT r.* FROM runs r'
        conditions = []
        params = []

        # Join with workflows and repositories if filtering by repository
        if repository:
            query += ' JOIN workflows w ON r.workflow_id = w.id JOIN repositories repo ON w.repository_id = repo.id'
            conditions.append('repo.name = ?')
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
        return runs


def _build_metrics_query(
    repository: str | None = None, days: int | None = None
) -> tuple[str, list[str]]:
    """Build unified metrics query with optional filters.

    Args:
        repository: Filter by repository name (None for all)
        days: Filter by last N days (None for all time)

    Returns:
        Tuple of (query_string, params_list)
    """

    if days and (not isinstance(days, int) or days <= 0):
        raise ValueError('Invalid days parameter - must be positive integer')
    # Common metric aggregations (avoid duplication)
    metrics_select = f"""
        COUNT(*) as total_runs,
        SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN r.conclusion = 'failure' THEN 1 ELSE 0 END) as failure_count,
        ROUND(AVG(r.duration_seconds), 2) as avg_duration_seconds,
        ROUND(
            CAST(SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) AS FLOAT) /
            NULLIF(SUM(CASE WHEN r.conclusion IN ('success', 'failure') THEN 1 ELSE 0 END), 0) * {config.DATABASE_SUCCESS_RATE_MULTIPLIER},
            2
        ) as success_rate,
        MIN(r.started_at) as first_run,
        MAX(r.started_at) as last_run
    """

    # MTTR: Use cache for all-time, compute for period-filtered queries
    if days:
        # Period-filtered: Compute MTTR with subquery (slower but accurate)
        mttr_select = """
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
        """
        health_select = ""
    else:
        # All-time: Use pre-computed cache (fast)
        mttr_select = 'c.mttr_seconds'
        health_select = """
            , h.overall_score
            , h.health_class
            , h.data_quality
            , h.success_rate_score
            , h.mttr_score
            , h.duration_score
            , h.throughput_score
        """

    # Build WHERE conditions
    where_conditions = ["r.status = 'completed'"]
    params = []

    if days:
        where_conditions.append("r.started_at >= datetime('now', '-' || ? || ' days')")
        params.append(days)
        params.append(days)  # For MTTR subquery

    if repository:
        where_conditions.append('repo.name = ?')
        params.append(repository)

    where_clause = ' AND '.join(where_conditions)

    # Build JOIN clause (add cache tables for all-time queries)
    if days:
        # Period-filtered: No cache join needed
        joins = """
            JOIN repositories repo ON w.repository_id = repo.id
            LEFT JOIN runs r ON w.id = r.workflow_id
        """
    else:
        # All-time: Join with cache tables
        joins = """
            JOIN repositories repo ON w.repository_id = repo.id
            LEFT JOIN runs r ON w.id = r.workflow_id
            LEFT JOIN mttr_cache c ON w.id = c.workflow_id
            LEFT JOIN health_score_cache h ON w.id = h.workflow_id
        """

    # Unified query for all cases
    query = f"""
        SELECT
            repo.name as repository,
            w.name as workflow_name,
            w.id as workflow_id,
            {metrics_select},
            {mttr_select}{health_select}
        FROM workflows w
        {joins}
        WHERE {where_clause}
        GROUP BY repo.name, w.id, w.name
        ORDER BY repo.name, w.name
    """

    return query, params


# Internal function with TTL-based caching
@lru_cache(maxsize=128)
def _get_metrics_cached(
    repository: str | None, days: int | None, cache_key: str
) -> list[sqlite3.Row]:
    """Internal cached version of metrics retrieval.

    Args:
        repository: Repository name (or None)
        days: Number of days (or None)
        cache_key: Timestamp for cache invalidation (minutes)

    Returns:
        Tuple of metric dictionaries
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Build unified query (eliminates code duplication)
        query, params = _build_metrics_query(repository=repository, days=days)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        metrics = []
        for row in rows:
            try:
                # Use cached health score for all-time queries, calculate for period-filtered
                if days:
                    # Period-filtered: Calculate health score on-the-fly
                    from cipette.health_calculator import calculate_health_score_safe

                    health_result = calculate_health_score_safe(
                        success_rate=row['success_rate'],
                        mttr_seconds=row['mttr_seconds'],
                        avg_duration_seconds=row['avg_duration_seconds'],
                        total_runs=row['total_runs'],
                        days=days,
                    )

                    # Log warnings if any
                    if health_result['warnings']:
                        logger.warning(
                            f'Health score warnings for {row["repository"]}/{row["workflow_name"]}: '
                            f'{", ".join(health_result["warnings"])}'
                        )

                    # Log errors if any
                    if health_result['errors']:
                        logger.error(
                            f'Health score errors for {row["repository"]}/{row["workflow_name"]}: '
                            f'{", ".join(health_result["errors"])}'
                        )

                    health_score = health_result['overall_score']
                    health_class = health_result['health_class']
                    data_quality = health_result['data_quality']
                    health_breakdown = {
                        'success_rate_score': round(
                            health_result['breakdown'].get('success_rate_score', 0.0), 1
                        ),
                        'mttr_score': round(
                            health_result['breakdown'].get('mttr_score', 0.0), 1
                        ),
                        'duration_score': round(
                            health_result['breakdown'].get('duration_score', 0.0), 1
                        ),
                        'throughput_score': round(
                            health_result['breakdown'].get('throughput_score', 0.0), 1
                        ),
                    }
                    health_warnings = health_result['warnings']
                    health_errors = health_result['errors']
                else:
                    # All-time: Use cached health score
                    health_score = row['overall_score'] if row['overall_score'] is not None else 0.0
                    health_class = row['health_class'] if row['health_class'] is not None else 'unknown'
                    data_quality = row['data_quality'] if row['data_quality'] is not None else 'insufficient'
                    health_breakdown = {
                        'success_rate_score': round(
                            row['success_rate_score'] if row['success_rate_score'] is not None else 0.0, 1
                        ),
                        'mttr_score': round(row['mttr_score'] if row['mttr_score'] is not None else 0.0, 1),
                        'duration_score': round(row['duration_score'] if row['duration_score'] is not None else 0.0, 1),
                        'throughput_score': round(row['throughput_score'] if row['throughput_score'] is not None else 0.0, 1),
                    }
                    health_warnings = []
                    health_errors = []

                metrics.append(
                    {
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
                        'mttr_seconds': row['mttr_seconds'],
                        'health_score': health_score,
                        'health_class': health_class,
                        'data_quality': data_quality,
                        'health_breakdown': health_breakdown,
                        'health_warnings': health_warnings,
                        'health_errors': health_errors,
                    }
                )

            except Exception as e:
                logger.error(
                    f'Failed to process health score for {row["repository"]}/{row["workflow_name"]}: {e}',
                    exc_info=True,
                )

                # Fallback: create metric entry without health score
                metrics.append(
                    {
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
                        'mttr_seconds': row['mttr_seconds'],
                        'health_score': 0.0,
                        'health_class': 'unknown',
                        'data_quality': 'insufficient',
                        'health_breakdown': {
                            'success_rate_score': 0.0,
                            'mttr_score': 0.0,
                            'duration_score': 0.0,
                            'throughput_score': 0.0,
                        },
                        'health_warnings': [
                            f'Health score processing failed: {str(e)}'
                        ],
                        'health_errors': [f'Processing error: {str(e)}'],
                    }
                )

        # Return as tuple for lru_cache (lists are not hashable)
        return tuple(tuple(m.items()) for m in metrics)


def get_metrics_by_repository(
    repository: str | None = None, days: int | None = None
) -> list[dict[str, object]]:
    """Get CI/CD metrics from view with MTTR (cached for 1 minute).

    Args:
        repository: Filter by specific repository (None for all)
        days: Only include runs from last N days (None for all time)

    Returns:
        List of dicts with metrics for each repository/workflow combination
    """
    # Calculate cache key (invalidates every minute)
    cache_key = int(time.time() / config.DATABASE_CACHE_TTL_SECONDS)

    # Get cached results
    cached_tuples = _get_metrics_cached(repository, days, cache_key)

    # Convert back to list of dicts
    return [dict(items) for items in cached_tuples]


# Legacy functions for backward compatibility
def calculate_health_score(
    success_rate: float | None,
    mttr_seconds: float | None,
    avg_duration_seconds: float | None,
    total_runs: int,
    days: int = 30,
) -> dict[str, float]:
    """Legacy health score calculation function.

    DEPRECATED: Use HealthScoreCalculator from health_calculator module instead.
    """
    from cipette.health_calculator import calculate_health_score_safe

    result = calculate_health_score_safe(
        success_rate, mttr_seconds, avg_duration_seconds, total_runs, days
    )

    # Convert to legacy format
    return {
        'success_rate_score': result['breakdown'].get('success_rate_score', 0.0),
        'mttr_score': result['breakdown'].get('mttr_score', 0.0),
        'duration_score': result['breakdown'].get('duration_score', 0.0),
        'throughput_score': result['breakdown'].get('throughput_score', 0.0),
        'overall_score': result['overall_score'],
    }


def get_health_score_class(score: float) -> str:
    """Get health score classification.

    Args:
        score: Health score (0-100)

    Returns:
        Classification string: 'excellent', 'good', 'fair', 'poor'
    """
    if score >= config.HEALTH_SCORE_EXCELLENT:
        return 'excellent'
    elif score >= config.HEALTH_SCORE_GOOD:
        return 'good'
    elif score >= config.HEALTH_SCORE_FAIR:
        return 'fair'
    else:
        return 'poor'


def calculate_mttr(
    workflow_id: str | None = None,
    repository: str | None = None,
    days: int | None = None,
) -> float | None:
    """Calculate Mean Time To Recovery (MTTR).

    MTTR = Average time from a failure completion to the next success completion.

    Args:
        workflow_id: Filter by workflow ID
        repository: Filter by repository
        days: Only include runs from last N days

    Returns:
        Average MTTR in seconds, or None if no data
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        filters = [
            "r1.conclusion IN ('success', 'failure')",
            "r1.status = 'completed'",
            'r1.completed_at IS NOT NULL',
        ]
        params = []

        if workflow_id:
            filters.append('r1.workflow_id = ?')
            params.append(workflow_id)

        if repository:
            filters.append('repo.name = ?')
            params.append(repository)

        if days:
            filters.append("r1.completed_at >= datetime('now', '-' || ? || ' days')")
            params.append(int(days))

        where_clause = ' AND '.join(filters)

        # Need to join workflows and repositories for repository filter
        if repository:
            from_clause = 'FROM runs r1 JOIN workflows w ON r1.workflow_id = w.id JOIN repositories repo ON w.repository_id = repo.id'
        else:
            from_clause = 'FROM runs r1'

        query = f"""
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
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return None

        # Calculate average time to recovery
        total_seconds = 0
        count = 0

        for row in rows:
            try:
                # Handle ISO 8601 format with timezone info
                failure_time = datetime.fromisoformat(
                    row['failure_time'].replace('Z', '+00:00')
                )
                recovery_time = datetime.fromisoformat(
                    row['recovery_time'].replace('Z', '+00:00')
                )
                delta = (recovery_time - failure_time).total_seconds()
                total_seconds += delta
                count += 1
            except ValueError as e:
                logger.warning(f'Error parsing datetime for MTTR calculation: {e}')
                continue

        return round(total_seconds / count, 2) if count > 0 else None


def refresh_mttr_cache() -> None:
    """Refresh MTTR cache for all workflows (background job).

    This function:
    1. Retrieves all workflows from the database
    2. Calculates MTTR for each workflow
    3. Stores/updates results in mttr_cache table

    Designed to be called by background worker thread.
    """
    logger.info('Starting MTTR cache refresh...')
    start_time = time.time()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

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
                        cursor.execute(
                            """
                            SELECT COUNT(*) as count
                            FROM runs
                            WHERE workflow_id = ?
                                AND conclusion = 'failure'
                                AND status = 'completed'
                        """,
                            (workflow_id,),
                        )
                        sample_size = cursor.fetchone()['count']

                        # Insert or update cache
                        cursor.execute(
                            """
                            INSERT INTO mttr_cache (workflow_id, mttr_seconds, sample_size, calculated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(workflow_id) DO UPDATE SET
                                mttr_seconds = excluded.mttr_seconds,
                                sample_size = excluded.sample_size,
                                calculated_at = excluded.calculated_at
                        """,
                            (workflow_id, mttr, sample_size),
                        )
                        success_count += 1
                    else:
                        # No MTTR data (no failures or no recovery) - clear cache entry
                        cursor.execute(
                            'DELETE FROM mttr_cache WHERE workflow_id = ?',
                            (workflow_id,),
                        )

                except Exception as e:
                    logger.error(
                        f'Error calculating MTTR for workflow {workflow_id}: {e}'
                    )
                    error_count += 1
                    continue

            elapsed = time.time() - start_time
            logger.info(
                f'MTTR cache refresh completed: {success_count} updated, {error_count} errors, {elapsed:.2f}s'
            )

    except Exception as e:
        logger.error(f'MTTR cache refresh failed: {e}')
        raise


def clear_mttr_cache() -> None:
    """Clear all MTTR cache entries.

    Useful for:
    - Manual cache invalidation
    - Testing
    - Forcing full recalculation
    """
    logger.info('Clearing MTTR cache...')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM mttr_cache')
        deleted_count = cursor.rowcount
        logger.info(f'MTTR cache cleared: {deleted_count} entries removed')


def refresh_health_score_cache() -> None:
    """Refresh health score cache for all workflows.

    This function:
    1. Retrieves all workflows from the database
    2. Calculates health score for each workflow
    3. Stores/updates results in health_score_cache table

    Designed to be called by background worker thread.
    """
    logger.info('Starting health score cache refresh...')
    start_time = time.time()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get all workflows with their metrics
            cursor.execute("""
                SELECT
                    w.id as workflow_id,
                    repo.name as repository,
                    w.name as workflow_name,
                    COUNT(r.id) as total_runs,
                    SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN r.conclusion = 'failure' THEN 1 ELSE 0 END) as failure_count,
                    ROUND(AVG(r.duration_seconds), 2) as avg_duration_seconds,
                    ROUND(
                        CAST(SUM(CASE WHEN r.conclusion = 'success' THEN 1 ELSE 0 END) AS FLOAT) /
                        NULLIF(SUM(CASE WHEN r.conclusion IN ('success', 'failure') THEN 1 ELSE 0 END), 0) * 100,
                        2
                    ) as success_rate
                FROM workflows w
                JOIN repositories repo ON w.repository_id = repo.id
                LEFT JOIN runs r ON w.id = r.workflow_id
                WHERE r.status = 'completed' OR r.status IS NULL
                GROUP BY w.id, repo.name, w.name
            """)
            workflows = cursor.fetchall()

            success_count = 0
            error_count = 0

            for workflow in workflows:
                workflow_id = workflow['workflow_id']

                try:
                    # Get MTTR from cache
                    cursor.execute(
                        'SELECT mttr_seconds FROM mttr_cache WHERE workflow_id = ?',
                        (workflow_id,),
                    )
                    mttr_row = cursor.fetchone()
                    mttr_seconds = mttr_row['mttr_seconds'] if mttr_row else None

                    # Calculate health score using the robust calculator
                    from cipette.health_calculator import calculate_health_score_safe

                    health_result = calculate_health_score_safe(
                        success_rate=workflow['success_rate'],
                        mttr_seconds=mttr_seconds,
                        avg_duration_seconds=workflow['avg_duration_seconds'],
                        total_runs=workflow['total_runs'],
                        days=30,  # Default to 30 days for cache
                    )

                    # Insert or update cache
                    cursor.execute(
                        """
                        INSERT INTO health_score_cache (
                            workflow_id, overall_score, health_class, data_quality,
                            success_rate_score, mttr_score, duration_score, throughput_score,
                            sample_size, calculated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(workflow_id) DO UPDATE SET
                            overall_score = excluded.overall_score,
                            health_class = excluded.health_class,
                            data_quality = excluded.data_quality,
                            success_rate_score = excluded.success_rate_score,
                            mttr_score = excluded.mttr_score,
                            duration_score = excluded.duration_score,
                            throughput_score = excluded.throughput_score,
                            sample_size = excluded.sample_size,
                            calculated_at = excluded.calculated_at
                    """,
                        (
                            workflow_id,
                            health_result['overall_score'],
                            health_result['health_class'],
                            health_result['data_quality'],
                            health_result['breakdown'].get('success_rate_score', 0.0),
                            health_result['breakdown'].get('mttr_score', 0.0),
                            health_result['breakdown'].get('duration_score', 0.0),
                            health_result['breakdown'].get('throughput_score', 0.0),
                            workflow['total_runs'],
                        ),
                    )

                    success_count += 1

                except Exception as e:
                    logger.error(
                        f'Error calculating health score for workflow {workflow_id}: {e}'
                    )
                    error_count += 1
                    continue

            elapsed = time.time() - start_time
            logger.info(
                f'Health score cache refresh completed: '
                f'{success_count} workflows processed, {error_count} errors, '
                f'{elapsed:.2f}s elapsed'
            )

    except Exception as e:
        logger.error(f'Health score cache refresh failed: {e}', exc_info=True)
        raise


def clear_health_score_cache() -> None:
    """Clear all health score cache entries.

    Useful for:
    - Manual cache invalidation
    - Testing
    - Forcing full recalculation
    """
    logger.info('Clearing health score cache...')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM health_score_cache')
        deleted_count = cursor.rowcount
        logger.info(f'Health score cache cleared: {deleted_count} entries removed')


if __name__ == '__main__':
    # Initialize database when run directly
    initialize_database()
