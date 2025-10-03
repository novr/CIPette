"""Configuration settings for CIPette application."""

import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Centralized configuration for CIPette application."""

    # Database configuration
    DATABASE_PATH = "data/cicd_metrics.db"
    DATABASE_TIMEOUT = 60.0
    DATABASE_BUSY_TIMEOUT = 10000  # 10 seconds
    DATABASE_CACHE_SIZE = 1000
    DATABASE_DEFAULT_TIMEOUT = 30.0  # Default connection timeout
    DATABASE_SUCCESS_RATE_MULTIPLIER = 100  # For percentage calculation
    DATABASE_CACHE_TTL_SECONDS = 60  # Cache TTL in seconds

    # GitHub API configuration
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_API_BASE_URL = "https://api.github.com"
    GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
    GITHUB_API_TIMEOUT = 30
    GITHUB_RATE_LIMIT_WARNING_THRESHOLD = 100
    GITHUB_RATE_LIMIT_STOP_THRESHOLD = 10
    GITHUB_RATE_LIMIT_DISPLAY_INTERVAL = 60  # Display countdown every 60 seconds
    GITHUB_RATE_LIMIT_DISPLAY_THRESHOLD = 10  # Display countdown when <= 10 seconds

    # Data collection configuration
    MAX_WORKFLOW_RUNS = int(os.getenv("MAX_WORKFLOW_RUNS", "10"))
    MAX_WORKFLOWS_PER_REPO = 50
    RETRY_MAX_ATTEMPTS = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF_FACTOR = 2.0

    # Web application configuration
    WEB_HOST = "127.0.0.1"
    WEB_PORT = 5001
    WEB_DEBUG = True
    WEB_DEFAULT_PORT = 5000  # Default Flask port
    MTTR_REFRESH_INTERVAL = int(os.getenv("MTTR_REFRESH_INTERVAL", "300"))  # 5 minutes
    MTTR_WORKER_INITIAL_DELAY = 5  # Initial delay for MTTR worker in seconds

    # Logging configuration
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_FILE = "data/cipette.log"
    LOG_SEPARATOR_LENGTH = 60  # Length of separator line in logs

    # Target repositories
    TARGET_REPOSITORIES = os.getenv("TARGET_REPOSITORIES", "").split(",") if os.getenv("TARGET_REPOSITORIES") else [
        "yumemi/taka_app_v2_server",
        "yumemi/kadokawa-cw-front",
        "yumemi/kadokawa-cw-be",
        "yumemi/kao-skin-measure-front"
    ]

    # Cache configuration
    CACHE_FILE = "data/last_run.json"

    # GraphQL queries
    WORKFLOWS_QUERY = """
        query GetRepositoryWorkflows($owner: String!, $repo: String!, $first: Int!) {
          repository(owner: $owner, name: $repo) {
            name
            workflows(first: $first) {
              nodes {
                id
                name
                path
                state
                createdAt
                updatedAt
                runs(first: 100) {
                  nodes {
                    id
                    runNumber
                    headSha
                    headBranch
                    event
                    status
                    conclusion
                    runStartedAt
                    updatedAt
                    actor {
                      login
                    }
                    url
                  }
                }
              }
            }
          }
        }
    """

    # Time formatting constants
    TIME_UNITS = [
        ('h', 3600),  # hours
        ('m', 60),    # minutes
        ('s', 1)      # seconds
    ]

    # Success rate thresholds
    SUCCESS_RATE_HIGH_THRESHOLD = 90
    SUCCESS_RATE_MEDIUM_THRESHOLD = 70

    # SQLite PRAGMA settings
    SQLITE_JOURNAL_MODE = "WAL"
    SQLITE_SYNCHRONOUS = "NORMAL"
    SQLITE_TEMP_STORE = "MEMORY"

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings.

        Raises:
            ValueError: If required configuration is missing
        """
        if not cls.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        if cls.MAX_WORKFLOW_RUNS <= 0:
            raise ValueError("MAX_WORKFLOW_RUNS must be positive")

        if cls.RETRY_MAX_ATTEMPTS <= 0:
            raise ValueError("RETRY_MAX_ATTEMPTS must be positive")

    @classmethod
    def get_database_config(cls) -> dict:
        """Get database configuration as dictionary.

        Returns:
            Dictionary with database configuration
        """
        return {
            'path': cls.DATABASE_PATH,
            'timeout': cls.DATABASE_TIMEOUT,
            'busy_timeout': cls.DATABASE_BUSY_TIMEOUT,
            'cache_size': cls.DATABASE_CACHE_SIZE
        }

    @classmethod
    def get_github_config(cls) -> dict:
        """Get GitHub API configuration as dictionary.

        Returns:
            Dictionary with GitHub configuration
        """
        return {
            'token': cls.GITHUB_TOKEN,
            'base_url': cls.GITHUB_API_BASE_URL,
            'timeout': cls.GITHUB_API_TIMEOUT,
            'rate_limit_warning': cls.GITHUB_RATE_LIMIT_WARNING_THRESHOLD,
            'rate_limit_stop': cls.GITHUB_RATE_LIMIT_STOP_THRESHOLD
        }

    @classmethod
    def get_retry_config(cls) -> dict:
        """Get retry configuration as dictionary.

        Returns:
            Dictionary with retry configuration
        """
        return {
            'max_attempts': cls.RETRY_MAX_ATTEMPTS,
            'delay': cls.RETRY_DELAY,
            'backoff_factor': cls.RETRY_BACKOFF_FACTOR
        }

    @classmethod
    def get_web_config(cls) -> dict:
        """Get web application configuration as dictionary.

        Returns:
            Dictionary with web configuration
        """
        return {
            'host': cls.WEB_HOST,
            'port': cls.WEB_PORT,
            'debug': cls.WEB_DEBUG,
            'mttr_refresh_interval': cls.MTTR_REFRESH_INTERVAL
        }

    @classmethod
    def get_logging_config(cls) -> dict:
        """Get logging configuration as dictionary.

        Returns:
            Dictionary with logging configuration
        """
        return {
            'level': cls.LOG_LEVEL,
            'format': cls.LOG_FORMAT,
            'date_format': cls.LOG_DATE_FORMAT,
            'file': cls.LOG_FILE
        }


# Validate configuration on import
Config.validate()

# Backward compatibility
DATABASE_PATH = Config.DATABASE_PATH
GITHUB_TOKEN = Config.GITHUB_TOKEN
MAX_WORKFLOW_RUNS = Config.MAX_WORKFLOW_RUNS
TARGET_REPOSITORIES = Config.TARGET_REPOSITORIES
