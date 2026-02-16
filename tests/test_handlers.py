"""Integration tests for Lambda handlers with mocked DynamoDB."""

import json
import pytest
from tests.conftest import make_api_event


class TestRegister:
    def test_successful_registration(self, dynamodb):
        from handlers.auth import register
        event = make_api_event(
            method="POST",
            path="/auth/register",
            body={
                "agent_name": "newbot",
                "operator_email": "ops@example.com",
                "description": "A new test bot",
            },
        )
        resp = register(event, None)
        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert "api_key" in body
        assert body["api_key"].startswith("ap_live_")

    def test_missing_email(self, dynamodb):
        from handlers.auth import register
        event = make_api_event(method="POST", body={"agent_name": "bot"})
        resp = register(event, None)
        assert resp["statusCode"] == 400

    def test_duplicate_name(self, dynamodb, sample_user):
        from handlers.auth import register
        event = make_api_event(
            method="POST",
            body={"agent_name": "testbot", "operator_email": "x@y.com"},
        )
        resp = register(event, None)
        assert resp["statusCode"] == 409


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
                "title": "Plumbing Repair",
                "description": "Licensed plumber in Austin",
                "category": "plumbing",
                "type": "service",
                "tags": ["plumbing", "repair"],
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


class TestGetTrust:
    def test_existing_user(self, dynamodb, sample_user):
        from handlers.trust import get_trust
        user_id, _ = sample_user
        event = make_api_event(path_params={"user_id": user_id})
        resp = get_trust(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "trust_score" in body
        assert "factors" in body

    def test_nonexistent_user(self, dynamodb):
        from handlers.trust import get_trust
        event = make_api_event(path_params={"user_id": "nonexistent"})
        resp = get_trust(event, None)
        assert resp["statusCode"] == 404
