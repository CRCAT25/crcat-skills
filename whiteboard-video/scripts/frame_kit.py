#!/usr/bin/env python3
"""Reusable Pillow frame-renderer kit for YouTube edits: 1920x1080 long-form (default) and 1080x1920 Shorts.
Forked from the TikTok kit (iPhone 18 vs 17 V22 pipeline). Pick the canvas BEFORE importing:

    FRAME_FORMAT=landscape  (default) 1920x1080, YouTube long-form
    FRAME_FORMAT=vertical             1080x1920, YouTube Shorts (same safe areas as the TikTok kit)

Import it from a project-specific render script that defines `scene_picture(i, t) -> RGBA Image`:

    import sys; sys.path.insert(0, str(Path("~/.claude/skills/whiteboard-video/scripts").expanduser()))
    import frame_kit as fk
    P = fk.load_pacing("captions/pacing-v01.json")
    T = fk.Typesetter()
    def scene_picture(i, t): ...  # draw with T.glyph / T.mid / fk.rect
    def frame(t):
        i = fk.scene_index(P["bounds"], t)
        im = fk.transition(scene_picture, P["bounds"], {2: "slide", 3: "zoom"}, t)
        fk.flash_border(im, flashes, t)
        return fk.karaoke(im, T, P, t).convert("RGB")
    fk.render(frame, P["duration"], "audio/mix-v01.wav", "exports/final-v01.mp4", T, fps=30)

Run with: uv run --offline --no-project --with pillow python render_v01.py
Self-test: uv run --offline --no-project --with pillow python frame_kit.py --demo OUT_DIR

Safe-area numbers are conservative starting points (see references/editorial-quality.md), not platform specs.
landscape: text inside x 96..1824 (5 % title-safe), bottom <= 1000, caption box bottom <= 980 (clear of the
           player's progress bar), min font 40 px; the last 5-20 s also keep the end-screen zone free.
vertical:  text inside x 0..1080, bottom <= 1632, caption box bottom <= 1536, right rail clear, min font 44 px.
Both: >= 24 px padding inside boxes.
"""
import json
import math
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_path import find_ffmpeg  # noqa: E402

FORMAT = os.environ.get("FRAME_FORMAT", "landscape")
assert FORMAT in ("landscape", "vertical"), f"FRAME_FORMAT must be landscape or vertical, not {FORMAT!r}"
if FORMAT == "landscape":
    W, H = 1920, 1080
    SAFE_LEFT, SAFE_RIGHT, SAFE_BOTTOM = 96, 1824, 1000
    CAPTION_MAX_BOTTOM = 980
    MIN_FONT = 40
    # karaoke defaults: a single-row-or-two band centred low in frame, like broadcast subtitles
    CAPTION = dict(top=850, size=46, wrap=1400, max_rows=2, left=240, right=1680)
    FOCUS = (960, 470)  # zoom anchor: upper-middle, where the subject is framed
else:
    W, H = 1080, 1920
    SAFE_LEFT, SAFE_RIGHT, SAFE_BOTTOM = 0, 1080, 1632
    CAPTION_MAX_BOTTOM = 1536
    MIN_FONT = 44
    CAPTION = dict(top=1268, size=48, wrap=788, max_rows=3, left=48, right=888)
    FOCUS = (540, 760)
MIN_PAD = 24
WHITE = (247, 248, 245)
LIME = (217, 238, 160)
BLUE = (155, 192, 243)
MUTED = (164, 179, 197)
PANEL = (18, 28, 42)
CAPTION_FILL = (6, 12, 20)
FONT_FILE = "/System/Library/Fonts/Avenir Next.ttc"  # index 0 bold, 5 regular; has Vietnamese glyphs
TRANSITION = 0.30


# ---------- easing ----------
def clamp(x):
    return max(0.0, min(1.0, x))


def ease(x):
    """Cosine ease in-out."""
    return (1 - math.cos(math.pi * clamp(x))) / 2


def smooth(x):
    """Smootherstep."""
    x = clamp(x)
    return x * x * x * (x * (x * 6 - 15) + 10)


def overshoot(x):
    x = clamp(x) - 1
    return 1 + 2.70158 * x ** 3 + 1.70158 * x ** 2


