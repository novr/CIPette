import logging
from datetime import UTC, datetime

from cipette.config import Config

# Create Config instance for property access
config = Config()
from cipette.data_processor import DataProcessor
from cipette.database import initialize_database
from cipette.error_handling import (
    ConfigurationError,
    GitHubAPIError,
)
from cipette.etag_manager import ETagManager
from cipette.github_client import GitHubClient
from cipette.logging_config import setup_logging
from cipette.retry import retry_api_call

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)


class GitHubDataCollector:
    """Collect workflow run data from GitHub Actions API using PyGithub and GraphQL."""

    LAST_RUN_FILE = 'last_run.json'

    def __init__(self):
        """Initialize the data collector."""
        self.github_client = GitHubClient(config.GITHUB_TOKEN)
        self.data_processor = DataProcessor(config.MAX_WORKFLOW_RUNS)
        self.etag_manager = ETagManager(config.CACHE_FILE)

    def check_rate_limit(self) -> dict[str, int]:
        """Check and display current GitHub API rate limit status."""
        return self.github_client.check_rate_limit()

    def wait_for_rate_limit_reset(self) -> None:
        """Wait for rate limit reset and display local time countdown."""
        self.github_client.wait_for_rate_limit_reset()

    def get_last_run_info(self) -> dict[str, object] | None:
        """Read last run information from file."""
        return self.etag_manager.get_last_run_info()

    def get_etag_for_repo(self, repo_name: str) -> str | None:
        """Get ETag for a specific repository."""
        return self.etag_manager.get_etag_for_repo(repo_name)

    def save_etag_for_repo(self, repo_name: str, etag: str, timestamp: str) -> None:
        """Save ETag for a specific repository."""
        self.etag_manager.save_etag_for_repo(repo_name, etag, timestamp)

    def parse_datetime(self, dt: datetime | None) -> str | None:
        """Parse datetime object to string format.

        Args:
            dt: Datetime object to parse

        Returns:
            Formatted datetime string or None
        """
        if dt is None:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def save_last_run_info(self, repo_data: dict[str, object]) -> None:
        """Save last run information to file.

        Args:
            repo_data: Dict of {repo_name: {'last_collected': timestamp, 'workflows_etag': etag}}
        """
        self.etag_manager.save_last_run_info(repo_data)

    @retry_api_call(max_retries=3)
    def collect_repository_data(
        self, repo_name: str, since: str | None = None
    ) -> dict[str, object]:
        """Collect all workflow and run data for a repository with idempotency.

        Args:
            repo_name: Repository name in format 'owner/repo'
            since: ISO 8601 datetime string to fetch runs created after this time
        """
        logger.info(f'Collecting data for repository: {repo_name}')
        if since:
            logger.info(f'Incremental update since: {since}')

        # Check rate limit before starting
        remaining_calls = self.check_rate_limit()
        if remaining_calls < 10:
            logger.warning('Very low API rate limit. Stopping collection.')
            return 0, 0

        try:
            repo = self.github_client.get_repository(repo_name)
        except Exception as e:
            logger.error(f'Error accessing repository {repo_name}: {e}')
            return 0, 0  # Return counts for tracking

        # Get all workflows with pagination
        try:
            workflows = repo.get_workflows()
            workflow_count, total_runs = (
                self.data_processor.process_workflows_from_rest(workflows, repo_name)
            )
            logger.info(f'Found {workflow_count} workflows')
        except Exception as e:
            logger.error(f'Error fetching workflows for repository {repo_name}: {e}')
            return 0, 0

        return workflow_count, total_runs

    def collect_all_data(self) -> None:
        """Collect data for all configured repositories.

        Raises:
            ConfigurationError: If required configuration is missing
            GitHubAPIError: If GitHub API access fails
        """
        if not config.GITHUB_TOKEN:
            error_msg = 'GITHUB_TOKEN not found in environment variables'
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

        if not config.TARGET_REPOSITORIES:
            error_msg = 'TARGET_REPOSITORIES not configured'
            logger.error(error_msg)
            logger.error('Please set TARGET_REPOSITORIES in .env file')
            logger.error('Example: TARGET_REPOSITORIES=owner/repo1,owner/repo2')
            raise ConfigurationError(error_msg)

        # Show last run info
        last_run = self.get_last_run_info()
        if last_run:
            logger.info('=' * config.LOG_SEPARATOR_LENGTH)
            logger.info('Last data collection:')
            repos_info = last_run.get('repositories', {})
            if isinstance(repos_info, dict):
                logger.info('  Repositories:')
                for repo, ts in repos_info.items():
                    logger.info(f'    - {repo}: {ts}')
            else:
                # Old format compatibility
                logger.info(f'  Repositories: {", ".join(repos_info)}')
            logger.info('=' * config.LOG_SEPARATOR_LENGTH)

        try:
            # Initialize database
            initialize_database()
        except Exception as e:
            error_msg = f'Failed to initialize database: {e}'
            logger.error(error_msg, exc_info=True)
            raise ConfigurationError(error_msg) from e

        # Parse repository list
        repos = [r.strip() for r in config.TARGET_REPOSITORIES if r.strip()]

        if not repos:
            error_msg = 'No repositories configured'
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

        logger.info(f'Starting data collection for {len(repos)} repository(ies)...')

        try:
            # Check rate limit before starting
            remaining_calls = self.check_rate_limit()
            if remaining_calls < 50:
                logger.warning('Low API rate limit remaining. Consider running later.')

            # Wait for rate limit reset if needed
            self.wait_for_rate_limit_reset()
        except Exception as e:
            error_msg = f'Failed to check GitHub API rate limit: {e}'
            logger.error(error_msg, exc_info=True)
            raise GitHubAPIError(error_msg) from e

        total_workflows = 0
        total_runs = 0
        repo_timestamps = {}

        for repo in repos:
            start_time = datetime.now(UTC).isoformat()
            try:
                # Collect data using REST API
                logger.info(f'Starting data collection for {repo}...')
                wf_count, run_count = self.collect_repository_data(repo, since=None)
                logger.info(
                    f'Completed data collection for {repo}: {wf_count} workflows, {run_count} runs'
                )
                total_workflows += wf_count
                total_runs += run_count

                # Record timestamp for this repo
                repo_timestamps[repo] = {
                    'last_collected': start_time,
                }

                # Check rate limit after each repository
                try:
                    remaining_calls = self.check_rate_limit()
                    if remaining_calls < 10:
                        logger.warning('Very low API rate limit. Stopping collection.')
                        break

                    # Wait for rate limit reset if needed before next repository
                    self.wait_for_rate_limit_reset()
                except Exception as e:
                    logger.warning(f'Rate limit check failed for {repo}: {e}')
                    # Continue with next repository even if rate limit check fails

            except Exception as e:
                logger.error(f'Error for {repo}: {e}', exc_info=True)
                logger.info(f'Skipping {repo}, continuing with next repository...')
                repo_timestamps[repo] = {
                    'last_collected': start_time,
                    'error': str(e),
                }
                continue

        logger.info('Data collection completed!')
        logger.info(f'Total workflows collected: {total_workflows}')
        logger.info(f'Total runs collected: {total_runs}')

        # Save this run info
        self.save_last_run_info(repo_timestamps)


def main() -> None:
    """Main entry point for the data collector."""
    try:
        collector = GitHubDataCollector()
        collector.collect_all_data()
    except ConfigurationError as e:
        logger.error(f'Configuration error: {e}')
        logger.error('Please check your .env file and configuration settings.')
        raise
    except GitHubAPIError as e:
        logger.error(f'GitHub API error: {e}')
        logger.error('Please check your GitHub token and network connection.')
        raise
    except Exception as e:
        logger.error(f'Unexpected error during data collection: {e}', exc_info=True)
        raise


if __name__ == '__main__':
    main()
