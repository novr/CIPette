# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**CIPette** is a simple CI/CD dashboard that collects GitHub Actions data and shows basic metrics.

**Goal**: Get CI/CD insights in 5 minutes, not 5 hours.

## What It Does

- Fetches GitHub Actions workflow data
- Calculates 4 key metrics: Duration, Success Rate, Throughput, MTTR
- Shows data in a simple web table
- Filters by time period and repository

## Tech Stack

- **Python 3.11+** with Flask
- **SQLite** database (no setup required)
- **uv** for package management
- **PyGithub** for GitHub API

## Quick Start

```bash
# Install (no venv needed!)
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/novr/CIPette
cd CIPette
uv sync  # Creates virtual environment automatically

# Setup
echo "GITHUB_TOKEN=your_token" > .env
echo "TARGET_REPOSITORIES=owner/repo" >> .env

# Run
uv run cipette-collect  # Get data
uv run cipette-web      # View dashboard
```

## Project Structure

```
cipette/
├── app.py          # Web dashboard
├── collector.py    # GitHub data collection
├── database.py     # SQLite operations
└── config.py       # Settings
```

## Key Features

- **Simple**: No complex setup, just run and go
- **Fast**: Cached metrics for quick loading
- **Focused**: Only essential CI/CD metrics
- **Local**: No cloud dependencies

## Development Guidelines

### Code Quality
- **Always run linter before commit**: `uv run ruff check cipette/ tests/ --fix`
- Use `--unsafe-fixes` if needed: `uv run ruff check cipette/ tests/ --fix --unsafe-fixes`
- Ensure all checks pass: `uv run ruff check cipette/ tests/`
- Follow PEP 8 style guidelines
- Use type hints consistently

### Commit Process
1. Make code changes
2. Run linter: `uv run ruff check cipette/ tests/ --fix`
3. Fix any remaining issues manually
4. Verify all checks pass: `uv run ruff check cipette/ tests/`
5. Commit with descriptive message

## Success Criteria

- [x] Collects GitHub Actions data
- [x] Shows metrics in web interface
- [x] Filters work
- [x] Fast performance
- [x] Code quality maintained with linting
- [ ] Useful insights from real data

**Philosophy**: Ship working software fast, optimize later.