"""v03 look: a rounder, more expressive host "Tí" and a 3D gold ingot.

`install()` swaps them in without touching the skill library: Board.stick -> Ti, scenes.gold_bar/gold_pile -> the
ingot versions. Call it BEFORE importing scenes_v02 / render code that does `from scenes import gold_bar`.

Ti keeps the Stick API (act / walk / jump / last / head_at / hand_at, same pose + mood names) and adds moods:
laugh, wink, cry, smug, confused, starstruck, money, nervous, determined. Face features are numeric parameters that
blend smoothly (eyes, brows, mouth, blush); poses blend with a slight overshoot plus a squash on every change;
hair and scarf tail trail the body.
"""
import math
import os
import sys

os.environ.setdefault("FRAME_FORMAT", "landscape")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import ImageDraw  # noqa: E402

import frame_kit as fk  # noqa: E402
import whiteboard as wb  # noqa: E402
from whiteboard import (BLUE, BLUSH, GREEN, INK, MOUTH, ORANGE, PAPER, PEN_SPEED, RED, SS, STICK_POSES,  # noqa: E402
                        YELLOW, Element, _ellipse, _heart, _length, _partial, _qcurve, _resample, _star)

SKIN = (253, 226, 200)
HAIR = (46, 40, 44)
SHIRT = (86, 146, 214)
TEAR = (120, 186, 245)
TONGUE = (238, 120, 120)

POSES = dict(STICK_POSES)
_SP = lambda arms, legs=((8, 3), (8, 3)), lean=0, tilt=0, look=(0, 0): dict(arms=arms, legs=legs, lean=lean, tilt=tilt, look=look)
POSES.update({
    "clap": _SP(((55, 150), (55, 150)), look=(0, -0.02)),
    "fist": _SP(((22, 12), (70, 170)), legs=((12, 4), (12, 4)), tilt=3),
    "cheeks": _SP(((40, 175), (40, 175)), legs=((6, 2), (6, 2))),
    "hug": _SP(((45, 120), (45, 120)), legs=((10, 3), (10, 3))),
})

# Face parameters: eye kind, eye openness, pupil scale, brow raise L/R, brow angle (+ = angry), mouth curve,
# mouth open, mouth width, wave, teeth, smirk, blush, extras.
_F = lambda eye="dot", eo=1.0, ps=1.0, bl=0.0, br=0.0, ba=0.0, mc=0.6, mo=0.0, mw=0.24, wav=0.0, teeth=0.0, \
    sk=0.0, blush=0.6, fx=(), look=(0, 0): dict(eye=eye, eo=eo, ps=ps, bl=bl, br=br, ba=ba, mc=mc, mo=mo, mw=mw,
                                                wav=wav, teeth=teeth, sk=sk, blush=blush, fx=fx, look=look)
FACES = {
    "happy": _F(mc=0.9, mo=0.45, mw=0.26, bl=0.3, br=0.3),
    "neutral": _F(mc=0.2, mw=0.16, blush=0.35),
    "shock": _F(eye="ring", eo=1.25, ps=0.7, bl=1.2, br=1.2, mc=0.0, mo=0.95, mw=0.14, blush=0.2, fx=("bang", "sweat")),
    "sad": _F(eo=0.85, bl=0.4, br=0.4, ba=-1.0, mc=-0.8, mw=0.2, blush=0.25, fx=("tear",), look=(0, 0.08)),
    "worried": _F(eo=1.05, ps=0.8, bl=0.6, br=0.6, ba=-0.9, mc=-0.25, mw=0.22, wav=1.0, blush=0.3, fx=("sweat",)),
    "think": _F(eo=0.95, bl=0.0, br=0.9, ba=0.2, mc=0.05, mw=0.12, sk=0.6, blush=0.3, look=(0.14, -0.14)),
    "angry": _F(eo=0.9, bl=-0.2, br=-0.2, ba=1.1, mc=-0.6, mo=0.3, mw=0.22, teeth=1.0, blush=0.0, fx=("vein",)),
    "love": _F(eye="heart", mc=1.0, mo=0.55, mw=0.26, bl=0.4, br=0.4, blush=1.0, fx=("hearts",)),
    "proud": _F(eye="arc", mc=0.85, mw=0.22, sk=0.35, bl=0.2, br=0.2, blush=0.7, fx=("sparkle",), look=(0, -0.08)),
    "laugh": _F(eye="arc", mc=1.0, mo=1.0, mw=0.3, bl=0.5, br=0.5, blush=0.9),
    "wink": _F(eye="wink", mc=0.9, mo=0.35, mw=0.24, bl=0.2, br=0.5, sk=0.4, blush=0.7, fx=("sparkle",)),
    "cry": _F(eye="cry", bl=0.5, br=0.5, ba=-1.2, mc=-1.0, mo=0.75, mw=0.24, blush=0.6, fx=("stream",)),
    "smug": _F(eye="lid", eo=0.55, bl=-0.1, br=0.5, ba=0.3, mc=0.7, mw=0.2, sk=0.9, blush=0.4),
    "confused": _F(eo=1.0, ps=0.85, bl=-0.3, br=0.9, mc=-0.1, mw=0.16, wav=0.8, sk=-0.5, blush=0.3, fx=("q",)),
    "starstruck": _F(eye="star", mc=1.0, mo=0.8, mw=0.28, bl=0.6, br=0.6, blush=0.9, fx=("sparkle",)),
    "money": _F(eye="dollar", mc=1.0, mo=0.6, mw=0.3, bl=0.5, br=0.5, blush=0.7, fx=("sparkle",)),
    "nervous": _F(eo=1.1, ps=0.65, bl=0.7, br=0.7, ba=-0.8, mc=-0.05, mo=0.35, mw=0.28, teeth=1.0, blush=0.3,
                  fx=("sweat",)),
    "determined": _F(eo=0.9, bl=-0.3, br=-0.3, ba=0.8, mc=0.35, mw=0.2, sk=0.3, blush=0.4, fx=("sparkle",)),
}
MOODS = tuple(FACES)
_NUM = ("eo", "ps", "bl", "br", "ba", "mc", "mo", "mw", "wav", "teeth", "sk", "blush")


