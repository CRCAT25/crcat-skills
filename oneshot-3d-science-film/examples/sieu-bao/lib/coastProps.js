// Rasterised props for the coast: coconut palms, stilt huts with thatch, outrigger boats. Built procedurally,
// instanced, lit by the coast's sun/sky lights, fogged and shadowed like the ray-marched terrain.
// Every prop merges into one geometry with attributes aK (material kind) and color; one shader handles all kinds:
// 0 wood/trunk, 1 palm frond (cut into leaflets), 2 plain paint, 3 thatch, 4 woven bamboo wall.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { rng } from './kit.js';
import { groundY, crossC, coastZ } from './coast.js';

const tag = (g, rgb, k) => {
  g = g.index ? g.toNonIndexed() : g;
  const n = g.attributes.position.count;
  const col = new Float32Array(n * 3), kk = new Float32Array(n);
  for (let i = 0; i < n; i++) { col.set(rgb, i * 3); kk[i] = k; }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setAttribute('aK', new THREE.BufferAttribute(kk, 1));
  if (!g.attributes.uv) g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(n * 2), 2));
  for (const a of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'color', 'aK'].includes(a)) g.deleteAttribute(a);
  return g;
};
const at = (g, x, y, z, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) => {
  const m = new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz, 'YXZ')), new THREE.Vector3(sx, sy, sz));
  return g.applyMatrix4(m);
};

// ---------- coconut palm (local origin at the trunk base, height ~ H) ----------
function palmGeo(seed) {
  const r = rng(seed), parts = [];
  const H = 9 + r() * 7, lean = 0.08 + r() * 0.2, la = r() * Math.PI * 2;
  const bend = 0.5 + r() * 1.2;
  const P = (h) => { const k = (h / H) ** 1.6 * H * lean * bend; return new THREE.Vector3(Math.cos(la) * k, h, Math.sin(la) * k); };
  const pts = []; for (let i = 0; i <= 14; i++) pts.push(P((i / 14) * H));
  const curve = new THREE.CatmullRomCurve3(pts);
  const tube = new THREE.TubeGeometry(curve, 28, 1, 9, false);
  // taper: thick flared base, slimmer below the crown
  const pos = tube.attributes.position, uv = tube.attributes.uv;
  for (let i = 0; i < pos.count; i++) {
    const s = uv.getX(i), c = curve.getPointAt(Math.min(s, 1));
    const rad = 0.17 + 0.16 * Math.exp(-s * 18) + 0.03 * (1 - s);
    const d = new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i)).sub(c);
    d.setLength(rad); pos.setXYZ(i, c.x + d.x, c.y + d.y, c.z + d.z);
    uv.setXY(i, uv.getX(i) * H, uv.getY(i));
  }
  tube.computeVertexNormals();
  parts.push(tag(tube, [0.42, 0.38, 0.32], 0));
  const top = curve.getPointAt(1);
  // crown: frond bases and coconuts
  parts.push(tag(at(new THREE.SphereGeometry(0.42, 10, 8), top.x, top.y - 0.15, top.z, 0, 0, 0, 1, 0.8, 1), [0.3, 0.28, 0.16], 2));
  const nuts = 4 + Math.floor(r() * 6);
  for (let i = 0; i < nuts; i++) {
    const a = r() * Math.PI * 2, rr = 0.32;
    parts.push(tag(at(new THREE.SphereGeometry(0.15, 8, 6), top.x + Math.cos(a) * rr, top.y - 0.45 - r() * 0.25, top.z + Math.sin(a) * rr),
      r() < 0.6 ? [0.32, 0.36, 0.1] : [0.45, 0.32, 0.12], 2));
  }
  const nF = 16 + Math.floor(r() * 8);
  for (let f = 0; f < nF; f++) {
    const a = f * 2.39996 + r() * 0.3;
    const tier = f / nF;                                   // 0 = young upright, 1 = old drooping
    const e0 = 1.0 - tier * 1.25 + (r() - 0.5) * 0.25;
    const L = 3.8 + r() * 1.6, droop = 0.35 + tier * 0.55 + r() * 0.15;
    const dir = new THREE.Vector3(Math.cos(a), 0, Math.sin(a)), side = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
    const N = 18, posA = [], uvA = [], idx = [];
    const twist = (r() - 0.5) * 0.6;
    for (let i = 0; i <= N; i++) {
      const s = i / N;
      const hz = L * s * Math.cos(e0), vy = L * s * Math.sin(e0) - droop * L * s * s * 1.2;
      const c = top.clone().addScaledVector(dir, hz + 0.2).add(new THREE.Vector3(0, vy, 0));
      const w = 1.25 * Math.pow(Math.sin(Math.PI * Math.min(1, s * 1.08)), 0.7) * (s < 0.06 ? s / 0.06 : 1);
      const fold = 0.35 + 0.2 * tier;
      for (const sg of [-1, 0, 1]) {
        const sd = side.clone().applyAxisAngle(dir, twist * s);
        const p = c.clone().addScaledVector(sd, sg * w * 0.5);
        p.y -= Math.abs(sg) * w * fold;
        posA.push(p.x, p.y, p.z); uvA.push(s, sg);
      }
    }
    for (let i = 0; i < N; i++) for (let j = 0; j < 2; j++) {
      const a0 = i * 3 + j, b0 = a0 + 1, c0 = a0 + 3, d0 = a0 + 4;
      idx.push(a0, c0, b0, b0, c0, d0);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(posA, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uvA, 2));
    g.setIndex(idx); g.computeVertexNormals();
    const old = tier > 0.8 && r() < 0.5;
    parts.push(tag(g, old ? [0.34, 0.3, 0.1] : [0.09 + r() * 0.04, 0.2 + r() * 0.05, 0.04], 1));
  }
  return { geo: mergeGeometries(parts), H };
}

