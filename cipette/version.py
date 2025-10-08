"""Version information for CIPette.

This module provides version information for the CIPette project.
The version is automatically managed by python-semantic-release.
"""

import tomllib
from pathlib import Path
from typing import Any


def _get_pyproject_data() -> dict[str, Any]:
    """Get pyproject.toml data.

    Returns:
        Parsed TOML data
    """
    # Get project root (go up from cipette/ to project root)
    project_root = Path(__file__).parent.parent
    pyproject_file = project_root / 'pyproject.toml'

    with open(pyproject_file, 'rb') as f:
        return tomllib.load(f)


def _get_version_from_pyproject() -> str:
    """Get version from pyproject.toml.

    Returns:
        Version string from pyproject.toml
    """
    try:
        data = _get_pyproject_data()
        return data['project']['version']
    except (KeyError, FileNotFoundError) as e:
        raise ValueError(f'Version not found in pyproject.toml: {e}') from e


# Get version from pyproject.toml (managed by python-semantic-release)
__version__ = _get_version_from_pyproject()


def get_version() -> str:
    """Get current version string."""
    return __version__


if __name__ == '__main__':
    # Print version information when run directly
    print(f'CIPette version: {get_version()}')