# ---------- typography with audit ----------
@lru_cache(None)
def font(size=48, bold=True):
    return ImageFont.truetype(FONT_FILE, size, index=0 if bold else 5)


def rect(d, box, outline=None, fill=PANEL, radius=28):
    d.rounded_rectangle(box, radius, fill=fill, outline=outline, width=2)


class Typesetter:
    """Draws text and records every glyph box so each frame can be audited for safe areas."""

    def __init__(self):
        self.audit, self.box_audit = [], []

    def clear(self):
        self.audit.clear()
        self.box_audit.clear()

    def fit_size(self, s, size, maxw=None, bold=True):
        maxw = maxw or (SAFE_RIGHT - SAFE_LEFT)
        while font(size, bold).getlength(s) > maxw and size > MIN_FONT:
            size -= 1
        assert font(size, bold).getlength(s) <= maxw, f"text too wide even at {MIN_FONT}px: {s!r}"
        return size

    def glyph(self, d, x, y, s, size=48, c=WHITE, bold=True, align="left", box=None, pad=MIN_PAD):
        assert size >= MIN_FONT, (s, size)
        f = font(size, bold)
        a, b, cc, dd = f.getbbox(s)
        width, height = cc - a, dd - b
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        d.text((round(x - a), round(y - b)), s, font=f, fill=c)
        bb = (x, y, x + width, y + height)
        self.audit.append((s, size, bb))
        if box:
            inset = min(bb[0] - box[0], bb[1] - box[1], box[2] - bb[2], box[3] - bb[3])
            self.box_audit.append((s, inset))
            assert inset >= pad - 0.5, (s, bb, box, inset, pad)
        return bb

    def mid(self, d, box, s, size=48, c=WHITE, pad=MIN_PAD, bold=True):
        """Center one line inside box, shrinking (not below MIN_FONT) to keep the padding."""
        size = self.fit_size(s, size, box[2] - box[0] - 2 * pad, bold)
        while size > MIN_FONT and font(size, bold).getbbox(s)[3] - font(size, bold).getbbox(s)[1] > box[3] - box[1] - 2 * pad:
            size -= 1
        bb = font(size, bold).getbbox(s)
        return self.glyph(d, (box[0] + box[2]) / 2, (box[1] + box[3] - (bb[3] - bb[1])) / 2, s, size, c, bold, "center", box, pad)

    def overflow(self, safe_bottom=SAFE_BOTTOM):
        return [(s, size, bb) for s, size, bb in self.audit
                if bb[0] < SAFE_LEFT - 0.5 or bb[2] > SAFE_RIGHT + 0.5 or bb[3] > safe_bottom]


