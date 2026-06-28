"""Render an EvalReport as a markdown table + human-eyeball checklist."""
from __future__ import annotations

from scribe.domain.types import EvalReport

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
