"""IP-based rate limiting using DynamoDB TTL."""

import os
import time

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def get_client_ip(event):
    """Extract client IP from API Gateway event."""
    identity = event.get("requestContext", {}).get("identity", {})
    return identity.get("sourceIp", "unknown")


def check_rate_limit(event, action, max_requests=10, window_seconds=60):
    """Check if client IP has exceeded rate limit.
    
    Returns (allowed: bool, remaining: int, retry_after: int)
    """
    ip = get_client_ip(event)
    table = _get_table()
    now = int(time.time())
    window_start = now - window_seconds

    pk = f"RATELIMIT#{ip}"
    sk = f"{action}#{now}"

    # Write this request
    table.put_item(Item={
        "PK": pk,
        "SK": sk,
        "ttl": now + window_seconds,  # Auto-cleanup via DynamoDB TTL
        "action": action,
        "timestamp": now,
    })

    # Count requests in window
    response = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": pk,
            ":start": f"{action}#{window_start}",
            ":end": f"{action}#{now + 1}",
        },
        Select="COUNT",
    )

    count = response.get("Count", 0)
    remaining = max(0, max_requests - count)
    
    if count > max_requests:
        retry_after = window_seconds - (now - window_start)
        return False, 0, retry_after

    return True, remaining, 0


def check_auth_failures(event, max_failures=5, window_seconds=300):
    """Check if IP has too many auth failures (5 min window).
    
    Returns True if blocked.
    """
    ip = get_client_ip(event)
    table = _get_table()
    now = int(time.time())
    window_start = now - window_seconds

    response = table.query(
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"AUTHFAIL#{ip}",
            ":start": f"FAIL#{window_start}",
            ":end": f"FAIL#{now + 1}",
        },
        Select="COUNT",
    )

    return response.get("Count", 0) >= max_failures


def record_auth_failure(event):
    """Record a failed auth attempt."""
    ip = get_client_ip(event)
    table = _get_table()
    now = int(time.time())

    table.put_item(Item={
        "PK": f"AUTHFAIL#{ip}",
        "SK": f"FAIL#{now}",
        "ttl": now + 300,  # 5 min TTL
        "timestamp": now,
    })
