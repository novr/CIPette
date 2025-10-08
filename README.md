# CIPette 🧪

**Simple CI/CD dashboard for GitHub Actions**

Get insights from your CI/CD pipeline in 5 minutes, not 5 hours.

## What You Get

- 🏥 **CI/CD Health Score**: Comprehensive 0-100 health assessment
- 📊 **4 Key Metrics**: Duration, Success Rate, Throughput, MTTR
- 🔍 **Filtering**: By time period and repository
- ⚡ **Fast**: Cached data for quick loading
- 🎯 **Simple**: No complex setup required
- 🛡️ **Robust**: Error handling and data quality assessment

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

Copy the example configuration and update with your values:

```bash
cp env.example .env
# Edit .env with your GitHub token and repositories
```

> 📋 **See `env.example` for all available configuration options**

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
3. **Calculate**: Computes metrics with robust error handling
4. **Assess**: Evaluates data quality and health scores
5. **Display**: Shows results with quality indicators

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
├── cipette/                    # Main package
│   ├── app.py                  # Web dashboard
│   ├── collector.py            # Data collection
│   ├── database.py             # SQLite operations
│   ├── health_calculator.py    # Health score calculation
│   ├── config.py               # Configuration
│   ├── error_handling.py       # Error handling utilities
│   └── retry.py                # Retry logic
├── templates/                  # HTML templates
├── static/                     # CSS styles
└── tests/                      # Test suite
```

## Features

### Health Score System
- **Comprehensive Assessment**: 0-100 health score based on 4 key metrics
- **Data Quality Indicators**: Visual indicators for data reliability
- **Error Handling**: Robust error handling with detailed logging
- **Warning System**: Alerts for data quality issues

### Performance
- **MTTR Cache**: Pre-computed for 10-10,000x speedup
- **Metrics Cache**: 1-minute TTL for fast loading
- **Incremental Updates**: Only fetch new data
- **Error Recovery**: Graceful handling of calculation failures

## Documentation

- **[User Guide](docs/USER_GUIDE.md)**: Complete user guide with best practices
- **[API Documentation](docs/API.md)**: Technical API reference
- **[Configuration](env.example)**: Configuration options

## License

MIT