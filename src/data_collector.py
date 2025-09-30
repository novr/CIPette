import json
import os
from datetime import datetime

from github import Auth, Github, GithubException

from config import GITHUB_TOKEN, MAX_WORKFLOW_RUNS, TARGET_REPOSITORIES
from database import initialize_database, insert_runs_batch, insert_workflow


class GitHubDataCollector:
    """Collect workflow run data from GitHub Actions API using PyGithub."""

    LAST_RUN_FILE = 'last_run.json'

    def __init__(self):
        auth = Auth.Token(GITHUB_TOKEN)
        self.github = Github(auth=auth)

    def get_last_run_info(self):
        """Read last run information from file."""
        if not os.path.exists(self.LAST_RUN_FILE):
            return None

        try:
            with open(self.LAST_RUN_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read last run file: {e}")
            return None

    def save_last_run_info(self, repo_timestamps, workflow_count, run_count):
        """Save last run information to file.

        Args:
            repo_timestamps: Dict of {repo_name: timestamp}
            workflow_count: Total workflows collected
            run_count: Total runs collected
        """
        last_run_info = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'repositories': repo_timestamps,
            'workflow_count': workflow_count,
            'run_count': run_count
        }

        try:
            with open(self.LAST_RUN_FILE, 'w') as f:
                json.dump(last_run_info, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save last run file: {e}")

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
        print(f"\nCollecting data for repository: {repo_name}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if since:
            print(f"Incremental update since: {since}")

        try:
            repo = self.github.get_repo(repo_name)
        except GithubException as e:
            print(f"Error accessing repository {repo_name}: {e}")
            return 0, 0  # Return counts for tracking

        # Get all workflows with pagination
        workflows = repo.get_workflows()
        workflow_count = workflows.totalCount
        total_runs = 0
        print(f"Found {workflow_count} workflows")

        for workflow in workflows:
            workflow_id = str(workflow.id)
            workflow_name = workflow.name
            workflow_path = workflow.path
            workflow_state = workflow.state

            print(f"  Processing workflow: {workflow_name} (ID: {workflow_id})")

            # Save workflow to database
            insert_workflow(workflow_id, repo_name, workflow_name, workflow_path, workflow_state)

            # Fetch workflow runs
            try:
                # Get runs with optional time filter
                if since:
                    runs_paginated = workflow.get_runs(created=f'>={since}')
                else:
                    runs_paginated = workflow.get_runs()

                runs = list(runs_paginated[:MAX_WORKFLOW_RUNS])
                print(f"    Found {len(runs)} runs")

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

                # Batch insert all runs
                insert_runs_batch(runs_data)
                total_runs += len(runs)
                print(f"    Saved {len(runs)} runs to database")

            except GithubException as e:
                print(f"    Error fetching runs for workflow {workflow_id}: {e}")
                continue

        return workflow_count, total_runs

    def collect_all_data(self):
        """Collect data for all configured repositories."""
        if not GITHUB_TOKEN:
            print("Error: GITHUB_TOKEN not found in environment variables")
            return

        if not TARGET_REPOSITORIES:
            print("Error: TARGET_REPOSITORIES not configured")
            print("Please set TARGET_REPOSITORIES in .env file")
            print("Example: TARGET_REPOSITORIES=owner/repo1,owner/repo2")
            return

        # Show last run info
        last_run = self.get_last_run_info()
        if last_run:
            print("=" * 60)
            print("Last data collection:")
            print(f"  Timestamp: {last_run['timestamp']}")
            repos_info = last_run.get('repositories', {})
            if isinstance(repos_info, dict):
                print("  Repositories:")
                for repo, ts in repos_info.items():
                    print(f"    - {repo}: {ts}")
            else:
                # Old format compatibility
                print(f"  Repositories: {', '.join(repos_info)}")
            print(f"  Workflows: {last_run['workflow_count']}")
            print(f"  Runs: {last_run['run_count']}")
            print("=" * 60)

        # Initialize database
        initialize_database()

        # Parse repository list
        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',') if r.strip()]

        if not repos:
            print("Error: No repositories configured")
            return

        print(f"Starting data collection for {len(repos)} repository(ies)...")

        total_workflows = 0
        total_runs = 0
        repo_timestamps = {}

        for repo in repos:
            try:
                # Get last run timestamp for this repo
                since = None
                if last_run and isinstance(last_run.get('repositories'), dict):
                    since = last_run['repositories'].get(repo)

                # Collect data
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                wf_count, run_count = self.collect_repository_data(repo, since=since)
                total_workflows += wf_count
                total_runs += run_count

                # Record timestamp for this repo
                repo_timestamps[repo] = start_time
            except Exception as e:
                print(f"Error collecting data for {repo}: {e}")

        print("\nData collection completed!")
        print(f"Total workflows collected: {total_workflows}")
        print(f"Total runs collected: {total_runs}")

        # Save this run info
        self.save_last_run_info(repo_timestamps, total_workflows, total_runs)


if __name__ == '__main__':
    collector = GitHubDataCollector()
    collector.collect_all_data()
