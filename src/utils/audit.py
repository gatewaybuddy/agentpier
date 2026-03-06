"""Audit logging for signal data access.

Append-only audit trail — no delete/update operations on audit records.
"""

import os
import uuid
from datetime import datetime, timezone

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def log_signal_access(
    accessor_id: str,
    accessor_type: str,
    agent_id: str,
    marketplace_id: str = None,
    action: str = "read",
    ip_address: str = None,
):
    """Log access to signal data for security audit trail.

    Args:
        accessor_id: ID of the entity accessing the data.
        accessor_type: One of "marketplace", "admin", "system".
        agent_id: The agent whose signals are being accessed.
        marketplace_id: The marketplace context (if applicable).
        action: The access action (e.g. "read", "ingest", "stats_query").
        ip_address: Client IP address.
    """
    now = datetime.now(timezone.utc).isoformat()
    entry_id = uuid.uuid4().hex

    item = {
        "PK": "AUDIT#SIGNAL_ACCESS",
        "SK": f"TS#{now}#{entry_id}",
        "audit_id": entry_id,
        "accessor_id": accessor_id,
        "accessor_type": accessor_type,
        "agent_id": agent_id,
        "action": action,
        "timestamp": now,
    }

    if marketplace_id:
        item["marketplace_id"] = marketplace_id
    if ip_address:
        item["ip_address"] = ip_address

    table = _get_table()
    table.put_item(Item=item)

    return entry_id
