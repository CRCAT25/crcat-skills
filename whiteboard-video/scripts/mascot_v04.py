"""v04 host "Tí": Open Peeps head + faces (CC0, Pablo Stanley; sprites from build_ti_assets.py) on a body drawn in
the same flat-colour / thick-ink style. Keeps the Stick API (act / walk / jump / last / head_at / hand_at, the pose
names) so `install()` swaps it into Board.stick exactly like v03. The 3D gold ingot comes from mascot_v03.

Motion: poses blend with an overshoot, the head turns on the neck (tilt, nod, bounce), faces cross-fade in 0.18 s
with a squash-and-stretch, walks flip the head toward the walking direction, effects (sparkles, hearts, ?, !, sweat,
tears, coins) float around the head. Call install() BEFORE importing scenes_v02 / render_shorts.
"""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import mascot_v03 as mv
from mascot_v03 import _back, _rot2, _curve3, wb, fk
from whiteboard import BLUE, GREEN, ORANGE, RED, SS, YELLOW, INK, Element, _ellipse

ASSETS = Path(__file__).resolve().parent.parent / "assets/ti-peeps"
SKIN = (241, 198, 165)
SHIRT = (90, 146, 214)
PANTS = (52, 60, 84)
SHOE = (252, 250, 246)
LINE = (22, 20, 20)
TEAR = (120, 186, 245)
COIN = (250, 196, 60)

# head sprite frame (1408 px canvas): crop box and the neck pivot the head turns around
CROP = (360, 110, 1250, 1230)
PIVOT = (800 - CROP[0], 1080 - CROP[1])
HEAD_PX = 1020           # hair top -> chin, in sprite px
HEAD_H = 0.46            # of total height
# head-local centre (for effects) relative to the pivot, in units of h
HC = (0.0, -0.205)
HR = 0.175

POSES = mv.POSES
# mood -> (Open Peeps face, effects)
MOODS = {
    "happy": ("smile", ()),
    "neutral": ("explaining", ()),
    "talk": ("explaining", ()),
    "calm": ("calm", ()),
    "shock": ("awe", ("bang", "sweat")),
    "sad": ("solemn", ()),
    "worried": ("concerned", ("sweat",)),
    "think": ("suspicious", ()),
    "angry": ("rage", ("vein",)),
    "furious": ("veryAngry", ("vein",)),
    "love": ("lovingGrin1", ("hearts",)),
    "proud": ("cute", ("sparkle",)),
    "laugh": ("smileLOL", ()),
    "wink": ("cheeky", ("sparkle",)),
    "cry": ("concernedFear", ("stream",)),
    "smug": ("contempt", ()),
    "confused": ("blank", ("q",)),
    "starstruck": ("lovingGrin2", ("sparkle",)),
    "money": ("smileBig", ("coins",)),
    "nervous": ("hectic", ("sweat",)),
    "determined": ("driven", ("sparkle",)),
    "fear": ("fear", ("sweat",)),
    "tired": ("tired", ()),
    "serious": ("serious", ()),
    "yummy": ("eatingHappy", ()),
    "grin": ("smileTeethGap", ()),
}


@lru_cache(maxsize=None)
def _sprite(name):
    return Image.open(ASSETS / f"{name}.png").convert("RGBA").crop(CROP)


@lru_cache(maxsize=256)
def _scaled(name, px):
    sp = _sprite(name)
    k = px / HEAD_PX
    return sp.resize((max(2, round(sp.width * k)), max(2, round(sp.height * k))), Image.Resampling.LANCZOS)


def _tube(d, pts, width, fill, ow):
    """Thick limb: black outline + flat fill, round caps."""
    for col, w in ((LINE, width + 2 * ow), (fill, width)):
        d.line(pts, fill=col + (255,), width=int(w), joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=col + (255,))


def _poly(d, pts, fill, ow):
    d.polygon(pts, fill=fill + (255,))
    d.line(pts + [pts[0], pts[1]], fill=LINE + (255,), width=int(ow), joint="curve")


