import logging
from datetime import UTC, datetime

from cipette.config import Config
from cipette.data_processor import DataProcessor
from cipette.database import initialize_database
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
        self.github_client = GitHubClient(Config.GITHUB_TOKEN)
        self.data_processor = DataProcessor(Config.MAX_WORKFLOW_RUNS)
        self.etag_manager = ETagManager(Config.CACHE_FILE)

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

    def make_graphql_request(
        self, query: str, variables: dict[str, object], etag: str | None = None
    ) -> tuple[dict[str, object], str]:
        """Make a GraphQL request to GitHub API with optional ETag."""
        return self.github_client.make_graphql_request(query, variables, etag)

    @retry_api_call(max_retries=3)
    def collect_repository_data_graphql(
        self, repo_name: str, etag: str | None = None
    ) -> dict[str, object]:
        """Collect repository data using GraphQL API."""
        logger.info(f'Fetching data for {repo_name} using GraphQL...')
        data, new_etag = self.github_client.get_workflows_graphql(repo_name, etag)

        if data is None:
            if new_etag:
                logger.info(f'No new data for {repo_name} (using cached ETag)')
                return 0, 0, new_etag
            else:
                logger.error(f'Failed to fetch data for {repo_name}')
                return 0, 0, None

        # Process the data using DataProcessor
        workflow_count, total_runs = self.data_processor.process_workflows_from_graphql(
            data, repo_name
        )

        return workflow_count, total_runs, new_etag

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
        """Collect data for all configured repositories."""
        if not Config.GITHUB_TOKEN:
            logger.error('GITHUB_TOKEN not found in environment variables')
            return

        if not Config.TARGET_REPOSITORIES:
            logger.error('TARGET_REPOSITORIES not configured')
            logger.error('Please set TARGET_REPOSITORIES in .env file')
            logger.error('Example: TARGET_REPOSITORIES=owner/repo1,owner/repo2')
            return

        # Show last run info
        last_run = self.get_last_run_info()
        if last_run:
            logger.info('=' * Config.LOG_SEPARATOR_LENGTH)
            logger.info('Last data collection:')
            repos_info = last_run.get('repositories', {})
            if isinstance(repos_info, dict):
                logger.info('  Repositories:')
                for repo, ts in repos_info.items():
                    logger.info(f'    - {repo}: {ts}')
            else:
                # Old format compatibility
                logger.info(f'  Repositories: {", ".join(repos_info)}')
            logger.info('=' * Config.LOG_SEPARATOR_LENGTH)

        # Initialize database
        initialize_database()

        # Parse repository list
        repos = [r.strip() for r in Config.TARGET_REPOSITORIES if r.strip()]

        if not repos:
            logger.error('No repositories configured')
            return

        logger.info(f'Starting data collection for {len(repos)} repository(ies)...')

        # Check rate limit before starting
        remaining_calls = self.check_rate_limit()
        if remaining_calls < 50:
            logger.warning('Low API rate limit remaining. Consider running later.')

        # Wait for rate limit reset if needed
        self.wait_for_rate_limit_reset()

        total_workflows = 0
        total_runs = 0
        repo_timestamps = {}

        for repo in repos:
            try:
                # Get ETag for this repo
                # etag = self.get_etag_for_repo(repo)  # TODO: Implement ETag support

                # Collect data using REST API (fallback for now)
                start_time = datetime.now(UTC).isoformat()
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
                    'workflows_etag': None,
                }

                # Check rate limit after each repository
                remaining_calls = self.check_rate_limit()
                if remaining_calls < 10:
                    logger.warning('Very low API rate limit. Stopping collection.')
                    break

                # Wait for rate limit reset if needed before next repository
                self.wait_for_rate_limit_reset()

            except Exception as e:
                logger.error(f'Unexpected error for {repo}: {e}')
                logger.info(f'Skipping {repo}, continuing with next repository...')
                continue  # Try next repository

        logger.info('Data collection completed!')
        logger.info(f'Total workflows collected: {total_workflows}')
        logger.info(f'Total runs collected: {total_runs}')

        # Save this run info
        self.save_last_run_info(repo_timestamps)


def main() -> None:
    """Main entry point for the data collector."""
    collector = GitHubDataCollector()
    collector.collect_all_data()


if __name__ == '__main__':
    main()