def _back(u, s=1.25):
    u = max(0.0, min(1.0, u))
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def _rot2(a_deg, side):
    a = math.radians(a_deg)
    return side * math.sin(a), math.cos(a)


def _curve3(a, m, b, n=12):
    """Quadratic curve through a, m (at u=.5) and b."""
    c = (2 * m[0] - (a[0] + b[0]) / 2, 2 * m[1] - (a[1] + b[1]) / 2)
    return _qcurve(a, c, b, n)


def _spark(cx, cy, s):
    pts = []
    for k in range(16):
        a = -math.pi / 2 + k * math.pi / 8
        rr = s if k % 4 == 0 else (0.22 * s if k % 2 else 0.32 * s)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


class Ti(Element):
    animated = True
    BLEND = 0.42
    FACE_BLEND = 0.3

    def __init__(self, cx, base, h, start, pose, mood, accent, color, dur, look, seed, drawn=True):
        assert pose in POSES and mood in FACES, (pose, mood)
        self.cx, self.base, self.h, self.start = cx, base, h, start
        self.accent, self.color = accent, color
        self.keys = [(start, pose, mood, look)]
        self.moves, self.jumps = [], []
        self.seed = seed
        self.w = max(4, round(h * 0.022))
        self.now = start
        self.drawn = drawn
        layers = self._layers(start, still=True)
        L = sum(_length(q) for kind, q, *_ in layers if kind == "line")
        self.dur = dur if dur is not None else (max(1.0, min(2.0, L / (PEN_SPEED * 1.2))) if drawn else 0.0)

    # -- timeline (same API as whiteboard.Stick) --
    def act(self, t, pose=None, mood=None, look=None):
        _, p0, m0, l0 = max((k for k in self.keys if k[0] <= t), key=lambda k: k[0], default=self.keys[0])
        assert (pose or p0) in POSES and (mood or m0) in FACES, (pose, mood)
        self.keys.append((t, pose or p0, mood or m0, look if look is not None else (None if pose else l0)))
        self.keys.sort(key=lambda k: k[0])
        if pose == "shock":
            self.jumps.append((t, 0.38, 0.08))
        return self

    def walk(self, t, to_x, dur=None):
        x0 = self.x_at(t)
        dur = dur or max(0.6, abs(to_x - x0) / (0.95 * self.h))
        self.moves.append((t, t + dur, x0, to_x))
        self.moves.sort()
        return self

    def jump(self, t, height=0.22, dur=0.6):
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
        return self._geom(t)["head"]

    def hand_at(self, t, side=1):
        return self._geom(t)["hands"][0 if side < 0 else 1]

    @property
    def bbox(self):
        xs = [self.cx] + [m[3] for m in self.moves]
        up = max([j[2] for j in self.jumps], default=0) + 0.32
        return (int(min(xs) - 0.8 * self.h), int(self.base - (1.12 + up) * self.h),
                int(max(xs) + 0.8 * self.h), int(self.base + 0.08 * self.h))

    # -- state at t --
    def _state(self, t, still=False):
        keys = [k for k in self.keys if k[0] <= t] or self.keys[:1]
        cur = keys[-1]
        prev = keys[-2] if len(keys) >= 2 else cur
        P, Q = POSES[cur[1]], POSES[prev[1]]
        dt = t - cur[0]
        u = 1.0 if cur is prev else _back(dt / self.BLEND)
        mix = lambda a, b: a + (b - a) * u
        arms = [[mix(qa, pa) for qa, pa in zip(q, p)] for q, p in zip(Q["arms"], P["arms"])]
        legs = [[mix(qa, pa) for qa, pa in zip(q, p)] for q, p in zip(Q["legs"], P["legs"])]
        lean, tilt = mix(Q["lean"], P["lean"]), mix(Q["tilt"], P["tilt"])
        FP, FQ = FACES[cur[2]], FACES[prev[2]]
        uf = 1.0 if cur is prev else fk.smooth(dt / self.FACE_BLEND)
        face = {k: FQ[k] + (FP[k] - FQ[k]) * uf for k in _NUM}
        face["eye"] = FP["eye"] if uf > 0.5 else FQ["eye"]
        face["fx"] = FP["fx"]
        face["fxa"] = uf
        face["mood"] = cur[2]
        lp = cur[3] if cur[3] is not None else (P["look"] if P["look"] != (0, 0) else FP["look"])
        lq = prev[3] if prev[3] is not None else (Q["look"] if Q["look"] != (0, 0) else FQ["look"])
        look = (lq[0] + (lp[0] - lq[0]) * uf, lq[1] + (lp[1] - lq[1]) * uf)
        x, y, sq = self.x_at(t), 0.0, 1.0
        hair_lag, tail_lag = 0.0, 0.0
        if not still:
            ph = self.seed * 1.7
            y += 0.008 * self.h * math.sin(2 * math.pi * 0.45 * t + ph)
            sq += 0.012 * math.sin(2 * math.pi * 0.45 * t + ph)
            tilt += 2.6 * math.sin(2 * math.pi * 0.27 * t + ph)
            if cur is not prev and dt < 0.42:  # squash-and-stretch on every change
                v = dt / 0.42
                sq -= 0.07 * math.sin(math.pi * min(1, v / 0.45)) if v < 0.45 else -0.03 * math.sin(math.pi * (v - 0.45) / 0.55)
            pose, mood = cur[1], cur[2]
            if pose == "wave":
                arms[1][1] += 26 * math.sin(2 * math.pi * 2.2 * t) * u
            elif pose == "cheer":
                k = abs(math.sin(2 * math.pi * 1.2 * dt))
                y -= 0.07 * self.h * k * u
                sq += 0.04 * k
                for a in arms:
                    a[1] += 12 * k
            elif pose == "clap":
                k = 0.5 + 0.5 * math.sin(2 * math.pi * 3.0 * dt)
                arms[0][1] += 14 * k
                arms[1][1] += 14 * k
            elif pose == "worried":
                x += 1.4 * math.sin(2 * math.pi * 8 * t)
            elif pose.startswith("point") or pose.startswith("present"):
                arms[1 if pose.endswith("_r") or pose == "point_up" else 0][1] += 5 * math.sin(2 * math.pi * 1.5 * t) * u
            elif pose == "fist":
                arms[1][1] += 10 * abs(math.sin(2 * math.pi * 1.6 * dt))
            if mood == "laugh":
                k = abs(math.sin(2 * math.pi * 3.2 * dt))
                y -= 0.015 * self.h * k
                face["mo"] = 0.75 + 0.25 * k
                tilt -= 4 * k
            elif mood == "cry":
                x += 1.2 * math.sin(2 * math.pi * 7 * t)
                face["mo"] += 0.12 * math.sin(2 * math.pi * 4 * t)
            elif mood == "nervous":
                x += 1.0 * math.sin(2 * math.pi * 11 * t)
            elif mood == "angry":
                y += 0.004 * self.h * math.sin(2 * math.pi * 12 * t)
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
                    y -= 0.025 * self.h * abs(math.sin(phs))
                    hair_lag -= d * 0.6
                    tail_lag -= d * 1.0
            for tj, dj, hj in self.jumps:
                pre = 0.14  # crouch before take-off
                if tj - pre <= t < tj:
                    sq -= 0.1 * math.sin(math.pi / 2 * (t - tj + pre) / pre)
                elif tj <= t < tj + dj:
                    v = (t - tj) / dj
                    y -= hj * self.h * math.sin(math.pi * v)
                    sq += 0.08 * math.cos(math.pi * v) if v < 0.5 else -0.02
                    hair_lag += 0.8 * math.cos(math.pi * v)
                    tail_lag += 1.0 * math.cos(math.pi * v)
                    for leg in legs:
                        leg[0] += 16 * math.sin(math.pi * v)
                        leg[1] -= 24 * math.sin(math.pi * v)
                elif tj + dj <= t < tj + dj + 0.18:
                    sq -= 0.08 * math.sin(math.pi * (t - tj - dj) / 0.18)
            # smooth blink: 0.16 s close-open every ~3.7 s
            bt = (t + self.seed * 0.9) % 3.7
            if bt < 0.16:
                face["eo"] *= abs(math.cos(math.pi * bt / 0.16)) ** 0.7
            hair_lag += 0.25 * math.sin(2 * math.pi * 0.9 * t + ph)
            tail_lag += 0.5 * math.sin(2 * math.pi * 1.1 * t + ph)
        return dict(arms=arms, legs=legs, lean=lean, tilt=tilt, look=look, face=face, x=x, y=y, sq=sq,
                    hair=hair_lag, tail=tail_lag)

    def _geom(self, t, still=False):
        S = self._state(t, still)
        h = self.h
        thigh, shin = 0.15 * h, 0.14 * h
        drops = [thigh * _rot2(a, s)[1] + shin * _rot2(b, s)[1] for s, (a, b) in zip((-1, 1), S["legs"])]
        X, base, sq = S["x"], self.base, S["sq"]
        sx = 1 / math.sqrt(max(0.5, sq))
        T = lambda p: (X + (p[0] - X) * sx, base - (base - p[1]) * sq + S["y"])
        hip = (X, base - max(drops))
        L = math.radians(S["lean"])
        ax, ay = math.sin(L), -math.cos(L)          # torso axis (up)
        px, py = math.cos(L), math.sin(L)           # perpendicular (screen right)
        tl = 0.23 * h
        neck = (hip[0] + tl * ax, hip[1] + tl * ay)
        r = 0.205 * h
        HT = math.radians(S["lean"] + S["tilt"])
        head = (neck[0] + 1.02 * r * math.sin(HT), neck[1] - 1.02 * r * math.cos(HT))
        arms, hands, legs = [], [], []
        for side, (a, b) in zip((-1, 1), S["arms"]):
            sh = (neck[0] + side * 0.075 * h * px - 0.035 * h * ax, neck[1] + side * 0.075 * h * py - 0.035 * h * ay)
            ux, uy = _rot2(a, side)
            el = (sh[0] + 0.125 * h * ux, sh[1] + 0.125 * h * uy)
            fx, fy = _rot2(b, side)
            hd = (el[0] + 0.12 * h * fx, el[1] + 0.12 * h * fy)
            arms.append([T(sh), T(el), T(hd)])
            hands.append(T(hd))
        for side, (a, b) in zip((-1, 1), S["legs"]):
            hp = (hip[0] + side * 0.045 * h * px, hip[1] + side * 0.045 * h * py)
            ux, uy = _rot2(a, side)
            kn = (hp[0] + thigh * ux, hp[1] + thigh * uy)
            fx, fy = _rot2(b, side)
            ft = (kn[0] + shin * fx, kn[1] + shin * fy)
            legs.append((side, [T(hp), T(kn), T(ft)]))
        # torso outline (neck -> right shoulder -> right hip -> left hip -> left shoulder)
        def tp(s_, w_, along):
            return T((hip[0] + along * tl * ax + s_ * w_ * h * px, hip[1] + along * tl * ay + s_ * w_ * h * py))
        torso = (_curve3(tp(-1, 0.07, 1.0), tp(-1, 0.09, 0.45), tp(-1, 0.085, 0.0), 10)
                 + _curve3(tp(-1, 0.085, 0.0), tp(0, 0, -0.06), tp(1, 0.085, 0.0), 8)[1:]
                 + _curve3(tp(1, 0.085, 0.0), tp(1, 0.09, 0.45), tp(1, 0.07, 1.0), 10)[1:]
                 + _curve3(tp(1, 0.07, 1.0), tp(0, 0, 1.06), tp(-1, 0.07, 1.0), 8)[1:])
        hx, hy = T(head)
        return dict(S=S, head=(hx, hy, r * math.sqrt(sx * sq)), neck=T(neck), hip=T(hip), arms=arms, hands=hands,
                    legs=legs, torso=torso, r=r, tiltr=HT, sx=sx, sq=sq)

    # -- drawing --
    def _face(self, g, t, still):
        """Face layers in head-local units (r = 1, +y down), already rotated/placed via `P`."""
        S, F = g["S"], g["S"]["face"]
        hx, hy, r = g["head"]
        cs, sn = math.cos(g["tiltr"]), math.sin(g["tiltr"])
        lx, ly = S["look"]

        def P(pts):
            return [(hx + r * (x * cs - y * sn), hy + r * (x * sn + y * cs)) for x, y in pts]

        out = []  # (kind, pts, colour, width_scale or alpha)
        line = lambda pts, col=self.color, ws=0.85: out.append(("line", P(pts), col, ws))
        fill = lambda pts, col, a=255: out.append(("fill", P(pts), col, a))
        E = lambda cx, cy, rx, ry, n=20, a0=0.0, a1=2 * math.pi: _ellipse(cx, cy, rx, ry, n, a0, a1)
        # blush
        if F["blush"] > 0.02:
            for s in (-1, 1):
                fill(E(s * 0.62 + 0.4 * lx, 0.28, 0.16, 0.085, 16), BLUSH, int(150 * min(1, F["blush"])))
        ey = 0.02
        eyes = [(-0.37 + lx, ey + ly), (0.37 + lx, ey + ly)]
        kind, eo = F["eye"], max(0.0, F["eo"])
        for i, (x, y) in enumerate(eyes):
            k = kind
            if kind == "wink":
                k = "arc" if i == 0 else "dot"
            if kind in ("dot", "lid") or k == "dot":
                ry = 0.175 * eo
                if ry < 0.025:
                    line([(x - 0.11, y), (x + 0.11, y)])
                else:
                    fill(E(x, y, 0.125 * F["ps"], ry * F["ps"] ** 0.5, 18), self.color)
                    if eo > 0.45:
                        fill(E(x + 0.04, y - 0.06 * eo, 0.045, 0.045, 8), (255, 255, 255))
                if kind == "lid":
                    line([(x - 0.15, y - 0.02), (x + 0.15, y - 0.06)], ws=1.0)
            elif k == "ring":
                ry = 0.2 * eo
                if ry < 0.03:
                    line([(x - 0.12, y), (x + 0.12, y)])
                else:
                    fill(E(x, y, 0.18, ry, 24), (255, 255, 255))
                    line(E(x, y, 0.18, ry, 24))
                    fill(E(x + 0.3 * lx, y + 0.3 * ly, 0.07 * F["ps"] / 0.7, 0.07 * F["ps"] / 0.7 * min(1, eo), 12), self.color)
            elif k == "arc":
                line(E(x, y + 0.06, 0.13, 0.12, 14, math.pi * 1.08, math.pi * 1.92), ws=1.0)
            elif k == "cry":
                s = 1 if i == 0 else -1
                line([(x - s * 0.12, y - 0.09), (x + s * 0.08, y), (x - s * 0.12, y + 0.09)], ws=1.0)
            elif k == "heart":
                beat = 1 + (0.12 * abs(math.sin(2 * math.pi * 1.6 * t)) if not still else 0)
                pts = _heart(x, y, 0.36 * beat, 40)
                fill(pts, RED)
                line(pts, ws=0.6)
            elif k == "star":
                spin = 0 if still else 0.4 * math.sin(2 * math.pi * 0.8 * t)
                pts = _star(x, y, 0.22, 0.1, 5, -math.pi / 2 + spin)
                pts = pts + [pts[0]]
                fill(pts, YELLOW)
                line(pts, ws=0.6)
            elif k == "dollar":
                fill(E(x, y, 0.22, 0.22, 24), (255, 255, 255))
                line(E(x, y, 0.22, 0.22, 24), GREEN, 0.7)
                s_ = [(x + 0.1 * math.cos(a), y - 0.065 + 0.065 * math.sin(a))
                      for a in [-0.3 - (math.pi * 1.2) * k_ / 10 for k_ in range(11)]]
                s_ += [(x + 0.1 * math.cos(a), y + 0.065 + 0.065 * math.sin(a))
                       for a in [-math.pi / 2 + (math.pi * 1.2) * k_ / 10 for k_ in range(11)]]
                line(s_, GREEN, 0.9)
                line([(x, y - 0.18), (x, y + 0.18)], GREEN, 0.7)
        # brows
        for i, (x, y) in enumerate(eyes):
            s = -1 if i == 0 else 1
            raise_ = F["bl"] if i == 0 else F["br"]
            by = y - 0.3 - 0.1 * raise_
            inner = (x - s * 0.12, by + 0.07 * F["ba"])
            outer = (x + s * 0.14, by - 0.03 * F["ba"])
            mid = ((inner[0] + outer[0]) / 2, (inner[1] + outer[1]) / 2 - 0.04)
            line(_curve3(inner, mid, outer, 8), ws=0.9)
        # mouth
        mx, my = 0.5 * lx, 0.44 + 0.5 * ly
        c, o, w, sk = F["mc"], max(0.0, F["mo"]), F["mw"], F["sk"]
        Lc = (mx - w, my - 0.08 * c - 0.05 * sk)
        Rc = (mx + w, my - 0.08 * c + 0.05 * sk)
        if o < 0.06:
            pts = []
            for k in range(13):
                u = k / 12
                x_ = Lc[0] + (Rc[0] - Lc[0]) * u
                y_ = Lc[1] + (Rc[1] - Lc[1]) * u + 4 * u * (1 - u) * 0.16 * c + 0.035 * F["wav"] * math.sin(u * 3 * math.pi)
                pts.append((x_, y_))
            line(pts, ws=0.9)
        else:
            up = [(Lc[0] + (Rc[0] - Lc[0]) * u, Lc[1] + (Rc[1] - Lc[1]) * u + 4 * u * (1 - u) * 0.05 * c)
                  for u in (k / 12 for k in range(13))]
            depth = 0.12 + 0.3 * o + 0.06 * max(0, c)
            lo = [(Lc[0] + (Rc[0] - Lc[0]) * u, Lc[1] + (Rc[1] - Lc[1]) * u + 4 * u * (1 - u) * depth * (1 if c > -0.3 else 0.8))
                  for u in (k / 12 for k in range(12, -1, -1))]
            if c < -0.3:  # wail / frown: lower edge flatter, upper arched
                up = [(x_, y_ - 4 * ((x_ - Lc[0]) / (Rc[0] - Lc[0])) * (1 - (x_ - Lc[0]) / (Rc[0] - Lc[0])) * 0.12 * o)
                      for x_, y_ in up]
            poly = up + lo[1:]
            fill(poly, MOUTH)
            if F["teeth"] > 0.5:
                fill(up + [(x_, y_ + 0.08) for x_, y_ in up[::-1]], (255, 255, 255))
                for k in range(1, 4):
                    xk = Lc[0] + (Rc[0] - Lc[0]) * k / 4
                    line([(xk, Lc[1] + 0.02), (xk, Lc[1] + 0.09)], ws=0.4)
            elif o > 0.3:
                ty = max(y_ for _, y_ in lo) - 0.07
                fill(E(mx, ty, 0.11 * (0.6 + o), 0.05 + 0.03 * o, 14), TONGUE)
            line(poly + [poly[0]], ws=0.85)
        # extras (fade in with the face blend)
        a = F["fxa"]
        if a > 0.4:
            fx = F["fx"]
            if "sweat" in fx:
                v = 0 if still else ((t * 0.5) % 1)
                sx_, sy_ = 0.95, -0.55 + 0.35 * v
                drop = [(sx_, sy_ - 0.2)] + E(sx_, sy_, 0.09, 0.09, 12, -0.3, math.pi + 0.3) + [(sx_, sy_ - 0.2)]
                fill(drop, TEAR, 230)
                line(drop, BLUE, 0.6)
            if "tear" in fx:
                v = 0 if still else ((t * 0.4) % 1)
                tx, ty = eyes[0][0] - 0.02, eyes[0][1] + 0.18 + 0.3 * v
                drop = [(tx, ty - 0.17)] + E(tx, ty, 0.075, 0.075, 12, -0.3, math.pi + 0.3) + [(tx, ty - 0.17)]
                fill(drop, TEAR, 230)
                line(drop, BLUE, 0.5)
            if "stream" in fx:
                for i, (x, y) in enumerate(eyes):
                    s = -1 if i == 0 else 1
                    wob = 0 if still else 0.03 * math.sin(2 * math.pi * 3 * t + i)
                    pts = [(x + s * 0.03 + wob * k, y + 0.1 + 0.11 * k) for k in range(7)]
                    poly = [(px_ - 0.05, py_) for px_, py_ in pts] + [(px_ + 0.05, py_) for px_, py_ in pts[::-1]]
                    fill(poly, TEAR, 220)
            if "vein" in fx:
                vx, vy = 0.62, -0.62
                for ang in (0.4, 0.4 + math.pi / 2, 0.4 + math.pi, 0.4 + 1.5 * math.pi):
                    line(_curve3((vx + 0.06 * math.cos(ang), vy + 0.06 * math.sin(ang)),
                                 (vx + 0.13 * math.cos(ang + 0.35), vy + 0.13 * math.sin(ang + 0.35)),
                                 (vx + 0.2 * math.cos(ang), vy + 0.2 * math.sin(ang)), 6), RED, 0.9)
        return out, a

    def _halo(self, g, t, still, a):
        """Effects around the head (not rotated with it): sparkles, hearts, ?, !."""
        hx, hy, r = g["head"]
        F = g["S"]["face"]
        out = []
        if a <= 0.4:
            return out
        fx = F["fx"]
        if "sparkle" in fx:
            for k, (dx, dy, s) in enumerate(((-1.25, -0.75, 0.22), (1.3, -0.95, 0.28), (1.2, 0.2, 0.16))):
                tw = 1.0 if still else 0.55 + 0.45 * math.sin(2 * math.pi * 1.3 * t + k * 2.1)
                pts = _spark(hx + dx * r, hy + dy * r, s * r * tw)
                out += [("fill", pts, YELLOW, 255), ("line", pts + [pts[0]], ORANGE, 0.5)]
        if "hearts" in fx:
            for k, dx in enumerate((-1.15, 1.2)):
                v = 0 if still else ((t * 0.45 + k * 0.5) % 1)
                pts = _heart(hx + dx * r + 0.1 * r * math.sin(6 * v), hy - (0.6 + 0.9 * v) * r, 0.35 * r * (1 - 0.3 * v), 36)
                out += [("fill", pts, RED, int(255 * (1 - v ** 3)))]
        if "q" in fx:
            qx, qy, s = hx + 1.2 * r, hy - 1.05 * r, 0.5 * r
            hook = _ellipse(qx, qy, 0.32 * s, 0.32 * s, 14, math.pi * 1.05, math.pi * 2.4)
            hook += [(qx, qy + 0.62 * s)]
            out += [("line", hook, BLUE, 1.0), ("fill", _ellipse(qx, qy + 0.95 * s, 0.09 * s, 0.09 * s, 10), BLUE, 255)]
        if "bang" in fx:
            bx, by_ = hx + 1.15 * r, hy - 1.1 * r
            pop = 1.0 if still else 1 + 0.12 * math.sin(2 * math.pi * 2 * t)
            out += [("line", [(bx, by_ - 0.4 * r * pop), (bx + 0.03 * r, by_ + 0.12 * r)], RED, 1.6),
                    ("fill", _ellipse(bx + 0.04 * r, by_ + 0.32 * r, 0.08 * r, 0.08 * r, 10), RED, 255)]
        return out

    def _hair(self, g):
        """Soft rounded cap with scalloped crown + side-swept fringe, and the old Tí curl on top (brand)."""
        hx, hy, r = g["head"]
        cs, sn = math.cos(g["tiltr"]), math.sin(g["tiltr"])
        lag = g["S"]["hair"]

        def P(pts):
            return [(hx + r * (x * cs - y * sn), hy + r * (x * sn + y * cs)) for x, y in pts]

        crown = []
        a0, a1, n = math.pi * 0.96, math.pi * 2.04, 60
        for k in range(n + 1):
            u = k / n
            a = a0 + (a1 - a0) * u
            rr = 1.05 + 0.085 * abs(math.sin(5 * math.pi * u))
            x, y = rr * math.cos(a), rr * 0.98 * math.sin(a)
            crown.append((x + lag * 0.05 * max(0.0, -y - 0.6), y))
        fringe = _curve3((1.02, 0.02), (0.82, -0.42), (0.45, -0.56), 8)
        fringe += _curve3((0.45, -0.56), (0.28, -0.42), (0.1, -0.5), 6)[1:]
        fringe += _curve3((0.1, -0.5), (-0.35, -0.72), (-0.8, -0.52), 8)[1:]
        fringe += _curve3((-0.8, -0.52), (-0.95, -0.3), (-1.03, 0.04), 6)[1:]
        cap = P(crown + fringe)
        tx = 0.05 + lag * 0.12
        curl = _curve3((0.02, -1.08), (tx - 0.12, -1.42), (tx + 0.14, -1.48), 10)
        curl += _curve3((tx + 0.14, -1.48), (tx + 0.24, -1.32), (tx + 0.08, -1.3), 6)[1:]
        return cap + [cap[0]], P(curl)

    def _layers(self, t, still=False):
        """Z-ordered drawing list: ("line", pts, colour, width, pen_rank) / ("fill", pts, colour, alpha, appear_frac)
        / ("disc", (x, y, rr), fill_colour, outline_w, appear_frac)."""
        g = self._geom(t, still)
        h, w, c = self.h, self.w, self.color
        hx, hy, r = g["head"]
        Ls = []
        # legs + shoes
        for side, (hp, kn, ft) in g["legs"]:
            Ls.append(("line", _curve3(hp, kn, ft, 10), c, w * 1.25, 5))
            shoe = _ellipse(ft[0] + side * 0.03 * h, ft[1] - 0.012 * h, 0.055 * h, 0.03 * h, 20)
            Ls.append(("fill", shoe, c, 255, 0.7))
        # back arms (those not in front of the face)
        front = [i for i, (x, y) in enumerate(g["hands"]) if math.hypot(x - hx, y - hy) < r * 1.15]
        arm_layers = []
        for i, (sh, el, hd) in enumerate(g["arms"]):
            arm = [("line", _curve3(sh, el, hd, 10), c, w * 1.1, 4),
                   ("disc", (hd[0], hd[1], 0.034 * h), SKIN, w * 0.75, 0.75)]
            arm_layers.append(arm)
        for i in range(2):
            if i not in front:
                Ls += arm_layers[i]
        # torso (shirt)
        Ls.append(("fill", g["torso"], SHIRT, 255, 0.55))
        Ls.append(("line", g["torso"] + [g["torso"][0]], c, w, 3))
        # head
        head = _ellipse(hx, hy, r, r * 0.97, 48, -1.9, -1.9 + 2 * math.pi * 1.02)
        Ls.append(("fill", head[:-1], SKIN, 255, 0.12))
        Ls.append(("line", head, c, w, 0))
        # ears
        for s in (-1, 1):
            ear = _ellipse(hx + s * 0.98 * r, hy + 0.08 * r, 0.13 * r, 0.17 * r, 14, s * 0 - math.pi / 2 if s > 0 else math.pi / 2,
                           math.pi / 2 if s > 0 else math.pi * 1.5)
            Ls.append(("fill", ear, SKIN, 255, 0.12))
            Ls.append(("line", ear, c, w * 0.8, 0))
        hair, curl = self._hair(g)
        Ls.append(("fill", hair, HAIR, 255, 0.3))
        Ls.append(("line", hair, c, w * 0.8, 1))
        Ls.append(("line", curl, c, w * 0.9, 1))
        # scarf (accent) with a trailing tail
        nx, ny = g["neck"]
        lag = g["S"]["tail"]
        sc = [(nx - 0.08 * h, ny - 0.012 * h), (nx + 0.08 * h, ny - 0.012 * h), (nx + 0.07 * h, ny + 0.022 * h),
              (nx - 0.07 * h, ny + 0.022 * h)]
        band = _curve3(sc[0], (nx, ny + 0.002 * h), sc[1], 8) + _curve3(sc[2], (nx, ny + 0.04 * h), sc[3], 8)
        tail = [(nx + 0.03 * h, ny + 0.01 * h), (nx + (0.1 + 0.02 * lag) * h, ny + (0.05 + 0.015 * lag) * h),
                (nx + (0.11 + 0.035 * lag) * h, ny + (0.1 - 0.01 * lag) * h), (nx + 0.06 * h, ny + 0.03 * h)]
        tail = _curve3(tail[0], tail[1], tail[2], 6) + [tail[3]]
        Ls.append(("fill", tail, self.accent, 255, 0.6))
        Ls.append(("line", tail + [tail[0]], c, w * 0.75, 2))
        Ls.append(("fill", band, self.accent, 255, 0.6))
        Ls.append(("line", band + [band[0]], c, w * 0.75, 2))
        # face
        face, a = self._face(g, t, still)
        for kind, pts, col, v in face:
            Ls.append(("line", pts, col, max(3, w * v), 6) if kind == "line" else ("fill", pts, col, v, 0.85))
        for i in front:
            Ls += arm_layers[i]
        for kind, pts, col, v in self._halo(g, t, still, a):
            Ls.append(("line", pts, col, max(3, w * v), 7) if kind == "line" else ("fill", pts, col, v, 0.9))
        return Ls

    # -- Element interface --
    def _wob(self, pts, i):
        ph = self.seed * 2.3 + i * 1.91
        q, s = [], 0.0
        rp = _resample(pts, 6.0)
        for k, pt in enumerate(rp):
            if k:
                s += math.dist(pt, rp[k - 1])
            q.append((pt[0] + 0.7 * math.sin(s * 0.03 + ph), pt[1] + 0.7 * math.sin(s * 0.037 + ph * 1.3)))
        return q

    def _prepared(self, p):
        t = self.start if p < 1 else self.now
        Ls = self._layers(t, still=p < 1)
        lines = [(i, L) for i, L in enumerate(Ls) if L[0] == "line"]
        order = sorted(lines, key=lambda il: (il[1][4], il[0]))
        polys = [self._wob(L[1], i) for i, L in order]
        vis_map, tip = {}, None
        if p < 1:
            vis, tip = _partial(polys, p)
            for (i, _L), v in zip(order, vis):
                vis_map[i] = v
        else:
            vis_map = {i: q for (i, _L), q in zip(order, polys)}
            tip = polys[-1][-1]
        return Ls, vis_map, tip, (polys[0][0] if polys else (self.cx, self.base))

    def draw(self, img, p, ox, oy):
        Ls, vis, _tip, _ = self._prepared(p)
        d = ImageDraw.Draw(img)
        P = lambda q: [((x - ox) * SS, (y - oy) * SS) for x, y in q]
        for i, L in enumerate(Ls):
            kind = L[0]
            if kind == "fill":
                if p >= L[4] and len(L[1]) > 2:
                    d.polygon(P(L[1]), fill=L[2] + (int(L[3]),))
            elif kind == "disc":
                if p >= L[4]:
                    (x, y), rr = P([L[1][:2]])[0], L[1][2] * SS
                    ow = max(2, int(L[3] * SS))
                    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=L[2] + (255,), outline=self.color + (255,), width=ow)
            elif i in vis:
                q, wd, col = P(vis[i]), int(L[3] * SS), L[2] + (255,)
                if len(q) > 1:
                    d.line(q, fill=col, width=wd, joint="curve")
                for x, y in (q[0], q[-1]):
                    d.ellipse((x - wd / 2, y - wd / 2, x + wd / 2, y + wd / 2), fill=col)

    def tip(self, p):
        return self._prepared(min(p, 0.999))[2]

    def first_point(self):
        return self._prepared(0.0)[3]