// ---------- stilt hut: raised floor, woven walls, a steep thatched gable roof ----------
function hutGeo(seed) {
  const r = rng(seed), parts = [];
  const w = 3.6 + r() * 1.4, d = 3.2 + r() * 1.2, st = 1.0 + r() * 0.5, wh = 2.1;
  const wood = [0.36, 0.27, 0.18];
  for (const sx of [-1, 1]) for (const sz of [-1, 0, 1]) parts.push(tag(at(new THREE.CylinderGeometry(0.08, 0.1, st + 0.3, 6), sx * w * 0.46, (st + 0.3) / 2 - 0.3, sz * d * 0.46), wood, 0));
  parts.push(tag(at(new THREE.BoxGeometry(w + 0.4, 0.14, d + 0.4), 0, st, 0), [0.4, 0.31, 0.2], 0));
  // walls: four woven panels, a doorway on the front
  const wall = [0.62, 0.52, 0.34];
  parts.push(tag(at(new THREE.BoxGeometry(w, wh, 0.06), 0, st + wh / 2, -d / 2), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(0.06, wh, d), -w / 2, st + wh / 2, 0), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(0.06, wh, d), w / 2, st + wh / 2, 0), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(w * 0.32, wh, 0.06), -w * 0.34, st + wh / 2, d / 2), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(w * 0.32, wh, 0.06), w * 0.34, st + wh / 2, d / 2), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(w * 0.36, 0.5, 0.06), 0, st + wh - 0.25, d / 2), wall, 4));
  parts.push(tag(at(new THREE.BoxGeometry(w * 0.36, wh - 0.5, 0.02), 0, st + (wh - 0.5) / 2, d / 2 - 0.25), [0.05, 0.04, 0.03], 2));
  // gable ends
  const rh = 1.9 + r() * 0.6;
  const gab = new THREE.BufferGeometry();
  gab.setAttribute('position', new THREE.Float32BufferAttribute([-w / 2, 0, 0, w / 2, 0, 0, 0, rh, 0], 3));
  gab.computeVertexNormals();
  for (const s of [-1, 1]) parts.push(tag(at(gab.clone(), 0, st + wh, s * d / 2), wall, 4));
  // roof: two thick thatch slabs with overhang
  const ov = 0.55, sl = Math.hypot(w / 2 + ov, rh + ov * rh / (w / 2)), ang = Math.atan2(rh, w / 2);
  for (const s of [-1, 1]) {
    const g = new THREE.BoxGeometry(sl, 0.22, d + 2 * ov);
    parts.push(tag(at(g, s * (w / 4 + ov / 2) * 0.98, st + wh + rh / 2 - ov * Math.tan(ang) / 2 + 0.05, 0, 0, 0, -s * ang), [0.55, 0.44, 0.27], 3));
  }
  parts.push(tag(at(new THREE.BoxGeometry(0.3, 0.3, d + 2 * ov), 0, st + wh + rh + 0.05, 0, 0, 0, Math.PI / 4), [0.4, 0.31, 0.19], 3));
  // ladder
  for (const s of [-1, 1]) parts.push(tag(at(new THREE.CylinderGeometry(0.04, 0.04, st * 1.5, 5), s * 0.3, st / 2, d / 2 + 0.55, 0.55), wood, 0));
  for (let i = 1; i < 4; i++) parts.push(tag(at(new THREE.CylinderGeometry(0.03, 0.03, 0.62, 5), 0, (st * i) / 4, d / 2 + 0.55 + (st * (4 - i)) / 4 * 0.6, 0, 0, Math.PI / 2), wood, 0));
  return mergeGeometries(parts);
}

