// The shared coast for the tsunami film: one fictional tropical bay (reef flat, white beach, coconut grove, green hill)
// ray-marched as a heightfield with a live water surface (calm sea, the drawback, the bore, the backwash), plus the
// hooks that let rasterised props (palms, huts, boats, debris) composite into it with depth, shadows and the same fog.
// Units are metres. x runs along the shore, +z is inland, y is up, sea level is y = 0.
// c = z - coastZ(x) is the cross-shore coordinate: c > 0 on land, c < 0 at sea.
// The macro shape is built from sines only and mirrored in JS (groundY, waterY), so props sit exactly on it.
import * as THREE from 'three';
import { NOISE, RAY_VS } from './glsl.js';
import { clamp, lerp, smooth, fsQuad } from './kit.js';

const S = (a, b, x) => smooth(a, b, x);
export const coastZ = (x) => 30 * Math.sin(x * 0.0023 + 0.4) + 14 * Math.sin(x * 0.0061 + 1.3)
  - 260 * (1 - Math.exp(-((x / 1400) ** 2))) - 170 * Math.exp(-(((x - 520) / 150) ** 2));
const hillH = (x) => 50 + 12 * Math.sin(x * 0.004 + 1.0) + 8 * Math.sin(x * 0.011 + 0.3);
const reefShift = (x) => 25 * Math.sin(x * 0.006 + 2.0) + 10 * Math.sin(x * 0.017);
export function profile(x, c) {
  let h;
  if (c < 0) {
    const r = c + reefShift(x);
    h = -1.5 * (1 - Math.exp(c / 10)) + 0.5 * S(-70, -110, r) + 0.35 * S(-260, -325, r) - 8.6 * S(-330, -380, r)
      - 16 * S(-380, -900, r) - 15 * S(-900, -2500, r) - 40 * S(-2500, -8000, r);
  } else {
    h = 2.25 * (1 - Math.exp(-c / 13)) + 1.3 * S(30, 260, c) + hillH(x) * S(360, 620, c)
      + 140 * S(1200, 3800, c) * (0.65 + 0.35 * Math.sin(x * 0.0017 + 0.5));
  }
  return h + 26 * Math.exp(-(((x - 520) / 150) ** 2)) * S(-30, 110, c);
}
export const crossC = (x, z) => z - coastZ(x);
export const groundY = (x, z) => profile(x, z - coastZ(x));
// the bore front's along-shore wiggle (same in GLSL)
const frontWig = (x) => 30 * Math.sin(x * 0.0047 + 1.0) + 12 * Math.sin(x * 0.013 + 2.0) + 5 * Math.sin(x * 0.041 + 0.7);
// water state, set by the scenes each frame and shared with the shader through the uniforms below
export const sea = { level: 0, front: -1e5, boreH: 0, back: 0 };
const boreB = (x, c) => {
  if (sea.boreH <= 0) return 0;
  const f = c - (sea.front + frontWig(x));
  return sea.boreH * S(3, -9, f) * (0.78 + 0.22 * Math.exp(Math.min(f, 0) / 90)) * (1 - 0.45 * S(-50, 500, c));
};
// macro water surface (no ripples); -Infinity where there is no water over the ground
export function waterY(x, z) {
  const c = z - coastZ(x), g = profile(x, c);
  const w = Math.max(sea.level, sea.level + boreB(x, c));
  return w > g ? w : -Infinity;
}

export const SUN0 = new THREE.Vector3(-0.5, 0.42, -0.62).normalize();

// monotone cubic through the keys [t, a, b, ...]: velocity stays continuous, no overshoot
export const track = (K) => {
  const n = K.length, m = K[0].length - 1, T = K.map((k) => k[0]), Sl = [];
  for (let c = 0; c < m; c++) {
    const v = K.map((k) => k[c + 1]), d = [], s = [];
    for (let i = 0; i < n - 1; i++) d[i] = (v[i + 1] - v[i]) / (T[i + 1] - T[i]);
    s[0] = d[0] * 0.3; s[n - 1] = 0;
    for (let i = 1; i < n - 1; i++) s[i] = d[i - 1] * d[i] <= 0 ? 0 : 2 / (1 / d[i - 1] + 1 / d[i]);
    Sl.push(s);
  }
  return (t) => {
    t = clamp(t, T[0], T[n - 1]);
    let i = 0; while (i < n - 2 && t > T[i + 1]) i++;
    const h = T[i + 1] - T[i], u = (t - T[i]) / h, u2 = u * u, u3 = u2 * u;
    const h00 = 2 * u3 - 3 * u2 + 1, h10 = u3 - 2 * u2 + u, h01 = -2 * u3 + 3 * u2, h11 = u3 - u2;
    return Sl.map((s, c) => h00 * K[i][c + 1] + h10 * h * s[i] + h01 * K[i + 1][c + 1] + h11 * h * s[i + 1]);
  };
};

const HELP = /* glsl */ `
  float vn2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash12(i), b = hash12(i + vec2(1.0, 0.0)), c = hash12(i + vec2(0.0, 1.0)), d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 2.0 - 1.0; }
  float fbm2(vec2 p, int oct){ float a = 0.5, s = 0.0; for (int i = 0; i < 10; i++){ if (i >= oct) break; s += a * vn2(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7); a *= 0.5; } return s; }
  vec3 vor2(vec2 x){ vec2 p = floor(x), f = fract(x); float d1 = 8.0, d2 = 8.0, id = 0.0;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++){ vec2 b = vec2(float(i), float(j)); vec2 r = b + hash22(p + b) - f; float d = dot(r, r);
      if (d < d1){ d2 = d1; d1 = d; id = hash12(p + b + 17.31); } else if (d < d2) d2 = d; }
    return vec3(sqrt(d1), sqrt(d2), id); }
  float sm(float a, float b, float x){ float k = clamp((x - a) / (b - a), 0.0, 1.0); return k * k * (3.0 - 2.0 * k); }
`;

// macro shape, mirrors the JS above
const MACRO = /* glsl */ `
  float coastZ(float x){ return 30.0 * sin(x * 0.0023 + 0.4) + 14.0 * sin(x * 0.0061 + 1.3)
    - 260.0 * (1.0 - exp(-pow(x / 1400.0, 2.0))) - 170.0 * exp(-pow((x - 520.0) / 150.0, 2.0)); }
  float headW(float x){ return exp(-pow((x - 520.0) / 150.0, 2.0)); }
  float reefShift(float x){ return 25.0 * sin(x * 0.006 + 2.0) + 10.0 * sin(x * 0.017); }
  float profile(float x, float c){
    float h;
    if (c < 0.0){
      float r = c + reefShift(x);
      h = -1.5 * (1.0 - exp(c / 10.0)) + 0.5 * sm(-70.0, -110.0, r) + 0.35 * sm(-260.0, -325.0, r) - 8.6 * sm(-330.0, -380.0, r)
        - 16.0 * sm(-380.0, -900.0, r) - 15.0 * sm(-900.0, -2500.0, r) - 40.0 * sm(-2500.0, -8000.0, r);
    } else {
      float hill = 50.0 + 12.0 * sin(x * 0.004 + 1.0) + 8.0 * sin(x * 0.011 + 0.3);
      h = 2.25 * (1.0 - exp(-c / 13.0)) + 1.3 * sm(30.0, 260.0, c) + hill * sm(360.0, 620.0, c)
        + 140.0 * sm(1200.0, 3800.0, c) * (0.65 + 0.35 * sin(x * 0.0017 + 0.5));
    }
    return h + 26.0 * headW(x) * sm(-30.0, 110.0, c);
  }
  float frontWig(float x){ return 30.0 * sin(x * 0.0047 + 1.0) + 12.0 * sin(x * 0.013 + 2.0) + 5.0 * sin(x * 0.041 + 0.7); }
`;

