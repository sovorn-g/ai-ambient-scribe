"""Drive /ambient/ws end-to-end from a real wav to see what events come back.

Usage:
    .venv/bin/python scripts/debug_ambient_ws.py data/primock57/day1_consultation01.wav

Prints every event the server emits, then exits. Helps diagnose why the live
listening flow produces no final draft in the UI.
"""
from __future__ import annotations

import asyncio
import json
import struct
import sys
import wave
from pathlib import Path

import websockets


WS_URL = "ws://localhost:8000/ambient/ws"


def load_pcm16_mono_16k(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        n_ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    print(f"[wav] channels={n_ch} sampwidth={sw} rate={sr} frames={n} dur={n/sr:.1f}s")
    # decode to int16
    if sw == 2:
        samples = struct.unpack(f"<{n*n_ch}h", raw)
    elif sw == 4:
        ints = struct.unpack(f"<{n*n_ch}i", raw)
        samples = [s >> 16 for s in ints]
    else:
        raise SystemExit(f"unsupported sampwidth {sw}")
    # downmix to mono
    if n_ch > 1:
        mono = []
        for i in range(n):
            mono.append(sum(samples[i*n_ch:(i+1)*n_ch]) // n_ch)
        samples = mono
    # crude resample to 16k by linear skip
    if sr != 16000:
        ratio = sr / 16000
        out_len = int(n / ratio)
        resampled = []
        for i in range(out_len):
            src = i * ratio
            lo = int(src)
            resampled.append(samples[lo])
        samples = resampled
    return struct.pack(f"<{len(samples)}h", *samples)


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: debug_ambient_ws.py <wav>")
    wav_path = Path(sys.argv[1])
    pcm = load_pcm16_mono_16k(wav_path)
    print(f"[pcm] {len(pcm)} bytes = {len(pcm)/2/16000:.1f}s @ 16kHz mono\n")

    chunk_bytes = 16000 * 2 * 1  # 1s chunks
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "start",
            "patient_ref": "patient-debug",
            "encounter_ref": "encounter-debug",
            "sample_rate": 16000,
        }))

        # Interleave send + recv so listening acks can be drained while we stream.
        sent = 0
        for off in range(0, len(pcm), chunk_bytes):
            chunk = pcm[off:off+chunk_bytes]
            await ws.send(chunk)
            sent += 1
            # Drain any pending events without blocking.
            for _ in range(20):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.05)
                except asyncio.TimeoutError:
                    break
                _print_event(msg)
        print(f"[sent] {sent} chunks\n")

        print("\n[sending stop]")
        await ws.send(json.dumps({"type": "stop"}))

        # Drain events until socket closes.
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=180.0)
                _print_event(msg)
        except (asyncio.TimeoutError, websockets.ConnectionClosed) as e:
            print(f"\n[done] {type(e).__name__}")


def _print_event(msg) -> None:
    if isinstance(msg, (bytes, bytearray)):
        print("[recv] binary frame (unexpected)")
        return
    data = json.loads(msg)
    t = data.get("type")
    if t == "draft_ready":
        draft = data.get("draft", {})
        dial = draft.get("dialogue", [])
        note = draft.get("note", {})
        n_claims = sum(len(note.get(k, [])) for k in ("subjective","objective","assessment","plan"))
        print(f"[recv] draft_ready id={draft.get('id')} utterances={len(dial)} claims={n_claims}")
        for u in dial[:3]:
            print(f"         {u.get('role')} {u.get('id')}: {u.get('text')[:80]!r}")
    else:
        print(f"[recv] {t}: {json.dumps({k:v for k,v in data.items() if k!='type'})[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
