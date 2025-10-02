# CIPette 🧪

**Simple CI/CD dashboard for GitHub Actions**

Get insights from your CI/CD pipeline in 5 minutes, not 5 hours.

## What You Get

- 📊 **4 Key Metrics**: Duration, Success Rate, Throughput, MTTR
- 🔍 **Filtering**: By time period and repository
- ⚡ **Fast**: Cached data for quick loading
- 🎯 **Simple**: No complex setup required

## Quick Start

### 1. Install

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup (no venv needed!)
git clone https://github.com/novr/CIPette
cd CIPette
uv sync  # Creates virtual environment automatically
```

### 2. Configure

Create `.env` file:

```bash
# Get token from: https://github.com/settings/tokens
GITHUB_TOKEN=ghp_your_token_here

# Repositories to analyze
TARGET_REPOSITORIES=owner/repo1,owner/repo2
```

### 3. Run

```bash
# Collect data
uv run cipette-collect

# View dashboard
uv run cipette-web

# Open http://localhost:5000
```

## Requirements

- Python 3.11+
- GitHub token with `repo` scope
- uv (no venv needed - handles virtual environment automatically)
- 5 minutes of your time

## How It Works

1. **Collect**: Fetches workflow data from GitHub API
2. **Store**: Saves to local SQLite database
3. **Calculate**: Computes metrics with caching
4. **Display**: Shows results in simple web table

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint code
uv run ruff check cipette/ tests/

# Format code
uv run ruff format cipette/ tests/
```

## Project Structure

```
CIPette/
├── cipette/           # Main package
│   ├── app.py         # Web dashboard
│   ├── collector.py   # Data collection
│   ├── database.py    # SQLite operations
│   └── config.py      # Configuration
├── templates/         # HTML templates
├── static/           # CSS styles
└── tests/            # Test suite
```

## Performance

- **MTTR Cache**: Pre-computed for 10-10,000x speedup
- **Metrics Cache**: 1-minute TTL for fast loading
- **Incremental Updates**: Only fetch new data

## License

MIT