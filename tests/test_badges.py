"""Tests for badge API and SVG generation."""

import json
import hashlib
import hmac
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from tests.conftest import make_api_event

# === Fixtures ===


@pytest.fixture
def sample_agent(dynamodb):
    """Insert a sample agent with AGENT# PK pattern."""
    agent_id = "agent-test-badge-001"
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(
        Item={
            "PK": f"AGENT#{agent_id}",
            "SK": "PROFILE",
            "agent_id": agent_id,
            "agent_name": "BadgeTestBot",
            "capabilities": ["sandbox_execution"],
            "declared_scope": "read_only",
            "description": "A test agent for badge tests",
            "registered_at": now,
            "trust_score": "72",
            "trust_tier": "trusted",
            "last_scored_at": now,
        }
    )

    return agent_id


@pytest.fixture
def sample_agent_with_signals(dynamodb, sample_agent):
    """Insert signals for the sample agent so scoring has data."""
    agent_id = sample_agent
    now = datetime.now(timezone.utc).isoformat()

    # Insert some transaction outcome signals
    for i in range(5):
        dynamodb.put_item(
            Item={
                "PK": f"SIGNAL#sig-{i}",
                "SK": f"TS#{now}#{i}",
                "GSI1PK": f"AGENT_SIGNALS#{agent_id}",
                "GSI1SK": f"TS#{now}#{i}",
                "signal_type": "transaction_outcome",
                "agent_id": agent_id,
                "marketplace_id": "mp-test-1",
                "outcome": "completed",
                "timestamp": now,
            }
        )

    return agent_id


@pytest.fixture
def sample_marketplace_for_badge(dynamodb):
    """Insert a sample marketplace for badge tests."""
    marketplace_id = "mp-badge-test-001"
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(
        Item={
            "PK": f"MARKETPLACE#{marketplace_id}",
            "SK": "PROFILE",
            "marketplace_id": marketplace_id,
            "name": "Badge Test Marketplace",
            "url": "https://badge-test.example.com",
            "description": "A marketplace for badge tests",
            "contact_email": "admin@badge-test.example.com",
            "registered_at": now,
            "marketplace_score": Decimal("65"),
            "tier": "certified",
            "signal_count": 150,
            "last_scored_at": now,
            "marketplace_dimensions": json.dumps(
                {
                    "data_quality": 75.0,
                    "reporting_volume": 60.0,
                    "fairness": 70.0,
                    "integration_health": 55.0,
                    "dispute_resolution": 65.0,
                }
            ),
        }
    )

    return marketplace_id


# === Badge Lookup Tests ===


class TestGetBadge:
    def test_happy_path(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}",
            path_params={"agent_id": agent_id},
        )
        resp = get_badge(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["agent_id"] == agent_id
        assert "tier" in body
        assert "overall_score" in body
        assert isinstance(body["overall_score"], int)
        assert "dimensions" in body
        assert "confidence" in body
        assert "badge_image_url" in body
        assert "verification_url" in body
        assert "valid_until" in body
        assert "last_updated" in body

    def test_nonexistent_agent_returns_404(self, dynamodb):
        from handlers.badges import get_badge

        event = make_api_event(
            method="GET",
            path="/badges/nonexistent-agent",
            path_params={"agent_id": "nonexistent-agent"},
        )
        resp = get_badge(event, {})
        assert resp["statusCode"] == 404

    def test_response_has_no_marketplace_source_data(
        self, dynamodb, sample_agent_with_signals
    ):
        from handlers.badges import get_badge

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}",
            path_params={"agent_id": agent_id},
        )
        resp = get_badge(event, {})
        body = json.loads(resp["body"])

        # Private fields must not appear
        assert "marketplace_breakdown" not in body
        assert "per_source_scores" not in body
        assert "signal_counts_by_source" not in body
        assert "source_weights" not in body
        assert "marketplace_contributions" not in body
        assert "raw_signals" not in body
        assert "marketplace_id" not in body

    def test_badge_image_url_format(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}",
            path_params={"agent_id": agent_id},
        )
        resp = get_badge(event, {})
        body = json.loads(resp["body"])

        assert body["badge_image_url"].startswith(f"/badges/{agent_id}/image")
        assert body["verification_url"] == f"/badges/{agent_id}/verify"


# === Batch Lookup Tests ===


