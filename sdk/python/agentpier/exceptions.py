"""Custom exceptions for the AgentPier SDK."""

from typing import Optional, Dict, Any


class AgentPierError(Exception):
    """Base exception for all AgentPier API errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details


class AuthenticationError(AgentPierError):
    """Raised when authentication fails (401)."""

    pass


class AuthorizationError(AgentPierError):
    """Raised when access is forbidden (403)."""

    pass


class NotFoundError(AgentPierError):
    """Raised when a resource is not found (404)."""

    pass


class ValidationError(AgentPierError):
    """Raised when request validation fails (400)."""

    pass


class ConflictError(AgentPierError):
    """Raised when there's a conflict (409) - e.g., username taken."""

    pass


class RateLimitError(AgentPierError):
    """Raised when rate limits are exceeded (429)."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(AgentPierError):
    """Raised for server errors (5xx)."""

    pass


class PaymentRequiredError(AgentPierError):
    """Raised when payment is required (402) - e.g., listing limit exceeded."""

    pass


class NetworkError(AgentPierError):
    """Raised when network/connection issues occur."""

    pass


class APIError(AgentPierError):
    """Raised for general API errors that don't fit other categories."""

    def __init__(self, response_data: Dict[str, Any], status_code: int):
        error_msg = response_data.get(
            "message", response_data.get("error", "Unknown API error")
        )
        error_code = response_data.get("error_code", response_data.get("error"))
        details = response_data.get("details")

        super().__init__(error_msg, error_code, status_code, details)
        self.response_data = response_data


def raise_for_status(response, response_data: Optional[Dict[str, Any]] = None):
    """Raise appropriate exception based on HTTP status code."""
    status_code = response.status_code

    if status_code < 400:
        return  # Success

    # Try to parse error details from response
    error_data = response_data or {}
    if not error_data:
        try:
            error_data = response.json()
        except:
            error_data = {
                "error": "Unknown error",
                "message": response.text or f"HTTP {status_code}",
            }

    message = error_data.get(
        "message", error_data.get("error", f"HTTP {status_code} error")
    )
    error_code = error_data.get("error_code", error_data.get("error"))
    details = error_data.get("details")

    # Map status codes to specific exceptions
    if status_code == 400:
        raise ValidationError(message, error_code, status_code, details)
    elif status_code == 401:
        raise AuthenticationError(message, error_code, status_code, details)
    elif status_code == 403:
        raise AuthenticationError(message, error_code, status_code, details)
    elif status_code == 404:
        raise NotFoundError(message, error_code, status_code, details)
    elif status_code == 409:
        raise ConflictError(message, error_code, status_code, details)
    elif status_code == 402:
        raise PaymentRequiredError(message, error_code, status_code, details)
    elif status_code == 429:
        retry_after = None
        if hasattr(response, "headers"):
            retry_after_header = response.headers.get("Retry-After")
            if retry_after_header:
                try:
                    retry_after = int(retry_after_header)
                except ValueError:
                    pass

        # Also check response data for retry_after
        if not retry_after and "retry_after" in error_data:
            retry_after = error_data.get("retry_after")

        raise RateLimitError(
            message,
            retry_after,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )
    elif status_code >= 500:
        raise ServerError(message, error_code, status_code, details)
    else:
        # Fallback for other 4xx errors
        raise APIError(error_data, status_code)
