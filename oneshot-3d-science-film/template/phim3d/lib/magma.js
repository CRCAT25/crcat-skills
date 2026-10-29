// The molten proto-Earth surface (scenes 3-5): convecting crust rafts on a magma sea, optional impact scar.
import * as THREE from 'three';
import { NOISE } from './glsl.js';

// Shared shading, all in unit-sphere space: p = surface direction, rel = surface point minus camera
// (passed separately so derivatives stay precise right under the camera).
// Scene 5 evaluates the very same function on its flat ground so the cut from scene 4 is seamless.
// near > 0 adds finer crack generations for close views (zero leaves scene 4's look untouched).
export const MAGMA_GLSL = /* glsl */ `
  vec3 magmaShade(vec3 p, vec3 rel, vec3 sun, float t, float age, vec3 imp, float cool, float near, out float heatOut, out float hgtOut){
    float camD = length(rel);
    // slow convection: domain-warped plates riding on a lava ocean
    vec3 w = p * 2.4 + 0.45 * vec3(fbm3(p * 2.0 + t * 0.03, 4), fbm3(p * 2.0 + 7.3 - t * 0.025, 4), fbm3(p * 2.0 + 3.1, 4));
    vec3 vv = voronoi3(w * 3.2); float edge = vv.y - vv.x;
    float flow = fbm3(p * 5.0 + w * 0.7 + vec3(0.0, t * 0.04, 0.0), 6);
    int oct = camD < 0.3 ? 6 : 4;
    float det = fbm3(p * 60.0 + w, oct);
    float fine = fbm3(p * 260.0 + w * 3.0, camD < 0.2 ? 4 : 2);
    // crust rafts (plate interiors) floating on a dull-red magma sea; only thin seams run yellow
    float raft = smoothstep(0.02, 0.12, edge) * smoothstep(-0.35, 0.05, -flow + det * 0.15);
    float seam = smoothstep(0.03, 0.0, edge) * (0.6 + 0.4 * fine);
    float vein = smoothstep(0.05, 0.0, abs(det + 0.05 * fine)) * raft;
    float hgtN = 0.0, crackH = 0.0, rim = 0.0;
    if (near > 0.0){
      // closer in, each raft breaks into smaller plates, and those into smaller ones still (fades in by distance)
      float k1 = near * smoothstep(0.02, 0.004, camD), k2 = near * smoothstep(0.003, 0.0006, camD);
      vec3 q1 = p * 900.0 + w * 9.0 + 0.6 * vec3(fbm3(p * 400.0, 3), fbm3(p * 400.0 + 4.0, 3), 0.0);
      vec3 c1 = voronoi3(q1); float e1 = c1.y - c1.x;
      vec3 c2 = voronoi3(p * 7000.0 + q1 * 3.0); float e2 = c2.y - c2.x;
      float f2 = fbm3(p * 20000.0, 4);
      float gap = mix(0.07, 0.012, cool);
      float sub1 = smoothstep(gap, gap + 0.05, e1), sub2 = smoothstep(gap * 0.7, gap * 0.7 + 0.05, e2);
      // the sea itself skins over as it cools
      float skin = smoothstep(-0.2 - cool * 1.2, 0.2 - cool * 1.2, -fbm3(p * 120.0 + w, 4)) ;
      raft = max(raft, skin * cool);
      float rr = mix(1.0, sub1, k1) * mix(1.0, sub2, k2);
      seam = max(seam, raft * (1.0 - rr) * (0.7 + 0.3 * f2));
      raft *= rr;
      hgtN = raft * (k1 * (0.5 + 0.3 * c1.z) + k2 * 0.4 * c2.z + k2 * 0.25 * f2);
      // open cracks stay incandescent while the plates go black; never thinner than ~a pixel so they don't alias away
      float w1 = max(gap * 0.6, ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e1) * 0.9), w2 = max(gap * 0.4, ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e2) * 0.9);
      float cr1 = 1.0 - smoothstep(w1, w1 + ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e1) * 1.2 + 0.004, e1);
      float cr2 = 1.0 - smoothstep(w2, w2 + ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e2) * 1.2 + 0.004, e2);
      // cells smaller than a few pixels just shimmer and dash: let them go
      cr1 *= smoothstep(0.3, 0.1, ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e1)); cr2 *= smoothstep(0.3, 0.1, ${(globalThis.PXF || 1).toFixed(4)} * fwidth(e2));
      float cr0 = smoothstep(0.03, 0.0, edge);
      float glowv = 0.75 + 0.25 * fbm3(p * 3000.0 + w * 20.0, 3);
      crackH = max(max(cr0 * 0.95, cr1 * k1 * 0.85 * (0.75 + 0.25 * c1.z)), cr2 * k2 * 0.6) * glowv * cool;
      // heat bleeding out of the cracks onto the plate rims
      rim = cool * (k1 * exp(-e1 * 9.0) * 0.6 + k2 * exp(-e2 * 12.0) * 0.4 + exp(-edge * 40.0) * 0.5) * glowv;
    }
    float sea = 1.0 - raft;
    float heat = clamp(sea * (0.38 + 0.12 * flow + 0.08 * fine) + seam * 0.35 + vein * 0.25, 0.0, 1.0);
    float lake = sea;
    // impact: white-hot core, an expanding melt front and a travelling shock ring
    float a = acos(clamp(dot(p, imp), -1.0, 1.0)), on = step(0.0, age); age = max(age, 0.0);
    float melt = on * smoothstep(0.08 + age * 0.13, 0.0, a) * (0.7 + 0.3 * fine);
    float ring = on * exp(-pow((a - age * 0.32) / (0.025 + age * 0.01), 2.0)) * exp(-age * 0.35) * (0.6 + 0.4 * det);
    float core = on * exp(-a * a / (0.004 + 0.01 * age)) * exp(-age * 0.3);
    heat = clamp(max(heat, melt * 0.75 * (1.0 - raft * near)) + ring * 0.5, 0.0, 1.0);
    heat *= 1.0 - cool * mix(0.55, 0.92, raft);
    heat = max(heat, crackH);

    // crust shading with bump from the height field
    float hgt = (1.0 - lake) * 0.7 + det * 0.25 + fine * 0.06 - seam * 0.3 + hgtN;
    hgtOut = hgt;
    vec3 n = p;
    vec3 sx = dFdx(rel), sy = dFdy(rel);
    vec3 r1 = cross(sy, n), r2 = cross(n, sx); float dt = dot(sx, r1);
    vec3 grad = sign(dt) * (dFdx(hgt) * r1 + dFdy(hgt) * r2);
    n = normalize(abs(dt) * n - grad * mix(0.012, 0.004, near));
    vec3 V = normalize(-rel);
    float dif = max(dot(n, sun), 0.0);
    vec3 crust = mix(vec3(0.03, 0.027, 0.027), vec3(0.11, 0.09, 0.08), smoothstep(-0.4, 0.5, det + fine * 0.3));
    vec3 irr = vec3(dif * 2.0 + 0.015);
#ifdef MAGMA_EXTRA
    irr += magmaExtra(n, V, rel, raft);
#endif
    vec3 col = crust * irr * (1.0 - heat * 0.85);
    float sp = pow(max(dot(reflect(-sun, n), V), 0.0), 40.0) * (1.0 - heat);
    col += vec3(1.0, 0.9, 0.8) * sp * 0.15;
    float T = heat * (0.75 + 0.25 * smoothstep(-0.3, 0.6, flow + fine * 0.2));
    col += blackbody(T) * (0.25 + 2.2 * T * T) * smoothstep(0.02, 0.15, T);
    col += vec3(1.0, 0.22, 0.04) * rim * rim * (1.0 - heat) * 0.5;
    col += (vec3(4.0, 2.6, 1.4) * core + vec3(1.8, 0.6, 0.15) * ring) * (1.0 - cool);
#ifdef MAGMA_EXTRA
    col += magmaSpec(n, V, raft) * (1.0 - heat);
#endif
    // smoky orange limb from the glowing atmosphere of rock vapour
    float fr = pow(1.0 - max(dot(p, V), 0.0), 4.0);
    col += vec3(0.7, 0.2, 0.04) * fr * 0.25 * (1.0 - cool);
    heatOut = T;
    return col;
  }`;

// pu: { uT, uSun, uImp, uAge, uCamO } uniforms owned by the scene
export function magmaMaterial(pu) {
  return new THREE.ShaderMaterial({
    uniforms: pu,
    vertexShader: /* glsl */ `${NOISE}
      varying vec3 vObj, vW;
      void main(){
        vObj = normalize(position);
        vec3 p = position * (1.0 + 0.0025 * fbm3(vObj * 18.0, 3));       // a little relief for grazing views
        vec4 w = modelMatrix * vec4(p, 1.0); vW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: /* glsl */ `${NOISE}${MAGMA_GLSL}
      uniform float uT, uAge; uniform vec3 uSun, uImp, uCamO; varying vec3 vObj, vW;
      void main(){
        float h, g;
        gl_FragColor = vec4(magmaShade(vObj, vW - uCamO, uSun, uT, uAge, uImp, 0.0, 0.0, h, g), 1.0);
      }`,
  });
}
