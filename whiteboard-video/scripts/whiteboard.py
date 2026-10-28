#!/usr/bin/env python3
"""Whiteboard ("vẽ tay bằng bút") scenes on top of frame_kit: paper, strokes that draw themselves, handwritten
text written letter by letter, a marker pen that follows the stroke tip, and a slow camera drift.
People (b.person: chibi characters with moods/poses), speech/thought bubbles (b.speech) and colour
die-cut stickers that pop in (b.sticker; sound: pop_track(b.pop_times(off), D)) make scenes livelier.

    import sys; sys.path.insert(0, str(Path("~/.claude/skills/whiteboard-video/scripts").expanduser()))
    import frame_kit as fk, whiteboard as wb
    b = wb.Board(seed=1)
    b.text(960, 300, "10 TRIỆU", size=150, start=0.3, align="center")
    b.icon("home", 500, 600, 260, start=1.2)
    b.arrow((700, 600), (1100, 600), start=2.0, color=wb.RED)
    im = wb.compose(b, t)            # RGBA 1920x1080 (paper + ink + pen), camera drift included

Every element takes `start` (seconds, board-local) and an optional `dur`; default durations come from stroke
length (PEN_SPEED px/s) or character count (WRITE_CPS). `b.end` is when the last element finishes.
Text boxes are recorded in `b.audit` (same tuple shape as frame_kit.Typesetter.audit) so the frame_kit safe-area
audit also covers handwriting: pass `wb.audit_into(T, board)` from the project's frame() function.

Icons: Tabler outline SVGs (MIT) in assets/icons/tabler; font: Patrick Hand (OFL, has Vietnamese) in assets/fonts.
Run with: uv run --offline --no-project --with pillow python …   Self-test: … whiteboard.py --demo OUT_DIR
"""
import math
import random
import re
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frame_kit as fk  # noqa: E402

W, H = fk.W, fk.H
ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICON_DIR = ASSETS / "icons" / "tabler"
HAND_FONT = ASSETS / "fonts" / "PatrickHand-Regular.ttf"

PAPER = (250, 248, 242)
INK = (32, 36, 46)
RED = (208, 58, 47)
BLUE = (38, 102, 196)
GREEN = (36, 132, 78)
ORANGE = (226, 128, 32)
GREY = (128, 132, 140)
HIGHLIGHT = (255, 214, 64)

PEN_SPEED = 1500.0   # px/s along a stroke
WRITE_CPS = 16.0     # characters/s for handwriting
SS = 2               # supersampling factor for antialiased strokes


# ---------- paper ----------
@lru_cache(None)
def paper():
    im = Image.new("RGB", (W, H), PAPER)
    noise = Image.effect_noise((W // 4, H // 4), 18).resize((W, H), Image.Resampling.BICUBIC)
    im = Image.blend(im, Image.merge("RGB", [noise] * 3), 0.035)
    # soft vignette
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGB", (W, H), (226, 222, 212))
    im = Image.composite(im, dark, vig)
    return im.convert("RGBA")


# ---------- svg path -> polylines ----------
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


def _arc(p0, rx, ry, phi, large, sweep, p1, n=None):
    x1, y1 = p0
    x2, y2 = p1
    if rx == 0 or ry == 0:
        return [p1]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0, num / den)) if den else 0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = n or max(4, int(abs(dt) / (math.pi / 16)))
    out = []
    for k in range(1, n + 1):
        a = t1 + dt * k / n
        out.append((cx + rx * math.cos(a) * cp - ry * math.sin(a) * sp, cy + rx * math.cos(a) * sp + ry * math.sin(a) * cp))
    return out


def _bez(pts, n=12):
    out = []
    for k in range(1, n + 1):
        u = k / n
        if len(pts) == 3:
            a, b, c = pts
            out.append(((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * b[0] + u * u * c[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * b[1] + u * u * c[1]))
        else:
            a, b, c, d = pts
            out.append(((1 - u) ** 3 * a[0] + 3 * (1 - u) ** 2 * u * b[0] + 3 * (1 - u) * u * u * c[0] + u ** 3 * d[0],
                        (1 - u) ** 3 * a[1] + 3 * (1 - u) ** 2 * u * b[1] + 3 * (1 - u) * u * u * c[1] + u ** 3 * d[1]))
    return out


def parse_path(d):
    toks = _TOKEN.findall(d)
    i, cmd = 0, None
    cur = start = (0.0, 0.0)
    last_ctrl = None
    polys, poly = [], []

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if poly:
                    poly.append(start)
                    polys.append(poly)
                poly, cur, last_ctrl = [], start, None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0, 0)
        if c == "M":
            if len(poly) > 1:
                polys.append(poly)
            cur = (num() + ox, num() + oy)
            start, poly = cur, [cur]
            cmd = "l" if rel else "L"
            last_ctrl = None
        elif c == "L":
            cur = (num() + ox, num() + oy)
            poly.append(cur)
            last_ctrl = None
        elif c == "H":
            cur = (num() + ox, cur[1])
            poly.append(cur)
            last_ctrl = None
        elif c == "V":
            cur = (cur[0], num() + oy)
            poly.append(cur)
            last_ctrl = None
        elif c == "C":
            p1 = (num() + ox, num() + oy)
            p2 = (num() + ox, num() + oy)
            p3 = (num() + ox, num() + oy)
            poly += _bez([cur, p1, p2, p3])
            cur, last_ctrl = p3, p2
        elif c == "S":
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p2 = (num() + ox, num() + oy)
            p3 = (num() + ox, num() + oy)
            poly += _bez([cur, p1, p2, p3])
            cur, last_ctrl = p3, p2
        elif c == "Q":
            p1 = (num() + ox, num() + oy)
            p2 = (num() + ox, num() + oy)
            poly += _bez([cur, p1, p2])
            cur, last_ctrl = p2, p1
        elif c == "T":
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p2 = (num() + ox, num() + oy)
            poly += _bez([cur, p1, p2])
            cur, last_ctrl = p2, p1
        elif c == "A":
            rx, ry, phi, large, sweep = num(), num(), num(), num(), num()
            p1 = (num() + ox, num() + oy)
            poly += _arc(cur, rx, ry, phi, int(large), int(sweep), p1)
            cur, last_ctrl = p1, None
    if len(poly) > 1:
        polys.append(poly)
    return polys


@lru_cache(None)
def icon_polys(name):
    """Polylines of a Tabler outline icon in its 24x24 box (the invisible bounding path is skipped)."""
    svg = (ICON_DIR / f"{name}.svg").read_text()
    polys = []
    for el in re.finditer(r"<(path|circle|line|rect|polyline|ellipse)\b([^>]*)/?>", svg):
        kind, attrs = el.group(1), dict(re.findall(r'([\w-]+)="([^"]*)"', el.group(2)))
        if attrs.get("stroke") == "none":
            continue
        if kind == "path":
            polys += parse_path(attrs["d"])
        elif kind in ("circle", "ellipse"):
            cx, cy = float(attrs["cx"]), float(attrs["cy"])
            rx = float(attrs.get("r", attrs.get("rx", 0)))
            ry = float(attrs.get("r", attrs.get("ry", 0)))
            polys.append([(cx + rx * math.cos(a / 32 * 2 * math.pi - math.pi / 2), cy + ry * math.sin(a / 32 * 2 * math.pi - math.pi / 2)) for a in range(33)])
        elif kind == "line":
            polys.append([(float(attrs["x1"]), float(attrs["y1"])), (float(attrs["x2"]), float(attrs["y2"]))])
        elif kind == "rect":
            x, y, w, h = (float(attrs[k]) for k in ("x", "y", "width", "height"))
            polys.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)])
        elif kind == "polyline":
            v = [float(n) for n in re.findall(r"-?\d*\.?\d+", attrs["points"])]
            polys.append(list(zip(v[::2], v[1::2])))
    return polys


# ---------- geometry helpers ----------
def _resample(poly, step=5.0):
    out = [poly[0]]
    for a, b in zip(poly, poly[1:]):
        seg = math.dist(a, b)
        n = max(1, int(seg / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def _wobble(poly, rnd, amp=1.4, freq=0.012):
    """Low-frequency hand tremor perpendicular-ish offset; deterministic per element."""
    ph1, ph2, ph3 = (rnd.uniform(0, 6.28) for _ in range(3))
    out, s = [], 0.0
    for k, p in enumerate(poly):
        if k:
            s += math.dist(p, poly[k - 1])
        out.append((p[0] + amp * math.sin(s * freq + ph1) + 0.5 * amp * math.sin(s * freq * 2.3 + ph3),
                    p[1] + amp * math.sin(s * freq * 1.3 + ph2)))
    return out


def _length(poly):
    return sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))


def _partial(polys, frac):
    """Cut a list of polylines at `frac` of their total length; returns (visible polylines, tip point)."""
    total = sum(_length(p) for p in polys) or 1
    left = total * max(0.0, min(1.0, frac))
    out, tip = [], polys[0][0]
    for p in polys:
        if left <= 0:
            break
        L = _length(p)
        if L <= left:
            out.append(p)
            left -= L
            tip = p[-1]
            continue
        acc, q = 0.0, [p[0]]
        for a, b in zip(p, p[1:]):
            seg = math.dist(a, b)
            if acc + seg >= left:
                u = (left - acc) / seg if seg else 0
                tip = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
                q.append(tip)
                break
            q.append(b)
            acc += seg
        out.append(q)
        left = 0
    return out, tip


def _bbox(polys, pad):
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    return (int(min(xs) - pad), int(min(ys) - pad), int(math.ceil(max(xs) + pad)), int(math.ceil(max(ys) + pad)))


@lru_cache(None)
def hand_font(size):
    return ImageFont.truetype(str(HAND_FONT), size)


# ---------- elements ----------
class Element:
    start = 0.0
    dur = 0.5
    bbox = (0, 0, 1, 1)

    @property
    def end(self):
        return self.start + self.dur

    def progress(self, t):
        return max(0.0, min(1.0, (t - self.start) / self.dur)) if self.dur > 0 else float(t >= self.start)

    def draw(self, img, p, ox, oy):  # draw at SS scale into a bbox-local RGBA canvas
        raise NotImplementedError

    def tip(self, p):
        raise NotImplementedError

    def first_point(self):
        return self.tip(0.0)


class Strokes(Element):
    def __init__(self, polys, start, dur, width, color, rnd, wobble=1.4, alpha=255):
        self.polys = [_wobble(_resample(p), rnd, wobble) for p in polys if len(p) > 1]
        self.start, self.width, self.color, self.alpha = start, width, color, alpha
        self.dur = dur if dur is not None else max(0.25, min(2.4, sum(_length(p) for p in self.polys) / PEN_SPEED))
        self.bbox = _bbox(self.polys, width)

    def draw(self, img, p, ox, oy):
        d = ImageDraw.Draw(img)
        vis, _ = _partial(self.polys, p)
        w = self.width * SS
        col = self.color + (self.alpha,)
        for poly in vis:
            pts = [((x - ox) * SS, (y - oy) * SS) for x, y in poly]
            if len(pts) > 1:
                d.line(pts, fill=col, width=w, joint="curve")
            for x, y in (pts[0], pts[-1]):
                d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col)

    def tip(self, p):
        return _partial(self.polys, p)[1]

    def first_point(self):
        return self.polys[0][0]


