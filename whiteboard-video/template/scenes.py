"""Whiteboard scenes for the demo "Đi làm bằng xe buýt hay xe máy?" — copy this file for a new video.

Contract: each builder gets `at(k, off)` = board-local seconds when sentence k of its chapter starts (minus the visual
lead LEAD) plus `off`, so ink follows the voice. Sentence numbers come from script.md (`python3 narration.py`).
Host and side characters are stickmen: call `install_stick()` before building boards.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("FRAME_FORMAT", "landscape")
SKILL = Path(os.environ.get("WHITEBOARD_SKILL", "~/.claude/skills/whiteboard-video")).expanduser()
sys.path.insert(0, str(SKILL / "scripts"))
import whiteboard as wb  # noqa: E402
from whiteboard import BLUE, GREEN, GREY, INK, ORANGE, RED, YELLOW  # noqa: E402,F401

from narration import CHAPTERS, PARAGRAPH_ENDS  # noqa: E402

LEAD = 0.6  # visuals start this long before the spoken clause
ACCENT = ORANGE
PINK, MINT, SKY = (255, 205, 205), (190, 230, 190), (205, 220, 255)
PHOTOS = Path(__file__).resolve().parent / "visuals" / "photos"  # transparent PNG cut-outs of real products


def install_stick():
    import stickman
    stickman.install()


# ---------- shared helpers  ----------
def chapter_head(b, at, n, name, k=0, y=60, size=104):
    b.text(960, y, f"Phần {n}", 56, at(k), color=GREY, align="center")
    b.text(960, y + 75, name, size, at(k, 0.4), align="center")


def host(b, x, t, h=380, base=1010, pose="stand", mood="happy", drawn=True, **kw):
    """Stickman narrator; returns the character: .act(t, pose=, mood=), .walk(t, to_x), .jump(t), .head_at(t)."""
    return b.stick(x, base, h, t, pose=pose, mood=mood, accent=ACCENT, drawn=drawn, **kw)


def extra(b, x, t, shirt=(226, 72, 60), h=380, base=1010, pose="hips", mood="happy", flip=False):
    """Side character: same stickman, another shirt colour; flip=True looks left."""
    return b.stick(x, base, h * 0.92, t, pose=pose, mood=mood, accent=ACCENT, look=(-0.3 if flip else 0.3, 0),
                   shirt=shirt)


def walk_in(b, x, t, h=380, base=1010, side=-1, pose="wave", mood="happy"):
    """Stickman walks in from off-screen (side -1 = left) to x, then takes `pose`."""
    s = b.stick(-0.6 * h if side < 0 else 1920 + 0.6 * h, base, h, t, pose="stand", mood=mood, accent=ACCENT,
                drawn=False)
    s.walk(t, x)
    s.act(s.last, pose=pose)
    return s


def paper(b, box, start, color=INK):
    """Receipt outline: straight top and sides, zig-zag tear at the bottom."""
    x0, y0, x1, y1 = box
    n = max(6, int((x1 - x0) / 46))
    zig = [(x0 + (x1 - x0) * i / n, y1 + (14 if i % 2 else -6)) for i in range(n + 1)]
    b.strokes([[(x1, y1 - 6), (x1, y0), (x0, y0), (x0, y1 - 6)] + zig], start, 1.2, width=6, color=color)


def bill(b, rows, at_row, L=300, R=1060, y0=170, step=92, size=60, box=True, total=None):
    """Receipt with rows (label, value, colour); at_row(k) = start time of row k; total = (label, value, colour, t)."""
    if box:
        paper(b, (L - 60, y0 - 50, R + 60, y0 + len(rows) * step + (150 if total else 40)), at_row(0) - 1.2)
    for k, (label, value, col) in enumerate(rows):
        y = y0 + k * step
        t = at_row(k)
        b.text(L, y, label, size, t, color=col if col == RED else INK)
        b.text(R, y, value, size, t + 0.5, color=col, align="right")
    y = y0 + len(rows) * step
    if total:
        label, value, col, t = total
        b.line((L, y + 4), (R, y + 6), t - 0.4, width=5)
        b.text(L, y + 30, label, size + 6, t)
        b.text(R, y + 30, value, size + 10, t + 0.4, color=col, align="right")
    return y


def hbar(b, box, start, fill, color=INK, width=6, alpha=120):
    """Bar drawn as a highlighter fill plus an ink outline (looks hand-coloured)."""
    b.highlight(box, start, color=fill, alpha=alpha)
    b.rect(box, start + 0.3, color=color, width=width)


def dot(b, x, y, start, color=RED, r=12):
    return b.fill([wb._ellipse(x, y, r, r, 14)], start, color, 0.15, alpha=255)


def note(b, s, t, x=110, y=945, align="left"):
    """Small grey source/assumption line at the bottom ("giả định", "ví dụ")."""
    b.text(x, y, s, 40, t, color=GREY, align=align)


def bus(b, cx, cy, w, start, color=BLUE):
    """Custom drawing when Tabler has no icon: body, windows, wheels as strokes (pen follows them)."""
    h = w * 0.5
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    b.strokes([[(x0, y1), (x0, y0 + 20), (x0 + 20, y0), (x1 - 20, y0), (x1, y0 + 20), (x1, y1), (x0, y1)]],
              start, 0.9, width=7, color=color)
    n = 4
    ws = [[(x0 + 20 + i * (w - 40) / n + 8, y0 + 22), (x0 + 20 + (i + 1) * (w - 40) / n - 8, y0 + 22),
           (x0 + 20 + (i + 1) * (w - 40) / n - 8, cy), (x0 + 20 + i * (w - 40) / n + 8, cy),
           (x0 + 20 + i * (w - 40) / n + 8, y0 + 22)] for i in range(n)]
    b.strokes(ws, start + 0.8, 0.8, width=5, color=color)
    r = h * 0.17
    b.strokes([wb._ellipse(x0 + w * 0.22, y1, r, r, 24), wb._ellipse(x1 - w * 0.22, y1, r, r, 24)],
              start + 1.5, 0.5, width=7, color=INK)


class Photo(wb.Sticker):
    """Cut-out product photo (transparent PNG) that pops in like a sticker, white die-cut edge, no bob."""

    def __init__(self, path, cx, cy, w, h, start, rot):
        super().__init__("photo:" + Path(path).stem, cx, cy, w, start, None, None, None, rot, 0.4, None, 0)
        im = wb.Image.open(path).convert("RGBA")
        k = min(w / im.width, h / im.height)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), wb.Image.Resampling.LANCZOS)
        self.sprite = sp = wb._die_cut(im, 7, rot)
        m = 0.08 * min(sp.width, sp.height)
        self.box = (cx - sp.width / 2 + m, cy - sp.height / 2 + m, cx + sp.width / 2 - m, cy + sp.height / 2 - m)

    def paste(self, im, t):
        if t < self.start:
            return
        u = (t - self.start) / self.pop
        sc = wb._back_out(min(1.0, u)) if u < 1 else 1.0
        if sc <= 0.02:
            return
        sp = self.sprite
        if abs(sc - 1) > 1e-3:
            sp = sp.resize((max(1, int(sp.width * sc)), max(1, int(sp.height * sc))), wb.Image.Resampling.BILINEAR)
        if u < 0.35:
            sp = sp.copy()
            sp.putalpha(sp.getchannel("A").point(lambda v: int(v * u / 0.35)))
        wb._paste(im, sp, self.cx - sp.width / 2, self.cy - sp.height / 2)


def photo(b, name, cx, cy, w, start, h=None, rot=0):
    """Real product photo visuals/photos/<name>.png centred on (cx, cy), fitted into w x h; pops in at `start`."""
    st = Photo(PHOTOS / f"{name}.png", cx, cy, w, h or round(w * 0.72), start, rot)
    b.live.append(st)
    return st


# ---------- 0 · Mở đầu ----------
def s0_vs(b, at):
    b.icon("motorbike", 480, 380, 300, at(0, 0.2), color=RED)
    b.text(480, 580, "xe máy", 90, at(0, 0.9), align="center")
    bus(b, 1440, 380, 380, at(0, 1.4))
    b.text(1440, 580, "xe buýt", 90, at(0, 2.4), color=BLUE, align="center")
    b.sticker("text:VS", 960, 380, at(0, 3.0), color=ORANGE, font=90, rot=-8)
    s = host(b, 960, at(1, 0.0), h=330, pose="shrug", mood="think")
    b.speech(1330, 720, "Xe máy rẻ hơn chứ?", at(1, 0.8), tail=(1060, 790), size=56, think=True)


def s0_count(b, at):
    b.text(960, 120, "Cộng từng đồng", 150, at(2, 0.0), align="center")
    b.underline(560, 1360, 300, at(2, 1.4), color=RED, width=8)
    b.icon("calculator", 640, 620, 240, at(2, 1.8), color=BLUE)
    s = host(b, 1220, at(2, 1.2), h=420, pose="hold_up", mood="determined")
    s.act(at(2, 3.0), pose="point_l", mood="happy")


# ---------- 1 · Hai hoá đơn ----------
def s1_bills(b, at):
    chapter_head(b, at, 1, "Hai hoá đơn", y=30, size=88)
    rows = [("xăng 20 km", "15.000 đ", INK), ("gửi xe", "5.000 đ", INK)]
    bill(b, rows, lambda k: at(0, 1.0) if k == 0 else at(1, 0.0), L=200, R=820, y0=330,
         total=("1 ngày", "20.000 đ", RED, at(1, 2.2)))
    b.icon("motorbike", 1350, 330, 200, at(0, 0.4), color=RED)
    b.sticker("face:shock", 1600, 560, at(1, 3.0), size=140)
    note(b, "số liệu ví dụ", at(0, 2.0))


def s1_compare(b, at):
    b.text(960, 40, "Mỗi ngày đi làm", 96, at(2, -0.3), align="center")
    base = 880
    hbar(b, (420, base - 20 * 26, 760, base), at(2, 0.4), PINK)
    b.text(590, base - 20 * 26 - 100, "20.000 đ", 80, at(2, 0.9), align="center")
    b.text(590, base + 20, "xe máy", 56, at(2, 0.6), color=GREY, align="center")
    hbar(b, (1160, base - 9 * 26, 1500, base), at(3, 0.6), SKY)
    b.text(1330, base - 9 * 26 - 100, "≈ 9.000 đ", 80, at(3, 1.2), color=BLUE, align="center")
    b.text(1330, base + 20, "vé tháng ÷ 22", 56, at(3, 0.8), color=GREY, align="center")
    b.sticker("text:RẺ HƠN", 1330, 380, at(3, 3.0), color=GREEN, shape="pill", font=64, rot=-5)


# ---------- 2 · Kết ----------
def s2_end(b, at):
    b.text(960, 80, "xe buýt ≈ ½", 160, at(0, 0.0), color=BLUE, align="center")
    b.circle((560, 50, 1360, 300), at(0, 1.2), color=RED, width=7)
    s = walk_in(b, 520, at(1, 0.0), h=400, pose="present_r", mood="happy")
    b.icon("hourglass", 1100, 600, 180, at(1, 1.0), color=ORANGE)
    b.text(1220, 560, "= tiền", 96, at(1, 1.6), color=ORANGE)
    s.act(at(2, 0.0), pose="wave", mood="laugh")
    b.sticker("heart", 1500, 860, at(3, 0.4), size=130, color=RED)


# (chapter, first sentence, builder, transition into this scene, optional chapter title)
SCENES = [
    (0, 0, s0_vs, "match", "Mở đầu"),
    (0, 2, s0_count, "slide", None),
    (1, 0, s1_bills, "zoom", "Hai hoá đơn"),
    (1, 2, s1_compare, "slide", None),
    (2, 0, s2_end, "zoom", "Kết"),
]

PAUSE = {}  # extra silence before a sentence, {(chapter, k): seconds}, e.g. a beat before the punchline


# ---------- timing ----------
def estimate_cues(chapters, cps=16.5, gap=0.25, para=0.55, chapter_gap=0.9, start=0.8):
    """Provisional sentence start times {(chapter, k): seconds} for silent drafts (no voice yet)."""
    cues, t = {}, start
    for ch in chapters:
        for k, s in enumerate(CHAPTERS[ch][1]):
            t += PAUSE.get((ch, k), 0.0)
            cues[(ch, k)] = t
            t += len(s) / cps + gap + (para if k in PARAGRAPH_ENDS.get(ch, ()) else 0)
        t += chapter_gap
    return cues, t


def build(cues, end_time, scenes=SCENES):
    """Return [(start, end, board, transition, chapter_title)] with boards filled from cue times."""
    starts = [max(0.0, cues[(ch, k)] - LEAD) if n else 0.0 for n, (ch, k, *_rest) in enumerate(scenes)]
    out = []
    for n, (ch, k, fn, kind, title) in enumerate(scenes):
        s0 = starts[n]
        s1 = starts[n + 1] if n + 1 < len(scenes) else end_time
        b = wb.Board(seed=100 + n)

        def at(j, off=0.0, ch=ch, s0=s0):
            return cues[(ch, j)] - LEAD - s0 + off

        fn(b, at)
        out.append((s0, s1, b, kind, title))
    return out
