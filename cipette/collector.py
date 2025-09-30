import json
import logging
import os
from datetime import UTC, datetime

from github import (
    Auth,
    BadCredentialsException,
    Github,
    GithubException,
    RateLimitExceededException,
)

from cipette.config import GITHUB_TOKEN, MAX_WORKFLOW_RUNS, TARGET_REPOSITORIES
from cipette.database import (
    calculate_and_cache_all_metrics,
    initialize_database,
    insert_runs_batch,
    insert_workflow,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class GitHubDataCollector:
    """Collect workflow run data from GitHub Actions API using PyGithub."""

    LAST_RUN_FILE = 'last_run.json'

    def __init__(self):
        auth = Auth.Token(GITHUB_TOKEN)
        self.github = Github(auth=auth)

    def check_rate_limit(self):
        """Check and display current GitHub API rate limit status."""
        rate_limit = self.github.get_rate_limit()
        core = rate_limit.resources.core
        logger.info(f"API Rate Limit: {core.remaining}/{core.limit} (resets at {core.reset.strftime('%Y-%m-%d %H:%M:%S')})")

        # Warn if running low
        if core.remaining < 100:
            logger.warning(f"Only {core.remaining} API calls remaining!")

        return core.remaining

    def get_last_run_info(self):
        """Read last run information from file."""
        if not os.path.exists(self.LAST_RUN_FILE):
            return None

        try:
            with open(self.LAST_RUN_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read last run file: {e}")
            return None

    def save_last_run_info(self, repo_timestamps):
        """Save last run information to file.

        Args:
            repo_timestamps: Dict of {repo_name: ISO 8601 UTC timestamp}
        """
        last_run_info = {
            'timestamp': datetime.now(UTC).isoformat(),
            'repositories': repo_timestamps,
        }

        try:
            with open(self.LAST_RUN_FILE, 'w') as f:
                json.dump(last_run_info, f, indent=2)
        except OSError as e:
            logger.warning(f"Could not save last run file: {e}")

    def parse_datetime(self, dt):
        """Convert datetime to string format for SQLite."""
        if not dt:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def collect_repository_data(self, repo_name, since=None):
        """Collect all workflow and run data for a repository with idempotency.

        Args:
            repo_name: Repository name in format 'owner/repo'
            since: ISO 8601 datetime string to fetch runs created after this time
        """
        logger.info(f"Collecting data for repository: {repo_name}")
        if since:
            logger.info(f"Incremental update since: {since}")

        # Check rate limit before starting
        self.check_rate_limit()

        try:
            repo = self.github.get_repo(repo_name)
        except GithubException as e:
            logger.error(f"Error accessing repository {repo_name}: {e}")
            return 0, 0  # Return counts for tracking

        # Get all workflows with pagination
        workflows = repo.get_workflows()
        workflow_count = workflows.totalCount
        total_runs = 0
        logger.info(f"Found {workflow_count} workflows")

        # Use a single database connection for all workflow operations
        # Repository-level transaction: all or nothing
        from cipette.database import get_connection

        try:
            with get_connection() as conn:
                for workflow in workflows:
                    workflow_id = str(workflow.id)
                    workflow_name = workflow.name
                    workflow_path = workflow.path
                    workflow_state = workflow.state

                    logger.info(f"Processing workflow: {workflow_name} (ID: {workflow_id})")

                    # Save workflow to database using shared connection
                    insert_workflow(workflow_id, repo_name, workflow_name, workflow_path, workflow_state, conn=conn)

                    # Fetch workflow runs
                    try:
                        # Get runs with optional time filter
                        if since:
                            # For incremental updates, fetch all new runs without limit
                            runs_paginated = workflow.get_runs(created=f'>={since}')
                            runs = list(runs_paginated)
                        else:
                            # For full fetch, limit to MAX_WORKFLOW_RUNS
                            runs_paginated = workflow.get_runs()
                            runs = list(runs_paginated[:MAX_WORKFLOW_RUNS])

                        logger.info(f"Found {len(runs)} runs for workflow {workflow_id}")

                        # Prepare batch data
                        runs_data = []
                        for run in runs:
                            run_id = str(run.id)
                            run_number = run.run_number
                            commit_sha = run.head_sha
                            branch = run.head_branch
                            event = run.event
                            status = run.status
                            conclusion = run.conclusion

                            # Parse timestamps
                            started_at = self.parse_datetime(run.run_started_at or run.created_at)
                            completed_at = self.parse_datetime(run.updated_at if run.status == 'completed' else None)

                            # Calculate duration in seconds
                            duration_seconds = None
                            if run.run_started_at and run.updated_at and run.status == 'completed':
                                duration = run.updated_at - run.run_started_at
                                duration_seconds = int(duration.total_seconds())

                            # Get actor
                            actor = run.actor.login if run.actor else None

                            # Get URL
                            url = run.html_url

                            runs_data.append((
                                run_id, workflow_id, run_number, commit_sha, branch, event,
                                status, conclusion, started_at, completed_at, duration_seconds, actor, url
                            ))

                        # Batch insert all runs using shared connection
                        insert_runs_batch(runs_data, conn=conn)
                        total_runs += len(runs)
                        logger.info(f"Saved {len(runs)} runs to database for workflow {workflow_id}")

                    except GithubException as e:
                        logger.error(f"Error fetching runs for workflow {workflow_id}: {e}")
                        # Continue with other workflows, don't break the transaction
                        continue

                # Commit entire repository transaction
                conn.commit()
                logger.info(f"Successfully committed {workflow_count} workflows and {total_runs} runs")

        except Exception as e:
            # Context manager handles rollback automatically
            logger.error(f"Transaction rolled back for repository {repo_name}: {e}")
            raise  # Re-raise to notify caller

        return workflow_count, total_runs

    def collect_all_data(self):
        """Collect data for all configured repositories."""
        if not GITHUB_TOKEN:
            logger.error("GITHUB_TOKEN not found in environment variables")
            return

        if not TARGET_REPOSITORIES:
            logger.error("TARGET_REPOSITORIES not configured")
            logger.error("Please set TARGET_REPOSITORIES in .env file")
            logger.error("Example: TARGET_REPOSITORIES=owner/repo1,owner/repo2")
            return

        # Show last run info
        last_run = self.get_last_run_info()
        if last_run:
            logger.info("=" * 60)
            logger.info("Last data collection:")
            logger.info(f"  Timestamp: {last_run['timestamp']}")
            repos_info = last_run.get('repositories', {})
            if isinstance(repos_info, dict):
                logger.info("  Repositories:")
                for repo, ts in repos_info.items():
                    logger.info(f"    - {repo}: {ts}")
            else:
                # Old format compatibility
                logger.info(f"  Repositories: {', '.join(repos_info)}")
            logger.info("=" * 60)

        # Initialize database
        initialize_database()

        # Parse repository list
        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',') if r.strip()]

        if not repos:
            logger.error("No repositories configured")
            return

        logger.info(f"Starting data collection for {len(repos)} repository(ies)...")

        total_workflows = 0
        total_runs = 0
        repo_timestamps = {}

        for repo in repos:
            try:
                # Get last run timestamp for this repo (ISO 8601 UTC)
                since = None
                if last_run and isinstance(last_run.get('repositories'), dict):
                    since = last_run['repositories'].get(repo)

                # Collect data (may raise exceptions)
                start_time = datetime.now(UTC).isoformat()
                wf_count, run_count = self.collect_repository_data(repo, since=since)
                total_workflows += wf_count
                total_runs += run_count

                # Record timestamp for this repo (ISO 8601 UTC)
                repo_timestamps[repo] = start_time

            except BadCredentialsException:
                logger.error(f"Invalid GitHub credentials for {repo}")
                logger.error("Please check your GITHUB_TOKEN")
                break  # No point continuing with bad credentials

            except RateLimitExceededException as e:
                logger.error(f"GitHub API rate limit exceeded for {repo}")
                logger.error(f"Rate limit resets at: {e}")
                break  # Stop to avoid further rate limit violations

            except GithubException as e:
                logger.error(f"GitHub API error for {repo}: {e.status} - {e.data.get('message', 'Unknown error')}")
                logger.info(f"Skipping {repo}, continuing with next repository...")
                continue  # Try next repository

            except OSError as e:
                logger.error(f"File system error for {repo}: {e}")
                logger.info(f"Skipping {repo}, continuing with next repository...")
                continue  # Try next repository

            except Exception as e:
                # Catch database errors and other unexpected errors
                logger.error(f"Unexpected error collecting data for {repo}: {type(e).__name__}: {e}")
                logger.warning(f"Repository {repo} data collection failed and rolled back")
                logger.info("Continuing with next repository...")
                continue  # Try next repository

        logger.info("Data collection completed!")
        logger.info(f"Total workflows collected: {total_workflows}")
        logger.info(f"Total runs collected: {total_runs}")

        # Save this run info
        self.save_last_run_info(repo_timestamps)

        # Calculate and cache metrics for all repositories
        if total_runs > 0:
            logger.info("Calculating and caching metrics...")
            try:
                cached_count = calculate_and_cache_all_metrics()
                logger.info(f"Successfully cached {cached_count} metric entries")
            except Exception as e:
                logger.error(f"Error caching metrics: {e}")
                logger.warning("Metrics will be calculated on-demand")


def main():
    """Main entry point for the data collector."""
    collector = GitHubDataCollector()
    collector.collect_all_data()


if __name__ == '__main__':
    main()
