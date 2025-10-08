"""Tests for version management."""

import pytest
from cipette.version import get_version


def test_get_version():
    """Test version string retrieval."""
    version = get_version()
    assert isinstance(version, str)
    assert version == "0.1.0"


def test_version_format():
    """Test version format is valid."""
    version = get_version()
    # Should be in format X.Y.Z (or X.Y.Z-suffix for prereleases)
    import re
    assert re.match(r'^\d+\.\d+\.\d+(?:[.-].*)?$', version), f"Invalid version format: {version}"
