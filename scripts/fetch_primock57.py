"""Fetch + reshape PriMock57 into the layout `eval.datasets.primock57` expects.

The upstream repo (https://github.com/babylonhealth/primock57, CC BY 4.0) ships
each consultation as **two** channel-split wavs (`*_doctor.wav`, `*_patient.wav`)
plus two Praat TextGrids and one clinician note JSON. Our `PriMock57Dataset`
adapter expects a flat `data/primock57/<stem>.{wav,txt,rttm}` layout so the
harness can treat each consultation as a single mixed-audio stream with a
reference transcript + reference diarization.

This script:
  1. Clones the upstream repo with Git LFS into a cache dir.
  2. For every consultation stem `dayN_consultationM`:
       * mixes doctor + patient wavs into one stream via ffmpeg `amix`
         (falls back to the doctor channel alone if the patient wav is missing)
       * parses both TextGrids, merges non-empty intervals in time order, and
         writes:
           - `<stem>.txt`   flat reference transcript (time-ordered utterances)
           - `<stem>.rttm`  reference diarization (one line per turn)
       * copies the clinician note to `<stem>.note.json`
  3. Copies LICENSE.md for attribution.

Idempotent: skips a consultation if its mixed wav already exists.

Usage:
    .venv/bin/python scripts/fetch_primock57.py
    .venv/bin/python scripts/fetch_primock57.py --force   # re-mix + re-derive
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/babylonhealth/primock57.git"
DEFAULT_CACHE = Path("data/.cache/primock57-raw")
DEFAULT_OUT = Path("data/primock57")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def clone_with_lfs(cache: Path) -> None:
    if (cache / "audio").exists():
        print(f"[clone] cache already present at {cache}, skipping clone")
        return
    cache.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("git-lfs") is None:
        sys.exit("[fatal] git-lfs not on PATH; run `brew install git-lfs` first.")
    run(["git", "lfs", "install"], cwd=cache.parent)
    run(["git", "clone", REPO_URL, str(cache)])


# ── TextGrid parsing ──────────────────────────────────────────────────────────
_INTERVAL_RE = re.compile(
    r"intervals\s*\[(\d+)\]:\s*\n\s*xmin\s*=\s*([\d.]+)\s*\n"
    r"\s*xmax\s*=\s*([\d.]+)\s*\n\s*text\s*=\s*\"(.*?)\"",
    re.DOTALL,
)
_TIER_NAME_RE = re.compile(r'name\s*=\s*"(.*?)"')


def parse_textgrid(path: Path) -> list[tuple[float, float, str]]:
    """Return [(xmin, xmax, text), ...] for every interval in the first tier."""
    text = path.read_text(encoding="utf-8")
    # Strip Praat's inside-out quotes: ""foo"" -> "foo"
    intervals = []
    for m in _INTERVAL_RE.finditer(text):
        _, xmin, xmax, raw = m.groups()
        # Praat escapes " as "" inside strings.
        cleaned = raw.replace('""', '"').strip()
        intervals.append((float(xmin), float(xmax), cleaned))
    return intervals


def normalize_text(s: str) -> str:
    # Drop Praat annotation tokens we don't want in a flat transcript.
    s = re.sub(r"<UNIN/>", "", s)
    s = re.sub(r"<UNSAFE>(.*?)</UNSAFE>", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── per-consultation conversion ───────────────────────────────────────────────
def mix_wavs(doctor: Path, patient: Path | None, out: Path) -> None:
    """Mix doctor + patient channels into one wav via ffmpeg amix."""
    if patient is not None and patient.exists():
        run([
            "ffmpeg", "-y",
            "-i", str(doctor),
            "-i", str(patient),
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=longest:dropout_transition=0[a]",
            "-map", "[a]",
            "-ac", "1",               # mono — matches our diarizer's expectation
            "-ar", "16000",           # 16 kHz — sherpa-onnx + mlx-whisper default
            str(out),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        run([
            "ffmpeg", "-y", "-i", str(doctor),
            "-ac", "1", "-ar", "16000",
            str(out),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write_txt_and_rttm(
    doctor_tg: Path,
    patient_tg: Path | None,
    out_txt: Path,
    out_rttm: Path,
) -> None:
    """Merge both TextGrids in time order → flat txt + RTTM.

    RTTM format (head fields, tab-separated):
        type  file  channel  onset  duration  <NA>  speaker  <NA>  <NA>  <NA>
    """
    turns: list[tuple[float, float, str, str]] = []  # (onset, end, text, speaker)
    for tg, speaker in ((doctor_tg, "doctor"), (patient_tg, "patient")):
        if tg is None or not tg.exists():
            continue
        for xmin, xmax, raw in parse_textgrid(tg):
            text = normalize_text(raw)
            if not text:
                continue
            turns.append((xmin, xmax, text, speaker))
    turns.sort(key=lambda t: t[0])

    txt_lines = [t[2] for t in turns]
    out_txt.write_text("\n".join(txt_lines) + ("\n" if txt_lines else ""), encoding="utf-8")

    rttm_lines = []
    for onset, end, _text, speaker in turns:
        dur = max(0.0, end - onset)
        rttm_lines.append(
            f"SPEAKER\t{out_rttm.stem}\t1\t{onset:.3f}\t{dur:.3f}\t<NA>\t<NA>\t{speaker}\t<NA>\t<NA>"
        )
    out_rttm.write_text("\n".join(rttm_lines) + ("\n" if rttm_lines else ""), encoding="utf-8")


def convert_one(stem: str, cache: Path, out: Path, force: bool) -> None:
    doctor_wav = cache / "audio" / f"{stem}_doctor.wav"
    patient_wav = cache / "audio" / f"{stem}_patient.wav"
    doctor_tg = cache / "transcripts" / f"{stem}_doctor.TextGrid"
    patient_tg = cache / "transcripts" / f"{stem}_patient.TextGrid"
    note_json = cache / "notes" / f"{stem}.json"

    out_wav = out / f"{stem}.wav"
    out_txt = out / f"{stem}.txt"
    out_rttm = out / f"{stem}.rttm"
    out_note = out / f"{stem}.note.json"

    if not force and out_wav.exists() and out_txt.exists():
        print(f"[skip] {stem} already converted")
        return

    if not doctor_wav.exists():
        print(f"[warn] no doctor wav for {stem}, skipping")
        return

    print(f"[conv] {stem}")
    mix_wavs(doctor_wav, patient_wav, out_wav)
    write_txt_and_rttm(doctor_tg, patient_tg, out_txt, out_rttm)
    if note_json.exists():
        shutil.copy2(note_json, out_note)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true", help="re-derive even if outputs exist")
    ap.add_argument("--no-clone", action="store_true", help="skip clone (use existing cache)")
    args = ap.parse_args()

    if not args.no_clone:
        clone_with_lfs(args.cache)

    args.out.mkdir(parents=True, exist_ok=True)
    out_gitignore = args.out / ".gitignore"
    if not out_gitignore.exists():
        out_gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")

    # Discover consultation stems from the doctor wavs.
    audio_dir = args.cache / "audio"
    if not audio_dir.exists():
        sys.exit(f"[fatal] {audio_dir} missing — clone failed?")
    stems = sorted({p.name.removesuffix("_doctor.wav")
                    for p in audio_dir.glob("*_doctor.wav")})
    print(f"[scan] {len(stems)} consultations")
    for stem in stems:
        convert_one(stem, args.cache, args.out, force=args.force)

    # Attribution
    src_license = args.cache / "LICENSE.md"
    if src_license.exists():
        shutil.copy2(src_license, args.out / "LICENSE.md")

    wavs = list(args.out.glob("*.wav"))
    txts = list(args.out.glob("*.txt"))
    rttms = list(args.out.glob("*.rttm"))
    print(f"[done] {len(wavs)} wavs, {len(txts)} transcripts, {len(rttms)} rttm "
          f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
