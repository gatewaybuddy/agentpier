"""Comprehensive data firewall security tests.

Validates marketplace isolation, audit logging, response sanitization,
and the X-Data-Firewall header enforcement.
"""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from tests.conftest import make_api_event


@pytest.fixture
def marketplace_a(dynamodb):
    """Marketplace A for isolation tests."""
    from utils.auth import generate_api_key

    marketplace_id = "mp_firewall_a"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": "MARKETPLACE_NAME#Firewall Test A",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": "Firewall Test A",
        "url": "https://firewall-a.example.com",
        "description": "Marketplace A for firewall tests",
        "contact_email": "admin@firewall-a.example.com",
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


@pytest.fixture
def marketplace_b(dynamodb):
    """Marketplace B for isolation tests."""
    from utils.auth import generate_api_key

    marketplace_id = "mp_firewall_b"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": "MARKETPLACE_NAME#Firewall Test B",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": "Firewall Test B",
        "url": "https://firewall-b.example.com",
        "description": "Marketplace B for firewall tests",
        "contact_email": "admin@firewall-b.example.com",
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


def _signal_event(api_key, body):
    return make_api_event(
        method="POST",
        path="/trust/signals",
        headers={"x-marketplace-key": api_key},
        body=body,
    )


def _stats_event(api_key):
    return make_api_event(
        method="GET",
        path="/trust/signals/stats",
        headers={"x-marketplace-key": api_key},
    )


def _ingest_signal(api_key, agent_id, signal_type="transaction_outcome",
                   outcome="completed", transaction_ref=None):
    """Helper to ingest a single signal."""
    from handlers.signals import ingest_signals

    body = {
        "agent_id": agent_id,
        "signal_type": signal_type,
        "outcome": outcome,
    }
    if transaction_ref:
        body["transaction_ref"] = transaction_ref

    return ingest_signals(_signal_event(api_key, body), {})


class TestMarketplaceIsolation:
    """Marketplace A cannot see Marketplace B's raw signals via any endpoint."""

    def test_marketplace_a_cannot_see_b_signals(self, dynamodb, marketplace_a, marketplace_b):
        """Marketplace A's stats should not include B's signals."""
        from handlers.signals import get_signal_stats

        mp_a_id, mp_a_key = marketplace_a
        mp_b_id, mp_b_key = marketplace_b

        # A ingests 2 signals
        _ingest_signal(mp_a_key, "agent-shared", transaction_ref="tx-a1")
        _ingest_signal(mp_a_key, "agent-shared", transaction_ref="tx-a2")

        # B ingests 3 signals
        _ingest_signal(mp_b_key, "agent-shared", transaction_ref="tx-b1")
        _ingest_signal(mp_b_key, "agent-shared", transaction_ref="tx-b2")
        _ingest_signal(mp_b_key, "agent-other", transaction_ref="tx-b3")

        # A's stats should show 2
        resp_a = get_signal_stats(_stats_event(mp_a_key), {})
        body_a = json.loads(resp_a["body"])
        assert body_a["marketplace_id"] == mp_a_id
        assert body_a["total_signals"] == 2

        # B's stats should show 3
        resp_b = get_signal_stats(_stats_event(mp_b_key), {})
        body_b = json.loads(resp_b["body"])
        assert body_b["marketplace_id"] == mp_b_id
        assert body_b["total_signals"] == 3

    def test_signal_pk_contains_marketplace_id(self, dynamodb, marketplace_a, marketplace_b):
        """Signals are stored with marketplace-partitioned PK."""
        import boto3
        from boto3.dynamodb.conditions import Key

        mp_a_id, mp_a_key = marketplace_a
        mp_b_id, mp_b_key = marketplace_b

        _ingest_signal(mp_a_key, "agent-pk-test", transaction_ref="tx-pk-a")
        _ingest_signal(mp_b_key, "agent-pk-test", transaction_ref="tx-pk-b")

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")

        # Query A's partition — should only find A's signal
        a_result = table.query(
            KeyConditionExpression=Key("PK").eq(f"SIGNAL#{mp_a_id}#agent-pk-test"),
        )
        a_signals = [i for i in a_result["Items"] if i["SK"].startswith("TS#")]
        assert len(a_signals) == 1
        assert a_signals[0]["marketplace_id"] == mp_a_id

        # Query B's partition — should only find B's signal
        b_result = table.query(
            KeyConditionExpression=Key("PK").eq(f"SIGNAL#{mp_b_id}#agent-pk-test"),
        )
        b_signals = [i for i in b_result["Items"] if i["SK"].startswith("TS#")]
        assert len(b_signals) == 1
        assert b_signals[0]["marketplace_id"] == mp_b_id

    def test_stats_only_returns_own_marketplace_data(self, dynamodb, marketplace_a, marketplace_b):
        """Stats endpoint only returns data for the authenticated marketplace."""
        from handlers.signals import get_signal_stats

        _, mp_a_key = marketplace_a
        mp_b_id, mp_b_key = marketplace_b

        # Only B ingests signals
        _ingest_signal(mp_b_key, "agent-stats-iso", transaction_ref="tx-stats-1")
        _ingest_signal(mp_b_key, "agent-stats-iso", transaction_ref="tx-stats-2")

        # A's stats should be empty
        resp_a = get_signal_stats(_stats_event(mp_a_key), {})
        body_a = json.loads(resp_a["body"])
        assert body_a["total_signals"] == 0
        assert body_a["by_type"] == {}