// ---------- outrigger fishing boat, ~6.5 m ----------
function boatGeo(seed) {
  const r = rng(seed), parts = [];
  const L = 5.5 + r() * 2.0, B = 0.75 + r() * 0.2, D = 0.6;
  const paints = [[0.12, 0.3, 0.55], [0.58, 0.16, 0.12], [0.12, 0.42, 0.36], [0.75, 0.72, 0.62]];
  const pc = paints[Math.floor(r() * paints.length)];
  // hull: a stretched half-ellipsoid, open top, pointed ends
  const hull = new THREE.SphereGeometry(1, 24, 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
  const pos = hull.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const k = Math.pow(Math.abs(x), 1.6);
    z *= 1 - k * 0.85; y *= 1 - k * 0.25;
    pos.setXYZ(i, x * L / 2, y * D + D, z * B / 2);
  }
  hull.computeVertexNormals();
  parts.push(tag(hull, pc, 2));
  // gunwale stripe and thwarts
  parts.push(tag(at(new THREE.BoxGeometry(L * 0.86, 0.07, 0.07), 0, D, B / 2 - 0.02), [0.85, 0.82, 0.74], 2));
  parts.push(tag(at(new THREE.BoxGeometry(L * 0.86, 0.07, 0.07), 0, D, -B / 2 + 0.02), [0.85, 0.82, 0.74], 2));
  for (const x of [-1.2, 0, 1.2]) parts.push(tag(at(new THREE.BoxGeometry(0.22, 0.04, B * 0.9), x, D * 0.85, 0), [0.4, 0.32, 0.22], 0));
  // two booms and the float
  for (const x of [-1.3, 1.3]) parts.push(tag(at(new THREE.CylinderGeometry(0.05, 0.05, 3.4, 6), x * L / 6.5, D + 0.12, 1.6, Math.PI / 2), [0.46, 0.38, 0.28], 0));
  parts.push(tag(at(new THREE.CylinderGeometry(0.11, 0.11, L * 0.62, 8), 0, 0.4, 3.2, 0, 0, Math.PI / 2), [0.5, 0.42, 0.3], 0));
  return mergeGeometries(parts);
}

