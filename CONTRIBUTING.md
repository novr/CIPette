# Contributing to CIPette

Thank you for your interest in contributing to CIPette! This document provides guidelines for contributing to the project.

## Development Setup

1. **Install uv** (fast Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/novr/CIPette
   cd CIPette
   uv sync --group dev
   ```

3. **Run tests**:
   ```bash
   uv run pytest
   ```

4. **Run linter**:
   ```bash
   uv run ruff check cipette/ tests/ --fix
   uv run ruff format cipette/ tests/
   ```

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning and changelog generation.

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **perf**: A performance improvement
- **refactor**: Code refactoring
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **test**: Adding or updating tests
- **build**: Build system changes
- **ci**: CI/CD changes
- **chore**: Maintenance tasks

### Examples

```bash
# New feature
git commit -m "feat: add health score caching system"

# Bug fix
git commit -m "fix: resolve MTTR calculation error"

# Breaking change
git commit -m "feat!: redesign dashboard UI

BREAKING CHANGE: The dashboard layout has been completely redesigned.
Old CSS classes are no longer supported."

# With scope
git commit -m "feat(database): add health score cache table"

# Multiple changes
git commit -m "feat: add new metrics

- Add throughput calculation
- Add MTTR metrics
- Update dashboard display"
```

### Breaking Changes

Use `!` after the type to indicate breaking changes:

```bash
git commit -m "feat!: change API response format"
```

## Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** and commit using conventional commits

3. **Run tests and linter**:
   ```bash
   uv run pytest
   uv run ruff check cipette/ tests/ --fix
   uv run ruff format cipette/ tests/
   ```

4. **Push your branch**:
   ```bash
   git push origin feat/your-feature-name
   ```

5. **Create a Pull Request** to main branch with a clear description

## Release Process

Releases are automatically generated based on commit messages:

- **feat** commits → Minor version bump (0.1.0 → 0.2.0)
- **fix** commits → Patch version bump (0.1.0 → 0.1.1)
- **feat!** or **BREAKING CHANGE** → Major version bump (0.1.0 → 1.0.0)

### Manual Release

If you need to trigger a release manually:

```bash
# Check what would be released
uv run semantic-release version --print

# Create a release
uv run semantic-release version
uv run semantic-release changelog
uv run semantic-release publish
```

## Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Write docstrings for all public functions
- Keep functions small and focused
- Use meaningful variable names

## Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for high test coverage
- Use descriptive test names

## Documentation

- Update documentation for new features
- Keep README.md up to date
- Add docstrings to new functions
- Update API documentation if needed

## Questions?

Feel free to open an issue or start a discussion if you have questions about contributing!
