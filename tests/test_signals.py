"""Tests for transaction signal ingestion handlers."""

import json
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from tests.conftest import make_api_event


@pytest.fixture
def sample_marketplace(dynamodb):
    """Register a marketplace and return (marketplace_id, raw_api_key)."""
    from utils.auth import generate_api_key

    marketplace_id = "mp_signals_test"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": "MARKETPLACE_NAME#Signals Test MP",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": "Signals Test MP",
        "url": "https://signals-test.example.com",
        "description": "A test marketplace for signal ingestion",
        "contact_email": "admin@signals-test.example.com",
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
def second_marketplace(dynamodb):
    """A second marketplace for isolation tests."""
    from utils.auth import generate_api_key

    marketplace_id = "mp_other_test"
    raw_key, key_hash = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    dynamodb.put_item(Item={
        "PK": f"MARKETPLACE#{marketplace_id}",
        "SK": "PROFILE",
        "GSI1PK": "MARKETPLACE_NAME#Other Test MP",
        "GSI1SK": "META",
        "marketplace_id": marketplace_id,
        "name": "Other Test MP",
        "url": "https://other-test.example.com",
        "description": "Another test marketplace",
        "contact_email": "admin@other-test.example.com",
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
    """Build a signal ingestion event with X-Marketplace-Key header."""
    return make_api_event(
        method="POST",
        path="/trust/signals",
        headers={"x-marketplace-key": api_key},
        body=body,
    )


def _stats_event(api_key):
    """Build a signal stats event with X-Marketplace-Key header."""
    return make_api_event(
        method="GET",
        path="/trust/signals/stats",
        headers={"x-marketplace-key": api_key},
    )


class TestIngestSignalsSingle:
    """Single signal ingestion tests."""

    def test_happy_path(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        mp_id, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "metrics": {
                "completion_time_ms": 4200,
                "error_count": 0,
                "user_rating": 5,
            },
            "transaction_ref": "tx-789",
            "timestamp": "2026-03-04T10:00:00Z",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201

        body = json.loads(resp["body"])
        assert body["accepted"] == 1
        assert body["duplicates"] == 0
        assert len(body["signals"]) == 1
        assert body["signals"][0]["status"] == "accepted"
        assert body["signals"][0]["agent_id"] == "agent-456"
        assert "signal_id" in body["signals"][0]

    def test_availability_signal(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-100",
            "signal_type": "availability",
            "outcome": "down",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201
        assert json.loads(resp["body"])["accepted"] == 1

    def test_user_feedback_signal(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-200",
            "signal_type": "user_feedback",
            "outcome": "completed",
            "metrics": {"user_rating": 4},
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201

    def test_incident_signal(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-300",
            "signal_type": "incident",
            "outcome": "security",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201

    def test_no_timestamp_defaults(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201


class TestIngestSignalsBatch:
    """Batch signal ingestion tests."""

    def test_batch_happy_path(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "signals": [
                {
                    "agent_id": "agent-1",
                    "signal_type": "transaction_outcome",
                    "outcome": "completed",
                    "transaction_ref": "tx-batch-1",
                },
                {
                    "agent_id": "agent-2",
                    "signal_type": "availability",
                    "outcome": "up",
                    "transaction_ref": "tx-batch-2",
                },
                {
                    "agent_id": "agent-3",
                    "signal_type": "incident",
                    "outcome": "safety",
                    "transaction_ref": "tx-batch-3",
                },
            ]
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 201

        body = json.loads(resp["body"])
        assert body["accepted"] == 3
        assert body["duplicates"] == 0
        assert len(body["signals"]) == 3

    def test_batch_exceeds_max(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        signals = [
            {"agent_id": f"agent-{i}", "signal_type": "transaction_outcome", "outcome": "completed"}
            for i in range(101)
        ]
        event = _signal_event(raw_key, {"signals": signals})
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "batch_too_large"

    def test_batch_empty_array(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {"signals": []})
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "empty_signals"

    def test_batch_not_array(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {"signals": "not-an-array"})
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_signals"

    def test_batch_validation_fails_entire_batch(self, dynamodb, sample_marketplace):
        """If one signal in a batch is invalid, none are stored."""
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "signals": [
                {
                    "agent_id": "agent-good",
                    "signal_type": "transaction_outcome",
                    "outcome": "completed",
                    "transaction_ref": "tx-good",
                },
                {
                    "agent_id": "agent-bad",
                    "signal_type": "INVALID_TYPE",
                    "outcome": "completed",
                },
            ]
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_signal_type"


class TestIdempotency:
    """Duplicate transaction_ref handling."""

    def test_duplicate_returns_already_received(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        signal = {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-idempotent-1",
        }

        # First submission
        resp1 = ingest_signals(_signal_event(raw_key, signal), {})
        assert resp1["statusCode"] == 201
        body1 = json.loads(resp1["body"])
        assert body1["accepted"] == 1
        assert body1["duplicates"] == 0

        # Second submission (same transaction_ref)
        resp2 = ingest_signals(_signal_event(raw_key, signal), {})
        assert resp2["statusCode"] == 200  # 200 not 201 for all-duplicate
        body2 = json.loads(resp2["body"])
        assert body2["accepted"] == 0
        assert body2["duplicates"] == 1
        assert body2["signals"][0]["status"] == "already_received"

    def test_batch_with_mix_of_new_and_duplicate(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace

        # Submit first signal
        resp = ingest_signals(_signal_event(raw_key, {
            "agent_id": "agent-1",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-dup-mix",
        }), {})
        assert resp["statusCode"] == 201

        # Submit batch with one duplicate and one new
        resp2 = ingest_signals(_signal_event(raw_key, {
            "signals": [
                {
                    "agent_id": "agent-1",
                    "signal_type": "transaction_outcome",
                    "outcome": "completed",
                    "transaction_ref": "tx-dup-mix",
                },
                {
                    "agent_id": "agent-2",
                    "signal_type": "transaction_outcome",
                    "outcome": "failed",
                    "transaction_ref": "tx-new",
                },
            ]
        }), {})
        assert resp2["statusCode"] == 201  # 201 because there's at least one new
        body = json.loads(resp2["body"])
        assert body["accepted"] == 1
        assert body["duplicates"] == 1

    def test_no_transaction_ref_not_deduped(self, dynamodb, sample_marketplace):
        """Signals without transaction_ref are never deduplicated."""
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        signal = {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
        }

        resp1 = ingest_signals(_signal_event(raw_key, signal), {})
        assert json.loads(resp1["body"])["accepted"] == 1

        resp2 = ingest_signals(_signal_event(raw_key, signal), {})
        assert json.loads(resp2["body"])["accepted"] == 1


class TestValidation:
    """Input validation tests."""

    def test_invalid_signal_type(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "nonexistent_type",
            "outcome": "completed",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_signal_type"

    def test_invalid_outcome_for_type(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "up",  # valid for availability, not transaction_outcome
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_outcome"

    def test_missing_agent_id(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "signal_type": "transaction_outcome",
            "outcome": "completed",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_agent_id"

    def test_user_feedback_missing_rating(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "user_feedback",
            "outcome": "completed",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "missing_user_rating"

    def test_user_feedback_rating_out_of_range(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "user_feedback",
            "outcome": "completed",
            "metrics": {"user_rating": 6},
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_user_rating"

    def test_user_feedback_rating_zero(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = _signal_event(raw_key, {
            "agent_id": "agent-456",
            "signal_type": "user_feedback",
            "outcome": "completed",
            "metrics": {"user_rating": 0},
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_user_rating"

    def test_invalid_json_body(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        event = make_api_event(
            method="POST",
            path="/trust/signals",
            headers={"x-marketplace-key": raw_key},
        )
        event["body"] = "{bad json"
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "invalid_body"


class TestAuthentication:
    """Marketplace authentication tests."""

    def test_no_key_rejected(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        event = make_api_event(
            method="POST",
            path="/trust/signals",
            body={
                "agent_id": "agent-456",
                "signal_type": "transaction_outcome",
                "outcome": "completed",
            },
        )
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 401

    def test_wrong_key_rejected(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals

        event = _signal_event("ap_live_boguskeyboguskeyboguskey1234567890", {
            "agent_id": "agent-456",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
        })
        resp = ingest_signals(event, {})
        assert resp["statusCode"] == 401

    def test_stats_no_key_rejected(self, dynamodb, sample_marketplace):
        from handlers.signals import get_signal_stats

        event = make_api_event(
            method="GET",
            path="/trust/signals/stats",
        )
        resp = get_signal_stats(event, {})
        assert resp["statusCode"] == 401


class TestRateLimiting:
    """Rate limiting tests."""

    def test_rate_limit_exceeded(self, dynamodb, sample_marketplace):
        from unittest.mock import patch
        from handlers.signals import ingest_signals

        _, raw_key = sample_marketplace
        with patch("handlers.signals.check_rate_limit", return_value=(False, 0, 3600)):
            event = _signal_event(raw_key, {
                "agent_id": "agent-456",
                "signal_type": "transaction_outcome",
                "outcome": "completed",
            })
            resp = ingest_signals(event, {})

        assert resp["statusCode"] == 429
        body = json.loads(resp["body"])
        assert body["error"] == "rate_limited"


class TestSignalStats:
    """Stats endpoint tests."""

    def test_stats_empty(self, dynamodb, sample_marketplace):
        from handlers.signals import get_signal_stats

        _, raw_key = sample_marketplace
        resp = get_signal_stats(_stats_event(raw_key), {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["total_signals"] == 0
        assert body["by_type"] == {}
        assert body["by_outcome"] == {}

    def test_stats_after_ingestion(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals, get_signal_stats

        mp_id, raw_key = sample_marketplace

        # Ingest some signals
        ingest_signals(_signal_event(raw_key, {
            "signals": [
                {"agent_id": "a1", "signal_type": "transaction_outcome", "outcome": "completed", "transaction_ref": "s1"},
                {"agent_id": "a2", "signal_type": "transaction_outcome", "outcome": "failed", "transaction_ref": "s2"},
                {"agent_id": "a3", "signal_type": "availability", "outcome": "up", "transaction_ref": "s3"},
            ]
        }), {})

        resp = get_signal_stats(_stats_event(raw_key), {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert body["marketplace_id"] == mp_id
        assert body["total_signals"] == 3
        assert body["by_type"]["transaction_outcome"] == 2
        assert body["by_type"]["availability"] == 1
        assert body["by_outcome"]["completed"] == 1
        assert body["by_outcome"]["failed"] == 1
        assert body["by_outcome"]["up"] == 1
        assert body["date_range"]["earliest"] is not None
        assert body["date_range"]["latest"] is not None


class TestDataFirewall:
    """Marketplace isolation / data firewall tests."""

    def test_signals_stored_with_marketplace_isolation(self, dynamodb, sample_marketplace, second_marketplace):
        from handlers.signals import ingest_signals
        import boto3

        mp1_id, mp1_key = sample_marketplace
        mp2_id, mp2_key = second_marketplace

        # MP1 submits a signal for agent-shared
        ingest_signals(_signal_event(mp1_key, {
            "agent_id": "agent-shared",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-mp1",
        }), {})

        # MP2 submits a signal for the same agent
        ingest_signals(_signal_event(mp2_key, {
            "agent_id": "agent-shared",
            "signal_type": "transaction_outcome",
            "outcome": "failed",
            "transaction_ref": "tx-mp2",
        }), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")

        # Verify signals are partitioned by marketplace in PK
        from boto3.dynamodb.conditions import Key

        mp1_signals = table.query(
            KeyConditionExpression=Key("PK").eq(f"SIGNAL#{mp1_id}#agent-shared"),
        )
        assert len(mp1_signals["Items"]) == 1
        assert mp1_signals["Items"][0]["outcome"] == "completed"
        assert mp1_signals["Items"][0]["marketplace_id"] == mp1_id

        mp2_signals = table.query(
            KeyConditionExpression=Key("PK").eq(f"SIGNAL#{mp2_id}#agent-shared"),
        )
        assert len(mp2_signals["Items"]) == 1
        assert mp2_signals["Items"][0]["outcome"] == "failed"
        assert mp2_signals["Items"][0]["marketplace_id"] == mp2_id

    def test_gsi1_allows_agent_signal_query(self, dynamodb, sample_marketplace, second_marketplace):
        """GSI1 allows querying all signals for an agent across marketplaces."""
        from handlers.signals import ingest_signals
        import boto3

        _, mp1_key = sample_marketplace
        _, mp2_key = second_marketplace

        # Both marketplaces submit signals for the same agent
        ingest_signals(_signal_event(mp1_key, {
            "agent_id": "agent-cross",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-cross-1",
        }), {})

        ingest_signals(_signal_event(mp2_key, {
            "agent_id": "agent-cross",
            "signal_type": "availability",
            "outcome": "up",
            "transaction_ref": "tx-cross-2",
        }), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        from boto3.dynamodb.conditions import Key

        # GSI1 query should return both signals
        result = table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq("AGENT_SIGNALS#agent-cross"),
        )
        # Filter out dedup records
        signals = [i for i in result["Items"] if i["PK"].startswith("SIGNAL#")]
        assert len(signals) == 2

    def test_stats_only_show_own_marketplace(self, dynamodb, sample_marketplace, second_marketplace):
        """Stats endpoint only shows a marketplace their OWN submission stats."""
        from handlers.signals import ingest_signals, get_signal_stats

        mp1_id, mp1_key = sample_marketplace
        mp2_id, mp2_key = second_marketplace

        # MP1 submits 2 signals
        ingest_signals(_signal_event(mp1_key, {
            "signals": [
                {"agent_id": "a1", "signal_type": "transaction_outcome", "outcome": "completed", "transaction_ref": "s-own-1"},
                {"agent_id": "a2", "signal_type": "availability", "outcome": "up", "transaction_ref": "s-own-2"},
            ]
        }), {})

        # MP2 submits 1 signal
        ingest_signals(_signal_event(mp2_key, {
            "agent_id": "a1",
            "signal_type": "incident",
            "outcome": "security",
            "transaction_ref": "s-own-3",
        }), {})

        # MP1 stats should show 2
        resp1 = get_signal_stats(_stats_event(mp1_key), {})
        body1 = json.loads(resp1["body"])
        assert body1["total_signals"] == 2
        assert body1["marketplace_id"] == mp1_id

        # MP2 stats should show 1
        resp2 = get_signal_stats(_stats_event(mp2_key), {})
        body2 = json.loads(resp2["body"])
        assert body2["total_signals"] == 1
        assert body2["marketplace_id"] == mp2_id


class TestCounterUpdates:
    """Verify that signal ingestion updates counters."""

    def test_marketplace_signal_count_incremented(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals
        import boto3

        mp_id, raw_key = sample_marketplace

        ingest_signals(_signal_event(raw_key, {
            "agent_id": "agent-counter",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-counter-1",
        }), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        mp = table.get_item(Key={"PK": f"MARKETPLACE#{mp_id}", "SK": "PROFILE"})["Item"]
        assert int(mp["signal_count"]) == 1
        assert mp["last_signal_at"] is not None

    def test_marketplace_signal_count_batch(self, dynamodb, sample_marketplace):
        from handlers.signals import ingest_signals
        import boto3

        mp_id, raw_key = sample_marketplace

        ingest_signals(_signal_event(raw_key, {
            "signals": [
                {"agent_id": "a1", "signal_type": "transaction_outcome", "outcome": "completed", "transaction_ref": "tx-cb-1"},
                {"agent_id": "a2", "signal_type": "availability", "outcome": "up", "transaction_ref": "tx-cb-2"},
                {"agent_id": "a3", "signal_type": "incident", "outcome": "safety", "transaction_ref": "tx-cb-3"},
            ]
        }), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        mp = table.get_item(Key={"PK": f"MARKETPLACE#{mp_id}", "SK": "PROFILE"})["Item"]
        assert int(mp["signal_count"]) == 3

    def test_agent_trust_profile_counter(self, dynamodb, sample_marketplace):
        """Agent signal_count is updated if trust profile exists."""
        from handlers.signals import ingest_signals
        import boto3

        mp_id, raw_key = sample_marketplace
        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")

        # Create an agent trust profile
        table.put_item(Item={
            "PK": "AGENT#agent-trust",
            "SK": "TRUST",
            "agent_id": "agent-trust",
            "signal_count": 0,
            "trust_score": Decimal("0.5"),
        })

        ingest_signals(_signal_event(raw_key, {
            "agent_id": "agent-trust",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-trust-1",
        }), {})

        agent = table.get_item(Key={"PK": "AGENT#agent-trust", "SK": "TRUST"})["Item"]
        assert int(agent["signal_count"]) == 1

    def test_duplicates_dont_increment_counters(self, dynamodb, sample_marketplace):
        """Duplicate signals should not increment counters."""
        from handlers.signals import ingest_signals
        import boto3

        mp_id, raw_key = sample_marketplace
        signal = {
            "agent_id": "agent-dup-counter",
            "signal_type": "transaction_outcome",
            "outcome": "completed",
            "transaction_ref": "tx-dup-counter",
        }

        ingest_signals(_signal_event(raw_key, signal), {})
        ingest_signals(_signal_event(raw_key, signal), {})

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("agentpier-test")
        mp = table.get_item(Key={"PK": f"MARKETPLACE#{mp_id}", "SK": "PROFILE"})["Item"]
        assert int(mp["signal_count"]) == 1  # not 2
