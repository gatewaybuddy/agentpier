"""Secure pagination cursor utilities with HMAC signing."""

import base64
import hashlib
import hmac
import json
import os
from typing import Dict, Optional


def _get_secret() -> str:
    """Get the HMAC secret from environment."""
    secret = os.environ.get("CURSOR_SECRET")
    if not secret:
        raise ValueError("CURSOR_SECRET environment variable is required")
    return secret


def sign_cursor(cursor_data: Dict) -> str:
    """Create a signed pagination cursor.
    
    Args:
        cursor_data: The DynamoDB LastEvaluatedKey dictionary
        
    Returns:
        Base64-encoded signed cursor string
    """
    # Convert to JSON string (deterministic ordering)
    json_str = json.dumps(cursor_data, sort_keys=True, default=str)
    
    # Create HMAC signature
    secret = _get_secret()
    signature = hmac.new(
        secret.encode('utf-8'),
        json_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Create signed payload: {data: ..., sig: ...}
    signed_payload = {
        "data": cursor_data,
        "sig": signature
    }
    
    # Base64 encode the entire payload
    payload_str = json.dumps(signed_payload, default=str)
    return base64.b64encode(payload_str.encode('utf-8')).decode('utf-8')


def verify_cursor(signed_cursor: str) -> Optional[Dict]:
    """Verify and decode a signed pagination cursor.
    
    Args:
        signed_cursor: Base64-encoded signed cursor string
        
    Returns:
        The original cursor data if signature is valid, None otherwise
    """
    try:
        # Decode from base64
        payload_str = base64.b64decode(signed_cursor).decode('utf-8')
        payload = json.loads(payload_str)
        
        # Extract data and signature
        if not isinstance(payload, dict) or "data" not in payload or "sig" not in payload:
            return None
        
        cursor_data = payload["data"]
        provided_sig = payload["sig"]
        
        # Recreate signature
        json_str = json.dumps(cursor_data, sort_keys=True, default=str)
        secret = _get_secret()
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            json_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        
        return cursor_data
        
    except Exception:
        return None