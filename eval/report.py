"""Render an EvalReport as a markdown table."""
from __future__ import annotations

from scribe.domain.types import EvalReport


def render_report(report: EvalReport, title: str = "Eval Report") -> str:
    """Return a markdown table of metrics, one row per (component, metric) pair."""
    if not report.metrics:
        return "No metrics collected.\n"

    lines = [
        f"## {title}",
        "",
        "| Component | Metric | Score |",
        "|---|---|---|",
    ]
    for component, scores in report.metrics.items():
        for metric, value in scores.items():
            lines.append(f"| {component} | {metric} | {value:.4f} |")

    return "\n".join(lines) + "\n"
