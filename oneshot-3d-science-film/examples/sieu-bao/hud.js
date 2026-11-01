// On-screen cues that show what the narration states (figures, processes), on a transparent 2D canvas over the film.
// Keyed in FINAL time (the 3D film plays 1.15x slower: film t = final t x 1.15). Laid out in 1920x1080 units.
// Cue times are scene time / 1.15: the film.js holds stretch them like the picture.
// window.hud(t) draws one frame and returns a PNG data URL, or '' when nothing is on screen.
import { unhold } from './film.js';
import { LAND } from './land110.js';
const SPEED = 1.15;
// N(n): a timeline time (as heard in the final cut) in cue time; used for cues timed to the rewritten narration
const N = (n) => unhold(n * SPEED) / SPEED;
const q = new URLSearchParams(location.search);
const W = +q.get('w') || 1920, H = +q.get('h') || 1080;
const C = document.getElementById('c'), X = C.getContext('2d');
C.width = W; C.height = H;
const FONT = '-apple-system, "SF Pro Display", "Helvetica Neue", sans-serif';
const INK = '#f6f3ec', DIM = 'rgba(246,243,236,0.82)', WARM = '#ffb04a', HOT = '#ff5f4c', COOL = '#7fdcff', OK = '#8ce89a';

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const sm = (a, b, t) => { const k = clamp((t - a) / (b - a)); return k * k * (3 - 2 * k); };
const eo = (k) => 1 - Math.pow(1 - clamp(k), 3);
// visible from a to b with fades
const win = (t, a, b, fi = 0.4, fo = 0.5) => Math.min(sm(a, a + fi, t), 1 - sm(b - fo, b, t));
const keys = (ks, t) => {
  if (t <= ks[0][0]) return ks[0][1];
  for (let i = 1; i < ks.length; i++) if (t < ks[i][0]) return lerp(ks[i - 1][1], ks[i][1], sm(ks[i - 1][0], ks[i][0], t));
  return ks[ks.length - 1][1];
};
const hash = (i) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
// Vietnamese number format: 6.300 and 26,5
const fmt = (n, d = 0) => { const [a, b] = n.toFixed(d).split('.'); return a.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (b ? ',' + b : ''); };

function T(s, x, y, size = 32, o = {}) {
  X.font = `${o.w || 600} ${size}px ${FONT}`;
  X.textAlign = o.a || 'left'; X.textBaseline = o.b || 'alphabetic';
  X.save(); X.fillStyle = o.c || INK;
  // a wide soft halo so text reads on bright sea and cloud without a box behind it
  if (o.sh !== 0) { X.shadowColor = 'rgba(0,0,0,0.6)'; X.shadowBlur = size * 0.7; X.shadowOffsetY = 0; X.fillText(s, x, y); }
  // a thin dark rim keeps small coloured labels legible on white cloud and foam
  X.shadowColor = 'transparent'; X.lineJoin = 'round'; X.strokeStyle = 'rgba(0,0,0,0.42)';
  X.lineWidth = Math.max(1.5, size * 0.11); X.strokeText(s, x, y);
  X.shadowColor = 'rgba(0,0,0,0.55)'; X.shadowBlur = o.sh ?? 6; X.shadowOffsetY = 2;
  X.fillText(s, x, y);
  const w = X.measureText(s).width; X.restore();
  return w;
}
// panels were dropped: everything sits straight on the picture (kept as a no-op so layouts still read)
function P() {}
function pill(s, x, y, size, bg, fg = INK) {
  X.font = `800 ${size}px ${FONT}`;
  const w = X.measureText(s).width + size * 1.1, h = size * 1.6;
  if (bg) { X.save(); X.beginPath(); X.roundRect(x, y - h / 2, w, h, h / 2);
    X.shadowColor = bg; X.shadowBlur = size * 0.9; X.fillStyle = bg; X.fill(); X.restore(); }
  // without a pill the label needs the full halo to stand off white cloud
  T(s, x + w / 2, y + 1, size, { a: 'center', b: 'middle', w: 800, c: fg, ...(bg ? { sh: 0 } : {}) });
  return w;
}
function head(x, y, a, c, hd) {
  X.fillStyle = c; X.beginPath(); X.moveTo(x, y);
  X.lineTo(x - hd * Math.cos(a - 0.45), y - hd * Math.sin(a - 0.45));
  X.lineTo(x - hd * Math.cos(a + 0.45), y - hd * Math.sin(a + 0.45)); X.closePath(); X.fill();
}
function A(x1, y1, x2, y2, c = INK, w = 6, hd = 20) {
  const a = Math.atan2(y2 - y1, x2 - x1);
  X.strokeStyle = c; X.lineWidth = w; X.lineCap = 'round';
  X.beginPath(); X.moveTo(x1, y1); X.lineTo(x2 - Math.cos(a) * hd * 0.7, y2 - Math.sin(a) * hd * 0.7); X.stroke();
  head(x2, y2, a, c, hd);
}
// arc arrow from angle a0 to a1 (a1 < a0 turns counter-clockwise on screen)
function AA(cx, cy, r, a0, a1, c = INK, w = 6, hd = 22) {
  const ccw = a1 < a0, back = (hd * 0.7) / r;
  X.strokeStyle = c; X.lineWidth = w; X.lineCap = 'round';
  X.beginPath(); X.arc(cx, cy, r, a0, ccw ? a1 + back : a1 - back, ccw); X.stroke();
  const tip = a1 + (ccw ? -0.5 : 0.5) * hd / r;
  head(cx + r * Math.cos(tip), cy + r * Math.sin(tip), tip + (ccw ? -Math.PI / 2 : Math.PI / 2), c, hd);
}
function cue(alpha, fn) {
  if (alpha <= 0.002) return;
  drew = true; X.save(); X.globalAlpha = alpha;
  // no panels behind cues: a soft dark shadow under every line, bar and icon keeps them off bright sky and foam
  X.shadowColor = 'rgba(0,0,0,0.5)'; X.shadowBlur = 12 * W / 1920; X.shadowOffsetY = 2 * W / 1920;
  const k = 1 - eo(alpha);
  if (k > 0.01) { X.translate(0, 16 * k); X.filter = `blur(${(6 * k * W / 1920).toFixed(2)}px)`; }
  fn(); X.restore();
}

