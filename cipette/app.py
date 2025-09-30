"""Flask web application for CIPette dashboard."""

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path

from flask import Flask, render_template, request

from cipette.database import get_connection, get_metrics_by_repository

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
SUCCESS_RATE_HIGH_THRESHOLD = 90
SUCCESS_RATE_MEDIUM_THRESHOLD = 70

# Flask app setup
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'templates'),
    static_folder=str(BASE_DIR / 'static')
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
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
            parts.append(f"{value}{unit_name}")
            remaining %= unit_seconds

    return ' '.join(parts) or f"0{units[-1][0]}"


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
    return _format_time(seconds, [('m', 60), ('s', 1)])


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
    if rate >= SUCCESS_RATE_HIGH_THRESHOLD:
        return 'high'
    elif rate >= SUCCESS_RATE_MEDIUM_THRESHOLD:
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
    return _format_time(seconds, [('h', 3600), ('m', 60)])


# Helper functions
@lru_cache(maxsize=1)
def get_available_repositories() -> list[str]:
    """Get list of all repositories in database.

    Returns:
        List of repository names

    Raises:
        sqlite3.OperationalError: If database not found or corrupted
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT repository FROM workflows ORDER BY repository')
            rows = cursor.fetchall()
            return [row['repository'] for row in rows]
    except sqlite3.OperationalError as e:
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching repositories: {e}")
        raise


# Routes
@app.route('/')
def dashboard():
    """Main dashboard view with metrics and filters.

    Query Parameters:
        days (int, optional): Filter runs from last N days
        repository (str, optional): Filter by repository name

    Returns:
        Rendered dashboard template with metrics
    """
    days = request.args.get('days', type=int)
    repository = request.args.get('repository', type=str)

    logger.info(f"Dashboard accessed: days={days}, repository={repository}")

    try:
        # Get metrics from database (with MTTR included via views)
        metrics = get_metrics_by_repository(repository=repository, days=days)
        repositories = get_available_repositories()

        logger.info(f"Loaded {len(metrics)} metrics with workflow-level MTTR")

        return render_template(
            'dashboard.html',
            metrics=metrics,
            repositories=repositories,
            selected_days=days,
            selected_repository=repository
        )

    except sqlite3.OperationalError:
        logger.error("Database not found or not initialized")
        return render_template(
            'error.html',
            error_message="Database not found. Please run 'cipette-collect' first."
        ), 500

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return render_template(
            'error.html',
            error_message="Failed to load dashboard metrics"
        ), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    try:
        return render_template('error.html', error_message="Page not found"), 404
    except Exception:
        return "Page not found", 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    try:
        return render_template('error.html', error_message="Internal server error"), 500
    except Exception:
        return "Internal server error", 500


# Main entry point
def main():
    """Main entry point for Flask application."""
    import os

    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))

    logger.info("Starting CIPette web dashboard...")
    logger.info(f"Access dashboard at: http://{host}:{port}")
    logger.info(f"Debug mode: {debug}")

    app.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    main()