class TiPeep(mv.Ti):
    animated = True
    BLEND = 0.42
    FACE_BLEND = 0.18

    def __init__(self, cx, base, h, start, pose, mood, accent, color, dur, look, seed, drawn=True):
        assert pose in POSES and mood in MOODS, (pose, mood)
        self.cx, self.base, self.h, self.start = cx, base, h, start
        self.accent, self.color = accent, color
        self.keys = [(start, pose, mood, look)]
        self.moves, self.jumps = [], []
        self.seed = seed
        self.w = max(3, round(h * 0.012))
        self.now = start
        self.drawn = drawn
        self.dur = dur if dur is not None else (max(1.0, min(1.8, h / 320)) if drawn else 0.0)

    def act(self, t, pose=None, mood=None, look=None):
        _, p0, m0, l0 = max((k for k in self.keys if k[0] <= t), key=lambda k: k[0], default=self.keys[0])
        assert (pose or p0) in POSES and (mood or m0) in MOODS, (pose, mood)
        self.keys.append((t, pose or p0, mood or m0, look if look is not None else (None if pose else l0)))
        self.keys.sort(key=lambda k: k[0])
        if pose == "shock":
            self.jumps.append((t, 0.38, 0.08))
        return self

    @property
    def bbox(self):
        xs = [self.cx] + [m[3] for m in self.moves]
        up = max([j[2] for j in self.jumps], default=0) + 0.3
        return (int(min(xs) - 0.75 * self.h), int(self.base - (1.0 + up) * self.h),
                int(max(xs) + 0.75 * self.h), int(self.base + 0.06 * self.h))

    def facing(self, t):
        f = 1
        for t0, t1, x0, x1 in self.moves:
            if t0 <= t and x1 != x0:
                f = 1 if x1 > x0 else -1
        keys = [k for k in self.keys if k[0] <= t] or self.keys[:1]
        lk = keys[-1][3]
        if lk is not None and abs(lk[0]) > 0.01 and not any(t0 <= t < t1 for t0, t1, *_ in self.moves):
            f = 1 if lk[0] > 0 else -1
        return f

    # -- state --
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
        uf = 1.0 if (cur is prev or cur[2] == prev[2]) else fk.smooth(dt / self.FACE_BLEND)
        mood = cur[2]
        x, y, sq, nod = self.x_at(t), 0.0, 1.0, 0.0
        if not still:
            ph = self.seed * 1.7
            y += 0.006 * self.h * math.sin(2 * math.pi * 0.45 * t + ph)
            sq += 0.01 * math.sin(2 * math.pi * 0.45 * t + ph)
            tilt += 3.0 * math.sin(2 * math.pi * 0.23 * t + ph)
            nod += 0.008 * self.h * math.sin(2 * math.pi * 0.37 * t + ph * 0.7)
            if cur is not prev and dt < 0.42:
                v = dt / 0.42
                sq -= 0.07 * math.sin(math.pi * min(1, v / 0.45)) if v < 0.45 else -0.03 * math.sin(math.pi * (v - 0.45) / 0.55)
                nod -= 0.02 * self.h * math.sin(math.pi * v) * (1 if cur[2] != prev[2] else 0.4)
            pose = cur[1]
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
                tilt -= 5 * k
            elif mood in ("cry", "fear"):
                x += 1.2 * math.sin(2 * math.pi * 7 * t)
            elif mood == "nervous":
                x += 1.0 * math.sin(2 * math.pi * 11 * t)
            elif mood in ("angry", "furious"):
                y += 0.004 * self.h * math.sin(2 * math.pi * 12 * t)
            elif mood in ("think", "confused"):
                tilt += 5
            elif mood in ("sad", "tired"):
                tilt -= 3
                nod += 0.012 * self.h
            for t0, t1, x0, x1 in self.moves:
                if t0 <= t < t1:
                    phs = 2 * math.pi * 2.4 * (t - t0)
                    d = 1 if x1 > x0 else -1
                    lean = 6 * d
                    for side, leg in zip((-1, 1), legs):
                        lift = max(0.0, math.sin(phs + (0 if side < 0 else math.pi)))
                        leg[0] += 26 * lift
                        leg[1] -= 30 * lift
                    for side, arm in zip((-1, 1), arms):
                        sw = 22 * math.sin(phs + (math.pi if side < 0 else 0))
                        arm[0] += sw
                        arm[1] += sw
                    y -= 0.025 * self.h * abs(math.sin(phs))
            for tj, dj, hj in self.jumps:
                pre = 0.14
                if tj - pre <= t < tj:
                    sq -= 0.1 * math.sin(math.pi / 2 * (t - tj + pre) / pre)
                elif tj <= t < tj + dj:
                    v = (t - tj) / dj
                    y -= hj * self.h * math.sin(math.pi * v)
                    sq += 0.08 * math.cos(math.pi * v) if v < 0.5 else -0.02
                    for leg in legs:
                        leg[0] += 16 * math.sin(math.pi * v)
                        leg[1] -= 24 * math.sin(math.pi * v)
                elif tj + dj <= t < tj + dj + 0.18:
                    sq -= 0.08 * math.sin(math.pi * (t - tj - dj) / 0.18)
        return dict(arms=arms, legs=legs, lean=lean, tilt=tilt, x=x, y=y, sq=sq, nod=nod, mood=mood,
                    pmood=prev[2], uf=uf, fxa=uf)

    def _geom(self, t, still=False):
        S = self._state(t, still)
        h = self.h
        thigh, shin = 0.125 * h, 0.115 * h
        drops = [thigh * _rot2(a, s)[1] + shin * _rot2(b, s)[1] for s, (a, b) in zip((-1, 1), S["legs"])]
        X, base, sq = S["x"], self.base, S["sq"]
        sx = 1 / math.sqrt(max(0.5, sq))
        T = lambda p: (X + (p[0] - X) * sx, base - (base - p[1]) * sq + S["y"])
        hip = (X, base - 0.035 * h - max(drops))
        L = math.radians(S["lean"])
        ax, ay = math.sin(L), -math.cos(L)
        px, py = math.cos(L), math.sin(L)
        tl = 0.235 * h
        neck = (hip[0] + tl * ax, hip[1] + tl * ay)
        pivot = (neck[0] + 0.03 * h * ax, neck[1] + 0.03 * h * ay + S["nod"])
        arms, hands, legs = [], [], []
        for side, (a, b) in zip((-1, 1), S["arms"]):
            sh = (neck[0] + side * 0.098 * h * px - 0.03 * h * ax, neck[1] + side * 0.098 * h * py - 0.03 * h * ay)
            ux, uy = _rot2(a, side)
            el = (sh[0] + 0.105 * h * ux, sh[1] + 0.105 * h * uy)
            fx, fy = _rot2(b, side)
            hd = (el[0] + 0.1 * h * fx, el[1] + 0.1 * h * fy)
            arms.append([T(sh), T(el), T(hd)])
            hands.append(T(hd))
        for side, (a, b) in zip((-1, 1), S["legs"]):
            hp = (hip[0] + side * 0.05 * h * px, hip[1] + side * 0.05 * h * py)
            ux, uy = _rot2(a, side)
            kn = (hp[0] + thigh * ux, hp[1] + thigh * uy)
            fx, fy = _rot2(b, side)
            ft = (kn[0] + shin * fx, kn[1] + shin * fy)
            legs.append((side, [T(hp), T(kn), T(ft)]))

        def tp(s_, w_, along):
            return T((hip[0] + along * tl * ax + s_ * w_ * h * px, hip[1] + along * tl * ay + s_ * w_ * h * py))
        # shirt: left hip -> left shoulder -> collar dip -> right shoulder -> right hip -> hem
        shirt = (_curve3(tp(-1, 0.1, 0.0), tp(-1, 0.112, 0.5), tp(-1, 0.105, 0.9), 10)
                 + _curve3(tp(-1, 0.105, 0.9), tp(-1, 0.09, 1.02), tp(-1, 0.05, 1.03), 6)[1:]
                 + _curve3(tp(-1, 0.05, 1.03), tp(0, 0, 0.84), tp(1, 0.05, 1.03), 10)[1:]
                 + _curve3(tp(1, 0.05, 1.03), tp(1, 0.09, 1.02), tp(1, 0.105, 0.9), 6)[1:]
                 + _curve3(tp(1, 0.105, 0.9), tp(1, 0.112, 0.5), tp(1, 0.1, 0.0), 10)[1:]
                 + _curve3(tp(1, 0.1, 0.0), tp(0, 0, -0.04), tp(-1, 0.1, 0.0), 8)[1:])
        collar = _curve3(tp(-1, 0.05, 1.03), tp(0, 0, 0.84), tp(1, 0.05, 1.03), 10)
        neckq = [tp(-1, 0.04, 0.85), tp(-1, 0.042, 1.18), tp(1, 0.042, 1.18), tp(1, 0.04, 0.85)]
        seat = [tp(-1, 0.1, 0.06), tp(1, 0.1, 0.06), T((hip[0] + 0.1 * h * px, hip[1] + 0.03 * h)),
                T((hip[0] - 0.1 * h * px, hip[1] + 0.03 * h))]
        HT = math.radians(S["lean"] + S["tilt"])
        pv = T(pivot)
        hc = (pv[0] + (HC[0] * math.cos(HT) - HC[1] * math.sin(HT)) * h,
              pv[1] + (HC[0] * math.sin(HT) + HC[1] * math.cos(HT)) * h * sq)
        return dict(S=S, head=(hc[0], hc[1], HR * h), pivot=pv, neck=T(neck), hip=T(hip), arms=arms, hands=hands,
                    legs=legs, shirt=shirt, collar=collar, neckq=neckq, seat=seat, tiltr=HT, sx=sx, sq=sq)

    # -- drawing --
    def _head_image(self, g, t):
        """Head + cross-faded face, squashed, flipped to the facing side and rotated around the neck pivot."""
        S = g["S"]
        px = round(HEAD_H * self.h * SS)
        im = _scaled("head", px).copy()
        f_cur, f_prev = MOODS[S["mood"]][0], MOODS[S["pmood"]][0]
        uf = S["uf"]
        if uf < 1 and f_prev != f_cur:
            prev = _scaled(f"face-{f_prev}", px).copy()
            prev.putalpha(prev.getchannel("A").point(lambda v: int(v * (1 - uf))))
            im.alpha_composite(prev)
        cur = _scaled(f"face-{f_cur}", px)
        if uf < 1 and f_prev != f_cur:
            cur = cur.copy()
            cur.putalpha(cur.getchannel("A").point(lambda v: int(v * uf)))
        im.alpha_composite(cur)
        k = px / HEAD_PX
        pvx, pvy = PIVOT[0] * k, PIVOT[1] * k
        if self.facing(t) < 0:
            im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            pvx = im.width - pvx
        sx, sq = g["sx"], g["sq"]
        if abs(sx - 1) > 0.004 or abs(sq - 1) > 0.004:
            im = im.resize((max(2, round(im.width * sx)), max(2, round(im.height * sq))), Image.Resampling.BICUBIC)
            pvx, pvy = pvx * sx, pvy * sq
        # pad so the pivot is the centre, then rotate about it
        R = int(math.hypot(max(pvx, im.width - pvx), max(pvy, im.height - pvy))) + 2
        pad = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
        pad.alpha_composite(im, (int(R - pvx), int(R - pvy)))
        deg = math.degrees(g["tiltr"])
        if abs(deg) > 0.05:
            pad = pad.rotate(-deg, resample=Image.Resampling.BICUBIC, center=(R, R))
        return pad, R

    def _halo(self, g, t, still):
        """Effects around the head: v03 sparkles / hearts / ? / ! plus sweat, tear streams, anger vein, coins."""
        S = g["S"]
        fx = MOODS[S["mood"]][1]
        a = S["fxa"]
        out = []
        if a <= 0.4:
            return out
        hx, hy, r = g["head"]
        fdir = self.facing(t)
        old = dict(g, S=dict(S, face=dict(fx=tuple(x for x in fx if x in ("sparkle", "hearts", "q", "bang")))))
        out += [(k, p, c, v) for k, p, c, v in mv.Ti._halo(self, old, t, still, a)]
        if "sweat" in fx:
            v = 0 if still else (t * 0.7) % 1
            sx_, sy_ = hx - fdir * 0.95 * r, hy - 0.35 * r + 0.5 * r * v
            drop = _ellipse(sx_, sy_ + 0.05 * r, 0.1 * r, 0.13 * r, 16, -0.4, math.pi + 0.4) + [(sx_, sy_ - 0.2 * r)]
            out += [("fill", drop, TEAR, int(255 * (1 - v ** 4))), ("line", drop + [drop[0]], LINE, 0.6)]
        if "stream" in fx:
            for k, ex in enumerate((0.12, 0.62)):
                ex_ = hx + fdir * ex * r
                ey = hy + 0.25 * r
                wob = 0 if still else 0.04 * r * math.sin(2 * math.pi * 3 * t + k)
                pts = [(ex_, ey), (ex_ + fdir * 0.05 * r + wob, ey + 0.45 * r), (ex_ - fdir * 0.02 * r, ey + 0.85 * r)]
                out += [("line", _curve3(*pts, 10), TEAR, 2.2)]
                v = 0 if still else (t * 1.6 + k * 0.5) % 1
                out += [("fill", _ellipse(ex_ - fdir * 0.02 * r, ey + (0.9 + 0.6 * v) * r, 0.07 * r, 0.09 * r, 12), TEAR,
                         int(255 * (1 - v)))]
        if "vein" in fx:
            vx, vy = hx + fdir * 0.75 * r, hy - 0.95 * r
            pop = 1.0 if still else 1 + 0.15 * abs(math.sin(2 * math.pi * 2.5 * t))
            for ang in (0.4, 2.0, 3.6, 5.2):
                c = (vx + 0.1 * r * pop * math.cos(ang), vy + 0.1 * r * pop * math.sin(ang))
                out += [("line", _curve3(c, (vx + 0.24 * r * pop * math.cos(ang + 0.5), vy + 0.24 * r * pop * math.sin(ang + 0.5)),
                                         (vx + 0.2 * r * pop * math.cos(ang + 1.0), vy + 0.2 * r * pop * math.sin(ang + 1.0)), 6), RED, 1.4)]
        if "coins" in fx:
            for k, (dx, ph) in enumerate(((-1.25, 0.0), (1.3, 0.33), (-0.9, 0.66))):
                v = 0 if still else (t * 0.55 + ph) % 1
                cx_, cy_ = hx + dx * r, hy - (0.3 + 0.9 * v) * r
                rr = 0.17 * r
                sq_ = abs(math.cos(2 * math.pi * 1.2 * t + k)) if not still else 1.0
                coin = _ellipse(cx_, cy_, rr * max(0.2, sq_), rr, 20)
                al = int(255 * min(1, 4 * (1 - v)))
                out += [("fill", coin, COIN, al), ("line", coin + [coin[0]], (176, 120, 20), 0.8)]
                if sq_ > 0.5:
                    out += [("line", [(cx_, cy_ - 0.55 * rr), (cx_, cy_ + 0.55 * rr)], (176, 120, 20), 0.6)]
        return out

    def _render(self, img, t, still, ox, oy):
        g = self._geom(t, still)
        h = self.h
        ow = max(3, 0.011 * h) * SS
        d = ImageDraw.Draw(img)
        P = lambda q: [((x - ox) * SS, (y - oy) * SS) for x, y in q]
        hx, hy, r = g["head"]
        front = [i for i, (x, y) in enumerate(g["hands"]) if math.hypot(x - hx, y - hy) < r * 1.25]
        arm_w, leg_w = 0.052 * h * SS, 0.068 * h * SS

        def arm(i):
            sh, el, hd = g["arms"][i]
            cuff = (sh[0] + 0.62 * (el[0] - sh[0]), sh[1] + 0.62 * (el[1] - sh[1]))
            _tube(d, P(_curve3(cuff, el, hd, 8)), arm_w * 0.72, SKIN, ow)
            x, y = P([hd])[0]
            rr = 0.027 * h * SS
            d.ellipse((x - rr - ow, y - rr - ow, x + rr + ow, y + rr + ow), fill=LINE + (255,))
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=SKIN + (255,))
            # short sleeve: a flared quad from the shoulder to the cuff, outlined, straight cuff edge
            a, b = sh, cuff
            L_ = math.dist(a, b) or 1
            nx, ny = -(b[1] - a[1]) / L_, (b[0] - a[0]) / L_
            w0, w1 = 0.5 * arm_w / SS, 0.62 * arm_w / SS
            back = (a[0] - (b[0] - a[0]) / L_ * w0 * 0.6, a[1] - (b[1] - a[1]) / L_ * w0 * 0.6)
            sleeve = (_curve3((a[0] + nx * w0, a[1] + ny * w0), back, (a[0] - nx * w0, a[1] - ny * w0), 8)
                      + [(b[0] - nx * w1, b[1] - ny * w1), (b[0] + nx * w1, b[1] + ny * w1)])
            _poly(d, P(sleeve), SHIRT, ow)
            # merge the sleeve top into the shirt
            x, y = P([(a[0] + 0.2 * (b[0] - a[0]), a[1] + 0.2 * (b[1] - a[1]))])[0]
            rr = 0.4 * arm_w
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=SHIRT + (255,))

        fdir = self.facing(t)
        # legs + shoes
        for side, (hp, kn, ft) in g["legs"]:
            sx_, sy_ = ft[0] + fdir * 0.03 * h, ft[1] + 0.005 * h
            shoe = _ellipse(sx_, sy_, 0.058 * h, 0.03 * h, 24, math.pi, 2 * math.pi) + [(sx_ + 0.058 * h, sy_ + 0.012 * h),
                                                                                       (sx_ - 0.058 * h, sy_ + 0.012 * h)]
            _tube(d, P(_curve3(hp, kn, ft, 8)), leg_w, PANTS, ow)
            _poly(d, P(shoe), SHOE, ow)
        _poly(d, P(g["seat"]), PANTS, ow)
        # neck, shirt, collar, then the arms (in front of the torso, behind the head)
        _poly(d, P(g["neckq"]), SKIN, ow)
        _poly(d, P(g["shirt"]), SHIRT, ow * 1.1)
        d.line(P(g["collar"]), fill=LINE + (255,), width=int(ow * 1.1), joint="curve")
        for i in range(2):
            if i not in front:
                arm(i)
        # head sprite
        pad, R = self._head_image(g, t)
        pv = g["pivot"]
        img.alpha_composite(pad, (int((pv[0] - ox) * SS - R), int((pv[1] - oy) * SS - R)))
        d = ImageDraw.Draw(img)
        for i in front:
            arm(i)
        for kind, pts, col, v in self._halo(g, t, still):
            if kind == "line":
                q = P(pts)
                wd = max(3, self.w * v) * SS
                d.line(q, fill=col + (255,), width=int(wd), joint="curve")
            elif len(pts) > 2:
                d.polygon(P(pts), fill=col + (int(v),))

    # -- Element interface --
    def _box(self):
        return (self.cx - 0.32 * self.h, self.base - 1.0 * self.h, self.cx + 0.32 * self.h, self.base + 0.04 * self.h)

    def _edge(self, p, bands=5):
        k = min(bands - 1, int(p * bands))
        f = p * bands - k
        return k, (1 - f if k % 2 else f)

    def draw(self, img, p, ox, oy):
        if p >= 1:
            self._render(img, self.now, False, ox, oy)
            return
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        self._render(layer, self.start, True, ox, oy)
        x0, y0, x1, y1 = [(v - o) * SS for v, o in zip(self._box(), (ox, oy, ox, oy))]
        bands = 5
        bh = (y1 - y0) / bands
        k, f = self._edge(p, bands)
        mask = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(mask)
        md.rectangle((0, 0, img.size[0], y0 + k * bh), fill=255)
        xa, xb = (x0 - 40 * SS, x0 + f * (x1 - x0)) if k % 2 == 0 else (x0 + f * (x1 - x0), x1 + 40 * SS)
        md.rectangle((xa, y0 + k * bh, xb, y0 + (k + 1) * bh), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(6 * SS))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        img.alpha_composite(layer)

    def tip(self, p):
        x0, y0, x1, y1 = self._box()
        k, f = self._edge(min(p, 0.999))
        bh = (y1 - y0) / 5
        return x0 + (x1 - x0) * f, y0 + bh * (k + 0.5 + 0.3 * math.sin(p * 80))

    def first_point(self):
        return self.tip(0.0)


def _stick(self, cx, base, height, start, pose="stand", mood="happy", accent=ORANGE, color=INK, dur=None,
           look=None, seed=None, drawn=True):
    seed = len(self.items) + 1 if seed is None else seed
    return self._add(TiPeep(cx, base, height, start, pose, mood, accent, color, dur, look, seed, drawn))


def install():
    sc = mv.install()
    wb.Board.stick = _stick
    return sc
