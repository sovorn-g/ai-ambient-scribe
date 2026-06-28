"""DraftStore [seam] — design.md §5. REAL (sqlite/file + in-memory fake).

The in-memory fake is the second adapter that makes this seam real and keeps
``Scribe`` end-to-end testable with no DB. Phase 5 fills the sqlite adapter.
"""

from __future__ import annotations

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
