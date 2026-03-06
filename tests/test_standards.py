"""Tests for certification standards API endpoints."""

import json
import re
import pytest

from tests.conftest import make_api_event


class TestGetStandardsCurrent:
    """Tests for GET /standards/current."""

    def test_returns_current_version(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert "version" in body
        assert "effective_date" in body
        assert "standards" in body

    def test_version_is_semver(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        body = json.loads(resp["body"])

        # Validate semver format: MAJOR.MINOR.PATCH
        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(
            semver_pattern, body["version"]
        ), f"Version {body['version']} is not valid semver"

    def test_includes_agent_and_marketplace_sections(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        body = json.loads(resp["body"])

        assert "agent" in body["standards"]
        assert "marketplace" in body["standards"]

    def test_agent_section_lists_categories(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        body = json.loads(resp["body"])

        agent = body["standards"]["agent"]
        assert "categories" in agent
        assert "reliability" in agent["categories"]
        assert "safety" in agent["categories"]
        assert "transparency" in agent["categories"]
        assert "accountability" in agent["categories"]

    def test_marketplace_section_lists_dimensions(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        body = json.loads(resp["body"])

        marketplace = body["standards"]["marketplace"]
        assert "dimensions" in marketplace
        assert "data_quality" in marketplace["dimensions"]
        assert "reporting_volume" in marketplace["dimensions"]
        assert "fairness" in marketplace["dimensions"]
        assert "integration_health" in marketplace["dimensions"]
        assert "dispute_resolution" in marketplace["dimensions"]

    def test_includes_document_urls(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        body = json.loads(resp["body"])

        assert "document_url" in body["standards"]["agent"]
        assert "document_url" in body["standards"]["marketplace"]

    def test_no_scoring_formulas_in_response(self):
        from handlers.standards import get_standards_current

        event = make_api_event(method="GET", path="/standards/current")
        resp = get_standards_current(event, {})
        raw = resp["body"]

        # Must NOT contain any scoring internals
        forbidden = [
            "weight",
            "formula",
            "decay",
            "half_life",
            "half-life",
            "lambda",
            "coefficient",
            "multiplier",
            "algorithm",
        ]
        raw_lower = raw.lower()
        for term in forbidden:
            assert (
                term not in raw_lower
            ), f"Response contains forbidden scoring term: '{term}'"


class TestGetStandardsAgent:
    """Tests for GET /standards/agent."""

    def test_returns_agent_standards(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert "version" in body
        assert "categories" in body

    def test_includes_all_four_categories(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        categories = body["categories"]
        assert "reliability" in categories
        assert "safety" in categories
        assert "transparency" in categories
        assert "accountability" in categories
        assert len(categories) == 4

    def test_each_category_has_standards(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        for cat_key, cat_data in body["categories"].items():
            assert "name" in cat_data, f"{cat_key} missing name"
            assert "description" in cat_data, f"{cat_key} missing description"
            assert "standards" in cat_data, f"{cat_key} missing standards"
            assert len(cat_data["standards"]) > 0, f"{cat_key} has no standards"

    def test_each_standard_has_required_fields(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        for cat_key, cat_data in body["categories"].items():
            for standard in cat_data["standards"]:
                assert "id" in standard, f"{cat_key} standard missing id"
                assert "name" in standard, f"{cat_key} standard missing name"
                assert (
                    "requirement" in standard
                ), f"{cat_key} standard missing requirement"
                assert "tiers" in standard, f"{cat_key} standard missing tiers"

    def test_tiers_include_all_badge_levels(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        expected_tiers = {"verified", "trusted", "certified", "enterprise"}
        for cat_key, cat_data in body["categories"].items():
            for standard in cat_data["standards"]:
                tier_keys = set(standard["tiers"].keys())
                assert (
                    tier_keys == expected_tiers
                ), f"Standard {standard['id']} has tiers {tier_keys}, expected {expected_tiers}"

    def test_version_is_semver(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, body["version"])

    def test_includes_scoring_integrity(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        assert "scoring_integrity" in body
        si = body["scoring_integrity"]
        assert "published" in si
        assert "proprietary" in si
        assert "rationale" in si

    def test_no_scoring_formulas_in_response(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        raw = resp["body"]

        # Scoring internals must never leak into public standards
        forbidden_patterns = [
            r"\b0\.\d{2,}\b.*weight",  # decimal weights like 0.35
            r"decay.*\d+\.\d+",  # decay parameters
            r"lambda.*=.*\d",  # lambda values
            r"half.life.*\d+",  # half-life values
        ]
        for pattern in forbidden_patterns:
            assert not re.search(
                pattern, raw, re.IGNORECASE
            ), f"Response matches forbidden scoring pattern: {pattern}"

    def test_standard_ids_are_unique(self):
        from handlers.standards import get_standards_agent

        event = make_api_event(method="GET", path="/standards/agent")
        resp = get_standards_agent(event, {})
        body = json.loads(resp["body"])

        all_ids = []
        for cat_data in body["categories"].values():
            for standard in cat_data["standards"]:
                all_ids.append(standard["id"])

        assert len(all_ids) == len(set(all_ids)), "Standard IDs are not unique"


class TestGetStandardsMarketplace:
    """Tests for GET /standards/marketplace."""

    def test_returns_marketplace_standards(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        assert resp["statusCode"] == 200

        body = json.loads(resp["body"])
        assert "version" in body
        assert "dimensions" in body

    def test_includes_all_dimensions(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        dimensions = body["dimensions"]
        assert "data_quality" in dimensions
        assert "reporting_volume" in dimensions
        assert "fairness" in dimensions
        assert "integration_health" in dimensions
        assert "dispute_resolution" in dimensions
        assert len(dimensions) == 5

    def test_each_dimension_has_standards(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        for dim_key, dim_data in body["dimensions"].items():
            assert "name" in dim_data, f"{dim_key} missing name"
            assert "description" in dim_data, f"{dim_key} missing description"
            assert "standards" in dim_data, f"{dim_key} missing standards"
            assert len(dim_data["standards"]) > 0, f"{dim_key} has no standards"

    def test_each_standard_has_required_fields(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        for dim_key, dim_data in body["dimensions"].items():
            for standard in dim_data["standards"]:
                assert "id" in standard, f"{dim_key} standard missing id"
                assert "name" in standard, f"{dim_key} standard missing name"
                assert (
                    "requirement" in standard
                ), f"{dim_key} standard missing requirement"
                assert "tiers" in standard, f"{dim_key} standard missing tiers"

    def test_marketplace_tiers_include_all_levels(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        expected_tiers = {
            "registered",
            "verified",
            "trusted",
            "certified",
            "enterprise",
        }
        for dim_key, dim_data in body["dimensions"].items():
            for standard in dim_data["standards"]:
                tier_keys = set(standard["tiers"].keys())
                assert (
                    tier_keys == expected_tiers
                ), f"Standard {standard['id']} has tiers {tier_keys}, expected {expected_tiers}"

    def test_version_is_semver(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        semver_pattern = r"^\d+\.\d+\.\d+$"
        assert re.match(semver_pattern, body["version"])

    def test_includes_scoring_integrity(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        assert "scoring_integrity" in body
        si = body["scoring_integrity"]
        assert "published" in si
        assert "proprietary" in si

    def test_no_scoring_formulas_in_response(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        raw = resp["body"]

        # Must not contain dimension weight values
        forbidden = [
            "0.30",
            "0.20",
            "0.15",  # actual dimension weights from scoring
            "weight_factor",
            "source_weight",
            "decay_rate",
            "half_life",
        ]
        for term in forbidden:
            assert (
                term not in raw
            ), f"Response contains forbidden scoring detail: '{term}'"

    def test_standard_ids_are_unique(self):
        from handlers.standards import get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/marketplace")
        resp = get_standards_marketplace(event, {})
        body = json.loads(resp["body"])

        all_ids = []
        for dim_data in body["dimensions"].values():
            for standard in dim_data["standards"]:
                all_ids.append(standard["id"])

        assert len(all_ids) == len(set(all_ids)), "Standard IDs are not unique"


class TestCrossEndpointConsistency:
    """Verify consistency across endpoints."""

    def test_versions_match_across_endpoints(self):
        from handlers.standards import (
            get_standards_current,
            get_standards_agent,
            get_standards_marketplace,
        )

        event = make_api_event(method="GET", path="/standards/current")
        current = json.loads(get_standards_current(event, {})["body"])

        event = make_api_event(method="GET", path="/standards/agent")
        agent = json.loads(get_standards_agent(event, {})["body"])

        event = make_api_event(method="GET", path="/standards/marketplace")
        marketplace = json.loads(get_standards_marketplace(event, {})["body"])

        assert current["version"] == agent["version"]
        assert current["version"] == marketplace["version"]

    def test_current_endpoint_categories_match_agent(self):
        from handlers.standards import get_standards_current, get_standards_agent

        event = make_api_event(method="GET", path="/standards/current")
        current = json.loads(get_standards_current(event, {})["body"])

        event = make_api_event(method="GET", path="/standards/agent")
        agent = json.loads(get_standards_agent(event, {})["body"])

        listed_categories = set(current["standards"]["agent"]["categories"])
        actual_categories = set(agent["categories"].keys())
        assert listed_categories == actual_categories

    def test_current_endpoint_dimensions_match_marketplace(self):
        from handlers.standards import get_standards_current, get_standards_marketplace

        event = make_api_event(method="GET", path="/standards/current")
        current = json.loads(get_standards_current(event, {})["body"])

        event = make_api_event(method="GET", path="/standards/marketplace")
        marketplace = json.loads(get_standards_marketplace(event, {})["body"])

        listed_dimensions = set(current["standards"]["marketplace"]["dimensions"])
        actual_dimensions = set(marketplace["dimensions"].keys())
        assert listed_dimensions == actual_dimensions
