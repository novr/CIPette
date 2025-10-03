"""ETag management for GitHub API conditional requests."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ETagManager:
    """Manages ETag caching for GitHub API conditional requests."""

    def __init__(self, cache_file_path: str = 'data/last_run.json'):
        self.cache_file_path = Path(cache_file_path)
        self.cache_file_path.parent.mkdir(exist_ok=True)

    def get_etag_for_repo(self, repo_name: str) -> str | None:
        """Get ETag for a repository from cache.

        Args:
            repo_name: Repository name in format 'owner/repo'

        Returns:
            ETag string if found, None otherwise
        """
        last_run = self.get_last_run_info()
        if not last_run:
            return None

        repos_info = last_run.get('repositories', {})
        if not isinstance(repos_info, dict):
            return None

        repo_data = repos_info.get(repo_name, {})
        if isinstance(repo_data, dict):
            return repo_data.get('workflows_etag')
        else:
            return None

    def save_etag_for_repo(self, repo_name: str, etag: str, timestamp: str):
        """Save ETag for a repository to cache.

        Args:
            repo_name: Repository name in format 'owner/repo'
            etag: ETag string from API response
            timestamp: ISO timestamp string
        """
        last_run = self.get_last_run_info() or {'repositories': {}}

        if repo_name not in last_run['repositories']:
            last_run['repositories'][repo_name] = {}

        last_run['repositories'][repo_name]['workflows_etag'] = etag
        last_run['repositories'][repo_name]['last_collected'] = timestamp

        self.save_last_run_info(last_run['repositories'])

    def get_last_run_info(self) -> dict | None:
        """Get last run information from cache file.

        Returns:
            Dictionary with last run info or None if file doesn't exist
        """
        if not self.cache_file_path.exists():
            return None

        try:
            with open(self.cache_file_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f'Error reading last run info: {e}')
            return None

    def save_last_run_info(self, repo_data: dict):
        """Save last run information to cache file.

        Args:
            repo_data: Dictionary with repository data
        """
        last_run_info = {
            'repositories': repo_data,
        }

        try:
            with open(self.cache_file_path, 'w') as f:
                json.dump(last_run_info, f, indent=2)
        except OSError as e:
            logger.error(f'Error saving last run info: {e}')
