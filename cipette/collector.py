import json
import logging
import os
import sqlite3
import time
from datetime import UTC, datetime

import requests
from github import (
    Auth,
    BadCredentialsException,
    Github,
    GithubException,
    RateLimitExceededException,
)

from cipette.config import GITHUB_TOKEN, MAX_WORKFLOW_RUNS, TARGET_REPOSITORIES
from cipette.database import get_connection
from cipette.database import initialize_database, insert_runs_batch, insert_workflow

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('data/collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GitHubDataCollector:
    """Collect workflow run data from GitHub Actions API using PyGithub and GraphQL."""

    LAST_RUN_FILE = 'last_run.json'
    GRAPHQL_ENDPOINT = 'https://api.github.com/graphql'
    
    # GraphQL query for fetching repository workflows and runs
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

    def __init__(self):
        auth = Auth.Token(GITHUB_TOKEN)
        self.github = Github(auth=auth)
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {GITHUB_TOKEN}',
            'Content-Type': 'application/json',
        })

    def check_rate_limit(self):
        """Check and display current GitHub API rate limit status."""
        rate_limit = self.github.get_rate_limit()
        core = rate_limit.resources.core
        
        # Convert UTC reset time to local time
        reset_time_local = core.reset.astimezone()
        reset_time_str = reset_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        logger.info(f"API Rate Limit: {core.remaining}/{core.limit} (resets at {reset_time_str})")

        # Warn if running low
        if core.remaining < 100:
            logger.warning(f"Only {core.remaining} API calls remaining!")

        return core.remaining

    def wait_for_rate_limit_reset(self):
        """Wait for rate limit reset and display local time countdown."""
        rate_limit = self.github.get_rate_limit()
        core = rate_limit.resources.core
        
        if core.remaining > 0:
            return  # No need to wait
        
        # Calculate wait time
        reset_time = core.reset
        now = datetime.now(UTC)
        wait_seconds = int((reset_time - now).total_seconds()) + 1
        
        if wait_seconds <= 0:
            return
        
        # Convert reset time to local time
        reset_time_local = reset_time.astimezone()
        reset_time_str = reset_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        logger.warning(f"Rate limit exceeded! Waiting until {reset_time_str}")
        logger.info(f"Waiting {wait_seconds} seconds ({wait_seconds//60} minutes {wait_seconds%60} seconds)...")
        
        # Countdown display
        for remaining in range(wait_seconds, 0, -1):
            if remaining % 60 == 0 or remaining <= 10:  # Show every minute or last 10 seconds
                minutes = remaining // 60
                seconds = remaining % 60
                logger.info(f"Rate limit reset in {minutes}m {seconds}s...")
            time.sleep(1)
        
        logger.info("Rate limit reset! Continuing data collection...")

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

    def get_etag_for_repo(self, repo_name):
        """Get ETag for a specific repository."""
        last_run = self.get_last_run_info()
        if not last_run:
            return None
        
        repos_info = last_run.get('repositories', {})
        if not isinstance(repos_info, dict):
            # Old format compatibility - no ETag available
            return None
        
        repo_data = repos_info.get(repo_name, {})
        if isinstance(repo_data, dict):
            return repo_data.get('workflows_etag')
        else:
            # Old format - just timestamp string
            return None

    def save_etag_for_repo(self, repo_name, etag, timestamp):
        """Save ETag for a specific repository."""
        last_run = self.get_last_run_info() or {'repositories': {}}
        
        if repo_name not in last_run['repositories']:
            last_run['repositories'][repo_name] = {}
        
        last_run['repositories'][repo_name]['workflows_etag'] = etag
        last_run['repositories'][repo_name]['last_collected'] = timestamp
        
        self.save_last_run_info(last_run['repositories'])

    def make_graphql_request(self, query, variables, etag=None):
        """Make a GraphQL request to GitHub API with optional ETag."""
        headers = {}
        if etag:
            headers['If-None-Match'] = etag
        
        payload = {
            'query': query,
            'variables': variables
        }
        
        try:
            response = self.session.post(
                self.GRAPHQL_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 304:
                # Not Modified - no data changes
                return None, response.headers.get('ETag')
            elif response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return None, None
                return data['data'], response.headers.get('ETag')
            else:
                logger.error(f"GraphQL request failed: {response.status_code} - {response.text}")
                return None, None
                
        except requests.RequestException as e:
            logger.error(f"GraphQL request error: {e}")
            return None, None

    def collect_repository_data_graphql(self, repo_name, etag=None):
        """Collect repository data using GraphQL API."""
        owner, repo = repo_name.split('/')
        
        variables = {
            'owner': owner,
            'repo': repo,
            'first': 50  # Maximum workflows to fetch
        }
        
        logger.info(f"Fetching data for {repo_name} using GraphQL...")
        data, new_etag = self.make_graphql_request(
            self.WORKFLOWS_QUERY, 
            variables, 
            etag
        )
        
        if data is None and new_etag:
            # No changes (304 Not Modified)
            logger.info(f"No changes for {repo_name} (ETag: {new_etag})")
            return 0, 0, new_etag
        
        if not data:
            logger.error(f"Failed to fetch data for {repo_name}")
            return 0, 0, None
        
        repository = data.get('repository')
        if not repository:
            logger.error(f"Repository {repo_name} not found")
            return 0, 0, None
        
        workflows = repository.get('workflows', {}).get('nodes', [])
        logger.info(f"Found {len(workflows)} workflows for {repo_name}")
        
        # Process workflows and runs
        total_workflows = 0
        total_runs = 0
        
        with get_connection() as conn:
            for workflow in workflows:
                workflow_id = workflow['id']
                workflow_name = workflow['name']
                workflow_path = workflow.get('path')
                workflow_state = workflow.get('state')
                
                # Insert workflow
                insert_workflow(
                    workflow_id, repo_name, workflow_name, 
                    workflow_path, workflow_state, conn=conn
                )
                total_workflows += 1
                
                # Process runs
                runs = workflow.get('runs', {}).get('nodes', [])
                runs_data = []
                
                for run in runs:
                    run_id = run['id']
                    run_number = run['runNumber']
                    commit_sha = run.get('headSha')
                    branch = run.get('headBranch')
                    event = run.get('event')
                    status = run.get('status')
                    conclusion = run.get('conclusion')
                    
                    # Parse timestamps
                    started_at = self.parse_datetime(run.get('runStartedAt'))
                    completed_at = self.parse_datetime(run.get('updatedAt') if status == 'completed' else None)
                    
                    # Calculate duration
                    duration_seconds = None
                    if run.get('runStartedAt') and run.get('updatedAt') and status == 'completed':
                        start = datetime.fromisoformat(run['runStartedAt'].replace('Z', '+00:00'))
                        end = datetime.fromisoformat(run['updatedAt'].replace('Z', '+00:00'))
                        duration_seconds = int((end - start).total_seconds())
                    
                    # Get actor
                    actor = run.get('actor', {}).get('login') if run.get('actor') else None
                    url = run.get('url')
                    
                    runs_data.append((
                        run_id, workflow_id, run_number, commit_sha, branch, event,
                        status, conclusion, started_at, completed_at, duration_seconds, actor, url
                    ))
                
                # Batch insert runs
                if runs_data:
                    insert_runs_batch(runs_data, conn=conn)
                    total_runs += len(runs_data)
                    logger.info(f"Saved {len(runs_data)} runs for workflow {workflow_name}")
            
            conn.commit()
        
        logger.info(f"Successfully processed {total_workflows} workflows and {total_runs} runs for {repo_name}")
        return total_workflows, total_runs, new_etag

    def save_last_run_info(self, repo_data):
        """Save last run information to file.

        Args:
            repo_data: Dict of {repo_name: {'last_collected': timestamp, 'workflows_etag': etag}}
        """
        last_run_info = {
            'repositories': repo_data,
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
        try:
            workflows = repo.get_workflows()
            workflow_count = workflows.totalCount
            total_runs = 0
            logger.info(f"Found {workflow_count} workflows")
        except GithubException as e:
            logger.error(f"Error fetching workflows for repository {repo_name}: {e}")
            return 0, 0

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
                            runs_list = list(runs_paginated)
                            # Safely slice the list, handling empty lists
                            runs = runs_list[:MAX_WORKFLOW_RUNS] if runs_list else []

                        logger.info(f"Found {len(runs)} runs for workflow {workflow_id}")

                        # Prepare batch data
                        runs_data = []
                        for run in runs:
                            try:
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
                            except (AttributeError, TypeError, ValueError) as e:
                                logger.warning(f"Skipping malformed run data for workflow {workflow_id}: {e}")
                                continue

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

        # Check rate limit before starting
        remaining_calls = self.check_rate_limit()
        if remaining_calls < 50:
            logger.warning("Low API rate limit remaining. Consider running later.")
        
        # Wait for rate limit reset if needed
        self.wait_for_rate_limit_reset()

        total_workflows = 0
        total_runs = 0
        repo_timestamps = {}

        for repo in repos:
            try:
                # Get ETag for this repo
                etag = self.get_etag_for_repo(repo)

                # Collect data using REST API (fallback for now)
                start_time = datetime.now(UTC).isoformat()
                logger.info(f"Starting data collection for {repo}...")
                wf_count, run_count = self.collect_repository_data(repo, since=None)
                logger.info(f"Completed data collection for {repo}: {wf_count} workflows, {run_count} runs")
                total_workflows += wf_count
                total_runs += run_count

                # Record timestamp for this repo
                repo_timestamps[repo] = {
                    'last_collected': start_time,
                    'workflows_etag': None
                }
                
                # Check rate limit after each repository
                remaining_calls = self.check_rate_limit()
                if remaining_calls < 10:
                    logger.warning("Very low API rate limit. Stopping collection.")
                    break
                
                # Wait for rate limit reset if needed before next repository
                self.wait_for_rate_limit_reset()

            except BadCredentialsException:
                logger.error(f"Invalid GitHub credentials for {repo}")
                logger.error("Please check your GITHUB_TOKEN")
                break  # No point continuing with bad credentials

            except RateLimitExceededException as e:
                logger.error(f"GitHub API rate limit exceeded for {repo}")
                logger.error(f"Rate limit resets at: {e}")
                # Wait for rate limit reset before continuing
                self.wait_for_rate_limit_reset()
                continue  # Continue with next repository after waiting

            except GithubException as e:
                logger.error(f"GitHub API error for {repo}: {e.status} - {e.data.get('message', 'Unknown error')}")
                logger.info(f"Skipping {repo}, continuing with next repository...")
                continue  # Try next repository

            except OSError as e:
                logger.error(f"File system error for {repo}: {e}")
                logger.info(f"Skipping {repo}, continuing with next repository...")
                continue  # Try next repository
            
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    logger.warning(f"Database locked for {repo}, retrying in 5 seconds...")
                    time.sleep(5)
                    try:
                        wf_count, run_count = self.collect_repository_data(repo, since=None)
                        total_workflows += wf_count
                        total_runs += run_count
                        logger.info(f"Retry successful for {repo}: {wf_count} workflows, {run_count} runs")
                    except Exception as retry_e:
                        logger.error(f"Retry failed for {repo}: {retry_e}")
                        continue
                else:
                    logger.error(f"Database error for {repo}: {e}")
                    continue

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


def main():
    """Main entry point for the data collector."""
    collector = GitHubDataCollector()
    collector.collect_all_data()


if __name__ == '__main__':
    main()