export function makeCoast({ W, H, fov = 38, near = 0.05, far = 90000 }) {
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(fov, W / H, near, far);
  const v3 = (a) => new THREE.Vector3(...a);
  const u = {
    uTan: { value: new THREE.Vector2() }, uCamWorld: { value: new THREE.Matrix4() }, uCam: { value: new THREE.Vector3() },
    uVP: { value: new THREE.Matrix4() }, uFpK: { value: 0.0006 }, uT: { value: 0 },
    uSun: { value: SUN0.clone() }, uSunC: { value: v3([1.0, 0.88, 0.72]).multiplyScalar(3.0) },
    uZen: { value: v3([0.05, 0.17, 0.5]) }, uHor: { value: v3([0.5, 0.66, 0.83]) }, uAmb: { value: v3([0.32, 0.42, 0.6]) },
    uFogC: { value: v3([0.6, 0.7, 0.82]) }, uFogK: { value: 1 }, uCloud: { value: 0 },
    // water: x = level (drawdown < 0), y = bore front (cross-shore c), z = bore height above level, w = backwash (0..1)
    uSea: { value: new THREE.Vector4(0, -1e5, 0, 0) },
    uMud: { value: 0 }, uWetTop: { value: 0.3 }, uSilt: { value: new THREE.Vector2(-1e5, 0) }, uSwell: { value: 1 },
    uSpray: { value: 0 },
    // storm: 0..1 overcast/gale, wind direction (xz, unit), spume (wind-torn foam + low spray), scud speed
    uStorm: { value: 0 }, uWd: { value: new THREE.Vector2(0.6, 0.8) }, uSpume: { value: 0 }, uScud: { value: 1 },
    uStormC: { value: v3([0.16, 0.18, 0.2]) },
    // the eye overhead: x amount, y = rd.y of the hole's rim (the stadium wall rises to it), z wall brightness
    uEyeO: { value: new THREE.Vector3(0, 0.6, 1) },
    // a bare sand clearing in the reef flat (centre x, z, radii x, z), e.g. where stranded fish lie
    uClear: { value: new THREE.Vector4(0, 0, 0, 0) },
    uSM: { value: null }, uSMat: { value: null }, uSMon: { value: 0 }, uSMtx: { value: 1 / 4096 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, vertexShader: RAY_VS, depthTest: true, depthWrite: true,
    fragmentShader: /* glsl */ `
      #include <packing>
      ${NOISE}${HELP}${MACRO}
      varying vec3 vDir;
      uniform vec3 uCam, uSun, uSunC, uZen, uHor, uAmb, uFogC; uniform mat4 uVP, uSMat;
      uniform float uT, uFpK, uFogK, uCloud, uMud, uWetTop, uSwell, uSpray, uSMon, uSMtx, uStorm, uSpume, uScud; uniform vec4 uSea, uClear; uniform vec2 uSilt, uWd; uniform vec3 uStormC, uEyeO;
      uniform sampler2D uSM;
      const float CB = 900.0, CT = 2300.0;

      // ---------- ground: macro profile + reef, beach, grove, hill forest, headland rock ----------
      // m: x = rock, y = forest canopy, z = coral, w = land vegetation (grass / scrub)
      float clearing(vec2 xz){
        if (uClear.z <= 0.0) return 0.0;
        vec2 d = (xz - uClear.xy) / uClear.zw;
        return sm(1.0, 0.6, length(d) + 0.15 * vn2(xz * 0.15));
      }
      float ground(vec2 xz, float fp, out vec4 m){
        float x = xz.x, c = xz.y - coastZ(x);
        float h = profile(x, c);
        m = vec4(0.0);
        float hw = headW(x);
        if (c < 0.0){
          float r = c + reefShift(x);
          // reef flat: coral heads (domes) in patches, sand between, spur-and-groove channels cut into the reef edge
          float rflat = sm(-60.0, -95.0, r) * sm(-400.0, -365.0, r);
          if (rflat > 0.0 && fp < 3.0){
            vec3 v = vor2(xz / 2.2 + 0.6 * vec2(vn2(xz * 0.21), vn2(xz * 0.21 + 9.0)));
            // radius kept inside the cell: rounded heads, no wall where a kept cell meets an empty one
            float wob = vn2(xz * 1.7) * 0.5 + 0.5;
            float dome = pow(max(0.0, 1.0 - pow(v.x / ((0.26 + 0.24 * v.z) * (0.75 + 0.4 * wob)), 2.0)), 0.7);
            float patchy = sm(-0.15, 0.35, fbm2(xz * 0.013, 3) + 0.25 * sm(-300.0, -200.0, r));
            // separate heads with sand between, not a continuous mat
            float co = dome * (0.2 + 0.75 * v.z * v.z + 0.2 * wob) * sm(0.4, 0.5, v.z) * patchy * rflat * (1.0 - clearing(xz));
            if (fp < 0.3) co *= 0.75 + 0.5 * fbm2(xz * 3.0, 3) + 0.12 * abs(vn2(xz * 7.0));
            h += co * (1.0 - sm(0.3, 1.4, fp));
            m.z = sm(0.02, 0.12, co);
          }
          // sparse big bommies in the lagoon
          float lag = sm(-8.0, -20.0, c) * sm(-110.0, -70.0, r);
          if (lag > 0.0 && fp < 3.0){
            vec3 v = vor2(xz / 11.0);
            float dome = pow(max(0.0, 1.0 - pow(v.x / (0.3 + 0.18 * v.z), 2.0)), 0.6) * step(0.82, v.z) * lag;
            if (fp < 0.5) dome *= 0.7 + 0.45 * fbm2(xz * 0.9, 3) + 0.25 * abs(vn2(xz * 2.3));
            h += dome * (0.7 + 0.9 * fract(v.z * 17.0));
            m.z = max(m.z, sm(0.05, 0.2, dome));
          }
          float edge = sm(-300.0, -335.0, r) * sm(-400.0, -360.0, r);
          if (edge > 0.0){
            float g = sm(0.45, 0.9, abs(sin(x * 0.085 + 2.5 * vn2(xz * 0.015))));
            h -= g * 2.2 * edge;
            m.z = max(m.z, (1.0 - g) * edge * 0.8);
            // spur tops: rough coral rock, not a flat slab
            if (fp < 2.0){
              vec3 v2 = vor2(xz / 1.6 + 3.0);
              float d2 = pow(max(0.0, 1.0 - pow(v2.x / 0.46, 2.0)), 0.7) * (0.25 + 0.45 * v2.z);
              h += (1.0 - g) * edge * (0.35 * fbm2(xz * 0.35, 3) + 0.2 * abs(vn2(xz * 1.3)) + d2 * (1.0 - sm(0.3, 1.4, fp)));
            }
          }
          if (fp < 0.5) h += 0.05 * fbm2(xz * 0.7, 3) * sm(-20.0, -60.0, c);
        } else {
          // grove floor: soft undulation, low scrub at its back edge, rain-forest canopy on the hill
          if (fp < 2.0) h += 0.18 * fbm2(xz * 0.05, 3) * sm(20.0, 60.0, c);
          float scrub = sm(150.0, 280.0, c) * sm(-0.1, 0.3, fbm2(xz * 0.02 + 3.0, 3)) * (1.0 - sm(330.0, 400.0, c));
          float F = sm(320.0, 420.0, c) * (1.0 - 0.6 * sm(0.3, 0.8, hw)) * max(sm(-0.5, -0.1, fbm2(xz * 0.004 + 5.0, 3)), sm(700.0, 1100.0, c));
          float cov = max(scrub, F);
          if (cov > 0.0){
            float can;
            if (fp < 3.0){
              vec3 v = vor2(xz / mix(2.4, 6.5, F));
              float dome = sqrt(max(0.0, 1.0 - pow(v.x / mix(0.38 + 0.3 * v.z, 0.72, F), 2.0)));
              dome *= mix(step(0.35, v.z) * (0.75 + 0.5 * fbm2(xz * 0.9, 3) + 0.3 * abs(vn2(xz * 2.7))), 1.0, F);
              can = mix(0.25 + 1.6 * dome * (0.5 + 0.8 * v.z), 9.0 + 7.0 * dome * (0.6 + 0.6 * v.z) + 1.5 * vn2(xz * 0.35), F);
            } else can = mix(1.6, 12.0 + 2.0 * vn2(xz * 0.05), F);
            h += can * cov;
            m.y = max(F, scrub * 0.7);
          }
          m.w = sm(18.0, 45.0, c);
          if (c > 1000.0) h += (60.0 * fbm2(xz * 0.0009, 5) + 25.0) * sm(1000.0, 2200.0, c);
        }
        // headland: weathered dark limestone, boulders at its foot
        if (hw > 0.05){
          float rk = hw * sm(-60.0, 40.0, c);
          if (fp < 6.0) h += rk * (4.0 * fbm2(xz * 0.06, fp < 1.0 ? 5 : 3) + 2.0 * abs(vn2(xz * 0.2)));
          if (fp < 3.0){
            vec3 v = vor2(xz / 5.0);
            float b = sqrt(max(0.0, 1.0 - pow(v.x / 0.6, 2.0))) * (0.8 + 2.5 * v.z) * step(0.5, v.z) * hw * sm(-90.0, -20.0, c) * sm(30.0, -10.0, c);
            h = max(h, -0.6 + b);
            rk = max(rk, step(0.02, b));
          }
          m.x = clamp(rk * 1.4, 0.0, 1.0) * (1.0 - m.y);
          float top = hw * sm(6.0, 14.0, h) * sm(-0.3, 0.2, fbm2(xz * 0.03, 3));
          m.y = max(m.y, top); m.x *= 1.0 - top;
        }
        return h;
      }
      float ground(vec2 xz, float fp){ vec4 m; return ground(xz, fp, m); }

      // ---------- water surface ----------
      float boreB(float x, float c){
        if (uSea.z <= 0.0) return 0.0;
        float f = c - (uSea.y + frontWig(x));
        return uSea.z * sm(3.0, -9.0, f) * (0.78 + 0.22 * exp(min(f, 0.0) / 90.0)) * (1.0 - 0.45 * sm(-50.0, 500.0, c));
      }
      // returns the surface height; b = bore weight, pool = 1 inside a drawback pool
      float water(vec2 xz, float fp, out float b, out float pool){
        float x = xz.x, c = xz.y - coastZ(x), r = c + reefShift(x);
        float lv = uSea.x;
        // wind sea and ocean swell outside the reef; the reef flat kills them, the lagoon only ripples
        float out_ = sm(-330.0, -420.0, r), shel = 1.0 - out_;
        float sw = 0.0;
        sw += 0.42 * sin(xz.y * 0.055 + x * 0.012 + uT * 0.62 + 0.8 * vn2(xz * 0.004));
        sw += 0.22 * sin(dot(xz, vec2(0.031, 0.082)) + uT * 0.81);
        if (fp < 2.0) sw += 0.1 * sin(dot(xz, vec2(-0.21, 0.33)) + uT * 1.7) + 0.07 * fbm2(xz * 0.12 + uT * 0.05, 3);
        float drown = sm(0.5, 3.5, lv);
        float h = sw * mix(mix(0.12, 0.7, drown), 1.0, out_) * uSwell;
        if (uStorm > 0.0){
          // wind sea: short steep crests running downwind, peaked tops (abs of a sine), patchy groups
          vec2 wp = vec2(dot(xz, uWd), dot(xz, vec2(-uWd.y, uWd.x)));
          float g1 = 1.0 - abs(sin(wp.x * 0.09 - uT * 2.2 + 1.3 * vn2(wp * 0.01)));
          float g2 = 1.0 - abs(sin(wp.x * 0.16 + wp.y * 0.05 - uT * 2.9 + 2.0 * vn2(wp * 0.02 + 5.0)));
          float grp = 0.55 + 0.45 * vn2(wp * vec2(0.006, 0.012) - vec2(uT * 0.05, 0.0));
          float ws = (g1 * g1 * 1.6 + g2 * g2 * 0.7) * grp;
          if (fp < 1.5) ws += 0.25 * fbm2(wp * vec2(0.25, 0.4) - vec2(uT * 1.1, 0.0), 3);
          h += ws * uSpume * mix(mix(0.15, 0.8, drown), 1.0, out_);
        }
        float rip = 0.0;
        if (fp < 0.6) rip = 0.035 * fbm2(xz * 0.9 + vec2(uT * 0.25, -uT * 0.18), fp < 0.08 ? 4 : 2);
        h += rip * (0.5 + shel);
        // the drawback leaves pools in the reef: water sitting just above the sand between the coral heads
        pool = 0.0;
        float w = lv + h;
        if (lv < -0.25){
          float zone = sm(-12.0, -40.0, c) * sm(-345.0, -325.0, r);
          float pm = sm(-0.25, 0.15, fbm2(xz * 0.02 + 7.0, 3) + 0.15) * (1.0 - clearing(xz));
          float pl = profile(x, c) + mix(-0.4, 0.16, pm) + rip * 0.2;
          if (zone > 0.0 && pl > w){ w = mix(w, pl, zone); pool = zone * pm; }
        }
        b = boreB(x, c);
        if (b > 0.0){
          // the bore: a steep turbulent front, a churning body behind it, flowing landward (or back to sea in the backwash)
          float f = c - (uSea.y + frontWig(x));
          float fl = mix(1.0, -1.0, uSea.w);
          vec2 q = vec2(x * 0.07, c * 0.07 - uT * 0.9 * fl);
          float tb = fbm2(q, fp < 0.5 ? 5 : 3) * 0.55 + (fp < 0.3 ? 0.18 * fbm2(q * 3.5 + uT * 0.6, 3) : 0.0);
          float front = sm(-30.0, -2.0, f) * sm(4.0, -1.0, f);
          float lump = vn2(vec2(x * 0.035, c * 0.04 - uT * 0.5 * fl)) * 0.5 + 0.5;
          float bw = lv + b + (tb * (0.6 + 1.6 * front) + 1.6 * lump * front * sm(-60.0, -8.0, f)) * sm(0.05, 1.5, b) * mix(1.0, 0.5, uSea.w);
          w = max(w, bw);
          pool *= 1.0 - sm(0.05, 0.6, b);
        }
        return w;
      }
      float water(vec2 xz, float fp){ float b, p; return water(xz, fp, b, p); }

      // ---------- sky, clouds, fog ----------
      vec3 sky(vec3 rd){
        float y = max(rd.y, 0.0), mu = dot(rd, uSun);
        vec3 c = mix(uHor, uZen, pow(y, 0.42));
        c += uSunC * (vec3(0.33, 0.22, 0.12) * pow(max(mu, 0.0), 6.0) * (1.0 - y) + vec3(0.33, 0.3, 0.25) * pow(max(mu, 0.0), 60.0) * 0.4);
        c += uSunC * smoothstep(0.99965, 0.9999, mu) * 20.0;
        if (rd.y < 0.0) c = mix(uHor * 0.92, uHor * 0.55, clamp(-rd.y * 4.0, 0.0, 1.0));
        if (uStorm > 0.0){
          // storm ceiling: a low dark base with ragged scud racing downwind beneath it, paler toward the horizon
          float y2 = max(rd.y, 0.004);
          vec2 q = rd.xz / y2 * 0.9 - uWd * uT * 0.05 * uScud;
          float base = fbm2(q * 0.35, 5), scud = fbm2(q * 1.3 - uWd * uT * 0.07 * uScud, 4);
          vec3 sc = uStormC * (0.75 + 0.6 * base) * mix(1.35, 0.5, pow(y2, 0.45));
          sc = mix(sc, uStormC * 1.6, sm(0.45, 0.8, scud) * 0.35 * sm(0.0, 0.25, y2));
          sc = mix(sc, uStormC * 0.55, sm(0.5, 0.9, base + 0.2 * scud) * 0.5);
          sc += uSunC * 0.05 * pow(max(mu, 0.0), 4.0);
          if (rd.y < 0.0) sc = uStormC * 1.1;
          float hole = 0.0;
          if (uEyeO.x > 0.0){
            // inside the eye: a clear hole overhead, ringed by the sunlit eyewall towering from the horizon up to its rim
            // billowed cumulus towers on a cylinder around the camera (no azimuth seam), lit from above and sunward
            vec2 hz = normalize(rd.xz + 1e-5);
            vec3 bp = vec3(hz * 2.6, rd.y * 4.2 - uT * 0.006);
            bp += 0.3 * vec3(fbm3(bp * 1.4, 3), fbm3(bp * 1.4 + 5.3, 3), 0.0);
            float d = fbm3(bp, 6), dUp = fbm3(bp + vec3(0.0, 0.0, 0.07), 6);
            float rim = uEyeO.y + 0.11 * d;
            hole = uEyeO.x * sm(rim - 0.015, rim + 0.03, rd.y);
            float wall = uEyeO.x * sm(-0.02, 0.1, rd.y) * (1.0 - hole);
            float lit = clamp(0.55 + (d - dUp) * 7.0, 0.0, 1.0) * (0.6 + 0.4 * max(dot(-hz, normalize(uSun.xz + 1e-5)), 0.0));
            float up = sm(0.0, rim, rd.y);
            vec3 wc = mix(uStormC * 1.25, vec3(0.97, 0.98, 1.0), lit * mix(0.55, 1.0, up));
            wc = mix(wc, uStormC * 1.5, (1.0 - up) * 0.45);
            wc = mix(wc, vec3(1.0, 0.99, 0.96) * 1.1, sm(rim - 0.05, rim, rd.y) * 0.5);
            wc *= uEyeO.z;
            sc = mix(sc, wc, wall * sm(-0.35, 0.05, d + 0.35 * (1.0 - up)));
          }
          c = mix(c, sc, uStorm * (1.0 - hole));
        }
        return c * 1.05;
      }
      float cloudDen(vec3 p){
        float yy = (p.y - CB) / (CT - CB);
        if (yy < 0.0 || yy > 1.0) return 0.0;
        vec2 q = p.xz / 2600.0 + vec2(uT * 0.003, 0.0);
        float c = fbm2(q, 6) + 0.25 * fbm2(p.xz / 420.0, 4) + uCloud;
        float prof = smoothstep(0.0, 0.12, yy) * smoothstep(1.0, 0.3, yy);
        return smoothstep(0.36, 0.62, c * prof - yy * 0.2 + 0.02) * 0.009;
      }
      float cloudShadow(vec3 p){
        vec3 q = p + uSun * ((CB + 400.0 - p.y) / max(uSun.y, 0.05));
        return 1.0 - 0.7 * smoothstep(0.0, 0.004, cloudDen(vec3(q.x, CB + 400.0, q.z)));
      }
      vec3 fogC(vec3 rd){ return mix(uFogC, uSunC * vec3(0.34, 0.28, 0.22), pow(max(dot(rd, uSun), 0.0), 5.0) * 0.6 * (1.0 - uStorm)); }
      vec3 fog(vec3 col, vec3 rd, float t, float y0){
        float dens = exp(-max(y0, 0.0) / 1600.0);
        float f = 1.0 - exp(-t * dens * uFogK / 11000.0);
        return mix(col, fogC(rd), f);
      }

      // ---------- shadows ----------
      float shadow(vec3 p, float fp){
        float res = 1.0, t = max(fp * 2.0, 0.05);
        for (int i = 0; i < 36; i++){
          vec3 q = p + uSun * t;
          if (q.y > 140.0) break;
          float hh = ground(q.xz, max(fp, t * 0.01));
          float dh = q.y - hh;
          res = min(res, 8.0 * dh / t);
          if (res < 0.0) break;
          t += clamp(dh * 0.6, fp + 0.08, 40.0);
        }
        return smoothstep(0.0, 1.0, res);
      }
      float meshShadow(vec3 p){
        if (uSMon < 0.5) return 1.0;
        vec4 sc = uSMat * vec4(p, 1.0); sc.xyz /= sc.w;
        if (sc.x < 0.0 || sc.x > 1.0 || sc.y < 0.0 || sc.y > 1.0 || sc.z > 1.0) return 1.0;
        float s = 0.0;
        for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++){
          float dd = unpackRGBAToDepth(texture2D(uSM, sc.xy + vec2(float(i), float(j)) * uSMtx * 1.5));
          s += step(sc.z - 0.0006, dd);
        }
        return s / 25.0;
      }

      // ---------- surfaces ----------
      // albedo of the ground (sea bed included); wet = 0..1
      vec3 albedo(vec3 p, vec3 n, vec4 m, float fp, out float wet, out float rough){
        float x = p.x, c = p.z - coastZ(x);
        float n1 = fbm2(p.xz * 0.05, 4), n2 = fp < 0.4 ? fbm2(p.xz * 1.1, 3) : 0.0;
        // coral sand: near-white with warm and grey patches
        vec3 sand = mix(vec3(0.62, 0.56, 0.45), vec3(0.74, 0.69, 0.58), sm(-0.4, 0.5, n1)) * (0.9 + 0.14 * n2);
        if (fp < 0.05) sand *= 0.93 + 0.1 * fbm2(p.xz * 6.0, 3);
        // sea grass and algae turf on the lagoon floor
        float grassS = sm(-4.0, -15.0, c) * sm(0.05, 0.35, fbm2(p.xz * 0.03 + 11.0, 4)) * (1.0 - m.z);
        vec3 bed = mix(sand, vec3(0.2, 0.22, 0.1) * (0.8 + 0.4 * n2), grassS * 0.85);
        // coral heads: ochre, olive, purplish rubble, a few bleached tops
        float ci = fbm2(p.xz * 0.15, 3);
        // turf algae over dead coral rock: olive and rust browns, darker than the sand between
        vec3 coral = mix(vec3(0.27, 0.21, 0.12), vec3(0.17, 0.18, 0.09), sm(-0.3, 0.3, ci));
        coral = mix(coral, vec3(0.3, 0.22, 0.22), sm(0.25, 0.6, fbm2(p.xz * 0.4 + 3.0, 3)) * 0.4 * sm(0.6, 0.15, fp));
        coral = mix(coral, vec3(0.75, 0.72, 0.64), sm(0.45, 0.8, n2) * 0.35);
        coral *= 0.7 + 0.45 * (fp < 0.3 ? fbm2(p.xz * 6.0, 3) * 0.5 + 0.5 : 0.5);
        bed = mix(bed, coral, m.z);
        // deep sea floor: muddier sand
        bed = mix(bed, vec3(0.42, 0.42, 0.36), sm(-380.0, -700.0, c + reefShift(x)));
        // beach berm: dry sand; wrack line of dead leaves and coconut husks
        vec3 soil = mix(vec3(0.36, 0.3, 0.2), vec3(0.3, 0.34, 0.15), sm(-0.3, 0.4, n1));
        vec3 alb = c < 0.0 ? bed : mix(sand, soil, sm(28.0, 60.0, c));
        float wr = sm(1.5, 0.0, abs(c - 21.0 - 3.0 * vn2(p.xz * 0.05))) * sm(0.0, 0.5, fbm2(p.xz * 0.7, 3));
        alb = mix(alb, vec3(0.2, 0.15, 0.08), wr * 0.7 * sm(0.0, 4.0, c));
        // grove floor: sandy soil, patchy grass, leaf litter
        vec3 grass = mix(vec3(0.24, 0.29, 0.1), vec3(0.42, 0.4, 0.18), sm(-0.3, 0.5, fbm2(p.xz * 0.04, 4)));
        grass = mix(grass, vec3(0.4, 0.32, 0.2), sm(0.1, 0.5, fbm2(p.xz * 0.25 + 4.0, 3)) * 0.45);
        alb = mix(alb, grass, m.w * sm(-0.2, 0.25, fbm2(p.xz * 0.012 + 2.0, 3) + 0.25) * (1.0 - m.y));
        // forest / scrub canopy
        vec3 leaf = mix(vec3(0.035, 0.08, 0.025), vec3(0.1, 0.17, 0.05), sm(-0.3, 0.6, fbm2(p.xz * 0.15, 3)));
        leaf = mix(leaf, vec3(0.16, 0.2, 0.07), sm(0.4, 0.8, fbm2(p.xz * 0.05 + 8.0, 3)) * 0.4);
        alb = mix(alb, leaf, m.y);
        // headland rock
        vec3 rock = mix(vec3(0.24, 0.23, 0.21), vec3(0.45, 0.43, 0.39), sm(-0.4, 0.5, fbm2(p.xz * 0.2 + p.y * 0.3, 4)));
        rock = mix(rock, vec3(0.05, 0.05, 0.05), sm(1.4, 0.0, p.y));
        alb = mix(alb, rock, m.x);
        // silt left by the flood
        float silt = uSilt.y * sm(uSilt.x, uSilt.x - 40.0, c) * sm(-30.0, 0.0, c) * (1.0 - m.x * 0.5);
        alb = mix(alb, vec3(0.22, 0.17, 0.11) * (0.8 + 0.35 * n2), silt * (1.0 - m.y * 0.2));
        wet = clamp(sm(uWetTop + 0.2, uWetTop - 0.25, p.y) + silt * 0.22 * sm(0.1, 0.6, fbm2(p.xz * 0.06 + 3.0, 3) + 0.3), 0.0, 1.0) * (1.0 - m.y);
        rough = mix(0.9, 0.25, wet);
        alb *= mix(1.0, mix(0.55, 0.5, m.z), wet);
        // pitted coral rock holds water in its pores but has no mirror sheen
        wet *= 1.0 - 0.5 * m.z;
        return alb;
      }
      vec3 light(vec3 p, vec3 n, vec3 rd, vec3 alb, float wet, float occ, float fp, float shTerrain){
        float sh = shTerrain * cloudShadow(p) * meshShadow(p);
        float dif = max(dot(n, uSun), 0.0);
        vec3 col = alb * (uSunC * dif * sh + uAmb * (0.45 + 0.55 * n.y) * 0.6 * occ + uSunC * vec3(0.06, 0.055, 0.045) * occ);
        vec3 R = reflect(rd, n);
        float fr = 0.02 + 0.98 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
        // the sun glint only where the bumps are resolved: no far sparkle
        col += wet * (sky(R) * fr * 0.8 + uSunC * pow(max(dot(R, uSun), 0.0), 160.0) * 3.0 * sh * sm(0.25, 0.04, fp));
        return col;
      }
      vec3 shadeGround(vec3 p, vec3 rd, float fp){
        vec4 m; ground(p.xz, fp, m);
        float e = max(fp, 0.01);
        vec3 n = normalize(vec3(ground(p.xz - vec2(e, 0.0), fp) - ground(p.xz + vec2(e, 0.0), fp), 2.0 * e,
                                ground(p.xz - vec2(0.0, e), fp) - ground(p.xz + vec2(0.0, e), fp)));
        float wet, rough;
        vec3 alb = albedo(p, n, m, fp, wet, rough);
        // canopy: dark gaps between crowns, translucent sunlit edges
        float occ = mix(1.0, 0.45 + 0.55 * smoothstep(0.4, 0.95, n.y), m.y);
        float sh = shadow(p + n * max(fp, 0.02) * 2.0, fp);
        if (uStorm > 0.0){ alb *= mix(1.0, mix(0.5, 0.7, m.y), uStorm); wet = max(wet, 0.6 * uStorm * (1.0 - m.y)); }
        vec3 col = light(p, n, rd, alb, wet, occ, fp, sh);
        col += m.y * alb * uSunC * 0.35 * pow(max(dot(rd, uSun), 0.0), 3.0) * sh;
        return col;
      }
      // sea bed seen through the water: sunlight attenuated on the way down, caustics, absorbed on the way up
      vec3 caustic(vec2 xz){
        vec2 q = xz * 1.3 + vec2(uT * 0.21, uT * 0.13);
        q += 0.7 * vec2(vn2(q * 0.25 + uT * 0.07), vn2(q * 0.25 + 4.0 - uT * 0.05));
        vec3 a = vor2(q);
        vec3 b = vor2(q * 1.41 + 5.0 - vec2(uT * 0.16, uT * 0.23));
        float ca = smoothstep(0.18, 0.0, a.y - a.x), cb = smoothstep(0.18, 0.0, b.y - b.x);
        return vec3(ca * 0.6 + cb * 0.45, ca * 0.66 + cb * 0.5, ca * 0.7 + cb * 0.55);
      }
      vec3 shadeWater(vec3 p, vec3 rd, float t, float fp){
        float bb, pool; float h0 = water(p.xz, fp, bb, pool);
        float e = max(fp, 0.03);
        vec3 n = normalize(vec3(h0 - water(p.xz + vec2(e, 0.0), fp), e, h0 - water(p.xz + vec2(0.0, e), fp)));
        float x = p.x, c = p.z - coastZ(x), r = c + reefShift(x);
        float g0 = ground(p.xz, max(fp, 0.05));
        float depth = max(h0 - g0, 0.0);
        float mud = clamp(uMud + sm(0.1, 1.2, bb) * 0.9, 0.0, 1.0);
        vec3 K = mix(vec3(0.42, 0.075, 0.055), vec3(1.6, 1.9, 2.4), mud);       // absorption per metre
        // in-scatter (fraction of sun + sky): turquoise over sand, ocean navy once the bed drops out of sight
        vec3 SC = mix(mix(vec3(0.0, 0.045, 0.05), vec3(0.0012, 0.006, 0.0115), sm(12.0, 45.0, depth)), vec3(0.11, 0.09, 0.055), mud);
        float sh = cloudShadow(p) * meshShadow(p);
        // refraction: two fixed-point steps onto the bed
        vec3 rr = refract(rd, n, 1.0 / 1.333);
        float L = depth / max(-rr.y, 0.2);
        vec3 pb = p + rr * L;
        for (int i = 0; i < 2; i++){ float gb = ground(pb.xz, max(fp, 0.05)); L = clamp((p.y - gb) / max(-rr.y, 0.2), 0.0, 60.0); pb = p + rr * L; }
        vec3 trans;
        vec3 Lin = uSunC * max(uSun.y, 0.0) * sh + uAmb * 0.6;
        vec3 inscat = SC * Lin * 3.0;
        if (L < 40.0 && mud < 0.95){
          vec4 m; float gb = ground(pb.xz, max(fp, 0.05), m);
          float wd, rg; vec3 alb = albedo(vec3(pb.x, gb, pb.z), vec3(0.0, 1.0, 0.0), m, max(fp, 0.05), wd, rg);
          float dB = max(h0 - gb, 0.0);
          vec3 down = exp(-K * dB / max(uSun.y, 0.2));
          float caus = 1.0;
          vec3 cs = caustic(pb.xz) * sm(0.05, 0.6, dB) * (1.0 - mud) * sm(0.12, 0.02, fp);
          vec3 bedc = alb * (uSunC * max(uSun.y, 0.0) * sh * (0.75 + 1.1 * cs) * down + uAmb * 0.5 * exp(-K * dB));
          vec3 ext = exp(-K * L);
          trans = bedc * ext + inscat * (1.0 - ext);
        } else trans = inscat;
        vec3 R = reflect(rd, n);
        float fr = 0.02 + 0.98 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
        if (uStorm > 0.0) trans = mix(trans, vec3(0.025, 0.04, 0.038) * (uAmb * 2.0 + 0.1), uStorm * sm(-2.0, -25.0, c - 0.0));
        vec3 col = mix(trans, sky(R), fr);
        col += uSunC * (pow(max(dot(R, uSun), 0.0), 1400.0) * 30.0 + pow(max(dot(R, uSun), 0.0), 120.0) * 0.5) * sh * (1.0 - mud * 0.6);
        // foam: the breaker line on the reef edge, swash at the beach, white water on the bore
        float lace = fbm2(p.xz * 0.3 + vec2(0.0, uT * 0.3), fp < 1.0 ? 5 : 3);
        float swl = 0.42 * sin(p.z * 0.055 + x * 0.012 + uT * 0.62 + 0.8 * vn2(p.xz * 0.004));
        float br = sm(-380.0, -345.0, r) * sm(-310.0, -338.0, r) * sm(0.05, 0.4, swl) * uSwell * step(uSea.x, -0.0 + 0.5) * sm(-1.5, -0.2, uSea.x + 1.0);
        float streak = fbm2(vec2(p.x * 0.05, p.z * 0.35) + vec2(0.0, uT * 0.2), 4);
        float trail = sm(-345.0, -325.0, r) * sm(-285.0, -330.0, r) * sm(0.25, 0.6, streak + 0.5 * lace) * 0.35 * uSwell * sm(-1.0, 0.0, uSea.x) * (1.0 - uStorm);
        float swash = sm(3.0, 0.0, abs(c - (0.8 + 1.4 * sin(uT * 0.45 + x * 0.01)))) * 0.7 * sm(-0.7, 0.0, uSea.x);
        float bf = 0.0;
        if (bb > 0.0){
          float f = c - (uSea.y + frontWig(x));
          float fl = mix(1.0, -1.0, uSea.w);
          vec2 q = vec2(x * 0.05, c * 0.05 - uT * 0.75 * fl);
          float st = fbm2(q * vec2(1.0, 0.35) + 2.0, fp < 0.5 ? 5 : 3);
          // the steep face: dark green-grey water streaked with foam; the white water rides the crest and behind it
          float face = sm(-9.0, -5.0, f) * sm(3.0, 0.5, f) * sm(0.3, 2.0, bb) * (1.0 - uSea.w);
          col = mix(col, vec3(0.01, 0.03, 0.032) * (uAmb * 1.3 + uSunC * 0.08) + sky(R) * fr * 0.4, face * 0.9);
          float ht = clamp((h0 - uSea.x) / max(bb, 0.5), 0.0, 1.2);
          float fall = fbm2(vec2(x * 0.32, h0 * 0.35 + uT * 1.6), fp < 0.5 ? 4 : 3) + 0.25 * vn2(vec2(x * 0.9, h0 * 1.2 + uT * 3.0));
          // v: 0 at the toe of the face, 1 at its top; white water pours from the lip in streaks
          float v = sm(3.0, -9.0, f);
          float cascade = face * sm(0.72, 0.95, v + 0.55 * fall - 0.05);
          // churning white skirt where the face hits the water ahead of it
          float toe = sm(3.5, 1.5, f) * sm(-1.0, 0.8, f) * sm(0.3, 2.0, bb) * sm(-0.15, 0.25, fbm2(vec2(x * 0.3, uT * 1.4), 3) + 0.4 * sm(1.5, 2.8, f));
          cascade = max(cascade, toe * 0.9 * (1.0 - uSea.w));
          float frontF = sm(-30.0, -10.0, f) * sm(-2.0, -6.5, f);
          bf = max(frontF * sm(-0.05, 0.35, lace + 0.12) * 0.9, sm(0.2, 0.55, st) * sm(0.2, 1.5, bb) * mix(0.4, 0.35, uSea.w) * (1.0 - face));
          // the churning brown body behind the crest: dark turbid water, not a lit lagoon
          col = mix(col, vec3(0.11, 0.085, 0.055) * (1.0 + 1.8 * uMud) * (uAmb * 1.1 + uSunC * 0.25 * max(n.y, 0.0) * sh) + sky(R) * fr * (0.3 - 0.16 * uMud), sm(0.3, 1.5, bb) * sm(-6.0, -20.0, f) * sm(-460.0, -300.0, c) * 0.92);
          bf = max(bf, cascade);
          bf = max(bf, face * sm(0.3, 0.6, fbm2(vec2(x * 0.15, h0 * 0.5 + uT * 1.2), 3)) * 0.3);
          bf = max(bf, sm(0.0, -0.6, n.y - 0.75) * sm(0.2, 1.0, bb) * (1.0 - face * sm(0.92, 0.7, v)));
        }
        float sp = 0.0;
        if (uSpume > 0.0){
          // gale foam: whitecaps break on every crest and the wind combs the foam into long streaks along its path
          vec2 wp = vec2(dot(p.xz, uWd), dot(p.xz, vec2(-uWd.y, uWd.x)));
          float crest = sm(0.5, 1.5, (h0 - uSea.x) / max(uSpume, 0.3));
          float st = fbm2(vec2(wp.x * 0.012 - uT * 0.35, wp.y * 0.22), fp < 0.5 ? 5 : 3);
          // many thin parallel streaks combed along the wind (ridged noise, stretched downwind, wavering), patchy via st
          float wy = wp.y * 0.55 + 3.0 * fbm2(wp * vec2(0.004, 0.02), 2) + 0.6 * fbm2(wp * vec2(0.03, 0.1), 2);
          float rid = 1.0 - abs(fbm2(vec2(wp.x * 0.012 - uT * 0.5, wy), 2) * 2.0);
          float rid2 = 1.0 - abs(fbm2(vec2(wp.x * 0.02 - uT * 0.7, wy * 2.1 + 7.0), 2) * 2.0);
          float fine = max(sm(0.88, 0.99, rid), 0.5 * sm(0.9, 0.99, rid2)) * sm(0.15, 0.6, st + 0.15);
          // fine lanes fade to their mean with distance (no shimmer once a lane is narrower than a pixel)
          float lf = sm(0.08, 0.5, fp);
          float lanes = mix(fine * 0.55, 0.14 * sm(0.3, 0.7, st), lf) * sm(0.2, 0.6, uSpume);
          // near the lens: torn lace and bubbles between the streaks
          if (fp < 0.1){
            float la = fbm2(vec2(wp.x * 0.09 - uT * 1.3, wp.y * 0.45), 4);
            lanes = max(lanes, sm(0.55, 0.72, la) * 0.6 * uSpume * (1.0 - sm(0.03, 0.1, fp)));
          }
          float cap = crest * sm(-0.1, 0.35, lace);
          // past ~250 km/h the crests smear into sheets of white; the troughs stay dark
          float wb = fbm2(vec2(wp.x * 0.006 - uT * 0.3, wp.y * 0.02), 3);
          float white = sm(0.85, 1.0, uSpume) * sm(0.1, 0.4, wb) * crest * 0.45;
          sp = clamp(max(max(cap, lanes * 0.8), white), 0.0, 1.0);
        }
        // gale surf: a wide churned band of white water along the beach, blurring the waterline
        float surf = 0.0;
        if (uSpume > 0.0) surf = sm(-22.0, -2.0, c) * sm(-0.3, 0.45, lace + 0.25 * sin(c * 0.6 - uT * 2.2 + x * 0.05)) * uSpume * 0.85;
        float foam = clamp(br * sm(-0.2, 0.4, lace + 0.3) + trail + swash * sm(-0.1, 0.5, lace + 0.2) + bf + sp + surf, 0.0, 1.0);
        foam *= 1.0 - pool;
        vec3 fc = mix(vec3(0.9, 0.92, 0.93), vec3(0.72, 0.66, 0.55), mud * 0.6) * (uSunC * max(dot(n, uSun), 0.25) * sh + uAmb * 0.8) * mix(1.0, 0.7, sm(0.2, 1.5, bb));
        col = mix(col, fc, foam);
        return col;
      }

      void main(){
        vec3 rd = normalize(vDir), ro = uCam;
        vec3 col; float tHit = -1.0;
        float t = 0.0, tmax = 80000.0, ymax = 260.0;
        if (ro.y > ymax){ t = rd.y < 0.0 ? (ro.y - ymax) / -rd.y : tmax; }
        bool hit = false, esc = false; float lt = t;
        for (int i = 0; i < 420; i++){
          if (t > tmax){ esc = true; break; }
          vec3 p = ro + rd * t;
          if (p.y > ymax && rd.y > 0.0){ esc = true; break; }
          float fp = t * uFpK;
          float hh = max(ground(p.xz, fp), water(p.xz, fp));
          float dh = p.y - hh;
          if (dh < fp * 0.5){ hit = true; break; }
          lt = t;
          t += max(dh * 0.42, fp * 0.8 + 1e-4 + t * 0.0025);
        }
        // grazing rays over flat sand can run out of steps: they are still skimming the surface, not the sky
        if (!hit && !esc) hit = true;
        float isW = 0.0;
        if (hit){
          float ta = lt, tb = t;
          for (int i = 0; i < 7; i++){ float tm = 0.5 * (ta + tb); vec3 p = ro + rd * tm; float fp = tm * uFpK;
            if (p.y - max(ground(p.xz, fp), water(p.xz, fp)) < 0.0) tb = tm; else ta = tm; }
          t = tb; tHit = t;
          vec3 p = ro + rd * t; float fp = t * uFpK;
          float gh = ground(p.xz, fp), wh = water(p.xz, fp);
          if (wh > gh){ isW = 1.0; col = shadeWater(vec3(p.x, wh, p.z), rd, t, fp); }
          else col = shadeGround(p, rd, fp);
          col = fog(col, rd, t, ro.y);
        } else {
          col = sky(rd);
          if (rd.y < 0.0){ float ts = (ro.y - uSea.x) / -rd.y; col = fog(shadeWater(ro + rd * ts, rd, ts, ts * uFpK), rd, ts, ro.y); tHit = ts; }
        }
        // spray and mist torn off the bore front: a soft layer hugging the water, thickest just behind the front
        if (uSpray > 0.0 && uSea.z > 0.0){
          float tEnd = tHit > 0.0 ? min(tHit, 2500.0) : 2500.0;
          float dt = tEnd / 16.0, tt = dt * hash12(gl_FragCoord.xy), tr = 1.0; vec3 acc = vec3(0.0);
          for (int i = 0; i < 16; i++){
            vec3 p = ro + rd * tt;
            float c = p.z - coastZ(p.x), f = c - (uSea.y + frontWig(p.x));
            float band = sm(-160.0, -15.0, f) * sm(25.0, 0.0, f);
            float top = uSea.x + boreB(p.x, c) * 1.25 + 3.0;
            float d = band * sm(top, top - 8.0, p.y) * sm(0.0, 0.6, fbm2(vec2(p.x * 0.03, p.y * 0.05 + c * 0.02 - uT * 0.4), 3) + 0.4);
            if (d > 0.0){
              float a = 1.0 - exp(-d * uSpray * dt * 0.05);
              vec3 lc = uSunC * (0.25 + 0.6 * pow(max(dot(rd, uSun), 0.0), 3.0)) + uAmb * 0.9;
              acc += tr * a * lc * 0.85; tr *= 1.0 - a;
            }
            tt += dt;
          }
          col = col * tr + acc;
        }
        // spume blown off the crests: a low white haze streaming downwind just above the sea
        if (uSpume > 0.0){
          float tEnd = tHit > 0.0 ? min(tHit, 1500.0) : 1500.0;
          float dt = tEnd / 14.0, tt = dt * hash12(gl_FragCoord.xy + 1.3), tr = 1.0; vec3 acc = vec3(0.0);
          for (int i = 0; i < 14; i++){
            vec3 p = ro + rd * tt;
            float top = uSea.x + 1.0 + 9.0 * uSpume * uSpume;
            if (p.y < top + 2.0){
              vec2 wp = vec2(dot(p.xz, uWd), dot(p.xz, vec2(-uWd.y, uWd.x)));
              float n = fbm2(vec2(wp.x * 0.006 - uT * 0.5, wp.y * 0.02 + p.y * 0.05), 3);
              float d = sm(top, uSea.x, p.y) * (0.08 + 0.92 * sm(0.4, 0.75, n)) * uSpume * uSpume;
              float a = 1.0 - exp(-d * dt * 0.02);
              acc += tr * a * (uAmb * 1.2 + uStormC * 1.4); tr *= 1.0 - a;
            }
            tt += dt;
          }
          col = col * tr + acc;
        }
        // cumulus deck
        if (uStorm < 0.99) {
          float ta = (CB - ro.y) / rd.y, tb = (CT - ro.y) / rd.y;
          if (ta > tb){ float xx = ta; ta = tb; tb = xx; }
          ta = max(ta, 0.0); tb = min(min(tb, tHit > 0.0 ? tHit : 1e9), 90000.0);
          if (tb > ta && rd.y > 0.0){
            float dt = (tb - ta) / 26.0, tt = ta + dt * hash12(gl_FragCoord.xy + 3.7);
            vec3 acc = vec3(0.0); float tr = 1.0;
            for (int i = 0; i < 26; i++){
              vec3 p = ro + rd * tt;
              float dd = cloudDen(p);
              if (dd > 0.0){
                float ls = cloudDen(p + uSun * 110.0) + cloudDen(p + uSun * 320.0);
                float lt2 = exp(-ls * 260.0);
                float hgt = (p.y - CB) / (CT - CB);
                vec3 cc = uSunC * (0.3 + 1.1 * lt2) * (0.65 + 0.35 * hgt) * 0.42 + uAmb * (0.6 + 0.5 * hgt);
                float a = 1.0 - exp(-dd * dt);
                acc += tr * a * cc; tr *= 1.0 - a;
                if (tr < 0.02) break;
              }
              tt += dt;
            }
            col = mix(col, col * tr + fog(acc, rd, ta, ro.y), 1.0 - uStorm);
          }
        }
        gl_FragColor = vec4(col, 1.0);
        if (tHit > 0.0){ vec4 cc = uVP * vec4(ro + rd * tHit, 1.0); gl_FragDepth = clamp(cc.z / cc.w * 0.5 + 0.5, 0.0, 1.0); }
        else gl_FragDepth = 0.999999;
      }`,
  });
  const quad = fsQuad(mat); quad.renderOrder = -1;
  scene.add(quad);

  // ---------- lights for the rasterised props, matched to the ray-marched sun and sky ----------
  const sunL = new THREE.DirectionalLight(0xffffff, 1);
  sunL.castShadow = true;
  sunL.shadow.mapSize.set(4096, 4096);
  sunL.shadow.bias = -0.0003; sunL.shadow.normalBias = 0.03;
  scene.add(sunL, sunL.target);
  u.uSMat.value = sunL.shadow.matrix;
  const hemi = new THREE.HemisphereLight(0xffffff, 0xffffff, Math.PI);
  scene.add(hemi);
  const aimShadow = (cx, cz, r) => {
    sunL.target.position.set(cx, 0, cz);
    sunL.position.set(cx, 0, cz).addScaledVector(u.uSun.value, 600);
    const c = sunL.shadow.camera; c.left = -r; c.right = r; c.top = r; c.bottom = -r; c.near = 1; c.far = 1300; c.updateProjectionMatrix();
    u.uSMtx.value = 1 / 4096;
  };
  const syncLights = () => {
    const s = u.uSunC.value, a = u.uAmb.value;
    sunL.color.setRGB(s.x, s.y, s.z).multiplyScalar(1 / Math.max(s.x, s.y, s.z));
    sunL.intensity = Math.max(s.x, s.y, s.z) * Math.PI;
    hemi.color.setRGB(a.x * 0.6, a.y * 0.6, a.z * 0.6);
    hemi.groundColor.setRGB(0.12 * s.x / 3, 0.11 * s.y / 3, 0.09 * s.z / 3);
    hemi.intensity = Math.PI;
  };

  // fog + wetness for prop materials, the same as the terrain pass
  const propU = { uCam: u.uCam, uSun: u.uSun, uSunC: u.uSunC, uFogC: u.uFogC, uFogK: u.uFogK, uWetTop: u.uWetTop, uMud: u.uMud, uT: u.uT };
  const PROP_HEAD = /* glsl */ `uniform vec3 uCam, uSun, uSunC, uFogC; uniform float uFogK, uWetTop, uMud, uT;`;
  const PROP_FOG = /* glsl */ `{
    vec3 rdF = normalize(vWP - uCam); float tF = length(vWP - uCam);
    float dens = exp(-max(uCam.y, 0.0) / 1600.0);
    float fF = 1.0 - exp(-tF * dens * uFogK / 11000.0);
    vec3 fcF = mix(uFogC, uSunC * vec3(0.34, 0.28, 0.22), pow(max(dot(rdF, uSun), 0.0), 5.0) * 0.6);
    gl_FragColor.rgb = mix(gl_FragColor.rgb, fcF, fF); }`;

  const setCam = (pos, look, fovDeg = fov, roll = 0) => {
    cam.fov = fovDeg; cam.position.set(...pos); cam.up.set(Math.sin(roll), Math.cos(roll), 0);
    cam.lookAt(...look); cam.updateProjectionMatrix(); cam.updateMatrixWorld();
  };
  const setSea = (o) => {
    Object.assign(sea, o);
    u.uSea.value.set(sea.level, sea.front, sea.boreH, sea.back);
  };
  function sync(t) {
    u.uT.value = t;
    const ty = Math.tan((cam.fov * Math.PI) / 360);
    u.uTan.value.set(ty * cam.aspect, ty); u.uCamWorld.value.copy(cam.matrixWorld); u.uCam.value.copy(cam.position);
    u.uVP.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    u.uFpK.value = ty / 540;
    syncLights();
  }
  let firstDraw = true;
  function draw(renderer) {
    renderer.setClearColor(0x000000, 1); renderer.clear(true, true, true);
    const au = renderer.shadowMap.autoUpdate;
    renderer.shadowMap.autoUpdate = false; renderer.shadowMap.needsUpdate = true;
    if (firstDraw && !sunL.shadow.map) { renderer.render(scene, cam); renderer.shadowMap.needsUpdate = true; renderer.clear(true, true, true); }
    firstDraw = false;
    u.uSM.value = sunL.shadow.map ? sunL.shadow.map.texture : null;
    u.uSMon.value = sunL.shadow.map ? 1 : 0;
    renderer.render(scene, cam);
    renderer.shadowMap.autoUpdate = au;
  }
  const dispose = () => { scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); sunL.shadow.map?.dispose(); };
  return { scene, cam, u, sunL, hemi, aimShadow, setCam, setSea, sync, draw, dispose, propU, PROP_HEAD, PROP_FOG };
}

// a balanced daylight grade for the coast scenes
export const coastGrade = (o = {}) => ({
  exposure: 0.92, bloom: 0.25, bloomThreshold: 0.9, bloomRadius: 0.4, hdrMax: 6, vignette: 0.38, sat: 1.06, contrast: 1.07,
  chroma: 0.0008, grain: 0.03, lift: [0.004, 0.004, 0.008], gain: [1.0, 0.99, 0.97], flash: [1, 1, 1, 0], ...o,
});
export { lerp, clamp, smooth };
