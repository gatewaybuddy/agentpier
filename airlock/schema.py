"""
airlock/schema.py — JSON Schema and validator for Airlock war stories.

Every field is scrubbed on ingest and egress via scrub_story().

Tagging spine — AgentErrorTaxonomy controlled vocabulary:
  memory      — the agent forgot, misremembered, or lost context
  reflection  — the agent failed to self-check or evaluate its own output
  planning    — the agent made a bad plan or skipped planning entirely
  action      — the agent took a wrong or destructive action
  system      — infrastructure, environment, or tooling failure

Plus any number of freeform lowercase kebab-case tags.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from airlock.scrubber import gate, scrub

# ---------------------------------------------------------------------------
# AgentErrorTaxonomy — controlled tag vocabulary (failure-mode categories)
# Reference: AgentErrorTaxonomy classification scheme
# ---------------------------------------------------------------------------

TAXONOMY_TAGS: frozenset[str] = frozenset([
    "memory",       # agent forgot, misremembered, or lost context
    "reflection",   # agent failed to self-check or evaluate its own output
    "planning",     # bad plan, skipped planning, wrong decomposition
    "action",       # wrong or destructive action executed
    "system",       # infra, environment, or tooling failure outside agent control
])


# ---------------------------------------------------------------------------
# JSON Schema (Draft-7 compatible)
# ---------------------------------------------------------------------------

STORY_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AgentPier War Story",
    "type": "object",
    "required": [
        "id", "title", "situation", "goal",
        "what_i_tried", "what_failed", "what_worked",
        "lesson", "tags", "narrator_id", "timestamp",
        "trust",
    ],
    "additionalProperties": False,
    "properties": {
        "id": {
            "type": "string",
            "description": "UUID v4 unique story identifier",
            "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        },
        "title": {
            "type": "string",
            "minLength": 3,
            "maxLength": 120,
            "description": "Short, memorable title for the war story",
        },
        "situation": {
            "type": "string",
            "minLength": 10,
            "description": "What was happening — context and environment",
        },
        "goal": {
            "type": "string",
            "minLength": 5,
            "description": "What the agent was trying to accomplish",
        },
        "what_i_tried": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "description": "Ordered list of approaches attempted",
        },
        "what_failed": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "What didn't work and why (can be empty if first try worked)",
        },
        "what_worked": {
            "type": "string",
            "minLength": 5,
            "description": "The approach that succeeded",
        },
        "lesson": {
            "type": "string",
            "minLength": 10,
            "maxLength": 280,
            "description": "Single-line distilled lesson — the takeaway another agent can apply",
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string",
                "pattern": r"^[a-z0-9\-]+$",
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Lowercase kebab-case tags for indexing",
        },
        "narrator_id": {
            "type": "string",
            "minLength": 1,
            "description": "Agent or narrator identifier (e.g. 'my-agent', 'agent-v1')",
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 UTC timestamp of story creation",
        },
        "trust": {
            "type": "object",
            "required": ["confidence"],
            "additionalProperties": False,
            "properties": {
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "0.0–1.0 confidence in lesson accuracy",
                },
                "verified_by": {
                    "type": ["string", "null"],
                    "description": "Agent or human who reviewed this story",
                },
                "provenance": {
                    "type": ["string", "null"],
                    "enum": ["self-report", "observed", "inferred", "human-verified", None],
                    "description": "How was this lesson derived?",
                },
                "gate_result": {
                    "type": ["object", "null"],
                    "description": "Snapshot of scrubber gate() result at ingest time",
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class StoryValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Validator — intentionally lightweight (no jsonschema dep required)
# ---------------------------------------------------------------------------

def _check_uuid4(s: str) -> bool:
    pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    )
    return bool(pattern.match(s))


def validate_story(story: dict) -> None:
    """
    Raise StoryValidationError if the story doesn't conform to STORY_SCHEMA.
    Intentionally simple — enough to catch structural mistakes.
    """
    errors: list[str] = []

    required = STORY_SCHEMA["required"]
    for field in required:
        if field not in story:
            errors.append(f"missing required field: '{field}'")

    if errors:
        raise StoryValidationError("; ".join(errors))

    if not _check_uuid4(story.get("id", "")):
        errors.append("'id' must be a valid UUID v4")

    title = story.get("title", "")
    if not (3 <= len(title) <= 120):
        errors.append(f"'title' length {len(title)} out of range [3, 120]")

    lesson = story.get("lesson", "")
    if not (10 <= len(lesson) <= 280):
        errors.append(f"'lesson' length {len(lesson)} out of range [10, 280]")

    tried = story.get("what_i_tried", [])
    if not isinstance(tried, list) or len(tried) < 1:
        errors.append("'what_i_tried' must be a non-empty list")

    failed = story.get("what_failed", None)
    if failed is not None and not isinstance(failed, list):
        errors.append("'what_failed' must be a list")

    tags = story.get("tags", [])
    if not isinstance(tags, list) or len(tags) < 1:
        errors.append("'tags' must be a non-empty list")
    else:
        tag_pattern = re.compile(r'^[a-z0-9\-]+$')
        for t in tags:
            if not tag_pattern.match(t):
                errors.append(f"tag '{t}' must be lowercase kebab-case")
        # At least one AgentErrorTaxonomy category tag is required
        has_taxonomy_tag = any(t in TAXONOMY_TAGS for t in tags)
        if not has_taxonomy_tag:
            errors.append(
                f"'tags' must include at least one taxonomy tag: "
                f"{sorted(TAXONOMY_TAGS)}"
            )

    trust = story.get("trust", {})
    if not isinstance(trust, dict):
        errors.append("'trust' must be an object")
    elif "confidence" not in trust:
        errors.append("'trust.confidence' is required")
    else:
        conf = trust["confidence"]
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append("'trust.confidence' must be a number in [0.0, 1.0]")

    if errors:
        raise StoryValidationError("; ".join(errors))


# ---------------------------------------------------------------------------
# Scrub helpers
# ---------------------------------------------------------------------------

def _scrub_value(v: Any) -> Any:
    """Recursively scrub string values in a story dict."""
    if isinstance(v, str):
        return scrub(v)
    if isinstance(v, list):
        return [_scrub_value(item) for item in v]
    if isinstance(v, dict):
        return {k: _scrub_value(val) for k, val in v.items()}
    return v


def scrub_story(story: dict) -> dict:
    """
    Return a copy of the story with ALL string fields run through scrub().
    Use on both ingest (before storing) and egress (before publishing).
    Attaches gate_result to trust metadata.
    """
    # Flatten to text for gate check
    flat = json.dumps(story, default=str)
    gate_result = gate(flat)

    scrubbed = _scrub_value(story)
    # Preserve non-string trust fields, set gate_result snapshot
    if "trust" not in scrubbed:
        scrubbed["trust"] = {}
    scrubbed["trust"]["gate_result"] = {
        "clean": gate_result["clean"],
        "finding_count": len(gate_result["findings"]),
    }
    return scrubbed


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def new_story(
    title: str,
    situation: str,
    goal: str,
    what_i_tried: list[str],
    what_failed: list[str],
    what_worked: str,
    lesson: str,
    tags: list[str],
    narrator_id: str,
    confidence: float = 0.8,
    verified_by: str | None = None,
    provenance: str = "self-report",
) -> dict:
    """Build a schema-valid story dict. Does NOT scrub — call scrub_story() after."""
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "situation": situation,
        "goal": goal,
        "what_i_tried": what_i_tried,
        "what_failed": what_failed,
        "what_worked": what_worked,
        "lesson": lesson,
        "tags": tags,
        "narrator_id": narrator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trust": {
            "confidence": confidence,
            "verified_by": verified_by,
            "provenance": provenance,
            "gate_result": None,
        },
    }
