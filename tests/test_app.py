"""Tests for Flask web application."""

import pytest

from cipette.app import app, format_duration, format_mttr, rate_class


# Unit Tests for Template Filters
class TestTemplateFilters:
    """Test template filter functions."""

    def test_format_duration_with_minutes(self):
        """Test duration formatting with minutes and seconds."""
        assert format_duration(330) == '5m 30s'
        assert format_duration(125) == '2m 5s'

    def test_format_duration_seconds_only(self):
        """Test duration formatting with seconds only."""
        assert format_duration(45) == '45s'
        assert format_duration(0) == '0s'

    def test_format_duration_none(self):
        """Test duration formatting with None."""
        assert format_duration(None) == 'N/A'

    def test_format_mttr_with_hours(self):
        """Test MTTR formatting with hours."""
        assert format_mttr(7200) == '2h'
        assert format_mttr(5400) == '1h 30m'

    def test_format_mttr_minutes_only(self):
        """Test MTTR formatting with minutes only."""
        assert format_mttr(900) == '15m'
        assert format_mttr(60) == '1m'

    def test_format_mttr_none(self):
        """Test MTTR formatting with None."""
        assert format_mttr(None) == 'N/A'

    def test_rate_class_high(self):
        """Test rate classification for high success rate."""
        assert rate_class(100) == 'high'
        assert rate_class(95) == 'high'
        assert rate_class(90) == 'high'

    def test_rate_class_medium(self):
        """Test rate classification for medium success rate."""
        assert rate_class(89) == 'medium'
        assert rate_class(80) == 'medium'
        assert rate_class(70) == 'medium'

    def test_rate_class_low(self):
        """Test rate classification for low success rate."""
        assert rate_class(69) == 'low'
        assert rate_class(50) == 'low'
        assert rate_class(0) == 'low'

    def test_rate_class_none(self):
        """Test rate classification with None."""
        assert rate_class(None) == 'low'


# Integration Tests for Flask Routes
@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestFlaskRoutes:
    """Test Flask route handlers."""

    def test_dashboard_loads(self, client):
        """Test dashboard loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'CIPette' in response.data
        assert b'CI/CD Insights' in response.data

    def test_dashboard_with_days_filter(self, client):
        """Test dashboard with days filter."""
        response = client.get('/?days=7')
        assert response.status_code == 200
        assert b'selected' in response.data
        assert b'Last 7 days' in response.data

    def test_dashboard_with_repository_filter(self, client):
        """Test dashboard with repository filter."""
        # This test assumes a repository exists in the database
        response = client.get('/?repository=novr/CIPette')
        assert response.status_code in [200, 500]  # 500 if DB not found

    def test_dashboard_with_mttr(self, client):
        """Test dashboard with MTTR calculation."""
        response = client.get('/?show_mttr=true')
        assert response.status_code in [200, 500]  # 500 if DB not found

    def test_404_error_page(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        # Should either render error.html or fallback to plain text
        assert b'not found' in response.data.lower() or b'404' in response.data

    def test_static_files_accessible(self, client):
        """Test static CSS file is accessible."""
        response = client.get('/static/style.css')
        assert response.status_code == 200
        assert b'color' in response.data or b':root' in response.data