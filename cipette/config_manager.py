"""Configuration management for CIPette application using TOML."""

import logging
import sys
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration settings from TOML file with environment variable overrides."""

    def __init__(self, config_file: str | None = None):
        """Initialize configuration manager.

        Args:
            config_file: Path to TOML configuration file. If None, uses default location.
        """
        if config_file is None:
            # Default to config.toml in project root
            project_root = Path(__file__).parent.parent
            config_file = project_root / 'config.toml'

        self.config_file = Path(config_file)
        self._config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from TOML file."""
        try:
            with open(self.config_file, 'rb') as f:
                self._config = tomllib.load(f)
        except FileNotFoundError:
            logger.warning(
                f'Configuration file not found: {self.config_file}. '
                'Please copy config.toml.example to config.toml and customize it.'
            )
            self._config = {}
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f'Invalid TOML configuration file: {e}') from e

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to configuration value (e.g., 'database.path')
            default: Default value if key is not found

        Returns:
            Configuration value or default

        Examples:
            >>> config.get('database.path')
            'data/cicd_metrics.db'
            >>> config.get('github.timeout', 30)
            30
        """
        keys = key_path.split('.')
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_database_config(self) -> dict[str, Any]:
        """Get database configuration.

        Returns:
            Dictionary with database configuration
        """
        return {
            'path': self.get('database.path'),
            'timeout': self.get('database.timeout'),
            'busy_timeout': self.get('database.busy_timeout'),
            'cache_size': self.get('database.cache_size'),
            'default_timeout': self.get('database.default_timeout'),
            'success_rate_multiplier': self.get('database.success_rate_multiplier'),
            'cache_ttl_seconds': self.get('database.cache_ttl_seconds'),
        }

    def get_github_config(self) -> dict[str, Any]:
        """Get GitHub API configuration.

        Returns:
            Dictionary with GitHub configuration
        """
        return {
            'token': self.get('github.token'),
            'base_url': self.get('github.base_url'),
            'timeout': self.get('github.timeout'),
            'rate_limit_warning': self.get('github.rate_limit_warning_threshold'),
            'rate_limit_stop': self.get('github.rate_limit_stop_threshold'),
            'rate_limit_display_interval': self.get(
                'github.rate_limit_display_interval'
            ),
            'rate_limit_display_threshold': self.get(
                'github.rate_limit_display_threshold'
            ),
        }

    def get_data_collection_config(self) -> dict[str, Any]:
        """Get data collection configuration.

        Returns:
            Dictionary with data collection configuration
        """
        return {
            'max_workflow_runs': self.get('data_collection.max_workflow_runs'),
            'max_workflows_per_repo': self.get(
                'data_collection.max_workflows_per_repo'
            ),
            'retry_max_attempts': self.get('data_collection.retry_max_attempts'),
            'retry_delay': self.get('data_collection.retry_delay'),
            'retry_backoff_factor': self.get('data_collection.retry_backoff_factor'),
        }

    def get_web_config(self) -> dict[str, Any]:
        """Get web application configuration.

        Returns:
            Dictionary with web configuration
        """
        return {
            'host': self.get('web.host'),
            'port': self.get('web.port'),
            'debug': self.get('web.debug'),
            'default_port': self.get('web.default_port'),
            'mttr_refresh_interval': self.get('web.mttr_refresh_interval'),
            'mttr_worker_initial_delay': self.get('web.mttr_worker_initial_delay'),
        }

    def get_logging_config(self) -> dict[str, Any]:
        """Get logging configuration.

        Returns:
            Dictionary with logging configuration
        """
        return {
            'level': self.get('logging.level'),
            'format': self.get('logging.format'),
            'date_format': self.get('logging.date_format'),
            'file': self.get('logging.file'),
            'separator_length': self.get('logging.separator_length'),
        }

    def get_repositories_config(self) -> list[str]:
        """Get target repositories configuration.

        Returns:
            List of target repository names
        """
        return self.get('repositories.targets', ['owner/repo1', 'owner/repo2'])

    def get_cache_config(self) -> dict[str, Any]:
        """Get cache configuration.

        Returns:
            Dictionary with cache configuration
        """
        return {
            'file': self.get('cache.file'),
        }

    def get_health_score_config(self) -> dict[str, Any]:
        """Get health score configuration.

        Returns:
            Dictionary with health score configuration
        """
        return {
            'weights': self.get('health_score.weights'),
            'excellent': self.get('health_score.excellent'),
            'good': self.get('health_score.good'),
            'fair': self.get('health_score.fair'),
            'poor': self.get('health_score.poor'),
            'duration_max_seconds': self.get('health_score.duration_max_seconds'),
            'mttr_max_seconds': self.get('health_score.mttr_max_seconds'),
            'throughput_min_days': self.get('health_score.throughput_min_days'),
        }

    def get_sqlite_config(self) -> dict[str, Any]:
        """Get SQLite configuration.

        Returns:
            Dictionary with SQLite configuration
        """
        return {
            'journal_mode': self.get('sqlite.journal_mode'),
            'synchronous': self.get('sqlite.synchronous'),
            'temp_store': self.get('sqlite.temp_store'),
        }

    def validate(self) -> None:
        """Validate configuration settings.

        Raises:
            ValueError: If required configuration is missing
        """
        # Skip validation in test environment
        if 'pytest' in sys.modules or 'test' in sys.argv:
            return

        github_token = self.get('github.token')
        if not github_token or github_token == 'ghp_your_token_here':
            raise ValueError(
                'GitHub token not configured. Please set github.token in config.toml'
            )

        target_repositories = self.get_repositories_config()
        if not target_repositories or target_repositories == [
            'owner/repo1',
            'owner/repo2',
        ]:
            raise ValueError(
                'Target repositories not configured. Please set repositories.targets in config.toml'
            )

        max_workflow_runs = self.get('data_collection.max_workflow_runs', 10)
        if max_workflow_runs <= 0:
            raise ValueError('max_workflow_runs must be positive')

        retry_max_attempts = self.get('data_collection.retry_max_attempts', 3)
        if retry_max_attempts <= 0:
            raise ValueError('retry_max_attempts must be positive')

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()

    def to_dict(self) -> dict[str, Any]:
        """Get all configuration as dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()


# Global configuration instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance.

    Returns:
        Global ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config() -> None:
    """Reload global configuration."""
    global _config_manager
    if _config_manager is not None:
        _config_manager.reload()
