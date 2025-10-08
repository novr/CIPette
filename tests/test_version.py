"""Tests for version management."""

from cipette.version import get_version


def test_get_version():
    """Test version string retrieval."""
    version = get_version()
    assert isinstance(version, str)
    assert version == "0.1.0"


def test_version_format():
    """Test version format is valid."""
    import re

    version = get_version()
    # Should be in format X.Y.Z (or X.Y.Z-suffix for prereleases)
    assert re.match(r'^\d+\.\d+\.\d+(?:[.-].*)?$', version), f"Invalid version format: {version}"
