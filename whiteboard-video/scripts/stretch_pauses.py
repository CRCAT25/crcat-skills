#!/usr/bin/env python3
"""Lengthen the beats between sentences of an aligned voice without time-stretching the speech.

Inserts silence at the quietest 20 ms of each inter-sentence gap: BASE everywhere, plus PARA after a
paragraph end, CHAPTER before a new chapter, plus scenes.PAUSE[(chapter, k)] before sentence k. Every
cue/word time moves with it. Reads captions/pacing-<src>b.json (fix_onsets.py output) and the voice it
names; writes audio/voiceover-<tag>.wav, captions/pacing-<tag>b.json and captions/subtitles-<tag>.srt,
so `TAG=<tag> render.py ...` then uses the stretched timing.

  uv run --offline --no-project --python 3.12 --with pillow --with numpy --with scipy python \
      $SKILL/scripts/stretch_pauses.py PROJECT --src v01 --tag v02
"""
import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--src", default="v01", help="tag of the aligned voice")
    ap.add_argument("--tag", default="v02", help="tag of the stretched output")
    ap.add_argument("--base", type=float, default=0.15)
    ap.add_argument("--para", type=float, default=0.65)
    ap.add_argument("--chapter", type=float, default=1.8)
    args = ap.parse_args()
    root = args.project.resolve()
    sys.path.insert(0, str(root))
    from narration import CHAPTERS, PARAGRAPH_ENDS
    from scenes import PAUSE

    pacing = json.loads((root / f"captions/pacing-{args.src}b.json").read_text())
    keys = [(ch, k) for ch in sorted(CHAPTERS) for k in range(len(CHAPTERS[ch][1]))]
    cues = pacing["cues"]
    assert len(keys) == len(cues), "script.md and the pacing file disagree"
    wav = root / f"audio/voiceover-{args.tag}.wav"
    for p in (wav, root / f"captions/pacing-{args.tag}b.json"):
        assert not p.exists(), f"{p} exists; bump the tag"

    src_wav = root / (pacing.get("audio") or f"audio/voiceover-{args.src}.wav")
    with wave.open(str(src_wav)) as w:
        sr, nch = w.getframerate(), w.getnchannels()
        assert w.getsampwidth() == 2
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, nch)

    win = int(sr * 0.02)
    inserts = []  # (sample position, seconds of silence)
    for i in range(len(keys) - 1):
        (ch, k), nxt = keys[i], keys[i + 1]
        extra = args.base + PAUSE.get(nxt, 0.0)
        extra += args.chapter if nxt[0] != ch else (args.para if k in PARAGRAPH_ENDS.get(ch, ()) else 0.0)
        g0, g1 = int(cues[i][1] * sr), int(cues[i + 1][0] * sr)
        seg = np.abs(a[g0:g1].astype(np.float32)).mean(1)
        if len(seg) > win:
            rms = np.convolve(seg, np.ones(win) / win, "valid")
            pos = g0 + int(np.argmin(rms)) + win // 2
        else:
            pos = (g0 + g1) // 2
        inserts.append((pos, extra))

    parts, last = [], 0
    for pos, extra in inserts:
        parts += [a[last:pos], np.zeros((int(round(extra * sr)), nch), np.int16)]
        last = pos
    parts.append(a[last:])
    out = np.concatenate(parts)

    def shift(i, t):  # every time inside sentence i moves by the silence inserted before it
        return round(t + sum(e for _, e in inserts[:i]), 3)

    new = dict(pacing)
    new["cues"] = [[shift(i, c[0]), shift(i, c[1]), *c[2:]] for i, c in enumerate(cues)]
    for field in ("words", "label_words"):
        if field in pacing:
            new[field] = [[{**wd, "start": shift(i, wd["start"]), "end": shift(i, wd["end"])} for wd in ws]
                          for i, ws in enumerate(pacing[field])]
    new["duration"] = round(len(out) / sr, 3)
    new["audio"] = f"audio/voiceover-{args.tag}.wav"
    new["pause_stretch"] = {"base": args.base, "paragraph": args.para, "chapter": args.chapter,
                            "added_s": round(sum(e for _, e in inserts), 2)}
    for f in ("bounds", "scene_durations"):
        new.pop(f, None)

    with wave.open(str(wav), "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out.tobytes())
    (root / f"captions/pacing-{args.tag}b.json").write_text(json.dumps(new, ensure_ascii=False, indent=1))
    if all(len(c) > 2 for c in new["cues"]):
        srt = "\n".join(f"{n + 1}\n{ts(max(0, c[0] - 0.03))} --> {ts(c[1])}\n{c[2]}\n"
                        for n, c in enumerate(new["cues"]))
        (root / f"captions/subtitles-{args.tag}.srt").write_text(srt)
    print(f"added {new['pause_stretch']['added_s']} s -> voice {new['duration']} s; "
          f"last cue ends {new['cues'][-1][1]}")


if __name__ == "__main__":
    main()
