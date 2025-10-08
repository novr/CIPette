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

Copy the example configuration files and update with your values:

```bash
# Copy environment variables (for sensitive data)
cp env.example .env
# Edit .env with your GitHub token

# Copy configuration file (for non-sensitive settings)
cp config.toml.example config.toml
# Edit config.toml with your repositories and settings
```

> 📋 **See `env.example` for environment variables and `config.toml.example` for all configuration options**

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
│   ├── retry.py                # Retry logic
│   └── version.py              # Version information
├── .github/workflows/          # GitHub Actions
│   ├── test.yml                # Tests and security scans
│   └── release.yml             # Automated releases
├── templates/                  # HTML templates
├── static/                     # CSS styles
├── tests/                      # Test suite
├── pyproject.toml              # Project configuration
├── CHANGELOG.md                # Auto-generated changelog
└── CONTRIBUTING.md             # Contribution guidelines
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

### Version Management
- **Automatic Semantic Versioning**: Based on conventional commits
- **GitHub Actions Integration**: Automated releases on push to main
- **Conventional Commits**: Automatic changelog generation
- **Quality Gates**: Tests, linting, and security scans

```bash
# Commit Convention (Automatic Versioning)
git commit -m "feat: add new feature"          # → Minor version bump
git commit -m "fix: resolve bug"               # → Patch version bump
git commit -m "feat!: breaking change"         # → Major version bump

# Manual Version Management
uv run python -c "from cipette.version import get_version; print(get_version())"  # Show current version
uv run semantic-release version --print        # Preview next version
uv run semantic-release changelog              # Generate changelog

# Release Process
# 1. Push conventional commits to main branch
# 2. GitHub Actions automatically:
#    - Runs tests and linting
#    - Determines version bump
#    - Creates git tag
#    - Generates changelog
#    - Creates GitHub release
```

## Documentation

- **[User Guide](docs/USER_GUIDE.md)**: Complete user guide with best practices
- **[API Documentation](docs/API.md)**: Technical API reference
- **[Configuration](env.example)**: Configuration options

## License

MIT