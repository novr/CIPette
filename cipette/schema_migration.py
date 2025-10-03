"""Database schema migration utilities for CIPette application."""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Generator

from cipette.config import Config
from cipette.database import get_connection

logger = logging.getLogger(__name__)


class SchemaMigrator:
    """Handles database schema migrations and normalization."""
    
    def __init__(self):
        """Initialize schema migrator."""
        self.current_version = self._get_current_version()
        self.target_version = 2  # Normalized schema version
    
    def _get_current_version(self) -> int:
        """Get current database schema version.
        
        Returns:
            Schema version number
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA user_version")
                return cursor.fetchone()[0]
            except sqlite3.OperationalError:
                return 0  # No version table exists
    
    def _set_version(self, version: int) -> None:
        """Set database schema version.
        
        Args:
            version: Version number to set
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA user_version = {version}")
            conn.commit()
    
    def migrate_to_normalized_schema(self) -> None:
        """Migrate database to normalized schema.
        
        This migration:
        1. Creates new normalized tables
        2. Migrates existing data
        3. Drops old tables
        4. Updates schema version
        """
        if self.current_version >= self.target_version:
            logger.info("Database already at target version")
            return
        
        logger.info(f"Migrating database from version {self.current_version} to {self.target_version}")
        
        try:
            self._create_normalized_tables()
            self._migrate_data()
            self._cleanup_old_tables()
            self._set_version(self.target_version)
            logger.info("Database migration completed successfully")
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            raise
    
    def _create_normalized_tables(self) -> None:
        """Create normalized tables."""
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Repositories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Actors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS actors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Branches table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS branches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Normalized workflows table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflows_normalized (
                    id TEXT PRIMARY KEY,
                    repository_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT,
                    state TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (repository_id) REFERENCES repositories (id)
                )
            ''')
            
            # Normalized runs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs_normalized (
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
                    FOREIGN KEY (workflow_id) REFERENCES workflows_normalized (id),
                    FOREIGN KEY (branch_id) REFERENCES branches (id),
                    FOREIGN KEY (event_id) REFERENCES events (id),
                    FOREIGN KEY (actor_id) REFERENCES actors (id)
                )
            ''')
            
            # Create indexes for normalized tables
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_workflows_normalized_repository
                ON workflows_normalized (repository_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_workflow
                ON runs_normalized (workflow_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_status
                ON runs_normalized (status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_completed_at
                ON runs_normalized (completed_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_conclusion
                ON runs_normalized (conclusion)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_branch
                ON runs_normalized (branch_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_event
                ON runs_normalized (event_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_normalized_actor
                ON runs_normalized (actor_id)
            ''')
            
            conn.commit()
    
    def _migrate_data(self) -> None:
        """Migrate data from old schema to normalized schema."""
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Migrate repositories
            cursor.execute('''
                INSERT OR IGNORE INTO repositories (name)
                SELECT DISTINCT repository FROM workflows
            ''')
            
            # Migrate actors
            cursor.execute('''
                INSERT OR IGNORE INTO actors (login)
                SELECT DISTINCT actor FROM runs WHERE actor IS NOT NULL
            ''')
            
            # Migrate events
            cursor.execute('''
                INSERT OR IGNORE INTO events (name)
                SELECT DISTINCT event FROM runs WHERE event IS NOT NULL
            ''')
            
            # Migrate branches
            cursor.execute('''
                INSERT OR IGNORE INTO branches (name)
                SELECT DISTINCT branch FROM runs WHERE branch IS NOT NULL
            ''')
            
            # Migrate workflows
            cursor.execute('''
                INSERT INTO workflows_normalized (id, repository_id, name, path, state)
                SELECT 
                    w.id,
                    r.id as repository_id,
                    w.name,
                    w.path,
                    w.state
                FROM workflows w
                JOIN repositories r ON w.repository = r.name
            ''')
            
            # Migrate runs
            cursor.execute('''
                INSERT INTO runs_normalized (
                    id, workflow_id, run_number, commit_sha, branch_id, event_id,
                    status, conclusion, started_at, completed_at, duration_seconds,
                    actor_id, url
                )
                SELECT 
                    r.id,
                    r.workflow_id,
                    r.run_number,
                    r.commit_sha,
                    b.id as branch_id,
                    e.id as event_id,
                    r.status,
                    r.conclusion,
                    r.started_at,
                    r.completed_at,
                    r.duration_seconds,
                    a.id as actor_id,
                    r.url
                FROM runs r
                LEFT JOIN branches b ON r.branch = b.name
                LEFT JOIN events e ON r.event = e.name
                LEFT JOIN actors a ON r.actor = a.login
            ''')
            
            conn.commit()
    
    def _cleanup_old_tables(self) -> None:
        """Clean up old tables after successful migration."""
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop old tables
            cursor.execute('DROP TABLE IF EXISTS runs')
            cursor.execute('DROP TABLE IF EXISTS workflows')
            
            # Rename normalized tables to original names
            cursor.execute('ALTER TABLE workflows_normalized RENAME TO workflows')
            cursor.execute('ALTER TABLE runs_normalized RENAME TO runs')
            
            # Update foreign key constraints
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_workflow_id
                ON runs (workflow_id)
            ''')
            
            conn.commit()
    
    def create_normalized_views(self) -> None:
        """Create views for backward compatibility."""
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Create workflow metrics view with normalized schema
            cursor.execute('''
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
            ''')
            
            # Create MTTR view with normalized schema
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
            
            conn.commit()


def migrate_database() -> None:
    """Migrate database to normalized schema."""
    migrator = SchemaMigrator()
    migrator.migrate_to_normalized_schema()
    migrator.create_normalized_views()


if __name__ == '__main__':
    migrate_database()
