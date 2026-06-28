"""ModelHost — internal, hidden (design.md §3).

Owns "ensure model X resident within 16GB, evict others." The sequential-load
dance from plan §2 is localized here; no caller ever sees load()/unload().

Slice 0: minimal single-model residency — just tracks the active model id.
Phase 4 deepens this with real evict/load coordination for the bake-off.
"""

from __future__ import annotations

from typing import Any


class ModelHost:
    """Tracks which model is currently resident (Slice 0: trivial)."""

    def __init__(self, cfg: Any | None = None) -> None:
        self.cfg = cfg or {}
        self._resident: str | None = None

    def ensure_resident(self, model_id: str) -> None:
        # Slice 0: no real eviction; just remember. Phase 4 will add the dance.
        self._resident = model_id

    @property
    def resident(self) -> str | None:
        return self._resident
