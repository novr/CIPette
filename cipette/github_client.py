"""GitHub API client for data collection."""

import logging
import time
from datetime import UTC, datetime

import requests
from github import (
    Auth,
    Github,
)

from cipette.config import Config
from cipette.retry import retry_api_call

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client with rate limit handling."""

    def __init__(self, token: str):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token
        """
        self.github = Github(auth=Auth.Token(token))
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Content-Type': 'application/json',
        })

    def check_rate_limit(self) -> int:
        """Check current API rate limit status.

        Returns:
            Number of remaining API calls
        """
        rate_limit = self.github.get_rate_limit()
        core = rate_limit.resources.core
        reset_time_local = core.reset.astimezone()
        reset_time_str = reset_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        logger.info(f"API Rate Limit: {core.remaining}/{core.limit} (resets at {reset_time_str})")

        if core.remaining < Config.GITHUB_RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning(f"Only {core.remaining} API calls remaining!")

        return core.remaining

    def wait_for_rate_limit_reset(self) -> None:
        """Wait for rate limit reset if exceeded."""
        rate_limit = self.github.get_rate_limit()
        core = rate_limit.resources.core

        if core.remaining > 0:
            return

        reset_time = core.reset
        now = datetime.now(UTC)
        wait_seconds = int((reset_time - now).total_seconds()) + 1

        if wait_seconds <= 0:
            return

        reset_time_local = reset_time.astimezone()
        reset_time_str = reset_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        logger.warning(f"Rate limit exceeded! Waiting until {reset_time_str}")
        logger.info(f"Waiting {wait_seconds} seconds ({wait_seconds//Config.GITHUB_RATE_LIMIT_DISPLAY_INTERVAL} minutes {wait_seconds%Config.GITHUB_RATE_LIMIT_DISPLAY_INTERVAL} seconds)...")

        for remaining in range(wait_seconds, 0, -1):
            if remaining % Config.GITHUB_RATE_LIMIT_DISPLAY_INTERVAL == 0 or remaining <= Config.GITHUB_RATE_LIMIT_DISPLAY_THRESHOLD:
                minutes = remaining // Config.GITHUB_RATE_LIMIT_DISPLAY_INTERVAL
                seconds = remaining % Config.GITHUB_RATE_LIMIT_DISPLAY_INTERVAL
                logger.info(f"Rate limit reset in {minutes}m {seconds}s...")
            time.sleep(1)

        logger.info("Rate limit reset! Continuing data collection...")

    @retry_api_call(max_retries=3)
    def make_graphql_request(self, query: str, variables: dict, etag: str = None) -> tuple[dict, str]:
        """Make a GraphQL request with conditional ETag support.

        Args:
            query: GraphQL query string
            variables: Query variables
            etag: Optional ETag for conditional request

        Returns:
            Tuple of (response_data, new_etag)
        """
        headers = self.session.headers.copy()
        if etag:
            headers['If-None-Match'] = etag

        payload = {
            'query': query,
            'variables': variables
        }

        try:
            response = self.session.post(
                Config.GITHUB_GRAPHQL_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=Config.GITHUB_API_TIMEOUT
            )

            if response.status_code == 304:
                logger.info("Data unchanged (304 Not Modified)")
                return None, etag

            response.raise_for_status()

            data = response.json()
            new_etag = response.headers.get('ETag', '').strip('"')

            if 'errors' in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                return None, None

            return data, new_etag

        except requests.RequestException as e:
            logger.error(f"GraphQL request error: {e}")
            return None, None

    def get_repository(self, repo_name: str) -> object:
        """Get repository object.

        Args:
            repo_name: Repository name in format 'owner/repo'

        Returns:
            Repository object
        """
        return self.github.get_repo(repo_name)

    def get_workflows_graphql(self, repo_name: str, etag: str = None) -> tuple[dict, str]:
        """Get workflows using GraphQL API.

        Args:
            repo_name: Repository name in format 'owner/repo'
            etag: Optional ETag for conditional request

        Returns:
            Tuple of (workflows_data, new_etag)
        """
        owner, repo = repo_name.split('/')

        variables = {
            'owner': owner,
            'repo': repo,
            'first': 50  # Maximum workflows to fetch
        }

        logger.info(f"Fetching data for {repo_name} using GraphQL...")
        return self.make_graphql_request(Config.WORKFLOWS_QUERY, variables, etag)
