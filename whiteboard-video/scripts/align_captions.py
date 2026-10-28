#!/usr/bin/env python3
"""Word-aligned pacing + SRT from the real narration (ASR mapped onto the settled script).

Plan JSON (list of scenes, each with spoken phrases and on-screen caption labels):
  [{"name": "Hook", "phrases": [{"speech": "iPhone mười tám Pro không đáng mua?",
                                 "label": "iPhone 18 Pro không đáng mua?"}]}, ...]

Run (Apple Silicon, offline):
  uv run --offline --no-project --with mlx-whisper --with numpy python align_captions.py \
      PROJECT/audio/plan.json PROJECT/audio/voice-raw.wav --out-dir PROJECT/captions --tag v01 \
      --prompt "iPhone 18 Pro, A20 Pro, ..." --padded-audio PROJECT/audio/voiceover-v01.wav

Writes pacing-<tag>.json (duration, fps, bounds, cues, words, label_words, scene_durations,
alignment_coverage, start_pad) and subtitles-<tag>.srt. Timings never come from the
storyboard: they are the ASR word timestamps of this exact recording plus a fixed start lead.
"""
import argparse
import difflib
import json
import math
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_path import find_ffmpeg  # noqa: E402

DEFAULT_MODEL = next((p for p in (Path.home() / ".cache/whiteboard-video/whisper-small-mlx",
                       Path.home() / ".cache/tiktok-ai-video/whisper-small-mlx") if p.exists()),
                     "mlx-community/whisper-small-mlx")  # local copy, else download from Hugging Face
DIGITS = "không một hai ba bốn năm sáu bảy tám chín".split()
DEFAULT_REPLACEMENTS = {"%": " phần trăm", "GB": " gigabyte", "TB": " terabyte", "MP": " megapixel"}


def read_two(n):
    tens, unit = divmod(n, 10)
    if tens == 0:
        return DIGITS[unit]
    head = "mười" if tens == 1 else f"{DIGITS[tens]} mươi"
    if unit == 0:
        return head
    tail = {1: "mốt" if tens > 1 else "một", 5: "lăm"}.get(unit, DIGITS[unit])
    return f"{head} {tail}"


def read_three(n, full):
    hundreds, rest = divmod(n, 100)
    if not full and hundreds == 0:
        return read_two(rest)
    words = f"{DIGITS[hundreds]} trăm"
    if rest == 0:
        return words
    return f"{words} linh {DIGITS[rest]}" if rest < 10 else f"{words} {read_two(rest)}"


def vi_number(n):
    """Spell a non-negative integer in Vietnamese (Northern): 21 -> hai mươi mốt."""
    if n == 0:
        return DIGITS[0]
    groups = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ"]
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        parts.append(read_three(g, full=i != len(groups) - 1))
        if units[i]:
            parts.append(units[i])
    return " ".join(parts)


def spell_numbers(text):
    text = re.sub(r"\d{1,3}(?:\.\d{3})+(?![\d,])", lambda m: m.group().replace(".", ""), text)
    text = re.sub(
        r"(\d+)[,.](\d+)",
        lambda m: f" {vi_number(int(m.group(1)))} phẩy {' '.join(DIGITS[int(c)] for c in m.group(2))} ",
        text,
    )
    return re.sub(r"\d+", lambda m: f" {vi_number(int(m.group()))} ", text)


def make_tokenizer(replacements):
    def tokens(text):
        for a, b in replacements.items():
            text = text.replace(a, b)
        text = spell_numbers(text)
        text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
        return re.findall("[a-z0-9]+", "".join(c for c in text if unicodedata.category(c) != "Mn"))

    return tokens


