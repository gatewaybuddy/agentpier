"""Tests for the AgentPier SDK."""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

import agentpier
from agentpier import (
    AgentPier,
    AgentPierClient,
    AgentPierError,
    AuthenticationError,
    ValidationError,
    RateLimitError,
    NotFoundError,
)
from agentpier.types import (
    UserProfile,
    AgentTrustScore,
    Challenge,
    RegistrationResult,
    Badge,
    Standards,
)


class TestAgentPierClient:
    """Test the core HTTP client."""

    def test_client_initialization(self):
        """Test client initialization with different parameters."""
        # Default initialization
        client = AgentPierClient()
        assert client.api_key is None
        assert client.base_url == "https://api.agentpier.org"

        # With API key
        client = AgentPierClient(api_key="ap_test_123")
        assert client.api_key == "ap_test_123"
        assert client.headers["X-API-Key"] == "ap_test_123"

        # Custom base URL
        client = AgentPierClient(base_url="https://staging.agentpier.org")
        assert client.base_url == "https://staging.agentpier.org"

    def test_set_api_key(self):
        """Test setting API key after initialization."""
        client = AgentPierClient()
        assert client.api_key is None

        client.set_api_key("ap_test_456")
        assert client.api_key == "ap_test_456"
        assert client.headers["X-API-Key"] == "ap_test_456"

    def test_build_url(self):
        """Test URL building."""
        client = AgentPierClient(base_url="https://api.agentpier.org")

        assert client._build_url("/auth/me") == "https://api.agentpier.org/auth/me"
        assert client._build_url("auth/me") == "https://api.agentpier.org/auth/me"
        assert (
            client._build_url("/trust/agents/123")
            == "https://api.agentpier.org/trust/agents/123"
        )

    @patch("requests.request")
    def test_successful_request(self, mock_request):
        """Test successful API request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        client = AgentPierClient(api_key="ap_test_123")
        result = client.get("/test")

        assert result == {"success": True}
        mock_request.assert_called_once()

    @patch("requests.request")
    def test_authentication_error(self, mock_request):
        """Test authentication error handling."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "unauthorized"}'
        mock_response.json.return_value = {
            "error": "unauthorized",
            "message": "Invalid API key",
        }
        mock_request.return_value = mock_response

        client = AgentPierClient(api_key="invalid_key")

        with pytest.raises(AuthenticationError) as exc_info:
            client.get("/auth/me")

        assert "Invalid API key" in str(exc_info.value)

    @patch("requests.request")
    def test_rate_limit_error(self, mock_request):
        """Test rate limit error handling."""
        # Mock 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.content = b'{"error": "rate_limited"}'
        mock_response.json.return_value = {"error": "rate_limited", "retry_after": 60}
        mock_request.return_value = mock_response

        client = AgentPierClient()

        with pytest.raises(RateLimitError) as exc_info:
            client.get("/auth/challenge")

        assert exc_info.value.retry_after == 60


class TestAgentPier:
    """Test the main AgentPier class."""

    def test_initialization(self):
        """Test AgentPier initialization."""
        ap = AgentPier(api_key="ap_test_123")

        assert ap.api_key == "ap_test_123"
        assert ap.base_url == "https://api.agentpier.org"
        assert hasattr(ap, "auth")
        assert hasattr(ap, "trust")
        assert hasattr(ap, "badges")
        assert hasattr(ap, "standards")
        assert hasattr(ap, "marketplace")
        assert hasattr(ap, "listings")

    @patch.dict("os.environ", {"AGENTPIER_API_KEY": "ap_env_123"})
    def test_env_var_api_key(self):
        """Test API key from environment variable."""
        ap = AgentPier()
        assert ap.api_key == "ap_env_123"

    def test_version_info(self):
        """Test version info method."""
        ap = AgentPier(api_key="ap_test_123")
        info = ap.version_info()

        assert "sdk_version" in info
        assert "python_version" in info
        assert "base_url" in info
        assert "has_api_key" in info
        assert info["has_api_key"] is True


class TestAuthMethods:
    """Test authentication methods."""

    @patch.object(AgentPierClient, "post")
    def test_request_challenge(self, mock_post):
        """Test requesting a registration challenge."""
        mock_post.return_value = {
            "challenge_id": "chall_123",
            "challenge": "What is 42 + 17?",
            "expires_in_seconds": 300,
        }

        ap = AgentPier()
        challenge = ap.auth.request_challenge("test_agent")

        assert isinstance(challenge, Challenge)
        assert challenge.challenge_id == "chall_123"
        assert challenge.challenge == "What is 42 + 17?"
        assert challenge.expires_in_seconds == 300

        mock_post.assert_called_once_with("/auth/challenge", {"username": "test_agent"})

    @patch.object(AgentPierClient, "post")
    def test_register(self, mock_post):
        """Test agent registration."""
        mock_post.return_value = {
            "user_id": "user_123",
            "username": "test_agent",
            "api_key": "ap_live_newkey123",
            "message": "Registration complete",
        }

        ap = AgentPier()
        result = ap.auth.register(
            username="test_agent",
            password="secure_pass",
            challenge_id="chall_123",
            answer=59,
        )

        assert isinstance(result, RegistrationResult)
        assert result.user_id == "user_123"
        assert result.username == "test_agent"
        assert result.api_key == "ap_live_newkey123"

    @patch.object(AgentPierClient, "get")
    def test_get_profile(self, mock_get):
        """Test getting user profile."""
        mock_get.return_value = {
            "user_id": "user_123",
            "username": "test_agent",
            "description": "Test agent",
            "trust_score": 75.5,
            "created_at": "2024-01-15T10:30:00+00:00",
            "moltbook_linked": True,
        }

        ap = AgentPier(api_key="ap_test_123")
        profile = ap.auth.get_profile()

        assert isinstance(profile, UserProfile)
        assert profile.user_id == "user_123"
        assert profile.username == "test_agent"
        assert profile.trust_score == 75.5
        assert profile.moltbook_linked is True


