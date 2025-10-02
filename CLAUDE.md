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
# Install
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/novr/CIPette
cd CIPette
uv sync

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

## Success Criteria

- [x] Collects GitHub Actions data
- [x] Shows metrics in web interface
- [x] Filters work
- [x] Fast performance
- [ ] Useful insights from real data

**Philosophy**: Ship working software fast, optimize later.