def decode(path, rate):
    import numpy as np

    raw = subprocess.check_output([find_ffmpeg(), "-v", "error", "-i", str(path), "-ar", str(rate), "-ac", "1", "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32).copy()


def transcribe(audio, model, language, prompt):
    import mlx_whisper

    return mlx_whisper.transcribe(
        decode(audio, 16000), path_or_hf_repo=str(model), language=language,
        word_timestamps=True, initial_prompt=prompt or None, verbose=False,
    )


def stamp(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def match(expected, actual):
    mapping = {}
    for a, b, n in difflib.SequenceMatcher(None, expected, [x[0] for x in actual], autojunk=False).get_matching_blocks():
        for k in range(n):
            mapping[a + k] = b + k
    return mapping


def word_spans(texts, tokens, mapping, actual, offset, fallback):
    """Time each display word from its matched ASR tokens; interpolate or drop when unmatched."""
    out, k = [], offset
    start, end, first, last = fallback
    for text in texts:
        n = len(tokens(text))
        ids = [mapping[q] for q in range(k, k + n) if q in mapping]
        if ids:
            ws, we = actual[min(ids)][1], actual[max(ids)][2]
        elif start is not None and n:
            ws = start + (end - start) * (k - first) / max(1, last - first)
            we = start + (end - start) * (k + n - first) / max(1, last - first)
        else:
            ws = we = None  # e.g. a caption-only word: never highlighted, never invented
        out.append({"text": text, "start": ws, "end": we})
        k += n
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("audio", type=Path, help="raw narration as delivered by TTS (any FFmpeg-readable format)")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tag", required=True, help="version suffix, e.g. v03")
    ap.add_argument("--asr", type=Path, help="reuse an existing ASR JSON instead of transcribing")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--language", default="vi")
    ap.add_argument("--prompt", default="", help="Whisper initial prompt: product names and jargon")
    ap.add_argument("--replace", type=Path, help="JSON {text: spoken} applied before tokenizing (e.g. {\"A19\": \"A mười chín\"})")
    ap.add_argument("--lead", type=float, default=0.24, help="silence before the first word (s)")
    ap.add_argument("--scene-lead", type=float, default=0.6, help="scene visual starts this long before its first clause")
    ap.add_argument("--tail", type=float, default=0.8, help="hold after the last word when --duration is omitted")
    ap.add_argument("--duration", type=float)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--override", action="append", default=[], metavar="PHRASE=START",
                    help="fix a mis-recognized phrase start (raw seconds, before lead); repeatable")
    ap.add_argument("--padded-audio", type=Path, help="write the voice with lead/tail padding (WAV)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    out_pacing = args.out_dir / f"pacing-{args.tag}.json"
    out_srt = args.out_dir / f"subtitles-{args.tag}.srt"
    out_asr = args.out_dir / f"asr-{args.tag}.json"
    targets = [out_pacing, out_srt] + ([args.padded_audio] if args.padded_audio else []) + ([] if args.asr else [out_asr])
    existing = [str(p) for p in targets if p.exists()]
    if existing and not args.overwrite:
        ap.error("refusing to overwrite: " + ", ".join(existing))

    replacements = dict(DEFAULT_REPLACEMENTS)
    if args.replace:
        replacements = {**json.loads(args.replace.read_text(encoding="utf-8")), **replacements}
    tokens = make_tokenizer(replacements)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    if args.asr:
        asr = json.loads(args.asr.read_text(encoding="utf-8"))
    else:
        asr = transcribe(args.audio, args.model, args.language, args.prompt)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out_asr.write_text(json.dumps(asr, ensure_ascii=False, indent=2), encoding="utf-8")

    actual = [(tok, w["start"], w["end"]) for seg in asr["segments"] for w in seg.get("words", []) for tok in tokens(w["word"])]
    phrases, groups, scene_first, expected = [], [], [], []
    for scene in plan:
        scene_first.append(len(phrases))
        for p in scene["phrases"]:
            a = len(expected)
            expected += tokens(p["speech"])
            phrases.append(p)
            groups.append((a, len(expected)))
    mapping = match(expected, actual)

    intervals, weak = [], []
    for i, (a, b) in enumerate(groups):
        ids = [mapping[k] for k in range(a, b) if k in mapping]
        if len(ids) < max(1, (b - a) // 3):
            weak.append(i)
        intervals.append([actual[min(ids)][1], actual[max(ids)][2]] if ids else None)
    for item in args.override:
        idx, value = item.split("=")
        intervals[int(idx)][0] = float(value)
    for i, iv in enumerate(intervals):  # unmatched phrase: borrow neighbours, flag it
        if iv is None:
            prev_end = next((intervals[j][1] for j in range(i - 1, -1, -1) if intervals[j]), 0.0)
            next_start = next((intervals[j][0] for j in range(i + 1, len(intervals)) if intervals[j]), prev_end + 1.0)
            intervals[i] = [prev_end, next_start]

    raw_duration = len(decode(args.audio, 16000)) / 16000
    lead = args.lead
    duration = args.duration or math.ceil((raw_duration + lead + args.tail) * 2) / 2
    if raw_duration + lead > duration:
        ap.error(f"narration ({raw_duration:.2f}s + lead) exceeds --duration {duration}")

    cues, words, label_words = [], [], []
    for i, p in enumerate(phrases):
        start, end = (t + lead for t in intervals[i])
        a, b = groups[i]
        cues.append([round(start, 3), round(end, 3), p["label"]])
        words.append(word_spans(p["speech"].split(), tokens, mapping, actual, a, (start - lead, end - lead, a, b)))
        # Display words come from the label (digits, line breaks) but take timing from speech tokens.
        labels = p["label"].split()
        lab_tokens, spans = [], []
        for label in labels:
            s = len(lab_tokens)
            lab_tokens += tokens(label)
            spans.append((s, len(lab_tokens)))
        spoken = [(tokens(w["text"]), w["start"], w["end"]) for w in words[-1] if w["start"] is not None]
        flat = [(t, s, e) for toks, s, e in spoken for t in toks]
        lab_map = match(lab_tokens, flat)
        items = []
        for label, (s, e) in zip(labels, spans):
            ids = [lab_map[k] for k in range(s, e) if k in lab_map]
            items.append({"text": label, "start": flat[min(ids)][1] if ids else None, "end": flat[max(ids)][2] if ids else None})
        for w in words[-1]:
            if w["start"] is not None:
                w["start"], w["end"] = round(w["start"] + lead, 3), round(w["end"] + lead, 3)
        for w in items:
            if w["start"] is not None:
                w["start"], w["end"] = round(w["start"] + lead, 3), round(w["end"] + lead, 3)
        label_words.append(items)

    bounds = [0.0]
    for first in scene_first[1:]:
        t = round(round((cues[first][0] - args.scene_lead) * args.fps) / args.fps, 4)
        bounds.append(max(t, bounds[-1] + 0.5))
    bounds.append(duration)

    pacing = {
        "duration": duration, "fps": args.fps, "bounds": bounds,
        "scene_names": [s.get("name", f"scene-{i}") for i, s in enumerate(plan)],
        "scene_durations": [round(b - a, 4) for a, b in zip(bounds, bounds[1:])],
        "cues": cues, "words": words, "label_words": label_words,
        "audio": str(args.padded_audio) if args.padded_audio else None,
        "raw_audio": str(args.audio), "raw_audio_duration": raw_duration,
        "alignment_coverage": len(mapping) / max(1, len(expected)), "weak_phrases": weak,
        "start_pad": lead, "scene_lead": args.scene_lead, "tail_pad": duration - raw_duration - lead,
        "overrides": args.override,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_pacing.write_text(json.dumps(pacing, ensure_ascii=False, indent=2), encoding="utf-8")
    out_srt.write_text("\n\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{s}" for i, (a, b, s) in enumerate(cues, 1)) + "\n", encoding="utf-8")

    if args.padded_audio:
        args.padded_audio.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([find_ffmpeg(), "-v", "error", "-y", "-i", str(args.audio), "-af",
                        f"adelay={round(lead * 1000)}:all=1,apad=whole_dur={duration}", "-t", str(duration),
                        "-ar", "48000", "-c:a", "pcm_s16le", str(args.padded_audio)], check=True)

    print(f"duration {duration}s raw {raw_duration:.2f}s coverage {pacing['alignment_coverage']:.3f}")
    print("scene bounds", bounds)
    for i, c in enumerate(cues):
        print(f"{i:2} {c[0]:7.2f} {c[1]:7.2f} {'WEAK ' if i in weak else ''}{c[2].replace(chr(10), ' / ')}")
    if weak:
        print(f"WARNING: weak alignment for phrases {weak}; listen and use --override if needed", file=sys.stderr)


if __name__ == "__main__":
    main()
