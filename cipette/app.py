"""Flask web application for CIPette dashboard."""

import logging
import os
import sqlite3
import threading
import time
from functools import lru_cache
from pathlib import Path

from flask import Flask, render_template, request

from cipette.config import Config
from cipette.database import (
    get_connection,
    get_metrics_by_repository,
    refresh_mttr_cache,
)
from cipette.error_handling import ConfigurationError, DatabaseError
from cipette.logging_config import setup_logging

# Initialize logging
setup_logging()

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent

# Flask app setup
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'templates'),
    static_folder=str(BASE_DIR / 'static'),
)

logger = logging.getLogger(__name__)


# Template filters
def _format_time(seconds: float | None, units: list[tuple[str, int]]) -> str:
    """Generic time formatter.

    Args:
        seconds: Time in seconds
        units: List of (unit_name, unit_seconds) tuples

    Returns:
        Formatted time string
    """
    if seconds is None:
        return 'N/A'

    parts = []
    remaining = int(seconds)

    for unit_name, unit_seconds in units:
        if remaining >= unit_seconds:
            value = remaining // unit_seconds
            parts.append(f'{value}{unit_name}')
            remaining %= unit_seconds

    return ' '.join(parts) or f'0{units[-1][0]}'


@app.template_filter('duration')
def format_duration(seconds: float | None) -> str:
    """Format duration in seconds to human-readable format.

    Examples:
        >>> format_duration(330)
        '5m 30s'
        >>> format_duration(45)
        '45s'
        >>> format_duration(None)
        'N/A'
    """
    return _format_time(seconds, Config.TIME_UNITS[1:])  # minutes and seconds


@app.template_filter('rate_class')
def rate_class(rate: float | None) -> str:
    """Classify success rate into CSS class.

    Args:
        rate: Success rate percentage (0-100 or None)

    Returns:
        CSS class name: 'high', 'medium', or 'low'
    """
    if rate is None:
        return 'low'
    if rate >= Config.SUCCESS_RATE_HIGH_THRESHOLD:
        return 'high'
    elif rate >= Config.SUCCESS_RATE_MEDIUM_THRESHOLD:
        return 'medium'
    else:
        return 'low'


@app.template_filter('mttr')
def format_mttr(seconds: float | None) -> str:
    """Format MTTR in seconds to human-readable format.

    Examples:
        >>> format_mttr(7200)
        '2h 0m'
        >>> format_mttr(900)
        '15m'
    """
    return _format_time(seconds, Config.TIME_UNITS[:2])  # hours and minutes


# Helper functions
@lru_cache(maxsize=128)
def get_available_repositories() -> list[str]:
    """Get list of all repositories in database.

    Returns:
        List of repository names

    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT name FROM repositories ORDER BY name')
            rows = cursor.fetchall()
            return [row['name'] for row in rows]
    except sqlite3.OperationalError as e:
        logger.error(f'Database operational error: {e}')
        raise DatabaseError(f'Database operation failed: {e}') from e
    except sqlite3.DatabaseError as e:
        logger.error(f'Database error: {e}')
        raise DatabaseError(f'Database error: {e}') from e
    except Exception as e:
        logger.error(f'Unexpected error fetching repositories: {e}', exc_info=True)
        raise DatabaseError(f'Unexpected database error: {e}') from e


# Routes
@app.route('/')
def dashboard() -> str:
    """Main dashboard view with metrics and filters.

    Query Parameters:
        days (int, optional): Filter runs from last N days
        repository (str, optional): Filter by repository name

    Returns:
        Rendered dashboard template with metrics
    """
    days = request.args.get('days', type=int)
    repository = request.args.get('repository', type=str)

    logger.info(f'Dashboard accessed: days={days}, repository={repository}')

    try:
        # Get metrics from database (with MTTR included via views)
        metrics = get_metrics_by_repository(repository=repository, days=days)
        repositories = get_available_repositories()

        logger.info(f'Loaded {len(metrics)} metrics with workflow-level MTTR')

        return render_template(
            'dashboard.html',
            metrics=metrics,
            repositories=repositories,
            selected_days=days,
            selected_repository=repository,
        )

    except DatabaseError as e:
        logger.error(f'Database error loading dashboard: {e}')
        return render_template(
            'error.html',
            error_message="Database error. Please run 'cipette-collect' first or check database configuration.",
        ), 500

    except ConfigurationError as e:
        logger.error(f'Configuration error loading dashboard: {e}')
        return render_template(
            'error.html',
            error_message='Configuration error. Please check your settings.',
        ), 500

    except Exception as e:
        logger.error(f'Unexpected error loading dashboard: {e}', exc_info=True)
        return render_template(
            'error.html', error_message='Failed to load dashboard metrics'
        ), 500


# Error handlers
@app.errorhandler(404)
def not_found(error: Exception) -> tuple[str, int]:
    """Handle 404 errors."""
    try:
        return render_template('error.html', error_message='Page not found'), 404
    except Exception:
        return 'Page not found', 404


@app.errorhandler(500)
def internal_error(error: Exception) -> tuple[str, int]:
    """Handle 500 errors."""
    logger.error(f'Internal error: {error}', exc_info=True)
    try:
        return render_template('error.html', error_message='Internal server error'), 500
    except Exception:
        return 'Internal server error', 500


# Background worker for MTTR cache refresh
def start_mttr_refresh_worker() -> None:
    """Start background thread to periodically refresh MTTR cache.

    Refresh interval is controlled by MTTR_REFRESH_INTERVAL environment variable.
    Default: 300 seconds (5 minutes)
    """

    def worker() -> None:
        # Get refresh interval from environment variable
        interval = Config.MTTR_REFRESH_INTERVAL
        logger.info(f'MTTR cache refresh worker starting (interval: {interval}s)')

        # Initial delay to let Flask app fully start
        time.sleep(Config.MTTR_WORKER_INITIAL_DELAY)

        while True:
            try:
                refresh_mttr_cache()
            except Exception as e:
                logger.error(f'MTTR cache refresh failed: {e}', exc_info=True)
                # Continue despite errors

            # Wait for next refresh
            time.sleep(interval)

    # Start daemon thread (terminates when main thread exits)
    thread = threading.Thread(target=worker, daemon=True, name='MTTRRefreshWorker')
    thread.start()
    logger.info('MTTR cache refresh worker started')


# Main entry point
def main() -> None:
    """Main entry point for Flask application."""
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.getenv('FLASK_HOST', Config.WEB_HOST)
    port = int(os.getenv('FLASK_PORT', Config.WEB_DEFAULT_PORT))

    logger.info('Starting CIPette web dashboard...')
    logger.info(f'Access dashboard at: http://{host}:{port}')
    logger.info(f'Debug mode: {debug}')

    # Start background worker for MTTR cache refresh
    start_mttr_refresh_worker()

    app.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    main()