class Text(Element):
    def __init__(self, x, y, s, size, color, start, dur, align):
        f = hand_font(size)
        self.s, self.size, self.color, self.start = s, size, color, start
        a, b, c, e = f.getbbox(s)
        width = c - a
        x0 = x - width / 2 if align == "center" else x - width if align == "right" else x
        self.origin = (x0 - a, y - b)          # pillow text origin so the ink box starts at (x0, y)
        self.ink = (x0, y, x0 + width, y + (e - b))
        self.dur = dur if dur is not None else max(0.3, len(s.replace(" ", "")) / WRITE_CPS)
        self.bbox = (int(self.ink[0] - 8), int(self.ink[1] - 8), int(self.ink[2] + 8), int(self.ink[3] + 8))
        # per-character x spans (ink space) for left-to-right writing
        self.spans = []
        for k, ch in enumerate(s):
            if ch == " ":
                continue
            l0 = f.getlength(s[:k])
            l1 = f.getlength(s[:k + 1])
            self.spans.append((self.origin[0] + l0, self.origin[0] + l1))
        self.total = sum(b - a for a, b in self.spans) or 1

    def _cut(self, p):
        left = self.total * p
        for a, b in self.spans:
            if left <= b - a:
                return a + left, (a, b), left / max(1e-6, b - a)
            left -= b - a
        a, b = self.spans[-1]
        return b, (a, b), 1.0

    def draw(self, img, p, ox, oy):
        f = hand_font(self.size * SS)
        layer = Image.new("L", img.size, 0)
        ImageDraw.Draw(layer).text(((self.origin[0] - ox) * SS, (self.origin[1] - oy) * SS), self.s, font=f, fill=255)
        if p < 1:
            x, _, _ = self._cut(p)
            cut = max(0, int((x - ox) * SS))
            ImageDraw.Draw(layer).rectangle((cut, 0, layer.size[0], layer.size[1]), fill=0)
        base = Image.new("RGBA", layer.size, self.color + (0,))
        base.putalpha(layer)
        img.alpha_composite(base)

    def tip(self, p):
        x, _, u = self._cut(p)
        y0, y1 = self.ink[1], self.ink[3]
        return x, y0 + (y1 - y0) * (0.55 + 0.35 * math.sin(u * math.pi * 3))

    def first_point(self):
        return self.spans[0][0], (self.ink[1] + self.ink[3]) / 2


class Highlight(Element):
    """Translucent marker fill, swept left to right in zig-zag strokes (drawn under ink by order of creation)."""

    def __init__(self, box, color, start, dur, rnd, alpha=110, vertical=False):
        x0, y0, x1, y1 = box
        self.box, self.color, self.alpha, self.start, self.vertical = box, color, alpha, start, vertical
        self.dur = dur if dur is not None else max(0.35, min(1.2, (x1 - x0) / 1400))
        self.bbox = (int(x0 - 6), int(y0 - 6), int(x1 + 6), int(y1 + 6))
        self.jit = [rnd.uniform(-3, 3) for _ in range(4)]

    def draw(self, img, p, ox, oy):
        x0, y0, x1, y1 = self.box
        j = self.jit
        if self.vertical:
            ye = y1 - (y1 - y0) * p
            poly = [(x0 + 3, y1), (x1 - 3, y1), (x1 - 3 + j[0] * 0.3, ye), (x0 + 3 + j[1] * 0.3, ye + j[2] * 0.5)]
        else:
            xe = x0 + (x1 - x0) * p
            poly = [(x0 + j[0], y0 + j[1]), (xe, y0 + j[2] * 0.5), (xe, y1 + j[3] * 0.5), (x0 + j[1], y1 + j[0])]
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([((x - ox) * SS, (y - oy) * SS) for x, y in poly], fill=self.color + (self.alpha,))
        img.alpha_composite(layer)

    def tip(self, p):
        x0, y0, x1, y1 = self.box
        if self.vertical:
            return x0 + (x1 - x0) * (0.5 + 0.45 * math.sin(p * 40)), y1 - (y1 - y0) * p
        return x0 + (x1 - x0) * p, y0 + (y1 - y0) * (0.5 + 0.45 * math.sin(p * 40))



class Fill(Element):
    """Marker colour inside polygons, swept left to right. Schedule it after the outline it fills (and before the
    details drawn on top): finished elements are cached in finishing order, so later ink stays on top."""

    def __init__(self, polys, color, start, dur, alpha=150):
        self.polys, self.color, self.alpha, self.start = polys, color, alpha, start
        self.bbox = _bbox(polys, 4)
        self.dur = dur if dur is not None else max(0.25, min(0.8, (self.bbox[2] - self.bbox[0]) / 900))

    def draw(self, img, p, ox, oy):
        mask = Image.new("L", img.size, 0)
        d = ImageDraw.Draw(mask)
        for poly in self.polys:
            d.polygon([((x - ox) * SS, (y - oy) * SS) for x, y in poly], fill=self.alpha)
        if p < 1:
            x0, _, x1, _ = self.bbox
            cut = max(0, int((x0 + (x1 - x0) * p - ox) * SS))
            d.rectangle((cut, 0, mask.size[0], mask.size[1]), fill=0)
        layer = Image.new("RGBA", img.size, self.color + (0,))
        layer.putalpha(mask)
        img.alpha_composite(layer)

    def tip(self, p):
        x0, y0, x1, y1 = self.bbox
        return x0 + (x1 - x0) * p, y0 + (y1 - y0) * (0.5 + 0.42 * math.sin(p * 46))


def _ellipse(cx, cy, rx, ry, n=48, a0=0.0, a1=2 * math.pi):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * k / n), cy + ry * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


SKIN = (247, 214, 186)
HAIR = (52, 44, 40)
MOODS = ("happy", "sad", "shock", "think", "angry", "worried", "neutral")
POSES = ("stand", "point_r", "point_l", "arms_up", "hands_hip", "think", "shrug", "hold", "wave")


class Person:
    """Anchors of a drawn character (screen coords): head=(x, y, r), hand_l/hand_r, top, end time."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _arm(kind, side, sh, h, head, hip_pt):
    """Elbow and hand for one arm. side=-1 is the character's arm on screen-left."""
    x, y = sh
    hx, hy, r = head
    if kind == "point":
        return (x + side * 0.15 * h, y + 0.0 * h), (x + side * 0.33 * h, y - 0.05 * h)
    if kind == "up":
        return (x + side * 0.09 * h, y - 0.12 * h), (x + side * 0.15 * h, y - 0.27 * h)
    if kind == "wave":
        return (x + side * 0.15 * h, y + 0.02 * h), (x + side * 0.20 * h, y - 0.17 * h)
    if kind == "hip":
        return (x + side * 0.13 * h, y + 0.11 * h), (hip_pt[0] + side * 0.01 * h, hip_pt[1] - 0.05 * h)
    if kind == "chin":
        return (x + side * 0.07 * h, y + 0.17 * h), (hx + side * 0.35 * r, hy + 1.02 * r)
    if kind == "shrug":
        return (x + side * 0.08 * h, y + 0.12 * h), (x + side * 0.22 * h, y + 0.02 * h)
    if kind == "hold":
        return (x + side * 0.05 * h, y + 0.15 * h), (x - side * 0.06 * h, y + 0.16 * h)
    return (x + side * 0.05 * h, y + 0.14 * h), (x + side * 0.07 * h, y + 0.27 * h)


_POSE_ARMS = {"stand": ("down", "down"), "point_r": ("down", "point"), "point_l": ("point", "down"),
              "arms_up": ("up", "up"), "hands_hip": ("hip", "hip"), "think": ("down", "chin"),
              "shrug": ("shrug", "shrug"), "hold": ("hold", "hold"), "wave": ("down", "wave")}


def _face(mood, hx, hy, r):
    """Face strokes (eyes, brows, mouth) and blue extras (sweat/tear) for a mood."""
    out, blue = [], []
    ex, ey, er = 0.36 * r, hy - 0.02 * r, 0.07 * r
    look = (0.08 * r, -0.08 * r) if mood == "think" else (0, 0)
    if mood == "shock":
        for sx in (-1, 1):
            out.append(_ellipse(hx + sx * ex, ey, 0.15 * r, 0.17 * r, 20))
            out.append(_ellipse(hx + sx * ex, ey + 0.03 * r, 0.04 * r, 0.04 * r, 8))
    elif mood == "happy":
        for sx in (-1, 1):
            out.append(_ellipse(hx + sx * ex, ey + 0.06 * r, 0.12 * r, 0.10 * r, 12, math.pi, 2 * math.pi))
    else:
        for sx in (-1, 1):
            out.append(_ellipse(hx + sx * ex + look[0], ey + look[1], er, er, 8))
    by = ey - 0.27 * r
    if mood == "angry":
        out += [[(hx - 0.55 * r, by - 0.06 * r), (hx - 0.16 * r, by + 0.10 * r)],
                [(hx + 0.55 * r, by - 0.06 * r), (hx + 0.16 * r, by + 0.10 * r)]]
    elif mood in ("sad", "worried"):
        out += [[(hx - 0.55 * r, by + 0.08 * r), (hx - 0.18 * r, by - 0.06 * r)],
                [(hx + 0.55 * r, by + 0.08 * r), (hx + 0.18 * r, by - 0.06 * r)]]
    elif mood == "shock":
        out += [_ellipse(hx + sx * ex, by - 0.08 * r, 0.16 * r, 0.06 * r, 10, math.pi, 2 * math.pi) for sx in (-1, 1)]
    elif mood == "think":
        out += [[(hx + 0.18 * r, by - 0.10 * r), (hx + 0.40 * r, by - 0.16 * r), (hx + 0.56 * r, by - 0.10 * r)]]
    my = hy + 0.45 * r
    if mood == "happy":
        out.append(_ellipse(hx, my - 0.12 * r, 0.36 * r, 0.24 * r, 18, 0.15, math.pi - 0.15))
    elif mood in ("sad", "angry"):
        out.append(_ellipse(hx, my + 0.16 * r, 0.26 * r, 0.16 * r, 14, math.pi + 0.3, 2 * math.pi - 0.3))
    elif mood == "shock":
        out.append(_ellipse(hx, my + 0.02 * r, 0.13 * r, 0.18 * r, 18))
    elif mood == "worried":
        out.append([(hx - 0.28 * r + 0.56 * r * k / 12, my + 0.05 * r * math.sin(k * 1.6)) for k in range(13)])
    elif mood == "think":
        out.append([(hx - 0.10 * r, my + 0.02 * r), (hx + 0.24 * r, my - 0.04 * r)])
    else:
        out.append([(hx - 0.2 * r, my), (hx + 0.2 * r, my)])
    if mood in ("worried", "shock"):
        sx, sy = hx + 0.92 * r, hy - 0.55 * r
        blue.append([(sx, sy)] + _ellipse(sx, sy + 0.24 * r, 0.09 * r, 0.09 * r, 12, -0.3, math.pi + 0.3) + [(sx, sy)])
    if mood == "sad":
        tx, ty = hx - ex, ey + 0.16 * r
        blue.append([(tx, ty)] + _ellipse(tx, ty + 0.20 * r, 0.07 * r, 0.07 * r, 12, -0.3, math.pi + 0.3) + [(tx, ty)])
    return out, blue


