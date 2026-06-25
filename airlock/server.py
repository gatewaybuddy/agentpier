"""
airlock/server.py — AgentPier MCP server (robust stdio JSON-RPC 2.0).

SDK status: the real `mcp` Python SDK is not installed. This implementation
is a spec-correct JSON-RPC 2.0 / MCP stdio server that works without it.

SDK swap-in path (when `pip install mcp` is available):
  1. Import:
       from mcp.server import Server
       from mcp.server.stdio import stdio_server
       import asyncio
  2. Replace `run_stdio()` with:
       app = Server("agentpier-airlock")
       @app.list_tools()
       async def list_tools(): return [Tool(...) for each _TOOLS entry]
       @app.call_tool()
       async def call_tool(name, arguments):
           result = _TOOLS[name]["handler"](arguments)
           return [TextContent(type="text", text=json.dumps(result))]
       asyncio.run(stdio_server(app))
  All handler functions (handle_submit_story, etc.) are unchanged.

Tools exposed:
  submit_story(story)                  — validate + gate on ingest; store if clean
  search_stories(query, tags?, limit?) — keyword/tag search; scrub on egress
  get_story(id)                        — fetch one; scrub on egress

Safety contract (never bypass):
  INGEST: schema validate → gate() → reject if dirty → scrub + store if clean
  EGRESS: scrub() every field before returning to any caller

Protocol:
  JSON-RPC 2.0 over stdio, one object per line (newline-delimited).
  Notifications (no "id" field) receive no response.
  Unknown methods → code -32601 (MethodNotFound).
  Parse errors    → code -32700 (ParseError).
  Invalid params  → code -32602 (InvalidParams).
  Server errors   → code -32000.

Run:
  PYTHONPATH=/path/to/agentpier python3 airlock/server.py
  python3 -m airlock.server

See airlock/SKILL.md for Claude Code / Cursor install config.
"""

import json
import os
import sys
from typing import Optional

from airlock.schema import StoryValidationError, scrub_story, validate_story
from airlock.scrubber import gate, load_denylist_from_env
from airlock.store import StoryStore
from airlock.seed_stories import STORY_A_RAW, STORY_B_RAW, STORY_C_RAW

# Load user-configured denylist from env at import time.
# Users set AIRLOCK_BUCKET_DENYLIST=name1,name2 before starting the server.
load_denylist_from_env()


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 error codes
# ---------------------------------------------------------------------------

_PARSE_ERROR      = -32700
_INVALID_REQUEST  = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS   = -32602
_SERVER_ERROR     = -32000


# ---------------------------------------------------------------------------
# Store lifecycle
# ---------------------------------------------------------------------------

_store: Optional[StoryStore] = None


def _get_store() -> StoryStore:
    global _store
    if _store is None:
        # Allow override via env (used by e2e tests and custom installs)
        db_path = os.environ.get("AIRLOCK_DB_PATH")
        _store = StoryStore(db_path) if db_path else StoryStore()
        _seed_if_empty(_store)
    return _store


def _seed_if_empty(store: StoryStore) -> None:
    """Seed the corpus with the 3 canonical war stories on first run."""
    if store.count() > 0:
        return
    for raw in [STORY_A_RAW, STORY_B_RAW, STORY_C_RAW]:
        scrubbed = scrub_story(raw)
        store.put(scrubbed)


# ---------------------------------------------------------------------------
# Tool handlers — these are the stable API; SDK swap does not change them
# ---------------------------------------------------------------------------

def handle_submit_story(story: object) -> dict:
    """
    Validate and gate a story on ingest.

    Returns:
      {"ok": true,  "id": "<uuid>"}
      {"ok": false, "error": "<reason>", "findings": [...]}
    """
    if not isinstance(story, dict):
        return {"ok": False, "error": "story must be a JSON object", "findings": []}

    # 1. Schema validation
    try:
        validate_story(story)
    except StoryValidationError as exc:
        return {"ok": False, "error": f"schema validation failed: {exc}", "findings": []}

    # 2. Gate on ingest — DEFAULT-DENY
    flat = json.dumps(story, default=str)
    gate_result = gate(flat)
    if not gate_result["clean"]:
        return {
            "ok": False,
            "error": "story rejected: sensitive data detected by gate",
            "findings": gate_result["findings"],
        }

    # 3. Scrub all fields (defense-in-depth) and store
    scrubbed = scrub_story(story)
    story_id = _get_store().put(scrubbed)
    return {"ok": True, "id": story_id}


def handle_search_stories(
    query: str = "",
    tags: Optional[list] = None,
    limit: int = 10,
) -> dict:
    """
    Search stories by keyword and/or tag. Results are scrubbed on egress.

    TODO: replace the keyword scan with a VectorIndex for semantic search.
    Hook: store.py::search() → replace with VectorIndex.query(text, k).
    """
    if tags is not None and not isinstance(tags, list):
        return {"ok": False, "error": "'tags' must be a list"}
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    stories = _get_store().search(query=str(query), tags=tags, limit=limit)
    safe = [scrub_story(s) for s in stories]
    return {"ok": True, "count": len(safe), "stories": safe}


