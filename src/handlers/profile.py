"""Profile, login, and migration handlers for AgentPier generic profile system."""

import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from utils.response import success, error, unauthorized, too_many_requests
from utils.auth import authenticate, generate_api_key
from utils.rate_limit import (
    check_rate_limit,
    check_auth_failures,
    record_auth_failure,
    get_client_ip,
)

TABLE_NAME = os.environ.get("TABLE_NAME", "agentpier-dev")

# Username validation: 3-30 chars, lowercase alphanumeric + underscore
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")

# Password: 12-128 chars
MIN_PASSWORD_LEN = 12
MAX_PASSWORD_LEN = 128

# Profile field limits
MAX_DISPLAY_NAME = 50
MAX_DESCRIPTION = 500
MAX_CAPABILITIES = 20
MAX_CAPABILITY_LEN = 50
VALID_CONTACT_TYPES = {"mcp", "webhook", "http"}


def _get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def _hash_password(password: str) -> str:
    """Hash a password with argon2id. Falls back to bcrypt if argon2 unavailable."""
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
        return ph.hash(password)
    except ImportError:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash (argon2id or bcrypt)."""
    if password_hash.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
            return ph.verify(password_hash, password)
        except (ImportError, VerifyMismatchError):
            return False
    elif password_hash.startswith("$2"):
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except ImportError:
            return False
    return False


def _validate_username(username: str) -> str | None:
    """Validate username. Returns error message or None if valid."""
    if not username:
        return "username is required"
    if not USERNAME_RE.match(username):
        return "username must be 3-30 chars, lowercase alphanumeric + underscore"
    return None


def _validate_password(password: str) -> str | None:
    """Validate password. Returns error message or None if valid."""
    if not password:
        return "password is required"
    if len(password) < MIN_PASSWORD_LEN:
        return f"password must be at least {MIN_PASSWORD_LEN} characters"
    if len(password) > MAX_PASSWORD_LEN:
        return f"password must be at most {MAX_PASSWORD_LEN} characters"
    return None


def _validate_profile_fields(body: dict) -> tuple[dict, str | None]:
    """Validate and extract updatable profile fields. Returns (fields, error_msg)."""
    fields = {}

    if "display_name" in body:
        dn = body["display_name"]
        if dn is not None:
            dn = str(dn).strip()
            if len(dn) > MAX_DISPLAY_NAME:
                return {}, f"display_name max {MAX_DISPLAY_NAME} chars"
            fields["display_name"] = dn

    if "description" in body:
        desc = body["description"]
        if desc is not None:
            desc = str(desc).strip()
            if len(desc) > MAX_DESCRIPTION:
                return {}, f"description max {MAX_DESCRIPTION} chars"
            fields["description"] = desc

    if "capabilities" in body:
        caps = body["capabilities"]
        if not isinstance(caps, list):
            return {}, "capabilities must be a list"
        if len(caps) > MAX_CAPABILITIES:
            return {}, f"capabilities max {MAX_CAPABILITIES} items"
        for c in caps:
            if not isinstance(c, str) or len(c) > MAX_CAPABILITY_LEN:
                return {}, f"each capability must be a string of max {MAX_CAPABILITY_LEN} chars"
        fields["capabilities"] = caps

    if "contact_method" in body:
        cm = body["contact_method"]
        if cm is not None:
            if not isinstance(cm, dict):
                return {}, "contact_method must be an object"
            cm_type = cm.get("type")
            if cm_type not in VALID_CONTACT_TYPES:
                return {}, f"contact_method.type must be one of: {', '.join(sorted(VALID_CONTACT_TYPES))}"
            endpoint = cm.get("endpoint", "")
            if not endpoint or not isinstance(endpoint, str):
                return {}, "contact_method.endpoint is required"
            if not endpoint.startswith("https://"):
                return {}, "contact_method.endpoint must be an HTTPS URL"
            fields["contact_method"] = cm

    return fields, None


def _lookup_user_by_username(table, username: str) -> dict | None:
    """Look up a user record by username via GSI1."""
    # Try new USERNAME# prefix first, then legacy AGENT_NAME#
    for prefix in ("USERNAME#", "AGENT_NAME#"):
        resp = table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(f"{prefix}{username.lower()}"),
            Limit=1,
        )
        items = resp.get("Items", [])
        if items:
            # GSI returns projected item; fetch full record by PK
            item = items[0]
            pk = item.get("PK")
            if pk:
                full = table.get_item(Key={"PK": pk, "SK": "META"})
                return full.get("Item")
    return None


# REMOVED: _get_user_api_key_raw function (security fix - no raw API key storage)


# ============================================================
# POST /auth/login
# ============================================================

def login(event, context):
    """POST /auth/login — Authenticate with username + password, return success confirmation."""
    # Auth failure lockout
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    # Rate limit: 10 login attempts per IP per minute
    allowed, remaining, retry_after = check_rate_limit(event, "login", max_requests=20, window_seconds=60)
    if not allowed:
        return too_many_requests("Login rate limit exceeded", retry_after)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    username = body.get("username", "").strip().lower()
    password = body.get("password", "")

    if not username or not password:
        return error("username and password are required", "missing_fields")

    table = _get_table()

    # Look up user by username
    user = _lookup_user_by_username(table, username)
    if not user:
        record_auth_failure(event)
        return error("Invalid username or password", "auth_failed", 401)

    # Verify password
    password_hash = user.get("password_hash")
    if not password_hash:
        record_auth_failure(event)
        return error("Invalid username or password", "auth_failed", 401)

    if not _verify_password(password, password_hash):
        record_auth_failure(event)
        return error("Invalid username or password", "auth_failed", 401)

    user_id = user["user_id"]

    # Update last_active
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression="SET last_active = :now",
        ExpressionAttributeValues={":now": now},
    )

    # Return success without API key (security fix)
    return success({
        "user_id": user_id,
        "username": user.get("username"),
        "note": "API key was provided at registration. Use POST /auth/rotate-key to generate a new one if lost.",
    })


# ============================================================
# PATCH /auth/profile
# ============================================================

def update_profile(event, context):
    """PATCH /auth/profile — Update profile fields."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    fields, err = _validate_profile_fields(body)
    if err:
        return error(err, "validation_error")

    if not fields:
        return error("No valid fields to update", "no_fields")

    user_id = user["user_id"]
    now = datetime.now(timezone.utc).isoformat()
    table = _get_table()

    # Build update expression
    update_parts = ["updated_at = :now"]
    attr_values = {":now": now}

    for i, (key, val) in enumerate(fields.items()):
        placeholder = f":v{i}"
        update_parts.append(f"{key} = {placeholder}")
        attr_values[placeholder] = val

    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeValues=attr_values,
    )

    # Fetch updated profile
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "META"})
    updated = resp.get("Item", {})

    profile = {
        "user_id": updated.get("user_id"),
        "username": updated.get("username"),
        "display_name": updated.get("display_name", ""),
        "description": updated.get("description", ""),
        "capabilities": updated.get("capabilities", []),
        "contact_method": updated.get("contact_method"),
        "trust_score": float(updated.get("trust_score", 0)),
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at"),
    }

    return success({"updated": True, "profile": profile})


