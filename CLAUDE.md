# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CIPette** is a CI/CD Insights Dashboard that collects GitHub Actions workflow data and visualizes basic metrics (Duration, Success Rate, Throughput, MTTR) through a simple web interface.

**Architecture**: GitHub Actions API → Python (Flask) → SQLite → HTML Dashboard

## Technical Stack

- **Language**: Python 3
- **Web Framework**: Flask (lightweight, minimal setup)
- **Database**: SQLite (file-based, no configuration required)
- **UI**: Plain HTML/CSS (no frameworks, ~50 lines of CSS)
- **Execution**: Local development (no Docker required)

## Project Structure

```
cicd_dashboard/
├── app.py              # Main Flask application
├── data_collector.py   # GitHub API data collection
├── database.py         # SQLite database operations
├── config.py          # Configuration (API tokens, etc.)
├── templates/
│   └── dashboard.html  # Main dashboard template
└── static/
    └── style.css       # Minimal CSS styling
```

## Development Setup

### Installation
```bash
pip install flask requests
```

### Environment Variables
- Set `GITHUB_TOKEN` environment variable with Personal Access Token
- SQLite database file will be created automatically

### Running the Application
```bash
# Collect data from GitHub API
python data_collector.py

# Start web dashboard
python app.py
```

## Database Schema

```sql
-- Workflow basic information
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  repository TEXT,
  name TEXT
);

-- Execution history for metrics calculation
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT,
  commit_sha TEXT,
  branch TEXT,
  status TEXT,  -- 'success', 'failure', 'cancelled'
  started_at DATETIME,
  completed_at DATETIME
);
```

## Core Metrics Calculation

- **Duration**: `completed_at - started_at` average
- **Success Rate**: `success_count ÷ (success_count + failure_count) × 100` (cancelled runs excluded)
- **Throughput**: Completed runs per time period
- **MTTR**: Average time from failure to next success

## Design Principles

- **Simplicity First**: Minimal features, maximum functionality
- **No Frameworks**: Plain HTML/CSS, no Bootstrap/React/etc.
- **Table-Centric UI**: Data display via HTML tables with basic filtering
- **Local Development**: No containerization or complex deployment
- **1-Week MVP**: Goal to have working prototype in one week

## UI Implementation

- **Filtering**: Simple select boxes and text fields
- **Display**: HTML table with hover effects and color coding
- **Styling**: ~50 lines of CSS, white background, minimal decoration
- **Color Coding**: Green/red Success Rate visualization

## Data Flow

1. `data_collector.py` fetches data from GitHub Actions API
2. Data stored in SQLite via `database.py`
3. `app.py` serves Flask web interface
4. `dashboard.html` displays metrics in table format with filtering

## Success Criteria

- [ ] GitHub API data collection works
- [ ] SQLite stores data correctly
- [ ] Web page displays basic metrics
- [ ] Filtering functionality works
- [ ] Meaningful results from real repositories
- [ ] 1-week data shows trends
- [ ] Improvement areas can be identified

This project prioritizes practical value delivery over technical sophistication, focusing on rapid prototyping and immediate utility for CI/CD process improvement.