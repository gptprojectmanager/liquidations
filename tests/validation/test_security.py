"""
Simple security tests for validation API.

KISS approach - test only essential security features.
"""

from fastapi.testclient import TestClient

from src.api.validation_app import app

client = TestClient(app)


class TestSecurityHeaders:
    """Test security headers are present."""

    def test_security_headers_present_in_response(self):
        """Security headers should be added to all responses."""
        response = client.get("/health")

        # Should have basic security headers
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers

    def test_x_frame_options_is_deny(self):
        """X-Frame-Options should be DENY to prevent clickjacking."""
        response = client.get("/health")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_content_type_options_is_nosniff(self):
        """X-Content-Type-Options should prevent MIME sniffing."""
        response = client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_headers_present(self):
        """Rate limit headers should be present in responses."""
        response = client.get("/health")

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_decreases_with_requests(self):
        """Remaining requests should decrease with each request."""
        response1 = client.get("/health")
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        response2 = client.get("/health")
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        # Remaining should decrease
        assert remaining2 < remaining1


class TestAPIEndpoints:
    """Test API endpoints are accessible (KISS)."""

    def test_health_endpoint_returns_200(self):
        """Health check should work."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "security" in data

    def test_root_endpoint_works(self):
        """Root endpoint should return API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data

    def test_health_check_includes_security_info(self):
        """Health check should include security configuration."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "security" in data
        security = data["security"]
        assert "rate_limiting" in security
        assert "security_headers" in security
