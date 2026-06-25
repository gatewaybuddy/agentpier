"""
airlock/tests/test_mcp_handlers.py — Tests for MCP tool handlers.

Tests:
  (a) submit_story with leaked account id / bucket name → REJECTED with findings
  (b) clean story → accepted and round-trips via get_story
  (c) search returns scrubbed results

Run with:
  PYTHONPATH=/mnt/d/Projects/agentpier-oss python3 -m pytest airlock/tests/test_mcp_handlers.py -v
"""

import uuid
from datetime import datetime, timezone

import pytest

from airlock.server import handle_get_story, handle_search_stories, handle_submit_story
from airlock.store import StoryStore
from airlock.scrubber import add_to_denylist, _BUCKET_DENYLIST
import airlock.server as _server_mod


# ---------------------------------------------------------------------------
# Fixture: fresh in-memory store for each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_store(tmp_path):
    """Replace the global store with a fresh SQLite DB for each test."""
    test_db = tmp_path / "test_stories.db"
    fresh_store = StoryStore(str(test_db))
    # Patch the module-level _store so handlers use this one
    _server_mod._store = fresh_store
    yield fresh_store
    fresh_store.close()
    _server_mod._store = None


@pytest.fixture(autouse=True)
def seed_denylist():
    """
    Seed the denylist with test names for tests that exercise denylist rejection.
    Uses RFC 2606 / documentation names — no real infrastructure identifiers.
    """
    add_to_denylist(["example-prod-bucket", "example-backups"])
    yield
    # Clear denylist after each test to avoid cross-test pollution
    _BUCKET_DENYLIST.clear()
    from airlock.scrubber import _recompile_denylist
    _recompile_denylist()


# ---------------------------------------------------------------------------
# Story factory helpers
# ---------------------------------------------------------------------------

