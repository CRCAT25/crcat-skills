// Open ocean far from any coast: a curved-Earth sea surface ray-cast per pixel, a directional wave spectrum whose
// unresolved slopes turn into glint roughness (no aliasing at any distance), a fair-weather cumulus layer with its
// shadows on the sea, aerial haze, and the tsunami: a ring a few tens of centimetres high racing outward from the
// source. Its height cannot be seen; it shows only as a long band where the sea's roughness and slope change, as it
// does in the sun glint on satellite photos. Sky, sun and fog match coast.js so the two worlds read as one day.
import * as THREE from 'three';
import { NOISE, RAY_VS } from './glsl.js';
import { fsQuad, clamp } from './kit.js';
import { SUN0 } from './coast.js';

export const TS_C = 212; // m/s, sqrt(g * 4600 m)
// tsunami surface height behind the front (d = metres behind the leading edge): crest, trough, a second crest
export function tsEta(d) {
  if (d < -600) return 0;
  const s = clamp((d + 600) / 3100), lead = s * s * (3 - 2 * s);
  const G = (m, w) => Math.exp(-(((d - m) / w) ** 2));
  return lead * Math.exp(-Math.max(d, 0) / 8000) - 0.7 * G(18000, 5000) + 0.55 * G(32000, 5000);
}

const HEAD = /* glsl */ `
  float vn2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y); }
  float fbm2(vec2 p, int oct){ float a = 0.5, s = 0.0; for (int i = 0; i < 8; i++){ if (i >= oct) break; s += a * vn2(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7); a *= 0.5; } return s; }
  float sm(float a, float b, float x){ return smoothstep(a, b, x); }
`;