def handle_get_story(story_id: object) -> dict:
    """Fetch a single story by id. Scrubbed on egress."""
    if not isinstance(story_id, str):
        return {"ok": False, "error": "'id' must be a string"}
    story = _get_store().get(story_id)
    if story is None:
        return {"ok": False, "error": f"story not found: {story_id!r}"}
    return {"ok": True, "story": scrub_story(story)}


# ---------------------------------------------------------------------------
# MCP tool registry
# SDK swap: replace this dict with @app.list_tools() + @app.call_tool().
# ---------------------------------------------------------------------------

_TOOLS: dict = {
    "submit_story": {
        "description": (
            "Submit a war story. Validated against the AgentPier schema and "
            "run through the safety gate on ingest. Rejected with findings if "
            "any sensitive data is detected (account IDs, IPs, ARNs, secrets, "
            "denylist buckets, PII). Returns the story id on success."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["story"],
            "properties": {
                "story": {
                    "type": "object",
                    "description": (
                        "War story object. Required fields: id (UUID v4), title, "
                        "situation, goal, what_i_tried (list), what_failed (list), "
                        "what_worked, lesson (max 280 chars), tags (list, must include "
                        "at least one of: memory|reflection|planning|action|system), "
                        "narrator_id, timestamp (ISO 8601), trust.confidence (0–1)."
                    ),
                },
            },
        },
        "handler": lambda args: handle_submit_story(args.get("story")),
    },
    "search_stories": {
        "description": (
            "Search war stories by keyword and/or tag. "
            "All results are scrubbed on egress (defense-in-depth). "
            "Returns a list of matching stories."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword to search in title, lesson, situation, goal, what_worked, what_i_tried, what_failed.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tag filter — all listed tags must be present on a story to match.",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of stories to return.",
                },
            },
        },
        "handler": lambda args: handle_search_stories(
            query=args.get("query", ""),
            tags=args.get("tags"),
            limit=args.get("limit", 10),
        ),
    },
    "get_story": {
        "description": "Fetch a single war story by UUID. Scrubbed on egress.",
        "inputSchema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "description": "Story UUID v4."},
            },
        },
        "handler": lambda args: handle_get_story(args.get("id")),
    },
}


# ---------------------------------------------------------------------------
# MCP protocol handlers
# ---------------------------------------------------------------------------

def _handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "agentpier-airlock", "version": "0.1.0"},
    }


def _handle_tools_list(params: dict) -> dict:
    return {
        "tools": [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in _TOOLS.items()
        ]
    }


def _handle_tools_call(params: dict) -> dict:
    tool_name = params.get("name")
    tool_args = params.get("arguments") or {}

    if not isinstance(tool_args, dict):
        raise _RpcError(_INVALID_PARAMS, "'arguments' must be an object")
    if tool_name not in _TOOLS:
        raise _RpcError(_METHOD_NOT_FOUND, f"unknown tool: {tool_name!r}")

    result = _TOOLS[tool_name]["handler"](tool_args)
    return {
        "content": [
            {"type": "text", "text": json.dumps(result, indent=2, default=str)}
        ]
    }


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 dispatch
# ---------------------------------------------------------------------------

class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message


_METHOD_MAP = {
    "initialize":              _handle_initialize,
    "tools/list":              _handle_tools_list,
    "tools/call":              _handle_tools_call,
    # Aliases some clients send
    "mcp/listTools":           _handle_tools_list,
    "mcp/callTool":            _handle_tools_call,
}

# Methods that are notifications — they carry no "id" and need no response
_NOTIFICATION_METHODS = {"notifications/initialized", "$/cancelRequest"}


def _dispatch(request: dict) -> Optional[dict]:
    """
    Route a JSON-RPC 2.0 request to the appropriate handler.
    Returns None for notifications (no response expected).
    """
    method  = request.get("method", "")
    params  = request.get("params") or {}
    req_id  = request.get("id")          # None means notification
    is_notif = "id" not in request

    # Pure notifications — never respond
    if method in _NOTIFICATION_METHODS or is_notif:
        # Still execute if we know the method, but don't return a response
        if method in _METHOD_MAP:
            try:
                _METHOD_MAP[method](params)
            except Exception:
                pass
        return None

    try:
        if not isinstance(params, dict):
            raise _RpcError(_INVALID_PARAMS, "'params' must be an object")
        if method not in _METHOD_MAP:
            raise _RpcError(_METHOD_NOT_FOUND, f"method not found: {method!r}")

        result = _METHOD_MAP[method](params)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    except _RpcError as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": exc.code, "message": exc.message},
        }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": _SERVER_ERROR, "message": str(exc)},
        }


# ---------------------------------------------------------------------------
# stdio transport — newline-delimited JSON, one request per line
# ---------------------------------------------------------------------------

def run_stdio() -> None:
    """
    Read newline-delimited JSON-RPC 2.0 from stdin; write responses to stdout.
    Stderr is used for diagnostic logs so it doesn't pollute the protocol stream.
    """
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": _PARSE_ERROR, "message": f"parse error: {exc}"},
            }
            _write(error_response)
            continue

        if not isinstance(request, dict):
            _write({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": _INVALID_REQUEST, "message": "request must be a JSON object"},
            })
            continue

        response = _dispatch(request)
        if response is not None:
            _write(response)


def _write(obj: dict) -> None:
    """Write a single JSON object as a newline-terminated line to stdout."""
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
