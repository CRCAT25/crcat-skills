// On-screen cues that show what the narration states (figures, processes), on a transparent 2D canvas over the film.
// Keyed in FINAL time (the 3D film plays SPEED times slower: film t = final t x SPEED). Laid out in 1920x1080 units.
// Write cue times from the caption/lines.json timings; the film.js holds stretch them like the picture.
// window.hud(t) draws one frame and returns a PNG data URL, or '' when nothing is on screen.
// Render: node hud.mjs <base.mp4> <out.mp4> [...flags] (see hud.mjs); --stills 12,30.5 to check a few frames first.
// Rules: no dark panels or boxes behind text (halo + thin rim only); keep cues above y≈900 (YouTube controls);
// every number or process the narration states gets a cue at that moment.
import { unhold } from './film.js';
import { LAND } from './land110.js';
const SPEED = 1.15;   // keep equal to episode.json "speed"
// N(n): a timeline time (as heard in the final cut) in cue time; for cues timed to narration recorded after holds were added
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
// a dial gauge: v of max, ticks every `step`, value in the middle with its unit
function gauge(cx, cy, r, v, max, label, unit = '', step = 50, o = {}) {
  const a0 = Math.PI * 0.75, a1 = Math.PI * 2.25, k = clamp(v / max);
  X.lineCap = 'round'; X.lineWidth = 18;
  X.strokeStyle = 'rgba(255,255,255,0.14)'; X.beginPath(); X.arc(cx, cy, r, a0, a1); X.stroke();
  const g = X.createConicGradient(a0, cx, cy);
  g.addColorStop(0, COOL); g.addColorStop(0.42, WARM); g.addColorStop(0.75, HOT); g.addColorStop(1, HOT);
  X.strokeStyle = g; X.beginPath(); X.arc(cx, cy, r, a0, a0 + (a1 - a0) * Math.max(k, 0.001)); X.stroke();
  X.lineWidth = 3; X.strokeStyle = 'rgba(255,255,255,0.5)';
  for (let s = 0; s <= max; s += step) {
    const a = a0 + (a1 - a0) * (s / max);
    X.beginPath(); X.moveTo(cx + Math.cos(a) * (r - 22), cy + Math.sin(a) * (r - 22)); X.lineTo(cx + Math.cos(a) * (r - 32), cy + Math.sin(a) * (r - 32)); X.stroke();
  }
  T(fmt(v), cx, cy + 22, r * 0.52, { a: 'center', w: 800, c: o.c || INK });
  if (unit) T(unit, cx, cy + 62, 26, { a: 'center', c: DIM });
  T(label, cx, cy + r + 6, 24, { a: 'center', w: 700, c: DIM });
}
// a thermometer from lo to hi degrees; the fill turns warm past `warm`, hot past `hot`; returns the degree -> y map
function thermo(x, top, bot, v, lo, hi, warm = 26.5, hot = 29) {
  const y = (c) => lerp(bot, top, (c - lo) / (hi - lo)), tw = 30;
  X.beginPath(); X.roundRect(x - tw / 2, top - 14, tw, bot - top + 30, tw / 2); X.fillStyle = 'rgba(255,255,255,0.14)'; X.fill();
  X.beginPath(); X.arc(x, bot + 34, 36, 0, Math.PI * 2); X.fill();
  X.fillStyle = v < warm ? COOL : v < hot ? WARM : HOT;
  X.beginPath(); X.roundRect(x - tw / 2 + 7, y(v), tw - 14, bot - y(v) + 20, 8); X.fill();
  X.beginPath(); X.arc(x, bot + 34, 27, 0, Math.PI * 2); X.fill();
  return y;
}
// a real world map (Natural Earth 1:110m land, public domain) for "where": MW x MH, lon from LON0, lat 70 N at the top
let MAP = null;
const MW = 600, MH = 208, LON0 = -30, KX = MW / 360, lon2x = (lo) => (((lo - LON0) % 360) + 360) % 360 * KX, lat2y = (la) => (70 - la) * KX;
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
function map(x, y) {
  if (!MAP) MAP = worldMap();
  X.save(); X.beginPath(); X.roundRect(x, y, MW, MH, 12); X.clip(); X.drawImage(MAP, x, y); X.restore();
  X.beginPath(); X.roundRect(x, y, MW, MH, 12); X.strokeStyle = 'rgba(255,255,255,0.25)'; X.lineWidth = 1.5; X.stroke();
}
// a grid of person icons (n of them, the first `hit` in colour c): "49 out of 100" reads at a glance
function people(x, y, n, hit, c = HOT, per = 20, s = 22) {
  for (let i = 0; i < n; i++) {
    const px = x + (i % per) * s * 1.1, py = y + Math.floor(i / per) * s * 1.9;
    X.fillStyle = i < hit ? c : 'rgba(255,255,255,0.55)';
    X.beginPath(); X.arc(px, py, s * 0.28, 0, Math.PI * 2); X.fill();
    X.beginPath(); X.roundRect(px - s * 0.33, py + s * 0.36, s * 0.66, s * 0.9, s * 0.25); X.fill();
  }
}

// ---- the cues, in final time: one block per narration line that states a figure or a process ----
function frameHud(t) {
  // example: a temperature rising past a threshold while the narration says it
  cue(win(t, 2.0, 9.0), () => {
    const v = keys([[2.0, 22], [4.0, 26.5], [6.0, 30]], t);
    T('NHIỆT ĐỘ NƯỚC BIỂN', 1670, 200, 22, { a: 'center', w: 700, c: DIM });
    T(fmt(v, 1) + ' °C', 1670, 272, 64, { a: 'center', w: 800, c: v < 26.5 ? COOL : v < 29 ? WARM : HOT });
    thermo(1670, 330, 730, v, 20, 32);
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
