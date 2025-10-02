import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_BASE_URL = 'https://api.github.com'

# Database Configuration
DATABASE_PATH = 'data/cicd_metrics.db'

# Target Repositories (comma-separated list)
# Example: 'owner/repo1,owner/repo2'
TARGET_REPOSITORIES = os.getenv('TARGET_REPOSITORIES', '')

# Data Collection Settings
MAX_WORKFLOW_RUNS = 100  # Maximum number of workflow runs to fetch per workflow

# MTTR Cache Settings
MTTR_REFRESH_INTERVAL = int(os.getenv('MTTR_REFRESH_INTERVAL', '300'))  # Seconds (default: 5 minutes)
