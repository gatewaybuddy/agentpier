"""Standard API response helpers."""

import json
from typing import Any


def success(body: Any, status_code: int = 200) -> dict:
    """Return a successful API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def error(message: str, error_code: str, status_code: int = 400) -> dict:
    """Return an error API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "error": error_code,
            "message": message,
            "status": status_code,
        }),
    }


def not_found(message: str = "Resource not found") -> dict:
    return error(message, "not_found", 404)


def unauthorized(message: str = "API key required") -> dict:
    return error(message, "unauthorized", 401)


def forbidden(message: str = "Access denied") -> dict:
    return error(message, "forbidden", 403)


def rate_limited(message: str = "Rate limit exceeded") -> dict:
    return error(message, "rate_limited", 429)