# ---------- pacing helpers ----------
def load_pacing(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scene_index(bounds, t):
    for j in range(len(bounds) - 1):
        if bounds[j] <= t < bounds[j + 1]:
            return j
    return len(bounds) - 2


# ---------- karaoke subtitles ----------
def karaoke(im, T, pacing, t, top=None, size=None, wrap=None, max_rows=None, left=None, right=None,
            hold=0.06, active=LIME, idle=WHITE, pad=26):
    """Dark rounded box, current word highlighted. Uses pacing['label_words'] from align_captions.py.
    Geometry defaults come from CAPTION for the active FRAME_FORMAT. Long-form note: YouTube viewers can also
    turn on the uploaded SRT, so burned-in karaoke is optional there (see references/editorial-quality.md)."""
    top = CAPTION["top"] if top is None else top
    size = size or CAPTION["size"]
    wrap = wrap or CAPTION["wrap"]
    max_rows = max_rows or CAPTION["max_rows"]
    left = CAPTION["left"] if left is None else left
    right = right or CAPTION["right"]
    d = ImageDraw.Draw(im)
    f = font(size)
    space = f.getlength(" ")
    top = top(t) if callable(top) else top
    for idx, (a, b, _label) in enumerate(pacing["cues"]):
        if not (a <= t <= b + hold):
            continue
        rows, row, width = [], [], 0
        for w in pacing["label_words"][idx]:
            ww = f.getlength(w["text"])
            add = ww + (space if row else 0)
            if row and width + add > wrap:
                rows.append(row)
                row, width = [], 0
                add = ww
            row.append((w, ww))
            width += add
        if row:
            rows.append(row)
        assert len(rows) <= max_rows, (idx, len(rows))
        heights = [max(f.getbbox(w["text"])[3] for w, _ in r) - min(f.getbbox(w["text"])[1] for w, _ in r) for r in rows]
        box = (left, top, right, top + 56 + sum(heights) + 22 * (len(rows) - 1))
        assert box[3] <= CAPTION_MAX_BOTTOM, ("caption box too low", box)
        rect(d, box, fill=CAPTION_FILL)
        y = top + 28
        for r, height in zip(rows, heights):
            x = (left + right - (sum(ww for _, ww in r) + space * (len(r) - 1))) / 2
            top_ref = min(f.getbbox(w["text"])[1] for w, _ in r)
            for w, ww in r:
                lit = w["start"] is not None and w["start"] <= t < w["end"]
                T.glyph(d, x, y + f.getbbox(w["text"])[1] - top_ref, w["text"], size, active if lit else idle, box=box, pad=pad)
                x += ww + space
            y += height + 22
        break
    return im


# ---------- transitions ----------
def zoom_image(im, scale, anchor=FOCUS):
    inv = 1 / scale
    ax, ay = anchor
    return im.transform((W, H), Image.Transform.AFFINE, (inv, 0, ax * (1 - inv), 0, inv, ay * (1 - inv)), Image.Resampling.BICUBIC)


def horizontal_blur(im, amount, taps=7):
    """Motion blur along x; edge pixels are stretched so no empty strips appear."""
    if amount < 0.5:
        return im
    result = None
    for k in range(taps):
        shift = round((k / (taps - 1) - 0.5) * 2 * amount)
        sample = im.transform(im.size, Image.Transform.AFFINE, (1, 0, shift, 0, 1, 0), Image.Resampling.BILINEAR)
        if shift > 0:
            sample.paste(sample.crop((W - shift - 1, 0, W - shift, H)).resize((shift, H)), (W - shift, 0))
        elif shift < 0:
            sample.paste(sample.crop((-shift, 0, -shift + 1, H)).resize((-shift, H)), (0, 0))
        result = sample if result is None else Image.blend(result, sample, 1 / (k + 1))
    return result


def slide(old, new, u, blur=22):
    """Push left with motion blur peaking mid-move."""
    offset = round(W * ease(u))
    im = Image.new("RGBA", (W, H))
    im.alpha_composite(old, (-offset, 0))
    im.alpha_composite(new, (W - offset, 0))
    return horizontal_blur(im, blur * math.sin(math.pi * clamp(u)))


def zoom_through(old, new, u, amount=0.12, anchor=FOCUS):
    """Old zooms in for the first half, new settles out from the same scale. No dissolve."""
    if u < 0.5:
        return zoom_image(old, 1 + amount * ease(u / 0.5), anchor)
    return zoom_image(new, 1 + amount * (1 - ease((u - 0.5) / 0.5)), anchor)


def transition(scene_picture, bounds, types, t, length=TRANSITION):
    """Compose frame t. types maps scene index -> 'slide' | 'zoom' | 'match' (hard cut)."""
    i = scene_index(bounds, t)
    local = t - bounds[i]
    kind = types.get(i, "match")
    if i and local < length and kind in ("slide", "zoom"):
        old = scene_picture(i - 1, bounds[i] - 0.001)
        new = scene_picture(i, t)
        return (slide if kind == "slide" else zoom_through)(old, new, local / length)
    return scene_picture(i, t)


def flash_border(im, flashes, t, fps=60, frames=2, width=7):
    """Two-frame outline accent on a card; never flashes the whole screen or covers text."""
    for fl in flashes:
        if fl["time"] - 1e-7 <= t < fl["time"] + frames / fps - 1e-7:
            ImageDraw.Draw(im).rounded_rectangle(fl["box"], 28, outline=WHITE if fl.get("color", "white") == "white" else LIME, width=width)
    return im


# ---------- output ----------
def contact_sheet(paths, out, cols=5, tile=None, labels=None):
    tile = tile or ((384, 216) if W > H else (260, 462))
    paths = list(paths)
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * (tile[0] + 10), rows * (tile[1] + 38)), (10, 15, 22))
    d = ImageDraw.Draw(sheet)
    for n, p in enumerate(paths):
        im = Image.open(p)
        im.thumbnail(tile)
        x, y = n % cols * (tile[0] + 10), n // cols * (tile[1] + 38)
        sheet.paste(im, (x, y + 30))
        d.text((x + 4, y + 4), labels[n] if labels else Path(p).stem, fill="white", font=font(MIN_FONT // 2))
    sheet.save(out, quality=92)
    return out


def preview(frame, times, T, folder):
    """Render still frames at given times, audit them, and write overview.jpg."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for n, t in enumerate(times):
        T.clear()
        im = frame(t)
        bad = T.overflow()
        assert not bad, (t, bad)
        paths.append(folder / f"preview-{n:02}-{t:06.2f}s.jpg")
        im.save(paths[-1], quality=92)
    return contact_sheet(paths, folder / "overview.jpg", labels=[f"{t:.2f}s" for t in times])


def render(frame, duration, audio, out, T, fps=30, log=None, crf=18, overwrite=False):
    """Pipe RGB frames into FFmpeg (H.264 yuv420p + AAC 256k, faststart); write geometry-*.json next to out."""
    out = Path(out)
    if out.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {out}; use a new version suffix")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [find_ffmpeg(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "256k"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-t", str(duration), "-movflags", "+faststart", str(out)]
    log_file = open(log or out.with_suffix(".render.log"), "w")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log_file)
    geometry = {"min_box_inset": None, "minimum_font": None, "overflow": [], "frames": 0}
    try:
        total = round(duration * fps)
        for n in range(total):
            T.clear()
            im = frame(n / fps)
            assert im.size == (W, H) and im.mode == "RGB", (im.size, im.mode)
            for s, size, bb in T.audit:
                geometry["minimum_font"] = size if geometry["minimum_font"] is None else min(size, geometry["minimum_font"])
            geometry["overflow"] += [(n / fps, s, bb) for s, _, bb in T.overflow()]
            if T.box_audit:
                low = min(x[1] for x in T.box_audit)
                geometry["min_box_inset"] = low if geometry["min_box_inset"] is None else min(low, geometry["min_box_inset"])
            proc.stdin.write(im.tobytes())
            if n % (fps * 10) == 0:
                print(f"render {n / fps:.0f}/{duration}s", flush=True)
        geometry["frames"] = total
        proc.stdin.close()
        assert proc.wait() == 0, f"ffmpeg failed, see {log_file.name}"
    finally:
        log_file.close()
    out.with_name(f"geometry-{out.stem}.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2))
    assert not geometry["overflow"], geometry["overflow"][:10]
    return geometry


def _demo(folder):
    """Two synthetic scenes, slide + zoom transitions, karaoke captions, 3 s render (in the active FRAME_FORMAT)."""
    folder = Path(folder)
    pacing = {
        "duration": 3.0, "bounds": [0, 1.0, 2.0, 3.0],
        "cues": [[0.2, 2.8, "Bộ công cụ dựng khung hình hoạt động"]],
        "label_words": [[{"text": w, "start": 0.2 + 0.4 * k, "end": 0.6 + 0.4 * k} for k, w in enumerate("Bộ công cụ dựng khung hình hoạt động".split())]],
    }
    T = Typesetter()
    colors = [(30, 60, 90), (70, 40, 90), (30, 80, 60)]

    def scene_picture(i, t):
        im = Image.new("RGBA", (W, H), colors[i] + (255,))
        d = ImageDraw.Draw(im)
        card = (W // 2 - 476, 300, W // 2 + 476, 500)
        rect(d, card)
        T.mid(d, card, f"Cảnh {i + 1} · {t:.2f}s", 72)
        return im

    def frame(t):
        im = transition(scene_picture, pacing["bounds"], {1: "slide", 2: "zoom"}, t)
        flash_border(im, [{"time": 2.0, "box": (W // 2 - 476, 300, W // 2 + 476, 500)}], t)
        return karaoke(im, T, pacing, t).convert("RGB")

    print(preview(frame, [0.5, 1.1, 1.15, 2.05, 2.5], T, folder))
    geometry = render(frame, pacing["duration"], None, folder / "demo.mp4", T, fps=30, overwrite=True)
    print(json.dumps({k: v for k, v in geometry.items() if k != "overflow"}))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--demo":
        _demo(sys.argv[2])
    else:
        print(__doc__)