def _hair(style, hx, hy, r):
    """Filled hair polygons for a style ('short', 'long', 'bun', 'none')."""
    if style == "none":
        return []
    cap = _ellipse(hx, hy, 1.06 * r, 1.06 * r, 24, math.pi * 1.04, math.pi * 1.96)
    fringe = [(hx + 0.9 * r - 1.8 * r * k / 6, hy - 0.42 * r + (0.10 * r if k % 2 else 0)) for k in range(7)]
    polys = [cap + fringe]
    if style == "long":
        for sx in (-1, 1):
            polys.append([(hx + sx * 1.04 * r, hy - 0.2 * r), (hx + sx * 1.14 * r, hy + 1.15 * r),
                          (hx + sx * 0.80 * r, hy + 1.10 * r), (hx + sx * 0.86 * r, hy - 0.1 * r)])
    if style == "bun":
        polys.append(_ellipse(hx + 0.2 * r, hy - 1.18 * r, 0.32 * r, 0.28 * r, 18))
    return polys


# ---------- animated stick-figure mascot: drawn by the pen, then alive (blink, breathe, act, walk, jump) ----------
# Limb angles in degrees from straight down; 90 = horizontal outward, 180 = straight up, < 0 or > 180 = across the body.
# arms/legs: ((upper, lower) for the screen-left limb, (upper, lower) for the screen-right limb).
_SP = lambda arms, legs=((8, 3), (8, 3)), lean=0, tilt=0, look=(0, 0): dict(arms=arms, legs=legs, lean=lean, tilt=tilt, look=look)
STICK_POSES = {
    "stand": _SP(((22, 12), (22, 12))),
    "wave": _SP(((22, 12), (100, 150)), tilt=-6),
    "point_r": _SP(((22, 12), (86, 90)), legs=((10, 3), (6, 3)), lean=3, tilt=5, look=(0.14, 0)),
    "point_l": _SP(((86, 90), (22, 12)), legs=((6, 3), (10, 3)), lean=-3, tilt=-5, look=(-0.14, 0)),
    "point_up": _SP(((22, 12), (115, 170)), tilt=4, look=(0.06, -0.12)),
    "cheer": _SP(((120, 150), (120, 150)), legs=((14, 5), (14, 5)), look=(0, -0.04)),
    "shrug": _SP(((42, 118), (42, 118)), tilt=-9),
    "think": _SP(((22, 12), (60, 200)), tilt=8, look=(0.12, -0.12)),
    "hips": _SP(((42, -28), (42, -28)), legs=((12, 4), (12, 4))),
    "present_r": _SP(((22, 12), (58, 82)), tilt=6, look=(0.12, 0.02)),
    "present_l": _SP(((58, 82), (22, 12)), tilt=-6, look=(-0.12, 0.02)),
    "hold_up": _SP(((125, 165), (125, 165)), look=(0, -0.1)),
    "shock": _SP(((58, 140), (58, 140)), legs=((14, 6), (14, 6)), tilt=0),
    "worried": _SP(((60, 200), (60, 200)), legs=((5, -2), (5, -2)), tilt=-4),
    "sad": _SP(((12, 5), (12, 5)), legs=((6, 2), (6, 2)), lean=0, tilt=-10, look=(0, 0.1)),
    "facepalm": _SP(((22, 12), (80, 195)), tilt=-6, look=(0, 0.06)),
}
STICK_MOODS = ("happy", "neutral", "shock", "sad", "worried", "think", "angry", "love", "proud")
MOUTH = (176, 62, 62)
BLUSH = (240, 120, 130)


def _rot(a_deg, side):
    a = math.radians(a_deg)
    return side * math.sin(a), math.cos(a)


def _qcurve(p0, p1, p2, n=10):
    return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
             (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]) for u in (k / n for k in range(n + 1))]


def _stick_face(mood, hx, hy, r, look, blink):
    """(ink polylines, filled polygons [(poly, colour, alpha)], blue polylines) for the mascot's face."""
    lines, fills, blue = [], [], []
    lx, ly = look[0] * r, look[1] * r
    ex, ey = 0.34 * r, hy - 0.04 * r
    eyes = [(hx - ex + lx, ey + ly), (hx + ex + lx, ey + ly)]
    dot = 0.095 * r
    if mood in ("happy", "proud"):
        for x, y in eyes:
            lines.append(_ellipse(x, y + 0.06 * r, 0.13 * r, 0.12 * r, 12, math.pi * 1.05, math.pi * 1.95))
    elif mood == "love":
        for x, y in eyes:
            fills.append((_heart(x, y, 0.3 * r), RED, 255))
    elif mood == "shock":
        for x, y in eyes:
            lines.append(_ellipse(x, y, 0.17 * r, 0.19 * r, 20))
            fills.append((_ellipse(x, y + 0.02 * r, 0.065 * r, 0.065 * r, 12), INK, 255))
    elif blink:
        for x, y in eyes:
            lines.append([(x - 0.1 * r, y), (x + 0.1 * r, y)])
    else:
        for x, y in eyes:
            fills.append((_ellipse(x, y, dot, dot * 1.15, 14), INK, 255))
            fills.append((_ellipse(x + 0.03 * r, y - 0.04 * r, 0.03 * r, 0.03 * r, 8), PAPER, 255))
    by = ey - 0.27 * r + ly
    if mood == "angry":
        lines += [[(eyes[0][0] - 0.16 * r, by - 0.06 * r), (eyes[0][0] + 0.12 * r, by + 0.07 * r)],
                  [(eyes[1][0] + 0.16 * r, by - 0.06 * r), (eyes[1][0] - 0.12 * r, by + 0.07 * r)]]
    elif mood in ("sad", "worried"):
        lines += [[(eyes[0][0] - 0.15 * r, by + 0.07 * r), (eyes[0][0] + 0.12 * r, by - 0.05 * r)],
                  [(eyes[1][0] + 0.15 * r, by + 0.07 * r), (eyes[1][0] - 0.12 * r, by - 0.05 * r)]]
    elif mood == "shock":
        lines += [_ellipse(x, by - 0.1 * r, 0.14 * r, 0.06 * r, 10, math.pi * 1.1, math.pi * 1.9) for x, _ in eyes]
    elif mood == "think":
        lines.append(_qcurve((eyes[1][0] - 0.14 * r, by - 0.04 * r), (eyes[1][0], by - 0.16 * r), (eyes[1][0] + 0.15 * r, by - 0.06 * r), 8))
    mx, my = hx + 0.6 * lx, hy + 0.4 * r + 0.5 * ly
    if mood in ("happy", "love"):
        mouth = _ellipse(mx, my - 0.08 * r, 0.27 * r, 0.25 * r, 18, 0.0, math.pi)
        mouth = mouth + [mouth[0]]
        fills.append((mouth, MOUTH, 255))
        fills.append((_ellipse(mx, my + 0.1 * r, 0.12 * r, 0.06 * r, 12), (236, 128, 128), 255))
        lines.append(mouth)
    elif mood == "proud":
        lines.append(_qcurve((mx - 0.22 * r, my - 0.02 * r), (mx + 0.02 * r, my + 0.14 * r), (mx + 0.26 * r, my - 0.1 * r), 10))
    elif mood == "neutral":
        lines.append(_ellipse(mx, my - 0.1 * r, 0.17 * r, 0.12 * r, 12, 0.35, math.pi - 0.35))
    elif mood == "shock":
        o = _ellipse(mx, my + 0.02 * r, 0.12 * r, 0.17 * r, 18)
        fills.append((o, MOUTH, 255))
        lines.append(o)
    elif mood in ("sad", "angry"):
        lines.append(_ellipse(mx, my + 0.14 * r, 0.2 * r, 0.13 * r, 12, math.pi + 0.35, 2 * math.pi - 0.35))
    elif mood == "worried":
        lines.append([(mx - 0.22 * r + 0.44 * r * k / 10, my + 0.035 * r * math.sin(k * 1.9)) for k in range(11)])
    elif mood == "think":
        lines.append([(mx - 0.08 * r, my + 0.02 * r), (mx + 0.18 * r, my - 0.05 * r)])
    if mood not in ("angry",):
        a = 140 if mood == "love" else 95
        for sx in (-1, 1):
            fills.append((_ellipse(hx + sx * 0.58 * r + 0.5 * lx, hy + 0.2 * r, 0.14 * r, 0.075 * r, 16), BLUSH, a))
    if mood in ("worried", "shock"):
        sx, sy = hx + 0.95 * r, hy - 0.5 * r
        blue.append([(sx, sy)] + _ellipse(sx, sy + 0.22 * r, 0.085 * r, 0.085 * r, 12, -0.3, math.pi + 0.3) + [(sx, sy)])
    if mood == "sad":
        tx, ty = eyes[0][0], eyes[0][1] + 0.14 * r
        blue.append([(tx, ty)] + _ellipse(tx, ty + 0.2 * r, 0.07 * r, 0.07 * r, 12, -0.3, math.pi + 0.3) + [(tx, ty)])
    return lines, fills, blue


