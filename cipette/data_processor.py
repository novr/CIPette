"""Data processing utilities for GitHub Actions data."""

import logging
from datetime import UTC, datetime
from typing import Any

from cipette.database import insert_runs_batch, insert_workflow

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes GitHub Actions data for database storage."""

    def __init__(self, max_workflow_runs: int = 10):
        """Initialize data processor.

        Args:
            max_workflow_runs: Maximum number of runs to process per workflow
        """
        self.max_workflow_runs = max_workflow_runs


    def process_workflows_from_rest(
        self, workflows, repository: str
    ) -> tuple[int, int]:
        """Process workflows data from REST API.

        Args:
            workflows: PyGithub workflows object
            repository: Repository name

        Returns:
            Tuple of (workflow_count, total_runs)
        """
        workflow_count = workflows.totalCount
        total_runs = 0

        logger.info(f'Processing {workflow_count} workflows from REST API')

        for workflow in workflows:
            workflow_id = workflow.id
            workflow_name = workflow.name
            workflow_path = workflow.path
            workflow_state = workflow.state

            # Insert workflow
            insert_workflow(
                workflow_id=workflow_id,
                repository=repository,
                name=workflow_name,
                path=workflow_path,
                state=workflow_state,
            )

            # Process runs
            try:
                runs = list(workflow.get_runs()[: self.max_workflow_runs])
                runs_data = self._process_runs_data_from_rest(runs, workflow_id)

                if runs_data:
                    insert_runs_batch(runs_data)
                    total_runs += len(runs_data)
                    logger.info(
                        f'Saved {len(runs_data)} runs to database for workflow {workflow_id}'
                    )

            except Exception as e:
                logger.warning(f'Error processing runs for workflow {workflow_id}: {e}')
                continue

        return workflow_count, total_runs

    def _process_runs_data(
        self, runs: list[dict[str, Any]], workflow_id: int
    ) -> list[tuple]:
        """Process runs data from GraphQL response.

        Args:
            runs: List of run data from GraphQL
            workflow_id: Workflow ID

        Returns:
            List of tuples for database insertion
        """
        runs_data = []

        for run in runs:
            try:
                run_id = int(run['id'])
                run_number = run['runNumber']
                commit_sha = run['headSha']
                branch = run['headBranch']
                event = run['event']
                status = run['status']
                conclusion = run.get('conclusion')

                # Parse timestamps
                created_at = self._parse_datetime(run['createdAt'])
                updated_at = self._parse_datetime(run['updatedAt'])

                # Calculate duration
                duration_seconds = None
                if created_at and updated_at and status == 'completed':
                    duration_seconds = int((updated_at - created_at).total_seconds())

                # Get actor
                actor = run.get('actor', {}).get('login', 'unknown')
                url = run.get('url', '')

                runs_data.append(
                    (
                        run_id,
                        workflow_id,
                        run_number,
                        commit_sha,
                        branch,
                        event,
                        status,
                        conclusion,
                        created_at,
                        updated_at,
                        duration_seconds,
                        actor,
                        url,
                    )
                )

            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f'Skipping malformed run data: {e}')
                continue

        return runs_data

    def _process_runs_data_from_rest(
        self, runs: list[Any], workflow_id: int
    ) -> list[tuple]:
        """Process runs data from REST API.

        Args:
            runs: List of PyGithub run objects
            workflow_id: Workflow ID

        Returns:
            List of tuples for database insertion
        """
        runs_data = []

        for run in runs:
            try:
                run_id = run.id
                run_number = run.run_number
                commit_sha = run.head_sha
                branch = run.head_branch
                event = run.event
                status = run.status
                conclusion = run.conclusion

                # Parse timestamps
                created_at = run.created_at
                updated_at = run.updated_at

                # Calculate duration
                duration_seconds = None
                if created_at and updated_at and status == 'completed':
                    duration_seconds = int((updated_at - created_at).total_seconds())

                # Get actor
                actor = run.actor.login if run.actor else 'unknown'
                url = run.html_url

                runs_data.append(
                    (
                        run_id,
                        workflow_id,
                        run_number,
                        commit_sha,
                        branch,
                        event,
                        status,
                        conclusion,
                        created_at,
                        updated_at,
                        duration_seconds,
                        actor,
                        url,
                    )
                )

            except (AttributeError, TypeError, ValueError) as e:
                logger.warning(f'Skipping malformed run data: {e}')
                continue

        return runs_data

    def _parse_datetime(self, datetime_str: str) -> datetime | None:
        """Parse datetime string from GraphQL response.

        Args:
            datetime_str: ISO datetime string

        Returns:
            Parsed datetime object or None
        """
        if not datetime_str:
            return None

        try:
            # Parse ISO format with timezone
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return dt.astimezone(UTC)
        except (ValueError, TypeError):
            return None

    def _datetime_to_string(self, dt: datetime | None) -> str | None:
        """Convert datetime to string format for SQLite.

        Args:
            dt: Datetime object

        Returns:
            String representation or None
        """
        if not dt:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