def _make_story(**overrides) -> dict:
    """Return a minimal valid, clean war story."""
    base = {
        "id": str(uuid.uuid4()),
        "title": "The classic permission boundary miss",
        "situation": "An agent tried to enumerate all resources in a cloud account.",
        "goal": "Map all active resources before migration.",
        "what_i_tried": ["Called describe-instances", "Called list-functions"],
        "what_failed": ["Both returned access denied"],
        "what_worked": "Called GetCallerIdentity first to map the permission scope.",
        "lesson": "Probe your permission boundary before assuming full access.",
        "tags": ["planning", "aws", "iam"],
        "narrator_id": "agent-x",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trust": {
            "confidence": 0.85,
            "verified_by": None,
            "provenance": "self-report",
            "gate_result": None,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# (a) submit_story with sensitive data — REJECTED
# ---------------------------------------------------------------------------

class TestSubmitStoryRejected:
    def test_leaked_account_id_rejected(self):
        """A story containing a 12-digit AWS account id must be rejected."""
        story = _make_story(
            situation=(
                # 123456789012 is AWS's documented example account id —
                # it must be caught by the scrubber just as a real id would be.
                "The agent was operating in account 123456789012 and tried "
                "to enumerate all resources."
            )
        )
        result = handle_submit_story(story)
        assert not result["ok"], f"Expected rejection, got: {result}"
        assert "findings" in result
        assert len(result["findings"]) > 0
        assert any(
            f["rule"] == "AWS_ACCOUNT_ID" for f in result["findings"]
        ), f"Expected AWS_ACCOUNT_ID finding. Got: {result['findings']}"

    def test_leaked_bucket_name_rejected(self):
        """A story mentioning a denylist bucket name must be rejected."""
        story = _make_story(
            what_worked=(
                "Restored from example-prod-bucket and re-ran the job."
            )
        )
        result = handle_submit_story(story)
        assert not result["ok"], f"Expected rejection, got: {result}"
        assert "findings" in result
        assert len(result["findings"]) > 0
        assert any(
            f["rule"] == "DENYLIST_BUCKET" for f in result["findings"]
        ), f"Expected DENYLIST_BUCKET finding. Got: {result['findings']}"

    def test_leaked_private_ip_rejected(self):
        """A story with a private IP must be rejected."""
        story = _make_story(
            situation="The agent connected to 192.168.1.55 to pull config."
        )
        result = handle_submit_story(story)
        assert not result["ok"]
        assert any(
            "IP" in f["rule"] for f in result["findings"]
        ), f"Expected IP finding. Got: {result['findings']}"

    def test_invalid_schema_rejected(self):
        """A story missing required fields must be rejected before gate."""
        story = {"id": str(uuid.uuid4()), "title": "Incomplete"}
        result = handle_submit_story(story)
        assert not result["ok"]
        assert "schema validation" in result["error"]


# ---------------------------------------------------------------------------
# (b) Clean story accepted, round-trips via get_story
# ---------------------------------------------------------------------------

class TestSubmitStoryAccepted:
    def test_clean_story_accepted(self):
        story = _make_story()
        result = handle_submit_story(story)
        assert result["ok"], f"Expected acceptance, got: {result}"
        assert "id" in result

    def test_round_trip_via_get_story(self):
        story = _make_story()
        submit_result = handle_submit_story(story)
        assert submit_result["ok"]

        story_id = submit_result["id"]
        get_result = handle_get_story(story_id)
        assert get_result["ok"], f"get_story failed: {get_result}"
        returned = get_result["story"]

        # Core fields preserved
        assert returned["id"] == story_id
        assert returned["title"] == story["title"]
        assert returned["lesson"] == story["lesson"]
        assert returned["narrator_id"] == story["narrator_id"]

    def test_get_story_not_found(self):
        result = handle_get_story("00000000-0000-4000-8000-000000000000")
        assert not result["ok"]
        assert "not found" in result["error"]

    def test_submitted_story_is_scrubbed_on_egress(self):
        """Even clean stories are scrub()-ed on egress (defense-in-depth)."""
        story = _make_story()
        submit_result = handle_submit_story(story)
        get_result = handle_get_story(submit_result["id"])
        assert get_result["ok"]
        # trust.gate_result must be populated by scrub_story
        trust = get_result["story"]["trust"]
        assert "gate_result" in trust
        assert trust["gate_result"]["clean"] is True


# ---------------------------------------------------------------------------
# (c) search_stories returns scrubbed results
# ---------------------------------------------------------------------------

class TestSearchStories:
    def _seed(self, n: int = 3) -> list[str]:
        ids = []
        for i in range(n):
            story = _make_story(
                id=str(uuid.uuid4()),
                title=f"Lesson about IAM permissions number {i}",
                tags=["planning", "aws", "iam"],
                lesson=f"Always check permission scope first. Lesson variant {i}.",
            )
            r = handle_submit_story(story)
            assert r["ok"], f"Seed failed: {r}"
            ids.append(r["id"])
        return ids

    def test_search_by_keyword(self):
        self._seed(3)
        result = handle_search_stories(query="permission scope")
        assert result["ok"]
        assert result["count"] >= 1

    def test_search_by_tag(self):
        self._seed(2)
        result = handle_search_stories(tags=["planning"])
        assert result["ok"]
        assert result["count"] >= 2

    def test_search_results_are_scrubbed(self):
        """Results from search must be run through scrub_story on egress."""
        self._seed(1)
        result = handle_search_stories(query="permission")
        assert result["ok"]
        for story in result["stories"]:
            # gate_result should be set by scrub_story (egress pass)
            assert "gate_result" in story["trust"]

    def test_search_empty_query_returns_all(self):
        self._seed(3)
        result = handle_search_stories(query="", limit=10)
        assert result["ok"]
        assert result["count"] == 3

    def test_search_limit_respected(self):
        self._seed(5)
        result = handle_search_stories(query="", limit=2)
        assert result["ok"]
        assert result["count"] <= 2

    def test_search_no_results(self):
        self._seed(2)
        result = handle_search_stories(query="zzznomatch")
        assert result["ok"]
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# Regression: search() must not crash when narrative fields are lists
# ---------------------------------------------------------------------------

class TestSearchListFields:
    """
    Regression for store.py search() haystack join crash.

    The schema makes what_i_tried / what_failed arrays. search() was calling
    ' '.join([..., story.get('situation'), ...]) which blows up with
    TypeError: sequence item N: expected str instance, list found
    when any of those values is a list.
    """

    LIST_STORY = {
        "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
        "title": "Reflection failure during tool selection",
        "situation": (
            "An agent chose a destructive tool without checking whether "
            "a read-only alternative existed first."
        ),
        "goal": "Delete stale resources from the environment.",
        "what_i_tried": [
            "Issued a delete command directly on the first pass.",
            "Tried to undo after realising the resource was still referenced.",
        ],
        "what_failed": [
            "The delete was irreversible — no soft-delete flag was set.",
            "Undo path required manual restore from backup.",
        ],
        "what_worked": (
            "Added a pre-flight check: list + classify resources before any "
            "destructive action, require explicit confirmation for irreversible ops."
        ),
        "lesson": (
            "Always enumerate and classify before destroying. "
            "Irreversible actions need an explicit confirmation gate."
        ),
        "tags": ["reflection", "action", "deletion", "production-safety"],
        "narrator_id": "agent-x",
        "timestamp": "2026-06-24T12:00:00+00:00",
        "trust": {
            "confidence": 0.90,
            "verified_by": None,
            "provenance": "self-report",
            "gate_result": None,
        },
    }

    def test_submit_list_story_accepted(self):
        """Schema-valid story with list narrative fields must be accepted."""
        result = handle_submit_story(self.LIST_STORY)
        assert result["ok"], f"Expected acceptance: {result}"

    def test_search_hits_list_field_content(self):
        """search() must not crash and must match words inside list fields."""
        handle_submit_story(self.LIST_STORY)

        # "irreversible" appears only inside what_failed — a list field
        result = handle_search_stories(query="irreversible")
        assert result["ok"], f"search crashed or failed: {result}"
        assert result["count"] >= 1, (
            "Expected match on word inside what_failed list field"
        )

    def test_search_hits_what_i_tried(self):
        """search() must match words inside what_i_tried list."""
        handle_submit_story(self.LIST_STORY)

        # "destructive" appears in what_i_tried[0]
        result = handle_search_stories(query="destructive")
        assert result["ok"]
        assert result["count"] >= 1

    def test_search_results_scrubbed_on_list_story(self):
        """Egress scrub must run even when the story has list fields."""
        handle_submit_story(self.LIST_STORY)
        result = handle_search_stories(query="irreversible")
        assert result["ok"]
        for story in result["stories"]:
            assert "gate_result" in story["trust"]
