#!/usr/bin/env python3
"""Score every TTS take of every chapter against its input text with Whisper and pick the closest one.

Inputs in PROJECT/audio/: tts-input-<tag>-ch<N>.txt (the exact text sent to TTS) and
voice-<tag>-ch<N>-take<T>.mp3 (one file per take). Writes audio/take-scores-<tag>.json:
{"scores": {file: {dur, ratio, ref_words, hyp_words, diffs}}, "pick": {N: T}}. Read the diffs of the
picked takes before using them: a high ratio can still hide one wrong number.

  uv run --offline --no-project --python 3.12 --with mlx-whisper --with numpy python \
      $SKILL/scripts/pick_takes.py PROJECT --tag v01
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_captions import DEFAULT_MODEL  # noqa: E402
from ffmpeg_path import find_ffmpeg  # noqa: E402


def words(s):
    return re.findall(r"\w+", unicodedata.normalize("NFC", s.lower()))


def decode(p):
    raw = subprocess.run([find_ffmpeg(), "-v", "error", "-i", str(p), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--tag", default="v01")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--language", default="vi")
    args = ap.parse_args()
    audio = args.project.resolve() / "audio"
    out = audio / f"take-scores-{args.tag}.json"
    assert not out.exists(), f"{out} exists; bump the tag"
    inputs = sorted(audio.glob(f"tts-input-{args.tag}-ch*.txt"), key=lambda p: int(p.stem.rsplit("ch", 1)[1]))
    assert inputs, f"no {audio}/tts-input-{args.tag}-ch*.txt"
    import mlx_whisper

    res, pick = {}, {}
    for txt in inputs:
        ch = int(txt.stem.rsplit("ch", 1)[1])
        ref = words(txt.read_text())
        takes = sorted(audio.glob(f"voice-{args.tag}-ch{ch}-take*.mp3"))
        assert takes, f"no takes for chapter {ch}"
        for p in takes:
            a = decode(p)
            hyp = words(mlx_whisper.transcribe(a, path_or_hf_repo=args.model, language=args.language,
                                               verbose=None)["text"])
            sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
            miss = [" ".join(ref[i1:i2]) for op, i1, i2, _, _ in sm.get_opcodes() if op in ("delete", "replace")]
            res[p.name] = {"dur": round(len(a) / 16000, 2), "ratio": round(sm.ratio(), 4), "ref_words": len(ref),
                           "hyp_words": len(hyp), "diffs": miss[:25]}
            print(p.name, res[p.name]["dur"], res[p.name]["ratio"], len(ref), len(hyp), flush=True)
        best = max(takes, key=lambda p: res[p.name]["ratio"])
        pick[ch] = int(best.stem.rsplit("take", 1)[1])
    out.write_text(json.dumps({"scores": res, "pick": pick}, ensure_ascii=False, indent=1))
    print("pick", pick, "->", out)


if __name__ == "__main__":
    main()
