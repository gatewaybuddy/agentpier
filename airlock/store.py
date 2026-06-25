"""
airlock/store.py — SQLite-backed story store for AgentPier.

Flat, dependency-light. One table. JSON blob per story.
Storage path is configurable; defaults to airlock/data/stories.db.

Usage:
    from airlock.store import StoryStore
    db = StoryStore()          # default path
    db = StoryStore("/path/to/stories.db")
    db.put(story_dict)
    story = db.get(story_id)
    results = db.search("permission boundary", tags=["planning"], limit=10)
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

# Default storage location — relative to this file's parent directory
_DEFAULT_DB = Path(__file__).parent / "data" / "stories.db"


def _flatten(v: object) -> str:
    """Return a searchable string from a field that may be str, list[str], or None."""
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(str(item) for item in v)
    return str(v)


class StoryStore:
    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id        TEXT PRIMARY KEY,
                title     TEXT NOT NULL,
                tags      TEXT NOT NULL,   -- JSON array
                narrator  TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data      TEXT NOT NULL    -- full JSON blob
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_narrator ON stories(narrator)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON stories(timestamp)
        """)
        self._conn.commit()

    def put(self, story: dict) -> str:
        """Insert or replace a story. Returns the story id."""
        sid = story["id"]
        self._conn.execute(
            """
            INSERT OR REPLACE INTO stories (id, title, tags, narrator, timestamp, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                story.get("title", ""),
                json.dumps(story.get("tags", [])),
                story.get("narrator_id", ""),
                story.get("timestamp", ""),
                json.dumps(story, default=str),
            ),
        )
        self._conn.commit()
        return sid

    def get(self, story_id: str) -> Optional[dict]:
        """Fetch one story by id. Returns None if not found."""
        row = self._conn.execute(
            "SELECT data FROM stories WHERE id = ?", (story_id,)
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def search(
        self,
        query: str = "",
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Simple keyword + tag search. Returns up to `limit` stories.

        TODO: replace with embedding/semantic search when a vector store
        is wired in. The interface (query, tags, limit) is stable.
        """
        rows = self._conn.execute(
            "SELECT id, title, tags, data FROM stories ORDER BY timestamp DESC LIMIT 200"
        ).fetchall()

        results: list[dict] = []
        query_lower = query.lower()

        for row in rows:
            story = json.loads(row["data"])
            story_tags: list[str] = json.loads(row["tags"])

            # Tag filter — all requested tags must be present
            if tags:
                if not all(t in story_tags for t in tags):
                    continue

            # Keyword match — query against all narrative fields.
            # Fields may be str or list[str]; _flatten() handles both.
            if query_lower:
                haystack = " ".join([
                    _flatten(story.get("title")),
                    _flatten(story.get("lesson")),
                    _flatten(story.get("situation")),
                    _flatten(story.get("goal")),
                    _flatten(story.get("what_worked")),
                    _flatten(story.get("what_i_tried")),
                    _flatten(story.get("what_failed")),
                ]).lower()
                if query_lower not in haystack:
                    continue

            results.append(story)
            if len(results) >= limit:
                break

        return results

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as n FROM stories").fetchone()
        return row["n"]

    def close(self) -> None:
        self._conn.close()
