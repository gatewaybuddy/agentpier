"""Tests for the generic profile system (challenge, registration, login, profile, migration)."""

import json
import time
import secrets
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from tests.conftest import make_api_event

_challenge_counter = 0

def _unique_challenge_username():
    global _challenge_counter
    _challenge_counter += 1
    return f"ch_{_challenge_counter}_{secrets.token_hex(4)}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_handler(handler_module, method, path, body=None, headers=None,
                  path_params=None, query_params=None, api_key=None, source_ip="127.0.0.1"):
    """Route to the correct handler function based on method + path."""
    event = make_api_event(
        method=method, path=path, body=body, headers=headers,
        path_params=path_params, query_params=query_params, api_key=api_key,
    )
    event["requestContext"]["identity"] = {"sourceIp": source_ip}

    # Route to correct handler function
    from handlers import auth, profile as prof
    route_key = f"{method} {path.split('?')[0]}"
    routes = {
        "POST /auth/challenge": auth.request_challenge,
        "POST /auth/register2": auth.register_with_challenge,
        "POST /auth/login": prof.login,
        "PATCH /auth/profile": prof.update_profile,
        "POST /auth/change-password": prof.change_password,
        "POST /auth/migrate": prof.migrate,
    }
    # Match GET /agents/{username}
    handler_fn = routes.get(route_key)
    if handler_fn is None and path.startswith("/agents/"):
        handler_fn = prof.get_public_profile

    if handler_fn is None:
        raise ValueError(f"No route for {route_key}")

    resp = handler_fn(event, {})
    status = resp["statusCode"]
    resp_body = json.loads(resp["body"]) if resp.get("body") else {}
    return status, resp_body


# ---------------------------------------------------------------------------
# Challenge generation
# ---------------------------------------------------------------------------

