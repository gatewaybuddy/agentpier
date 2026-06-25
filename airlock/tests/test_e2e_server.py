"""
airlock/tests/test_e2e_server.py — End-to-end smoke test for the Airlock MCP server.

Spawns server.py as a subprocess and speaks to it over stdio using real
JSON-RPC 2.0 wire protocol. Proves the transport layer works end-to-end,
not just the in-process handlers.

Run:
  PYTHONPATH=/mnt/d/Projects/agentpier-oss python3 -m pytest airlock/tests/test_e2e_server.py -v -s
"""

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Absolute path to the server module
_SERVER = str(Path(__file__).parent.parent / "server.py")
_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)  # contains airlock/


# ---------------------------------------------------------------------------
# Wire helpers
# ---------------------------------------------------------------------------

class ServerProcess:
    """Context manager wrapping the Airlock MCP server subprocess."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "ServerProcess":
        env = {
            "PYTHONPATH": _PROJECT_ROOT,
            "AIRLOCK_DB_PATH": self.db_path,
            "PATH": "/usr/bin:/bin",
        }
        self.proc = subprocess.Popen(
            [sys.executable, _SERVER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,          # line-buffered
        )
        return self

    def __exit__(self, *_) -> None:
        if self.proc:
            self.proc.stdin.close()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def send(self, obj: dict) -> None:
        """Write one JSON-RPC request to the server's stdin."""
        line = json.dumps(obj) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def recv(self, timeout: float = 5.0) -> dict:
        """
        Read one JSON-RPC response from stdout.
        Uses readline — the server emits one object per line.
        """
        line = self.proc.stdout.readline()
        if not line:
            raise EOFError("server stdout closed unexpectedly")
        return json.loads(line.strip())

    def call(self, req_id: int, method: str, params: dict | None = None) -> dict:
        """Send a request and return the response."""
        self.send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        return self.recv()

    def notify(self, method: str, params: dict | None = None) -> None:
        """Send a notification (no id, no response expected)."""
        self.send({"jsonrpc": "2.0", "method": method, "params": params or {}})


def _clean_story(uid: str | None = None) -> dict:
    """Return a schema-valid, gate-clean war story."""
    return {
        "id": uid or str(uuid.uuid4()),
        "title": "E2E test: permission boundary probe",
        "situation": "An agent tried to enumerate resources in a cloud account.",
        "goal": "Produce a full resource map before a migration.",
        "what_i_tried": [
            "Called describe-instances on all regions.",
            "Called list-functions on Lambda.",
        ],
        "what_failed": [
            "Both returned AccessDenied — the credential was scoped.",
        ],
        "what_worked": (
            "Called GetCallerIdentity first to map the permission scope, "
            "then scoped the inventory to only accessible services."
        ),
        "lesson": (
            "Probe your permission boundary before assuming full access. "
            "A scoped key looks identical to broad access until the first denial."
        ),
        "tags": ["planning", "aws", "iam", "least-privilege"],
        "narrator_id": "agent-e2e",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trust": {
            "confidence": 0.88,
            "verified_by": None,
            "provenance": "self-report",
            "gate_result": None,
        },
    }


def _leaked_story(uid: str | None = None) -> dict:
    """
    Return a story that contains a leaked AWS account id.
    Uses 123456789012 — AWS's documented example id — which the
    scrubber catches just as it would a real 12-digit account id.
    """
    s = _clean_story(uid or str(uuid.uuid4()))
    s["situation"] = (
        "The agent was operating in AWS account 123456789012 and attempted "
        "to enumerate all resources before a migration."
    )
    return s


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def server(tmp_path):
    db = str(tmp_path / "e2e.db")
    with ServerProcess(db_path=db) as srv:
        # MCP handshake
        resp = srv.call(1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test", "version": "0.1"},
        })
        assert resp["result"]["serverInfo"]["name"] == "agentpier-airlock"
        srv.notify("notifications/initialized")
        yield srv


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

