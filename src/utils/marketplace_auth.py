"""Marketplace authentication via X-Marketplace-Key header."""

import os

import boto3
from boto3.dynamodb.conditions import Key

from utils.auth import hash_key

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def authenticate_marketplace(event):
    """Authenticate marketplace by X-Marketplace-Key header.

    Returns marketplace profile dict or None.
    """
    headers = event.get("headers", {}) or {}
    api_key = headers.get("x-marketplace-key") or headers.get("X-Marketplace-Key")

    if not api_key:
        return None

    try:
        key_hash_val = hash_key(api_key)
        table = _get_table()

        # Look up key hash in GSI2
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"APIKEY#{key_hash_val}"),
        )

        items = response.get("Items", [])
        if not items:
            return None

        marketplace_id = items[0].get("marketplace_id")
        if not marketplace_id:
            return None

        # Get the full marketplace record
        mp_response = table.get_item(
            Key={"PK": f"MARKETPLACE#{marketplace_id}", "SK": "PROFILE"}
        )
        return mp_response.get("Item")
    except Exception:
        return None
