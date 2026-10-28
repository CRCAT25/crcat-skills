"""Stickman host (v01): big round white head with a tiny dot face, a flat-colour T-shirt, thin black stick limbs —
the "người que" look. Motion, poses, moods, effects and the Board.stick API
come from mascot_v04.TiPeep; only the body proportions, the clothes and the vector face change.
Call install() BEFORE importing scenes. Extra kwarg on Board.stick: shirt=(r, g, b) for a second character.
"""
import math
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from PIL import ImageDraw  # noqa: E402

import mascot_v04 as m4  # noqa: E402
from mascot_v03 import _rot2, _curve3, wb  # noqa: E402
from whiteboard import ORANGE, SS, INK, _ellipse, _heart, _star  # noqa: E402

LINE = (24, 24, 28)
HEAD = (255, 255, 255)
SHIRT_BLUE = (74, 136, 226)
SHIRT_RED = (226, 72, 60)
SHIRT_GREEN = (64, 168, 104)
SHIRT_YELLOW = (246, 196, 54)
MOUTH_IN = (150, 40, 44)
TONGUE = (238, 110, 110)
BLUSH = (246, 150, 150)
HR = 0.205                # head radius, of total height
POSES = m4.POSES
MOODS = m4.MOODS

def _ln(d, q, fill, width, joint=None):
    """Polyline with round joins AND round caps (PIL leaves square, gappy ends)."""
    col, w = fill, int(max(1, width))
    d.line(q, fill=col, width=w, joint="curve")
    r = w / 2
    for x, y in (q[0], q[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)


def _outlined(d, shapes, fill, ow):
    """Fill several polygons as ONE silhouette with a single continuous outline: first every shape grown by the
    outline width in black (stroke + round dots on each vertex, so no seam or notch), then all fills on top —
    shared edges between the shapes disappear."""
    r = ow
    for q in shapes:
        d.polygon(q, fill=LINE + (255,))
        d.line(q + q[:1], fill=LINE + (255,), width=int(2 * ow), joint="curve")
        for x, y in q:
            d.ellipse((x - r, y - r, x + r, y + r), fill=LINE + (255,))
    for q in shapes:
        d.polygon(q, fill=fill + (255,))


# mood -> (eyes, mouth, brows, blush)
FACE = {
    "happy": ("dot", "smile", None, False),
    "neutral": ("dot", "small", None, False),
    "talk": ("dot", "talk", None, False),
    "calm": ("closed", "small", None, False),
    "shock": ("wide", "o", "up", False),
    "sad": ("dot", "frown", "sad", False),
    "worried": ("dot", "wavy", "sad", False),
    "think": ("dot", "side", "one", False),
    "angry": ("dot", "frown", "angry", False),
    "furious": ("dot", "shout", "angry", False),
    "love": ("heart", "open", None, True),
    "proud": ("arc", "smile", None, True),
    "laugh": ("arc", "open", None, True),
    "wink": ("wink", "smile", None, True),
    "cry": ("cry", "shout", "sad", False),
    "smug": ("lid", "smirk", "one", False),
    "confused": ("odd", "wavy", "one", False),
    "starstruck": ("star", "open", None, True),
    "money": ("dot", "grin", None, True),
    "nervous": ("dot", "teeth", "sad", False),
    "determined": ("dot", "flat", "angry", False),
    "fear": ("wide", "wavy", "sad", False),
    "tired": ("lid", "flat", None, False),
    "serious": ("dot", "flat", "flat", False),
    "yummy": ("arc", "tongue", None, True),
    "grin": ("dot", "grin", None, False),
}
assert set(FACE) == set(MOODS)


class StickPeep(m4.TiPeep):
    shirt = SHIRT_BLUE

    def _geom(self, t, still=False):
        S = self._state(t, still)
        h = self.h
        thigh, shin = 0.125 * h, 0.12 * h
        drops = [thigh * _rot2(a, s)[1] + shin * _rot2(b, s)[1] for s, (a, b) in zip((-1, 1), S["legs"])]
        X, base, sq = S["x"], self.base, S["sq"]
        sx = 1 / math.sqrt(max(0.5, sq))
        T = lambda p: (X + (p[0] - X) * sx, base - (base - p[1]) * sq + S["y"])
        hip = (X, base - 0.01 * h - max(drops))
        L = math.radians(S["lean"])
        ax, ay = math.sin(L), -math.cos(L)
        px, py = math.cos(L), math.sin(L)
        tl = 0.2 * h
        neck = (hip[0] + tl * ax, hip[1] + tl * ay)
        arms, hands, legs = [], [], []
        for side, (a, b) in zip((-1, 1), S["arms"]):
            sh = (neck[0] + side * 0.07 * h * px - 0.025 * h * ax, neck[1] + side * 0.07 * h * py - 0.025 * h * ay)
            ux, uy = _rot2(a, side)
            el = (sh[0] + 0.1 * h * ux, sh[1] + 0.1 * h * uy)
            fx, fy = _rot2(b, side)
            hd = (el[0] + 0.1 * h * fx, el[1] + 0.1 * h * fy)
            arms.append([T(sh), T(el), T(hd)])
            hands.append(T(hd))
        for side, (a, b) in zip((-1, 1), S["legs"]):
            hp = (hip[0] + side * 0.035 * h * px, hip[1] + side * 0.035 * h * py)
            ux, uy = _rot2(a, side)
            kn = (hp[0] + thigh * ux, hp[1] + thigh * uy)
            fx, fy = _rot2(b, side)
            ft = (kn[0] + shin * fx, kn[1] + shin * fy)
            legs.append((side, [T(hp), T(kn), T(ft)]))

        def tp(s_, w_, along):
            return T((hip[0] + along * tl * ax + s_ * w_ * h * px, hip[1] + along * tl * ay + s_ * w_ * h * py))
        # T-shirt: hem slightly wider than the waist, rounded shoulders, small neck dip
        shirt = (_curve3(tp(-1, 0.075, 0.0), tp(-1, 0.07, 0.5), tp(-1, 0.078, 0.88), 16)
                 + _curve3(tp(-1, 0.078, 0.88), tp(-1, 0.07, 1.0), tp(-1, 0.03, 1.0), 12)[1:]
                 + _curve3(tp(-1, 0.03, 1.0), tp(0, 0, 0.93), tp(1, 0.03, 1.0), 16)[1:]
                 + _curve3(tp(1, 0.03, 1.0), tp(1, 0.07, 1.0), tp(1, 0.078, 0.88), 12)[1:]
                 + _curve3(tp(1, 0.078, 0.88), tp(1, 0.07, 0.5), tp(1, 0.075, 0.0), 16)[1:])
        HT = math.radians(S["lean"] + S["tilt"])
        pv = T((neck[0], neck[1] + S["nod"]))
        R = HR * h
        hc = (pv[0] + math.sin(HT) * 0.93 * R, pv[1] - math.cos(HT) * 0.93 * R * sq)
        return dict(S=S, head=(hc[0], hc[1], R), pivot=pv, neck=T(neck), hip=T(hip), arms=arms, hands=hands,
                    legs=legs, shirt=shirt, tiltr=HT, sx=sx, sq=sq)

    # -- face --
    def _face(self, d, g, t, still, P, ow):
        hx, hy, r = g["head"]
        S = g["S"]
        eyes, mouth, brows, blush = FACE[S["mood"]]
        fdir = self.facing(t)
        HT = g["tiltr"]
        c, s = math.cos(HT), math.sin(HT)
        lx = fdir * 0.12  # features shift toward the facing side

        def Q(pts):  # head-local (units of r) -> screen, rotated with the head
            return P([(hx + (u * c - v * s) * r, hy + (u * s + v * c) * r) for u, v in pts])

        lw = int(max(2, 0.6 * ow))
        blink = (not still) and eyes in ("dot", "wide", "odd") and ((t + self.seed * 0.77) % 3.7) < 0.12
        ey, ex = -0.02, 0.3
        for k, side in enumerate((-1, 1)):
            u0 = lx + side * ex
            kind = eyes
            if kind == "wink":
                kind = "arc" if side == fdir else "dot"
            if kind == "odd":
                kind = "dot"
            if blink:
                kind = "closed"
            if kind == "dot":
                rr = 0.085 * (1.25 if eyes == "odd" and side > 0 else 1.0)
                d.polygon(Q(_ellipse(u0, ey, rr, rr * 1.15, 20)), fill=LINE + (255,))
            elif kind == "wide":
                d.polygon(Q(_ellipse(u0, ey, 0.13, 0.15, 24)), fill=LINE + (255,))
                d.polygon(Q(_ellipse(u0 + 0.04, ey - 0.05, 0.04, 0.04, 20)), fill=HEAD + (255,))
            elif kind == "arc":  # happy ^ eyes
                _ln(d, Q(_curve3((u0 - 0.1, ey + 0.04), (u0, ey - 0.12), (u0 + 0.1, ey + 0.04), 20)),
                       fill=LINE + (255,), width=lw, joint="curve")
            elif kind == "closed":
                _ln(d, Q(_curve3((u0 - 0.1, ey), (u0, ey + 0.08), (u0 + 0.1, ey), 20)),
                       fill=LINE + (255,), width=lw, joint="curve")
            elif kind == "cry":
                _ln(d, Q(_curve3((u0 - 0.1, ey + 0.04), (u0, ey - 0.06), (u0 + 0.1, ey + 0.04), 20)),
                       fill=LINE + (255,), width=lw, joint="curve")
            elif kind == "lid":
                d.polygon(Q(_ellipse(u0, ey + 0.03, 0.085, 0.06, 16, 0, math.pi)), fill=LINE + (255,))
                _ln(d, Q([(u0 - 0.11, ey + 0.02), (u0 + 0.11, ey + 0.02)]), fill=LINE + (255,), width=lw)
            elif kind == "heart":
                d.polygon(Q(_heart(u0, ey, 0.28)), fill=(226, 60, 70, 255))
            elif kind == "star":
                d.polygon(Q(_star(u0, ey, 0.15, 0.065)), fill=(246, 190, 40, 255))
                _ln(d, Q(_star(u0, ey, 0.15, 0.065) + _star(u0, ey, 0.15, 0.065)[:1]), fill=LINE + (255,),
                       width=max(1, lw // 2))
            if kind == "cry" or (eyes == "cry" and blink):
                self._tear(d, Q, u0, ey, side, t, still, max(1, lw // 2))
            # brows
            if brows:
                bu, bv = u0, ey - 0.24
                tilt = {"sad": 0.07 * side, "angry": -0.08 * side, "up": 0.0, "flat": 0.0,
                        "one": 0.0}[brows] * (1 if fdir > 0 else 1)
                lift = -0.08 if brows == "up" or (brows == "one" and side == fdir) else 0.0
                if brows == "one" and side != fdir:
                    continue
                _ln(d, Q([(bu - 0.1, bv + lift - tilt), (bu + 0.1, bv + lift + tilt)]), fill=LINE + (255,),
                       width=lw)
            if blush:
                d.polygon(Q(_ellipse(u0 + side * 0.07, ey + 0.2, 0.1, 0.05, 16)), fill=BLUSH + (150,))
        # mouth
        mu, mv_ = lx, 0.32
        F = LINE + (255,)
        if mouth == "talk":
            mouth = "open" if (not still and math.sin(2 * math.pi * 3.1 * t + self.seed) > 0.2) else "small"
        if mouth in ("smile", "small"):
            w = 0.22 if mouth == "smile" else 0.13
            dep = 0.1 if mouth == "smile" else 0.05
            _ln(d, Q(_curve3((mu - w, mv_ - dep / 2), (mu, mv_ + dep), (mu + w, mv_ - dep / 2), 20)), fill=F,
                   width=lw, joint="curve")
        elif mouth == "frown":
            _ln(d, Q(_curve3((mu - 0.17, mv_ + 0.06), (mu, mv_ - 0.07), (mu + 0.17, mv_ + 0.06), 20)), fill=F,
                   width=lw, joint="curve")
        elif mouth in ("flat", "side"):
            off = fdir * 0.08 if mouth == "side" else 0.0
            _ln(d, Q([(mu + off - 0.12, mv_), (mu + off + 0.12, mv_ - (0.03 if mouth == "side" else 0))]), fill=F,
                   width=lw)
        elif mouth == "smirk":
            _ln(d, Q(_curve3((mu - 0.14, mv_), (mu + 0.02, mv_ + 0.03), (mu + fdir * 0.17, mv_ - 0.07), 20)),
                   fill=F, width=lw, joint="curve")
        elif mouth == "o":
            d.polygon(Q(_ellipse(mu, mv_ + 0.02, 0.08, 0.11, 20)), fill=MOUTH_IN + (255,), outline=F)
        elif mouth == "wavy":
            pts = [(mu - 0.17 + 0.34 * k / 16, mv_ + 0.03 * math.sin(k / 16 * 4 * math.pi)) for k in range(17)]
            _ln(d, Q(pts), fill=F, width=lw, joint="curve")
        elif mouth in ("open", "grin", "tongue", "teeth"):
            top = mv_ - 0.02
            dmouth = _ellipse(mu, top, 0.2, 0.17, 24, 0, math.pi) + [(mu - 0.2, top)]
            d.polygon(Q(dmouth), fill=MOUTH_IN + (255,))
            if mouth in ("open", "tongue"):
                d.polygon(Q(_ellipse(mu, top + 0.13, 0.11, 0.05, 16)), fill=TONGUE + (255,))
            if mouth in ("grin", "teeth"):
                d.polygon(Q([(mu - 0.19, top), (mu + 0.19, top), (mu + 0.17, top + 0.06), (mu - 0.17, top + 0.06)]),
                          fill=HEAD + (255,))
            _ln(d, Q(dmouth), fill=F, width=lw, joint="curve")
        elif mouth == "shout":  # open frown
            dm = _ellipse(mu, mv_ + 0.12, 0.15, 0.14, 24, math.pi, 2 * math.pi) + [(mu + 0.15, mv_ + 0.12)]
            d.polygon(Q(dm), fill=MOUTH_IN + (255,))
            _ln(d, Q(dm), fill=F, width=lw, joint="curve")

    def _tear(self, d, Q, u0, ey, side, t, still, ow):
        """Cartoon tear stream on the cheek right under one eye (head-local, so it tilts with the head and never
        leaves the face), plus a small drop sliding down it."""
        top, bot = ey + 0.07, 0.78
        wob = 0 if still else 0.015 * math.sin(2 * math.pi * 2.4 * t + side)
        n = 10
        left, right = [], []
        for k in range(n + 1):
            f = k / n
            v = top + f * (bot - top)
            w = 0.035 + 0.035 * f  # widens toward the jaw
            c = u0 + wob * f
            left.append((c - w, v))
            right.append((c + w, v))
        stream = left + _ellipse(u0 + wob, bot, 0.07, 0.04, 10, 0, math.pi)[::-1][1:-1] + right[::-1]
        d.polygon(Q(stream), fill=m4.TEAR + (235,))
        _ln(d, Q(left), fill=LINE + (255,), width=ow)
        _ln(d, Q(right), fill=LINE + (255,), width=ow)
        p = 0.35 if still else (t * 1.3 + (0.5 if side > 0 else 0)) % 1
        dv = top + 0.1 + p * (bot - top - 0.1)
        d.polygon(Q(_ellipse(u0 + wob * p, dv, 0.028, 0.04, 10)), fill=HEAD + (200,))

    def _halo(self, g, t, still):
        out = super()._halo(g, t, still)
        if "stream" in MOODS[g["S"]["mood"]][1]:  # tears are drawn on the face instead
            out = [o for o in out if o[2] != m4.TEAR]
        return out

    def _render(self, img, t, still, ox, oy):
        g = self._geom(t, still)
        h = self.h
        ow = max(3, 0.011 * h) * SS
        lw = max(4, 0.022 * h) * SS
        d = ImageDraw.Draw(img)
        P = lambda q: [((x - ox) * SS, (y - oy) * SS) for x, y in q]
        fdir = self.facing(t)

        def stroke(pts, w=lw):
            q = P(pts)
            d.line(q, fill=LINE + (255,), width=int(w), joint="curve")
            for x, y in q:  # round dot on every vertex: no wedge gaps at bends, round caps at the ends
                d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=LINE + (255,))

        for side, (hp, kn, ft) in g["legs"]:
            stroke(_curve3(hp, kn, ft, 24))
            # small shoe: a short rounded stroke pointing to the facing side
            stroke([ft, (ft[0] + fdir * 0.035 * h, ft[1])], lw * 1.35)
        hx, hy, r = g["head"]
        # hands touching the face (think, facepalm, cheeks, hold_up) go in front of the head
        front = [i for i, (x, y) in enumerate(g["hands"]) if math.hypot(x - hx, y - hy) < r * 1.15]
        for i, (sh, el, hd) in enumerate(g["arms"]):
            stroke(_curve3(sh, el, hd, 24))
        # T-shirt body + both short sleeves + round shoulders as ONE outlined silhouette
        parts = [P(g["shirt"])]
        for side, (sh, el, hd) in zip((-1, 1), g["arms"]):
            b = (sh[0] + 0.45 * (el[0] - sh[0]), sh[1] + 0.45 * (el[1] - sh[1]))
            L_ = math.dist(sh, b) or 1
            nx, ny = -(b[1] - sh[1]) / L_, (b[0] - sh[0]) / L_
            w0, w1 = 0.03 * h, 0.026 * h
            parts.append(P([(sh[0] + nx * w0, sh[1] + ny * w0), (b[0] + nx * w1, b[1] + ny * w1),
                            (b[0] - nx * w1, b[1] - ny * w1), (sh[0] - nx * w0, sh[1] - ny * w0)]))
            c = (sh[0] + 0.2 * (b[0] - sh[0]), sh[1] + 0.2 * (b[1] - sh[1]))
            parts.append(P(_ellipse(c[0], c[1], 0.028 * h, 0.028 * h, 24)))
        _outlined(d, parts, self.shirt, ow)
        # head: black disc then white disc -> perfectly even outline with no seam
        e = ow * 1.15 / 2 / SS
        d.polygon(P(_ellipse(hx, hy, r * g["sx"] + e, r * g["sq"] + e, 144)), fill=LINE + (255,))
        d.polygon(P(_ellipse(hx, hy, r * g["sx"] - e, r * g["sq"] - e, 144)), fill=HEAD + (255,))
        self._face(d, g, t, still, P, ow)
        for i in front:
            sh, el, hd = g["arms"][i]
            stroke(_curve3(el, el, hd, 8))
            x, y = P([hd])[0]
            rr = 0.024 * h * SS
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=LINE + (255,))
        for kind, pts, col, v in self._halo(g, t, still):
            if kind == "line":
                d.line(P(pts), fill=col + (255,), width=int(max(3, self.w * v) * SS), joint="curve")
            elif len(pts) > 2:
                d.polygon(P(pts), fill=col + (int(v),))


def _stick(self, cx, base, height, start, pose="stand", mood="happy", accent=ORANGE, color=INK, dur=None,
           look=None, seed=None, drawn=True, shirt=None):
    seed = len(self.items) + 1 if seed is None else seed
    s = StickPeep(cx, base, height, start, pose, mood, accent, color, dur, look, seed, drawn)
    if shirt is not None:
        s.shirt = shirt
    return self._add(s)


def install():
    sc = m4.install()
    wb.Board.stick = _stick
    return sc
