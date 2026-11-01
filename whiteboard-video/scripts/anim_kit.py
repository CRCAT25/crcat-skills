"""Living props for the whiteboard: things that move every frame on top of the ink (the pen never draws them).
Vehicles roll in with spinning wheels, bounce and cartoon exhaust puffs (xe xăng) or little sparks (xe điện);
rubber stamps slam down and shake the board; rumor chat bubbles slide in; a boom barrier drops; clocks spin;
tear-off calendars flip; a cà vẹt card flips over; pins drop and ping; pointers hop.

Usage: b = ABoard(seed) (scenes.build does it), then b.anim(Vehicle(...)), b.stamp(...), b.chat(...).
All coordinates are 1920x1080 screen px.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

import whiteboard as wb

SS = 2
INK = wb.INK
LINE = (24, 24, 28)
WHITE = (255, 255, 255)
TIRE = (52, 52, 58)
RIM = (205, 208, 214)
SMOKE = (214, 214, 220)
GLASS = (196, 226, 246)
HELMET = (236, 92, 70)


def clamp(u):
    return max(0.0, min(1.0, u))


def ease(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def back_out(u, k=1.9):
    u = clamp(u) - 1
    return 1 + (k + 1) * u ** 3 + k * u ** 2


# ---------- tiny vector painter: record shapes in screen px, then draw them supersampled in their own bbox ----------
class Painter:
    def __init__(self):
        self.ops = []
        self.box = [1e9, 1e9, -1e9, -1e9]

    def _grow(self, pts, pad):
        for x, y in pts:
            b = self.box
            b[0], b[1], b[2], b[3] = min(b[0], x - pad), min(b[1], y - pad), max(b[2], x + pad), max(b[3], y + pad)

    def poly(self, pts, fill=None, line=LINE, w=6):
        self.ops.append(("poly", pts, fill, line, w))
        self._grow(pts, w + 2)

    def line(self, pts, color=LINE, w=6):
        self.ops.append(("line", pts, color, w))
        self._grow(pts, w + 2)

    def circle(self, cx, cy, r, fill=None, line=LINE, w=6):
        self.ops.append(("circle", (cx, cy, r), fill, line, w))
        self._grow([(cx - r, cy - r), (cx + r, cy + r)], w + 2)

    def text(self, x, y, s, size, color=INK):
        self.ops.append(("text", (x, y), s, size, color))
        f = wb.hand_font(size)
        a, b_, c, e = f.getbbox(s, anchor="mm")
        self._grow([(x + a, y + b_), (x + c, y + e)], 4)

    def paste_to(self, im):
        if not self.ops:
            return
        x0, y0 = int(max(0, self.box[0])), int(max(0, self.box[1]))
        x1, y1 = int(min(im.width, self.box[2] + 1)), int(min(im.height, self.box[3] + 1))
        if x1 <= x0 or y1 <= y0:
            return
        big = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)

        def tr(pts):
            return [((x - x0) * SS, (y - y0) * SS) for x, y in pts]

        for op in self.ops:
            kind = op[0]
            if kind == "poly":
                _, pts, fill, line, w = op
                q = tr(pts)
                if fill is not None:
                    d.polygon(q, fill=fill)
                if line is not None and w > 0:
                    d.line(q + q[:1], fill=line, width=int(w * SS), joint="curve")
            elif kind == "line":
                _, pts, color, w = op
                q = tr(pts)
                d.line(q, fill=color, width=int(w * SS), joint="curve")
                r = w * SS / 2
                for x, y in (q[0], q[-1]):
                    d.ellipse((x - r, y - r, x + r, y + r), fill=color)
            elif kind == "circle":
                _, (cx, cy, r), fill, line, w = op
                (cx, cy), = tr([(cx, cy)])
                r *= SS
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill,
                          outline=line if (line is not None and w > 0) else None, width=int(w * SS))
            elif kind == "text":
                _, (x, y), s, size, color = op
                (x, y), = tr([(x, y)])
                d.text((x, y), s, font=wb.hand_font(int(size * SS)), fill=color, anchor="mm")
        small = big.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
        im.alpha_composite(small, (x0, y0))


class Anim:
    start = 0.0
    until = None

    def visible(self, t):
        return t >= self.start and (self.until is None or t < self.until)

    def paste(self, im, t):
        raise NotImplementedError


# ---------- board with a living layer + stamp shake ----------
class ABoard(wb.Board):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.anims = []
        self.shakes = []

    def anim(self, a):
        self.anims.append(a)
        return a

    def ink(self, t):
        live, self.live = self.live, []
        try:
            im = super().ink(t)
        finally:
            self.live = live
        for a in self.anims:
            if a.visible(t):
                a.paste(im, t)
        for st in live:
            st.paste(im, t)
        dx = dy = 0.0
        for t0, amp in self.shakes:
            u = t - t0
            if 0 <= u < 0.32:
                k = amp * (1 - u / 0.32)
                dx += k * math.sin(u * 95)
                dy += k * 0.6 * math.cos(u * 77)
        if abs(dx) + abs(dy) > 0.3:
            out = Image.new("RGBA", im.size, (0, 0, 0, 0))
            out.alpha_composite(im, (int(round(dx)), int(round(dy))))
            im = out
        return im

    # -- convenience --
    def stamp(self, s, cx, cy, start, color=wb.RED, font=96, rot=-8, until=None, shake=9):
        st = Stamp(s, cx, cy, start, color, font, rot, until)
        self.live.append(st)
        self.audit.append((s, font, st.box))
        self.shakes.append((start + Stamp.DROP, shake))
        return st

    def chat(self, s, x, y, start, name="", side=-1, size=48, until=None, width=None):
        st = Chat(s, x, y, start, name, side, size, until, width)
        self.live.append(st)
        self.audit.append((s, size, st.box))
        if name:
            self.audit.append((name, 40, st.box))
        return st


# ---------- motion along x ----------
class Track:
    """Keyframes [(t, x), ...]: eased move between consecutive keys, parked before the first / after the last."""

    def __init__(self, keys):
        self.keys = sorted(keys)

    def x(self, t):
        k = self.keys
        if t <= k[0][0]:
            return k[0][1]
        for (t0, x0), (t1, x1) in zip(k, k[1:]):
            if t < t1:
                return x0 + (x1 - x0) * ease((t - t0) / max(1e-6, t1 - t0))
        return k[-1][1]

    def v(self, t, h=1 / 60):
        return (self.x(t + h) - self.x(t - h)) / (2 * h)

    def a(self, t, h=1 / 30):
        return (self.v(t + h) - self.v(t - h)) / (2 * h)


# ---------- vehicles ----------
SHAPES = {
    # body polygons in local units: u forward, v up from the ground; wheels (u, radius)
    "scooter": dict(
        wheels=[(-82, 30), (88, 30)],
        body=[(-130, 66), (-122, 100), (-96, 118), (-44, 122), (-24, 104), (-22, 70), (34, 66), (52, 150),
              (74, 152), (96, 70), (114, 52), (104, 40), (-60, 38), (-110, 40)],
        seat=[(-112, 118), (-96, 132), (-40, 134), (-28, 120)],
        bar=[(62, 152), (58, 178)], grip=(52, 180), lamp=(92, 128), pipe=[(-60, 30), (-128, 36)],
        hip=(-62, 136), foot=(18, 70), shoulder=(-46, 220), head=(-38, 270), hr=36),
    "car": dict(
        wheels=[(-118, 36), (122, 36)],
        body=[(-190, 40), (-196, 104), (-150, 112), (-96, 176), (70, 178), (128, 116), (190, 106), (198, 44)],
        windows=[[(-140, 116), (-92, 166), (-18, 166), (-18, 116)], [(-4, 116), (-4, 166), (62, 166), (114, 116)]],
        lamp=(186, 92), pipe=[(-170, 30), (-210, 30)]),
    "bus": dict(
        wheels=[(-180, 38), (176, 38)],
        body=[(-280, 40), (-280, 250), (270, 250), (290, 200), (290, 40)],
        windows=[[(-250 + 92 * k, 150), (-250 + 92 * k, 224), (-182 + 92 * k, 224), (-182 + 92 * k, 150)]
                 for k in range(5)] + [[(212, 120), (212, 226), (268, 226), (282, 180), (282, 120)]],
        lamp=(280, 80), pipe=[(-268, 30), (-300, 30)]),
    "truck": dict(
        wheels=[(-150, 38), (40, 38), (166, 38)],
        body=[(-240, 40), (-240, 230), (100, 230), (100, 40)],
        cab=[(110, 40), (110, 180), (190, 180), (226, 120), (230, 40)],
        windows=[[(124, 120), (124, 168), (184, 168), (212, 120)]],
        lamp=(222, 70), pipe=[(-230, 30), (-266, 30)]),
}


class Vehicle(Anim):
    """A rolling vehicle. kind: scooter | app (scooter + delivery box) | ebike (scooter, no smoke, sparks) |
    car | bus | truck. keys = [(t, x), ...] (centre x over time), ground = y of the road, s = scale,
    face = +1 right / -1 left. Gas vehicles puff exhaust while visible (more when moving).
    label: words painted on the side (bus/truck). rider: shirt colour or None."""

    def __init__(self, kind, keys, ground, start, s=1.0, face=1, color=(74, 136, 226), rider=(246, 196, 54),
                 helmet=HELMET, label=None, label_size=56, until=None, gas=None, seed=1, mood="happy"):
        self.kind, self.track, self.ground, self.start, self.s, self.face = kind, Track(keys), ground, start, s, face
        self.color, self.rider, self.helmet, self.label, self.label_size, self.until = (
            color, rider, helmet, label, label_size, until)
        self.gas = (kind != "ebike") if gas is None else gas
        self.shape = SHAPES["scooter" if kind in ("app", "ebike") else kind]
        self.seed = seed
        self.mood = mood
        self.moods = []
        self.phase = random.Random(seed).uniform(0, 6.28)

    def act(self, t, mood):
        self.moods.append((t, mood))
        return self

    def mood_at(self, t):
        m = self.mood
        for t0, mm in sorted(self.moods):
            if t >= t0:
                m = mm
        return m

    def x_at(self, t):
        return self.track.x(t)

    def top_at(self, t):
        """Screen point just above the rider's head (or roof): for speech bubbles."""
        sh = self.shape
        v = (sh["head"][1] + sh["hr"] + 10) if "head" in sh and self.rider else max(p[1] for p in sh["body"]) + 10
        u = sh["head"][0] if "head" in sh and self.rider else 0
        return self.x_at(t) + self.face * u * self.s, self.ground - v * self.s

    # local -> screen
    def _P(self, t, pitch, bounce):
        X, Y, s, f = self.track.x(t), self.ground, self.s, self.face
        c, sn = math.cos(pitch), math.sin(pitch)

        def P(u, v, body=True):
            if body:
                u, v = u * c - v * sn, u * sn + v * c
                v += bounce
            return X + f * u * s, Y - v * s
        return P

    def _state(self, t):
        v = self.track.v(t)
        a = self.track.a(t)
        moving = abs(v) > 8
        sp = min(1.0, abs(v) / 500)
        bounce = (2.2 * sp * abs(math.sin(t * 17 + self.phase)) + (0.8 * math.sin(t * 46) if self.gas else 0.0))
        pitch = max(-0.05, min(0.05, -0.00004 * a * self.face * (1 if v * self.face >= 0 else -1)))
        return v, moving, bounce, pitch

    def paste(self, im, t):
        p = Painter()
        v, moving, bounce, pitch = self._state(t)
        P = self._P(t, pitch, bounce)
        sh = self.shape
        s = self.s
        lw = max(3.0, 6 * s)

        # exhaust first (behind the body)
        if self.gas:
            self._smoke(p, t)
        else:
            self._sparks(p, t, P)
        # speed lines
        if abs(v) > 260:
            k = min(1.0, (abs(v) - 260) / 600)
            back = min(u for u, _ in sh["body"]) - 20
            for j, hv in enumerate((60, 110, 160)):
                L = (60 + 90 * k) * (1 - 0.2 * j)
                a0 = P(back - 10 - 18 * j, hv, False)
                a1 = P(back - 10 - 18 * j - L, hv, False)
                p.line([a0, a1], color=(150, 150, 158), w=max(3, 5 * s))
        # body
        if self.kind == "app":
            box = [(-160, 118), (-160, 210), (-74, 210), (-74, 118)]
            p.poly([P(*q) for q in box], fill=(64, 168, 104), w=lw)
            p.line([P(-150, 168), P(-84, 168)], color=WHITE, w=max(3, 5 * s))
        if "cab" in sh:
            p.poly([P(*q) for q in sh["cab"]], fill=self.color, w=lw)
        p.poly([P(*q) for q in sh["body"]], fill=(self.color if self.kind != "truck" else (238, 236, 228)), w=lw)
        for win in sh.get("windows", []):
            p.poly([P(*q) for q in win], fill=GLASS, w=max(3, 4.5 * s))
        if "seat" in sh:
            p.line([P(*q) for q in sh["seat"]], color=LINE, w=max(5, 11 * s))
        if self.kind == "ebike":
            bolt = [(-82, 100), (-96, 76), (-84, 78), (-92, 56), (-70, 84), (-82, 82), (-74, 100)]
            p.poly([P(*q) for q in bolt], fill=(246, 196, 54), w=max(2, 3 * s))
        if "lamp" in sh:
            lx, ly = P(*sh["lamp"])
            p.circle(lx, ly, 9 * s, fill=(255, 236, 150), w=max(2, 3.5 * s))
        if self.label:
            lab_v = 92 if self.kind == "bus" else 140
            lx, ly = P(-20 if self.kind == "bus" else -70, lab_v)
            p.text(lx, ly, self.label, self.label_size * s, color=(255, 255, 255) if self.kind == "bus" else INK)
        if "bar" in sh:
            p.line([P(*q) for q in sh["bar"]], color=LINE, w=lw)
            gx, gy = sh["grip"]
            p.line([P(gx - 8, gy), P(gx + 18, gy - 2)], color=LINE, w=max(4, 8 * s))
        if self.kind in ("scooter", "app", "ebike") and self.rider:
            self._rider(p, t, P, lw)
        # wheels last (rotate with distance)
        x = self.track.x(t)
        for wu, wr in sh["wheels"]:
            cx, cy = P(wu, wr, False)
            cy -= 0
            R = wr * s
            p.circle(cx, cy, R, fill=TIRE, w=lw)
            p.circle(cx, cy, R * 0.58, fill=RIM, w=max(2, 3 * s))
            ang = (x - self.track.keys[0][1]) / max(1, R) * self.face
            for j in range(5):
                a = ang + j * 2 * math.pi / 5
                p.line([(cx, cy), (cx + R * 0.52 * math.cos(a), cy + R * 0.52 * math.sin(a))], color=TIRE,
                       w=max(2, 3.5 * s))
            p.circle(cx, cy, R * 0.16, fill=TIRE, w=0)
        p.paste_to(im)

    def _rider(self, p, t, P, lw):
        sh = self.shape
        hip, foot, shl, head, hr = sh["hip"], sh["foot"], sh["shoulder"], sh["head"], sh["hr"]
        knee = (foot[0] - 4, hip[1] - 8)
        s = self.s
        p.line([P(*hip), P(*knee), P(*foot)], color=LINE, w=max(4, 8 * s))
        torso = [(hip[0] - 22, hip[1]), (shl[0] - 26, shl[1]), (shl[0] + 26, shl[1] + 4), (hip[0] + 24, hip[1] - 4)]
        p.poly([P(*q) for q in torso], fill=self.rider, w=lw)
        gx, gy = sh["grip"]
        elbow = ((shl[0] + gx) / 2 + 6, (shl[1] + gy) / 2 - 18)
        p.line([P(shl[0] + 10, shl[1] - 6), P(*elbow), P(gx, gy)], color=LINE, w=max(4, 8 * s))
        hx, hy = P(*head)
        R = hr * s
        p.circle(hx, hy, R, fill=WHITE, w=lw)
        # helmet: top cap + strap
        cap = [P(head[0] + hr * 1.06 * math.cos(a), head[1] + hr * 1.06 * math.sin(a))
               for a in [math.pi * (0.02 + 0.96 * k / 16) for k in range(17)]]
        cap += [P(head[0] - hr * 1.06, head[1] + 2), P(head[0] + hr * 1.06, head[1] + 2)][::-1][:0]
        p.poly(cap, fill=self.helmet, w=lw)
        p.line([P(head[0] + hr * 0.6, head[1] + 2), P(head[0] + hr * 1.25, head[1] - 2)], color=LINE, w=max(3, 5 * s))
        # face looks forward
        mood = self.mood_at(t)
        blink = (t * 0.7 + self.phase) % 3.1 < 0.12
        ex, ey = P(head[0] + hr * 0.42, head[1] - hr * 0.22)
        if blink:
            p.line([(ex - 5 * s, ey), (ex + 5 * s, ey)], color=LINE, w=max(2, 3.5 * s))
        elif mood == "shock":
            p.circle(ex, ey, 7 * s, fill=WHITE, w=max(2, 3 * s))
            p.circle(ex, ey, 3.5 * s, fill=LINE, w=0)
        else:
            p.circle(ex, ey, 4.5 * s, fill=LINE, w=0)
        mx, my = P(head[0] + hr * 0.5, head[1] - hr * 0.55)
        f = self.face
        if mood == "shock":
            p.circle(mx, my, 6 * s, fill=(150, 40, 44), w=max(2, 3 * s))
        elif mood == "sad":
            p.line([(mx - f * 10 * s, my + 2 * s), (mx, my - 4 * s), (mx + f * 8 * s, my + 2 * s)], color=LINE,
                   w=max(2, 3.5 * s))
        else:
            p.line([(mx - f * 10 * s, my - 3 * s), (mx, my + 4 * s), (mx + f * 9 * s, my - 4 * s)], color=LINE,
                   w=max(2, 3.5 * s))

    def _pipe_end(self, t):
        v, moving, bounce, pitch = self._state(t)
        P = self._P(t, pitch, bounce)
        return P(*self.shape["pipe"][-1])

    def _smoke(self, p, t):
        """Cartoon puffs: born at the pipe, drift back and up, swell then shrink away (no alpha needed)."""
        life = 1.15
        dt = 0.11
        t0 = max(self.start, t - life)
        k0 = math.ceil((t0 - self.start) / dt)
        k1 = math.floor((t - self.start) / dt)
        blobs = []
        for k in range(k0, k1 + 1):
            tb = self.start + k * dt
            sp = abs(self.track.v(tb))
            if sp < 8 and k % 3:      # idling: fewer puffs
                continue
            u = (t - tb) / life
            if not 0 <= u < 1:
                continue
            rnd = random.Random(self.seed * 9973 + k)
            bx, by = self._pipe_end(tb)
            drift = -self.face * (40 + 0.18 * sp) * (t - tb) * self.s
            x = bx + drift + rnd.uniform(-6, 6) * self.s
            y = by - (34 + rnd.uniform(0, 30)) * (t - tb) * self.s - 6 * self.s
            r = (8 + 18 * rnd.uniform(0.7, 1.1)) * self.s * math.sin(math.pi * min(1.0, u * 1.15)) ** 0.7
            if r > 1.2:
                # each puff = a little cloud of 3 lumps
                blobs += [(x, y, r), (x + 0.55 * r, y + 0.25 * r, 0.7 * r), (x - 0.5 * r, y + 0.3 * r, 0.62 * r)]
        ow = max(2, 3.5 * self.s)
        for x, y, r in blobs:      # outline pass, then fill pass -> one merged cloud with a single outline
            p.circle(x, y, r + ow, fill=(150, 150, 158), line=None, w=0)
        for x, y, r in blobs:
            p.circle(x, y, r, fill=SMOKE, line=None, w=0)

    def _sparks(self, p, t, P):
        """Electric: a tiny yellow zigzag spark near the back, flickering."""
        if (t * 2.3 + self.phase) % 1.0 < 0.22:
            bx, by = P(-128, 92)
            f = -self.face * self.s
            p.line([(bx, by), (bx + 16 * f, by - 10 * self.s), (bx + 8 * f, by - 14 * self.s),
                    (bx + 26 * f, by - 26 * self.s)], color=(246, 196, 54), w=max(3, 5 * self.s))