# ============================================================
# POST /auth/change-password
# ============================================================

def change_password(event, context):
    """POST /auth/change-password — Change password (requires current password)."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")

    if not current_password or not new_password:
        return error("current_password and new_password are required", "missing_fields")

    # Validate current password
    password_hash = user.get("password_hash")
    if not password_hash or not _verify_password(current_password, password_hash):
        record_auth_failure(event)
        return error("Current password is incorrect", "auth_failed", 401)

    # Validate new password
    pw_err = _validate_password(new_password)
    if pw_err:
        return error(pw_err, "validation_error")

    # Hash and store
    new_hash = _hash_password(new_password)
    now = datetime.now(timezone.utc).isoformat()
    table = _get_table()

    table.update_item(
        Key={"PK": f"USER#{user['user_id']}", "SK": "META"},
        UpdateExpression="SET password_hash = :ph, updated_at = :now",
        ExpressionAttributeValues={":ph": new_hash, ":now": now},
    )

    return success({"changed": True, "message": "Password updated."})


# ============================================================
# GET /agents/{username} — Public profile
# ============================================================

def get_public_profile(event, context):
    """GET /agents/{username} — Public agent profile (no auth required)."""
    username = (event.get("pathParameters") or {}).get("username", "").strip().lower()
    if not username:
        return error("username is required", "missing_username")

    table = _get_table()
    user = _lookup_user_by_username(table, username)

    if not user:
        return error("Agent not found", "not_found", 404)

    # Public fields only — no password_hash, api_key, IP, internal IDs
    profile = {
        "username": user.get("username") or user.get("agent_name"),
        "display_name": user.get("display_name", ""),
        "description": user.get("description", ""),
        "capabilities": user.get("capabilities", []),
        "contact_method": user.get("contact_method"),
        "created_at": user.get("created_at"),
        "last_active": user.get("last_active"),
        "trust_score": float(user.get("trust_score", 0)),
        "moltbook_verified": user.get("moltbook_verified", False),
        "moltbook_name": user.get("moltbook_name", ""),
        "listings_count": int(user.get("listings_count", 0)),
    }

    return success(profile)


# ============================================================
# POST /auth/migrate — Add username/password to legacy account
# ============================================================

def migrate(event, context):
    """POST /auth/migrate — Add username+password to an existing API-key-only account."""
    if check_auth_failures(event):
        return too_many_requests("Too many failed auth attempts. Try again in 5 minutes.", 300)

    user = authenticate(event)
    if not user:
        record_auth_failure(event)
        return unauthorized()

    # Check if already migrated (has username set)
    if user.get("username"):
        return error("Account already has a username. Migration is a one-time operation.", "already_migrated", 409)

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return error("Invalid JSON body", "invalid_body")

    username = body.get("username", "").strip().lower()
    password = body.get("password", "")

    # Validate username
    usr_err = _validate_username(username)
    if usr_err:
        return error(usr_err, "validation_error")

    # Validate password
    pw_err = _validate_password(password)
    if pw_err:
        return error(pw_err, "validation_error")

    table = _get_table()

    # Check username uniqueness (both USERNAME# and AGENT_NAME# prefixes)
    for prefix in ("USERNAME#", "AGENT_NAME#"):
        existing = table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(f"{prefix}{username}"),
            Limit=1,
        )
        if existing.get("Items"):
            return error("Username already taken", "username_taken", 409)

    # Hash password and update record
    password_hash = _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    user_id = user["user_id"]

    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": "META"},
        UpdateExpression="SET username = :u, password_hash = :ph, GSI1PK = :gsi1pk, updated_at = :now",
        ExpressionAttributeValues={
            ":u": username,
            ":ph": password_hash,
            ":gsi1pk": f"USERNAME#{username}",
            ":now": now,
        },
    )

    return success({
        "migrated": True,
        "username": username,
        "message": "Username and password added. You can now log in with username + password.",
    })
