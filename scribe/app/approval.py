"""approval.py — the ONLY door from EditedDraft to ApprovedNote (design.md §4).

The human-in-the-loop guarantee is *structural*: ``ApprovedNote`` cannot be
constructed without the module-private ``_APPROVAL_KEY`` sentinel, which only
this module holds. There is no path from ``Draft`` to ``DocumentRef`` that
skips ``approve()``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from scribe.domain.types import (
    _APPROVAL_KEY,  # module-private sentinel — not for external use
    Approver,
    ApprovedNote,
    EditedDraft,
)


def approve(edited: EditedDraft, approver: Approver) -> ApprovedNote:
    """Sign off on an edited draft. The sole constructor of ``ApprovedNote``."""
    return ApprovedNote(
        note=edited.note,
        approver=approver,
        approved_at=datetime.now(timezone.utc),
        ctx=edited.ctx,
        _approval_key=_APPROVAL_KEY,
    )