# ---------- rubber stamp ----------
@lru_cache(None)
def stamp_sprite(s, color, font, rot):
    S = 3
    f = wb.hand_font(font * S)
    a, b_, c, e = f.getbbox(s)
    tw, th = c - a, e - b_
    w, h = int(tw + 110 * S), int(th + 90 * S)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = 7 * S
    d.rounded_rectangle((lw, lw, w - lw, h - lw), radius=22 * S, outline=color, width=lw)
    d.rounded_rectangle((lw * 3.2, lw * 3.2, w - lw * 3.2, h - lw * 3.2), radius=14 * S, outline=color,
                        width=int(lw * 0.45))
    d.text((w / 2, h / 2), s, font=f, fill=color, anchor="mm", stroke_width=int(font * S * 0.04), stroke_fill=color)
    # worn ink: knock out small speckles
    rnd = random.Random(hash(s) & 0xFFFF)
    alpha = im.getchannel("A")
    da = ImageDraw.Draw(alpha)
    for _ in range(int(w * h / (S * S) / 900)):
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(1.0, 3.2) * S
        da.ellipse((x - r, y - r, x + r, y + r), fill=0)
    im.putalpha(alpha.point(lambda v: int(v * 0.9)))
    im = im.resize((w // S, h // S), Image.Resampling.LANCZOS)
    return im.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)


class Stamp(wb.Sticker):
    """Rubber stamp that slams down (big + faint -> full size), shakes the board, and stays (no bob)."""
    DROP = 0.17

    def __init__(self, s, cx, cy, start, color, font, rot, until):
        super().__init__("stamp:" + s, cx, cy, font, start, color, None, font, rot, self.DROP, until, 0)
        self.sprite = stamp_sprite(s, color, font, rot)
        sp = self.sprite
        m = 0.1 * min(sp.width, sp.height)
        self.box = (cx - sp.width / 2 + m, cy - sp.height / 2 + m, cx + sp.width / 2 - m, cy + sp.height / 2 - m)
        self.end = start + 0.3

    def paste(self, im, t):
        if t < self.start or (self.until is not None and t >= self.until + 0.25):
            return
        u = (t - self.start) / self.DROP
        if u < 1:
            sc = 2.3 - 1.3 * u * u
            al = 0.25 + 0.75 * u
        else:
            w = t - self.start - self.DROP
            sc = 1 - 0.06 * math.sin(min(1.0, w / 0.16) * math.pi) if w < 0.16 else 1.0
            al = 1.0
        if self.until is not None and t > self.until:
            al *= max(0.0, 1 - (t - self.until) / 0.25)
        sp = self.sprite
        if abs(sc - 1) > 1e-3:
            sp = sp.resize((max(1, int(sp.width * sc)), max(1, int(sp.height * sc))), Image.Resampling.BILINEAR)
        if al < 0.999:
            sp = sp.copy()
            sp.putalpha(sp.getchannel("A").point(lambda v: int(v * al)))
        wb._paste(im, sp, self.cx - sp.width / 2, self.cy - sp.height / 2)


# ---------- rumor chat bubble ----------
@lru_cache(None)
def chat_sprite(s, name, side, size, width):
    S = 3
    f = wb.hand_font(size * S)
    fn = wb.hand_font(40 * S)
    words, lines, cur = s.split(), [], ""
    maxw = (width or 760) * S
    for wd in words:
        trial = (cur + " " + wd).strip()
        if f.getlength(trial) > maxw and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    lines.append(cur)
    lh = size * 1.12 * S
    tw = max(f.getlength(ln) for ln in lines)
    av = 84 * S
    pad = 28 * S
    nh = 48 * S if name else 0
    bw, bh = tw + 2 * pad, len(lines) * lh + 2 * pad * 0.8 + nh
    W, H = int(bw + av + 30 * S), int(max(bh, av) + 14 * S)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bx0 = av + 22 * S if side < 0 else 4 * S
    ax = av / 2 + 2 * S if side < 0 else W - av / 2 - 2 * S
    # avatar: grey circle with a tiny head-and-shoulders
    ay = H - av / 2 - 4 * S
    d.ellipse((ax - av / 2, ay - av / 2, ax + av / 2, ay + av / 2), fill=(200, 206, 216), outline=LINE, width=3 * S)
    d.ellipse((ax - av * 0.17, ay - av * 0.3, ax + av * 0.17, ay + av * 0.04), fill=WHITE)
    d.pieslice((ax - av * 0.32, ay + av * 0.08, ax + av * 0.32, ay + av * 0.7), 180, 360, fill=WHITE)
    fill = (255, 255, 255) if side < 0 else (214, 232, 255)
    d.rounded_rectangle((bx0, 4 * S, bx0 + bw, 4 * S + bh), radius=34 * S, fill=fill, outline=(120, 124, 134),
                        width=4 * S)
    y = 4 * S + pad * 0.8
    if name:
        d.text((bx0 + pad, y), name, font=fn, fill=(90, 96, 110), anchor="la")
        y += nh
    for ln in lines:
        d.text((bx0 + pad, y), ln, font=f, fill=INK, anchor="la")
        y += lh
    return im.resize((W // S, H // S), Image.Resampling.LANCZOS)


class Chat(wb.Sticker):
    """Messenger-style bubble with an avatar; slides up + fades in (pop sound), x = left edge (side -1) or right
    edge (side +1), y = top."""

    def __init__(self, s, x, y, start, name, side, size, until, width):
        sp = chat_sprite(s, name, side, size, width)
        cx = x + sp.width / 2 if side < 0 else x - sp.width / 2
        super().__init__("chat:" + s, cx, y + sp.height / 2, size, start, None, None, size, 0, 0.3, until, 0)
        self.sprite = sp
        self.box = (cx - sp.width / 2, y, cx + sp.width / 2, y + sp.height)

    def paste(self, im, t):
        if t < self.start or (self.until is not None and t >= self.until + 0.25):
            return
        u = clamp((t - self.start) / 0.3)
        al = ease(u)
        if self.until is not None and t > self.until:
            al *= max(0.0, 1 - (t - self.until) / 0.25)
        dy = 36 * (1 - back_out(u))
        sp = self.sprite
        if al < 0.999:
            sp = sp.copy()
            sp.putalpha(sp.getchannel("A").point(lambda v: int(v * al)))
        wb._paste(im, sp, self.cx - sp.width / 2, self.cy - sp.height / 2 + dy)


# ---------- boom barrier ----------
class Barrier(Anim):
    """Post at (x, ground); arm points toward `side` (+1 right / -1 left), length L. Up until t_down, then
    drops with a bounce; red light blinks once down. t_up (optional) raises it again."""

    def __init__(self, x, ground, start, t_down, L=420, side=1, t_up=None, until=None):
        self.x, self.ground, self.start, self.t_down, self.L, self.side, self.t_up, self.until = (
            x, ground, start, t_down, L, side, t_up, until)

    def angle(self, t):
        up = math.radians(84)
        if t < self.t_down:
            return up
        if self.t_up is not None and t >= self.t_up:
            return up * ease((t - self.t_up) / 0.6)
        return up * (1 - back_out((t - self.t_down) / 0.45, 2.6))

    def paste(self, im, t):
        p = Painter()
        x, g = self.x, self.ground
        top = g - 150
        p.poly([(x - 16, g), (x - 16, top), (x + 16, top), (x + 16, g)], fill=(90, 92, 100), w=5)
        p.poly([(x - 40, g), (x - 40, g - 16), (x + 40, g - 16), (x + 40, g)], fill=(90, 92, 100), w=5)
        a = self.angle(t)
        ux, uy = self.side * math.cos(a), -math.sin(a)
        nx, ny = -uy, ux
        hx, hy = x, top + 24
        n = 7
        for k in range(n):
            u0, u1 = self.L * k / n, self.L * (k + 1) / n
            q = [(hx + ux * u0 + nx * 13, hy + uy * u0 + ny * 13), (hx + ux * u1 + nx * 13, hy + uy * u1 + ny * 13),
                 (hx + ux * u1 - nx * 13, hy + uy * u1 - ny * 13), (hx + ux * u0 - nx * 13, hy + uy * u0 - ny * 13)]
            p.poly(q, fill=(226, 60, 52) if k % 2 == 0 else WHITE, line=None, w=0)
        ends = [(hx + nx * 13, hy + ny * 13), (hx + ux * self.L + nx * 13, hy + uy * self.L + ny * 13),
                (hx + ux * self.L - nx * 13, hy + uy * self.L - ny * 13), (hx - nx * 13, hy - ny * 13)]
        p.poly(ends, fill=None, w=5)
        p.circle(hx, hy, 14, fill=(90, 92, 100), w=5)
        on = t >= self.t_down + 0.3 and (self.t_up is None or t < self.t_up) and (t * 2.2) % 1.0 < 0.5
        p.circle(x, top - 26, 18, fill=(255, 70, 60) if on else (120, 40, 40), w=5)
        if on:
            for j in range(6):
                aa = j * math.pi / 3
                p.line([(x + 28 * math.cos(aa), top - 26 + 28 * math.sin(aa)),
                        (x + 40 * math.cos(aa), top - 26 + 40 * math.sin(aa))], color=(255, 90, 70), w=4)
        p.paste_to(im)


# ---------- clock that spins from one time to another ----------
class Clock(Anim):
    def __init__(self, cx, cy, r, start, h0, h1, t0, t1, color=INK, until=None, night=False):
        self.cx, self.cy, self.r, self.start, self.h0, self.h1, self.t0, self.t1, self.color, self.until = (
            cx, cy, r, start, h0, h1, t0, t1, color, until)
        self.night = night

    def paste(self, im, t):
        p = Painter()
        cx, cy, r = self.cx, self.cy, self.r
        pop = back_out((t - self.start) / 0.35)
        r *= max(0.01, pop)
        p.circle(cx, cy, r, fill=(40, 46, 72) if self.night else WHITE, line=self.color, w=8)
        tick = WHITE if self.night else self.color
        for k in range(12):
            a = k * math.pi / 6
            r0 = r * (0.78 if k % 3 else 0.7)
            p.line([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)), (cx + r * 0.88 * math.sin(a),
                                                                   cy - r * 0.88 * math.cos(a))], color=tick, w=5)
        h = self.h0 + (self.h1 - self.h0) * ease((t - self.t0) / max(1e-6, self.t1 - self.t0))
        ah = (h % 12) / 12 * 2 * math.pi
        am = (h % 1) * 2 * math.pi
        p.line([(cx, cy), (cx + r * 0.5 * math.sin(ah), cy - r * 0.5 * math.cos(ah))], color=tick, w=10)
        p.line([(cx, cy), (cx + r * 0.75 * math.sin(am), cy - r * 0.75 * math.cos(am))], color=(226, 72, 60), w=6)
        p.circle(cx, cy, 9, fill=(226, 72, 60), w=0)
        p.paste_to(im)


# ---------- tear-off calendar that flips between labels ----------
class Calendar(Anim):
    """pages = [(t, big, small), ...]: shows each page from its time; the old page flips up (squash) in 0.3 s."""

    def __init__(self, cx, cy, w, h, start, pages, color=wb.RED, until=None):
        self.cx, self.cy, self.w, self.h, self.start, self.pages, self.color, self.until = (
            cx, cy, w, h, start, sorted(pages, key=lambda q: q[0]), color, until)

    def _page(self, p, big, small, sq=1.0):
        cx, cy, w, h = self.cx, self.cy, self.w, self.h
        top = cy - h / 2 + 46
        yb = top + (cy + h / 2 - top) * (1 - sq) if sq < 1 else top
        y1 = cy + h / 2
        if y1 - yb < 4:
            return
        p.poly([(cx - w / 2, yb), (cx + w / 2, yb), (cx + w / 2, y1), (cx - w / 2, y1)], fill=WHITE, w=6)
        if sq > 0.6:
            hh = (y1 - yb)
            p.text(cx, yb + hh * 0.46, big, int(h * 0.36 * min(1, sq)), color=INK)
            if small:
                p.text(cx, yb + hh * 0.82, small, max(40, int(h * 0.13)), color=(120, 120, 128))

    def paste(self, im, t):
        p = Painter()
        cx, cy, w, h = self.cx, self.cy, self.w, self.h
        pop = back_out((t - self.start) / 0.35)
        if pop < 0.05:
            return
        cur = 0
        for k, (tk, *_r) in enumerate(self.pages):
            if t >= tk:
                cur = k
        top = cy - h / 2
        p.poly([(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, top + 50), (cx - w / 2, top + 50)],
               fill=self.color, w=6)
        for j in (-1, 1):
            p.line([(cx + j * w * 0.25, top - 16), (cx + j * w * 0.25, top + 20)], color=LINE, w=10)
        nxt = cur + 1 < len(self.pages) and t >= self.pages[cur + 1][0] - 0.3
        _, big, small = self.pages[cur]
        if nxt:
            tn, nb, ns = self.pages[cur + 1]
            self._page(p, nb, ns)
            self._page(p, big, small, sq=1 - ease((t - (tn - 0.3)) / 0.3))
        else:
            self._page(p, big, small)
        p.paste_to(im)


# ---------- pin that drops and pings ----------
class Pin(Anim):
    def __init__(self, x, y, start, color=wb.RED, size=60, ping=True, until=None):
        self.x, self.y, self.start, self.color, self.size, self.ping, self.until = x, y, start, color, size, ping, until

    def paste(self, im, t):
        p = Painter()
        u = (t - self.start) / 0.45
        drop = (1 - back_out(u, 2.4)) * -260 if u < 1 else 0
        bob = 6 * math.sin((t - self.start) * 3.2) if u >= 1 else 0
        if self.ping and u >= 1:
            for j in range(2):
                ph = ((t - self.start - 0.45) * 0.8 + j * 0.5) % 1.0
                rr = 20 + 90 * ph
                g = int(150 + 100 * ph)
                p.circle(self.x, self.y, rr, fill=None, line=(255, g - 60, g - 60), w=max(1, 6 * (1 - ph)))
        s = self.size
        x, y = self.x, self.y + drop + bob - 4
        pts = [(x, y)] + [(x + s * 0.5 * math.cos(a), y - s * 1.05 + s * 0.5 * math.sin(a))
                          for a in [math.pi * (0.85 - 1.7 * k / 20) for k in range(21)]]
        pts = [(x, y)] + [(x + s * 0.5 * math.cos(a), y - s * 1.05 - s * 0.5 * math.sin(a))
                          for a in [math.pi * (-0.2 + 1.4 * k / 20) for k in range(21)]]
        p.poly(pts, fill=self.color, w=5)
        p.circle(x, y - s * 1.05, s * 0.2, fill=WHITE, w=4)
        p.paste_to(im)


# ---------- pointer arrow that hops between spots ----------
class Pointer(Anim):
    """Fat arrow; keys = [(t, x, y), ...] (tip position), direction 'down' | 'right' | 'left'."""

    def __init__(self, keys, start, direction="down", color=wb.RED, size=70, until=None):
        self.keys, self.start, self.dir, self.color, self.size, self.until = (
            sorted(keys), start, direction, color, size, until)

    def pos(self, t):
        k = self.keys
        if t <= k[0][0]:
            return k[0][1], k[0][2], 0.0
        for (t0, x0, y0), (t1, x1, y1) in zip(k, k[1:]):
            if t < t1:
                u = ease((t - t0) / max(1e-6, t1 - t0))
                hop = math.sin(math.pi * clamp((t - t0) / max(1e-6, t1 - t0))) * 50
                return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, hop
        return k[-1][1], k[-1][2], 0.0

    def paste(self, im, t):
        p = Painter()
        x, y, hop = self.pos(t)
        u = (t - self.start) / 0.35
        sc = back_out(u) if u < 1 else 1.0
        wig = 10 * abs(math.sin((t - self.start) * 5.0))
        s = self.size * max(0.01, sc)
        shape = [(0, 0), (-0.55, -0.6), (-0.22, -0.6), (-0.22, -1.25), (0.22, -1.25), (0.22, -0.6), (0.55, -0.6)]
        if self.dir == "down":
            pts = [(x + a * s, y - hop - wig + b * s) for a, b in shape]
        elif self.dir == "right":
            pts = [(x - wig + b * s, y + a * s) for a, b in shape]
        else:
            pts = [(x + wig - b * s, y + a * s) for a, b in shape]
        p.poly(pts, fill=self.color, w=5)
        p.paste_to(im)


# ---------- gauge with a swinging needle ----------
class Gauge(Anim):
    """Half-dial; needle goes to `value` (0..1) at t_go with a wobble; red zone above `limit`."""

    def __init__(self, cx, cy, r, start, keys, limit=0.7, until=None):
        self.cx, self.cy, self.r, self.start, self.keys, self.limit, self.until = cx, cy, r, start, sorted(keys), limit, until

    def value(self, t):
        v = self.keys[0][1]
        for (t0, v0), (t1, v1) in zip(self.keys, self.keys[1:]):
            if t >= t0:
                v = v0 + (v1 - v0) * back_out((t - t0) / max(1e-6, t1 - t0), 1.4)
        if t >= self.keys[-1][0]:
            v = self.keys[-1][1]
        return v + 0.012 * math.sin(t * 13)

    def paste(self, im, t):
        p = Painter()
        cx, cy, r = self.cx, self.cy, self.r
        arc = lambda a0, a1, rr: [(cx + rr * math.cos(math.pi + (a0 + (a1 - a0) * k / 24) * math.pi),
                                   cy + rr * math.sin(math.pi + (a0 + (a1 - a0) * k / 24) * math.pi)) for k in range(25)]
        p.poly(arc(0, 1, r) + [(cx, cy)], fill=WHITE, w=7)
        p.poly(arc(0, self.limit, r * 0.94) + arc(self.limit, 0, r * 0.72)[::-1][::-1], fill=None, line=None, w=0)
        p.poly(arc(0, self.limit, r * 0.94) + list(reversed(arc(0, self.limit, r * 0.74))), fill=(190, 230, 190),
               line=None, w=0)
        p.poly(arc(self.limit, 1, r * 0.94) + list(reversed(arc(self.limit, 1, r * 0.74))), fill=(255, 190, 186),
               line=None, w=0)
        v = max(0.0, min(1.0, self.value(t)))
        a = math.pi + v * math.pi
        p.line([(cx, cy), (cx + r * 0.82 * math.cos(a), cy + r * 0.82 * math.sin(a))], color=LINE, w=9)
        p.circle(cx, cy, 14, fill=LINE, w=0)
        p.paste_to(im)


# ---------- progress bar that fills over time ----------
class Progress(Anim):
    def __init__(self, box, start, t0, t1, color=(64, 168, 104), until=None):
        self.box, self.start, self.t0, self.t1, self.color, self.until = box, start, t0, t1, color, until

    def paste(self, im, t):
        p = Painter()
        x0, y0, x1, y1 = self.box
        u = ease((t - self.t0) / max(1e-6, self.t1 - self.t0))
        if u > 0.01:
            p.poly([(x0 + 8, y0 + 8), (x0 + 8 + (x1 - x0 - 16) * u, y0 + 8), (x0 + 8 + (x1 - x0 - 16) * u, y1 - 8),
                    (x0 + 8, y1 - 8)], fill=self.color, line=None, w=0)
            # little shine stripes moving
            for k in range(int((x1 - x0) / 60) + 2):
                sx = x0 + 8 + ((k * 60 + (t * 90)) % (x1 - x0))
                if sx + 20 < x0 + 8 + (x1 - x0 - 16) * u:
                    p.line([(sx, y1 - 12), (sx + 20, y0 + 12)], color=(255, 255, 255, 120), w=6)
        p.paste_to(im)


# ---------- cà vẹt (registration card) that flips to show the year ----------
class Card(Anim):
    """A blue-ish registration card; at t_flip it turns over and shows rows, the year row highlighted."""

    def __init__(self, cx, cy, w, h, start, t_flip, year="2015", until=None):
        self.cx, self.cy, self.w, self.h, self.start, self.t_flip, self.year, self.until = (
            cx, cy, w, h, start, t_flip, year, until)
        self.front = self._front()
        self.back = self._back()

    def _base(self):
        S = 2
        w, h = int(self.w * S), int(self.h * S)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((4, 4, w - 4, h - 4), radius=28 * S, fill=(214, 232, 250), outline=LINE, width=6 * S)
        return im, d, S

    def _front(self):
        im, d, S = self._base()
        w, h = im.size
        d.text((w / 2, h * 0.24), "CÀ VẸT XE", font=wb.hand_font(int(h * 0.17)), fill=INK, anchor="mm")
        for k in range(3):
            y = h * (0.48 + 0.15 * k)
            d.line((w * 0.12, y, w * (0.88 - 0.15 * (k == 2)), y), fill=(120, 140, 170), width=5 * S)
        d.ellipse((w * 0.72, h * 0.6, w * 0.88, h * 0.6 + w * 0.16), outline=(226, 72, 60), width=5 * S)
        return im.resize((w // S, h // S), Image.Resampling.LANCZOS)

    def _back(self):
        im, d, S = self._base()
        w, h = im.size
        f = wb.hand_font(int(h * 0.13))
        d.text((w * 0.1, h * 0.2), "Nhãn hiệu: ....", font=f, fill=(90, 96, 110), anchor="lm")
        d.text((w * 0.1, h * 0.4), "Số máy: ....", font=f, fill=(90, 96, 110), anchor="lm")
        d.rectangle((w * 0.06, h * 0.52, w * 0.94, h * 0.76), fill=(255, 236, 130))
        d.text((w * 0.1, h * 0.64), f"Năm sản xuất: {self.year}", font=wb.hand_font(int(h * 0.15)), fill=INK,
               anchor="lm")
        d.text((w * 0.1, h * 0.86), "Biển số: ....", font=f, fill=(90, 96, 110), anchor="lm")
        return im.resize((w // S, h // S), Image.Resampling.LANCZOS)

    def paste(self, im, t):
        u = (t - self.start) / 0.4
        sc = back_out(u) if u < 1 else 1.0
        if sc < 0.05:
            return
        f = (t - self.t_flip) / 0.5
        if f < 0.5:
            sp, sx = self.front, abs(math.cos(math.pi * clamp(f)))
        else:
            sp, sx = self.back, abs(math.cos(math.pi * clamp(f)))
        sx = max(0.02, sx) * sc
        sy = sc * (1 + 0.06 * math.sin(math.pi * clamp(f)))
        sp = sp.resize((max(1, int(sp.width * sx)), max(1, int(sp.height * sy))), Image.Resampling.BILINEAR)
        rot = -4 + 4 * clamp(f)
        sp = sp.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
        wb._paste(im, sp, self.cx - sp.width / 2, self.cy - sp.height / 2)


# ---------- magnifier that follows a point (e.g. a stick's hand) ----------
class Magnifier(Anim):
    def __init__(self, at, start, r=56, until=None):
        self.at, self.start, self.r, self.until = at, start, r, until  # at: t -> (x, y) of the handle end

    def paste(self, im, t):
        p = Painter()
        x, y = self.at(t)
        sc = back_out((t - self.start) / 0.3)
        r = self.r * max(0.05, sc)
        a = -0.8 + 0.12 * math.sin(t * 2.4)
        cx, cy = x + math.cos(a) * r * 1.9, y + math.sin(a) * r * 1.9
        p.line([(x, y), (x + math.cos(a) * r * 0.95, y + math.sin(a) * r * 0.95)], color=(120, 80, 50), w=14)
        p.circle(cx, cy, r, fill=(220, 240, 255), line=LINE, w=9)
        p.line([(cx - r * 0.45, cy - r * 0.2), (cx - r * 0.2, cy - r * 0.5)], color=WHITE, w=7)
        p.paste_to(im)


# ---------- odometer counting up ----------
class Counter(Anim):
    def __init__(self, cx, cy, start, t0, t1, v0, v1, size=110, fmt="{:,}", suffix="", color=INK, until=None):
        self.cx, self.cy, self.start, self.t0, self.t1, self.v0, self.v1, self.size, self.fmt, self.suffix, \
            self.color, self.until = cx, cy, start, t0, t1, v0, v1, size, fmt, suffix, color, until

    def paste(self, im, t):
        p = Painter()
        v = self.v0 + (self.v1 - self.v0) * ease((t - self.t0) / max(1e-6, self.t1 - self.t0))
        s = self.fmt.format(int(round(v))).replace(",", ".") + self.suffix
        p.text(self.cx, self.cy, s, self.size, color=self.color)
        p.paste_to(im)


# ---------- camera that flashes ----------
class Camera(Anim):
    def __init__(self, x, y, start, flashes=(), face=1, until=None):
        self.x, self.y, self.start, self.flashes, self.face, self.until = x, y, start, flashes, face, until

    def paste(self, im, t):
        p = Painter()
        x, y, f = self.x, self.y, self.face
        sc = back_out((t - self.start) / 0.35)
        if sc < 0.05:
            return
        sw = math.sin((t - self.start) * 1.3) * 0.15
        P = lambda u, v: (x + f * (u * math.cos(sw) - v * math.sin(sw)) * sc, y + (u * math.sin(sw) + v * math.cos(sw)) * sc)
        p.line([(x, y - 10), (x, y + 140 * sc)], color=(90, 92, 100), w=12)
        p.poly([P(-70, -40), P(80, -40), P(80, 40), P(-70, 40)], fill=(236, 238, 242), w=7)
        p.poly([P(80, -24), P(126, -36), P(126, 36), P(80, 24)], fill=(90, 92, 100), w=6)
        rec = (t * 1.6) % 1.0 < 0.5
        cx, cy = P(-40, -14)
        p.circle(cx, cy, 10, fill=(255, 60, 50) if rec else (150, 60, 60), w=3)
        for tf in self.flashes:
            u = (t - tf) / 0.35
            if 0 <= u < 1:
                lx, ly = P(126, 0)
                for j in range(8):
                    a = j * math.pi / 4
                    r0, r1 = 20 + 30 * u, 50 + 90 * u
                    p.line([(lx + f * r0 * math.cos(a), ly + r0 * math.sin(a)),
                            (lx + f * r1 * math.cos(a), ly + r1 * math.sin(a))], color=(246, 196, 54), w=8)
        p.paste_to(im)