export function makeOcean({ W, H, fov = 50, near = 0.5, far = 400000 }) {
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(fov, W / H, near, far);
  const v3 = (a) => new THREE.Vector3(...a);
  const u = {
    uTan: { value: new THREE.Vector2() }, uCamWorld: { value: new THREE.Matrix4() }, uCam: { value: new THREE.Vector3() },
    uVP: { value: new THREE.Matrix4() }, uFpK: { value: 0.001 }, uT: { value: 0 }, uBlur: { value: 0 },
    uSun: { value: SUN0.clone() }, uSunC: { value: v3([1.0, 0.88, 0.72]).multiplyScalar(3.0) },
    uZen: { value: v3([0.05, 0.17, 0.5]) }, uHor: { value: v3([0.5, 0.66, 0.83]) }, uAmb: { value: v3([0.32, 0.42, 0.6]) },
    uFogC: { value: v3([0.6, 0.7, 0.82]) }, uFogK: { value: 1 },
    // tsunami ring: source xz, front radius, amplitude at 4 km, slope gain (the real slope is ~1e-4), roughness gain
    uSrc: { value: new THREE.Vector2(0, 0) }, uR: { value: 0 }, uTsA: { value: 0.6 }, uTsK: { value: 800 }, uBand: { value: 12 },
    // ship: x, z, heading (rad, 0 = +x), half length
    uShip: { value: new THREE.Vector4(0, -1e6, 0, 110) },
    uLandZ: { value: 36000 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, vertexShader: RAY_VS, depthTest: true, depthWrite: true,
    fragmentShader: /* glsl */ `
      ${NOISE}${HEAD}
      varying vec3 vDir;
      uniform vec3 uCam, uSun, uSunC, uZen, uHor, uAmb, uFogC; uniform mat4 uVP;
      uniform float uT, uFpK, uFogK, uBlur, uR, uTsA, uTsK, uBand, uLandZ; uniform vec2 uSrc; uniform vec4 uShip;
      const float RE = 6371000.0, CB = 1050.0, CT = 1900.0;

      // ---------- sky (as coast.js) ----------
      vec3 sky(vec3 rd){
        float y = max(rd.y, 0.0), mu = dot(rd, uSun);
        vec3 c = mix(uHor, uZen, pow(y, 0.42));
        c += uSunC * (vec3(0.33, 0.22, 0.12) * pow(max(mu, 0.0), 6.0) * (1.0 - y) + vec3(0.33, 0.3, 0.25) * pow(max(mu, 0.0), 60.0) * 0.4);
        return c * 1.05;
      }
      vec3 fogC(vec3 rd){ return mix(uFogC, uSunC * vec3(0.34, 0.28, 0.22), pow(max(dot(rd, uSun), 0.0), 5.0) * 0.6); }
      // haze in an exponential atmosphere (scale height 1600 m), integrated along the ray between heights y0 and y1
      vec3 fog(vec3 col, vec3 rd, float t, float y0, float y1){
        float a = max(y0, 0.0) / 1600.0, b = max(y1, 0.0) / 1600.0;
        float dens = abs(a - b) > 1e-3 ? (exp(-min(a, b)) - exp(-max(a, b))) / abs(a - b) : exp(-a);
        float f = 1.0 - exp(-t * dens * uFogK / 11000.0);
        return mix(col, fogC(rd), f);
      }

      // ---------- cumulus layer ----------
      float cover(vec2 xz){
        vec2 q = xz / 4600.0 + vec2(uT * 0.0009, 0.0);
        float c = fbm2(q, 4) + 0.16 * fbm2(xz / 1500.0, 3) - 0.16;
        // keep the sky over the source and along the camera's climb open
        vec2 g = (xz - vec2(800.0, 3200.0)) / vec2(3000.0, 5200.0);
        c -= 0.4 * exp(-dot(g, g));
        return c;
      }
      float cloudDen(vec3 p){
        float yy = (p.y - CB) / (CT - CB);
        if (yy < 0.0 || yy > 1.0) return 0.0;
        // billowed edges: 3D noise erodes the rim more than the core, tops round off, bases stay flat
        float c = cover(p.xz) + 0.1 * snoise(p * vec3(0.0022, 0.004, 0.0022)) + 0.05 * snoise(p * 0.009);
        return sm(0.37, 0.52, c - yy * yy * 0.3 - (1.0 - sm(0.0, 0.12, yy)) * 0.08) * 0.007;
      }
      float cloudShadow(vec2 xz){
        vec2 q = xz + uSun.xz * ((CB + 350.0) / max(uSun.y, 0.05));
        vec2 qq = q / 4600.0 + vec2(uT * 0.0009, 0.0);
        return 1.0 - 0.55 * sm(0.3, 0.62, fbm2(qq, 3) - 0.16);
      }
      // returns rgb in-scatter, a = transmittance
      vec4 clouds(vec3 ro, vec3 rd, float tMax){
        float ta = (CB - ro.y) / rd.y, tb = (CT - ro.y) / rd.y;
        if (abs(rd.y) < 1e-4){ if (ro.y < CB || ro.y > CT) return vec4(0, 0, 0, 1); ta = 0.0; tb = 40000.0; }
        float t0 = max(min(ta, tb), 0.0), t1 = min(max(ta, tb), min(tMax, t0 + 30000.0));
        if (t1 <= t0) return vec4(0, 0, 0, 1);
        const int N = 44;
        float dt = (t1 - t0) / float(N), T = 1.0;
        vec3 acc = vec3(0.0);
        float mu = dot(rd, uSun), ph = 0.6 + 0.9 * pow(max(mu, 0.0), 6.0);
        for (int i = 0; i < N; i++){
          float t = t0 + dt * (float(i) + 0.5);
          vec3 p = ro + rd * t;
          float d = cloudDen(p);
          if (d < 1e-5) continue;
          float ls = cloudDen(p + uSun * 90.0) + cloudDen(p + uSun * 260.0);
          float hgt = (p.y - CB) / (CT - CB);
          float sun = exp(-ls * 260.0) * (1.0 - exp(-d * 400.0));
          vec3 lc = uSunC * sun * ph * 0.55 + uAmb * (0.38 + 0.75 * hgt) + uSunC * 0.04;
          float a = 1.0 - exp(-d * dt);
          vec3 c = fog(lc, rd, t, ro.y, p.y);
          acc += T * a * c; T *= 1.0 - a;
          if (T < 0.02) break;
        }
        return vec4(acc, T);
      }

      // ---------- waves ----------
      // tsunami height profile (mirrors tsEta in JS)
      float tsEta(float d){
        if (d < -600.0) return 0.0;
        float lead = sm(-600.0, 2500.0, d);
        return lead * exp(-max(d, 0.0) / 8000.0) - 0.7 * exp(-pow((d - 18000.0) / 5000.0, 2.0)) + 0.55 * exp(-pow((d - 32000.0) / 5000.0, 2.0));
      }
      // slope (xz) of the resolved waves, the unresolved slope variance, and the swell height
      vec3 waves(vec2 xz, float fp, out float lost){
        vec2 sl = vec2(0.0); float h = 0.0; lost = 0.0;
        for (int i = 0; i < 30; i++){
          float fi = float(i);
          float lam = 220.0 * pow(0.79, fi);
          float k = 6.2832 / lam, w = sqrt(9.81 * k);
          float spread = mix(0.35, 1.5, fi / 29.0);
          float ang = 1.25 + (hash11(fi * 7.13 + 1.0) - 0.5) * 2.0 * spread;
          vec2 d = vec2(cos(ang), sin(ang));
          float ka = lam > 60.0 ? 0.03 : 0.055;
          float A = ka / k;
          float ph = k * dot(d, xz) - w * uT + hash11(fi * 3.7) * 6.2832;
          float f = clamp((lam / fp - 2.5) / 5.0, 0.0, 1.0);
          sl += d * (ka * cos(ph) * f);
          lost += ka * ka * 0.5 * (1.0 - f * f);
          if (lam > 18.0) h += A * sin(ph);
        }
        return vec3(sl, h);
      }
      float swellH(vec2 xz){
        float h = 0.0;
        for (int i = 0; i < 8; i++){
          float fi = float(i);
          float lam = 220.0 * pow(0.79, fi);
          float k = 6.2832 / lam, w = sqrt(9.81 * k);
          float ang = 1.25 + (hash11(fi * 7.13 + 1.0) - 0.5) * 2.0 * mix(0.35, 1.5, fi / 29.0);
          vec2 d = vec2(cos(ang), sin(ang));
          float ka = lam > 60.0 ? 0.03 : 0.055;
          h += ka / k * sin(k * dot(d, xz) - w * uT + hash11(fi * 3.7) * 6.2832);
        }
        return h;
      }

      // ---------- ship wake: turbulent strip behind the stern, the Kelvin wedge arms, bow foam ----------
      float wake(vec2 xz){
        vec2 hd = vec2(cos(uShip.z), sin(uShip.z)), pr = vec2(-hd.y, hd.x);
        vec2 q = xz - uShip.xy;
        float al = dot(q, hd), la = abs(dot(q, pr)), L = uShip.w;
        if (al > L + 40.0 || al < -L - 3000.0 || la > 1200.0) return 0.0;
        float b = -al - L, bb = L - al;
        float n = fbm2(xz * 0.06 + vec2(uT * 0.3, 0.0), 4);
        float strip = b > -20.0 ? exp(-max(b, 0.0) / 650.0) * sm(17.0 + 0.07 * max(b, 0.0), 6.0 + 0.04 * max(b, 0.0), la) * (0.45 + 0.8 * n) : 0.0;
        float e = la - bb * 0.354;
        float arms = bb > 0.0 ? exp(-e * e / (6.0 + 0.002 * bb * bb)) * exp(-bb / 500.0) * (0.3 + 0.9 * n) * sm(0.0, 30.0, bb) : 0.0;
        float bow = sm(L - 70.0, L - 10.0, al) * (1.0 - sm(L - 5.0, L + 25.0, al)) * sm(28.0, 16.0, la) * (0.5 + n);
        return clamp(strip * 0.9 + arms * 0.55 + bow * 0.9, 0.0, 1.0);
      }

      // ---------- distant land: the coast the wave is heading for, a hazy ridge on the horizon ----------
      float landH(float x){ return 140.0 + 330.0 * fbm2(vec2(x * 0.00011, 3.0), 5) + 260.0 * sm(-30000.0, 9000.0, x) * (1.0 - sm(9000.0, 40000.0, x)); }

      void main(){
        vec3 rd = normalize(vDir), ro = uCam;
        // sea surface on a curved Earth: y = -s^2 / 2R around the camera (s = horizontal distance)
        float a = (1.0 - rd.y * rd.y) / (2.0 * RE), disc = rd.y * rd.y - 4.0 * a * ro.y;
        float tHit = -1.0;
        if (rd.y < 0.0 && disc > 0.0) tHit = (-rd.y - sqrt(disc)) / (2.0 * a);
        // swell displacement near the camera (refined with a few steps)
        if (tHit > 0.0 && tHit < 4000.0){
          for (int i = 0; i < 3; i++){
            vec3 p = ro + rd * tHit;
            float s2 = dot(p.xz - ro.xz, p.xz - ro.xz);
            float hs = swellH(p.xz) - s2 / (2.0 * RE);
            tHit = (ro.y - hs) / max(-rd.y, 1e-3);
          }
        }
        vec3 col;
        // land ridge
        float tL = rd.z > 1e-4 ? (uLandZ - ro.z) / rd.z : -1.0;
        bool land = false;
        if (tL > 0.0 && (tHit < 0.0 || tL < tHit)){
          vec3 pl = ro + rd * tL;
          float s = length(pl.xz - ro.xz), yl = pl.y + s * s / (2.0 * RE);
          if (yl < landH(pl.x) && yl > -5.0){ land = true; tHit = tL; }
        }
        if (land){
          vec3 p = ro + rd * tHit;
          float s = length(p.xz - ro.xz), yl = p.y + s * s / (2.0 * RE);
          float g = fbm2(vec2(p.x * 0.004, yl * 0.02), 4);
          vec3 alb = mix(vec3(0.07, 0.1, 0.05), vec3(0.12, 0.13, 0.08), g);
          col = alb * (uSunC * 0.35 + uAmb * 0.7) * cloudShadow(p.xz);
          col = fog(col, rd, tHit * 0.55, ro.y, yl);
        } else if (tHit > 0.0){
          vec3 p = ro + rd * tHit;
          float fp = uFpK * tHit / max(abs(rd.y), 0.08) * 0.5 + uFpK * tHit + uBlur;
          float lost;
          vec3 wv = waves(p.xz, fp, lost);
          vec2 sl = wv.xy;
          // tsunami ring: slope (scaled up so the eye can find what the glint shows) and the roughness band
          vec2 rv = p.xz - uSrc; float r = max(length(rv), 1.0); vec2 rn = rv / r;
          float dd = uR - r, att = uTsA * sqrt(4000.0 / max(r, 4000.0));
          float dEta = (tsEta(dd + 150.0) - tsEta(dd - 150.0)) / 300.0;
          sl += rn * (-dEta * att * uTsK);
          float band = exp(-pow((dd - 700.0) / 1300.0, 2.0)) * att / uTsA;
          float s2 = 0.0035 + lost;
          s2 *= 1.0 + uBand * band;
          vec3 n = normalize(vec3(-sl.x, 1.0, -sl.y));
          vec3 V = -rd, R = reflect(rd, n);
          R.y = abs(R.y);
          float ndv = max(dot(n, V), 0.02);
          float F = 0.02 + 0.98 * pow(1.0 - ndv, 5.0);
          float csh = cloudShadow(p.xz);
          // unresolved slopes also widen the reflection: blend toward a hazier sky as roughness grows
          vec3 refl = mix(sky(R), sky(normalize(vec3(R.x, R.y + 0.15, R.z))) * 0.92, clamp(s2 * 6.0, 0.0, 1.0));
          vec3 body = vec3(0.0035, 0.018, 0.034) * (uSunC * max(uSun.y, 0.0) * (0.4 + 0.6 * csh) + uAmb * 1.2);
          col = mix(body, refl, F) * (1.0 - 0.16 * band);
          // Beckmann glint over the resolved normal, width from the unresolved slopes
          vec3 hv = normalize(uSun + V);
          float ndh = max(dot(n, hv), 1e-3), ndl = max(dot(n, uSun), 0.0);
          float t2 = (1.0 - ndh * ndh) / (ndh * ndh);
          float D = exp(-t2 / s2) / (3.1416 * s2 * ndh * ndh * ndh * ndh);
          float Fh = 0.02 + 0.98 * pow(1.0 - max(dot(hv, V), 0.0), 5.0);
          col += uSunC * Fh * D * ndl / (4.0 * ndv * max(ndl, 0.05)) * csh * 0.6;
          // wind whitecaps (sparse) and the ship's wake
          float wc = sm(0.72, 0.9, fbm2(p.xz * 0.045 + vec2(uT * 0.05, uT * 0.03), 4)) * sm(0.6, 0.85, fbm2(p.xz * 0.004, 3)) * 0.35;
          float fm = max(wc * (1.0 - sm(800.0, 3000.0, tHit) * 0.6), wake(p.xz));
          vec3 foam = vec3(0.82, 0.86, 0.88) * (uSunC * max(uSun.y, 0.0) * csh * 0.8 + uAmb * 0.9);
          col = mix(col, foam, fm * 0.85);
          col = fog(col, rd, tHit, ro.y, 0.0);
        } else {
          col = sky(rd);
          col += uSunC * smoothstep(0.99965, 0.9999, dot(rd, uSun)) * 20.0;
          col = mix(col, fogC(rd), sm(0.06, -0.01, rd.y) * 0.85);
        }
        vec4 cl = clouds(ro, rd, tHit > 0.0 ? tHit : 1e7);
        col = col * cl.a + cl.rgb;
        gl_FragColor = vec4(col, 1.0);
        if (tHit > 0.0){ vec4 cc = uVP * vec4(ro + rd * tHit, 1.0); gl_FragDepth = clamp(cc.z / cc.w * 0.5 + 0.5, 0.0, 1.0); }
        else gl_FragDepth = 0.999999;
      }`,
  });
  const quad = fsQuad(mat); quad.renderOrder = -1;
  scene.add(quad);

  // lights for the ship, matched to the ray-cast sun and sky
  const sunL = new THREE.DirectionalLight(0xffffff, 1);
  sunL.castShadow = true; sunL.shadow.mapSize.set(2048, 2048);
  sunL.shadow.bias = -0.0004; sunL.shadow.normalBias = 0.05;
  scene.add(sunL, sunL.target);
  const hemi = new THREE.HemisphereLight(0xffffff, 0xffffff, Math.PI);
  scene.add(hemi);
  const aimShadow = (cx, cy, cz, r) => {
    sunL.target.position.set(cx, cy, cz);
    sunL.position.set(cx, cy, cz).addScaledVector(u.uSun.value, 500);
    const c = sunL.shadow.camera; c.left = -r; c.right = r; c.top = r; c.bottom = -r; c.near = 1; c.far = 1200; c.updateProjectionMatrix();
  };
  const syncLights = () => {
    const s = u.uSunC.value, a = u.uAmb.value;
    sunL.color.setRGB(s.x, s.y, s.z).multiplyScalar(1 / Math.max(s.x, s.y, s.z));
    sunL.intensity = Math.max(s.x, s.y, s.z) * Math.PI;
    hemi.color.setRGB(a.x * 0.6, a.y * 0.6, a.z * 0.6);
    hemi.groundColor.setRGB(0.02, 0.05, 0.07);
    hemi.intensity = Math.PI;
  };
  // the same aerial haze on rasterised materials
  const fogU = { uCam: u.uCam, uSun: u.uSun, uSunC: u.uSunC, uFogC: u.uFogC, uFogK: u.uFogK };
  const withFog = (m, key) => {
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, fogU);
      sh.vertexShader = 'varying vec3 vWP;\n' + sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
        { vec4 wp = vec4(transformed, 1.0);
          #ifdef USE_INSTANCING
            wp = instanceMatrix * wp;
          #endif
          vWP = (modelMatrix * wp).xyz; }`);
      sh.fragmentShader = 'varying vec3 vWP; uniform vec3 uCam, uSun, uSunC, uFogC; uniform float uFogK;\n' + sh.fragmentShader
        .replace('#include <fog_fragment>', `{
          vec3 rdF = normalize(vWP - uCam); float tF = length(vWP - uCam);
          float a = max(uCam.y, 0.0) / 1600.0, b = max(vWP.y, 0.0) / 1600.0;
          float dens = abs(a - b) > 1e-3 ? (exp(-min(a, b)) - exp(-max(a, b))) / abs(a - b) : exp(-a);
          float fF = 1.0 - exp(-tF * dens * uFogK / 11000.0);
          vec3 fcF = mix(uFogC, uSunC * vec3(0.34, 0.28, 0.22), pow(max(dot(rdF, uSun), 0.0), 5.0) * 0.6);
          gl_FragColor.rgb = mix(gl_FragColor.rgb, fcF, fF); }`);
    };
    m.customProgramCacheKey = () => 'oceanFog' + key;
    return m;
  };
  const setCam = (pos, look, fovDeg = fov, roll = 0) => {
    cam.fov = fovDeg; cam.position.set(...pos); cam.up.set(Math.sin(roll), Math.cos(roll), 0);
    cam.lookAt(...look); cam.updateProjectionMatrix(); cam.updateMatrixWorld();
  };
  function sync(t) {
    u.uT.value = t;
    const ty = Math.tan((cam.fov * Math.PI) / 360);
    u.uTan.value.set(ty * cam.aspect, ty); u.uCamWorld.value.copy(cam.matrixWorld); u.uCam.value.copy(cam.position);
    u.uVP.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    u.uFpK.value = ty / (H * 0.5);
    syncLights();
  }
  const dispose = () => { scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); sunL.shadow.map?.dispose(); };
  return { scene, cam, u, sunL, aimShadow, withFog, setCam, sync, dispose };
}

// ---------- a container ship, ~220 m, built from boxes; bow toward +x, waterline at y = 0 ----------
export function makeShip(O, { seed = 3 } = {}) {
  let s = seed >>> 0;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const L = 110, B = 16;
  const halfW = (x) => {
    if (x > 40) { const k = (x - 40) / (L + 2 - 40); return B * Math.sqrt(Math.max(1 - k * k, 0)) * (1 - 0.15 * k); }
    if (x < -96) { const k = (-96 - x) / 14; return B * Math.sqrt(Math.max(1 - k * k * k * k, 0)); }
    return B;
  };
  const shape = new THREE.Shape();
  const N = 60;
  for (let i = 0; i <= N; i++) { const x = -L + (2 * L * i) / N; i ? shape.lineTo(x, halfW(x)) : shape.moveTo(x, halfW(x)); }
  for (let i = N; i >= 0; i--) { const x = -L + (2 * L * i) / N; shape.lineTo(x, -halfW(x)); }
  const hullPart = (y0, y1, color, rough = 0.6) => {
    const g = new THREE.ExtrudeGeometry(shape, { depth: y1 - y0, bevelEnabled: false, steps: 1 });
    g.rotateX(-Math.PI / 2); g.translate(0, y0, 0);
    const m = new THREE.Mesh(g, O.withFog(new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0.2 }), 'hull' + color));
    m.castShadow = m.receiveShadow = true;
    return m;
  };
  const group = new THREE.Group();
  group.add(hullPart(-12, 0.9, 0x6a1c16, 0.7));
  group.add(hullPart(0.9, 9, 0x1b232c, 0.5));
  const box = (w, h, d, x, y, z, color, rough = 0.6) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), O.withFog(new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0.1 }), 'box' + color));
    m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; group.add(m); return m;
  };
  // accommodation block aft, bridge with wings, funnel, deck house windows
  box(16, 26, 28, -86, 9 + 13, 0, 0xe8e6df);
  box(17, 3.2, 38, -84, 9 + 26 + 1.6, 0, 0xe8e6df);
  box(17.2, 1.4, 38.2, -84, 9 + 26 + 2.0, 0, 0x14181c, 0.2);
  for (let k = 0; k < 5; k++) box(16.2, 0.9, 28.2, -86, 9 + 5 + k * 4.5, 0, 0x2a3036, 0.25);
  box(9, 12, 9, -99, 9 + 6 + 20, 0, 0xd8d4cb);
  box(9.2, 2.5, 9.2, -99, 9 + 6 + 26 + 1.25, 0, 0x1a1a1a);
  // forecastle
  box(14, 2.5, 18, L - 12, 9 + 1.25, 0, 0x4a5258);
  // containers: 40-ft boxes in bays, rows limited by the hull width, tiers stepped toward the bow
  const pal = [0x2b5f8a, 0x8c2a22, 0x9a9e9f, 0xd9d6cc, 0xb8642a, 0x2f6a46, 0x7a4b2e, 0x1f3f63, 0xc9a23a, 0x5f6a72, 0x3d7fa0];
  const list = [];
  for (let bx = -73; bx < L - 22; bx += 12.9) {
    const hw = Math.min(halfW(bx - 6), halfW(bx + 6)) - 1.2;
    const rows = Math.min(13, Math.floor((2 * hw) / 2.5));
    const tiersBase = 3 + Math.floor(rnd() * 3) - (bx > 60 ? 1 : 0);
    for (let r = 0; r < rows; r++) {
      const z = (r - (rows - 1) / 2) * 2.5;
      const tiers = Math.max(1, tiersBase - (rnd() < 0.18 ? 1 + Math.floor(rnd() * 2) : 0));
      for (let t = 0; t < tiers; t++) list.push({ x: bx, y: 9 + 1.3 + t * 2.62, z, c: pal[Math.floor(rnd() * pal.length)] });
    }
  }
  const cg = new THREE.BoxGeometry(12.19, 2.59, 2.44);
  const cm = O.withFog(new THREE.MeshStandardMaterial({ roughness: 0.75, metalness: 0.25 }), 'cont');
  const im = new THREE.InstancedMesh(cg, cm, list.length);
  const o = new THREE.Object3D(), col = new THREE.Color();
  list.forEach((p, i) => {
    o.position.set(p.x, p.y, p.z); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
    col.setHex(p.c).multiplyScalar(0.75 + 0.35 * rnd()); im.setColorAt(i, col);
  });
  im.castShadow = im.receiveShadow = true;
  group.add(im);
  return { group, L };
}
