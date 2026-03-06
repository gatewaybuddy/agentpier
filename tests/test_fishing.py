"""Tests for the fishing mini-game handlers."""

import json
import time
from decimal import Decimal
from unittest.mock import patch
import pytest
from tests.conftest import make_api_event


class TestCastLine:
    def test_successful_cast(self, dynamodb, sample_user):
        """Test casting line returns a valid catch."""
        from handlers.fishing import cast_line

        _, raw_key = sample_user
        event = make_api_event(method="POST", api_key=raw_key)

        with patch("handlers.fishing.random.randint") as mock_randint, patch(
            "handlers.fishing.random.choice"
        ) as mock_choice, patch("handlers.fishing.random.uniform") as mock_uniform:
            # Mock to always get a common fish
            mock_randint.return_value = 75  # Falls in common fish range (60-79)
            mock_choice.side_effect = lambda x: x[0]  # Always pick first option
            mock_uniform.return_value = 1.5

            resp = cast_line(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["result"] == "catch"
        assert "catch" in body
        assert body["catch"]["type"] == "fish"
        assert body["catch"]["name"] == "Sardine"  # First in species list
        assert body["catch"]["weight_kg"] == 1.5
        assert body["catch"]["rarity"] == "common"
        assert "flavor_text" in body["catch"]
        assert "stats" in body
        assert body["stats"]["total_casts"] == 1
        assert body["stats"]["total_catches"] == 1

    def test_nothing_catch(self, dynamodb, sample_user):
        """Test catching nothing still works."""
        from handlers.fishing import cast_line

        _, raw_key = sample_user
        event = make_api_event(method="POST", api_key=raw_key)

        with patch("handlers.fishing.random.randint") as mock_randint, patch(
            "handlers.fishing.random.choice"
        ) as mock_choice:
            # Mock to always get nothing
            mock_randint.return_value = 10  # Falls in nothing range (1-20)
            mock_choice.side_effect = lambda x: x[0]  # Always pick first option

            resp = cast_line(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["result"] == "nothing"
        assert body["catch"]["type"] == "nothing"
        assert body["catch"]["name"] == "Nothing"
        assert body["catch"]["weight_kg"] == 0.0
        assert body["stats"]["total_casts"] == 1
        assert body["stats"]["total_catches"] == 0  # Nothing doesn't count as catch

    def test_legendary_catch_special_message(self, dynamodb, sample_user):
        """Test that legendary catches get special messages."""
        from handlers.fishing import cast_line

        _, raw_key = sample_user
        event = make_api_event(method="POST", api_key=raw_key)

        with patch("handlers.fishing.random.randint") as mock_randint, patch(
            "handlers.fishing.random.choice"
        ) as mock_choice, patch("handlers.fishing.random.uniform") as mock_uniform:
            # Mock to always get legendary
            mock_randint.return_value = 100  # Falls in legendary range (98-100)
            mock_choice.side_effect = lambda x: x[0]  # Always pick first option
            mock_uniform.return_value = 500.0

            resp = cast_line(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["catch"]["rarity"] == "legendary"
        assert "special_message" in body
        assert "TREMBLES" in body["special_message"]

    def test_rate_limiting(self, dynamodb, sample_user):
        """Test that casting is rate limited to 10 minutes."""
        from handlers.fishing import cast_line

        _, raw_key = sample_user
        event = make_api_event(method="POST", api_key=raw_key)

        # First cast should succeed
        with patch("handlers.fishing.random.randint", return_value=75):
            resp1 = cast_line(event, None)
        assert resp1["statusCode"] == 200

        # Immediate second cast should fail
        with patch("handlers.fishing.random.randint", return_value=75):
            resp2 = cast_line(event, None)
        assert resp2["statusCode"] == 429
        body = json.loads(resp2["body"])
        assert body["error"] == "cast_cooldown"
        assert (
            "m " in body["message"]
            or "s " in body["message"]
            or "minutes" in body["message"]
            or "seconds" in body["message"]
        )

    def test_unauthenticated_cast(self, dynamodb):
        """Test that unauthenticated users cannot cast."""
        from handlers.fishing import cast_line

        event = make_api_event(method="POST")
        resp = cast_line(event, None)

        assert resp["statusCode"] == 401
        body = json.loads(resp["body"])
        assert body["error"] == "unauthorized"

    def test_all_rarities_possible(self, dynamodb, sample_user):
        """Test that all rarity levels can be generated."""
        from handlers.fishing import cast_line

        _, raw_key = sample_user
        event = make_api_event(method="POST", api_key=raw_key)

        rarities_found = set()
        test_cases = [
            (10, "common"),  # Nothing
            (25, "common"),  # Old Boot
            (40, "common"),  # Tin Can
            (50, "common"),  # Seaweed
            (70, "common"),  # Common fish
            (85, "uncommon"),  # Uncommon fish
            (94, "rare"),  # Rare fish
            (99, "legendary"),  # Legendary
        ]

        for i, (roll, expected_rarity) in enumerate(test_cases):
            with patch("handlers.fishing.random.randint", return_value=roll), patch(
                "handlers.fishing.random.choice", side_effect=lambda x: x[0]
            ), patch("handlers.fishing.random.uniform", return_value=1.0), patch(
                "handlers.fishing._check_cast_cooldown", return_value=(True, 0)
            ):  # Bypass cooldown

                resp = cast_line(event, None)
                assert resp["statusCode"] == 200
                body = json.loads(resp["body"])
                rarities_found.add(body["catch"]["rarity"])

        # Should have found all expected rarities
        expected_rarities = {"common", "uncommon", "rare", "legendary"}
        assert rarities_found == expected_rarities


class TestLeaderboard:
    def test_biggest_leaderboard(self, dynamodb, sample_user):
        """Test biggest fish leaderboard."""
        from handlers.fishing import get_leaderboard

        # Add some sample catches to the leaderboard
        user_id, _ = sample_user
        now_iso = "2024-01-01T00:00:00Z"

        # Create catches with different weights
        catches = [
            {"weight": 50.5, "name": "Big Tuna", "rarity": "rare"},
            {"weight": 25.0, "name": "Salmon", "rarity": "uncommon"},
            {"weight": 100.0, "name": "Marlin", "rarity": "rare"},
        ]

        for i, catch in enumerate(catches):
            weight_padded = f"{catch['weight']:08.1f}"
            dynamodb.put_item(
                Item={
                    "PK": f"USER#{user_id}",
                    "SK": f"CATCH#{1000000 + i}",
                    "GSI2PK": "PIER#LEADERBOARD",
                    "GSI2SK": f"{weight_padded}#{user_id}",
                    "catch_name": catch["name"],
                    "weight_kg": Decimal(str(catch["weight"])),
                    "rarity": catch["rarity"],
                    "username": "testbot",
                    "user_id": user_id,
                    "created_at": now_iso,
                }
            )

        event = make_api_event(method="GET", query_params={"type": "biggest"})
        resp = get_leaderboard(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["type"] == "biggest"
        assert body["title"] == "🏆 Biggest Catches"
        assert len(body["entries"]) == 3
        # Should be sorted by weight descending
        assert body["entries"][0]["weight_kg"] == 100.0
        assert body["entries"][0]["catch_name"] == "Marlin"

    def test_recent_leaderboard(self, dynamodb, sample_user):
        """Test recent catches leaderboard."""
        from handlers.fishing import get_leaderboard

        event = make_api_event(method="GET", query_params={"type": "recent"})
        resp = get_leaderboard(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["type"] == "recent"
        assert body["title"] == "🕒 Recent Catches"

    def test_most_active_leaderboard(self, dynamodb, sample_user):
        """Test most active anglers leaderboard."""
        from handlers.fishing import get_leaderboard

        event = make_api_event(method="GET", query_params={"type": "most"})
        resp = get_leaderboard(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["type"] == "most"
        assert body["title"] == "🎣 Most Active Anglers"

    def test_invalid_leaderboard_type(self, dynamodb):
        """Test invalid leaderboard type returns error."""
        from handlers.fishing import get_leaderboard

        event = make_api_event(method="GET", query_params={"type": "invalid"})
        resp = get_leaderboard(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["error"] == "invalid_type"


class TestTackleBox:
    def test_get_tackle_box_authenticated(self, dynamodb, sample_user):
        """Test getting user's tackle box."""
        from handlers.fishing import get_tackle_box

        user_id, raw_key = sample_user

        # Add a sample catch
        now_iso = "2024-01-01T00:00:00Z"
        dynamodb.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "CATCH#1000000",
                "catch_name": "Test Fish",
                "catch_type": "fish",
                "weight_kg": Decimal("5.5"),
                "rarity": "common",
                "flavor_text": "A nice test fish!",
                "created_at": now_iso,
            }
        )

        event = make_api_event(method="GET", api_key=raw_key)
        resp = get_tackle_box(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert "catches" in body
        assert "stats" in body
        assert len(body["catches"]) == 1
        assert body["catches"][0]["catch_name"] == "Test Fish"
        assert body["catches"][0]["weight_kg"] == 5.5
        assert body["stats"]["total_catches"] == 1

    def test_tackle_box_pagination(self, dynamodb, sample_user):
        """Test tackle box respects limit parameter."""
        from handlers.fishing import get_tackle_box

        _, raw_key = sample_user
        event = make_api_event(
            method="GET", api_key=raw_key, query_params={"limit": "5"}
        )
        resp = get_tackle_box(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["pagination"]["limit"] == 5

    def test_tackle_box_unauthenticated(self, dynamodb):
        """Test that unauthenticated users cannot access tackle box."""
        from handlers.fishing import get_tackle_box

        event = make_api_event(method="GET")
        resp = get_tackle_box(event, None)

        assert resp["statusCode"] == 401


class TestPierStats:
    def test_pier_stats_no_catches(self, dynamodb):
        """Test pier stats when no catches exist."""
        from handlers.fishing import get_pier_stats

        event = make_api_event(method="GET")
        resp = get_pier_stats(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["total_casts"] == 0
        assert body["total_catches"] == 0
        assert body["biggest_fish"] is None
        assert body["rarest_catch"] is None
        assert body["most_active_angler"] is None
        assert body["legendary_catches"] == 0
        assert "no catches yet" in body["pier_status"]

    def test_pier_stats_with_catches(self, dynamodb, sample_user):
        """Test pier stats with some catches."""
        from handlers.fishing import get_pier_stats

        user_id, _ = sample_user
        now_iso = "2024-01-01T00:00:00Z"

        # Add sample catches
        catches = [
            {"weight": 50.5, "name": "Big Tuna", "rarity": "rare"},
            {"weight": 250.0, "name": "Pier Kraken", "rarity": "legendary"},
        ]

        for i, catch in enumerate(catches):
            weight_padded = f"{catch['weight']:08.1f}"
            dynamodb.put_item(
                Item={
                    "PK": f"USER#{user_id}",
                    "SK": f"CATCH#{1000000 + i}",
                    "GSI2PK": "PIER#LEADERBOARD",
                    "GSI2SK": f"{weight_padded}#{user_id}",
                    "catch_name": catch["name"],
                    "weight_kg": Decimal(str(catch["weight"])),
                    "rarity": catch["rarity"],
                    "username": "testbot",
                    "user_id": user_id,
                    "created_at": now_iso,
                }
            )

        event = make_api_event(method="GET")
        resp = get_pier_stats(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])

        assert body["total_catches"] == 2
        assert body["biggest_fish"]["weight_kg"] == 250.0
        assert body["biggest_fish"]["name"] == "Pier Kraken"
        assert body["rarest_catch"]["rarity"] == "legendary"
        assert body["legendary_catches"] == 1
        assert body["most_active_angler"]["username"] == "testbot"
        assert body["most_active_angler"]["total_catches"] == 2

    def test_pier_stats_status_messages(self, dynamodb):
        """Test that pier status messages vary based on activity."""
        from handlers.fishing import _get_pier_status_message

        # Test different activity levels (note: 0 catches is handled separately in get_pier_stats)
        assert "Early days" in _get_pier_status_message(5, 0)
        assert "getting popular" in _get_pier_status_message(15, 0)
        assert "Business is good" in _get_pier_status_message(75, 0)
        assert "bustling" in _get_pier_status_message(150, 0)
        assert "mystical energy" in _get_pier_status_message(50, 1)
        assert "legendary" in _get_pier_status_message(50, 6)