class TestAuditLogging:
    """Audit log entries are created for signal access."""

    def test_ingest_creates_audit_log(self, dynamodb, marketplace_a):
        """Signal ingestion creates an audit log entry."""
        import boto3
        from boto3.dynamodb.conditions import Key

        mp_id, mp_key = marketplace_a
        _ingest_signal(mp_key, "agent-audit-1", transaction_ref="tx-audit-1")

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        result = table.query(
            KeyConditionExpression=Key("PK").eq("AUDIT#SIGNAL_ACCESS"),
        )

        audit_entries = [
            i for i in result["Items"]
            if i.get("action") == "ingest" and i.get("agent_id") == "agent-audit-1"
        ]
        assert len(audit_entries) >= 1

        entry = audit_entries[0]
        assert entry["accessor_id"] == mp_id
        assert entry["accessor_type"] == "marketplace"
        assert entry["marketplace_id"] == mp_id
        assert "timestamp" in entry

    def test_stats_creates_audit_log(self, dynamodb, marketplace_a):
        """Stats query creates an audit log entry."""
        import boto3
        from boto3.dynamodb.conditions import Key
        from handlers.signals import get_signal_stats

        mp_id, mp_key = marketplace_a
        get_signal_stats(_stats_event(mp_key), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        result = table.query(
            KeyConditionExpression=Key("PK").eq("AUDIT#SIGNAL_ACCESS"),
        )

        audit_entries = [
            i for i in result["Items"]
            if i.get("action") == "stats_query" and i.get("accessor_id") == mp_id
        ]
        assert len(audit_entries) >= 1

    def test_audit_records_are_append_only(self, dynamodb, marketplace_a):
        """Audit records use unique SK so they cannot be overwritten."""
        import boto3
        from boto3.dynamodb.conditions import Key

        mp_id, mp_key = marketplace_a

        # Ingest multiple signals
        _ingest_signal(mp_key, "agent-append-1", transaction_ref="tx-append-1")
        _ingest_signal(mp_key, "agent-append-2", transaction_ref="tx-append-2")

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        result = table.query(
            KeyConditionExpression=Key("PK").eq("AUDIT#SIGNAL_ACCESS"),
        )

        ingest_entries = [i for i in result["Items"] if i.get("action") == "ingest"]
        # Each unique agent_id should have its own audit entry
        agent_ids = {e.get("agent_id") for e in ingest_entries}
        assert "agent-append-1" in agent_ids
        assert "agent-append-2" in agent_ids

        # Each entry has a unique SK (TS#{timestamp}#{uuid})
        sks = [e["SK"] for e in ingest_entries]
        assert len(sks) == len(set(sks)), "Audit entries must have unique sort keys"

    def test_audit_log_includes_ip_address(self, dynamodb, marketplace_a):
        """Audit log entries include the client IP address."""
        import boto3
        from boto3.dynamodb.conditions import Key

        _, mp_key = marketplace_a
        _ingest_signal(mp_key, "agent-ip-test", transaction_ref="tx-ip-1")

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        result = table.query(
            KeyConditionExpression=Key("PK").eq("AUDIT#SIGNAL_ACCESS"),
        )

        ip_entries = [
            i for i in result["Items"]
            if i.get("agent_id") == "agent-ip-test"
        ]
        assert len(ip_entries) >= 1
        assert ip_entries[0].get("ip_address") == "127.0.0.1"


class TestFirewallHeader:
    """X-Data-Firewall: enforced header present on signal responses."""

    def test_ingest_response_has_firewall_header(self, dynamodb, marketplace_a):
        _, mp_key = marketplace_a
        resp = _ingest_signal(mp_key, "agent-hdr-1", transaction_ref="tx-hdr-1")
        assert resp["headers"].get("X-Data-Firewall") == "enforced"

    def test_stats_response_has_firewall_header(self, dynamodb, marketplace_a):
        from handlers.signals import get_signal_stats

        _, mp_key = marketplace_a
        resp = get_signal_stats(_stats_event(mp_key), {})
        assert resp["headers"].get("X-Data-Firewall") == "enforced"


class TestSanitizeSignalsForApi:
    """sanitize_signals_for_api strips all source-identifying fields."""

    def test_strips_marketplace_id(self):
        from utils.score_query import sanitize_signals_for_api

        signals = [
            {
                "signal_id": "abc123",
                "agent_id": "agent-1",
                "signal_type": "transaction_outcome",
                "outcome": "completed",
                "marketplace_id": "mp_secret",
                "timestamp": "2026-03-04T10:00:00Z",
            }
        ]
        sanitized = sanitize_signals_for_api(signals)
        assert len(sanitized) == 1
        assert "marketplace_id" not in sanitized[0]
        assert sanitized[0]["signal_id"] == "abc123"
        assert sanitized[0]["agent_id"] == "agent-1"

    def test_strips_dynamodb_key_fields(self):
        from utils.score_query import sanitize_signals_for_api

        signals = [
            {
                "PK": "SIGNAL#mp1#agent-1",
                "SK": "TS#2026-03-04#abc",
                "GSI1PK": "AGENT_SIGNALS#agent-1",
                "GSI1SK": "TS#2026-03-04#abc",
                "GSI2PK": "something",
                "GSI2SK": "something",
                "signal_id": "abc",
                "agent_id": "agent-1",
                "marketplace_id": "mp1",
                "signal_type": "transaction_outcome",
                "outcome": "completed",
            }
        ]
        sanitized = sanitize_signals_for_api(signals)
        assert len(sanitized) == 1
        for field in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "marketplace_id"):
            assert field not in sanitized[0], f"{field} should be stripped"

        # Ensure non-private fields are preserved
        assert sanitized[0]["signal_id"] == "abc"
        assert sanitized[0]["agent_id"] == "agent-1"
        assert sanitized[0]["signal_type"] == "transaction_outcome"

    def test_empty_list(self):
        from utils.score_query import sanitize_signals_for_api

        assert sanitize_signals_for_api([]) == []