// ---------- flood debris: a log, a broken plank, a torn piece of thatch, a palm frond ----------
function debrisGeo(k, seed) {
  const r = rng(seed);
  if (k === 0) return mergeGeometries([tag(at(new THREE.CylinderGeometry(0.16 + r() * 0.08, 0.2 + r() * 0.08, 3 + r() * 3, 7), 0, 0.15, 0, 0, 0, Math.PI / 2), [0.33, 0.25, 0.17], 0)]);
  if (k === 1) return mergeGeometries([tag(at(new THREE.BoxGeometry(2.2 + r() * 1.5, 0.05, 0.25), 0, 0.03, 0), [0.45, 0.36, 0.25], 0),
    tag(at(new THREE.BoxGeometry(1.4, 0.05, 0.25), 0.3, 0.06, 0.32, 0, 0.12, 0), [0.42, 0.33, 0.22], 0)]);
  if (k === 2) return mergeGeometries([tag(at(new THREE.BoxGeometry(2.4 + r(), 0.12, 1.6 + r()), 0, 0.06, 0, 0, 0, 0.06), [0.5, 0.4, 0.25], 3)]);
  return mergeGeometries([tag(at(new THREE.CylinderGeometry(0.04, 0.06, 4.5, 5), 0, 0.05, 0, 0, 0, Math.PI / 2), [0.4, 0.36, 0.2], 0),
    ...[-1, 1].map((sd) => tag(at(new THREE.BoxGeometry(3.6, 0.02, 0.7), 0.3, 0.05, sd * 0.4, 0, sd * 0.15, 0), [0.36, 0.36, 0.14], 3))]);
}