// ---- reusable instruments ----
function gauge(cx, cy, r, v, max, label, o = {}) {
  const a0 = Math.PI * 0.75, a1 = Math.PI * 2.25, k = clamp(v / max);
  X.lineCap = 'round'; X.lineWidth = 18;
  X.strokeStyle = 'rgba(255,255,255,0.14)'; X.beginPath(); X.arc(cx, cy, r, a0, a1); X.stroke();
  const g = X.createConicGradient(a0, cx, cy);
  g.addColorStop(0, COOL); g.addColorStop(0.42, WARM); g.addColorStop(0.75, HOT); g.addColorStop(1, HOT);
  X.strokeStyle = g; X.beginPath(); X.arc(cx, cy, r, a0, a0 + (a1 - a0) * Math.max(k, 0.001)); X.stroke();
  X.lineWidth = 3; X.strokeStyle = 'rgba(255,255,255,0.5)';
  for (let s = 0; s <= max; s += 50) {
    const a = a0 + (a1 - a0) * (s / max);
    X.beginPath(); X.moveTo(cx + Math.cos(a) * (r - 22), cy + Math.sin(a) * (r - 22)); X.lineTo(cx + Math.cos(a) * (r - 32), cy + Math.sin(a) * (r - 32)); X.stroke();
  }
  T(fmt(v), cx, cy + 22, r * 0.52, { a: 'center', w: 800, c: o.c || INK });
  T('km/h', cx, cy + 62, 26, { a: 'center', c: DIM });
  T(label, cx, cy + r + 6, 24, { a: 'center', w: 700, c: DIM });
}
function thermo(x, top, bot, v, lo, hi) {
  const y = (c) => lerp(bot, top, (c - lo) / (hi - lo)), tw = 30;
  X.beginPath(); X.roundRect(x - tw / 2, top - 14, tw, bot - top + 30, tw / 2); X.fillStyle = 'rgba(255,255,255,0.14)'; X.fill();
  X.beginPath(); X.arc(x, bot + 34, 36, 0, Math.PI * 2); X.fill();
  const col = v < 26.5 ? COOL : v < 29 ? WARM : HOT;
  X.fillStyle = col;
  X.beginPath(); X.roundRect(x - tw / 2 + 7, y(v), tw - 14, bot - y(v) + 20, 8); X.fill();
  X.beginPath(); X.arc(x, bot + 34, 27, 0, Math.PI * 2); X.fill();
  return y;
}
// top view of the storm with the island; iy = island position from the centre in radii (negative = ahead, top)
// a satellite-like top view: cloud bands spiral into a clear eye over dark ocean; drawn once, then turned each frame
let CLOUD = null;
function cloudTex(r) {
  const c = new OffscreenCanvas(2 * r, 2 * r), g = c.getContext('2d');
  const blob = (x, y, rad, al) => {
    const q = g.createRadialGradient(x, y, 0, x, y, rad);
    q.addColorStop(0, `rgba(250,252,255,${al})`); q.addColorStop(1, 'rgba(250,252,255,0)');
    g.fillStyle = q; g.beginPath(); g.arc(x, y, rad, 0, Math.PI * 2); g.fill();
  };
  // dense core around the eye, then four arms that loosen outward
  const core = g.createRadialGradient(r, r, r * 0.12, r, r, r * 0.62);
  core.addColorStop(0, 'rgba(250,252,255,0.97)'); core.addColorStop(0.6, 'rgba(240,246,255,0.8)'); core.addColorStop(1, 'rgba(240,246,255,0)');
  g.fillStyle = core; g.fillRect(0, 0, 2 * r, 2 * r);
  for (let i = 0; i < 2200; i++) {
    const k = i % 4, s = Math.pow(hash(i * 3.1), 0.8);
    const rr = r * (0.22 + 0.8 * s) * (1 + 0.08 * (hash(i * 7.7) - 0.5));
    const a = k * Math.PI / 2 + s * 3.2 + 0.7 * (hash(i * 5.3) - 0.5) * (0.4 + s);
    blob(r + rr * Math.cos(a), r + rr * Math.sin(a), r * (0.05 + 0.09 * (1 - s) * hash(i * 1.9)), 0.16 * (1 - 0.6 * s));
  }
  // the eye: a clean hole with a bright rim (the eyewall)
  g.globalCompositeOperation = 'destination-out';
  const e = g.createRadialGradient(r, r, 0, r, r, r * 0.15);
  e.addColorStop(0, 'rgba(0,0,0,1)'); e.addColorStop(0.7, 'rgba(0,0,0,0.95)'); e.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = e; g.fillRect(0, 0, 2 * r, 2 * r);
  g.globalCompositeOperation = 'source-over';
  return c;
}
function islandPath(x, y, s) {
  X.beginPath();
  for (let i = 0; i < 24; i++) {
    const a = i / 24 * Math.PI * 2, k = 1 + 0.28 * (hash(i + 4) - 0.5) + 0.18 * Math.sin(a * 2 + 1);
    const px = x + Math.cos(a) * s * 1.45 * k, py = y + Math.sin(a) * s * 0.85 * k;
    i ? X.lineTo(px, py) : X.moveTo(px, py);
  }
  X.closePath();
}
function radar(cx, cy, r, t, iy, wall) {
  if (!CLOUD || CLOUD.width !== 2 * r) CLOUD = cloudTex(r);
  X.save();
  X.beginPath(); X.arc(cx, cy, r, 0, Math.PI * 2);
  const sea = X.createRadialGradient(cx, cy, 0, cx, cy, r);
  sea.addColorStop(0, '#16507f'); sea.addColorStop(1, '#0a2c4d');
  X.fillStyle = sea; X.fill(); X.clip();
  // island under the clouds, so the storm visibly passes over it
  const ix = cx, iyy = cy + iy * r;
  islandPath(ix, iyy, 17); X.fillStyle = '#e6d6a6'; X.fill();
  islandPath(ix, iyy, 13); X.fillStyle = '#4f8a45'; X.fill();
  // counter-clockwise turn (northern hemisphere)
  X.save(); X.translate(cx, cy); X.rotate(-t * 0.5); X.globalAlpha = 0.92; X.drawImage(CLOUD, -r, -r); X.restore();
  const pulse = 0.75 + 0.25 * Math.sin(t * 6);
  X.beginPath(); X.arc(cx, cy, r * 0.17, 0, Math.PI * 2);
  X.strokeStyle = wall ? `rgba(255,77,61,${0.9 * pulse})` : 'rgba(255,160,64,0.7)'; X.lineWidth = r * 0.035; X.stroke();
  // vignette towards the rim, so the disc reads as a window onto a larger storm
  const v = X.createRadialGradient(cx, cy, r * 0.7, cx, cy, r);
  v.addColorStop(0, 'rgba(4,10,20,0)'); v.addColorStop(1, 'rgba(4,10,20,0.55)');
  X.fillStyle = v; X.fillRect(cx - r, cy - r, 2 * r, 2 * r);
  X.restore();
  X.beginPath(); X.arc(cx, cy, r, 0, Math.PI * 2); X.strokeStyle = 'rgba(255,255,255,0.3)'; X.lineWidth = 2; X.stroke();
  // the island stays findable through the cloud: a ring and its name; the wind on it is westward ahead of the
  // centre and eastward behind it
  X.beginPath(); X.ellipse(ix, iyy, 30, 22, 0, 0, Math.PI * 2); X.strokeStyle = OK; X.lineWidth = 3; X.setLineDash([7, 6]); X.stroke(); X.setLineDash([]);
  T('Đảo', ix + 36, iyy + 8, 22, { w: 800 });
  const s = clamp(1 - Math.abs(Math.abs(iy) - 0.22) / 0.1);
  if (s > 0.05) { const d = iy < 0 ? -1 : 1, L = 26 + 54 * s; A(ix - d * L / 2 + d * 26, iyy - 40, ix + d * L / 2 + d * 26, iyy - 40, iy < 0 ? WARM : HOT, 6, 18); }
  A(cx + r * 0.78, cy + r * 0.42, cx + r * 0.78, cy - r * 0.02, 'rgba(255,255,255,0.8)', 4, 14);
  T('bão đi', cx + r * 0.78, cy + r * 0.58, 20, { a: 'center', c: INK });
  T('NHÌN TỪ TRÊN CAO', cx, cy - r - 14, 22, { a: 'center', w: 700, c: DIM });
}
// the tropics on a world map centred on the Pacific (lon -30..330), lat 70 N..55 S
let MAP = null;
const MW = 600, MH = 208, LON0 = -30, KX = MW / 360, lat2y = (la) => (70 - la) * KX;
function worldMap() {
  const c = new OffscreenCanvas(MW, MH), g = c.getContext('2d');
  g.fillStyle = '#123f66'; g.fillRect(0, 0, MW, MH);
  g.fillStyle = 'rgba(214,220,200,0.82)';
  for (const off of [0, 360]) for (const ring of LAND) {
    g.beginPath();
    for (let i = 0; i < ring.length; i += 2) { const x = (ring[i] + off - LON0) * KX, y = lat2y(ring[i + 1]); i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.closePath(); g.fill();
  }
  return c;
}
function tropics(t, x, y) {
  if (!MAP) MAP = worldMap();
  X.save(); X.beginPath(); X.roundRect(x, y, MW, MH, 12); X.clip();
  X.drawImage(MAP, x, y);
  // the band opens out from the equator to the two tropics (23.5 N / S)
  const k = eo((t - 9.6) / 1.2), y0 = y + lat2y(0), hb = (lat2y(-23.5) - lat2y(0)) * k;
  X.globalCompositeOperation = 'source-atop';
  const b = X.createLinearGradient(0, y0 - hb, 0, y0 + hb);
  b.addColorStop(0, 'rgba(255,140,50,0.25)'); b.addColorStop(0.5, 'rgba(255,120,40,0.55)'); b.addColorStop(1, 'rgba(255,140,50,0.25)');
  X.fillStyle = b; X.fillRect(x, y0 - hb, MW, 2 * hb);
  X.globalCompositeOperation = 'source-over';
  X.strokeStyle = `rgba(255,170,90,${0.9 * k})`; X.lineWidth = 1.5;
  for (const yy of [y0 - hb, y0 + hb]) { X.beginPath(); X.moveTo(x, yy); X.lineTo(x + MW, yy); X.stroke(); }
  X.strokeStyle = 'rgba(255,255,255,0.85)'; X.lineWidth = 2; X.setLineDash([8, 6]);
  X.beginPath(); X.moveTo(x, y0); X.lineTo(x + MW * sm(9.2, 10.2, t), y0); X.stroke(); X.setLineDash([]);
  X.restore();
  X.beginPath(); X.roundRect(x, y, MW, MH, 12); X.strokeStyle = 'rgba(255,255,255,0.25)'; X.lineWidth = 1.5; X.stroke();
  cue(sm(9.9, 10.4, t), () => T('xích đạo', x + MW - 10, y0 - 8, 20, { a: 'right', w: 700 }));
}
// ---- debris drawn as objects, centred on the origin, about 180 x 110 ----
// corrugated roof sheet, bent along one edge, with rust
function tin() {
  const c = [[-85, -38], [80, -52], [86, 34], [-80, 40]], n = 14;
  const pt = (u, v) => { const tx = lerp(c[0][0], c[1][0], u), ty = lerp(c[0][1], c[1][1], u) - 14 * Math.sin(u * Math.PI) * (1 - v);
    const bx = lerp(c[3][0], c[2][0], u), by = lerp(c[3][1], c[2][1], u); return [lerp(tx, bx, v), lerp(ty, by, v)]; };
  X.save(); X.shadowColor = 'rgba(0,0,0,0.5)'; X.shadowBlur = 18; X.shadowOffsetY = 8;
  for (let i = 0; i < n; i++) {
    const u0 = i / n, u1 = (i + 1) / n, q = [pt(u0, 0), pt(u1, 0), pt(u1, 1), pt(u0, 1)];
    const g = X.createLinearGradient(q[0][0], 0, q[1][0], 0);
    g.addColorStop(0, '#dfe5ea'); g.addColorStop(0.5, '#9aa5ae'); g.addColorStop(1, '#5f6a73');
    X.beginPath(); X.moveTo(...q[0]); for (const p of q.slice(1)) X.lineTo(...p); X.closePath(); X.fillStyle = g; X.fill();
    if (i === 0) { X.shadowColor = 'transparent'; }
  }
  X.restore();
  X.save(); X.beginPath(); X.moveTo(...pt(0, 0)); for (let u = 0.1; u <= 1.001; u += 0.1) X.lineTo(...pt(u, 0)); X.lineTo(...pt(1, 1)); X.lineTo(...pt(0, 1)); X.closePath(); X.clip();
  for (let i = 0; i < 7; i++) { const [x, y] = pt(hash(i + 9), 0.3 + 0.7 * hash(i + 20)), r = 8 + 16 * hash(i + 31);
    const g = X.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, 'rgba(150,72,30,0.6)'); g.addColorStop(1, 'rgba(150,72,30,0)'); X.fillStyle = g; X.fillRect(x - r, y - r, 2 * r, 2 * r); }
  X.restore();
  X.beginPath(); X.moveTo(...pt(0, 0)); for (let u = 0.1; u <= 1.001; u += 0.1) X.lineTo(...pt(u, 0)); X.lineTo(...pt(1, 1)); X.lineTo(...pt(0, 1)); X.closePath();
  X.strokeStyle = 'rgba(40,46,52,0.8)'; X.lineWidth = 2; X.stroke();
}
// a broken-off branch with its leaves
function branch() {
  const limb = (pts, w0, w1) => {
    for (let i = 0; i < pts.length - 1; i++) { X.beginPath(); X.moveTo(...pts[i]); X.lineTo(...pts[i + 1]); X.lineWidth = lerp(w0, w1, i / (pts.length - 1)); X.strokeStyle = '#6b4a2f'; X.lineCap = 'round'; X.stroke(); }
  };
  X.save(); X.shadowColor = 'rgba(0,0,0,0.45)'; X.shadowBlur = 14; X.shadowOffsetY = 6;
  limb([[-90, 30], [-40, 14], [10, 4], [60, -14], [92, -20]], 14, 4);
  limb([[-20, 10], [0, -22], [12, -46]], 7, 3);
  limb([[30, -4], [52, 20], [70, 34]], 6, 2.5);
  X.restore();
  X.beginPath(); X.moveTo(-92, 22); X.lineTo(-86, 30); X.lineTo(-94, 38); X.fillStyle = '#d9c3a0'; X.fill();
  const L = [[12, -46], [4, -40], [20, -38], [70, 34], [62, 26], [78, 28], [92, -20], [84, -28], [96, -10], [60, -14], [50, -24], [40, 0]];
  L.forEach(([x, y], i) => {
    X.save(); X.translate(x, y); X.rotate(hash(i + 2) * Math.PI * 2);
    const g = X.createLinearGradient(-14, 0, 14, 0); g.addColorStop(0, '#2f6b2a'); g.addColorStop(1, hash(i) > 0.5 ? '#7bb34a' : '#4f8f36');
    X.beginPath(); X.ellipse(0, 0, 15, 7, 0, 0, Math.PI * 2); X.fillStyle = g; X.fill();
    X.strokeStyle = 'rgba(20,40,15,0.5)'; X.lineWidth = 1; X.beginPath(); X.moveTo(-13, 0); X.lineTo(13, 0); X.stroke();
    X.restore();
  });
}
// a jagged chunk of brick wall with plaster still on one face
function wall() {
  const sh = [[-80, -40], [-30, -52], [10, -38], [40, -54], [82, -30], [70, 0], [86, 30], [40, 46], [0, 38], [-50, 50], [-84, 22], [-70, -6]];
  const path = () => { X.beginPath(); X.moveTo(...sh[0]); for (const p of sh.slice(1)) X.lineTo(...p); X.closePath(); };
  X.save(); X.shadowColor = 'rgba(0,0,0,0.5)'; X.shadowBlur = 18; X.shadowOffsetY = 8; path(); X.fillStyle = '#d6c7ae'; X.fill(); X.restore();
  X.save(); path(); X.clip();
  for (let r = 0; r < 6; r++) for (let c = -1; c < 7; c++) {
    const x = -90 + c * 32 + (r % 2) * 16, y = -56 + r * 19, h = hash(r * 11 + c);
    X.fillStyle = `rgb(${170 + 30 * h | 0},${78 + 18 * h | 0},${52 + 10 * h | 0})`; X.fillRect(x + 2, y + 2, 28, 15);
  }
  X.beginPath(); X.moveTo(-90, -60); X.lineTo(-20, -60); X.lineTo(-34, -20); X.lineTo(-18, 10); X.lineTo(-44, 60); X.lineTo(-90, 60); X.closePath();
  X.fillStyle = '#e8e2d6'; X.fill();
  X.restore();
  path(); X.strokeStyle = 'rgba(60,40,30,0.7)'; X.lineWidth = 2; X.stroke();
}
const ISLAND = [[96, -0.27], [104.6, -0.25], [166, -0.07], [176, 0.0], [182, 0.07], [190.6, 0.22], [209.5, 0.3]];