# ---------- 3D gold ingot ----------
GOLD_TOP = (255, 226, 122)
GOLD_FRONT = (246, 186, 48)
GOLD_SIDE = (214, 148, 38)
GOLD_EDGE = (150, 96, 20)


class GoldIngot(Element):
    """Ingot (truncated pyramid) in a light oblique view: bright top, front face, darker right side. The pen draws
    the outline (0-0.55), colour sweeps in (0.55-0.85), then the stamp + shine (0.85-1); a glint pops now and then."""
    animated = True

    def __init__(self, cx, cy, w, start, width, seed, glint=True):
        self.cx, self.cy, self.w, self.start, self.width = cx, cy, w, start, width
        self.seed, self.glint, self.now = seed, glint, start
        H, D, kx, ky = 0.3 * w, 0.44 * w, 0.36, 0.42
        y0 = cy + 0.5 * (H + ky * D) - 0.06 * w   # front-bottom edge so the whole thing centres on (cx, cy)
        x0 = cx - 0.5 * kx * D
        Pj = lambda X, Y, Z: (x0 + X + kx * Z, y0 - Y - ky * Z)
        tw, z0, z1 = 0.37 * w, 0.17 * D, 0.83 * D
        self.v = dict(fbl=Pj(-w / 2, 0, 0), fbr=Pj(w / 2, 0, 0), bbr=Pj(w / 2, 0, D),
                      ftl=Pj(-tw, H, z0), ftr=Pj(tw, H, z0), btr=Pj(tw, H, z1), btl=Pj(-tw, H, z1))
        v = self.v
        self.front = [v["fbl"], v["fbr"], v["ftr"], v["ftl"]]
        self.top = [v["ftl"], v["ftr"], v["btr"], v["btl"]]
        self.side = [v["fbr"], v["bbr"], v["btr"], v["ftr"]]
        self.left = [v["fbl"], v["ftl"], v["btl"]]   # sliver of the left slope above the front-left edge
        self.dur = max(0.9, min(1.6, 1.4 * self._outline_len() / PEN_SPEED))
        pts = list(v.values())
        pad = width + 0.1 * w
        self.bbox = (int(min(x for x, _ in pts) - pad), int(min(y for _, y in pts) - pad),
                     int(max(x for x, _ in pts) + pad), int(max(y for _, y in pts) + pad))

    def _outline(self):
        v = self.v
        sil = [v["fbl"], v["fbr"], v["bbr"], v["btr"], v["btl"], v["ftl"], v["fbl"]]
        return [sil, [v["ftl"], v["ftr"], v["fbr"]], [v["ftr"], v["btr"]], [v["ftl"], v["btl"]]]

    def _outline_len(self):
        return sum(_length(p) for p in self._outline())

    def _wob(self, poly, i):
        ph = self.seed * 1.37 + i * 2.1
        q, s = [], 0.0
        rp = _resample(poly, 5.0)
        for k, pt in enumerate(rp):
            if k:
                s += math.dist(pt, rp[k - 1])
            q.append((pt[0] + 0.9 * math.sin(s * 0.02 + ph), pt[1] + 0.9 * math.sin(s * 0.027 + ph * 1.4)))
        return q

    def draw(self, img, p, ox, oy):
        d = ImageDraw.Draw(img)
        P = lambda q: [((x - ox) * SS, (y - oy) * SS) for x, y in q]
        w, v = self.w, self.v
        lerp = lambda a, b, u: (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        cf = min(1.0, max(0.0, (p - 0.55) / 0.3))
        if cf > 0:
            xc = self.bbox[0] + (self.bbox[2] - self.bbox[0]) * cf
            for poly, col in ((self.left, GOLD_SIDE), (self.side, GOLD_SIDE), (self.front, GOLD_FRONT), (self.top, GOLD_TOP)):
                clip = [(min(x, xc), y) for x, y in poly] if cf < 1 else poly
                d.polygon(P(clip), fill=col + (255,))
        if p >= 0.85:
            ew = max(2, int(0.014 * w * SS))
            # lit edge along the front-top rim, darker foot on the front face
            d.line(P([lerp(v["ftl"], v["ftr"], 0.04), lerp(v["ftl"], v["ftr"], 0.96)]), fill=(255, 244, 190, 255), width=ew * 2)
            foot = [lerp(v["fbl"], v["ftl"], 0.0), lerp(v["fbr"], v["ftr"], 0.0), lerp(v["fbr"], v["ftr"], 0.2), lerp(v["fbl"], v["ftl"], 0.2)]
            d.polygon(P(foot), fill=(232, 166, 40, 255))
            # embossed plate on top
            c = lambda u, t_: lerp(lerp(v["ftl"], v["ftr"], u), lerp(v["btl"], v["btr"], u), t_)
            plate = [c(0.22, 0.25), c(0.78, 0.25), c(0.78, 0.75), c(0.22, 0.75), c(0.22, 0.25)]
            d.line(P(plate), fill=(212, 160, 60, 255), width=ew, joint="curve")
            # two slanted shine streaks on the front face
            for a_, b_, wd in ((0.12, 0.2, 3.2), (0.25, 0.29, 1.8)):
                lo = lerp(lerp(v["fbl"], v["fbr"], a_), lerp(v["ftl"], v["ftr"], a_), 0.22)
                hi = lerp(lerp(v["fbl"], v["fbr"], b_), lerp(v["ftl"], v["ftr"], b_), 0.82)
                d.line(P([lo, hi]), fill=(255, 250, 225, 255), width=max(3, int(wd * ew)))
            font = wb.hand_font(max(14, int(0.13 * w * SS)))
            fc = lerp(lerp(v["fbl"], v["fbr"], 0.6), lerp(v["ftl"], v["ftr"], 0.6), 0.48)
            d.text(((fc[0] - ox) * SS, (fc[1] - oy) * SS), "999.9", font=font, fill=GOLD_EDGE + (255,), anchor="mm")
        polys = [self._wob(q, i) for i, q in enumerate(self._outline())]
        vis = _partial(polys, p / 0.55)[0] if p < 0.55 else polys
        wd = int(self.width * SS)
        for q in vis:
            q = P(q)
            if len(q) > 1:
                d.line(q, fill=INK + (255,), width=wd, joint="curve")
            for x, y in (q[0], q[-1]):
                d.ellipse((x - wd / 2, y - wd / 2, x + wd / 2, y + wd / 2), fill=INK + (255,))
        if p >= 1 and self.glint:
            ph = ((self.now - self.end) + self.seed * 0.77) % 3.2
            if ph < 0.6:
                s = math.sin(math.pi * ph / 0.6)
                gx, gy = lerp(v["btr"], v["ftr"], 0.15)
                pts = _spark(gx, gy, 0.12 * w * s)
                d.polygon(P(pts), fill=(255, 255, 255, 255))
                d.line(P(pts + [pts[0]]), fill=(255, 220, 120, 255), width=max(2, int(SS * 1.5)))

    def tip(self, p):
        if p < 0.55:
            return _partial(self._outline(), p / 0.55)[1]
        x0, y0, x1, y1 = self.bbox
        if p < 0.85:
            u = (p - 0.55) / 0.3
            return x0 + (x1 - x0) * u, (y0 + y1) / 2 + 0.3 * (y1 - y0) * math.sin(u * 40)
        return self.v["ftl"][0] + 0.2 * self.w, self.v["ftl"][1] + 0.1 * self.w

    def first_point(self):
        return self.v["fbl"]


def gold_bar(b, cx, cy, w, start, width=7):
    """Drop-in for scenes.gold_bar: same footprint centre, returns an element with .end."""
    return b._add(GoldIngot(cx, cy, w, start, max(5, width - 1), seed=len(b.items) + 1))


def gold_pile(b, cx, cy, w, start, step=0.5):
    gold_bar(b, cx - 0.5 * w, cy, w, start)
    gold_bar(b, cx + 0.52 * w, cy, w, start + step)
    return gold_bar(b, cx + 0.06 * w, cy - 0.36 * w, w, start + 2 * step)


def _stick(self, cx, base, height, start, pose="stand", mood="happy", accent=ORANGE, color=INK, dur=None,
           look=None, seed=None, drawn=True):
    seed = len(self.items) + 1 if seed is None else seed
    return self._add(Ti(cx, base, height, start, pose, mood, accent, color, dur, look, seed, drawn))


def install():
    wb.Board.stick = _stick
    wb.STICK_POSES.update(POSES)
    try:  # a project's scenes.py may use gold_bar / gold_pile helpers; patch them in when it is importable
        import scenes as sc
    except ImportError:
        return None
    sc.gold_bar = gold_bar
    sc.gold_pile = gold_pile
    return sc
