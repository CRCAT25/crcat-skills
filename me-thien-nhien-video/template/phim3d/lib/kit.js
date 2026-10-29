// Small helpers shared by scenes: easing, keyframes, soft sprites, displaced rocks.
import * as THREE from 'three';
import { NOISE } from './glsl.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, k) => a + (b - a) * k;
export const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k); };
export const ease = {
  inOut: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
  out: (k) => 1 - Math.pow(1 - k, 3),
  in: (k) => k * k * k,
  expo: (k) => (k <= 0 ? 0 : k >= 1 ? 1 : k < 0.5 ? Math.pow(2, 20 * k - 10) / 2 : (2 - Math.pow(2, -20 * k + 10)) / 2),
  sine: (k) => -(Math.cos(Math.PI * k) - 1) / 2,
};
// keys([[t, v], ...], t, easeFn): piecewise interpolation of numbers or arrays
export function keys(ks, t, e = ease.inOut) {
  if (t <= ks[0][0]) return ks[0][1];
  for (let i = 1; i < ks.length; i++) if (t < ks[i][0]) {
    const [ta, a] = ks[i - 1], [tb, b] = ks[i], k = e((t - ta) / (tb - ta));
    return Array.isArray(a) ? a.map((x, j) => lerp(x, b[j], k)) : lerp(a, b, k);
  }
  return ks[ks.length - 1][1];
}
export const pxf = () => globalThis.PXF || 1;

// seeded RNG
export function rng(seed = 1) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

