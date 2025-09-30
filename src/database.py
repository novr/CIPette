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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Workflow runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            commit_sha TEXT,
            branch TEXT,
            status TEXT NOT NULL,
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def insert_workflow(workflow_id, repository, name):
    """Insert or update a workflow record."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO workflows (id, repository, name)
        VALUES (?, ?, ?)
    ''', (workflow_id, repository, name))

    conn.commit()
    conn.close()


def insert_run(run_id, workflow_id, commit_sha, branch, status, started_at, completed_at):
    """Insert or update a workflow run record."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO runs
        (id, workflow_id, commit_sha, branch, status, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, workflow_id, commit_sha, branch, status, started_at, completed_at))

    conn.commit()
    conn.close()


def insert_runs_batch(runs_data):
    """Insert or update multiple workflow run records in a single transaction."""
    if not runs_data:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany('''
        INSERT OR REPLACE INTO runs
        (id, workflow_id, commit_sha, branch, status, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', runs_data)

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