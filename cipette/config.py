"""Configuration settings for CIPette application.

This module provides backward compatibility with the old Config class
while using the new TOML-based configuration system.
"""

from typing import Any, Dict, List

from .config_manager import get_config_manager


class Config:
    """Centralized configuration for CIPette application.
    
    This class provides backward compatibility while using the new TOML-based
    configuration system under the hood.
    """

    def __init__(self):
        """Initialize configuration manager."""
        self._config_manager = get_config_manager()

    @classmethod
    def create_instance(cls):
        """Create a new Config instance."""
        return cls()

    @property
    def DATABASE_PATH(self) -> str:
        return self._config_manager.get('database.path')

    @property
    def DATABASE_TIMEOUT(self) -> float:
        return self._config_manager.get('database.timeout')

    @property
    def DATABASE_BUSY_TIMEOUT(self) -> int:
        return self._config_manager.get('database.busy_timeout')

    @property
    def DATABASE_CACHE_SIZE(self) -> int:
        return self._config_manager.get('database.cache_size')

    @property
    def DATABASE_DEFAULT_TIMEOUT(self) -> float:
        return self._config_manager.get('database.default_timeout')

    @property
    def DATABASE_SUCCESS_RATE_MULTIPLIER(self) -> int:
        return self._config_manager.get('database.success_rate_multiplier')

    @property
    def DATABASE_CACHE_TTL_SECONDS(self) -> int:
        return self._config_manager.get('database.cache_ttl_seconds')

    @property
    def GITHUB_TOKEN(self) -> str:
        return self._config_manager.get_with_env_override('github.token', 'GITHUB_TOKEN')

    @property
    def GITHUB_API_BASE_URL(self) -> str:
        return self._config_manager.get('github.base_url')

    @property
    def GITHUB_API_TIMEOUT(self) -> int:
        return self._config_manager.get('github.timeout')

    @property
    def GITHUB_RATE_LIMIT_WARNING_THRESHOLD(self) -> int:
        return self._config_manager.get('github.rate_limit_warning_threshold')

    @property
    def GITHUB_RATE_LIMIT_STOP_THRESHOLD(self) -> int:
        return self._config_manager.get('github.rate_limit_stop_threshold')

    @property
    def GITHUB_RATE_LIMIT_DISPLAY_INTERVAL(self) -> int:
        return self._config_manager.get('github.rate_limit_display_interval')

    @property
    def GITHUB_RATE_LIMIT_DISPLAY_THRESHOLD(self) -> int:
        return self._config_manager.get('github.rate_limit_display_threshold')

    @property
    def MAX_WORKFLOW_RUNS(self) -> int:
        return self._config_manager.get_with_env_override(
            'data_collection.max_workflow_runs', 'MAX_WORKFLOW_RUNS', 10
        )

    @property
    def MAX_WORKFLOWS_PER_REPO(self) -> int:
        return self._config_manager.get('data_collection.max_workflows_per_repo')

    @property
    def RETRY_MAX_ATTEMPTS(self) -> int:
        return self._config_manager.get('data_collection.retry_max_attempts')

    @property
    def RETRY_DELAY(self) -> float:
        return self._config_manager.get('data_collection.retry_delay')

    @property
    def RETRY_BACKOFF_FACTOR(self) -> float:
        return self._config_manager.get('data_collection.retry_backoff_factor')

    @property
    def WEB_HOST(self) -> str:
        return self._config_manager.get('web.host')

    @property
    def WEB_PORT(self) -> int:
        return self._config_manager.get('web.port')

    @property
    def WEB_DEBUG(self) -> bool:
        return self._config_manager.get('web.debug')

    @property
    def WEB_DEFAULT_PORT(self) -> int:
        return self._config_manager.get('web.default_port')

    @property
    def MTTR_REFRESH_INTERVAL(self) -> int:
        return self._config_manager.get_with_env_override(
            'web.mttr_refresh_interval', 'MTTR_REFRESH_INTERVAL', 300
        )

    @property
    def MTTR_WORKER_INITIAL_DELAY(self) -> int:
        return self._config_manager.get('web.mttr_worker_initial_delay')

    @property
    def LOG_LEVEL(self) -> str:
        return self._config_manager.get('logging.level')

    @property
    def LOG_FORMAT(self) -> str:
        return self._config_manager.get('logging.format')

    @property
    def LOG_DATE_FORMAT(self) -> str:
        return self._config_manager.get('logging.date_format')

    @property
    def LOG_FILE(self) -> str:
        return self._config_manager.get('logging.file')

    @property
    def LOG_SEPARATOR_LENGTH(self) -> int:
        return self._config_manager.get('logging.separator_length')

    @property
    def TARGET_REPOSITORIES(self) -> List[str]:
        return self._config_manager.get_repositories_config()

    @property
    def CACHE_FILE(self) -> str:
        return self._config_manager.get('cache.file')

    @property
    def TIME_UNITS(self) -> List[tuple]:
        return self._config_manager.get('time_formatting.units')

    @property
    def SUCCESS_RATE_HIGH_THRESHOLD(self) -> int:
        return self._config_manager.get('success_rate.high_threshold')

    @property
    def SUCCESS_RATE_MEDIUM_THRESHOLD(self) -> int:
        return self._config_manager.get('success_rate.medium_threshold')

    @property
    def HEALTH_SCORE_WEIGHTS(self) -> Dict[str, float]:
        return self._config_manager.get('health_score.weights')

    @property
    def HEALTH_SCORE_EXCELLENT(self) -> int:
        return self._config_manager.get('health_score.excellent')

    @property
    def HEALTH_SCORE_GOOD(self) -> int:
        return self._config_manager.get('health_score.good')

    @property
    def HEALTH_SCORE_FAIR(self) -> int:
        return self._config_manager.get('health_score.fair')

    @property
    def HEALTH_SCORE_POOR(self) -> int:
        return self._config_manager.get('health_score.poor')

    @property
    def HEALTH_SCORE_DURATION_MAX_SECONDS(self) -> int:
        return self._config_manager.get('health_score.duration_max_seconds')

    @property
    def HEALTH_SCORE_MTTR_MAX_SECONDS(self) -> int:
        return self._config_manager.get('health_score.mttr_max_seconds')

    @property
    def HEALTH_SCORE_THROUGHPUT_MIN_DAYS(self) -> int:
        return self._config_manager.get('health_score.throughput_min_days')

    @property
    def SQLITE_JOURNAL_MODE(self) -> str:
        return self._config_manager.get('sqlite.journal_mode')

    @property
    def SQLITE_SYNCHRONOUS(self) -> str:
        return self._config_manager.get('sqlite.synchronous')

    @property
    def SQLITE_TEMP_STORE(self) -> str:
        return self._config_manager.get('sqlite.temp_store')

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings.

        Raises:
            ValueError: If required configuration is missing
        """
        config_manager = get_config_manager()
        config_manager.validate()

    @classmethod
    def get_database_config(cls) -> Dict[str, Any]:
        """Get database configuration as dictionary.

        Returns:
            Dictionary with database configuration
        """
        config_manager = get_config_manager()
        return config_manager.get_database_config()

    @classmethod
    def get_github_config(cls) -> Dict[str, Any]:
        """Get GitHub API configuration as dictionary.

        Returns:
            Dictionary with GitHub configuration
        """
        config_manager = get_config_manager()
        return config_manager.get_github_config()

    @classmethod
    def get_retry_config(cls) -> Dict[str, Any]:
        """Get retry configuration as dictionary.

        Returns:
            Dictionary with retry configuration
        """
        config_manager = get_config_manager()
        return config_manager.get_data_collection_config()

    @classmethod
    def get_web_config(cls) -> Dict[str, Any]:
        """Get web application configuration as dictionary.

        Returns:
            Dictionary with web configuration
        """
        config_manager = get_config_manager()
        return config_manager.get_web_config()

    @classmethod
    def get_logging_config(cls) -> Dict[str, Any]:
        """Get logging configuration as dictionary.

        Returns:
            Dictionary with logging configuration
        """
        config_manager = get_config_manager()
        return config_manager.get_logging_config()


# Create global Config instance for backward compatibility
_config_instance = Config()

# Backward compatibility - expose as module-level attributes
DATABASE_PATH = _config_instance.DATABASE_PATH
GITHUB_TOKEN = _config_instance.GITHUB_TOKEN
MAX_WORKFLOW_RUNS = _config_instance.MAX_WORKFLOW_RUNS
TARGET_REPOSITORIES = _config_instance.TARGET_REPOSITORIES
