"""Silent draft and voiced final for the whiteboard video in this folder.

  R="uv run --offline --no-project --python 3.12 --with pillow --with numpy --with scipy python"
  $R render.py timing              scene table (start, length, ink end) — flags drawings that run past their scene
  $R render.py preview [t ...]     PNG stills (default: last frame of every scene) + safe-area / overlap asserts
  $R render.py draft               exports/draft-<TAG>-NO-VOICE.mp4 (estimated cues, music pad + sticker pops, 30 fps)
  $R render.py plan                audio/plan-<TAG>.json for align_captions.py (one phrase per script sentence)
  $R render.py beds                after the voice is aligned: music bed + pops + mix spec (then run mix_audio.py)
  $R render.py render              exports/<SLUG>-<TAG>.mp4 on real cues + audio/mix-<TAG>.wav, 60 fps

Cues: captions/pacing-<TAG>b.json (from fix_onsets.py) when it exists, otherwise estimated from script.md.
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import scenes as sc  # noqa: E402  (puts the skill's scripts/ on sys.path)

sc.install_stick()  # stickman draws Board.stick; must run before the boards are built

import frame_kit as fk  # noqa: E402
import whiteboard as wb  # noqa: E402

ROOT = Path(__file__).resolve().parent
SLUG = ROOT.name
TAG = os.environ.get("TAG", "v01")  # bump for every new export: fk.render refuses to overwrite
SR = 48000
HOLD, FADE = 0.3, 1.0  # title card fully visible 0.3 s, then fades out (gone at 1.3 s)
WASH = 0.80  # paper wash over the first scene behind the title card
LINES = [("XE BUÝT hay XE MÁY?", 200, wb.INK), ("cộng từng đồng", 120, wb.RED)]
END_HOLD = 4.0  # seconds after the last sentence (use ~11 s on a real video: YouTube end-screen elements need ~20 s)
NEXT_THUMB = None  # e.g. ROOT / "../other-episode/exports/thumbnail.jpg": fades into BOX on the end screen
BOX = (1000, 230, 1780, 670)  # grey frame the last scene draws for YouTube's end-screen video element
T_IN_AFTER = 8.3  # seconds after the last scene starts; only once the pen has left the box (check with preview)

PACING = ROOT / f"captions/pacing-{TAG}b.json"
CHAPTER_IDS = sorted(sc.CHAPTERS)
if PACING.exists():
    p = json.loads(PACING.read_text())
    keys = [(ch, k) for ch in CHAPTER_IDS for k in range(len(sc.CHAPTERS[ch][1]))]
    assert len(keys) == len(p["cues"]), "plan and script.md disagree: rerun `render.py plan` and the alignment"
    cues = {key: c[0] for key, c in zip(keys, p["cues"])}
    END = round(p["cues"][-1][1] + END_HOLD, 2)
    VOICED = True
else:
    cues, end = sc.estimate_cues(CHAPTER_IDS)
    END = end + END_HOLD
    VOICED = False
SCENES = sc.build(cues, END)
BOUNDS = [s[0] for s in SCENES] + [END]
TYPES = {n: s[3] for n, s in enumerate(SCENES)}
T = fk.Typesetter()
T_IN = SCENES[-1][0] + T_IN_AFTER


def title_card():
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fonts = [wb.hand_font(size) for _, size, _ in LINES]
    heights = [d.textbbox((0, 0), s, font=f, anchor="ls")[3] - d.textbbox((0, 0), s, font=f, anchor="ls")[1]
               for (s, _, _), f in zip(LINES, fonts)]
    gap = 40
    y = 540 - (sum(heights) + gap) / 2
    for (s, _size, color), f, h in zip(LINES, fonts, heights):
        box = d.textbbox((960, y + h / 2), s, font=f, anchor="mm")
        assert box[0] >= 96 and box[2] <= 1824, f"title line too wide: {s} {box}"
        if color == wb.INK:
            d.rectangle((box[0] - 30, box[1] + h * 0.35, box[2] + 30, box[3] + 18), fill=(*wb.HIGHLIGHT, 150))
        d.text((960, y + h / 2), s, font=f, fill=color, anchor="mm")
        y += h + gap
    return im


CARD = title_card()
PAPER = wb.paper().convert("RGB")
THUMB = None
if NEXT_THUMB:
    THUMB = Image.open(NEXT_THUMB).convert("RGB").resize((BOX[2] - BOX[0] - 10, BOX[3] - BOX[1] - 6),
                                                         Image.Resampling.LANCZOS)


def scene_picture(i, t):
    s0, s1, b, _kind, _title = SCENES[i]
    return wb.compose(b, t - s0, s1 - s0)


def frame(t):
    i = fk.scene_index(BOUNDS, t)
    wb.audit_into(T, SCENES[i][2])
    im = fk.transition(scene_picture, BOUNDS, TYPES, t).convert("RGB")
    if t < HOLD + FADE:
        k = 1.0 - fk.smooth((t - HOLD) / FADE) if t > HOLD else 1.0
        im = Image.blend(im, PAPER, WASH * k).convert("RGBA")
        card = CARD.copy()
        card.putalpha(card.getchannel("A").point(lambda a: int(a * k)))
        im = Image.alpha_composite(im, card).convert("RGB")
    if THUMB is not None and t >= T_IN:
        k = fk.smooth((t - T_IN) / 0.6)
        region = im.crop((BOX[0] + 5, BOX[1] + 3, BOX[2] - 5, BOX[3] - 3))
        im.paste(Image.blend(region, THUMB, k), (BOX[0] + 5, BOX[1] + 3))
    if t > END - 0.8:  # fade to paper at the very end
        im = Image.blend(im, PAPER, fk.smooth((t - (END - 0.8)) / 0.8))
    return im


# ---------- audio ----------
def read_wav(path):
    with wave.open(str(path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32) / 32768
    return a if a.shape[1] == 2 else np.repeat(a, 2, 1)


def write_wav(path, m):
    assert not path.exists(), f"{path} exists; bump TAG"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(m, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


def stereo(a, n):
    a = a if a.ndim == 2 else np.repeat(a[:, None], 2, 1)
    return np.pad(a, ((0, max(0, n - len(a))), (0, 0)))[:n]


def music_pad(n):
    """Self-synthesised calm pad (no licence needed), looped with a 2 s crossfade if shorter than the video."""
    src = ROOT / "audio/library/pad.wav"
    if not src.exists():
        subprocess.run([sys.executable, str(sc.SKILL / "scripts/make_music_pad.py"), str(src),
                        str(max(60, int(END) + 5))], check=True)
    pad = read_wav(src)
    xf, base = SR * 2, pad.copy()
    fade = np.linspace(0, 1, xf)[:, None]
    while len(pad) < n:
        pad[-xf:] = pad[-xf:] * (1 - fade) + base[:xf] * fade
        pad = np.concatenate([pad, base[xf:]])
    return pad[:n]


def pops(n):
    times = [p for s0, s1, b, *_ in SCENES for p in b.pop_times(s0) if p < s1]
    return stereo(wb.pop_track(times, END, SR), n), len(times)


def draft_mix(out):
    """Music bed at about -24 dB RMS with fade in/out + sticker pops (no pen/scribble sound)."""
    n = int(END * SR)
    pad = music_pad(n)
    pad *= 10 ** (-24 / 20) / (np.sqrt(np.mean(pad ** 2)) + 1e-9)
    ramp = np.minimum(1, np.arange(n) / (SR * 1.5))[:, None]
    tail = np.clip((END - np.arange(n) / SR) / 2.0, 0, 1)[:, None]
    pop, _ = pops(n)
    m = pad * ramp * tail + pop * 10 ** (-4 / 20)
    return write_wav(out, m * min(1.0, 0.89 / np.max(np.abs(m))))


def plan():
    """One plan scene per chapter, one phrase per sentence: the alignment then yields one cue per sentence."""
    out = ROOT / f"audio/plan-{TAG}.json"
    data = [{"name": sc.CHAPTERS[ch][0], "phrases": [{"speech": s, "label": s} for s in sc.CHAPTERS[ch][1]]}
            for ch in CHAPTER_IDS]
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print("wrote", out)


def beds():
    assert VOICED, f"no {PACING.name} yet: generate the voice, align_captions.py, fix_onsets.py first"
    n = int(END * SR)
    pad = music_pad(n)
    write_wav(ROOT / f"audio/bed-pad-{TAG}.wav", pad * 0.25 / (np.max(np.abs(pad)) + 1e-9))
    fx, count = pops(n)
    write_wav(ROOT / f"audio/fx-{TAG}.wav", fx * 0.5 / (np.max(np.abs(fx)) + 1e-9))
    spec = {"duration": END, "voice": f"audio/voiceover-{TAG}.wav",
            "music": {"file": f"audio/bed-pad-{TAG}.wav", "bed_db": -24, "duck_db": -5, "attack_ms": 60,
                      "release_ms": 400, "fade_in": 1.5, "fade_out": 2.0},
            "sfx": {"events": [{"time": 0.0, "sfx": "fx", "relative_voice_db": -21, "label": "pops"}],
                    "assets": {"fx": {"file": f"audio/fx-{TAG}.wav", "fade_ms": 20}}, "max_layers": 1},
            "loudness": {"I": -14, "TP": -2.0, "LRA": 9}}
    p = ROOT / f"audio/mix-spec-{TAG}.json"
    assert not p.exists(), f"{p} exists; bump TAG"
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    print(f"wrote beds ({count} pops) + {p.name}; next: mix_audio.py {p.relative_to(ROOT)} audio/mix-{TAG}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "timing"
    print(f"{'voiced' if VOICED else 'estimated'} cues; length {END:.1f}s = {int(END // 60)}:{END % 60:04.1f}")
    for n, (s0, s1, b, _k, title) in enumerate(SCENES):
        flag = "  <-- drawing runs past scene end" if b.end > s1 - s0 else ""
        print(f"  {n:2d} {int(s0 // 60)}:{s0 % 60:04.1f} len {s1 - s0:5.1f}s ink {b.end:5.1f}s "
              f"{sc.SCENES[n][2].__name__} {title or ''}{flag}")
    if mode == "preview":
        times = [float(a) for a in sys.argv[2:]] or [s1 - 0.3 for s0, s1, *_ in SCENES]
        print(fk.preview(frame, times, T, ROOT / f"visuals/preview-{TAG}"))
    elif mode == "draft":
        out = ROOT / f"exports/draft-{TAG}-NO-VOICE.mp4"
        assert not out.exists(), f"{out} exists; bump TAG"
        fk.render(frame, END, draft_mix(ROOT / f"audio/draft-{TAG}-NO-VOICE-mix.wav"), out, T, fps=30)
    elif mode == "plan":
        plan()
    elif mode == "beds":
        beds()
    elif mode == "render":
        assert VOICED, f"no {PACING.name}: the final export needs aligned cues"
        out = ROOT / f"exports/{SLUG}-{TAG}.mp4"
        assert not out.exists(), f"{out} exists; bump TAG"
        fk.render(frame, END, ROOT / f"audio/mix-{TAG}.wav", out, T, fps=60)
