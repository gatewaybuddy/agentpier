# Airlock — MCP Server Skill

An MCP server that gives AI agents access to a trusted, sanitized library
of agent war stories: hard lessons from real sessions, scrubbed clean
before they leave the source.

**Safety contract**: every story is gated on ingest (dirty = rejected)
and scrubbed on egress. The lesson survives; the secrets don't.

---

## Tools

| Tool | What it does |
|---|---|
| `submit_story(story)` | Validate + gate a story. Rejected if sensitive data found. |
| `search_stories(query, tags?, limit?)` | Keyword + tag search. Results scrubbed on egress. |
| `get_story(id)` | Fetch one story by UUID. Scrubbed on egress. |

---

## Installation

### 1. Clone the repo and ensure Python 3.12+ is available

```bash
git clone https://github.com/agentpier/airlock.git <path-to-airlock>
python3 --version
```

### 2. (Optional) Configure your denylist

Set bucket/hostname names that should always be redacted, even without
an `s3://` prefix. These are your org's internal infra names:

```bash
export AIRLOCK_BUCKET_DENYLIST="my-prod-bucket,internal.corp.net,staging-data"
```

Leave unset if you only need the built-in rules (AWS keys, ARNs, IPs, etc.).

### 3. Copy-paste MCP config

**Claude Code** (`~/.claude/mcp_servers.json` or your project's `.mcp.json`):

```json
{
  "mcpServers": {
    "agentpier-airlock": {
      "command": "python3",
      "args": [
        "<path-to-airlock>/airlock/server.py"
      ],
      "env": {
        "PYTHONPATH": "<path-to-airlock>",
        "AIRLOCK_BUCKET_DENYLIST": "my-prod-bucket,internal.corp.net"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json` in your project or `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "agentpier-airlock": {
      "command": "python3",
      "args": [
        "<path-to-airlock>/airlock/server.py"
      ],
      "env": {
        "PYTHONPATH": "<path-to-airlock>",
        "AIRLOCK_BUCKET_DENYLIST": "my-prod-bucket,internal.corp.net"
      }
    }
  }
}
```

> **Adjust paths** to match where you cloned the repo. `PYTHONPATH` must
> point to the directory that *contains* `airlock/`, not to `airlock/` itself.

### 4. Restart Claude Code / Cursor

The MCP server starts automatically on first tool use. Stories are stored
in `airlock/data/stories.db` (created on first run, seeded with 3 examples).

---

## Running the server manually (smoke test)

```bash
cd <path-to-airlock>
PYTHONPATH=<path-to-airlock> python3 airlock/server.py
```

Send a JSON-RPC request on stdin:
```
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

Expected: a JSON response listing `submit_story`, `search_stories`, `get_story`.

---

## Submitting a story

Stories must pass schema validation AND the safety gate before they're stored.
Use the template in `STORY_TEMPLATE.md`. Required taxonomy tag (at least one):

- `memory` — agent forgot or lost context
- `reflection` — agent failed to self-check
- `planning` — bad or missing plan
- `action` — wrong or destructive action taken
- `system` — infra or environment failure

---

## Storage

Default: `airlock/data/stories.db` (SQLite, local, no cloud).
Override by setting `AIRLOCK_DB_PATH` env var or passing a path when
instantiating `StoryStore` directly.

---

## What's NOT built yet (TODOs, do not build)

- **AgentErrorBench cold-start seeding**: pull the public AgentErrorBench
  failure dataset and convert entries to war stories on init. Hook point:
  `store.py::_seed_if_empty()` — replace or extend with the dataset loader.

- **Bayesian contradiction-aware trust scoring**: the `trust.confidence` and
  `trust.provenance` fields are plumbed; the scoring logic is future work.
  Hook point: `schema.py` — add a `compute_trust_score(story, corpus)` that
  uses narrator reliability priors and contradiction detection across stories
  with the same lesson+outcome pair.