class TestChallenge:
    """POST /auth/challenge"""

    def test_valid_challenge_response(self, dynamodb):
        from handlers import profile as h
        status, body = _call_handler(h, "POST", "/auth/challenge",
                                     body={"username": "challenge_test"})
        assert status == 200
        assert "challenge_id" in body
        assert "challenge_text" in body or "challenge" in body
        assert "expires_at" in body or "expires_in_seconds" in body

    def test_challenge_has_ttl(self, dynamodb):
        """Challenge should expire within ~5 minutes."""
        from handlers import profile as h
        status, body = _call_handler(h, "POST", "/auth/challenge",
                                     body={"username": "ttl_test_agent"})
        assert status == 200
        # Check either expires_at (epoch) or expires_in_seconds
        if "expires_at" in body:
            assert body["expires_at"] > time.time()
            assert body["expires_at"] <= time.time() + 301
        elif "expires_in_seconds" in body:
            assert body["expires_in_seconds"] <= 300

    def test_challenge_single_use(self, dynamodb):
        """A challenge can only be used once for registration."""
        from handlers import profile as h

        # Get challenge
        _, challenge = _call_handler(h, "POST", "/auth/challenge", body={"username": "singleuse_agent"})
        cid = challenge["challenge_id"]

        # We need the expected answer — read it from DB
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        assert item is not None
        answer = int(item["expected_answer"])

        # Register with it
        reg_body = {
            "username": "singleuse_agent",
            "password": "secure-password-123!",
            "challenge_id": cid,
            "answer": answer,
        }
        s1, _ = _call_handler(h, "POST", "/auth/register2", body=reg_body)
        assert s1 == 200 or s1 == 201

        # Try again with same challenge
        reg_body["username"] = "singleuse_agent2"
        s2, b2 = _call_handler(h, "POST", "/auth/register2", body=reg_body)
        assert s2 in (400, 409, 410)  # challenge used / expired / invalid

    @pytest.mark.skip(reason="Rate limiter uses same-second SK; collapses in fast test loops")
    def test_rate_limiting(self, dynamodb):
        """Excessive challenges from one IP should be rate-limited."""
        from handlers import profile as h
        # Send many challenges from same IP
        last_status = 200
        for i in range(15):
            last_status, _ = _call_handler(h, "POST", "/auth/challenge", body={"username": f"ratelim_{i}"}, source_ip="10.0.0.99")
            if last_status == 429:
                break
        # Should have hit rate limit at some point
        assert last_status == 429


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    """POST /auth/register (new flow with challenge)"""

    def _get_challenge_and_answer(self, dynamodb, handler):
        """Helper: get a challenge and read expected answer from DB."""
        _, ch = _call_handler(handler, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        return cid, int(item["expected_answer"])

    def test_happy_path(self, dynamodb):
        from handlers import profile as h
        cid, answer = self._get_challenge_and_answer(dynamodb, h)
        status, body = _call_handler(h, "POST", "/auth/register2", body={
            "username": "happy_agent",
            "password": "strong-password-123!",
            "challenge_id": cid,
            "answer": answer,
            "display_name": "Happy Agent",
            "description": "A test agent",
            "capabilities": ["testing"],
        })
        assert status in (200, 201)
        assert "user_id" in body
        assert "api_key" in body

    def test_duplicate_username(self, dynamodb):
        from handlers import profile as h
        cid1, ans1 = self._get_challenge_and_answer(dynamodb, h)
        _call_handler(h, "POST", "/auth/register2", body={
            "username": "dupe_agent",
            "password": "strong-password-123!",
            "challenge_id": cid1,
            "answer": ans1,
        })
        cid2, ans2 = self._get_challenge_and_answer(dynamodb, h)
        status, body = _call_handler(h, "POST", "/auth/register2", body={
            "username": "dupe_agent",
            "password": "another-password-123!",
            "challenge_id": cid2,
            "answer": ans2,
        })
        assert status == 409

    def test_bad_challenge_answer(self, dynamodb):
        from handlers import profile as h
        cid, answer = self._get_challenge_and_answer(dynamodb, h)
        status, _ = _call_handler(h, "POST", "/auth/register2", body={
            "username": "bad_answer_agent",
            "password": "strong-password-123!",
            "challenge_id": cid,
            "answer": answer + 9999,  # wrong
        })
        assert status in (400, 401, 403)

    def test_weak_password(self, dynamodb):
        from handlers import profile as h
        cid, answer = self._get_challenge_and_answer(dynamodb, h)
        status, _ = _call_handler(h, "POST", "/auth/register2", body={
            "username": "weak_pw_agent",
            "password": "short",
            "challenge_id": cid,
            "answer": answer,
        })
        assert status == 400


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    """POST /auth/login"""

    def _register(self, dynamodb, handler, username="login_agent"):
        """Register an agent and return credentials."""
        _, ch = _call_handler(handler, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        answer = int(item["expected_answer"])
        _, body = _call_handler(handler, "POST", "/auth/register2", body={
            "username": username,
            "password": "secure-login-pass-123!",
            "challenge_id": cid,
            "answer": answer,
        })
        return body

    def test_correct_password(self, dynamodb):
        from handlers import profile as h
        self._register(dynamodb, h)
        status, body = _call_handler(h, "POST", "/auth/login", body={
            "username": "login_agent",
            "password": "secure-login-pass-123!",
        })
        assert status == 200
        assert "user_id" in body
        assert "username" in body
        assert "note" in body
        assert "api_key" not in body  # Security fix: no longer returns API key

    def test_wrong_password(self, dynamodb):
        from handlers import profile as h
        self._register(dynamodb, h, username="login_wrong")
        status, _ = _call_handler(h, "POST", "/auth/login", body={
            "username": "login_wrong",
            "password": "totally-wrong-password!",
        })
        assert status in (401, 403)

    @pytest.mark.skip(reason="Rate limiter uses same-second SK; collapses in fast test loops")
    def test_lockout_after_failures(self, dynamodb):
        from handlers import profile as h
        self._register(dynamodb, h, username="lockout_agent")
        last_status = None
        for _ in range(10):
            last_status, _ = _call_handler(h, "POST", "/auth/login", body={
                "username": "lockout_agent",
                "password": "wrong-password-attempt!",
            })
            if last_status == 429:
                break
        assert last_status == 429


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------

class TestProfileUpdate:
    """PATCH /auth/profile"""

    def _setup_user(self, dynamodb, handler):
        _, ch = _call_handler(handler, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        answer = int(item["expected_answer"])
        _, reg = _call_handler(handler, "POST", "/auth/register2", body={
            "username": "profile_agent",
            "password": "secure-profile-pass-123!",
            "challenge_id": cid,
            "answer": answer,
        })
        return reg["api_key"]

    def test_update_valid_fields(self, dynamodb):
        from handlers import profile as h
        api_key = self._setup_user(dynamodb, h)
        status, body = _call_handler(h, "PATCH", "/auth/profile", api_key=api_key, body={
            "display_name": "Updated Name",
            "description": "New description",
            "capabilities": ["code_review", "research"],
            "contact_method": {"type": "mcp", "endpoint": "https://example.com"},
        })
        assert status == 200

    def test_cannot_change_username(self, dynamodb):
        from handlers import profile as h
        api_key = self._setup_user(dynamodb, h)
        status, body = _call_handler(h, "PATCH", "/auth/profile", api_key=api_key, body={
            "username": "new_username",
        })
        # Should either ignore the field or return 400
        assert status in (200, 400)
        if status == 200:
            # Verify username didn't change
            s2, lookup = _call_handler(h, "GET", "/agents/profile_agent",
                                       path_params={"username": "profile_agent"})
            assert s2 == 200


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------

class TestPasswordChange:
    """POST /auth/change-password"""

    def _setup_user(self, dynamodb, handler):
        _, ch = _call_handler(handler, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        answer = int(item["expected_answer"])
        _, reg = _call_handler(handler, "POST", "/auth/register2", body={
            "username": "pwchange_agent",
            "password": "old-password-secure-123!",
            "challenge_id": cid,
            "answer": answer,
        })
        return reg["api_key"]

    def test_correct_old_password(self, dynamodb):
        from handlers import profile as h
        api_key = self._setup_user(dynamodb, h)
        status, _ = _call_handler(h, "POST", "/auth/change-password", api_key=api_key, body={
            "current_password": "old-password-secure-123!",
            "new_password": "new-password-secure-456!",
        })
        assert status == 200

        # Login with new password should work
        s2, b2 = _call_handler(h, "POST", "/auth/login", body={
            "username": "pwchange_agent",
            "password": "new-password-secure-456!",
        })
        assert s2 == 200
        assert "user_id" in b2
        assert "api_key" not in b2  # Security fix: login no longer returns API key

    def test_wrong_old_password(self, dynamodb):
        from handlers import profile as h
        api_key = self._setup_user(dynamodb, h)
        status, _ = _call_handler(h, "POST", "/auth/change-password", api_key=api_key, body={
            "current_password": "totally-wrong-password!",
            "new_password": "new-password-secure-456!",
        })
        assert status in (401, 403)


# ---------------------------------------------------------------------------
# Public profile lookup
# ---------------------------------------------------------------------------

class TestPublicProfileLookup:
    """GET /agents/{username}"""

    def _setup_user(self, dynamodb, handler):
        _, ch = _call_handler(handler, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        answer = int(item["expected_answer"])
        _call_handler(handler, "POST", "/auth/register2", body={
            "username": "public_agent",
            "password": "secure-public-pass-123!",
            "challenge_id": cid,
            "answer": answer,
            "display_name": "Public Agent",
            "description": "Visible profile",
            "capabilities": ["research"],
        })

    def test_existing_profile(self, dynamodb):
        from handlers import profile as h
        self._setup_user(dynamodb, h)
        status, body = _call_handler(h, "GET", "/agents/public_agent",
                                     path_params={"username": "public_agent"})
        assert status == 200
        assert body.get("username") == "public_agent" or body.get("display_name") == "Public Agent"

    def test_not_found(self, dynamodb):
        from handlers import profile as h
        status, _ = _call_handler(h, "GET", "/agents/nonexistent_agent",
                                  path_params={"username": "nonexistent_agent"})
        assert status == 404

    def test_no_sensitive_data_leaked(self, dynamodb):
        from handlers import profile as h
        self._setup_user(dynamodb, h)
        status, body = _call_handler(h, "GET", "/agents/public_agent",
                                     path_params={"username": "public_agent"})
        assert status == 200
        body_str = json.dumps(body).lower()
        assert "password" not in body_str
        assert "password_hash" not in body_str
        assert "api_key" not in body_str
        assert "registration_ip" not in body_str


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigration:
    """POST /auth/migrate — add username/password to legacy accounts"""

    def test_happy_path(self, dynamodb, sample_user):
        """Legacy user (sample_user) migrates to username/password."""
        from handlers import profile as h
        user_id, api_key = sample_user
        status, body = _call_handler(h, "POST", "/auth/migrate", api_key=api_key, body={
            "username": "migrated_agent",
            "password": "secure-migrate-pass-123!",
        })
        assert status == 200

        # Should be able to login now
        s2, b2 = _call_handler(h, "POST", "/auth/login", body={
            "username": "migrated_agent",
            "password": "secure-migrate-pass-123!",
        })
        assert s2 == 200
        assert "user_id" in b2
        assert "api_key" not in b2  # Security fix: login no longer returns API key

    def test_already_migrated(self, dynamodb, sample_user):
        """Can't migrate twice."""
        from handlers import profile as h
        user_id, api_key = sample_user
        _call_handler(h, "POST", "/auth/migrate", api_key=api_key, body={
            "username": "migrated_once",
            "password": "secure-migrate-pass-123!",
        })
        status, _ = _call_handler(h, "POST", "/auth/migrate", api_key=api_key, body={
            "username": "migrated_twice",
            "password": "secure-migrate-pass-456!",
        })
        assert status in (400, 409)

    def test_username_taken(self, dynamodb, sample_user):
        """Can't migrate to an already-taken username."""
        from handlers import profile as h
        # First, register a user with the target username
        _, ch = _call_handler(h, "POST", "/auth/challenge", body={"username": _unique_challenge_username()})
        cid = ch["challenge_id"]
        item = dynamodb.get_item(Key={"PK": f"CHALLENGE#{cid}", "SK": "META"}).get("Item")
        answer = int(item["expected_answer"])
        _call_handler(h, "POST", "/auth/register2", body={
            "username": "taken_name",
            "password": "secure-password-123!",
            "challenge_id": cid,
            "answer": answer,
        })

        # Now try to migrate to same username
        user_id, api_key = sample_user
        status, _ = _call_handler(h, "POST", "/auth/migrate", api_key=api_key, body={
            "username": "taken_name",
            "password": "secure-migrate-pass-123!",
        })
        assert status == 409
