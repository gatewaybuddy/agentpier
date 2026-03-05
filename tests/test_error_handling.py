"""Tests for SDK error handling scenarios."""

import pytest
import requests_mock
from unittest.mock import Mock

from agentpier.client import AgentPierClient
from agentpier.exceptions import (
    AgentPierError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
    NetworkError,
    ConflictError,
    PaymentRequiredError
)


class TestSDKErrorHandling:
    """Test that the SDK properly maps HTTP error codes to exception types."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = AgentPierClient(api_key="ap_test_123456789abcdef")
    
    def test_authentication_error_401(self):
        """Test that 401 responses raise AuthenticationError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=401,
                json={
                    "error": "invalid_api_key",
                    "message": "Invalid API key provided"
                }
            )
            
            with pytest.raises(AuthenticationError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 401
            assert "Invalid API key provided" in str(exc_info.value)
    
    def test_authorization_error_403(self):
        """Test that 403 responses raise AuthenticationError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=403,
                json={
                    "error": "insufficient_permissions",
                    "message": "Insufficient permissions for this operation"
                }
            )
            
            with pytest.raises(AuthenticationError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 403
            assert "Insufficient permissions" in str(exc_info.value)
    
    def test_not_found_error_404(self):
        """Test that 404 responses raise NotFoundError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=404,
                json={
                    "error": "resource_not_found",
                    "message": "The requested resource was not found"
                }
            )
            
            with pytest.raises(NotFoundError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value)
    
    def test_validation_error_400(self):
        """Test that 400 responses raise ValidationError."""
        with requests_mock.Mocker() as m:
            m.post(
                "https://api.agentpier.org/test",
                status_code=400,
                json={
                    "error": "validation_failed",
                    "message": "Invalid request format",
                    "details": "Missing required field: name"
                }
            )
            
            with pytest.raises(ValidationError) as exc_info:
                self.client.post("/test", json_data={"invalid": "data"})
            
            assert exc_info.value.status_code == 400
            assert "Invalid request format" in str(exc_info.value)
            assert exc_info.value.details == "Missing required field: name"
    
    def test_rate_limit_error_429(self):
        """Test that 429 responses raise RateLimitError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=429,
                headers={"Retry-After": "60"},
                json={
                    "error": "rate_limit_exceeded",
                    "message": "Rate limit exceeded. Try again later.",
                    "retry_after": 60
                }
            )
            
            with pytest.raises(RateLimitError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 429
            assert exc_info.value.retry_after == 60
            assert "Rate limit exceeded" in str(exc_info.value)
    
    def test_server_error_500(self):
        """Test that 500 responses raise ServerError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=500,
                json={
                    "error": "internal_error",
                    "message": "Internal server error occurred"
                }
            )
            
            with pytest.raises(ServerError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 500
            assert "Internal server error" in str(exc_info.value)
    
    def test_server_error_502(self):
        """Test that 502 responses raise ServerError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=502,
                json={
                    "error": "bad_gateway",
                    "message": "Bad gateway error"
                }
            )
            
            with pytest.raises(ServerError) as exc_info:
                self.client.get("/test")
            
            assert exc_info.value.status_code == 502
    
    def test_conflict_error_409(self):
        """Test that 409 responses raise ConflictError."""
        with requests_mock.Mocker() as m:
            m.post(
                "https://api.agentpier.org/test",
                status_code=409,
                json={
                    "error": "conflict",
                    "message": "Resource already exists"
                }
            )
            
            with pytest.raises(ConflictError) as exc_info:
                self.client.post("/test", json_data={"name": "duplicate"})
            
            assert exc_info.value.status_code == 409
            assert "already exists" in str(exc_info.value)
    
    def test_payment_required_error_402(self):
        """Test that 402 responses raise PaymentRequiredError."""
        with requests_mock.Mocker() as m:
            m.post(
                "https://api.agentpier.org/test",
                status_code=402,
                json={
                    "error": "payment_required",
                    "message": "Payment required to access this feature"
                }
            )
            
            with pytest.raises(PaymentRequiredError) as exc_info:
                self.client.post("/test")
            
            assert exc_info.value.status_code == 402
            assert "Payment required" in str(exc_info.value)
    
    def test_network_error_connection_timeout(self):
        """Test that connection timeouts raise NetworkError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                exc=requests.exceptions.ConnectTimeout("Connection timed out")
            )
            
            with pytest.raises(NetworkError) as exc_info:
                self.client.get("/test")
            
            assert "timeout" in str(exc_info.value).lower()
    
    def test_network_error_connection_error(self):
        """Test that connection errors raise NetworkError."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                exc=requests.exceptions.ConnectionError("Failed to establish connection")
            )
            
            with pytest.raises(NetworkError) as exc_info:
                self.client.get("/test")
            
            assert "Connection error" in str(exc_info.value)
    
    def test_api_key_sanitization_in_error_messages(self):
        """Test that API keys are sanitized from error messages."""
        client = AgentPierClient(api_key="ap_live_1234567890abcdef1234567890abcdef")
        
        with requests_mock.Mocker() as m:
            # Mock an error that might contain the API key in the response
            m.get(
                "https://api.agentpier.org/test",
                status_code=401,
                json={
                    "error": "invalid_key",
                    "message": f"The API key ap_live_1234567890abcdef1234567890abcdef is invalid"
                }
            )
            
            with pytest.raises(AuthenticationError) as exc_info:
                client.get("/test")
            
            error_message = str(exc_info.value)
            # Should not contain the full API key
            assert "ap_live_1234567890abcdef1234567890abcdef" not in error_message
            # Should contain masked version
            assert "ap_live_****" in error_message or "1234567890abcdef****cdef" in error_message
    
    def test_invalid_api_key_format_validation(self):
        """Test that invalid API key formats are rejected."""
        # Test non-string API key
        with pytest.raises(AgentPierError) as exc_info:
            AgentPierClient(api_key=12345)
        assert "must be a string" in str(exc_info.value)
        
        # Test API key without ap_ prefix
        with pytest.raises(AgentPierError) as exc_info:
            AgentPierClient(api_key="invalid_key_format")
        assert "must start with 'ap_'" in str(exc_info.value)
        
        # Test invalid prefix
        with pytest.raises(AgentPierError) as exc_info:
            AgentPierClient(api_key="ap_invalid_prefix")
        assert "ap_live_" in str(exc_info.value) and "ap_test_" in str(exc_info.value)
    
    def test_valid_api_key_formats(self):
        """Test that valid API key formats are accepted."""
        # Test live key
        client_live = AgentPierClient(api_key="ap_live_1234567890abcdef")
        assert client_live.api_key == "ap_live_1234567890abcdef"
        
        # Test test key
        client_test = AgentPierClient(api_key="ap_test_1234567890abcdef")
        assert client_test.api_key == "ap_test_1234567890abcdef"
    
    def test_retry_logic_for_rate_limits(self):
        """Test that rate limits with short retry delays are retried."""
        with requests_mock.Mocker() as m:
            # First request: rate limited with short retry
            # Second request: success
            m.get(
                "https://api.agentpier.org/test",
                [
                    {
                        "status_code": 429,
                        "headers": {"Retry-After": "1"},
                        "json": {"error": "rate_limited", "message": "Rate limited"}
                    },
                    {
                        "status_code": 200,
                        "json": {"success": True}
                    }
                ]
            )
            
            # Should succeed after retry
            result = self.client.get("/test")
            assert result["success"] is True
    
    def test_retry_logic_for_server_errors(self):
        """Test that 5xx errors are retried."""
        with requests_mock.Mocker() as m:
            # First request: server error
            # Second request: success
            m.get(
                "https://api.agentpier.org/test",
                [
                    {
                        "status_code": 500,
                        "json": {"error": "server_error", "message": "Internal error"}
                    },
                    {
                        "status_code": 200,
                        "json": {"success": True}
                    }
                ]
            )
            
            # Should succeed after retry
            result = self.client.get("/test")
            assert result["success"] is True
    
    def test_no_retry_for_client_errors(self):
        """Test that 4xx errors (except 429) are not retried."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://api.agentpier.org/test",
                status_code=400,
                json={"error": "bad_request", "message": "Bad request"}
            )
            
            with pytest.raises(ValidationError):
                self.client.get("/test")
            
            # Should only have made one request (no retry)
            assert m.call_count == 1