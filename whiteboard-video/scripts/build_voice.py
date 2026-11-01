#!/usr/bin/env python3
"""Join the picked take of every chapter (audio/take-scores-<tag>.json from pick_takes.py) into one mono
48 kHz wav with a short silence between chapters: audio/voice-raw-<tag>.wav plus audio/voice-offsets-<tag>.json.

  uv run --offline --no-project --python 3.12 --with numpy python $SKILL/scripts/build_voice.py PROJECT --tag v01
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_path import find_ffmpeg  # noqa: E402

SR = 48000


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--tag", default="v01")
    ap.add_argument("--gap", type=float, default=0.9, help="seconds of silence between chapters")
    args = ap.parse_args()
    audio = args.project.resolve() / "audio"
    raw_out, offs_out = audio / f"voice-raw-{args.tag}.wav", audio / f"voice-offsets-{args.tag}.json"
    for p in (raw_out, offs_out):
        assert not p.exists(), f"{p} exists; bump the tag"
    pick = json.loads((audio / f"take-scores-{args.tag}.json").read_text())["pick"]

    parts, offsets, t = [], {}, 0.0
    for i, ch in enumerate(sorted(pick, key=int)):
        name = f"voice-{args.tag}-ch{ch}-take{pick[ch]}.mp3"
        raw = subprocess.run([find_ffmpeg(), "-v", "error", "-i", str(audio / name), "-ac", "1", "-ar", str(SR),
                              "-f", "s16le", "-"], capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.int16)
        if i:
            parts.append(np.zeros(int(args.gap * SR), np.int16))
            t += args.gap
        offsets[ch] = {"take": name, "start": round(t, 3), "dur": round(len(a) / SR, 3)}
        parts.append(a)
        t += len(a) / SR

    with wave.open(str(raw_out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.concatenate(parts).tobytes())
    offs_out.write_text(json.dumps(offsets, ensure_ascii=False, indent=1))
    print(f"voice {t:.2f}s -> {raw_out}")


if __name__ == "__main__":
    main()