class TestGetBadgesBatch:
    def test_batch_multiple_agents(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badges_batch

        agent_id = sample_agent_with_signals

        # Create a second agent
        now = datetime.now(timezone.utc).isoformat()
        agent_id_2 = "agent-test-badge-002"
        dynamodb.put_item(
            Item={
                "PK": f"AGENT#{agent_id_2}",
                "SK": "PROFILE",
                "agent_id": agent_id_2,
                "agent_name": "SecondBot",
                "capabilities": [],
                "declared_scope": "network_call",
                "registered_at": now,
                "trust_score": "45",
                "trust_tier": "established",
            }
        )

        event = make_api_event(
            method="POST",
            path="/badges/batch",
            body={"agent_ids": [agent_id, agent_id_2]},
        )
        resp = get_badges_batch(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert "badges" in body
        assert len(body["badges"]) == 2

        returned_ids = {b["agent_id"] for b in body["badges"]}
        assert agent_id in returned_ids
        assert agent_id_2 in returned_ids

    def test_batch_limit_enforced(self, dynamodb):
        from handlers.badges import get_badges_batch

        agent_ids = [f"agent-{i}" for i in range(51)]
        event = make_api_event(
            method="POST",
            path="/badges/batch",
            body={"agent_ids": agent_ids},
        )
        resp = get_badges_batch(event, {})
        assert resp["statusCode"] == 400

        body = json.loads(resp["body"])
        assert body["error"] == "batch_limit_exceeded"

    def test_batch_nonexistent_agents_skipped(
        self, dynamodb, sample_agent_with_signals
    ):
        from handlers.badges import get_badges_batch

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="POST",
            path="/badges/batch",
            body={"agent_ids": [agent_id, "nonexistent-1", "nonexistent-2"]},
        )
        resp = get_badges_batch(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert len(body["badges"]) == 1
        assert body["badges"][0]["agent_id"] == agent_id

    def test_batch_empty_list(self, dynamodb):
        from handlers.badges import get_badges_batch

        event = make_api_event(
            method="POST",
            path="/badges/batch",
            body={"agent_ids": []},
        )
        resp = get_badges_batch(event, {})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["badges"] == []


# === SVG Badge Image Tests ===


class TestGetBadgeImage:
    def test_compact_svg(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge_image

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/image",
            path_params={"agent_id": agent_id},
            query_params={"style": "compact"},
        )
        resp = get_badge_image(event, {})
        assert resp["statusCode"] == 200
        assert resp["headers"]["Content-Type"] == "image/svg+xml"
        assert "Cache-Control" in resp["headers"]
        assert "max-age=14400" in resp["headers"]["Cache-Control"]
        assert "<svg" in resp["body"]
        assert "AgentPier" in resp["body"]

    def test_detailed_svg(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge_image

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/image",
            path_params={"agent_id": agent_id},
            query_params={"style": "detailed"},
        )
        resp = get_badge_image(event, {})
        assert resp["statusCode"] == 200
        assert resp["headers"]["Content-Type"] == "image/svg+xml"
        assert "<svg" in resp["body"]
        assert "Reliability" in resp["body"]
        assert "Safety" in resp["body"]
        assert "Capability" in resp["body"]
        assert "Transparency" in resp["body"]

    def test_default_style_is_compact(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge_image

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/image",
            path_params={"agent_id": agent_id},
        )
        resp = get_badge_image(event, {})
        assert resp["statusCode"] == 200
        # Compact badge does not have dimension bars
        assert "Reliability" not in resp["body"]

    def test_svg_cache_headers(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import get_badge_image

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/image",
            path_params={"agent_id": agent_id},
        )
        resp = get_badge_image(event, {})
        assert resp["headers"]["Cache-Control"] == "public, max-age=14400"

    def test_svg_not_found(self, dynamodb):
        from handlers.badges import get_badge_image

        event = make_api_event(
            method="GET",
            path="/badges/nonexistent/image",
            path_params={"agent_id": "nonexistent"},
        )
        resp = get_badge_image(event, {})
        assert resp["statusCode"] == 404


# === SVG Generator Direct Tests ===


class TestSvgGeneration:
    def test_all_agent_tiers(self):
        from utils.badge_svg import generate_compact_badge

        tiers = ["untrusted", "provisional", "established", "trusted", "highly_trusted"]
        for tier in tiers:
            svg = generate_compact_badge(tier, 50)
            assert "<svg" in svg
            assert "AgentPier" in svg

    def test_compact_badge_contains_score(self):
        from utils.badge_svg import generate_compact_badge

        svg = generate_compact_badge("trusted", 87)
        assert "87" in svg
        assert "Trusted" in svg

    def test_detailed_badge_dimensions(self):
        from utils.badge_svg import generate_detailed_badge

        dims = {
            "reliability": 92.0,
            "safety": 85.0,
            "capability": 90.0,
            "transparency": 82.0,
        }
        svg = generate_detailed_badge("highly_trusted", 87, dims)
        assert "<svg" in svg
        assert "Reliability" in svg
        assert "Safety" in svg
        assert "Capability" in svg
        assert "Transparency" in svg
        assert "Highly Trusted" in svg

    def test_marketplace_compact_badge(self):
        from utils.badge_svg import generate_marketplace_badge

        svg = generate_marketplace_badge("verified", 45, style="compact")
        assert "<svg" in svg
        assert "Verified Marketplace" in svg

    def test_marketplace_detailed_badge(self):
        from utils.badge_svg import generate_marketplace_badge

        svg = generate_marketplace_badge("enterprise", 90, style="detailed")
        assert "<svg" in svg
        assert "Verified Marketplace" in svg
        assert "Enterprise" in svg


# === Verification Endpoint Tests ===


class TestVerifyBadge:
    def test_verification_with_signature(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import verify_badge

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/verify",
            path_params={"agent_id": agent_id},
        )
        resp = verify_badge(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["agent_id"] == agent_id
        assert "tier" in body
        assert "overall_score" in body
        assert "dimensions" in body
        assert "signature" in body
        assert body["signature_algorithm"] == "HMAC-SHA256"
        assert body["signed_fields"] == "agent_id:tier:overall_score:last_updated"
        assert "last_updated" in body
        assert "valid_until" in body

    def test_signature_validation(self, dynamodb, sample_agent_with_signals):
        """Verify the signature can be recomputed from the response data."""
        from handlers.badges import verify_badge, BADGE_SECRET

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/verify",
            path_params={"agent_id": agent_id},
        )
        resp = verify_badge(event, {})
        body = json.loads(resp["body"])

        # Recompute the signature
        message = f"{body['agent_id']}:{body['tier']}:{body['overall_score']}:{body['last_updated']}"
        expected_sig = hmac.new(
            BADGE_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert body["signature"] == expected_sig

    def test_verify_not_found(self, dynamodb):
        from handlers.badges import verify_badge

        event = make_api_event(
            method="GET",
            path="/badges/nonexistent/verify",
            path_params={"agent_id": "nonexistent"},
        )
        resp = verify_badge(event, {})
        assert resp["statusCode"] == 404

    def test_verify_includes_agent_name(self, dynamodb, sample_agent_with_signals):
        from handlers.badges import verify_badge

        agent_id = sample_agent_with_signals
        event = make_api_event(
            method="GET",
            path=f"/badges/{agent_id}/verify",
            path_params={"agent_id": agent_id},
        )
        resp = verify_badge(event, {})
        body = json.loads(resp["body"])
        assert body["agent_name"] == "BadgeTestBot"


# === Marketplace Badge Tests ===


class TestMarketplaceBadge:
    def test_marketplace_badge_lookup(self, dynamodb, sample_marketplace_for_badge):
        from handlers.badges import get_marketplace_badge

        mp_id = sample_marketplace_for_badge
        event = make_api_event(
            method="GET",
            path=f"/badges/marketplace/{mp_id}",
            path_params={"marketplace_id": mp_id},
        )
        resp = get_marketplace_badge(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        assert body["name"] == "Badge Test Marketplace"
        assert body["tier"] == "certified"
        assert body["overall_score"] == 65
        assert "dimensions" in body
        assert "badge_image_url" in body
        assert "verification_url" in body
        assert "valid_until" in body

    def test_marketplace_badge_not_found(self, dynamodb):
        from handlers.badges import get_marketplace_badge

        event = make_api_event(
            method="GET",
            path="/badges/marketplace/nonexistent",
            path_params={"marketplace_id": "nonexistent"},
        )
        resp = get_marketplace_badge(event, {})
        assert resp["statusCode"] == 404


# === Rate Limiting Tests ===


class TestBadgeRateLimiting:
    def test_badge_rate_limit(self, dynamodb, sample_agent):
        from handlers.badges import get_badge

        agent_id = sample_agent

        with patch("handlers.badges.check_rate_limit", return_value=(False, 0, 86400)):
            event = make_api_event(
                method="GET",
                path=f"/badges/{agent_id}",
                path_params={"agent_id": agent_id},
            )
            resp = get_badge(event, {})
            assert resp["statusCode"] == 429

    def test_batch_rate_limit(self, dynamodb):
        from handlers.badges import get_badges_batch

        with patch("handlers.badges.check_rate_limit", return_value=(False, 0, 86400)):
            event = make_api_event(
                method="POST",
                path="/badges/batch",
                body={"agent_ids": ["agent-1"]},
            )
            resp = get_badges_batch(event, {})
            assert resp["statusCode"] == 429
