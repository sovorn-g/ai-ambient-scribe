"""Slice-0 CLI adapter — thin (design.md §5: cli is NOT a seam).

Plays a hardcoded PriMock57 wav → DialogueExtractor → NoteGenerator → Draft →
y/n approval gate → writes FHIR JSON to disk. This is the walking skeleton's
"manual; needs Ollama + mlx-whisper" smoke path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scribe.composition import build_scribe
from scribe.domain.types import Approver, EditedDraft, PatientContext


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Ambient Scribe — Slice 0 walking skeleton")
    parser.add_argument("--audio", required=True, help="Path to a wav file (e.g. PriMock57 sample)")
    parser.add_argument(
        "--out",
        default="out/documentreference.json",
        help="Where to write the FHIR DocumentReference JSON",
    )
    parser.add_argument("--patient-id", default="primock-patient-01")
    parser.add_argument("--encounter-id", default="primock-encounter-01")
    parser.add_argument("--approver", default="Dr. Slice Zero")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive y/n gate (NOT for real use — defeats HITL)",
    )
    args = parser.parse_args(argv)

    cfg: dict[str, Any] = {
        "audio_path": args.audio,
        "patient_ref": args.patient_id,
        "encounter_ref": args.encounter_id,
    }
    scribe = build_scribe(cfg)

    audio = scribe._audio_source.load()  # thin CLI adapter — reaching for the seam is fine here
    ctx = PatientContext(
        patient_ref=args.patient_id,
        encounter_ref=args.encounter_id,
        patient_display="PriMock57 Sample Patient",
    )

    print("[scribe] generating draft…", file=sys.stderr)
    draft = scribe.generateDraft(audio, ctx)
    _print_note(draft.note)

    if not args.yes:
        choice = input("\nApprove this note and export FHIR? [y/N]: ").strip().lower()
        if choice != "y":
            print("[scribe] not approved — nothing written.", file=sys.stderr)
            return 1

    edited = EditedDraft(
        id=draft.id,
        ctx=draft.ctx,
        dialogue=draft.dialogue,
        note=draft.note,
        provenance=draft.provenance,
    )
    doc = scribe.approveAndExport(edited, Approver(name=args.approver, role="clinician"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc.json_text, encoding="utf-8")
    print(f"[scribe] wrote FHIR DocumentReference → {out_path}", file=sys.stderr)
    return 0


def _print_note(note: Any) -> None:
    for section in ("subjective", "objective", "assessment", "plan"):
        print(f"\n== {section.upper()} ==")
        for i, claim in enumerate(getattr(note, section), 1):
            print(f"{i}. {claim.text}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