class TestSanitizeScoreResponse:
    """sanitize_score_response removes per-marketplace breakdown."""

    def test_removes_marketplace_breakdown(self):
        from utils.score_response import sanitize_score_response

        score = {
            "agent_id": "agent-1",
            "overall_score": 0.85,
            "dimensions": {
                "reliability": 0.9,
                "safety": 0.8,
                "capability": 0.85,
                "transparency": 0.7,
            },
            "marketplace_breakdown": {
                "mp1": {"score": 0.9, "signal_count": 50},
                "mp2": {"score": 0.7, "signal_count": 20},
            },
            "per_source_scores": {"mp1": 0.9, "mp2": 0.7},
            "signal_counts_by_source": {"mp1": 50, "mp2": 20},
            "signal_count": 70,
            "last_updated": "2026-03-04T10:00:00Z",
        }

        sanitized = sanitize_score_response(score)

        assert sanitized["agent_id"] == "agent-1"
        assert sanitized["overall_score"] == 0.85
        assert sanitized["dimensions"]["reliability"] == 0.9
        assert sanitized["signal_count"] == 70
        assert "marketplace_breakdown" not in sanitized
        assert "per_source_scores" not in sanitized
        assert "signal_counts_by_source" not in sanitized

    def test_removes_source_weights(self):
        from utils.score_response import sanitize_score_response

        score = {
            "agent_id": "agent-1",
            "overall_score": 0.5,
            "source_weights": {"mp1": 0.6, "mp2": 0.4},
            "marketplace_contributions": [
                {"marketplace_id": "mp1", "weight": 0.6},
            ],
        }
        sanitized = sanitize_score_response(score)
        assert "source_weights" not in sanitized
        assert "marketplace_contributions" not in sanitized

    def test_removes_nested_marketplace_id(self):
        from utils.score_response import sanitize_score_response

        score = {
            "agent_id": "agent-1",
            "overall_score": 0.5,
            "dimensions": {
                "reliability": 0.9,
                "marketplace_id": "mp_sneaky",
            },
        }
        sanitized = sanitize_score_response(score)
        assert "marketplace_id" not in sanitized["dimensions"]
        assert sanitized["dimensions"]["reliability"] == 0.9

    def test_removes_raw_signals(self):
        from utils.score_response import sanitize_score_response

        score = {
            "agent_id": "agent-1",
            "overall_score": 0.5,
            "raw_signals": [
                {"signal_id": "s1", "marketplace_id": "mp1"},
            ],
        }
        sanitized = sanitize_score_response(score)
        assert "raw_signals" not in sanitized

    def test_preserves_public_fields(self):
        from utils.score_response import sanitize_score_response

        score = {
            "agent_id": "agent-1",
            "overall_score": 0.85,
            "trust_score": 0.85,
            "reliability": 0.9,
            "safety": 0.8,
            "capability": 0.85,
            "transparency": 0.7,
            "signal_count": 70,
            "last_updated": "2026-03-04T10:00:00Z",
            "confidence": "high",
            "tier": "verified",
        }
        sanitized = sanitize_score_response(score)
        for key in score:
            assert key in sanitized, f"Public field {key} should be preserved"
            assert sanitized[key] == score[key]


