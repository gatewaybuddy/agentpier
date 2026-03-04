"""Tests for marketplace registration and management handlers."""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from tests.conftest import make_api_event


@pytest.fixture
def sample_marketplace(dynamodb):
    """Register a marketplace and return (marketplace_id, raw_api_key)."""
    from utils.auth import generate_api_key

    marketplace_id = "mp_test_abc123"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": "MARKETPLACE_NAME#Test Marketplace",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": "Test Marketplace",
        "url": "https://test-marketplace.example.com",
        "description": "A test marketplace",
        "contact_email": "admin@test-marketplace.example.com",
        "api_key_hash": key_hash,
        "registered_at": now,
        "verified_at": None,
        "marketplace_score": Decimal("0"),
        "tier": "registered",
        "signal_count": 0,
        "last_signal_at": None,
    })

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": f"APIKEY#{key_hash[:16]}",
        "GSI2PK": f"APIKEY#{key_hash}",
        "GSI2SK": now,
        "marketplace_id": marketplace_id,
        "key_hash": key_hash,
        "created_at": now,
    })

    return marketplace_id, raw_key


class TestRegisterMarketplace:
    def test_happy_path(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "name": "My New Marketplace",
                "url": "https://my-marketplace.io",
                "contact_email": "hello@my-marketplace.io",
                "description": "A great marketplace for AI agents",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 201

        body = json.loads(resp["body"])
        assert "marketplace_id" in body
        assert body["name"] == "My New Marketplace"
        assert body["api_key"].startswith("ap_live_")
        assert "Store your API key securely" in body["message"]

    def test_duplicate_name_rejected(self, dynamodb, sample_marketplace):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "name": "Test Marketplace",
                "url": "https://other.example.com",
                "contact_email": "other@example.com",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 409
        body = json.loads(resp["body"])
        assert body["error"] == "name_taken"

    def test_missing_name(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "url": "https://example.com",
                "contact_email": "a@b.com",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_name"

    def test_invalid_url(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "name": "Valid Name",
                "url": "not-a-url",
                "contact_email": "a@b.com",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_url"

    def test_invalid_email(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "name": "Valid Name",
                "url": "https://example.com",
                "contact_email": "not-an-email",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_email"

    def test_invalid_json_body(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(method="POST", path="/marketplace/register")
        event["body"] = "{bad json"
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_body"

    def test_name_too_short(self, dynamodb):
        from handlers.marketplace import register_marketplace

        event = make_api_event(
            method="POST",
            path="/marketplace/register",
            body={
                "name": "A",
                "url": "https://example.com",
                "contact_email": "a@b.com",
            },
        )
        resp = register_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_name"

    def test_rate_limiting(self, dynamodb):
        from unittest.mock import patch
        from handlers.marketplace import register_marketplace

        # Simulate rate limit exceeded
        with patch("handlers.marketplace.check_rate_limit", return_value=(False, 0, 3600)):
            event = make_api_event(
                method="POST",
                path="/marketplace/register",
                body={
                    "name": "Rate Limited MP",
                    "url": "https://example.com",
                    "contact_email": "a@b.com",
                },
            )
            resp = register_marketplace(event, {})

        assert resp["statusCode"] == 429
        body = json.loads(resp["body"])
        assert body["error"] == "rate_limited"


class TestGetMarketplace:
    def test_get_public_profile(self, dynamodb, sample_marketplace):
        from handlers.marketplace import get_marketplace

        mp_id, _ = sample_marketplace
        event = make_api_event(
            method="GET",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
        )
        resp = get_marketplace(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        assert body["name"] == "Test Marketplace"
        assert body["url"] == "https://test-marketplace.example.com"
        assert body["tier"] == "registered"
        assert body["marketplace_score"] == 0.0
        assert body["signal_count"] == 0
        assert "registered_at" in body

        # Sensitive fields must NOT be exposed
        assert "api_key_hash" not in body
        assert "contact_email" not in body

    def test_not_found(self, dynamodb):
        from handlers.marketplace import get_marketplace

        event = make_api_event(
            method="GET",
            path="/marketplace/nonexistent",
            path_params={"id": "nonexistent"},
        )
        resp = get_marketplace(event, {})
        assert resp["statusCode"] == 404


class TestUpdateMarketplace:
    def test_update_description(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"description": "Updated description"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["description"] == "Updated description"
        assert body["marketplace_id"] == mp_id

    def test_update_url(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"url": "https://new-url.example.com"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["url"] == "https://new-url.example.com"

    def test_update_contact_email(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"contact_email": "new@example.com"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 200

    def test_unauthorized_no_key(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, _ = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            body={"description": "Hacked!"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 401

    def test_unauthorized_wrong_key(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, _ = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key="ap_live_boguskey",
            body={"description": "Hacked!"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 401

    def test_unauthorized_wrong_marketplace(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        _, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path="/marketplace/other_mp_id",
            path_params={"id": "other_mp_id"},
            api_key=raw_key,
            body={"description": "Wrong mp"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 401

    def test_no_valid_fields(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"name": "Cant change name"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "no_updates"

    def test_invalid_url_update(self, dynamodb, sample_marketplace):
        from handlers.marketplace import update_marketplace

        mp_id, raw_key = sample_marketplace
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"url": "not-valid"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_url"


class TestRotateMarketplaceKey:
    def test_rotate_key(self, dynamodb, sample_marketplace):
        from handlers.marketplace import rotate_marketplace_key, get_marketplace

        mp_id, raw_key = sample_marketplace

        # Rotate the key
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/rotate-key",
            path_params={"id": mp_id},
            api_key=raw_key,
        )
        resp = rotate_marketplace_key(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        new_key = body["api_key"]
        assert new_key.startswith("ap_live_")
        assert new_key != raw_key
        assert "Key rotated" in body["message"]

    def test_old_key_invalid_after_rotation(self, dynamodb, sample_marketplace):
        from handlers.marketplace import rotate_marketplace_key, update_marketplace

        mp_id, raw_key = sample_marketplace

        # Rotate
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/rotate-key",
            path_params={"id": mp_id},
            api_key=raw_key,
        )
        resp = rotate_marketplace_key(event, {})
        assert resp["statusCode"] == 200

        # Try using old key — should fail
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=raw_key,
            body={"description": "Should fail"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 401

    def test_new_key_works_after_rotation(self, dynamodb, sample_marketplace):
        from handlers.marketplace import rotate_marketplace_key, update_marketplace

        mp_id, raw_key = sample_marketplace

        # Rotate
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/rotate-key",
            path_params={"id": mp_id},
            api_key=raw_key,
        )
        resp = rotate_marketplace_key(event, {})
        new_key = json.loads(resp["body"])["api_key"]

        # Use new key
        event = make_api_event(
            method="PUT",
            path=f"/marketplace/{mp_id}",
            path_params={"id": mp_id},
            api_key=new_key,
            body={"description": "Updated with new key"},
        )
        resp = update_marketplace(event, {})
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["description"] == "Updated with new key"

    def test_rotate_unauthorized(self, dynamodb, sample_marketplace):
        from handlers.marketplace import rotate_marketplace_key

        mp_id, _ = sample_marketplace
        event = make_api_event(
            method="POST",
            path=f"/marketplace/{mp_id}/rotate-key",
            path_params={"id": mp_id},
        )
        resp = rotate_marketplace_key(event, {})
        assert resp["statusCode"] == 401