class Stick(Element):
    """Recurring stick-figure host. The pen draws it at `start` (dur ~1.2-1.8 s); afterwards it is re-drawn every
    frame from its timeline: idle breathing/blinking/head sway, `act()` pose/mood changes (0.35 s blend),
    `walk()` across the board, `jump()`. Wave/cheer/worried poses keep moving on their own."""
    animated = True
    BLEND = 0.35

    def __init__(self, cx, base, h, start, pose, mood, accent, color, dur, look, seed, drawn=True):
        assert pose in STICK_POSES and mood in STICK_MOODS, (pose, mood)
        self.cx, self.base, self.h, self.start = cx, base, h, start
        self.accent, self.color = accent, color
        self.keys = [(start, pose, mood, look)]
        self.moves, self.jumps = [], []
        self.seed = seed
        self.w = max(5, round(h * 0.027))
        self.now = start
        self.drawn = drawn
        ink, _ = self._shapes(start, still=True)
        L = sum(_length(p) for p, _w, _c in ink)
        self.dur = dur if dur is not None else (max(0.9, min(1.8, L / (PEN_SPEED * 1.1))) if drawn else 0.0)

    # -- timeline --
    def act(self, t, pose=None, mood=None, look=None):
        _, p0, m0, l0 = max((k for k in self.keys if k[0] <= t), key=lambda k: k[0], default=self.keys[0])
        assert (pose or p0) in STICK_POSES and (mood or m0) in STICK_MOODS, (pose, mood)
        self.keys.append((t, pose or p0, mood or m0, look if look is not None else (None if pose else l0)))
        self.keys.sort(key=lambda k: k[0])
        if pose == "shock":
            self.jumps.append((t, 0.35, 0.07))
        return self

    def walk(self, t, to_x, dur=None):
        x0 = self.x_at(t)
        dur = dur or max(0.6, abs(to_x - x0) / (0.95 * self.h))
        self.moves.append((t, t + dur, x0, to_x))
        self.moves.sort()
        return self

    def jump(self, t, height=0.22, dur=0.55):
        self.jumps.append((t, dur, height))
        return self

    @property
    def last(self):
        return max([k[0] for k in self.keys] + [m[1] for m in self.moves] + [j[0] + j[1] for j in self.jumps])

    def x_at(self, t):
        x = self.cx
        for t0, t1, x0, x1 in self.moves:
            if t >= t1:
                x = x1
            elif t >= t0:
                return x0 + (x1 - x0) * fk.smooth((t - t0) / (t1 - t0))
        return x

    def head_at(self, t):
        g = self._geom(t)
        return g["head"]

    def hand_at(self, t, side=1):
        return self._geom(t)["hands"][0 if side < 0 else 1]

    @property
    def bbox(self):
        xs = [self.cx] + [m[3] for m in self.moves]
        up = max([j[2] for j in self.jumps], default=0) + 0.25
        return (int(min(xs) - 0.72 * self.h), int(self.base - (1.1 + up) * self.h),
                int(max(xs) + 0.72 * self.h), int(self.base + 0.06 * self.h))

    # -- pose at time t --
    def _pose(self, t, still=False):
        keys = [k for k in self.keys if k[0] <= t] or self.keys[:1]
        cur = keys[-1]
        P = STICK_POSES[cur[1]]
        u = 1.0 if len(keys) < 2 else fk.smooth((t - cur[0]) / self.BLEND)
        Q = STICK_POSES[keys[-2][1]] if len(keys) >= 2 else P
        mix = lambda a, b: a + (b - a) * u
        arms = [[mix(qa, pa) for qa, pa in zip(q, p)] for q, p in zip(Q["arms"], P["arms"])]
        legs = [[mix(qa, pa) for qa, pa in zip(q, p)] for q, p in zip(Q["legs"], P["legs"])]
        lean, tilt = mix(Q["lean"], P["lean"]), mix(Q["tilt"], P["tilt"])
        look_p = cur[3] if cur[3] is not None else P["look"]
        look_q = (keys[-2][3] if keys[-2][3] is not None else Q["look"]) if len(keys) >= 2 else look_p
        look = (mix(look_q[0], look_p[0]), mix(look_q[1], look_p[1]))
        mood = cur[2] if u > 0.4 or len(keys) < 2 else keys[-2][2]
        x, y = self.x_at(t), 0.0
        if not still:
            ph = self.seed * 1.7
            y += 0.006 * self.h * math.sin(2 * math.pi * 0.45 * t + ph)
            tilt += 3.0 * math.sin(2 * math.pi * 0.27 * t + ph)
            if cur[1] == "wave":
                arms[1][1] += 24 * math.sin(2 * math.pi * 2.3 * t) * u
            elif cur[1] == "cheer":
                k = abs(math.sin(2 * math.pi * 1.25 * (t - cur[0])))
                y -= 0.07 * self.h * k * u
                for a in arms:
                    a[1] += 10 * k
            elif cur[1] == "worried":
                x += 1.6 * math.sin(2 * math.pi * 9 * t)
            elif cur[1].startswith("point") or cur[1].startswith("present"):
                arms[1 if cur[1].endswith("_r") or cur[1] == "point_up" else 0][1] += 6 * math.sin(2 * math.pi * 1.6 * t) * u
            for t0, t1, x0, x1 in self.moves:
                if t0 <= t < t1:
                    phs = 2 * math.pi * 2.4 * (t - t0)
                    d = 1 if x1 > x0 else -1
                    lean = 7 * d
                    for side, leg in zip((-1, 1), legs):
                        lift = max(0.0, math.sin(phs + (0 if side < 0 else math.pi)))
                        leg[0] += 26 * lift
                        leg[1] -= 30 * lift
                    for side, arm in zip((-1, 1), arms):
                        sw = 22 * math.sin(phs + (math.pi if side < 0 else 0))
                        arm[0] += sw
                        arm[1] += sw
                    y -= 0.02 * self.h * abs(math.sin(phs))
            for tj, dj, hj in self.jumps:
                if tj <= t < tj + dj:
                    v = (t - tj) / dj
                    y -= hj * self.h * math.sin(math.pi * v)
                    for leg in legs:
                        leg[0] += 18 * math.sin(math.pi * v)
                        leg[1] -= 26 * math.sin(math.pi * v)
        blink = (not still) and ((t + self.seed * 0.9) % 3.7) < 0.13
        return dict(arms=arms, legs=legs, lean=lean, tilt=tilt, look=look, mood=mood, x=x, y=y, blink=blink)

    def _geom(self, t, still=False):
        S = self._pose(t, still)
        h = self.h
        thigh, shin = 0.205 * h, 0.195 * h
        drops = []
        for side, (a, b) in zip((-1, 1), S["legs"]):
            drops.append(thigh * _rot(a, side)[1] + shin * _rot(b, side)[1])
        hip = (S["x"], self.base - max(drops) + S["y"])
        L = math.radians(S["lean"])
        neck = (hip[0] + 0.27 * h * math.sin(L), hip[1] - 0.27 * h * math.cos(L))
        r = 0.165 * h
        HT = math.radians(S["lean"] + S["tilt"])
        head = (neck[0] + (r + 0.012 * h) * math.sin(HT), neck[1] - (r + 0.012 * h) * math.cos(HT), r)
        sh = (neck[0] - 0.045 * h * math.sin(L), neck[1] + 0.045 * h * math.cos(L))
        arms, hands, legs = [], [], []
        for side, (a, b) in zip((-1, 1), S["arms"]):
            ux, uy = _rot(a, side)
            el = (sh[0] + 0.16 * h * ux, sh[1] + 0.16 * h * uy)
            fx, fy = _rot(b, side)
            hd = (el[0] + 0.15 * h * fx, el[1] + 0.15 * h * fy)
            arms.append([sh, el, hd])
            hands.append(hd)
        for side, (a, b) in zip((-1, 1), S["legs"]):
            ux, uy = _rot(a, side)
            kn = (hip[0] + thigh * ux, hip[1] + thigh * uy)
            fx, fy = _rot(b, side)
            ft = (kn[0] + shin * fx, kn[1] + shin * fy)
            legs.append([hip, kn, ft, (ft[0] + side * 0.05 * h, ft[1])])
        return dict(S=S, hip=hip, neck=neck, head=head, arms=arms, hands=hands, legs=legs, r=r)

    def _shapes(self, t, still=False):
        """Ink strokes [(poly, width, colour)] in pen order and fills [(poly, colour, alpha, after_frac)]."""
        g = self._geom(t, still)
        S, (hx, hy, r), w = g["S"], g["head"], self.w
        c = self.color
        head = _ellipse(hx, hy, r, r * 1.03, 44, -1.9, -1.9 + 2 * math.pi * 1.03)
        top = (hx + 0.1 * r * math.sin(math.radians(S["tilt"])), hy - r * 1.02)
        tuft = _qcurve(top, (top[0] - 0.05 * self.h, top[1] - 0.09 * self.h), (top[0] + 0.045 * self.h, top[1] - 0.075 * self.h), 10) \
            + _qcurve((top[0] + 0.045 * self.h, top[1] - 0.075 * self.h), (top[0] + 0.06 * self.h, top[1] - 0.03 * self.h), (top[0] + 0.015 * self.h, top[1] - 0.045 * self.h), 6)[1:]
        ink = [(head, w, c), (tuft, w, c), ([g["neck"], g["hip"]], w, c)]
        ink += [(a, w, c) for a in g["arms"]] + [(l, w, c) for l in g["legs"]]
        nx, ny = g["neck"]
        wig = math.sin(2 * math.pi * 1.1 * t) * 0.012 * self.h if not still else 0
        scarf = [(nx - 0.055 * self.h, ny - 0.004 * self.h), (nx + 0.055 * self.h, ny - 0.004 * self.h), (nx, ny + 0.06 * self.h)]
        tail = [(nx + 0.03 * self.h, ny), (nx + 0.1 * self.h, ny + 0.035 * self.h + wig), (nx + 0.075 * self.h, ny + 0.075 * self.h + wig)]
        face, ffills, blue = _stick_face(S["mood"], hx, hy, r, S["look"], S["blink"])
        ink += [(scarf + [scarf[0]], max(4, w - 2), c), (tail + [tail[0]], max(4, w - 2), c)]
        ink += [(p, max(4, w - 1), c) for p in face] + [(p, max(4, w - 2), BLUE) for p in blue]
        fills = [(head[:-2], PAPER, 255, 0.12), (scarf, self.accent, 255, 0.6), (tail, self.accent, 255, 0.6)]
        fills += [(p, col, a, 0.85) for p, col, a in ffills] + [(p[:-1], (150, 200, 245), 230, 0.95) for p in blue]
        return ink, fills

    # -- Element interface --
    def _wob(self, polys):
        out = []
        for i, p in enumerate(polys):
            ph = self.seed * 2.3 + i * 1.91
            q, s = [], 0.0
            rp = _resample(p, 6.0)
            for k, pt in enumerate(rp):
                if k:
                    s += math.dist(pt, rp[k - 1])
                q.append((pt[0] + 0.9 * math.sin(s * 0.03 + ph), pt[1] + 0.9 * math.sin(s * 0.037 + ph * 1.3)))
            out.append(q)
        return out

    def _draw_list(self, p):
        t = self.start if p < 1 else self.now
        ink, fills = self._shapes(t, still=p < 1)
        polys = self._wob([q for q, _w, _c in ink])
        if p < 1:
            vis, tip = _partial(polys, p)
        else:
            vis, tip = polys, polys[-1][-1]
        return ink, fills, polys, vis, tip

    def draw(self, img, p, ox, oy):
        ink, fills, polys, vis, _ = self._draw_list(p)
        d = ImageDraw.Draw(img)
        P = lambda q: [((x - ox) * SS, (y - oy) * SS) for x, y in q]

        def fill(k):
            for poly, col, a, frac in fills[k[0]:k[1]]:
                if p >= frac:
                    d.polygon(P(poly), fill=col + (a,))

        def line(i):
            if i >= len(vis):
                return
            q, w, col = P(vis[i]), ink[i][1] * SS, ink[i][2] + (255,)
            if len(q) > 1:
                d.line(q, fill=col, width=w, joint="curve")
            for x, y in (q[0], q[-1]):
                d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col)

        g = self._geom(self.start if p < 1 else self.now, still=p < 1)
        hx, hy, r = g["head"]
        front = [3 + k for k, (x, y) in enumerate(g["hands"]) if math.hypot(x - hx, y - hy) < r * 1.1]

        def hand(i):
            if p >= 1 or i < len(vis) and len(vis[i]) == len(polys[i]):
                x, y = P([g["hands"][i - 3]])[0]
                rr = 0.024 * self.h * SS
                d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=self.color + (255,))

        fill((0, 1))                     # head paper (hides whatever is behind the face)
        for i in range(2, 7):            # body, arms, legs
            if i not in front:
                line(i)
                if i in (3, 4):
                    hand(i)
        line(0)
        line(1)
        fill((1, 3))                     # scarf colour, then its outline
        line(7)
        line(8)
        fill((3, len(fills)))            # eyes, mouth, blush, drops
        for i in range(9, len(ink)):
            line(i)
        for i in front:                  # a hand on the chin / face stays in front of it
            line(i)
            hand(i)

    def tip(self, p):
        return self._draw_list(min(p, 0.999))[4]

    def first_point(self):
        return self._shapes(self.start, still=True)[0][0][0][0]