// ---- the diagram: warm sea feeds the storm (27.5 - 40) ----
function engine(t) {
  const px = 60, py = 110, pw = 740, ph = 780, cx = px + 300, seaY = py + ph - 120, cloudY = py + 330;
  const s1 = 27.55, s2 = 28.86, s3 = 29.91, s4 = 31.08, s5 = 33.85, s6 = 36.21;
  P(px, py, pw, ph);
  // warm column pushed higher
  const up = sm(s5, s5 + 1.2, t);
  if (up > 0) {
    X.save(); X.globalAlpha *= 0.55 * up;
    const top = lerp(cloudY, py + 120, up);
    X.fillStyle = WARM; X.beginPath();
    X.moveTo(cx - 34, seaY - 40); X.lineTo(cx - 34, top + 70); X.lineTo(cx - 70, top + 70); X.lineTo(cx, top);
    X.lineTo(cx + 70, top + 70); X.lineTo(cx + 34, top + 70); X.lineTo(cx + 34, seaY - 40); X.closePath(); X.fill();
    X.restore();
  }
  // height cools: a temperature bar up the left side
  const cool = sm(s2, s2 + 0.5, t);
  if (cool > 0) {
    X.save(); X.globalAlpha *= cool;
    const g = X.createLinearGradient(0, seaY, 0, py + 60); g.addColorStop(0, WARM); g.addColorStop(1, COOL);
    X.fillStyle = g; X.beginPath(); X.roundRect(px + 34, py + 60, 14, seaY - py - 70, 7); X.fill();
    T('lạnh', px + 41, py + 46, 20, { a: 'center', c: COOL, w: 700 });
    X.restore();
  }
  // sea
  X.save(); X.beginPath(); X.roundRect(px, py, pw, ph, 20); X.clip();
  const sg = X.createLinearGradient(0, seaY, 0, py + ph); sg.addColorStop(0, 'rgba(255,140,60,0.95)'); sg.addColorStop(1, 'rgba(20,70,140,0.95)');
  X.fillStyle = sg; X.beginPath(); X.moveTo(px, py + ph);
  for (let x = px; x <= px + pw; x += 10) X.lineTo(x, seaY + 6 * Math.sin(x * 0.03 + t * 2));
  X.lineTo(px + pw, py + ph); X.closePath(); X.fill();
  X.restore();
  T('Biển 30 °C', px + pw - 30, py + ph - 30, 32, { a: 'right', w: 800 });
  // vapour: rises, cools from warm to white, more of it once the storm draws air in
  const vis = sm(s1, s1 + 0.6, t), more = sm(s6, s6 + 1.5, t), n = Math.round(70 + 90 * more);
  for (let i = 0; i < n; i++) {
    const sp = 0.16 + 0.12 * hash(i) + 0.12 * more, k = (t * sp + hash(i + 50)) % 1;
    const x0 = cx + (hash(i + 99) - 0.5) * 420, x = lerp(x0, cx + (x0 - cx) * 0.45, k * (0.4 + 0.6 * more));
    const y = lerp(seaY - 8, cloudY + 50, k), a = vis * Math.min(1, k * 6, (1 - k) * 4);
    const c = cool > 0 ? (k < 0.5 ? WARM : '#e8f6ff') : '#ffe2c4';
    X.globalAlpha = a * 0.9 * (X.globalAlpha > 0 ? 1 : 0);
    X.fillStyle = c; X.beginPath(); X.arc(x, y, 5, 0, Math.PI * 2); X.fill();
  }
  X.globalAlpha = 1;
  // cloud forms, then grows a tower
  const cl = eo((t - s3) / 0.9), tower = eo((t - s5) / 1.6);
  if (cl > 0) {
    const puffs = [[-120, 25, 55], [-55, -5, 72], [20, -20, 84], [95, 2, 68], [150, 28, 46], [-165, 38, 38], [55, 32, 62], [-15, 38, 66]];
    const tw = [[0, -100, 70], [-20, -170, 62], [10, -230, 56], [-90, -250, 40], [100, -250, 42]];
    X.fillStyle = 'rgba(238,244,250,0.95)';
    for (const [dx, dy, r] of puffs) { X.beginPath(); X.arc(cx + dx * cl, cloudY + dy * cl, r * cl, 0, Math.PI * 2); X.fill(); }
    for (const [dx, dy, r] of tw) if (tower > 0) { X.beginPath(); X.arc(cx + dx, cloudY + dy * tower, r * tower, 0, Math.PI * 2); X.fill(); }
  }
  // latent heat glows out of the cloud
  const heat = sm(s4, s4 + 0.6, t);
  if (heat > 0) {
    X.save(); X.globalAlpha *= heat;
    const gl = X.createRadialGradient(cx, cloudY, 10, cx, cloudY, 150);
    gl.addColorStop(0, 'rgba(255,150,50,0.9)'); gl.addColorStop(1, 'rgba(255,150,50,0)');
    X.fillStyle = gl; X.beginPath(); X.arc(cx, cloudY, 150, 0, Math.PI * 2); X.fill();
    for (let i = 0; i < 6; i++) {
      const a = -Math.PI + (i + 0.5) * Math.PI / 6, k = (t * 0.8 + i * 0.37) % 1, r0 = 120 + 70 * k;
      X.strokeStyle = WARM; X.lineWidth = 5; X.lineCap = 'round'; X.globalAlpha = heat * (1 - k);
      X.beginPath();
      for (let j = 0; j <= 10; j++) { const rr = r0 + j * 4, w = 7 * Math.sin(j * 1.4 + t * 6); X.lineTo(cx + rr * Math.cos(a) - w * Math.sin(a), cloudY + rr * Math.sin(a) + w * Math.cos(a)); }
      X.stroke();
    }
    X.restore();
  }
  // inflow along the sea surface
  const inf = sm(s6, s6 + 0.6, t);
  if (inf > 0) {
    X.save(); X.globalAlpha *= inf;
    const sh = ((t * 60) % 60);
    A(px + 70 + sh * 0.6, seaY - 30, cx - 90, seaY - 30, COOL, 7, 22);
    A(px + 560 - sh * 0.6, seaY - 30, cx + 90, seaY - 30, COOL, 7, 22);
    X.restore();
  }
  // step labels down the right side; the newest one is bright
  const lx = px + 540, steps = [
    [s1, seaY - 90, ['Hơi nước', 'bốc lên'], INK, true],
    [s2, seaY - 205, ['Lên cao', 'nguội đi'], COOL, false],
    [s3, seaY - 320, ['Ngưng', 'thành mây'], INK, false],
    [s4, seaY - 435, ['Nhả ra', 'nhiệt'], WARM, false],
    [s5, seaY - 550, ['Đẩy khí', 'lên cao hơn'], WARM, false],
    [s6, seaY + 52, ['Hút thêm', 'hơi nước'], COOL, false],
  ];
  steps.forEach(([at, y, l, c, arrow], i) => {
    const a = sm(at, at + 0.35, t);
    if (a <= 0) return;
    const next = steps.slice(i + 1).find((s) => s[0] <= t), now = next ? (i === 4 && t < s6 ? 1 : 0.45) : 1;
    X.save(); X.globalAlpha *= a * now;
    if (i === 5) { T(l[0] + ' ' + l[1], cx, y, 30, { a: 'center', w: 800, c: INK }); X.restore(); return; }
    T(l[0], lx, y, 30, { w: 800, c }); T(l[1], lx, y + 36, 30, { w: 800, c });
    if (arrow) A(lx - 30, y + 40, lx - 30, y - 30, c, 5, 16);
    X.restore();
  });
}

