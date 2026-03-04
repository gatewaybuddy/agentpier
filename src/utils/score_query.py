"""Internal score query helpers for the scoring engine.

WARNING: These functions access signals across ALL marketplaces.
They must NEVER be exposed via any public API endpoint.
Only the internal scoring engine (issue #42) should call these.
"""

import os

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Fields that identify the signal source — must be stripped before API responses
_SOURCE_FIELDS = {"marketplace_id", "PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"}


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def get_agent_signals_all_sources(agent_id: str, limit: int = 500) -> list:
    """INTERNAL ONLY: Query all signals for an agent across all marketplaces.

    Uses GSI1 (AGENT_SIGNALS#{agent_id}).
    Returns signals WITH marketplace_id for source weighting by the scoring engine.
    Must NEVER be exposed via any public API endpoint.

    Args:
        agent_id: The agent to query signals for.
        limit: Maximum number of signals to return (default 500).

    Returns:
        List of signal dicts including marketplace_id for scoring.
    """
    table = _get_table()
    signals = []

    query_kwargs = {
        "IndexName": "GSI1",
        "KeyConditionExpression": Key("GSI1PK").eq(f"AGENT_SIGNALS#{agent_id}"),
        "Limit": limit,
        "ScanIndexForward": False,  # newest first
    }

    response = table.query(**query_kwargs)
    for item in response.get("Items", []):
        # Only include actual signal records, not dedup records
        if item.get("PK", "").startswith("SIGNAL#"):
            signals.append(dict(item))

    return signals


def sanitize_signals_for_api(signals: list) -> list:
    """Strip source-identifying fields from signals before API responses.

    Removes marketplace_id and DynamoDB key fields so that public API
    consumers cannot determine which marketplace contributed each signal.

    Args:
        signals: List of raw signal dicts.

    Returns:
        List of sanitized signal dicts safe for public API responses.
    """
    sanitized = []
    for signal in signals:
        clean = {k: v for k, v in signal.items() if k not in _SOURCE_FIELDS}
        sanitized.append(clean)
    return sanitized
