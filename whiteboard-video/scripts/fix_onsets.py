#!/usr/bin/env python3
"""Fix Whisper word onsets after align_captions.py (proven 2026-10-07, "Sạc qua đêm").

Whisper-small folds the silence before a phrase into its first word, so cues start early. This snaps any word
start that falls inside a detected silence to that silence's end, splits words collapsed onto one instant,
interpolates unaligned label words, then rebuilds cues and scene bounds (scene_lead before each scene's first word).

  python3 fix_onsets.py captions/pacing-vNN.json audio/voiceover-vNN.wav captions/pacing-vNNb.json --plan audio/plan-vNN.json
  # short hook takes / tight pauses: --min-silence 0.08

Use the padded voice (the same file the pacing JSON times refer to). Read the printed table; fix remaining cues
with a listened-to value, never a guess."""
import argparse
import json
import re
import subprocess
from pathlib import Path

from ffmpeg_path import find_ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("wav"); ap.add_argument("dst")
ap.add_argument("--plan", required=True, help="plan JSON used for align_captions (gives phrases per scene)")
ap.add_argument("--noise", default="-38dB")
ap.add_argument("--min-silence", type=float, default=0.2)
ap.add_argument("--min-scene", type=float, default=1.0, help="minimum scene length when rebuilding bounds")
args = ap.parse_args()

log = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", args.wav, "-af", f"silencedetect=n={args.noise}:d={args.min_silence}",
                      "-f", "null", "-"], capture_output=True, text=True).stderr
SIL = list(zip([float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)],
               [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]))
P = json.load(open(args.src))
sizes = [len(s["phrases"]) for s in json.load(open(args.plan))]
assert sum(sizes) == len(P["cues"]), f"plan has {sum(sizes)} phrases, pacing has {len(P['cues'])} cues"


def snap(ws):
    for w in ws:
        if w["start"] is None:
            continue
        for a, b in SIL:
            if a - 0.15 <= w["start"] < b and w["end"] is not None and b < w["end"] - 0.06:
                w["start"] = round(b, 3)
    for i in range(1, len(ws)):  # words collapsed onto one instant: give each an even share
        a, b = ws[i - 1], ws[i]
        if None not in (a["start"], b["start"]) and b["start"] <= a["start"] and b["end"] and b["end"] > a["start"]:
            mid = round((a["start"] + b["end"]) / 2, 3); a["end"] = b["start"] = mid
    for i, w in enumerate(ws):  # interpolate unaligned words between neighbours
        if w["start"] is None:
            prev = ws[i - 1]["end"] if i else None
            nxt = next((x["start"] for x in ws[i + 1:] if x["start"] is not None), None)
            if prev is not None and nxt is None:
                nxt = min([a for a, b in SIL if a >= prev - 0.01] or [prev + 0.3])
                nxt = min(nxt, prev + 0.45)
            if prev is not None and nxt is not None and nxt > prev:
                w["start"], w["end"] = prev, round(nxt, 3)


for key in ("words", "label_words"):
    for ws in P[key]:
        snap(ws)
for c, ws in zip(P["cues"], P["label_words"]):
    c[0] = min(w["start"] for w in ws if w["start"] is not None)
    c[1] = max(w["end"] for w in ws if w["end"] is not None)
b, k = [0.0], 0
for s in sizes[:-1]:
    k += s
    first = min(w["start"] for w in P["words"][k] if w["start"] is not None)
    b.append(round(max(b[-1] + args.min_scene, first - P["scene_lead"]), 4))
b.append(P["duration"])
P["bounds"] = b
P["scene_durations"] = [round(y - x, 4) for x, y in zip(b, b[1:])]
P["onset_fix"] = f"word starts inside silencedetect({args.noise},{args.min_silence}s) gaps snapped to gap end; unaligned label words interpolated"
Path(args.dst).write_text(json.dumps(P, ensure_ascii=False, indent=1))
print("bounds", b)
for i, (c, ws) in enumerate(zip(P["cues"], P["label_words"])):
    print(f"{i:2} {c[0]:6.2f} {c[1]:6.2f} " + " ".join(f'{w["text"]}@{w["start"]}' for w in ws))
