"""API key authentication utilities."""

import hashlib
import os
import secrets

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash.
    
    Returns:
        (raw_key, key_hash) — raw_key is shown once, key_hash is stored.
    """
    raw_key = f"ap_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


def hash_key(raw_key: str) -> str:
    """Hash an API key for lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def authenticate(event: dict) -> dict | None:
    """Authenticate a request by API key.
    
    Returns the user record if valid, None if not.
    """
    headers = event.get("headers", {}) or {}
    # Support both X-API-Key header and Authorization: Bearer
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    
    if not api_key:
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
    
    if not api_key:
        return None
    
    try:
        key_hash = hash_key(api_key)
        
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)
        
        # Look up the key hash in GSI2 (api key index)
        response = table.query(
            IndexName="GSI2",
            KeyConditionExpression=Key("GSI2PK").eq(f"APIKEY#{key_hash}"),
        )
        
        items = response.get("Items", [])
        if not items:
            return None
        
        # Get the full user record
        user_id = items[0].get("user_id")
        if not user_id:
            return None
        
        user_response = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": "META"}
        )
        
        return user_response.get("Item")
    except Exception:
        return None