// Soft round sprites (bokeh, dust, stars). Per-point: position, size (world units), colour, phase.
export function softPoints({ count, place, sizeAtten = true, additive = true, depthWrite = false, soft = 1.0 }) {
  const pos = new Float32Array(count * 3), col = new Float32Array(count * 3), siz = new Float32Array(count), ph = new Float32Array(count), rph = rng(count); // seeded so separately rendered chunks twinkle in step
  for (let i = 0; i < count; i++) {
    const p = place(i);
    pos.set(p.p, i * 3); col.set(p.c, i * 3); siz[i] = p.s; ph[i] = p.ph ?? rph();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setAttribute('size', new THREE.BufferAttribute(siz, 1));
  g.setAttribute('phase', new THREE.BufferAttribute(ph, 1));
  const m = new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 1 }, uTime: { value: 0 }, uGain: { value: 1 }, uFocus: { value: 0 }, uBokeh: { value: 0 },
      uTwinkle: { value: 0 }, uMinPx: { value: 1.2 } },
    // pixel-sized constants were tuned at 1080p; PXF (= H / 1080, set by page.html) keeps the look at other resolutions
    vertexShader: /* glsl */ `
      const float PXF = ${pxf().toFixed(4)};
      attribute float size; attribute float phase; attribute vec3 color;
      uniform float uScale, uTime, uGain, uFocus, uBokeh, uTwinkle, uMinPx; varying vec3 vCol; varying float vSoft;
      void main(){
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        float z = -mv.z;
        float px = ${sizeAtten ? 'size * uScale / z' : 'size * PXF'};
        // fake depth of field: points away from the focus distance swell into dim discs
        float coc = uBokeh * abs(z - uFocus) / max(z, 1e-6);
        float px2 = max(px, uMinPx * PXF) + coc * PXF;
        float tw = 1.0 + uTwinkle * sin(uTime * (2.0 + 3.0 * phase) + phase * 40.0);
        vCol = color * uGain * tw * min(1.0, (px * px + PXF * PXF) / (px2 * px2));
        vSoft = clamp(coc / max(px2, 1.0), 0.0, 1.0);
        gl_PointSize = min(px2, 400.0 * PXF);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */ `
      varying vec3 vCol; varying float vSoft;
      void main(){
        vec2 d = gl_PointCoord * 2.0 - 1.0; float r = dot(d, d);
        if (r > 1.0) discard;
        float core = exp(-r * ${(4.0 * soft).toFixed(2)});
        float disc = smoothstep(1.0, 0.82, r) * (0.55 + 0.45 * r);
        float a = mix(core, disc, vSoft);
        gl_FragColor = vec4(vCol * a, a);
      }`,
    transparent: true, depthWrite, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
  });
  const pts = new THREE.Points(g, m);
  pts.frustumCulled = false;
  return pts;
}

// CPU noise for displacing meshes (value noise, cheap, deterministic)
export function vnoise3(seed = 7) {
  const r = rng(seed), P = new Uint8Array(512), G = new Float32Array(256);
  for (let i = 0; i < 256; i++) { P[i] = i; G[i] = r() * 2 - 1; }
  for (let i = 255; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [P[i], P[j]] = [P[j], P[i]]; }
  for (let i = 0; i < 256; i++) P[i + 256] = P[i];
  const f = (t) => t * t * (3 - 2 * t);
  const n = (x, y, z) => {
    const X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z), u = f(x - X), v = f(y - Y), w = f(z - Z);
    const h = (a, b, c) => G[P[P[P[(a & 255)] + (b & 255)] + (c & 255)]];
    const l = (a, b, k) => a + (b - a) * k;
    return l(l(l(h(X, Y, Z), h(X + 1, Y, Z), u), l(h(X, Y + 1, Z), h(X + 1, Y + 1, Z), u), v),
      l(l(h(X, Y, Z + 1), h(X + 1, Y, Z + 1), u), l(h(X, Y + 1, Z + 1), h(X + 1, Y + 1, Z + 1), u), v), w);
  };
  return (x, y, z, oct = 4) => { let a = 0.5, s = 0; for (let i = 0; i < oct; i++) { s += a * n(x, y, z); x *= 2.03; y *= 2.03; z *= 2.03; a *= 0.5; } return s; };
}

// A lumpy rock / grain: icosphere displaced by fbm, optional flat facets.
export function rockGeo({ radius = 1, detail = 5, seed = 3, amp = 0.25, freq = 1.6, stretch = [1, 1, 1], oct = 5 }) {
  let g = new THREE.IcosahedronGeometry(radius, detail);
  // weld the icosphere so normals are smooth instead of faceted
  g.deleteAttribute('normal'); g.deleteAttribute('uv'); g = mergeVertices(g);
  const n = vnoise3(seed), p = g.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i).normalize();
    const d = 1 + amp * n(v.x * freq + 5, v.y * freq + 2, v.z * freq + 9, oct);
    p.setXYZ(i, v.x * radius * d * stretch[0], v.y * radius * d * stretch[1], v.z * radius * d * stretch[2]);
  }
  g.computeVertexNormals();
  return g;
}

export const fsQuad = (mat) => {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  m.frustumCulled = false;
  return m;
};
export { NOISE };

// Procedural mineral surface (object-space): dark silicate, crystal seams, optional ice frost, bump, glowing cracks.
// heat > 0 adds incandescent cracks (molten rock); uHeat uniform can be animated via mat.userData.uHeat.
export function rockMaterial({ frost = 0, scale = 1, heat = 0, tint = [1, 1, 1], roughness = 0.62 } = {}) {
  const m = new THREE.MeshStandardMaterial({ roughness, metalness: 0.05 });
  const uHeat = { value: heat };
  m.userData.uHeat = uHeat;
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uHeat = uHeat;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vObj;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj = position * ' + scale.toFixed(3) + ';');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vObj; uniform float uHeat;\n' + NOISE)
      .replace('#include <map_fragment>', `
        float gA = fbm3(vObj * 5.0, 5), gB = voronoi3(vObj * 7.0).y - voronoi3(vObj * 7.0).x, gC = fbm3(vObj * 34.0, 4);
        vec3 alb = mix(vec3(0.07, 0.06, 0.065), vec3(0.24, 0.2, 0.17), smoothstep(-0.35, 0.45, gA));
        alb = mix(alb, vec3(0.5, 0.42, 0.33), smoothstep(0.025, 0.0, gB) * 0.3 * smoothstep(0.0, 0.3, gA));
        float frost = smoothstep(0.05, 0.4, gA + gC * 0.35) * ${frost.toFixed(3)};
        alb = mix(alb, vec3(0.62, 0.72, 0.85), frost);
        diffuseColor.rgb = alb * vec3(${tint.map((x) => x.toFixed(3)).join(',')});`)
      .replace('#include <roughnessmap_fragment>', `float roughnessFactor = mix(roughness, 0.28, frost) * (0.8 + 0.3 * gC);`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        { float hgt = gC * 0.5 + gA * 0.8 - smoothstep(0.06, 0.0, gB) * 0.3;
          vec3 sx = dFdx(-vViewPosition), sy = dFdy(-vViewPosition);
          vec3 r1 = cross(sy, normal), r2 = cross(normal, sx); float det = dot(sx, r1);
          vec3 grad = sign(det) * (dFdx(hgt) * r1 + dFdy(hgt) * r2);
          normal = normalize(abs(det) * normal - grad * 0.05); }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        if (uHeat > 0.001){
          // warped, broken fissures (not a regular cell net) + magma pooling in the low ground
          vec3 wq = vObj * 3.2 + vec3(fbm3(vObj * 2.0, 3), fbm3(vObj * 2.0 + 5.2, 3), fbm3(vObj * 2.0 + 9.1, 3)) * 0.9;
          vec3 vv = voronoi3(wq); float edge = vv.y - vv.x;
          float width = 0.015 + 0.05 * smoothstep(-0.2, 0.6, fbm3(vObj * 1.5 + 2.0, 3));
          float crack = smoothstep(width, 0.0, edge) * smoothstep(-0.25, 0.25, fbm3(vObj * 2.3 + 11.0, 4));
          float pool = smoothstep(-0.3, -0.6, gA) * 0.5;
          float glow = uHeat * (crack * (0.7 + 0.6 * gC) * 2.5 + pool * 1.4);
          diffuseColor.rgb *= 1.0 - 0.6 * min(uHeat, 1.0);                       // crust darkened by heat
          totalEmissiveRadiance += vec3(1.5, 0.32, 0.05) * glow + vec3(1.4, 0.85, 0.35) * uHeat * crack * pool * 2.0;
        }`);
  };
  return m;
}
