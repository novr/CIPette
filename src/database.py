import sqlite3
from datetime import datetime
from config import DATABASE_PATH


def get_connection():
    """Create and return a database connection."""
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

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def insert_workflow(workflow_id, repository, name, path=None, state=None):
    """Insert or update a workflow record with idempotency."""
    conn = get_connection()
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


def insert_runs_batch(runs_data):
    """Insert or update multiple workflow run records in a single transaction with idempotency.

    Args:
        runs_data: List of tuples with format:
            (id, workflow_id, run_number, commit_sha, branch, event, status, conclusion,
             started_at, completed_at, duration_seconds, actor, url)
    """
    if not runs_data:
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Use ON CONFLICT for true upsert behavior
    for run_data in runs_data:
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
        ''', run_data)

    conn.commit()
    conn.close()


def get_workflows():
    """Retrieve all workflows."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM workflows ORDER BY repository, name')
    workflows = cursor.fetchall()

    conn.close()
    return workflows


def get_runs(workflow_id=None, limit=None):
    """Retrieve workflow runs, optionally filtered by workflow_id."""
    conn = get_connection()
    cursor = conn.cursor()

    if workflow_id:
        query = 'SELECT * FROM runs WHERE workflow_id = ? ORDER BY completed_at DESC'
        params = (workflow_id,)
    else:
        query = 'SELECT * FROM runs ORDER BY completed_at DESC'
        params = ()

    if limit:
        query += f' LIMIT {limit}'

    cursor.execute(query, params)
    runs = cursor.fetchall()

    conn.close()
    return runs


if __name__ == '__main__':
    # Initialize database when run directly
    initialize_database()