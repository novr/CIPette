# CIPette 🧪

CI/CD Insights Dashboard - Collect and visualize GitHub Actions workflow metrics

## Features

- 📊 Collect GitHub Actions workflow data
- 💾 Store metrics in SQLite database
- 🔄 Incremental updates with timestamp tracking
- 🎯 Calculate key metrics: Duration, Success Rate, Throughput, MTTR

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- [mise](https://mise.jdx.dev/) (optional) - Runtime version manager

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Setup Project

```bash
# Clone repository
git clone https://github.com/novr/CIPette
cd CIPette

# Create virtual environment and install dependencies
uv sync --all-extras

# Configure environment
cp .env.example .env
# Edit .env and set GITHUB_TOKEN and TARGET_REPOSITORIES
```

### 3. Run Data Collection

```bash
# Run collector
uv run cipette-collect
```

### 4. Start Web Dashboard

```bash
# Start Flask web server
uv run cipette-web

# Access dashboard in your browser
open http://localhost:5000
```

## Development

### Install Development Dependencies

```bash
uv sync --all-extras
```

### Run Tests

```bash
# All tests (unit + integration)
uv run pytest

# Only unit tests
uv run pytest tests/test_data_collector.py tests/test_database.py

# Verbose output
uv run pytest -v
```

### Lint

```bash
uv run ruff check cipette/ tests/
```

### Format

```bash
uv run ruff format cipette/ tests/
```

## Project Structure

```
CIPette/
├── cipette/              # Main package
│   ├── __init__.py
│   ├── config.py         # Configuration
│   ├── database.py       # SQLite operations
│   └── collector.py      # GitHub API data collection
├── tests/                # Test suite
│   ├── test_database.py
│   ├── test_data_collector.py
│   └── test_integration.py
├── .mise.toml            # mise configuration
├── pyproject.toml        # Project metadata & dependencies
├── uv.lock               # Locked dependencies
└── README.md
```

## Environment Variables

Create a `.env` file with:

```bash
# GitHub Configuration
GITHUB_TOKEN=ghp_your_token_here
TARGET_REPOSITORIES=owner/repo1,owner/repo2

# Flask Configuration (optional)
FLASK_DEBUG=True
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

## Architecture

**Tech Stack:**
- Python 3.13+
- Flask (web framework)
- PyGithub (GitHub API client)
- SQLite (data storage)
- pytest (testing)
- ruff (linting)
- uv (package management)

**Data Flow:**
1. `collector.py` fetches data from GitHub Actions API
2. Data stored in SQLite via `database.py`
3. Incremental updates tracked in `last_run.json`
4. `app.py` serves web dashboard with metrics visualization

**Features:**
- 📊 Real-time metrics dashboard
- 🔍 Filter by period (7/30/90 days) and repository
- 📈 Success rate visualization with color coding
- ⏱️ Average duration and MTTR calculation
- 📱 Responsive design

## License

MIT