class TestScoreQueryInternal:
    """Internal score query helper tests."""

    def test_get_agent_signals_all_sources(self, dynamodb, marketplace_a, marketplace_b):
        """Internal query returns signals from all marketplaces."""
        from utils.score_query import get_agent_signals_all_sources

        _, mp_a_key = marketplace_a
        _, mp_b_key = marketplace_b

        # Both marketplaces submit signals for same agent
        _ingest_signal(mp_a_key, "agent-internal", transaction_ref="tx-int-a")
        _ingest_signal(mp_b_key, "agent-internal", transaction_ref="tx-int-b")

        signals = get_agent_signals_all_sources("agent-internal")
        assert len(signals) == 2

        # Should include marketplace_id for scoring
        mp_ids = {s["marketplace_id"] for s in signals}
        assert "mp_firewall_a" in mp_ids
        assert "mp_firewall_b" in mp_ids

    def test_get_agent_signals_includes_marketplace_id(self, dynamodb, marketplace_a):
        """Returned signals include marketplace_id for source weighting."""
        from utils.score_query import get_agent_signals_all_sources

        _, mp_key = marketplace_a
        _ingest_signal(mp_key, "agent-weight", transaction_ref="tx-weight-1")

        signals = get_agent_signals_all_sources("agent-weight")
        assert len(signals) == 1
        assert "marketplace_id" in signals[0]

    def test_sanitize_then_no_marketplace_id(self, dynamodb, marketplace_a):
        """After sanitization, marketplace_id is gone."""
        from utils.score_query import get_agent_signals_all_sources, sanitize_signals_for_api

        _, mp_key = marketplace_a
        _ingest_signal(mp_key, "agent-sanitize", transaction_ref="tx-san-1")

        raw = get_agent_signals_all_sources("agent-sanitize")
        assert raw[0]["marketplace_id"] == "mp_firewall_a"

        clean = sanitize_signals_for_api(raw)
        assert "marketplace_id" not in clean[0]

    def test_empty_agent(self, dynamodb, marketplace_a):
        """Query for non-existent agent returns empty list."""
        from utils.score_query import get_agent_signals_all_sources

        signals = get_agent_signals_all_sources("agent-does-not-exist")
        assert signals == []

    def test_respects_limit(self, dynamodb, marketplace_a):
        """Limit parameter caps the number of returned signals."""
        from utils.score_query import get_agent_signals_all_sources

        _, mp_key = marketplace_a
        for i in range(5):
            _ingest_signal(mp_key, "agent-limit", transaction_ref=f"tx-limit-{i}")

        signals = get_agent_signals_all_sources("agent-limit", limit=3)
        assert len(signals) <= 3