# ---------- stickers (coloured, die-cut, pop in; never drawn by the pen) ----------
YELLOW = (255, 200, 58)
STICKER_DARK = (70, 44, 22)
_SS3 = 3


def _heart(cx, cy, s, n=60):
    pts = []
    for k in range(n + 1):
        t = 2 * math.pi * k / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s / 34, cy - y * s / 34 - s * 0.04))
    return pts


def _star(cx, cy, ro, ri, n=5, rot=-math.pi / 2):
    return [(cx + (ro if k % 2 == 0 else ri) * math.cos(rot + math.pi * k / n),
             cy + (ro if k % 2 == 0 else ri) * math.sin(rot + math.pi * k / n)) for k in range(2 * n)]


def _die_cut(core, border, rot):
    """White border + soft shadow around an RGBA sprite, then rotate."""
    pad = border * 3
    big = Image.new("RGBA", (core.width + 2 * pad, core.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(core, (pad, pad))
    a = big.getchannel("A").filter(ImageFilter.GaussianBlur(border * 0.6)).point(lambda v: 255 if v > 10 else 0)
    a = a.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
    white = Image.new("RGBA", big.size, (255, 255, 255, 0))
    white.putalpha(a)
    shadow = Image.new("RGBA", big.size, (20, 20, 30, 0))
    shadow.putalpha(a.point(lambda v: int(v * 0.32)).filter(ImageFilter.GaussianBlur(border * 0.8)))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (int(border * 0.4), int(border * 0.7)))
    out.alpha_composite(white)
    out.alpha_composite(big)
    if rot:
        out = out.rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
    return out


def _face_sticker(d, mood, D, c):
    """Emoji-style face drawn with PIL on draw `d`, centre c, diameter D (already supersampled)."""
    cx, cy = c
    R = D / 2
    base = (244, 112, 64) if mood == "angry" else YELLOW
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=base, outline=(196, 128, 24), width=int(D * 0.03))
    k = STICKER_DARK
    lw = max(3, int(D * 0.045))
    ex, ey = R * 0.36, cy - R * 0.12

    def eye_dots(rr=0.09, dy=0.0, dx=0.0):
        for sx in (-1, 1):
            x, y = cx + sx * ex + dx * R, ey + dy * R
            d.ellipse((x - rr * R, y - rr * 1.25 * R, x + rr * R, y + rr * 1.25 * R), fill=k)

    if mood in ("happy", "laugh"):
        for sx in (-1, 1):
            x = cx + sx * ex
            d.arc((x - 0.17 * R, ey - 0.12 * R, x + 0.17 * R, ey + 0.2 * R), 200, 340, fill=k, width=lw)
        d.chord((cx - 0.5 * R, cy - 0.05 * R, cx + 0.5 * R, cy + 0.62 * R), 0, 180, fill=k)
        d.ellipse((cx - 0.22 * R, cy + 0.3 * R, cx + 0.22 * R, cy + 0.56 * R), fill=(232, 84, 96))
        if mood == "laugh":
            for sx in (-1, 1):
                d.polygon([(cx + sx * 0.62 * R, ey + 0.05 * R), (cx + sx * 0.78 * R, ey + 0.38 * R),
                           (cx + sx * 0.52 * R, ey + 0.36 * R)], fill=(90, 170, 240))
    elif mood == "love":
        for sx in (-1, 1):
            d.polygon(_heart(cx + sx * ex, ey, 0.42 * R), fill=(226, 48, 72))
        d.chord((cx - 0.42 * R, cy + 0.05 * R, cx + 0.42 * R, cy + 0.58 * R), 0, 180, fill=k)
    elif mood == "shock":
        for sx in (-1, 1):
            x = cx + sx * ex
            d.ellipse((x - 0.17 * R, ey - 0.2 * R, x + 0.17 * R, ey + 0.2 * R), fill=(255, 255, 255), outline=k, width=lw // 2)
            d.ellipse((x - 0.07 * R, ey - 0.06 * R, x + 0.07 * R, ey + 0.1 * R), fill=k)
            d.arc((x - 0.2 * R, ey - 0.52 * R, x + 0.2 * R, ey - 0.22 * R), 200, 340, fill=k, width=lw)
        d.ellipse((cx - 0.17 * R, cy + 0.2 * R, cx + 0.17 * R, cy + 0.66 * R), fill=k)
    elif mood in ("sad", "cry"):
        eye_dots()
        for sx in (-1, 1):
            d.line([(cx + sx * 0.55 * R, ey - 0.25 * R), (cx + sx * 0.18 * R, ey - 0.38 * R)], fill=k, width=lw)
        d.arc((cx - 0.34 * R, cy + 0.32 * R, cx + 0.34 * R, cy + 0.8 * R), 200, 340, fill=k, width=lw)
        x = cx - ex
        d.polygon([(x, ey + 0.12 * R), (x - 0.13 * R, ey + 0.45 * R), (x + 0.13 * R, ey + 0.45 * R)], fill=(90, 170, 240))
        d.ellipse((x - 0.13 * R, ey + 0.34 * R, x + 0.13 * R, ey + 0.58 * R), fill=(90, 170, 240))
    elif mood == "angry":
        eye_dots(dy=0.06)
        for sx in (-1, 1):
            d.line([(cx + sx * 0.62 * R, ey - 0.32 * R), (cx + sx * 0.14 * R, ey - 0.1 * R)], fill=k, width=lw + 2)
        d.arc((cx - 0.3 * R, cy + 0.3 * R, cx + 0.3 * R, cy + 0.66 * R), 200, 340, fill=k, width=lw)
    elif mood == "think":
        eye_dots(dx=0.08, dy=-0.06)
        d.arc((cx + 0.1 * R, ey - 0.5 * R, cx + 0.62 * R, ey - 0.22 * R), 200, 330, fill=k, width=lw)
        d.line([(cx - 0.18 * R, cy + 0.42 * R), (cx + 0.3 * R, cy + 0.34 * R)], fill=k, width=lw)
    elif mood == "cool":
        for sx in (-1, 1):
            x = cx + sx * ex
            d.rounded_rectangle((x - 0.3 * R, ey - 0.16 * R, x + 0.3 * R, ey + 0.2 * R), int(0.12 * R), fill=(28, 30, 36))
        d.line([(cx - 0.1 * R, ey - 0.06 * R), (cx + 0.1 * R, ey - 0.06 * R)], fill=(28, 30, 36), width=lw)
        d.arc((cx - 0.38 * R, cy + 0.0 * R, cx + 0.38 * R, cy + 0.55 * R), 20, 160, fill=k, width=lw)
    elif mood == "money":
        f = hand_font(int(0.62 * R))
        for sx in (-1, 1):
            d.text((cx + sx * ex, ey), "đ", font=f, fill=(36, 132, 78), anchor="mm")
        d.chord((cx - 0.48 * R, cy + 0.0 * R, cx + 0.48 * R, cy + 0.6 * R), 0, 180, fill=k)
    else:
        eye_dots()
        d.line([(cx - 0.26 * R, cy + 0.4 * R), (cx + 0.26 * R, cy + 0.4 * R)], fill=k, width=lw)


@lru_cache(None)
def sticker_sprite(kind, size, color, shape, font, rot):
    """RGBA sprite for a sticker. kind: 'face:<mood>', 'icon:<tabler name>', 'text:<words>', 'heart', 'star',
    'check', 'cross', '!', '?'. size = diameter (text stickers grow to fit `font`)."""
    S = _SS3
    D = size * S
    if kind.startswith("text:"):
        txt = kind[5:]
        f = hand_font(font * S)
        a, b_, c, e = f.getbbox(txt)
        tw, th = c - a, e - b_
        if shape == "burst":
            R = max(tw * 0.62, th * 1.1) + 14 * S
            w = h = int(2 * R + 8)
        else:
            w, h = int(tw + 0.9 * th + 40 * S), int(th * 1.65 + 20 * S)
        core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(core)
        if shape == "burst":
            d.polygon(_star(w / 2, h / 2, R, R * 0.8, n=14), fill=color)
        else:
            d.rounded_rectangle((2, 2, w - 2, h - 2), int(h * 0.5 if shape == "pill" else h * 0.18), fill=color)
        d.text((w / 2, h / 2), txt, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=int(font * S * 0.05),
               stroke_fill=tuple(int(v * 0.55) for v in color))
    else:
        core = Image.new("RGBA", (int(D * 1.06), int(D * 1.06)), (0, 0, 0, 0))
        d = ImageDraw.Draw(core)
        c = (core.width / 2, core.height / 2)
        R = D / 2
        if kind.startswith("face:"):
            _face_sticker(d, kind[5:], D, c)
        elif kind == "heart":
            d.polygon(_heart(c[0], c[1] + 0.06 * D, D * 1.04), fill=color or (226, 48, 72))
        elif kind == "star":
            d.polygon(_star(c[0], c[1] + 0.04 * D, R, R * 0.45), fill=color or YELLOW)
        else:
            d.ellipse((c[0] - R, c[1] - R, c[0] + R, c[1] + R), fill=color)
            lw = int(D * 0.09)
            if kind == "check":
                d.line([(c[0] - 0.42 * R, c[1]), (c[0] - 0.08 * R, c[1] + 0.34 * R), (c[0] + 0.46 * R, c[1] - 0.36 * R)],
                       fill=(255, 255, 255), width=lw, joint="curve")
            elif kind == "cross":
                for sx in (-1, 1):
                    d.line([(c[0] - 0.36 * R, c[1] - sx * 0.36 * R), (c[0] + 0.36 * R, c[1] + sx * 0.36 * R)],
                           fill=(255, 255, 255), width=lw)
            elif kind in ("!", "?"):
                d.text(c, kind, font=hand_font(int(D * 0.78)), fill=(255, 255, 255), anchor="mm")
            elif kind.startswith("icon:"):
                s = D * 0.62 / 24
                for poly in icon_polys(kind[5:]):
                    pts = [(c[0] + (x - 12) * s, c[1] + (y - 12) * s) for x, y in poly]
                    if len(pts) > 1:
                        d.line(pts, fill=(255, 255, 255), width=int(D * 0.055), joint="curve")
                        for x, y in (pts[0], pts[-1]):
                            r2 = D * 0.0275
                            d.ellipse((x - r2, y - r2, x + r2, y + r2), fill=(255, 255, 255))
            else:
                raise ValueError(kind)
    core = core.resize((max(1, core.width // S), max(1, core.height // S)), Image.Resampling.LANCZOS)
    return _die_cut(core, max(6, int(size * 0.055)), rot)


def _back_out(u, k=2.2):
    u -= 1
    return 1 + (k + 1) * u ** 3 + k * u ** 2


class Sticker:
    def __init__(self, kind, cx, cy, size, start, color, shape, font, rot, pop, until, bob):
        self.kind, self.cx, self.cy, self.start = kind, cx, cy, start
        self.pop, self.until, self.bob = pop, until, bob
        self.key = (kind, size, color, shape, font, rot)
        self.phase = (cx * 0.013 + cy * 0.007) % 6.28
        self.end = start + pop

    def paste(self, im, t):
        if t < self.start or (self.until is not None and t >= self.until + 0.25):
            return
        sp = sticker_sprite(*self.key)
        u = (t - self.start) / self.pop
        sc = _back_out(min(1.0, u)) if u < 1 else 1.0
        if self.until is not None and t > self.until:
            sc *= max(0.0, 1 - (t - self.until) / 0.25)
        y = self.cy + (self.bob * math.sin(2 * math.pi * 0.55 * (t - self.start) + self.phase) if u >= 1 else 0)
        if sc <= 0.02:
            return
        if abs(sc - 1) > 1e-3:
            sp = sp.resize((max(1, int(sp.width * sc)), max(1, int(sp.height * sc))), Image.Resampling.BILINEAR)
        if u < 0.35:
            sp = sp.copy()
            sp.putalpha(sp.getchannel("A").point(lambda v: int(v * u / 0.35)))
        _paste(im, sp, self.cx - sp.width / 2, y - sp.height / 2)


PEEP_DIR = ASSETS / "people" / "open-peeps"   # Open Peeps (CC0), see LICENSE.txt / catalog.json there


@lru_cache(None)
def peep_image(name, height, color, flip):
    """Open Peeps bust scaled to `height` (at SS scale), black recoloured to `color`, white to paper."""
    im = Image.open(PEEP_DIR / f"{name}.png").convert("RGBA")
    im = im.crop(im.getbbox())
    if flip:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    w = round(im.width * height * SS / im.height)
    im = im.resize((w, height * SS), Image.Resampling.LANCZOS)
    lum = im.convert("L")
    out = Image.composite(Image.new("RGB", im.size, PAPER), Image.new("RGB", im.size, color), lum).convert("RGBA")
    out.putalpha(im.getchannel("A"))
    return out


class Peep(Element):
    """Raster drawing inked in boustrophedon bands top to bottom (soft edge); the pen zig-zags along the band."""

    def __init__(self, name, cx, base, height, start, dur, color, flip, bands=6):
        self.sprite = peep_image(name, int(height), color, flip)
        w = self.sprite.width / SS
        self.box = (cx - w / 2, base - height, cx + w / 2, base)
        self.bbox = tuple(int(v) for v in (self.box[0] - 2, self.box[1] - 2, self.box[2] + 2, self.box[3] + 2))
        self.start, self.bands = start, bands
        self.dur = dur if dur is not None else max(1.2, min(2.8, height / 280))

    def _edge(self, p):
        k = min(self.bands - 1, int(p * self.bands))
        f = p * self.bands - k
        return k, (1 - f if k % 2 else f)

    def draw(self, img, p, ox, oy):
        sp = self.sprite
        if p < 1:
            mw, mh = sp.size
            bh = mh / self.bands
            k, f = self._edge(p)
            mask = Image.new("L", sp.size, 0)
            d = ImageDraw.Draw(mask)
            d.rectangle((0, 0, mw, k * bh), fill=255)
            x0, x1 = (0, f * mw) if k % 2 == 0 else (f * mw, mw)
            d.rectangle((x0, k * bh, x1, (k + 1) * bh), fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(6 * SS))
            sp = sp.copy()
            sp.putalpha(ImageChops.multiply(sp.getchannel("A"), mask))
        img.alpha_composite(sp, (int((self.box[0] - ox) * SS), int((self.box[1] - oy) * SS)))

    def tip(self, p):
        x0, y0, x1, y1 = self.box
        k, f = self._edge(p)
        bh = (y1 - y0) / self.bands
        return x0 + (x1 - x0) * f, y0 + bh * (k + 0.5 + 0.35 * math.sin(p * 90))


# ---------- board ----------
class Board:
    def __init__(self, seed=1, drift=0.035, anchor=None):
        self.rnd = random.Random(seed)
        self.items = []
        self.live = []      # stickers: composited on top every frame, ignored by the pen
        self.audit = []
        self.texts = []     # (text, ink box, start) for the sticker-overlap check
        self.drift = drift
        self.anchor = anchor or (W / 2, H * 0.45)
        self._cache_key, self._cache = None, None

    # -- adding --
    def _add(self, el):
        self.items.append(el)
        self._cache_key = None
        return el

    def strokes(self, polys, start, dur=None, width=8, color=INK, wobble=1.4, alpha=255):
        return self._add(Strokes(polys, start, dur, width, color, self.rnd, wobble, alpha))

    def line(self, a, b, start, **kw):
        return self.strokes([[a, b]], start, **kw)

    def arrow(self, a, b, start, head=28, **kw):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        h1 = (b[0] - head * math.cos(ang - 0.45), b[1] - head * math.sin(ang - 0.45))
        h2 = (b[0] - head * math.cos(ang + 0.45), b[1] - head * math.sin(ang + 0.45))
        return self.strokes([[a, b], [h1, b, h2]], start, **kw)

    def rect(self, box, start, **kw):
        x0, y0, x1, y1 = box
        o = 6
        return self.strokes([[(x0 - o, y0), (x1 + o, y0 + 1)], [(x1, y0 - o), (x1 - 1, y1 + o)],
                             [(x1 + o, y1), (x0 - o, y1 - 1)], [(x0, y1 + o), (x0 + 1, y0 - o)]], start, **kw)

    def circle(self, box, start, turns=1.08, **kw):
        """Rough hand-drawn ellipse around box (slightly overshooting the start)."""
        x0, y0, x1, y1 = box
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        n = 72
        a0 = -2.2
        pts = [(cx + rx * (1 + 0.04 * math.sin(k / 9)) * math.cos(a0 + turns * 2 * math.pi * k / n),
                cy + ry * (1 + 0.04 * math.cos(k / 7)) * math.sin(a0 + turns * 2 * math.pi * k / n)) for k in range(n + 1)]
        return self.strokes([pts], start, **kw)

    def underline(self, x0, x1, y, start, **kw):
        return self.strokes([[(x0, y), ((x0 + x1) / 2, y + 4), (x1, y - 3)]], start, **kw)

    def cross(self, box, start, **kw):
        x0, y0, x1, y1 = box
        return self.strokes([[(x0, y0), (x1, y1)], [(x1, y0), (x0, y1)]], start, **kw)

    def check(self, x, y, size, start, **kw):
        """Tick mark ('✓' is not in the font); (x, y) is the bottom of the tick."""
        return self.strokes([[(x - size * 0.45, y - size * 0.4), (x, y), (x + size * 0.55, y - size)]], start, **kw)

    def bar(self, box, start, color=INK, fill=None, **kw):
        """Hand-drawn chart bar growing upward: marker fill swept bottom-up, then the outline."""
        x0, y0, x1, y1 = box
        if fill:
            self._add(Highlight((x0, y0, x1, y1), fill, start, kw.get("dur", 0.6), self.rnd, alpha=95, vertical=True))
        return self.strokes([[(x0, y1), (x0, y0), (x1, y0), (x1, y1)]], start + 0.1, color=color, **kw)

    def drawing_intervals(self, offset=0.0):
        """(start, end) of every element, shifted by offset: feed to scribble_track for the marker sound."""
        return [(e.start + offset, e.end + offset, isinstance(e, Highlight)) for e in self.items]

    def icon(self, name, cx, cy, size, start, dur=None, width=8, color=INK):
        s = size / 24
        polys = [[(cx + (x - 12) * s, cy + (y - 12) * s) for x, y in p] for p in icon_polys(name)]
        return self.strokes(polys, start, dur, width, color, wobble=1.0)

    def text(self, x, y, s, size=96, start=0.0, dur=None, color=INK, align="left"):
        assert size >= fk.MIN_FONT, (s, size)
        el = self._add(Text(x, y, s, size, color, start, dur, align))
        self.audit.append((s, size, el.ink))
        self.texts.append((s, el.ink, el.start))
        return el

    def highlight(self, box, start, dur=None, color=HIGHLIGHT, alpha=110):
        return self._add(Highlight(box, color, start, dur, self.rnd, alpha))


    def fill(self, polys, start, color=BLUE, dur=None, alpha=150):
        return self._add(Fill(polys, color, start, dur, alpha))

    def person(self, cx, base, height, start, mood="happy", pose="stand", shirt=BLUE, hair="short", skin=SKIN,
               color=INK, dur=None, width=None):
        """Hand-drawn chibi character, feet on y=base, `height` px tall: outline -> colour -> face.
        mood: happy sad shock think angry worried neutral. pose: stand point_r point_l arms_up hands_hip think
        shrug hold wave. hair: short long bun none. Returns anchors (head, hand_l, hand_r, top, end)."""
        assert mood in MOODS and pose in POSES, (mood, pose)
        h = height
        w = width or max(5, round(h * 0.016))
        r = 0.165 * h
        hx, hy = cx, base - h + r
        sy = hy + r + 0.03 * h
        hip = base - 0.34 * h
        shw, hipw = 0.15 * h, 0.12 * h
        torso = [(cx - hipw, hip), (cx - shw, sy + 0.06 * h), (cx - shw + 0.05 * h, sy), (cx + shw - 0.05 * h, sy),
                 (cx + shw, sy + 0.06 * h), (cx + hipw, hip), (cx - hipw, hip)]
        head = _ellipse(hx, hy, r, r * 1.02, 40, -1.9, -1.9 + 2 * math.pi * 1.04)
        legs = [[(cx - 0.06 * h, hip), (cx - 0.075 * h, base), (cx - 0.14 * h, base)],
                [(cx + 0.06 * h, hip), (cx + 0.075 * h, base), (cx + 0.14 * h, base)]]
        kinds = _POSE_ARMS[pose]
        arms, hands = [], []
        for side, kind in zip((-1, 1), kinds):
            sh = (cx + side * (shw - 0.02 * h), sy + 0.04 * h)
            el, hand = _arm(kind, side, sh, h, (hx, hy, r), (cx + side * hipw, hip))
            arms.append([sh, el, hand])
            hands.append(hand)
            arms.append(_ellipse(hand[0], hand[1], 0.028 * h, 0.028 * h, 12))
        total = dur or None
        out = self.strokes([head, torso] + legs, start, None if total is None else total * 0.4, w, color)
        t = out.end
        fills = []
        if skin:
            fills.append(self.fill([head[:-1]], t, skin, 0.25, alpha=200))
        if shirt:
            fills.append(self.fill([torso], t + 0.1, shirt, 0.3, alpha=170))
        hp = _hair(hair, hx, hy, r)
        if hp:
            fills.append(self.fill(hp, t + 0.2, HAIR, 0.25, alpha=235))
        t = max(f.end for f in fills) if fills else t
        t = self.strokes(arms, t, None if total is None else total * 0.2, w, color).end   # arms over the shirt
        face, blue = _face(mood, hx, hy, r)
        fe = self.strokes(face, t, None if total is None else total * 0.2, max(4, w - 1), color, wobble=0.5)
        end = fe.end
        if mood == "happy":
            self.fill([_ellipse(hx + sx * 0.6 * r, hy + 0.3 * r, 0.14 * r, 0.08 * r, 16) for sx in (-1, 1)], end,
                      (240, 120, 130), 0.2, alpha=120)
        if blue:
            end = self.strokes(blue, end, 0.3, max(4, w - 1), BLUE, wobble=0.3).end
            self.fill([p[:-1] for p in blue], end, (150, 200, 245), 0.15, alpha=220)
        return Person(head=(hx, hy, r), hand_l=hands[0], hand_r=hands[1], top=(hx, hy - r),
                      bbox=(cx - 0.4 * h, base - h, cx + 0.4 * h, base), end=self.end)

    def stick(self, cx, base, height, start, pose="stand", mood="happy", accent=ORANGE, color=INK, dur=None,
              look=None, seed=None, drawn=True):
        """Animated stick-figure host (the channel mascot), feet on y=base, `height` px tall. The pen draws it, then
        it breathes/blinks/sways. Chain s.act(t, pose=, mood=, look=), s.walk(t, to_x), s.jump(t) on the result;
        s.head_at(t) -> (x, y, r) and s.hand_at(t, side) place bubbles/props. drawn=False: it is simply there.
        poses: see STICK_POSES; moods: see STICK_MOODS.""" 
        seed = len(self.items) + 1 if seed is None else seed
        return self._add(Stick(cx, base, height, start, pose, mood, accent, color, dur, look, seed, drawn))

    def peep(self, name, cx, base, height, start, dur=None, color=INK, flip=False):
        """Open Peeps bust (e.g. "peep-11"; pick by mood/pose from assets/people/open-peeps/catalog.json).
        Returns Person(head, top, bbox, end) so bubbles and stickers can be placed against it."""
        el = self._add(Peep(name, cx, base, height, start, dur, color, flip))
        x0, y0, x1, y1 = el.box
        hx = cx + (-0.04 if flip else 0.04) * (x1 - x0)
        return Person(head=(hx, y0 + 0.2 * height, 0.17 * height), top=(hx, y0), bbox=el.box, end=el.end,
                      hand_l=None, hand_r=None)

    def speech(self, x, y, s, start, tail, size=56, color=INK, think=False, width=6, align="center"):
        """Hand-drawn speech (or thought, think=True) bubble with handwritten text, tail pointing at `tail`."""
        f = hand_font(size)
        a, b_, c, e = f.getbbox(s)
        tw, th = c - a, e - b_
        px, py = 30, 22
        x0 = x - tw / 2 - px if align == "center" else x - px
        x1, y0 = x0 + tw + 2 * px, y
        y1 = y0 + th + 2 * py
        rad = min(26, (y1 - y0) / 2)
        path = []
        for (qx, qy, a0) in ((x1 - rad, y0 + rad, -math.pi / 2), (x1 - rad, y1 - rad, 0),
                             (x0 + rad, y1 - rad, math.pi / 2), (x0 + rad, y0 + rad, math.pi)):
            path += _ellipse(qx, qy, rad, rad, 6, a0, a0 + math.pi / 2)
        path.append(path[0])
        tx, ty = tail
        bx = min(max(tx, x0 + rad + 30), x1 - rad - 30)
        polys = [path]
        if think:
            for k, rr in enumerate((14, 10, 7)):
                u = (k + 1) / 3.5
                polys.append(_ellipse(bx + (tx - bx) * u, y1 + (ty - y1) * u, rr, rr, 12))
        bg = self.fill([path[:-1]], start, PAPER, 0.12, alpha=255)
        if not think:
            gap = [(bx - 22, y1), (tx, ty), (bx + 22, y1)]
            self.fill([gap], start, PAPER, 0.12, alpha=255)
            polys.append(gap)
        outline = self.strokes(polys, bg.end, None, width, color, wobble=0.8)
        el = self.text(x0 + px, y0 + py, s, size, outline.end, color=color)
        return el

    def sticker(self, kind, cx, cy, start, size=150, color=RED, shape="burst", font=64, rot=-6, pop=0.35,
                until=None, bob=4):
        """Coloured die-cut sticker that pops in (overshoot) and floats gently; the pen ignores it.
        kind: 'face:<happy|laugh|love|shock|sad|angry|think|cool|money|neutral>', 'icon:<tabler>', 'text:<words>'
        (shape burst|pill|tag, `font` px), 'heart', 'star', 'check', 'cross', '!', '?'. until = pop-out time."""
        if kind.startswith("text:"):
            assert font >= fk.MIN_FONT, (kind, font)
        st = Sticker(kind, cx, cy, size, start, color, shape, font, rot, pop, until, bob)
        self.live.append(st)
        sp = sticker_sprite(*st.key)
        box = (cx - sp.width / 2, cy - sp.height / 2 - bob, cx + sp.width / 2, cy + sp.height / 2 + bob)
        if kind.startswith("text:"):
            self.audit.append((kind[5:], font, box))
        m = 0.12 * min(sp.width, sp.height)   # transparent corners / soft shadow
        st.box = (box[0] + m, box[1] + m, box[2] - m, box[3] - m)
        return st

    def overlaps(self):
        """Stickers covering handwriting while both are visible (stickers float above all ink)."""
        bad = []
        for st in self.live:
            gone = st.until + 0.25 if st.until is not None else 1e9
            for s, ink, t0 in self.texts:
                if t0 < gone and not (st.box[2] <= ink[0] or ink[2] <= st.box[0] or st.box[3] <= ink[1] or ink[3] <= st.box[1]):
                    bad.append((st.kind, s))
        return bad

    def pop_times(self, offset=0.0):
        return [st.start + offset for st in self.live]

    @property
    def end(self):
        return max([e.end for e in self.items] + [st.end for st in self.live], default=0.0)

    # -- rendering --
    def _paint(self, canvas, el, p):
        x0, y0, x1, y1 = el.bbox
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 <= x0 or y1 <= y0:
            return
        big = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS), (0, 0, 0, 0))
        el.draw(big, p, x0, y0)
        canvas.alpha_composite(big.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS), (x0, y0))

    def ink(self, t):
        """Transparent RGBA layer with everything drawn up to time t (finished elements cached)."""
        done = tuple(k for k, e in enumerate(self.items) if e.end <= t and not getattr(e, "animated", False))
        if done != self._cache_key:
            if self._cache_key is not None and set(self._cache_key) <= set(done):
                base = self._cache.copy()
                todo = [k for k in done if k not in self._cache_key]
            else:
                base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                todo = list(done)
            for k in todo:
                self._paint(base, self.items[k], 1.0)
            self._cache_key, self._cache = done, base
        im = self._cache.copy()
        for k, e in enumerate(self.items):
            if k not in done and e.start <= t:
                e.now = t
                self._paint(im, e, e.progress(t))
        for st in self.live:
            st.paste(im, t)
        return im

    def pen(self, t, travel=0.9, park=(W + 260, H + 220)):
        """Pen tip position at t, or None when parked off-screen."""
        active = [e for e in self.items if e.start <= t < e.end]
        if active:
            e = active[-1]
            return e.tip(e.progress(t))
        past = [e for e in self.items if e.end <= t]
        future = [e for e in self.items if e.start > t]
        a = past and max(past, key=lambda e: e.end)
        b = future and min(future, key=lambda e: e.start)
        pa = a.tip(1.0) if a else park
        pb = b.first_point() if b else park
        ta = a.end if a else -1e9
        tb = b.start if b else 1e9
        if tb - ta <= 2 * travel:
            u = fk.smooth((t - ta) / max(1e-6, tb - ta))
            return _lift(pa, pb, u)
        if t - ta < travel:
            return _lift(pa, park, fk.smooth((t - ta) / travel))
        if tb - t < travel:
            return _lift(park, pb, fk.smooth(1 - (tb - t) / travel))
        return None


def _lift(a, b, u):
    x = a[0] + (b[0] - a[0]) * u
    y = a[1] + (b[1] - a[1]) * u - math.sin(math.pi * u) * min(60, math.dist(a, b) * 0.15)
    return x, y


# ---------- pen sprite ----------
@lru_cache(None)
def pen_sprite(color=INK, length=520, thick=58, angle=-38):
    """Marker pen pointing down-left; returns (RGBA image, tip offset inside it)."""
    s = 3
    Lp, T = length * s, thick * s
    im = Image.new("RGBA", (Lp + 40 * s, T + 40 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y0, y1 = 20 * s, 20 * s + T
    cy = (y0 + y1) / 2
    tip_len, cone_len = 26 * s, 70 * s
    x_tip = 6 * s
    # felt tip
    d.polygon([(x_tip, cy), (x_tip + tip_len, cy - T * 0.16), (x_tip + tip_len, cy + T * 0.16)], fill=color + (255,))
    # cone (grey plastic)
    xc = x_tip + tip_len
    d.polygon([(xc, cy - T * 0.16), (xc + cone_len, y0 + T * 0.06), (xc + cone_len, y1 - T * 0.06), (xc, cy + T * 0.16)], fill=(150, 154, 160, 255))
    # barrel with vertical shading (white plastic)
    xb = xc + cone_len
    xe = Lp
    for k in range(T):
        v = k / T
        shade = 0.72 + 0.28 * math.sin(math.pi * min(1, v * 1.15))
        c = tuple(int(244 * shade) for _ in range(3))
        d.line([(xb, y0 + k), (xe - 30 * s, y0 + k)], fill=c + (255,))
    # colour band + end cap in ink colour
    band = xb + (xe - xb) * 0.55
    for k in range(T):
        v = k / T
        shade = 0.65 + 0.35 * math.sin(math.pi * min(1, v * 1.15))
        c = tuple(int(ch * shade) for ch in color)
        d.line([(band, y0 + k), (band + 28 * s, y0 + k)], fill=c + (255,))
        d.line([(xe - 120 * s, y0 + k), (xe, y0 + k)], fill=c + (255,))
    d.rounded_rectangle((xe - 40 * s, y0, xe + 10 * s, y1), 18 * s, fill=None)
    # outline for definition
    d.line([(xb, y0), (xe, y0)], fill=(60, 60, 64, 120), width=s * 2)
    d.line([(xb, y1), (xe, y1)], fill=(60, 60, 64, 160), width=s * 2)
    im = im.resize((im.width // s, im.height // s), Image.Resampling.LANCZOS)
    tip = (x_tip / s, cy / s)
    rot = im.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    # rotate tip offset (PIL rotates counter-clockwise for positive angle around centre)
    cx0, cy0 = im.width / 2, im.height / 2
    a = math.radians(angle)
    dx, dy = tip[0] - cx0, tip[1] - cy0
    rx, ry = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    tip_r = (rot.width / 2 + rx, rot.height / 2 + ry)
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    shadow.putalpha(rot.getchannel("A").point(lambda v: v * 0.22))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    return rot, shadow, tip_r


def draw_pen(im, pos, t=0.0, color=INK):
    if pos is None:
        return im
    sprite, shadow, tip = pen_sprite(color)
    x, y = pos
    x += 1.5 * math.sin(t * 9.0)
    y += 1.5 * math.cos(t * 7.0)
    _paste(im, shadow, x - tip[0] + 22, y - tip[1] + 30)
    _paste(im, sprite, x - tip[0], y - tip[1])
    return im


def _paste(im, sp, x, y):
    x, y = int(round(x)), int(round(y))
    if x >= im.width or y >= im.height or x + sp.width <= 0 or y + sp.height <= 0:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(sp.width, im.width - x), min(sp.height, im.height - y)
    im.alpha_composite(sp.crop((cx0, cy0, cx1, cy1)), (x + cx0, y + cy0))


# ---------- composition ----------
def compose(board, t, duration=None, pen=True):
    """Paper + ink + pen at board-local time t, with a slow push-in over the board's duration."""
    im = paper().copy()
    im.alpha_composite(board.ink(t))
    if pen:
        draw_pen(im, board.pen(t), t)
    span = duration or max(board.end + 1.0, 4.0)
    z = 1 + board.drift * fk.smooth(t / span)
    if z > 1.0005:
        im = fk.zoom_image(im, z, board.anchor)
    return im


def scribble_track(intervals, duration, sr=48000, seed=5, level_db=-36):
    """Synthetic felt-marker sound (band-passed noise, stroke-rate amplitude flutter) under every drawing interval.
    Returns float32 stereo array at about level_db dBFS RMS while drawing (default -36: 6 dB quieter than the old -30,
    user asked for a softer pen 2026-10-22); mix it ~-27 dB under the voice. Band 1200-4500 Hz keeps the highs soft."""
    import numpy as np
    from scipy import signal
    n = int(duration * sr)
    rng = np.random.default_rng(seed)
    env = np.zeros(n, np.float32)
    for a, b, soft in intervals:
        i0, i1 = max(0, int(a * sr)), min(n, int(b * sr))
        if i1 - i0 < sr * 0.05:
            continue
        L = i1 - i0
        t = np.arange(L) / sr
        flutter = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * rng.uniform(5.5, 8.5) * t + rng.uniform(0, 6)))
        fade = np.minimum(1, np.minimum(t / 0.03, (L / sr - t) / 0.06))
        env[i0:i1] = np.maximum(env[i0:i1], flutter * fade * (0.6 if soft else 1.0))
    noise = rng.standard_normal((n, 2)).astype(np.float32)
    sos = signal.butter(4, [1200, 4500], btype="band", fs=sr, output="sos")
    noise = signal.sosfilt(sos, noise, axis=0)
    noise /= np.sqrt(np.mean(noise ** 2)) + 1e-9
    return (noise * env[:, None] * 10 ** (level_db / 20)).astype(np.float32)


def pop_track(times, duration, sr=48000, seed=9):
    """Soft 'bloop' for every sticker pop (rising sine + click), ~-20 dBFS peak; mix about -10 dB under the voice."""
    import numpy as np
    n = int(duration * sr)
    out = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(seed)
    L = int(0.12 * sr)
    t = np.arange(L) / sr
    for t0 in times:
        f0 = rng.uniform(380, 520)
        ph = 2 * np.pi * np.cumsum(f0 * (1 + 1.6 * t / t[-1])) / sr
        env = np.minimum(1, t / 0.004) * np.exp(-t / 0.035)
        x = (np.sin(ph) * env + 0.25 * rng.standard_normal(L) * np.exp(-t / 0.004)).astype(np.float32)
        i0 = int(t0 * sr)
        if 0 <= i0 < n:
            seg = x[: n - i0] * 10 ** (-20 / 20)
            out[i0:i0 + len(seg)] += seg[:, None]
    return out


def audit_into(T, board):
    """Add the board's text boxes to the frame_kit audit; also fails fast if a sticker covers handwriting."""
    bad = board.overlaps()
    assert not bad, ("sticker covers text", bad)
    T.audit.extend(board.audit)


def _demo(folder):
    folder = Path(folder)
    T = fk.Typesetter()
    b = Board(seed=3)
    b.text(960, 120, "Lương 10 triệu", 120, start=0.2, align="center")
    b.underline(640, 1280, 270, start=1.3, color=RED, width=9)
    b.icon("home", 520, 560, 300, start=1.8)
    b.icon("bowl", 960, 560, 300, start=2.8)
    b.icon("motorbike", 1400, 560, 300, start=3.8, color=BLUE)
    b.highlight((380, 760, 680, 840), start=4.9)
    b.text(530, 770, "3,6 triệu", 64, start=5.2, align="center", color=RED)
    b.circle((1260, 400, 1540, 720), start=5.9, color=RED, width=7)
    dur = 7.5

    def frame(t):
        audit_into(T, b)
        return compose(b, t, dur).convert("RGB")

    print(fk.preview(frame, [0.6, 1.5, 2.4, 4.2, 5.5, 7.4], T, folder))
    fk.render(frame, dur, None, folder / "whiteboard-demo.mp4", T, fps=30, overwrite=True)


def _demo_people(folder):
    folder = Path(folder)
    T = fk.Typesetter()
    b = Board(seed=4)
    b.text(960, 70, "Ngày lương về", 96, start=0.2, align="center")
    a = b.person(420, 900, 560, start=0.9, mood="happy", pose="arms_up", shirt=GREEN)
    b.sticker("icon:cash-banknote", 640, 330, a.end + 0.1, size=150, color=GREEN, rot=8)
    b.sticker("face:money", 230, 360, a.end + 0.4, size=120, rot=-10)
    c = b.person(1000, 900, 560, start=a.end + 0.6, mood="shock", pose="shrug", shirt=ORANGE, hair="long")
    b.sticker("text:-5 TRIỆU", 1240, 330, c.end + 0.1, color=RED, font=60, rot=-7)
    d = b.person(1530, 900, 560, start=c.end + 0.6, mood="think", pose="think", shirt=BLUE, hair="bun")
    b.speech(1640, 200, "Mua nhà?", d.end + 0.1, tail=(d.head[0] - d.head[2] - 10, d.head[1] - d.head[2]), size=60, think=True)
    b.sticker("?", 1790, 620, d.end + 1.4, size=110, color=BLUE, rot=10)
    dur = b.end + 1.2
    print("demo duration", round(dur, 2))

    def frame(t):
        audit_into(T, b)
        return compose(b, t, dur).convert("RGB")

    print(fk.preview(frame, [1.6, a.end + 0.25, a.end + 1.2, c.end + 0.6, d.end + 0.6, dur - 0.1], T, folder))
    return b, dur, frame, T


def _demo_peeps(folder):
    folder = Path(folder)
    T = fk.Typesetter()
    b = Board(seed=6)
    b.text(960, 70, "Cuối tháng còn bao nhiêu?", 96, start=0.2, align="center")
    a = b.peep("peep-11", 360, 1000, 600, start=1.0)
    b.speech(430, 270, "Còn dư!", a.end + 0.1, tail=(a.head[0] + 40, a.head[1] - a.head[2]), size=60)
    b.sticker("face:happy", 640, 540, a.end + 0.5, size=120, rot=8)
    c = b.peep("peep-80", 930, 1000, 600, start=a.end + 0.9, flip=True)
    b.sticker("text:-5 TRIỆU", 1170, 380, c.end + 0.1, color=RED, font=60, rot=-7)
    d = b.peep("peep-46", 1520, 1000, 600, start=c.end + 0.9)
    b.speech(1530, 220, "Tính lại nào", d.end + 0.1, tail=(d.head[0], d.head[1] - d.head[2]), size=56, think=True)
    dur = b.end + 1.2
    print("demo duration", round(dur, 2))

    def frame(t):
        audit_into(T, b)
        return compose(b, t, dur).convert("RGB")

    print(fk.preview(frame, [1.6, a.end - 0.4, a.end + 1.0, c.end + 0.6, d.end - 0.5, dur - 0.1], T, folder))
    return b, dur, frame, T


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--demo":
        _demo(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--demo-people":
        b, dur, frame, T = _demo_people(sys.argv[2])
        fk.render(frame, dur, None, Path(sys.argv[2]) / "people-demo.mp4", T, fps=30, overwrite=True)
    elif len(sys.argv) == 3 and sys.argv[1] == "--demo-peeps":
        b, dur, frame, T = _demo_peeps(sys.argv[2])
        fk.render(frame, dur, None, Path(sys.argv[2]) / "peeps-demo.mp4", T, fps=30, overwrite=True)
    else:
        print(__doc__)
