"""scribe.app — public surface + approval gate + draft persistence."""

from scribe.app.approval import approve
from scribe.app.drafts import DraftStore, InMemoryDraftStore
from scribe.app.scribe import Scribe

__all__ = ["Scribe", "DraftStore", "InMemoryDraftStore", "approve"]
