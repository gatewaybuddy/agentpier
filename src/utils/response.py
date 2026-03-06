"""Standard API response helpers."""

import json
import os
import traceback
import uuid
from functools import wraps
from typing import Any

# Determine allowed origins based on stage
STAGE = os.environ.get("STAGE", "dev")
if STAGE == "prod":
    ALLOWED_ORIGINS = ["https://agentpier.org"]
else:
    ALLOWED_ORIGINS = [
        "https://agentpier.org",
        "http://localhost:3000",
        "http://localhost:8080",
    ]


def _cors_headers(origin: str = None) -> dict:
    """Common CORS headers."""
    # If origin is provided and in allowed list, use it; otherwise use first allowed origin
    allowed_origin = ALLOWED_ORIGINS[0]  # Default to first
    if origin and origin in ALLOWED_ORIGINS:
        allowed_origin = origin

    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed_origin,
    }


def success(body: Any, status_code: int = 200) -> dict:
    """Return a successful API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(body, default=str),
    }


def error(message: str, error_code: str, status_code: int = 400) -> dict:
    """Return an error API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(
            {
                "error": error_code,
                "message": message,
                "status": status_code,
            }
        ),
    }


def not_found(message: str = "Resource not found") -> dict:
    return error(message, "not_found", 404)


def unauthorized(
    message: str = "Invalid or missing API key. Register at POST /auth/register to get your API key.",
) -> dict:
    return error(message, "unauthorized", 401)


def missing_auth(
    message: str = "API key required. Add 'x-api-key' header with your API key from POST /auth/register.",
) -> dict:
    return error(message, "missing_auth", 401)


def invalid_auth(
    message: str = "Invalid API key. Check your key or register a new account at POST /auth/register.",
) -> dict:
    return error(message, "invalid_auth", 401)


def forbidden(message: str = "Access denied") -> dict:
    return error(message, "forbidden", 403)


def rate_limited(message: str = "Rate limit exceeded") -> dict:
    return error(message, "rate_limited", 429)


def too_many_requests(
    message: str = "Too many requests", retry_after: int = 60
) -> dict:
    """429 with Retry-After header."""
    headers = _cors_headers()
    headers["Retry-After"] = str(retry_after)
    return {
        "statusCode": 429,
        "headers": headers,
        "body": json.dumps(
            {
                "error": "rate_limited",
                "message": message,
                "status": 429,
                "retry_after": retry_after,
            }
        ),
    }


def handler(fn):
    """Decorator that wraps Lambda handlers with error logging and trace IDs."""

    @wraps(fn)
    def wrapper(event, context):
        trace_id = uuid.uuid4().hex[:12]
        try:
            return fn(event, context)
        except Exception as e:
            print(f"HANDLER_ERROR trace={trace_id} fn={fn.__name__} error={e}")
            traceback.print_exc()
            return {
                "statusCode": 500,
                "headers": _cors_headers(),
                "body": json.dumps(
                    {
                        "error": "internal_error",
                        "message": f"Internal error (trace: {trace_id})",
                        "trace_id": trace_id,
                        "status": 500,
                    }
                ),
            }

    return wrapper
