"""Render an EvalReport as a markdown table + human-eyeball checklist."""
from __future__ import annotations

from scribe.domain.types import EvalReport
from eval.bakeoff import BakeoffReport

_EYEBALL_CHECKLIST = """\

## 5-Note Human Eyeball Checklist

For 5 randomly sampled generated notes, manually verify:

- [ ] Every SOAP section is populated (no empty sections without clinical cause)
- [ ] No hallucinated medications, doses, or diagnoses absent from the dialogue
- [ ] Speaker attribution looks correct (CLINICIAN vs PATIENT turns)
- [ ] Citation spans are plausible and point to genuine transcript evidence
- [ ] Note reads coherently as a clinical document (no garbled or repeated text)
"""


def render_report(report: EvalReport, title: str = "Eval Report") -> str:
    """Return a markdown metrics table followed by the human-eyeball checklist."""
    if not report.metrics:
        return "No metrics collected.\n" + _EYEBALL_CHECKLIST

    lines = [
        f"## {title}",
        "",
        "| Component | Metric | Score |",
        "|---|---|---|",
    ]
    for component, scores in report.metrics.items():
        for metric, value in scores.items():
            lines.append(f"| {component} | {metric} | {value:.4f} |")

    return "\n".join(lines) + "\n" + _EYEBALL_CHECKLIST


# ── Bake-off report — per-model axis + locked-axes section ────────────────────
def render_bakeoff_report(report: BakeoffReport, title: str = "Bake-off Report") -> str:
    """Render a per-model comparison table.

    Layout:
      * Locked-axes section (WER/DER) — model-invariant, reported once.
      * Per-model section — grounding + completeness, one row per model.
      * Human-eyeball checklist (unchanged from the single-model report).
    """
    lines = [f"## {title}", ""]

    if not report.per_model:
        lines.append("_No models in registry._")
        return "\n".join(lines) + "\n" + _EYEBALL_CHECKLIST

    # ── Locked axes (model-invariant) ────────────────────────────────────────
    locked_components = ("asr", "diarization")
    locked_rows = _collect_locked_rows(report, locked_components)
    if locked_rows:
        lines += ["### Locked axes (model-invariant)", "",
                  "| Component | Metric | Score |",
                  "|---|---|---|"]
        lines.extend(locked_rows)
        lines.append("")

    # ── Per-model comparison ─────────────────────────────────────────────────
    per_model_components = ("completeness", "grounding")
    lines += ["### Per-model comparison", "",
              "| Model | Component | Metric | Score |",
              "|---|---|---|---|"]
    for spec in report.registry.models:
        sub = report.per_model.get(spec.model_id)
        if sub is None:
            continue
        for component in per_model_components:
            scores = sub.metrics.get(component)
            if not scores:
                continue
            for metric, value in scores.items():
                lines.append(f"| {spec.model_id} | {component} | {metric} | {value:.4f} |")
    lines.append("")

    return "\n".join(lines) + _EYEBALL_CHECKLIST


def _collect_locked_rows(report: BakeoffReport, components: tuple[str, ...]) -> list[str]:
    """Pull WER/DER from the first per-model report that has them.

    They're model-invariant by construction; taking them from the first model
    avoids duplicating them per row.
    """
    rows: list[str] = []
    for sub in report.per_model.values():
        for component in components:
            scores = sub.metrics.get(component)
            if not scores:
                continue
            for metric, value in scores.items():
                rows.append(f"| {component} | {metric} | {value:.4f} |")
        if rows:
            break  # one model's locked-axes is enough
    return rows
