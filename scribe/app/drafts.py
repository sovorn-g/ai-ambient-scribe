"""DraftStore [seam] — design.md §5. REAL (sqlite/file + in-memory fake).

The in-memory fake is the second adapter that makes this seam real and keeps
``Scribe`` end-to-end testable with no DB. Phase 5 fills the sqlite adapter.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod

from scribe.domain.types import Draft, EditedDraft


class DraftStore(ABC):
    """Persists drafts between generation and approval."""

    @abstractmethod
    def save(self, draft: Draft) -> str:
        """Store a draft, return its id."""
        raise NotImplementedError

    @abstractmethod
    def get(self, draft_id: str) -> Draft:
        """Retrieve a draft by id. Raise KeyError if absent."""
        raise NotImplementedError

    @abstractmethod
    def update(self, edited: EditedDraft) -> None:
        """Persist edits to an existing draft."""
        raise NotImplementedError


class InMemoryDraftStore(DraftStore):
    """Slice-0 / test adapter. Not durable — process-local dict."""

    def __init__(self) -> None:
        self._drafts: dict[str, Draft | EditedDraft] = {}

    def save(self, draft: Draft) -> str:
        self._drafts[draft.id] = draft
        return draft.id

    def get(self, draft_id: str) -> Draft:
        if draft_id not in self._drafts:
            raise KeyError(f"No draft with id {draft_id!r}")
        return self._drafts[draft_id]

    def update(self, edited: EditedDraft) -> None:
        if edited.id not in self._drafts:
            raise KeyError(f"Cannot update unknown draft {edited.id!r}")
        self._drafts[edited.id] = edited


class SqliteDraftStore(DraftStore):
    """Durable adapter backed by SQLite. Phase 5 production path."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,   -- 'draft' | 'edited'
        payload TEXT NOT NULL -- JSON blob
    )
    """

    def __init__(self, db_path: str = "drafts.db") -> None:
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(self._DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, draft: Draft) -> str:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO drafts (id, kind, payload) VALUES (?, ?, ?)",
                (draft.id, "draft", draft.model_dump_json()),
            )
        return draft.id

    def get(self, draft_id: str) -> Draft:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT kind, payload FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"No draft with id {draft_id!r}")
        if row["kind"] == "edited":
            return EditedDraft.model_validate_json(row["payload"])
        return Draft.model_validate_json(row["payload"])

    def update(self, edited: EditedDraft) -> None:
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE drafts SET kind = 'edited', payload = ? WHERE id = ?",
                (edited.model_dump_json(), edited.id),
            )
        if result.rowcount == 0:
            raise KeyError(f"Cannot update unknown draft {edited.id!r}")