// one material for every prop kind
function propMaterial(C, { leaf = true, depth = false } = {}) {
  const U = { uT: C.propU.uT, uWind: { value: 1 }, uGale: { value: 0 }, uWd: { value: new THREE.Vector2(0.6, 0.8) } };
  const vHead = /* glsl */ `attribute float aK; varying float vK; varying vec2 vUv2; varying vec3 vWP; varying vec3 vOP; uniform float uT, uWind, uGale; uniform vec2 uWd;`;
  const vSway = /* glsl */ `
    vK = aK; vUv2 = uv; vOP = position;
    float ph = 0.0;
    #ifdef USE_INSTANCING
      ph = instanceMatrix[3].x * 0.071 + instanceMatrix[3].z * 0.043;
    #endif
    float hh = max(position.y, 0.0);
    vec2 sw = vec2(sin(uT * 0.9 + ph), cos(uT * 0.7 + ph * 1.3)) * 0.0012 * hh * hh * uWind;
    if (aK > 0.5 && aK < 1.5){ sw += vec2(sin(uT * 2.6 + ph * 3.0 + position.x), cos(uT * 2.1 + position.z)) * 0.06 * uv.x * uWind;
      transformed.y += sin(uT * 3.1 + ph * 2.0 + position.x * 1.7) * 0.07 * uv.x * uWind; }
    transformed.xz += sw * step(0.5, hh);
    if (uGale > 0.0){
      // gale: wind direction in the instance's own frame; trunks lean and pump in the gusts, fronds stream downwind
      vec3 wl = vec3(uWd.x, 0.0, uWd.y);
      #ifdef USE_INSTANCING
        wl = normalize(transpose(mat3(instanceMatrix)) * wl);
      #endif
      float gust = 0.75 + 0.25 * sin(uT * 1.7 + ph) + 0.15 * sin(uT * 4.3 + ph * 2.0);
      // only the tall palms bow hard; low props (huts, boats) keep the slight original lean
      float lean = (0.011 + 0.03 * smoothstep(5.0, 8.0, hh)) * hh * hh * uGale * gust;
      transformed.xz += wl.xz * lean * step(0.5, hh);
      transformed.y -= 0.6 * lean * lean / max(hh, 1.0);
      if (aK > 0.5 && aK < 1.5){
        float L = uv.x;
        float fl = sin(uT * 9.0 + ph * 3.0 + L * 2.5) * 0.25 + sin(uT * 14.0 + position.x * 3.0) * 0.12;
        transformed.xz += wl.xz * L * 4.6 * uGale * (0.8 + 0.3 * gust);
        transformed.y += (0.15 * L * uGale) + fl * L * uGale * 0.7;
        transformed.xz += vec2(-wl.z, wl.x) * fl * L * 0.5 * uGale;
      }
      if (aK > 2.5 && aK < 3.5) transformed.y += sin(uT * 11.0 + position.x * 2.0 + ph) * 0.06 * uGale * step(2.0, hh);
    }`;
  const vWorld = /* glsl */ `
    { vec4 wp = vec4(transformed, 1.0);
      #ifdef USE_INSTANCING
        wp = instanceMatrix * wp;
      #endif
      vWP = (modelMatrix * wp).xyz; }`;
  const fCut = /* glsl */ `
    if (vK > 0.5 && vK < 1.5){
      // leaflets: narrow blades angled toward the tip, ragged ends, a gap at the midrib
      float s = vUv2.x, v = abs(vUv2.y);
      float lod = clamp(fwidth(s * 30.0) * 2.0 - 0.2, 0.0, 1.0);
      float bl = mix(fract(s * 30.0 - v * 2.2), 0.0, lod);
      float wd = 0.55 + 0.25 * hash12(vec2(floor(s * 30.0 - v * 2.2), sign(vUv2.y)));
      if (bl > wd || v > mix(0.96, 1.2, lod) - 0.2 * hash12(vec2(floor(s * 30.0 - v * 2.2), 3.0)) || (v < 0.04 && s > 0.08)) discard;
    }`;
  const HASH = /* glsl */ `float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }`;
  const patch = (sh) => {
    Object.assign(sh.uniforms, U, depth ? {} : C.propU);
    sh.vertexShader = vHead + '\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>' + vSway)
      .replace('#include <project_vertex>', '#include <project_vertex>' + vWorld);
    sh.fragmentShader = /* glsl */ `varying float vK; varying vec2 vUv2; varying vec3 vWP; varying vec3 vOP; ${HASH}\n` + (depth ? '' : C.PROP_HEAD + '\nuniform float uGale;\n') + sh.fragmentShader;
    if (depth) { sh.fragmentShader = sh.fragmentShader.replace('void main() {', 'void main() {' + fCut); return; }
    sh.fragmentShader = sh.fragmentShader
      .replace('void main() {', 'void main() {' + fCut)
      .replace('#include <color_fragment>', /* glsl */ `#include <color_fragment>
        { float n = hash12(floor(vWP.xz * 7.0) + floor(vWP.y * 7.0));
          if (vK < 0.5){ diffuseColor.rgb *= 0.8 + 0.25 * sin(vUv2.x * 9.0) * 0.5 + 0.2 * n; diffuseColor.rgb *= 0.75 + 0.25 * smoothstep(0.0, 0.5, fract(vUv2.x * 2.6)); }
          else if (vK < 1.5){ diffuseColor.rgb *= 0.8 + 0.35 * hash12(vec2(floor(vUv2.x * 30.0 - abs(vUv2.y) * 2.2), sign(vUv2.y))) - 0.25 * abs(vUv2.y);
            diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.45, 0.38, 0.16), smoothstep(0.75, 1.0, vUv2.x) * 0.6); }
          else if (vK < 2.5){ diffuseColor.rgb *= 0.9 + 0.15 * n; }
          else if (vK < 3.5){ float st = hash12(vec2(floor(dot(vWP.xz, vec2(0.7, 0.7)) * 14.0), floor(vWP.y * 6.0)));
            diffuseColor.rgb *= 0.65 + 0.55 * st; diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.3, 0.26, 0.2), 0.3 * hash12(floor(vWP.xz * 3.0))); }
          else { vec2 q = vec2(dot(vWP.xz, vec2(1.0)), vWP.y) * 9.0; float wv = step(0.5, fract(q.x)) == step(0.5, fract(q.y)) ? 1.0 : 0.78;
            diffuseColor.rgb *= wv * (0.85 + 0.2 * n); }
          // wet / mud line left by the flood
          diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * mix(vec3(0.6), vec3(0.42, 0.36, 0.28), uMud), smoothstep(uWetTop + 0.1, uWetTop - 0.1, vWP.y));
          // gale: rain-soaked, grey light: colours drain and darken
          diffuseColor.rgb = mix(diffuseColor.rgb, vec3(dot(diffuseColor.rgb, vec3(0.3, 0.55, 0.15))), 0.45 * uGale) * (1.0 - 0.3 * uGale);
        }`)
      .replace('#include <emissivemap_fragment>', /* glsl */ `#include <emissivemap_fragment>
        if (vK > 0.5 && vK < 1.5){ vec3 vd = normalize(vWP - uCam); totalEmissiveRadiance += diffuseColor.rgb * (uSunC * 0.35 * pow(max(dot(vd, uSun), 0.0), 3.0) + vec3(0.32, 0.4, 0.42) * 0.55 * min(length(uSunC) / 5.2, 1.0)); }`)
      .replace('#include <fog_fragment>', C.PROP_FOG);
  };
  const m = depth
    ? new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, side: THREE.DoubleSide })
    : new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, metalness: 0, side: THREE.DoubleSide });
  m.onBeforeCompile = patch;
  m.customProgramCacheKey = () => (depth ? 'coastPropD' : 'coastProp');
  return { m, U };
}

