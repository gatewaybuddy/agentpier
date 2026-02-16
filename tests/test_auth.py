"""Tests for auth utilities."""

import pytest
from unittest.mock import patch


class TestGenerateApiKey:
    def test_key_format(self):
        from utils.auth import generate_api_key
        raw, hashed = generate_api_key()
        assert raw.startswith("ap_live_")
        assert len(hashed) == 64  # SHA-256 hex

    def test_keys_are_unique(self):
        from utils.auth import generate_api_key
        keys = {generate_api_key()[0] for _ in range(10)}
        assert len(keys) == 10

    def test_hash_deterministic(self):
        from utils.auth import hash_key
        assert hash_key("test123") == hash_key("test123")


class TestAuthenticate:
    def test_valid_key(self, dynamodb, sample_user):
        from utils.auth import authenticate
        user_id, raw_key = sample_user
        event = {"headers": {"x-api-key": raw_key}, "requestContext": {}}
        user = authenticate(event)
        assert user is not None
        assert user["user_id"] == user_id

    def test_invalid_key(self, dynamodb):
        from utils.auth import authenticate
        event = {"headers": {"x-api-key": "ap_live_boguskey"}, "requestContext": {}}
        user = authenticate(event)
        assert user is None

    def test_missing_key(self, dynamodb):
        from utils.auth import authenticate
        event = {"headers": {}, "requestContext": {}}
        assert authenticate(event) is None

    def test_bearer_token(self, dynamodb, sample_user):
        from utils.auth import authenticate
        user_id, raw_key = sample_user
        event = {"headers": {"authorization": f"Bearer {raw_key}"}, "requestContext": {}}
        user = authenticate(event)
        assert user is not None
