"""Integration tests for Lambda handlers with mocked DynamoDB."""

import json
import pytest
from tests.conftest import make_api_event


class TestGetMe:
    def test_authenticated(self, dynamodb, sample_user):
        from handlers.auth import get_me

        user_id, raw_key = sample_user
        event = make_api_event(api_key=raw_key)
        resp = get_me(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["user_id"] == user_id

    def test_unauthenticated(self, dynamodb):
        from handlers.auth import get_me

        event = make_api_event()
        resp = get_me(event, None)
        assert resp["statusCode"] == 401


class TestCreateListing:
    def test_success(self, dynamodb, sample_user):
        from handlers.listings import create_listing

        _, raw_key = sample_user
        event = make_api_event(
            method="POST",
            api_key=raw_key,
            body={
                "title": "Code Review Service",
                "description": "Expert code review and debugging for Python applications",
                "category": "code_review",
                "type": "service",
                "tags": ["code_review", "debugging"],
            },
        )
        resp = create_listing(event, None)
        assert resp["statusCode"] == 201

    def test_blocked_content(self, dynamodb, sample_user):
        from handlers.listings import create_listing

        _, raw_key = sample_user
        event = make_api_event(
            method="POST",
            api_key=raw_key,
            body={
                "title": "Buy cocaine online",
                "description": "Fast delivery",
                "category": "other",
                "type": "product",
            },
        )
        resp = create_listing(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "content_policy_violation"

    def test_unauthenticated(self, dynamodb):
        from handlers.listings import create_listing

        event = make_api_event(method="POST", body={"title": "test"})
        resp = create_listing(event, None)
        assert resp["statusCode"] == 401


class TestTrustRegister:
    def test_register_agent(self, dynamodb):
        from handlers.trust import trust_register

        event = make_api_event(
            method="POST",
            body={
                "agent_name": "test-agent",
                "capabilities": ["undo", "sandbox"],
                "declared_scope": "read_only",
            },
        )
        resp = trust_register(event, None)
        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert "agent_id" in body
        assert "trust_score" in body
        assert "trust_tier" in body

    def test_register_missing_name(self, dynamodb):
        from handlers.trust import trust_register

        event = make_api_event(method="POST", body={})
        resp = trust_register(event, None)
        assert resp["statusCode"] == 400


class TestTrustQuery:
    def test_nonexistent_agent(self, dynamodb):
        from handlers.trust import trust_query

        event = make_api_event(path_params={"agent_id": "nonexistent"})
        resp = trust_query(event, None)
        assert resp["statusCode"] == 404