class TestE2EServer:
    def test_tools_list(self, server: ServerProcess):
        """tools/list returns the three registered tools."""
        resp = server.call(2, "tools/list")
        assert "result" in resp, f"Unexpected error: {resp}"
        tools = {t["name"] for t in resp["result"]["tools"]}
        assert tools == {"submit_story", "search_stories", "get_story"}, (
            f"Unexpected tool set: {tools}"
        )

    def test_submit_clean_story_accepted(self, server: ServerProcess):
        """A clean story is accepted and returns an id."""
        story = _clean_story()
        resp = server.call(3, "tools/call", {
            "name": "submit_story",
            "arguments": {"story": story},
        })
        assert "result" in resp, f"RPC error: {resp}"
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["ok"] is True, f"Story rejected: {payload}"
        assert "id" in payload

    def test_get_story_round_trip(self, server: ServerProcess):
        """Submit a story then retrieve it by id; content is preserved and scrubbed."""
        story = _clean_story()
        # Submit
        submit_resp = server.call(4, "tools/call", {
            "name": "submit_story",
            "arguments": {"story": story},
        })
        assert "result" in submit_resp
        story_id = json.loads(submit_resp["result"]["content"][0]["text"])["id"]

        # Retrieve
        get_resp = server.call(5, "tools/call", {
            "name": "get_story",
            "arguments": {"id": story_id},
        })
        assert "result" in get_resp
        payload = json.loads(get_resp["result"]["content"][0]["text"])
        assert payload["ok"] is True
        returned = payload["story"]
        assert returned["id"] == story_id
        assert returned["title"] == story["title"]
        assert returned["lesson"] == story["lesson"]
        # Egress scrub stamps gate_result
        assert returned["trust"]["gate_result"]["clean"] is True

    def test_submit_leaked_story_rejected_with_findings(self, server: ServerProcess):
        """A story with a leaked AWS account id is rejected; findings are returned."""
        story = _leaked_story()
        resp = server.call(6, "tools/call", {
            "name": "submit_story",
            "arguments": {"story": story},
        })
        assert "result" in resp, f"RPC error: {resp}"
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["ok"] is False, "Expected rejection of leaked story"
        assert len(payload["findings"]) > 0, "Expected findings to be non-empty"
        assert any(
            f["rule"] == "AWS_ACCOUNT_ID" for f in payload["findings"]
        ), f"Expected AWS_ACCOUNT_ID finding. Got: {payload['findings']}"

    def test_search_returns_scrubbed_results(self, server: ServerProcess):
        """Search returns matching stories with egress scrub applied."""
        # Seed one story
        server.call(7, "tools/call", {
            "name": "submit_story",
            "arguments": {"story": _clean_story()},
        })

        search_resp = server.call(8, "tools/call", {
            "name": "search_stories",
            "arguments": {"query": "permission boundary", "limit": 5},
        })
        assert "result" in search_resp
        payload = json.loads(search_resp["result"]["content"][0]["text"])
        assert payload["ok"] is True
        assert payload["count"] >= 1
        for story in payload["stories"]:
            # gate_result set by scrub_story on egress
            assert "gate_result" in story["trust"], (
                "Egress scrub must set gate_result"
            )

    def test_get_story_not_found(self, server: ServerProcess):
        """get_story with a nonexistent id returns ok=False."""
        resp = server.call(9, "tools/call", {
            "name": "get_story",
            "arguments": {"id": "00000000-0000-4000-8000-000000000000"},
        })
        assert "result" in resp
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["ok"] is False
        assert "not found" in payload["error"]

    def test_unknown_method_returns_method_not_found(self, server: ServerProcess):
        """An unknown JSON-RPC method returns code -32601."""
        resp = server.call(10, "rpc.bogus")
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_parse_error_on_malformed_json(self, server: ServerProcess):
        """Malformed JSON on the wire returns a parse error response."""
        server.proc.stdin.write("this is not json\n")
        server.proc.stdin.flush()
        resp = server.recv()
        assert "error" in resp
        assert resp["error"]["code"] == -32700

    def test_notification_gets_no_response(self, server: ServerProcess):
        """
        notifications/initialized is a one-way message; the server must not reply.
        We send the notification then immediately send a known request and assert
        we get exactly ONE response (the request's), not two.
        """
        server.notify("notifications/initialized")
        # Follow with a real request
        server.send({"jsonrpc": "2.0", "id": 99, "method": "tools/list", "params": {}})
        resp = server.recv()
        # Must be the tools/list response, not a spurious notification ack
        assert resp.get("id") == 99
        assert "result" in resp

    def test_unknown_tool_returns_error(self, server: ServerProcess):
        """Calling a non-existent tool returns an error payload."""
        resp = server.call(11, "tools/call", {
            "name": "delete_everything",
            "arguments": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] in (-32601, -32000)