// ---- surge cross-section (125 - 133) ----
function surge(t) {
  const ox = 60, oy = 70, pw = 780, ph = 380, sea = oy + 250, bed = oy + 350;
  P(ox, oy, pw, ph);
  const hs = 100 * eo((t - 125.6) / 2.6);
  const ground = (x) => x < ox + 330 ? bed : x < ox + 560 ? lerp(bed, sea - 34, (x - ox - 330) / 230) : sea - 34 - (x - ox - 560) * 0.04;
  const water = (x) => sea - hs * sm(ox + 60, ox + 500, x);
  X.save(); X.beginPath(); X.roundRect(ox, oy, pw, ph, 20); X.clip();
  // ground
  X.fillStyle = '#8a7a5c'; X.beginPath(); X.moveTo(ox + 330, oy + ph);
  for (let x = ox + 330; x <= ox + pw; x += 8) X.lineTo(x, Math.min(ground(x), bed));
  X.lineTo(ox + pw, oy + ph); X.closePath(); X.fill();
  // water between its surface and the ground
  X.fillStyle = 'rgba(40,140,220,0.85)'; X.beginPath();
  const xs = []; for (let x = ox; x <= ox + pw; x += 8) xs.push(x);
  xs.forEach((x, i) => { const y = Math.min(water(x) + 3 * Math.sin(x * 0.05 + t * 3), ground(x)); i ? X.lineTo(x, y) : X.moveTo(x, y); });
  for (let i = xs.length - 1; i >= 0; i--) X.lineTo(xs[i], ground(xs[i]) >= bed ? oy + ph : ground(xs[i]) + 1);
  X.closePath(); X.fill();
  X.restore();
  // house
  const hx = ox + 640, hy = ground(hx);
  X.fillStyle = '#e9e2d0'; X.fillRect(hx - 30, hy - 46, 60, 46);
  X.fillStyle = '#b5523b'; X.beginPath(); X.moveTo(hx - 40, hy - 44); X.lineTo(hx, hy - 78); X.lineTo(hx + 40, hy - 44); X.closePath(); X.fill();
  // normal level
  X.setLineDash([12, 10]); X.strokeStyle = 'rgba(255,255,255,0.7)'; X.lineWidth = 2.5;
  X.beginPath(); X.moveTo(ox + 20, sea); X.lineTo(ox + 600, sea); X.stroke(); X.setLineDash([]);
  T('mực nước bình thường', ox + 30, sea + 34, 22, { c: DIM });
  // wind pushes the water ashore
  const w = sm(125.05, 125.5, t), sh = (t * 90) % 90;
  if (w > 0) {
    X.save(); X.globalAlpha *= w;
    for (let i = 0; i < 3; i++) A(ox + 40 + i * 150 + sh, oy + 70 + (i % 2) * 34, ox + 150 + i * 150 + sh, oy + 70 + (i % 2) * 34, INK, 6, 18);
    T('Gió dồn nước vào bờ', ox + 30, oy + 48, 26, { w: 700 });
    X.restore();
  }
  const lab = sm(127.53, 127.9, t);
  if (lab > 0 && hs > 4) {
    X.save(); X.globalAlpha *= lab;
    const bx = ox + 420;
    X.strokeStyle = HOT; X.lineWidth = 4;
    X.beginPath(); X.moveTo(bx, sea); X.lineTo(bx, water(bx)); X.moveTo(bx - 10, sea); X.lineTo(bx + 10, sea); X.moveTo(bx - 10, water(bx)); X.lineTo(bx + 10, water(bx)); X.stroke();
    pill('NƯỚC DÂNG DO BÃO', ox + 30, oy + 168, 28, HOT);
    X.restore();
  }
}