// instanced group of one geometry; place: list of {x, z, ry, s, tilt, y}
function instanced(C, geo, list, mats) {
  const im = new THREE.InstancedMesh(geo, mats.m.m, list.length);
  im.customDepthMaterial = mats.d.m;
  const o = new THREE.Object3D();
  list.forEach((p, i) => {
    o.position.set(p.x, p.y ?? groundY(p.x, p.z), p.z);
    o.rotation.set(p.tx || 0, p.ry || 0, p.tz || 0, 'YXZ'); o.scale.setScalar(p.s || 1);
    o.updateMatrix(); im.setMatrixAt(i, o.matrix);
  });
  im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false;
  return im;
}

// the village bay: palms over the grove, a handful of huts behind the beach, boats pulled up on the sand
export function addCoastProps(C, { seed = 5, x0 = -900, x1 = 380, palms = 520, huts = 9, boats = 7, moored = 0, debris = 0 } = {}) {
  const mats = { m: propMaterial(C), d: propMaterial(C, { depth: true }) };
  const group = new THREE.Group(); C.scene.add(group);
  const r = rng(seed);
  // huts first, so palms keep clear of them
  const hutList = [];
  for (let i = 0; i < huts; i++) {
    const x = -260 + i * 52 + (r() - 0.5) * 22, c = 42 + r() * 40;
    const z = coastZ(x) + c, d = 0.002;
    const ry = Math.atan2(coastZ(x + 1) - coastZ(x - 1), 2) + (r() - 0.5) * 0.3;
    hutList.push({ x, z, ry, k: i % 3, y: groundY(x, z) - 0.05 });
  }
  const boatList = [];
  for (let i = 0; i < boats; i++) {
    const x = -230 + i * 61 + (r() - 0.5) * 30, c = 7 + r() * 9;
    const z = coastZ(x) + c;
    const ry = Math.atan2(coastZ(x + 1) - coastZ(x - 1), 2) + Math.PI / 2 + (r() - 0.5) * 0.5 + (r() < 0.5 ? Math.PI : 0);
    boatList.push({ x, z, ry, k: i % 3, y: groundY(x, z) - 0.15, tz: (r() - 0.5) * 0.12 });
  }
  const palmList = [];
  let guard = 0;
  while (palmList.length < palms && guard++ < palms * 20) {
    const x = x0 + r() * (x1 - x0);
    // clustered: thicker groves, gaps, sparse along the berm
    const c = 12 + Math.pow(r(), 1.3) * 300;
    const dens = 0.5 + 0.5 * Math.sin(x * 0.013 + 1.0) * Math.sin(x * 0.0051 + 2.0) + (c < 30 ? -0.3 : 0);
    if (r() > dens) continue;
    const z = coastZ(x) + c;
    if (Math.abs(crossC(x, z) - c) > 1) continue;
    if (hutList.some((h) => Math.hypot(h.x - x, h.z - z) < 6)) continue;
    if (palmList.some((p) => Math.hypot(p.x - x, p.z - z) < 3.2)) continue;
    if (groundY(x, z) > 9) continue;
    palmList.push({ x, z, ry: r() * Math.PI * 2, s: 0.85 + r() * 0.35, k: palmList.length % 6, y: groundY(x, z) - 0.1 });
  }
  const palmV = [0, 1, 2, 3, 4, 5].map((k) => palmGeo(seed * 31 + k * 7));
  palmV.forEach((v, k) => group.add(instanced(C, v.geo, palmList.filter((p) => p.k === k), mats)));
  [0, 1, 2].forEach((k) => group.add(instanced(C, hutGeo(seed * 17 + k), hutList.filter((p) => p.k === k), mats)));
  [0, 1, 2].forEach((k) => group.add(instanced(C, boatGeo(seed * 13 + k), boatList.filter((p) => p.k === k), mats)));
  // boats riding at anchor in the lagoon: the scene moves them each frame (afloat, then grounded when the sea drops)
  const moorList = [];
  for (let i = 0; i < moored; i++) {
    const x = -70 + i * (130 / Math.max(moored - 1, 1)) + (r() - 0.5) * 14, c = -95 - r() * 70;
    moorList.push({ x, z: coastZ(x) + c, ry: r() * Math.PI * 2, k: i % 3, ph: r() * 6.28, lean: (r() < 0.5 ? -1 : 1) * (0.16 + r() * 0.12) });
  }
  const moorIM = [0, 1, 2].map((k) => {
    const l = moorList.filter((p) => p.k === k), im = instanced(C, boatGeo(seed * 13 + 40 + k), l, mats);
    group.add(im); return { im, l };
  });
  const o3 = new THREE.Object3D();
  const moor = (pose) => moorIM.forEach(({ im, l }) => {
    l.forEach((p, i) => {
      const q = pose(p);
      o3.position.set(p.x + (q.dx || 0), q.y, p.z + (q.dz || 0)); o3.rotation.set(q.tx || 0, p.ry + (q.dry || 0), q.tz || 0, 'YXZ'); o3.scale.setScalar(1);
      o3.updateMatrix(); im.setMatrixAt(i, o3.matrix);
    });
    im.instanceMatrix.needsUpdate = true;
  });
  // debris the scene moves each frame: list of {k}; drift(fn) asks fn(piece, i) for {x, y, z, ry, tx, tz}
  const debrisList = [];
  for (let i = 0; i < debris; i++) debrisList.push({ k: i % 4, i, ph: r() * 6.28 });
  const debIM = [0, 1, 2, 3].map((k) => {
    const l = debrisList.filter((p) => p.k === k).map((p) => ({ ...p, x: 0, z: 0, y: -50 }));
    const im = instanced(C, debrisGeo(k, seed * 7 + k), l, mats); group.add(im); return { im, l };
  });
  const drift = (pose) => debIM.forEach(({ im, l }) => {
    l.forEach((p, j) => {
      const q = pose(p);
      o3.position.set(q.x, q.y, q.z); o3.rotation.set(q.tx || 0, q.ry || 0, q.tz || 0, 'YXZ'); o3.scale.setScalar(q.s || 1);
      o3.updateMatrix(); im.setMatrixAt(j, o3.matrix);
    });
    im.instanceMatrix.needsUpdate = true;
  });
  return { group, palms: palmList, huts: hutList, boats: boatList, moored: moorList, moor, drift, wind: (w) => { mats.m.U.uWind.value = w; mats.d.U.uWind.value = w; },
    gale: (g, wd) => { for (const m of [mats.m, mats.d]) { m.U.uGale.value = g; if (wd) m.U.uWd.value.set(wd[0], wd[1]); } } };
}
