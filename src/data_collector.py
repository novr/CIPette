from github import Github, GithubException, Auth
from datetime import datetime
from config import GITHUB_TOKEN, TARGET_REPOSITORIES, MAX_WORKFLOW_RUNS
from database import initialize_database, insert_workflow, insert_runs_batch


class GitHubDataCollector:
    """Collect workflow run data from GitHub Actions API using PyGithub."""

    def __init__(self):
        auth = Auth.Token(GITHUB_TOKEN)
        self.github = Github(auth=auth)

    def parse_datetime(self, dt):
        """Convert datetime to string format for SQLite."""
        if not dt:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def collect_repository_data(self, repo_name):
        """Collect all workflow and run data for a repository."""
        print(f"\nCollecting data for repository: {repo_name}")

        try:
            repo = self.github.get_repo(repo_name)
        except GithubException as e:
            print(f"Error accessing repository {repo_name}: {e}")
            return

        # Get all workflows
        workflows = repo.get_workflows()
        print(f"Found {workflows.totalCount} workflows")

        for workflow in workflows:
            workflow_id = str(workflow.id)
            workflow_name = workflow.name

            print(f"  Processing workflow: {workflow_name} (ID: {workflow_id})")

            # Save workflow to database
            insert_workflow(workflow_id, repo_name, workflow_name)

            # Fetch workflow runs
            try:
                runs = workflow.get_runs()[:MAX_WORKFLOW_RUNS]
                print(f"    Found {len(runs)} runs")

                # Prepare batch data
                runs_data = []
                for run in runs:
                    run_id = str(run.id)
                    commit_sha = run.head_sha
                    branch = run.head_branch

                    # Map GitHub status/conclusion to our status
                    status = self._determine_status(run)

                    # Parse timestamps
                    started_at = self.parse_datetime(run.run_started_at or run.created_at)
                    completed_at = self.parse_datetime(run.updated_at if run.status == 'completed' else None)

                    runs_data.append((
                        run_id, workflow_id, commit_sha, branch,
                        status, started_at, completed_at
                    ))

                # Batch insert all runs
                insert_runs_batch(runs_data)
                print(f"    Saved {len(runs)} runs to database")

            except GithubException as e:
                print(f"    Error fetching runs for workflow {workflow_id}: {e}")
                continue

    def _determine_status(self, run):
        """Determine run status from GitHub API response."""
        conclusion = run.conclusion
        status = run.status

        if conclusion == 'success':
            return 'success'
        elif conclusion == 'failure':
            return 'failure'
        elif conclusion == 'cancelled':
            return 'cancelled'
        elif status == 'in_progress':
            return 'in_progress'
        else:
            return 'unknown'

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

        # Initialize database
        initialize_database()

        # Parse repository list
        repos = [r.strip() for r in TARGET_REPOSITORIES.split(',') if r.strip()]

        if not repos:
            print("Error: No repositories configured")
            return

        print(f"Starting data collection for {len(repos)} repository(ies)...")

        for repo in repos:
            try:
                self.collect_repository_data(repo)
            except Exception as e:
                print(f"Error collecting data for {repo}: {e}")

        print("\nData collection completed!")


if __name__ == '__main__':
    collector = GitHubDataCollector()
    collector.collect_all_data()