function frameHud(t) {
  // 0.8: the headline wind speed
  cue(win(t, 0.85, 8.2), () => {
    gauge(1650, 300, 150, 345 * eo((t - 0.85) / 1.9), 360, 'SỨC GIÓ');
    cue(sm(3.25, 3.65, t), () => { T('≈ 3 lần bão cấp 12', 1650, 580, 28, { a: 'center', w: 800, c: WARM }); });
  });

  // 9.0: tropical seas, on a world map
  cue(win(t, 9.05, 14.7), () => {
    P(80, 560, 660, 340);
    T('Biển', 110, 610, 34, { w: 800 }); const w = T('nhiệt đới', 196, 610, 34, { w: 800, c: WARM });
    T('· quanh xích đạo', 196 + w + 14, 610, 24, { c: DIM });
    tropics(t, 110, 640);
  });

  // 15.2 - 26: the sea's temperature against the threshold
  cue(win(t, 15.24, N(30.4)), () => {
    P(1480, 150, 380, 720);
    const v = keys([[15.3, 22], [17.4, 26.5], [N(22.9), 26.5], [N(24.0), 30]], t);
    T('NHIỆT ĐỘ NƯỚC BIỂN', 1670, 200, 22, { a: 'center', w: 700, c: DIM });
    T(fmt(v, 1) + ' °C', 1670, 272, 64, { a: 'center', w: 800, c: v < 26.5 ? COOL : v < 29 ? WARM : HOT });
    const x = 1580, y = thermo(x, 330, 730, v, 20, 32);
    X.lineWidth = 2; X.strokeStyle = 'rgba(255,255,255,0.45)';
    for (let c = 20; c <= 32; c += 2) { X.beginPath(); X.moveTo(x - 30, y(c)); X.lineTo(x - 20, y(c)); X.stroke(); T(String(c), x - 38, y(c) + 8, 20, { a: 'right', c: DIM }); }
    // the threshold
    X.setLineDash([10, 8]); X.strokeStyle = WARM; X.lineWidth = 3;
    X.beginPath(); X.moveTo(x - 24, y(26.5)); X.lineTo(x + 40, y(26.5)); X.stroke(); X.setLineDash([]);
    T('26,5 °C', x + 50, y(26.5) + 10, 30, { w: 800, c: WARM });
    T('ngưỡng bão', x + 50, y(26.5) + 42, 22, { c: DIM });
    cue(sm(17.84, 18.2, t), () => T('≈ hồ bơi, ấm hơn chút', x + 50, y(26.5) - 46, 20, { c: DIM }));
    cue(sm(19.84, 20.2, t), () => T('✓ đủ để sinh bão', x + 50, y(26.5) + 74, 22, { w: 700, c: OK }));
    // 30 °C and the surplus above the threshold: the fuel
    cue(sm(N(23.4), N(23.8), t), () => {
      T('30 °C', x + 50, y(30) + 10, 30, { w: 800, c: HOT });
      T('biển ở đây', x + 50, y(30) + 42, 22, { c: DIM });
    });
    cue(sm(N(25.68), N(26.0), t), () => T('↑ hơi nước bốc lên nhiều', 1510, 790, 22, { w: 700, c: COOL }));
    cue(sm(N(28.26), N(28.6), t), () => {
      const p = 0.6 + 0.4 * Math.sin(t * 9);
      X.fillStyle = `rgba(255,77,61,${0.35 * p})`; X.fillRect(x - 22, y(30), 44, y(26.5) - y(30));
      pill('= NHIÊN LIỆU CỦA BÃO', 1510, 836, 24, HOT);
    });
  });

  // 27.5 - 40: how warm water becomes a storm
  cue(win(t, 27.45, 40.2, 0.4, 0.6), () => engine(t));

  // 40.5: the spin
  cue(win(t, 40.55, 47.9), () => {
    P(80, 80, 520, 130);
    const ex = 150, ey = 145;
    X.beginPath(); X.arc(ex, ey, 36, 0, Math.PI * 2); X.fillStyle = '#1d5d9c'; X.fill();
    X.strokeStyle = 'rgba(255,255,255,0.5)'; X.lineWidth = 2; X.stroke();
    const sp = -t * 2;
    AA(ex, ey, 50, sp + 2.4, sp + 0.3, INK, 4, 14);
    T('Trái Đất tự quay', 215, 140, 32, { w: 800 });
    cue(sm(41.52, 41.9, t), () => T('→ mây xoay quanh một tâm', 215, 178, 24, { c: COOL, w: 700 }));
  });
  cue(win(t, 41.52, 47.9, 0.8, 0.6), () => {
    const b = -(t - 41.5) * 0.7;
    for (let i = 0; i < 3; i++) AA(960, 540, 270, b + i * 2.094, b + i * 2.094 - 1.25, 'rgba(255,255,255,0.85)', 7, 26);
    cue(sm(43, 43.5, t), () => { X.beginPath(); X.arc(960, 540, 9, 0, Math.PI * 2); X.fillStyle = WARM; X.fill(); T('tâm', 978, 532, 24, { w: 700, c: WARM }); });
  });

  // 48.5: a storm is born
  cue(win(t, 48.55, 56.6), () => {
    const k = eo((t - 48.55) / 0.8);
    X.setLineDash([18, 12]); X.lineDashOffset = -t * 30; X.strokeStyle = WARM; X.lineWidth = 5;
    X.beginPath(); X.arc(960, 540, lerp(320, 220, k), 0, Math.PI * 2); X.stroke(); X.setLineDash([]);
    A(1250, 380, 1150, 440, WARM, 5, 18);
    T('Một cơn bão', 1280, 352, 34, { w: 800 }); T('vừa thành hình', 1280, 394, 34, { w: 800, c: WARM });
    cue(sm(50.74, 51.1, t), () => T('…và còn mạnh thêm ↑', 1280, 470, 28, { w: 700, c: HOT }));
  });

  // 58: Patricia
  cue(win(t, 58.05, 65.9), () => {
    T('BÃO PATRICIA', 115, 760, 50, { w: 800 });
    T('Tháng 10/2015 · ngoài khơi Mexico', 115, 812, 28, { c: DIM });
    cue(sm(61.34, 61.7, t), () => pill('KỶ LỤC', 520, 744, 24, HOT));
  });
  // 66.6: +195 km/h in 24 hours, peak 345
  cue(win(t, N(69.6), N(86.0)), () => {
    const k = sm(N(71.23), N(73.8), t), v = lerp(150, 345, k), peak = sm(N(79.13), N(79.5), t);
    gauge(1650, 320, 150, v, 360, 'SỨC GIÓ · PATRICIA', { c: peak > 0.5 ? HOT : INK });
    P(1470, 540, 360, 190);
    const cx = 1545, cy = 635, h = clamp((t - N(69.6)) / (N(70.9) - N(69.6)));
    X.beginPath(); X.arc(cx, cy, 52, 0, Math.PI * 2); X.strokeStyle = 'rgba(255,255,255,0.4)'; X.lineWidth = 4; X.stroke();
    X.beginPath(); X.moveTo(cx, cy); X.arc(cx, cy, 46, -Math.PI / 2, -Math.PI / 2 + h * Math.PI * 2); X.closePath(); X.fillStyle = 'rgba(255,160,64,0.6)'; X.fill();
    A(cx, cy, cx + 40 * Math.cos(-Math.PI / 2 + h * Math.PI * 2), cy + 40 * Math.sin(-Math.PI / 2 + h * Math.PI * 2), INK, 4, 10);
    T(`${Math.round(h * 24)} giờ`, 1615, 618, 34, { w: 800 });
    cue(sm(N(71.3), N(71.7), t), () => T('+' + fmt(195 * k) + ' km/h', 1615, 660, 30, { w: 800, c: WARM }));
    cue(sm(N(75.9), N(76.3), t), () => pill('MẠNH NHẤT TỪNG ĐO', 1470, 770, 24, HOT));
    cue(sm(N(81.82), N(82.2), t), () => T('xé mái nhà · nhổ bật cây', 1470, 860, 26, { w: 700 }));
    cue(peak, () => {
      X.beginPath(); X.arc(1650, 320, 150 + 40 * ((t * 1.2) % 1), 0, Math.PI * 2);
      X.strokeStyle = `rgba(255,77,61,${1 - ((t * 1.2) % 1)})`; X.lineWidth = 5; X.stroke();
      pill('ĐỈNH ĐIỂM', 1565, 105, 26, HOT);
    });
  });

  // 80.5: the eye and the pressure
  cue(win(t, N(86.3), N(99.2)), () => {
    X.setLineDash([14, 10]); X.lineDashOffset = -t * 20; X.strokeStyle = INK; X.lineWidth = 4;
    X.beginPath(); X.arc(960, 540, 120, 0, Math.PI * 2); X.stroke(); X.setLineDash([]);
    A(1160, 380, 1060, 455, INK, 5, 18);
    pill('MẮT BÃO', 1170, 370, 34, null);
    // lower pressure pulls the air in harder
    cue(sm(N(95.15), N(95.6), t), () => {
      for (let i = 0; i < 6; i++) {
        const a = i * Math.PI / 3 + 0.5, r = lerp(300, 175, (t * 0.8 + i * 0.17) % 1);
        A(960 + (r + 70) * Math.cos(a), 540 + (r + 70) * Math.sin(a), 960 + r * Math.cos(a), 540 + r * Math.sin(a), COOL, 5, 16);
      }
      T('không khí bị hút vào', 960, 900 - 40, 28, { a: 'center', w: 700, c: COOL });
    });
    cue(sm(N(97.36), N(97.7), t), () => pill('GIÓ CÀNG DỮ', 600, 380, 26, HOT));
  });
  cue(win(t, N(88.1), N(99.2)), () => {
    P(1340, 640, 520, 250);
    const v = keys([[N(88.6), 1013], [N(90.9), 872]], t);
    T('ÁP SUẤT KHÔNG KHÍ', 1370, 685, 22, { w: 700, c: DIM });
    T(fmt(v) + ' hPa', 1370, 750, 56, { w: 800, c: v < 950 ? HOT : INK });
    const xa = 1380, xb = 1820, y = 820, px = (p) => lerp(xa, xb, (p - 860) / (1030 - 860));
    const g = X.createLinearGradient(xa, 0, xb, 0); g.addColorStop(0, HOT); g.addColorStop(0.5, WARM); g.addColorStop(1, COOL);
    X.fillStyle = g; X.beginPath(); X.roundRect(xa, y - 6, xb - xa, 12, 6); X.fill();
    X.fillStyle = INK; X.fillRect(px(1013) - 2, y - 18, 4, 36);
    T('1.013 bình thường', px(1013), y + 46, 20, { a: 'right', c: DIM });
    X.beginPath(); X.moveTo(px(v), y - 12); X.lineTo(px(v) - 12, y - 32); X.lineTo(px(v) + 12, y - 32); X.closePath(); X.fillStyle = INK; X.fill();
    cue(sm(N(91.0), N(91.4), t), () => T('thấp kỷ lục', px(872), y + 46, 22, { w: 800, c: HOT }));
  });

  // 90: a hypothetical island
  cue(win(t, 90.05, 95.8), () => pill('GIẢ ĐỊNH · một hòn đảo nhỏ', 80, 110, 28, null));
  // 96: the eyewall
  cue(win(t, 96.25, 104.6), () => {
    radar(1650, 300, 180, t, keys(ISLAND, t), true);
    T('Thành bão', 1210, 570, 38, { w: 800, c: HOT });
    T('vòng gió mạnh nhất quanh mắt bão', 1210, 612, 26, { c: DIM });
  });

  // 106: debris, drawn as the real things, shaking in the wind before they fly
  cue(win(t, N(115.5), N(123.9)), () => {
    const items = [[N(116.75), 'Mái tôn', 0], [N(117.61), 'Cành cây', 1], [N(118.46), 'Mảnh tường', 2]];
    P(80, 670, 1000, 250);
    items.forEach(([at, s, k], i) => {
      const a = sm(at, at + 0.3, t);
      if (a <= 0) return;
      const e = eo((t - at) / 0.7), cx = 240 + i * 320 - 160 * (1 - e), cy = 765;
      X.save(); X.globalAlpha *= a;
      X.strokeStyle = 'rgba(255,255,255,0.35)'; X.lineWidth = 3; X.lineCap = 'round';
      for (let j = 0; j < 3; j++) { const y = cy - 30 + j * 30, L = 40 + 30 * hash(j + k * 3); X.beginPath(); X.moveTo(cx - 95 - L, y); X.lineTo(cx - 95, y); X.stroke(); }
      X.translate(cx, cy); X.rotate(-1.6 * (1 - e) + 0.1 * Math.sin(t * 7 + k * 2) + [-0.15, 0.25, 0.1][k]);
      [tin, branch, wall][k]();
      X.restore();
      cue(a, () => T(s, 240 + i * 320, 885, 30, { a: 'center', w: 800 }));
    });
    cue(sm(N(119.2), N(119.55), t), () => { A(1100, 790, 1160, 790, HOT, 6, 20); pill('THÀNH VẬT BAY', 1174, 790, 28, HOT); });
    cue(sm(N(120.81), N(121.2), t), () => { T('nguy hiểm như một viên đạn', 1174, 863, 26, { w: 700, c: '#ff7a6b' }); });
  });

  // 115: not the wind
  cue(win(t, 115.05, 124.6), () => {
    T('Thứ cướp nhiều mạng người nhất', 960, 140, 34, { a: 'center', w: 700 });
    cue(sm(116.9, 117.3, t), () => {
      T('KHÔNG PHẢI GIÓ', 960, 200, 44, { a: 'center', w: 800, c: HOT });
    });
  });
  // 125: storm surge
  cue(win(t, 125.0, 132.9), () => surge(t));

  // 133: Haiyan, its surge height, its toll
  cue(win(t, 133.05, N(161.5)), () => {
    T('BÃO HAIYAN', 115, 760, 50, { w: 800 });
    T('Tháng 11/2013 · Philippines', 115, 812, 28, { c: DIM });
  });
  cue(win(t, 134.9, 142.0), () => {
    P(1480, 150, 380, 720);
    T('NƯỚC DÂNG', 1670, 200, 22, { a: 'center', w: 700, c: DIM });
    const y0 = 790, m = 62, y = (h) => y0 - h * m, x = 1600;
    const h1 = 4.6 * eo((t - N(144.6)) / 1.4), h2 = lerp(4.6, 7, eo((t - N(146.7)) / 1.0));
    X.fillStyle = 'rgba(40,140,220,0.8)'; X.fillRect(x - 70, y(h1), 240, y0 - y(h1));
    if (t > N(146.7)) { X.fillStyle = 'rgba(40,140,220,0.38)'; X.fillRect(x - 70, y(h2), 240, y(4.6) - y(h2)); }
    X.strokeStyle = 'rgba(255,255,255,0.45)'; X.lineWidth = 2;
    for (let h = 0; h <= 8; h += 2) { X.beginPath(); X.moveTo(x - 84, y(h)); X.lineTo(x - 72, y(h)); X.stroke(); T(h + ' m', x - 92, y(h) + 8, 20, { a: 'right', c: DIM }); }
    // a 1.7 m person for scale
    const px = x + 120, ph = 1.7 * m, py = y0;
    X.fillStyle = INK; X.beginPath(); X.arc(px, py - ph + 12, 12, 0, Math.PI * 2); X.fill();
    X.lineWidth = 9; X.strokeStyle = INK; X.lineCap = 'round'; X.beginPath();
    X.moveTo(px, py - ph + 28); X.lineTo(px, py - ph * 0.45); X.moveTo(px, py - ph * 0.45); X.lineTo(px - 10, py - 4); X.moveTo(px, py - ph * 0.45); X.lineTo(px + 10, py - 4);
    X.moveTo(px - 18, py - ph * 0.62); X.lineTo(px, py - ph + 34); X.lineTo(px + 18, py - ph * 0.62); X.stroke();
    T('người 1,7 m', px, py + 34, 20, { a: 'center', c: DIM });
    cue(sm(N(146.0), N(146.4), t), () => T('4,6 m', x + 180, y(4.6) + 10, 30, { w: 800 }));
    cue(sm(N(147.0), N(147.4), t), () => T('7 m', x + 180, y(7) + 10, 30, { w: 800, c: HOT }));
    cue(sm(N(148.06), N(148.4), t), () => T('> nhà 2 tầng', x + 180, y(7) + 40, 20, { c: DIM }));
  });
  cue(win(t, N(152.0), N(161.5)), () => {
    T(fmt(6300 * eo((t - N(152.0)) / 1.6)) + '+', 115, 560, 110, { w: 800, c: HOT });
    T('người thiệt mạng', 115, 618, 36, { w: 700 });
    cue(sm(N(154.47), N(154.8), t), () => T('phần lớn vì nước, không phải gió', 115, 662, 24, { w: 700, c: COOL }));
  });

  // 152.5: half of US hurricane deaths came from the surge: 100 people, the water rises over 49 of them
  cue(win(t, 152.55, 163.0), () => {
    P(1300, 150, 560, 720);
    T('Ở MỸ · 50 NĂM', 1330, 205, 30, { w: 800 });
    T('(1963–2012) · cứ 100 người chết vì bão', 1330, 242, 22, { c: DIM });
    const k = sm(N(164.1), N(166.6), t), n = Math.round(49 * k);
    const gx = 1350, gy = 275, gw = 490, gh = 440;
    // water: rises from the bottom of the grid to just under half, with a moving surface
    const lvl = gy + gh - gh * 0.49 * k;
    X.save(); X.beginPath(); X.roundRect(gx - 10, gy - 6, gw + 20, gh + 12, 14); X.clip();
    X.beginPath(); X.moveTo(gx - 10, gy + gh + 6);
    for (let x = 0; x <= gw + 20; x += 10) X.lineTo(gx - 10 + x, lvl + 5 * Math.sin(x * 0.04 + t * 3) * k);
    X.lineTo(gx + gw + 10, gy + gh + 6); X.closePath();
    const w = X.createLinearGradient(0, lvl, 0, gy + gh);
    w.addColorStop(0, 'rgba(98,208,255,0.42)'); w.addColorStop(1, 'rgba(30,110,190,0.6)');
    X.fillStyle = w; X.fill(); X.restore();
    for (let i = 0; i < 100; i++) {
      const cx = gx + 24 + (i % 10) * 49, cy = gy + gh - 44 - Math.floor(i / 10) * 44;
      X.fillStyle = i < n ? '#e9f8ff' : 'rgba(255,255,255,0.22)';
      X.beginPath(); X.arc(cx, cy + 8, 6.5, 0, Math.PI * 2); X.fill();
      X.beginPath(); X.roundRect(cx - 10, cy + 17, 20, 21, [9, 9, 3, 3]); X.fill();
    }
    const tw = T(`${n}`, 1330, 790, 64, { w: 800, c: COOL });
    T('người do nước dâng', 1330 + tw + 14, 790, 30, { w: 700, c: COOL });
    let hw = 0;
    cue(sm(N(166.0), N(166.4), t), () => { hw = T('≈ một nửa', 1330, 835, 24, { w: 700 }); });
    cue(sm(N(168.71), N(169.1), t), () => T('· cứ 2 người, gần 1 bị nước cuốn', 1330 + hw + 10, 835, 22, { c: DIM }));
  });

  // 167 - 209: the eye passes over the island, then the back wall
  cue(win(t, 167.55, 209.6), () => radar(1650, 300, 180, t, keys(ISLAND, t), t > 181));
  cue(win(t, 167.55, 172.9), () => {
    T('Trong mắt bão', 1210, 570, 38, { w: 800, c: COOL });
    T('gió lặng, trời quang', 1210, 612, 26, { c: DIM });
  });
  cue(win(t, 173.05, 180.9), () => {
    P(80, 690, 720, 170);
    const x = 130, y = 775;
    X.beginPath(); X.moveTo(x, y - 40); X.lineTo(x + 44, y + 36); X.lineTo(x - 44, y + 36); X.closePath(); X.fillStyle = '#ffc233'; X.fill();
    T('!', x, y + 28, 48, { a: 'center', w: 900, c: '#1a1a1a', sh: 0 });
    T('LÚC NGUY HIỂM NHẤT', 200, 765, 40, { w: 800, c: '#ffc233' });
    cue(sm(174.94, 175.3, t), () => T('Bão chưa qua, đừng ra ngoài', 200, 815, 30, { w: 700 }));
  });
  cue(win(t, 181.05, 190.4), () => {
    T('Nửa sau đang tới', 1210, 570, 38, { w: 800, c: HOT });
    T('thành bão phía sau, gió mạnh trở lại', 1210, 612, 26, { c: DIM });
  });
  cue(win(t, 190.55, 209.6), () => {
    P(1180, 520, 650, 200);
    T('GIÓ ĐỔI CHIỀU', 1210, 568, 34, { w: 800, c: HOT });
    X.save(); X.globalAlpha *= 0.55;
    A(1520, 620, 1300, 620, WARM, 8, 24); T('trước', 1540, 630, 26, { c: DIM });
    X.restore();
    const k = eo((t - 191) / 0.8);
    A(1300, 680, lerp(1300, 1520, k) + 1, 680, HOT, 8, 24); T('bây giờ', 1540, 690, 26, { w: 700 });
    cue(sm(200.05, 200.4, t), () => pill('QUẬT NGƯỢC LẠI', 1210, 760, 26, HOT));
  });

  // 212: the water goes down; 216.5: the rivers come up
  cue(win(t, 212.04, 216.4), () => {
    P(80, 560, 400, 300);
    T('MỰC NƯỚC', 110, 605, 22, { w: 700, c: DIM });
    const lv = keys([[212.3, 0.85], [215.5, 0.2]], t);
    X.fillStyle = 'rgba(255,255,255,0.12)'; X.fillRect(120, 630, 90, 200);
    X.fillStyle = 'rgba(40,140,220,0.9)'; X.fillRect(120, 630 + 200 * (1 - lv), 90, 200 * lv);
    A(300, 660, 300, 790, COOL, 7, 22);
    T('rút dần', 330, 735, 32, { w: 800 });
  });
  cue(win(t, 216.55, 222.3), () => {
    P(80, 560, 560, 300);
    T('MỰC NƯỚC SÔNG', 110, 605, 22, { w: 700, c: DIM });
    const pts = [0.15, 0.4, 0.7, 0.85, 0.75], k = clamp((t - 217) / 2.5) * 4;
    X.strokeStyle = 'rgba(255,255,255,0.3)'; X.lineWidth = 2; X.beginPath(); X.moveTo(120, 800); X.lineTo(600, 800); X.stroke();
    X.strokeStyle = COOL; X.lineWidth = 6; X.lineJoin = 'round'; X.beginPath();
    for (let i = 0; i <= Math.floor(k); i++) {
      const f = Math.min(1, k - i + 1), y = (j) => 800 - pts[j] * 160;
      const x0 = 140 + (i - 1) * 110, xi = 140 + i * 110;
      i === 0 ? X.moveTo(xi, y(0)) : X.lineTo(lerp(x0, xi, f), lerp(y(i - 1), y(i), f));
    }
    X.stroke();
    for (let i = 0; i < 5; i++) T(`ngày ${i + 1}`, 140 + i * 110, 836, 20, { a: 'center', c: DIM });
    T('dâng lên nhiều ngày sau', 110, 650, 28, { w: 800, c: COOL });
  });

  // 222.5: freshwater floods
  cue(win(t, N(232.0), N(244.5)), () => {
    P(1240, 170, 620, 330);
    T('Ở MỸ · 10 NĂM GẦN ĐÂY', 1270, 225, 30, { w: 800 });
    T('(2013–2022) · người chết trực tiếp vì bão', 1270, 262, 22, { c: DIM });
    const k = 0.57 * eo((t - N(234.1)) / 1.8);
    X.fillStyle = 'rgba(255,255,255,0.14)'; X.beginPath(); X.roundRect(1270, 300, 560, 54, 10); X.fill();
    X.fillStyle = COOL; X.beginPath(); X.roundRect(1270, 300, Math.max(1, 560 * k), 54, 10); X.fill();
    T(`≈ ${Math.round(k * 100)}%`, 1290, 340, 32, { w: 800, c: '#06243a', sh: 0 });
    T('lũ do mưa', 1270, 400, 34, { w: 800, c: COOL });
    cue(sm(N(236.0), N(236.4), t), () => pill('NGUYÊN NHÂN SỐ 1', 1270, 452, 24, HOT));
    cue(sm(N(238.24), N(238.6), t), () => T('cứ 10 người · gần 6', 1530, 400, 28, { w: 700 }));
  });

  // 236: what warming changes
  cue(win(t, N(244.85), N(255.3)), () => {
    const rows = [[N(244.85), 'Đại dương ấm lên', '↑', HOT], [N(246.5), 'Bão thêm nhiên liệu', '+', WARM], [N(248.78), 'Số cơn bão: có thể không tăng', '≈', DIM], [N(250.41), 'Tỷ lệ bão cấp 4, cấp 5', '↑', HOT]];
    rows.forEach(([at, s, m, c], i) => cue(sm(at, at + 0.35, t), () => {
      T(m, 115, 615 + i * 72, 46, { w: 900, c });
      T(s, 175, 607 + i * 72, 30, { w: 700, c: i === 2 ? DIM : INK });
    }));
  });
}

let drew = false;
window.hud = (t) => {
  X.setTransform(1, 0, 0, 1, 0, 0); X.clearRect(0, 0, W, H);
  X.setTransform(W / 1920, 0, 0, H / 1080, 0, 0);
  drew = false;
  frameHud(unhold(t * SPEED) / SPEED);
  return drew ? C.toDataURL('image/png') : '';
};
window.READY = true;