class TestTrustMethods:
    """Test trust scoring methods."""

    @patch.object(AgentPierClient, "get")
    def test_get_score(self, mock_get):
        """Test getting agent trust score."""
        mock_get.return_value = {
            "agent_id": "agent_123",
            "agent_name": "test_agent",
            "trust_score": 85.3,
            "trust_tier": "verified",
            "event_count": 42,
            "last_updated": "2024-01-15T14:30:00+00:00",
        }

        ap = AgentPier(api_key="ap_test_123")
        score = ap.trust.get_score("agent_123")

        assert isinstance(score, AgentTrustScore)
        assert score.agent_id == "agent_123"
        assert score.trust_score == 85.3
        assert score.trust_tier == "verified"
        assert score.event_count == 42

        mock_get.assert_called_once_with("/trust/agents/agent_123")

    @patch.object(AgentPierClient, "post")
    def test_report_task_completion(self, mock_post):
        """Test reporting task completion."""
        mock_post.return_value = {"status": "recorded"}

        ap = AgentPier(api_key="ap_test_123")
        result = ap.trust.report_task_completion(
            "agent_123", success=True, details="Completed successfully"
        )

        assert result["status"] == "recorded"
        mock_post.assert_called_once()

        # Check the call arguments
        call_args = mock_post.call_args
        assert call_args[0][0] == "/trust/agents/agent_123/events"
        assert call_args[0][1]["event_type"] == "task_completion"
        assert call_args[0][1]["outcome"] == "success"


class TestBadgeMethods:
    """Test badge methods."""

    @patch.object(AgentPierClient, "get")
    def test_get_badge(self, mock_get):
        """Test getting agent badge."""
        mock_get.return_value = {
            "badge_url": "https://api.agentpier.org/badges/agent_123.svg",
            "trust_level": "verified",
            "score": 85.3,
        }

        ap = AgentPier(api_key="ap_test_123")
        badge = ap.badges.get("agent_123")

        assert isinstance(badge, Badge)
        assert badge.trust_level == "verified"
        assert badge.score == 85.3
        assert "agent_123.svg" in badge.badge_url

    @patch.object(AgentPierClient, "get")
    def test_get_html_embed(self, mock_get):
        """Test getting HTML embed code."""
        mock_get.return_value = {
            "badge_url": "https://api.agentpier.org/badges/agent_123.svg",
            "trust_level": "verified",
            "score": 85.3,
        }

        ap = AgentPier(api_key="ap_test_123")
        html = ap.badges.get_html_embed("agent_123")

        assert "<img src=" in html
        assert "Trust Level: Verified" in html
        assert "Trust Score: 85.3" in html


class TestStandardsMethods:
    """Test standards methods."""

    @patch.object(AgentPierClient, "get")
    def test_current_standards(self, mock_get):
        """Test getting current standards."""
        mock_get.return_value = {
            "version": "1.0.0",
            "effective_date": "2026-03-04",
            "standards": {
                "agent": {
                    "version": "1.0.0",
                    "document_url": "/docs/certification-standards-v1.md",
                    "api_url": "/standards/agent",
                    "categories": [
                        "reliability",
                        "safety",
                        "transparency",
                        "accountability",
                    ],
                },
                "marketplace": {
                    "version": "1.0.0",
                    "document_url": "/docs/marketplace-standards-v1.md",
                    "api_url": "/standards/marketplace",
                    "dimensions": [
                        "data_quality",
                        "reporting_volume",
                        "fairness",
                        "integration_health",
                        "dispute_resolution",
                    ],
                },
            },
        }

        ap = AgentPier()
        standards = ap.standards.current()

        assert isinstance(standards, Standards)
        assert standards.version == "1.0.0"
        assert standards.effective_date == "2026-03-04"
        assert "agent" in standards.standards
        assert "marketplace" in standards.standards


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_client_function(self):
        """Test the client() convenience function."""
        ap = agentpier.client(api_key="ap_test_123")

        assert isinstance(ap, AgentPier)
        assert ap.api_key == "ap_test_123"

    def test_client_function_no_key(self):
        """Test client() function without API key."""
        ap = agentpier.client()

        assert isinstance(ap, AgentPier)


if __name__ == "__main__":
    pytest.main([__file__])
