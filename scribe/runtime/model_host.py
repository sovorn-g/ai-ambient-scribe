"""ModelHost — internal, hidden (design.md §3).

Owns "ensure model X resident within 16GB, evict others." The sequential-load
dance from plan §2 is localized here; no caller ever sees ``load()``/``unload()``.

Phase 4 deepens this from the Slice-0 single-model tracker into an
ensure-then-evict coordinator: when the requested model differs from the
current resident, the previous resident is evicted *before* the new one is
loaded, so the bake-off runs sequentially within the 16GB budget.

The actual Ollama load/unload is injected as ``loader`` / ``evictor`` callbacks
(defaults are no-ops). That keeps the host testable with fakes — no real 7B in
CI — and lets the composition root wire in real Ollama commands when they're
available, without leaking Ollama into this module.
"""

from __future__ import annotations

from typing import Callable, Any


class ModelHost:
    """Tracks which model is resident; evicts others within a fixed budget.

    Args:
        cfg:           optional config dict (kept for Phase-0 signature compat).
        loader:        ``callable(model_tag) -> None`` invoked when a model
                       needs to be loaded. Default: no-op.
        evictor:       ``callable(model_tag) -> None`` invoked when the
                       previous resident is evicted. Default: no-op.
        memory_budget_gb: advisory budget; not enforced yet (single-resident
                       sequential model). Phase 4+ may use it for planning.
    """

    def __init__(
        self,
        cfg: Any | None = None,
        *,
        loader: Callable[[str], None] | None = None,
        evictor: Callable[[str], None] | None = None,
        memory_budget_gb: float = 16.0,
    ) -> None:
        self.cfg = cfg or {}
        self._loader = loader
        self._evictor = evictor
        self.memory_budget_gb = float(memory_budget_gb)
        self._resident: str | None = None
        self._loaded: set[str] = set()
        self.evictions: list[str] = []  # exposed for test inspection

    def ensure_resident(self, model_tag: str) -> None:
        """Make ``model_tag`` the resident, evicting the previous one first.

        No-op when ``model_tag`` is already resident. Otherwise:
          1. If a different model is currently resident, evict it.
          2. Load ``model_tag`` (idempotent — skipped if already loaded).
          3. Mark it resident.
        """
        if model_tag == self._resident:
            return
        if self._resident is not None:
            self._evict(self._resident)
        if model_tag not in self._loaded:
            self._load(model_tag)
        self._resident = model_tag

    @property
    def resident(self) -> str | None:
        return self._resident

    # ── internals ────────────────────────────────────────────────────────────
    def _load(self, tag: str) -> None:
        if self._loader is not None:
            self._loader(tag)
        self._loaded.add(tag)

    def _evict(self, tag: str) -> None:
        if self._evictor is not None:
            self._evictor(tag)
        self._loaded.discard(tag)
        self.evictions.append(tag)
