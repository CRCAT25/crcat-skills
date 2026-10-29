// Scene 9 — the age of dinosaurs: a Mesozoic river valley in late golden light. A sauropod herd fords the river,
// pterosaurs glide past, a tyrannosaur steps into the foreground and looks up as a fire streak crosses the sky.
// Same look as S8's coast: a ray-marched heightfield (metres, y up) with the same sun/sky/fog shading, but it writes
// gl_FragDepth so the rasterised, skinned animals (CC0 Quaternius models, restyled) composite into it with occlusion.
// The animals' shadow map is sampled by the terrain shader, so they cast shadows on the ground and water.
import { NOISE, RAY_VS } from '../lib/glsl.js';
import { keys, ease, smooth, rng, fsQuad, clamp, lerp } from '../lib/kit.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

// mode 'after' is S11: the same valley after the impact (impact winter, then the recovery), see s11_phuchoi.js
export async function build({ THREE, W, H, mode }) {
  const AFTER = mode === 'after';
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const DEG = Math.PI / 180;
  const SUN = V(0.85, 0.45, 0.25).normalize();                         // afternoon sun from the right, a little behind the camera: modelled animals, long shadows
  const SUNCOL = [1.0, 0.86, 0.68], SUNI = 3.0;                         // same sun as S8
  const WL = -0.6;                                                     // river surface

  // the river crosses the view left to right; same formula in JS and GLSL (smooth terms only, so feet stay on the ground)
  const riverZ = (x) => -260 + 70 * Math.sin(x * 0.004 + 0.6) + 28 * Math.sin(x * 0.011 + 2.0);
  const plain = (x, z) => 0.6 * Math.sin(x * 0.013 + z * 0.007) + 0.4 * Math.sin(x * 0.005 - z * 0.017 + 1.3);
  const groundY = (x, z) => {
    const d = Math.abs(z - riverZ(x));
    const bank = smooth(14, 40, d);
    return lerp(WL - 1.6 + d * 0.02, plain(x, z) + 0.8, bank);
  };

  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(38, W / H, 0.5, 60000);

  // ---------- terrain / sky (ray-marched) ----------
  const tu = {
    uTan: { value: new THREE.Vector2() }, uCamWorld: { value: new THREE.Matrix4() }, uCam: { value: new THREE.Vector3() },
    uVP: { value: new THREE.Matrix4() }, uSun: { value: SUN }, uT: { value: 0 },
    uSM: { value: null }, uSMat: { value: null }, uSMon: { value: 0 }, uSMtx: { value: 1 / 4096 },
    uWhite: { value: 0 }, uWC: { value: new THREE.Vector3(2.1, 2.05, 2.0) }, uStreak: { value: new THREE.Vector4(0, 0, 0, 0) },
    uImp: { value: new THREE.Vector4(0, 0, -1, -1) }, uDust: { value: 0 },
    // the impact's aftermath: x = shock-dome radius, y = dust-front radius (m, from the impact point uP0),
    // z = how far the camera is inside the dust, w = visibility inside it (m); uDC dust colour, uSG sun through the dust
    uP0: { value: new THREE.Vector3() }, uRad: { value: new THREE.Vector4(0, 0, 0, 1) },
    uDC: { value: new THREE.Vector3() }, uSG: { value: new THREE.Vector3() }, uSunK: { value: new THREE.Vector3(1, 1, 1) },
    // the burn and the recovery: uScar x = scorched, y = fire, z = ash cover; uRegrow x = fern spike, y = the forest back;
    // uOver = overcast ash sky (uOC its colour, uOSun the sun through it, uTc its time-lapse clock); uAmb sky light, uFogK haze
    uScar: { value: new THREE.Vector4(0, 0, 0, 0) }, uRegrow: { value: new THREE.Vector2(0, 0) },
    uOver: { value: 0 }, uOC: { value: new THREE.Vector3(0.5, 0.5, 0.5) }, uOSun: { value: 0 }, uTc: { value: 0 },
    uAmb: { value: new THREE.Vector3(1, 1, 1) }, uFogK: { value: 1 }, uSnow: { value: 0 },
  };
  const HELP = /* glsl */ `
    float vn2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
      float a = hash12(i), b = hash12(i + vec2(1.0, 0.0)), c = hash12(i + vec2(0.0, 1.0)), d = hash12(i + vec2(1.0, 1.0));
      return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 2.0 - 1.0; }
    float fbm2(vec2 p, int oct){ float a = 0.5, s = 0.0; for (int i = 0; i < 10; i++){ if (i >= oct) break; s += a * vn2(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + vec2(3.1, 1.7); a *= 0.5; } return s; }
    vec3 vor2(vec2 x){ vec2 p = floor(x), f = fract(x); float d1 = 8.0, d2 = 8.0, id = 0.0; vec2 c = vec2(0.0);
      for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++){ vec2 b = vec2(float(i), float(j)); vec2 r = b + hash22(p + b) - f; float d = dot(r, r);
        if (d < d1){ d2 = d1; d1 = d; id = hash12(p + b + 17.31); } else if (d < d2) d2 = d; }
      return vec3(sqrt(d1), sqrt(d2), id); }
  `;
  const terrMat = new THREE.ShaderMaterial({
    uniforms: tu, vertexShader: RAY_VS, depthTest: true, depthWrite: true,
    fragmentShader: /* glsl */ `
      ${NOISE}${HELP}
      #include <packing>
      varying vec3 vDir;
      uniform vec3 uCam, uSun, uWC; uniform mat4 uVP, uSMat; uniform float uT, uSMon, uSMtx, uWhite; uniform sampler2D uSM; uniform vec4 uStreak, uImp;
      uniform vec3 uP0, uDC, uSG, uSunK; uniform vec4 uRad;
      uniform vec4 uScar; uniform vec2 uRegrow; uniform float uOver, uOSun, uTc, uFogK; uniform vec3 uOC, uAmb;
      const float WL = ${WL.toFixed(3)};
      const vec3 SUNC0 = vec3(${SUNCOL.join(', ')}) * ${SUNI.toFixed(2)};
      #define SUNC (SUNC0 * uSunK)
      const vec2 VOLC = vec2(2600.0, -9500.0);

      float riverZ(float x){ return -260.0 + 70.0 * sin(x * 0.004 + 0.6) + 28.0 * sin(x * 0.011 + 2.0); }
      float plain(vec2 p){ return 0.6 * sin(p.x * 0.013 + p.y * 0.007) + 0.4 * sin(p.x * 0.005 - p.y * 0.017 + 1.3); }
      // far relief: valley walls, a ridge line, and the volcano
      float relief(vec2 p, float fp){
        float far = smoothstep(500.0, 4000.0, length(p - vec2(0.0, -300.0)));
        float r = 0.0;
        if (far > 0.0){
          vec2 q = p * 0.00025;
          float rg = 1.0 - abs(fbm2(q * 1.3 + 3.0, fp < 30.0 ? 6 : 4));
          r = far * (180.0 * (fbm2(q, 4) + 0.6) + 520.0 * rg * rg * smoothstep(3000.0, 9000.0, -p.y)) ;
          r = max(r, 0.0);
        }
        float vr = length(p - VOLC);
        float cone = 2300.0 * pow(max(0.0, 1.0 - vr / 5200.0), 1.6);
        cone -= 260.0 * smoothstep(420.0, 120.0, vr);                       // crater
        cone += 120.0 * fbm2(p * 0.0012, 5) * smoothstep(5200.0, 1500.0, vr) + 60.0 * (1.0 - abs(vn2(vec2(atan(p.y - VOLC.y, p.x - VOLC.x) * 9.0, vr * 0.002)))) * smoothstep(5000.0, 800.0, vr);
        return max(r, cone);
      }
      // m: x = forest canopy weight, y = river sand, z = fern/understory, w = conifer id
      float terrain(vec2 p, float fp, out vec4 m){
        float rz = riverZ(p.x), d = abs(p.y - rz);
        float bank = smoothstep(14.0, 40.0, d + 6.0 * vn2(p * 0.03));
        float h = mix(WL - 1.6 + d * 0.02, plain(p) + 0.8, bank);
        if (fp < 3.0) h += 0.12 * fbm2(p * 0.15, 3) * bank;
        h += relief(p, fp);
        // conifer stands: tall cones, kept off the river margins and the herd's ford
        float fm = smoothstep(0.05, 0.3, fbm2(p * 0.0021 + 7.0, 4) + 0.12 * smoothstep(600.0, 1500.0, length(p - vec2(0.0, -260.0))));
        fm *= smoothstep(60.0, 110.0, d) * smoothstep(260.0, 420.0, length((p - vec2(20.0, -150.0)) * vec2(0.8, 1.0)) + 60.0 * vn2(p * 0.01));
        fm *= 1.0 - smoothstep(800.0, 2500.0, relief(p, 9.0));
        float can = 0.0, id = 0.0;
        if (fm > 0.0){
          if (fp < 6.0){
            vec3 v = vor2(p / 9.0); id = v.z;
            float ht = 16.0 + 18.0 * v.z;
            float cone = max(0.0, 1.0 - v.x / (0.55 + 0.25 * v.z));
            // tiers of branches give the cones a ragged, layered edge
            float tiers = 0.85 + 0.15 * sin(cone * 30.0 + v.z * 20.0);
            can = ht * pow(cone, 0.75) * tiers * step(0.18, v.z) + 4.0 * smoothstep(0.0, 1.0, cone);
          } else can = 20.0 + 4.0 * vn2(p * 0.02);
        }
        can *= fm;
        // ferns and cycads: low knee-high cover on the plain
        float fern = bank * smoothstep(-0.2, 0.5, fbm2(p * 0.02 + 2.0, 3)) * (1.0 - fm);
        if (fp < 0.1) h += fern * 0.25 * fbm2(p * 1.1, 4);
        if (fp < 0.6 && fern > 0.0){
          vec3 v = vor2(p / 6.0);
          float dome = sqrt(max(0.0, 1.0 - pow(v.x / (0.28 + 0.2 * v.z), 2.0)));
          float b = dome * (0.9 + 1.6 * v.z) * step(0.55, v.z) * (fp < 0.15 ? 0.8 + 0.3 * vn2(p * 3.0) + 0.22 * fbm2(p * 7.0, fp < 0.04 ? 4 : 2) : 1.0);
          b *= smoothstep(0.2, 0.6, fern);
          h += b;
          fern = max(fern, smoothstep(0.0, 0.3, b));
        }
        h += can;
        m = vec4(fm * smoothstep(1.0, 4.0, can), 1.0 - bank, fern, id);
        return h;
      }
      float terrain(vec2 p, float fp){ vec4 m; return terrain(p, fp, m); }

      // ---------- sky ----------
      // burning ejecta falling back through the sky: short fiery streaks on a few scrolling layers (direction-space cells)
      vec3 ejectaRain(vec3 rd, float s){
        float a = smoothstep(2.4, 5.0, s) * smoothstep(0.0, 0.06, rd.y);
        if (a <= 0.0) return vec3(0.0);
        vec2 q = vec2(atan(rd.x, -rd.z), asin(clamp(rd.y, -1.0, 1.0)));
        vec3 acc = vec3(0.0);
        for (int L = 0; L < 3; L++){
          float fl = float(L), sc = 8.0 + 6.0 * fl;
          vec2 dir = normalize(vec2(-0.45 + 0.2 * fl, -1.0));
          vec2 g = q * sc - dir * s * (1.5 + 0.5 * fl) + fl * 17.3;
          vec2 id = floor(g), f = fract(g) - 0.5;
          float h = hash12(id + 3.1 * fl);
          if (h < 0.5) continue;
          vec2 pa = f - (hash22(id) - 0.5) * 0.3;
          float al = dot(pa, -dir); vec2 pp = pa + dir * al;
          float w = 0.01 + 0.025 * max(al, 0.0);
          float l = exp(-dot(pp, pp) / (w * w)) * smoothstep(-0.03, 0.0, al) * exp(-max(al, 0.0) * 6.0) * step(al, 0.44);
          vec3 hc = mix(vec3(1.0, 0.88, 0.65), vec3(1.0, 0.38, 0.08), clamp(al * 4.0, 0.0, 1.0));
          acc += hc * l * (2.5 + 5.0 * fract(h * 13.7)) / (1.0 + 0.5 * fl);
        }
        return acc * a;
      }
      // the impact beyond the horizon: a white-hot fireball that boils up into an ash column, a fan of glowing ejecta,
      // the shock dome (a thin condensation shell growing over the sky), burning debris raining back, a reddening sky
      vec3 impactSky(vec3 c, vec3 rd){
        float s = uImp.w; vec3 id = normalize(uImp.xyz);
        vec3 rt = normalize(cross(id, vec3(0.0, 1.0, 0.0)));
        float hx = dot(rd, rt), hy = rd.y, fwd = dot(rd, id);
        float rs = smoothstep(0.0, 9.0, s);
        c = mix(c, c * vec3(1.3, 0.62, 0.42) * (1.0 - 0.35 * smoothstep(4.0, 9.0, s)), rs * 0.8);
        // shock dome: seen from outside, its limb is an arch around the impact that rises and sweeps overhead
        {
          vec3 oc = uCam - uP0; float b = dot(oc, rd), cc = dot(oc, oc), Rs = uRad.x;
          if (Rs > 1.0 && Rs * Rs < cc && b < 0.0){
            float d = sqrt(max(cc - b * b, 0.0)), w = 0.03 * Rs + 80.0;
            float n = fbm2(vec2(atan(hx, fwd) * 30.0, hy * 25.0) + vec2(s * 0.3, 0.0), 4);
            float shell = exp(-pow((d - Rs) / w, 2.0)) * (0.5 + 0.7 * smoothstep(-0.4, 0.5, n));
            float inside = smoothstep(Rs + w, Rs - 3.0 * w, d);
            c = mix(c, c * vec3(1.1, 0.92, 0.82) + vec3(0.1, 0.06, 0.03), inside * 0.55);
            c += vec3(1.0, 0.94, 0.86) * shell * 1.6 * smoothstep(-0.005, 0.02, hy);
          }
        }
        if (fwd > 0.0){
          float sz = min(s, 10.0);
          float R = 0.05 + 0.15 * sqrt(sz), yc = R * (0.2 + 0.08 * sz);
          float n = fbm2(vec2(hx, hy) * 60.0 / (1.0 + 0.4 * sz) + vec2(0.0, -0.5 * s), 5);
          float dd = length(vec2(hx / (R * 1.15), (hy - yc) / R));
          float stem = smoothstep(R * 0.45, R * 0.2, abs(hx)) * step(hy, yc) * step(0.0, hy);
          float dens = max(smoothstep(1.0, 0.75, dd + 0.35 * n), stem * smoothstep(0.0, 0.4, s - 1.0));
          float hot = smoothstep(0.9, 0.05, dd + 0.3 * n);
          vec3 emi = mix(vec3(1.0, 0.93, 0.8) * 26.0, vec3(1.0, 0.55, 0.2) * 9.0, smoothstep(0.0, 1.5, s));
          emi = mix(emi, vec3(0.9, 0.22, 0.04) * 1.8, smoothstep(1.5, 7.0, s));
          emi *= hot * hot;
          vec3 smk = mix(vec3(0.42, 0.3, 0.24), vec3(0.2, 0.15, 0.13), smoothstep(-0.2, 0.4, n)) * (0.8 + 0.6 * smoothstep(-0.1, 0.3, hy - yc));
          smk += vec3(1.0, 0.4, 0.1) * 0.6 * smoothstep(0.4, -0.2, hy - yc) * exp(-s * 0.15);       // lit from below by the fire
          c = mix(c, smk + emi, dens * smoothstep(-0.003, 0.004, hy));
          // the ejecta fan: glowing rays thrown up and out of the crater in the first seconds
          float r = length(vec2(hx, hy)), ang = atan(max(hy, 0.0), hx);
          float rays = smoothstep(0.4, 0.95, vn2(vec2(ang * 13.0, 3.0))) * smoothstep(0.0, 0.03, hy) * (0.6 + 0.4 * vn2(vec2(ang * 40.0, r * 30.0 - s)));
          float Rr = 0.06 + 0.3 * sqrt(s);
          c += vec3(1.0, 0.55, 0.2) * rays * smoothstep(Rr, Rr * 0.25, r) * smoothstep(0.01, 0.05, r) * 3.0 * exp(-s * 0.9) * smoothstep(0.0, 0.15, s);
        }
        // the glow pooled along the horizon: the burning land beyond
        c += vec3(1.0, 0.45, 0.12) * exp(-max(hy, 0.0) * 18.0) * exp(-abs(hx) * 2.2) * (4.0 * exp(-s * 0.3) + 1.0) * smoothstep(-0.02, 0.0, hy) * max(fwd + 0.3, 0.0);
        c += ejectaRain(rd, s);
        return c;
      }
      vec3 sky(vec3 rd){
        float y = max(rd.y, 0.0), mu = dot(rd, uSun);
        vec3 zen = vec3(0.07, 0.2, 0.55), hor = vec3(0.66, 0.72, 0.82);
        vec3 c = mix(hor, zen, pow(y, 0.45));
        c += vec3(1.0, 0.65, 0.35) * pow(max(mu, 0.0), 6.0) * 0.5 * (1.0 - y);
        c += vec3(1.0, 0.9, 0.75) * pow(max(mu, 0.0), 60.0) * 1.2;
        c += vec3(1.0, 0.95, 0.85) * smoothstep(0.99965, 0.9999, mu) * 60.0;
        // thin high cirrus, lit warm from the low sun
        if (rd.y > 0.0){
          vec2 q = rd.xz / (rd.y + 0.08) * 0.6 + vec2(uT * 0.004, 0.0);
          float ci = smoothstep(0.0, 0.7, fbm2(q * vec2(1.0, 3.0), 5) + 0.1) * smoothstep(0.0, 0.2, rd.y);
          c = mix(c, vec3(1.0, 0.95, 0.88) * (1.0 + 1.4 * pow(max(mu, 0.0), 6.0)), ci * 0.18);
        }
        // the volcano's ash plume, leaning downwind
        {
          vec3 vp = vec3(VOLC.x, 2100.0, VOLC.y) - uCam;
          vec3 dir = normalize(vp); float ang = acos(clamp(dot(rd, dir), -1.0, 1.0));
          vec3 up = normalize(vec3(-0.25, 1.0, 0.0));
          float hgt = dot(rd - dir, up) / 0.12;                         // ~0..1 up the plume in view space
          vec3 sd = normalize(cross(dir, up));
          float side = dot(rd - dir, sd) / 0.12;
          float wdt = 0.06 + 0.35 * clamp(hgt, 0.0, 1.0);
          float pl = smoothstep(wdt, wdt * 0.3, abs(side + hgt * hgt * 0.5 + 0.05 * fbm2(vec2(hgt * 6.0, uT * 0.05), 4)))
                   * smoothstep(-0.02, 0.05, hgt) * smoothstep(1.2, 0.5, hgt);
          pl *= smoothstep(-0.2, 0.4, fbm2(vec2(side * 8.0, hgt * 6.0 - uT * 0.03), 5) + 0.4);
          vec3 ash = mix(vec3(0.35, 0.3, 0.3), vec3(0.95, 0.72, 0.55), clamp(0.5 + 0.5 * side, 0.0, 1.0));
          c = mix(c, ash * (0.75 + 0.35 * hgt), pl * 0.7);
        }
        // fire streak (the asteroid), a hot head with a long glowing trail
        if (uStreak.w > 0.0){
          vec3 hd = normalize(uStreak.xyz); vec3 tdir = vec3(-0.75, 0.42, 0.2); tdir = normalize(tdir - hd * dot(tdir, hd));   // trail lies on the sky sphere
          vec3 rel = rd - hd; float along = dot(rel, tdir); vec3 perp = rel - tdir * along;
          float al = max(along, 0.0), pl = length(perp);
          float wd = 0.0025 + 0.03 * al;
          float tb = 0.65 + 0.7 * fbm2(vec2(al * 60.0 - uT * 3.0, dot(perp, cross(tdir, hd)) * 400.0), 4);
          float tr = exp(-pl * pl / (wd * wd)) * smoothstep(-0.004, 0.0, along) * exp(-al * 4.0) * tb;
          float smoke = exp(-pl * pl / (4.0 * wd * wd)) * smoothstep(0.0, 0.05, al) * exp(-al * 2.0) * tb;
          float head = exp(-dot(rel, rel) / 0.00003), halo = exp(-sqrt(dot(rel, rel)) / 0.012);
          vec3 hot = mix(vec3(1.0, 0.92, 0.75), vec3(1.0, 0.45, 0.12), smoothstep(0.0, 0.12, al));
          c = mix(c, vec3(0.42, 0.36, 0.33), smoke * 0.35 * min(uStreak.w, 1.0));
          c += (hot * tr * 5.0 + vec3(1.0, 0.95, 0.85) * head * 40.0 + vec3(1.0, 0.6, 0.3) * halo * 0.8) * uStreak.w;
        }
        if (rd.y < 0.0) c = hor * 0.9;
        // the impact winter: a low ceiling of ash cloud racing over (time-lapse), breaking up as it clears
        if (uOver > 0.0){
          vec2 q = rd.xz / (max(rd.y, 0.0) + 0.12) * 0.45 + vec2(uTc * 0.05, uTc * 0.02);
          float n = fbm2(q, 5), n2 = fbm2(q * 3.0 + vec2(uTc * 0.08, 0.0), 3);
          vec3 oc = uOC * (0.7 + 0.45 * smoothstep(-0.5, 0.6, n + 0.3 * n2)) * (0.8 + 0.3 * smoothstep(-0.1, 0.5, rd.y));
          oc += uOC * vec3(1.0, 0.92, 0.8) * pow(max(mu, 0.0), 10.0) * uOSun * 1.5 + vec3(1.0, 0.9, 0.75) * smoothstep(0.9993, 0.9997, mu) * uOSun * 5.0;
          float cov = rd.y < 0.0 ? 1.0 : smoothstep(-0.12, 0.12, 0.5 + 0.5 * n + 0.15 * n2 - (1.0 - uOver));
          c = mix(c, oc, cov * min(uOver * 3.0, 1.0));
        }
        if (uImp.w > 0.0) c = impactSky(c, rd);
        return c * 1.1;
      }
      // shadows: terrain soft shadow + the animals' shadow map
      float shadow(vec3 p, float fp){
        float res = 1.0, t = max(fp * 2.0, 0.05);
        for (int i = 0; i < 32; i++){
          vec3 q = p + uSun * t;
          if (q.y > 2600.0) break;
          float h = terrain(q.xz, max(fp, t * 0.01));
          float dh = q.y - h;
          res = min(res, 10.0 * dh / t);
          if (res < 0.0) break;
          t += clamp(dh * 0.6, fp + 0.1, 120.0);
        }
        return smoothstep(0.0, 1.0, res);
      }
      float animalShadow(vec3 p){
        if (uSMon < 0.5) return 1.0;
        vec4 sc = uSMat * vec4(p, 1.0); sc.xyz /= sc.w;
        if (sc.x < 0.0 || sc.x > 1.0 || sc.y < 0.0 || sc.y > 1.0 || sc.z > 1.0) return 1.0;
        float s = 0.0;
        for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++){
          float dd = unpackRGBAToDepth(texture2D(uSM, sc.xy + vec2(float(i), float(j)) * uSMtx * 1.5));
          s += step(sc.z - 0.0008, dd);
        }
        return s / 25.0;
      }
      vec3 fog(vec3 col, vec3 rd, float t, float y0){
        float dens = exp(-max(y0, 0.0) / 2500.0);
        float f = 1.0 - exp(-t * dens * uFogK / 16000.0);
        vec3 fc = mix(vec3(0.62, 0.7, 0.82), vec3(1.0, 0.8, 0.6), pow(max(dot(rd, uSun), 0.0), 4.0) * 0.6);
        fc = mix(fc, uOC * 0.95, min(uOver * 1.5, 1.0));
        return mix(col, fc, f);
      }
      vec3 shadeGround(vec3 p, vec3 rd, float t, float fp){
        vec4 m; float h = terrain(p.xz, fp, m);
        float e = max(fp, 0.01);
        vec3 n = normalize(vec3(terrain(p.xz - vec2(e, 0.0), fp) - terrain(p.xz + vec2(e, 0.0), fp), 2.0 * e,
                                terrain(p.xz - vec2(0.0, e), fp) - terrain(p.xz + vec2(0.0, e), fp)));
        float steep = 1.0 - smoothstep(0.6, 0.9, n.y);
        float rel = relief(p.xz, fp);
        // soils: dark wet mud at the river, pale sandbars, then green-brown floodplain
        vec3 mud = mix(vec3(0.2, 0.16, 0.11), vec3(0.5, 0.42, 0.3), smoothstep(WL + 0.1, WL + 1.2, p.y));
        vec3 meadow = mix(vec3(0.13, 0.19, 0.06), vec3(0.3, 0.29, 0.12), smoothstep(-0.4, 0.5, fbm2(p.xz * 0.012, 4)));
        meadow *= 0.8 + 0.4 * fbm2(p.xz * 0.25, 4) + 0.15 * fbm2(p.xz * 2.0, 3);
        meadow = mix(meadow, vec3(0.36, 0.29, 0.16), smoothstep(0.2, 0.7, fbm2(p.xz * 0.004 + 4.0, 3)) * 0.6);
        vec3 fernc = mix(vec3(0.04, 0.09, 0.03), vec3(0.1, 0.16, 0.05), smoothstep(-0.3, 0.6, fbm2(p.xz * 0.7, 3)));
        vec3 conif = mix(vec3(0.025, 0.07, 0.025), vec3(0.07, 0.14, 0.045), m.w) * (0.6 + 0.6 * smoothstep(0.2, 0.95, n.y));
        vec3 rock = mix(vec3(0.24, 0.2, 0.18), vec3(0.4, 0.33, 0.27), smoothstep(-0.4, 0.4, fbm2(p.xz * 0.01 + p.y * 0.01, 4)));
        vec3 ash = vec3(0.17, 0.15, 0.15);
        vec3 alb = mix(meadow, mud, m.y);
        alb = mix(alb, fernc, m.z * 0.8);
        alb = mix(alb, conif, m.x);
        float hi = smoothstep(150.0, 600.0, rel);
        alb = mix(alb, mix(vec3(0.12, 0.15, 0.08), rock, steep), hi);
        alb = mix(alb, ash, smoothstep(5200.0, 2500.0, length(p.xz - VOLC)) * smoothstep(400.0, 1200.0, p.y));
        // scorched: plants burn to black stubs and the ground to char, then grey ash settles on everything;
        // the recovery: ferns spread over the ash first (the fern spike), then the forest and the meadow come back
        if (uScar.x > 0.0){
          vec3 alb0 = alb;
          float veg = max(m.x, m.z);
          vec3 charc = mix(vec3(0.03, 0.026, 0.024), vec3(0.09, 0.075, 0.065), smoothstep(-0.3, 0.5, fbm2(p.xz * 0.3, 3)));
          vec3 burnt = mix(alb0 * 0.35, charc, 0.55 + 0.45 * veg);
          burnt = mix(burnt, vec3(0.36, 0.35, 0.34) * (0.8 + 0.35 * fbm2(p.xz * 0.5, 3)), uScar.z * smoothstep(0.3, 0.8, n.y) * (1.0 - 0.6 * m.x));
          alb = mix(alb0, burnt, uScar.x * (1.0 - 0.7 * hi) * (1.0 - 0.6 * m.y));
          float spike = smoothstep(0.0, 0.3, fbm2(p.xz * 0.025 + 5.0, 4) + 0.2 * fbm2(p.xz * 0.3, 3) + 1.5 * uRegrow.x - 1.1) * (1.0 - m.y) * (1.0 - hi);
          vec3 fresh = mix(vec3(0.08, 0.2, 0.04), vec3(0.2, 0.32, 0.08), smoothstep(-0.3, 0.6, fbm2(p.xz * 0.7, 3)));
          alb = mix(alb, fresh, spike * (1.0 - 0.7 * m.x));
          alb = mix(alb, alb0, uRegrow.y);
        }
        float sh = shadow(p + n * max(fp, 0.02) * 2.0, fp) * animalShadow(p);
        float dif = max(dot(n, uSun), 0.0);
        vec3 col = alb * (SUNC * dif * sh + vec3(0.32, 0.4, 0.58) * uAmb * (0.45 + 0.55 * n.y) * 0.55 + vec3(0.3, 0.22, 0.14) * 0.1);
        // the land on fire behind the front: flame patches crawling through the undergrowth, the conifers burning like torches
        if (uScar.y > 0.0){
          float fn = fbm2(p.xz * 0.06 + vec2(0.0, -uT * 0.25), 4) + 0.35 * fbm2(p.xz * 0.5 + vec2(uT * 0.6, -uT * 1.3), 3);
          float fire = smoothstep(0.2, 0.6, fn + 0.3 * max(m.x, m.z)) * (1.0 - m.y) * (1.0 - hi);
          col += vec3(1.0, 0.33, 0.06) * fire * uScar.y * (2.0 + 3.0 * m.x) * (0.75 + 0.25 * sin(uT * 11.0 + fn * 20.0));
          col += vec3(0.7, 0.18, 0.03) * uScar.y * 0.06 * (1.0 - m.y);
        }
        // foliage is thin: the low sun glows through needles and fronds seen against it
        float back = pow(max(dot(rd, uSun), 0.0), 3.0);
        col += max(m.x, m.z * 0.7) * vec3(0.5, 0.6, 0.15) * SUNC * back * 0.18 * sh;
        // wet mud mirrors the bright sky
        vec3 R = reflect(rd, n);
        col += m.y * smoothstep(WL + 0.6, WL + 0.05, p.y) * (sky(R) * 0.15 + SUNC * pow(max(dot(R, uSun), 0.0), 80.0) * 1.5 * sh);
        return col;
      }
      float waveH(vec2 p, float fp){
        float h = 0.03 * sin(p.x * 0.35 - uT * 1.2 + 2.0 * vn2(p * 0.05)) + 0.02 * sin(dot(p, vec2(0.5, 0.8)) + uT * 1.7);
        if (fp < 1.0) h += 0.02 * fbm2(p * 0.8 + vec2(-uT * 0.4, 0.0), 3);
        return h;
      }
      vec3 shadeWater(vec3 p, vec3 rd, float t, float fp){
        float e = max(fp, 0.03);
        float h0 = waveH(p.xz, fp);
        vec3 n = normalize(vec3(h0 - waveH(p.xz + vec2(e, 0.0), fp), e, h0 - waveH(p.xz + vec2(0.0, e), fp)));
        n = normalize(mix(vec3(0.0, 1.0, 0.0), n, smoothstep(40.0, 2.0, fp) * 0.5 + 0.2));
        float depth = max(WL - terrain(p.xz, max(fp, 0.5)), 0.0);
        vec3 R = reflect(rd, n);
        float fr = 0.02 + 0.98 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
        float sh = animalShadow(p);
        vec3 body = mix(vec3(0.24, 0.2, 0.12) * SUNC * 0.25, vec3(0.03, 0.08, 0.06), smoothstep(0.1, 1.5, depth)) * (0.4 + 0.6 * sh);
        vec3 col = mix(body, sky(R), fr);
        // the glitter path towards the sun
        col += SUNC * (pow(max(dot(R, uSun), 0.0), 700.0) * 25.0 + pow(max(dot(R, uSun), 0.0), 60.0) * 0.6) * sh;
        return col;
      }

      // the dust front: a towering turbulent wall rolling outwards over the plain, its foot lit by the fires behind it.
      // March from where the ray enters the front's cylinder; the wall is taller further inside. Returns coverage.
      float dustWall(vec3 ro, vec3 rd, float tEnd, out vec3 wc, out float tW){
        wc = vec3(0.0); tW = tEnd;
        float Rf = uRad.y; if (Rf < 1.0) return 0.0;
        vec2 oc = ro.xz - uP0.xz, d2 = rd.xz;
        float a = dot(d2, d2), b = dot(oc, d2), c = dot(oc, oc) - Rf * Rf;
        if (c < 0.0 || a < 1e-6) return 0.0;
        float disc = b * b - a * c; if (disc < 0.0 || b > 0.0) return 0.0;
        float sq = sqrt(disc), t1 = (-b - sq) / a, t2 = min((-b + sq) / a, tEnd);
        if (t1 > tEnd) return 0.0;
        float s = uImp.w, grow = smoothstep(0.0, 3.0, s);
        for (int i = 0; i < 14; i++){
          float k = float(i) / 13.0, t = mix(t1, t2, k * k);
          vec3 p = ro + rd * t; vec2 q = p.xz - uP0.xz; float r = length(q);
          float ang = atan(q.y, q.x);
          vec2 wq = vec2(ang * Rf / 420.0, p.y / 380.0 - uT * 0.4);
          float n = fbm2(wq, 5);
          float H = grow * (1300.0 + 1100.0 * n) + (Rf - r) * 0.06;
          if (p.y < H){
            float cov = smoothstep(0.0, 200.0, H - p.y);
            float top = smoothstep(-700.0, 0.0, p.y - H);
            // billows: finer churning detail, lit from above (a cheap vertical-gradient normal)
            float n2 = fbm2(vec2(ang * Rf / 120.0, p.y / 110.0 - uT * 1.1), 4);
            float lit = clamp(0.55 + 2.2 * (fbm2(wq + vec2(0.0, 0.25), 5) - n) + 0.35 * n2, 0.1, 1.3);
            vec3 base = mix(vec3(0.26, 0.18, 0.13), vec3(0.58, 0.43, 0.32), smoothstep(-0.4, 0.6, n + 0.4 * n2));
            wc = base * mix(0.45, 1.0, top) * lit * SUNC * 0.45 + base * vec3(0.3, 0.25, 0.25) * 0.25;
            wc += vec3(1.0, 0.36, 0.08) * 1.8 * exp(-max(p.y, 0.0) / 250.0) * (0.3 + 0.7 * smoothstep(-0.2, 0.6, n2));   // fires at its foot
            wc += vec3(1.0, 0.5, 0.2) * 0.6 * smoothstep(140.0, 0.0, H - p.y) * exp(-s * 0.15);                         // rim lit by the fireball
            wc = fog(wc, rd, t * 0.5, ro.y);
            tW = t; return cov;
          }
        }
        return 0.0;
      }
      // inside the dust: a choking brown-red haze, glowing from above and from the fires, the sun a dull disc
      vec3 inDust(vec3 rd){
        float n = fbm3(rd * 3.0 + vec3(0.0, uT * 0.12, uT * 0.05), 4);
        vec3 c = uDC * (0.7 + 0.5 * n) * (0.75 + 0.45 * smoothstep(-0.3, 0.8, rd.y));
        c += vec3(0.6, 0.14, 0.03) * smoothstep(0.25, -0.25, rd.y) * (0.6 + 0.4 * n) * length(uDC) * 1.5;
        float mu = max(dot(rd, uSun), 0.0);
        c += uSG * (pow(mu, 8.0) * 0.5 + pow(mu, 120.0) * 2.0 + smoothstep(0.9990, 0.9995, mu) * 8.0);
        return c;
      }

      void main(){
        vec3 rd = normalize(vDir), ro = uCam;
        vec3 col; float tHit = -1.0;
        float t = 0.0, tmax = uRad.z > 0.99 ? uRad.w * 12.0 : 50000.0, ymax = 2600.0;
        if (ro.y > ymax){ t = rd.y < 0.0 ? (ro.y - ymax) / -rd.y : tmax; }
        bool hit = false; float fpK = 1.0 / 540.0 * ${Math.tan((38 * Math.PI) / 360).toFixed(4)};
        float lt = t;
        for (int i = 0; i < 300; i++){
          if (t > tmax) break;
          vec3 p = ro + rd * t;
          if (p.y > ymax && rd.y > 0.0) break;
          float fp = t * fpK;
          float h = max(terrain(p.xz, fp), WL);
          float dh = p.y - h;
          if (dh < fp * 0.5){ hit = true; break; }
          lt = t;
          t += max(dh * 0.4, fp * 0.8 + 1e-4);
        }
        if (hit){
          float ta = lt, tb = t;
          for (int i = 0; i < 7; i++){ float tm = 0.5 * (ta + tb); vec3 p = ro + rd * tm; if (p.y - max(terrain(p.xz, tm * fpK), WL) < 0.0) tb = tm; else ta = tm; }
          t = tb; tHit = t;
          vec3 p = ro + rd * t; float fp = t * fpK;
          float gh = terrain(p.xz, fp);
          col = gh > WL ? shadeGround(p, rd, t, fp) : shadeWater(vec3(p.x, WL, p.z), rd, t, fp);
          if (uImp.w > 0.0){
            // the shock racing over the land kicks up a bright line of dust; behind it the land is hazed
            float r = length(p.xz - uP0.xz);
            col = mix(col, vec3(0.5, 0.38, 0.28) * uSunK, 0.4 * smoothstep(uRad.x + 200.0, uRad.x - 1500.0, r));
            col += vec3(0.9, 0.7, 0.5) * exp(-pow((r - uRad.x) / 220.0, 2.0)) * 0.8 * uSunK;
          }
          col = fog(col, rd, t, ro.y);
        } else col = sky(rd);
        if (uImp.w > 0.0){
          vec3 wc; float tW;
          float wa = dustWall(ro, rd, hit ? tHit : 60000.0, wc, tW);
          col = mix(col, wc, wa);
          if (wa > 0.5) tHit = tW;
          if (uRad.z > 0.0) col = mix(col, inDust(rd), (1.0 - exp(-(hit ? tHit : 1e6) / uRad.w)) * uRad.z);
        }
        col = mix(col, uWC, uWhite);
        gl_FragColor = vec4(col, 1.0);
        if (tHit > 0.0){ vec4 c = uVP * vec4(ro + rd * tHit, 1.0); gl_FragDepth = clamp(c.z / c.w * 0.5 + 0.5, 0.0, 1.0); }
        else gl_FragDepth = 0.999999;
      }`,
  });
  const terr = fsQuad(terrMat); terr.renderOrder = -1;
  scene.add(terr);
  // inside the dust cloud: drifting, swirling haze over everything (the terrain pass only gives a static depth fog),
  // and the white the scene opens and closes on
  const dustMat = new THREE.ShaderMaterial({
    uniforms: tu, vertexShader: RAY_VS, depthTest: false, depthWrite: false, transparent: true,
    fragmentShader: /* glsl */ `
      ${NOISE}
      varying vec3 vDir;
      uniform vec3 uWC, uDC; uniform vec4 uRad; uniform float uWhite, uT;
      void main(){
        vec3 rd = normalize(vDir);
        float n = fbm3(vec3(rd.x * 2.6 + uT * 0.45, rd.y * 3.2 - uT * 0.1, rd.z * 2.6 - uT * 0.3), 5)
                + 0.4 * fbm3(rd * 9.0 + vec3(uT * 0.9, 0.0, 0.0), 3);
        float a = uRad.z * smoothstep(-0.35, 0.8, n) * 0.6 * (1.0 - smoothstep(150.0, 600.0, uRad.w));
        vec3 col = uDC * (0.85 + 0.6 * n);
        col = mix(col, uWC, uWhite);
        gl_FragColor = vec4(col, max(a, uWhite));
      }`,
  });
  const dust = fsQuad(dustMat); dust.renderOrder = 100;
  scene.add(dust);
  // embers: glowing flecks drifting down through the dust (additive, in front of everything)
  const emberMat = new THREE.ShaderMaterial({
    uniforms: tu, vertexShader: RAY_VS, depthTest: false, depthWrite: false, transparent: true, blending: THREE.AdditiveBlending,
    fragmentShader: /* glsl */ `
      ${NOISE}
      varying vec3 vDir;
      uniform vec4 uRad; uniform float uWhite, uT;
      void main(){
        vec3 rd = normalize(vDir);
        vec2 q = vec2(atan(rd.x, -rd.z), asin(clamp(rd.y, -1.0, 1.0)));
        vec3 acc = vec3(0.0);
        for (int L = 0; L < 3; L++){
          float fl = float(L), sc = 22.0 + 16.0 * fl;
          vec2 g = q * sc + vec2(uT * (0.5 + 0.3 * fl), uT * (0.9 + 0.5 * fl)) + fl * 11.7;
          vec2 id = floor(g), f = fract(g) - 0.5;
          float h = hash12(id + fl * 5.3);
          if (h < 0.86) continue;
          vec2 pa = f - (hash22(id) - 0.5) * 0.6;
          pa.y *= 0.5;
          float l = exp(-dot(pa, pa) / 0.0006) * (0.55 + 0.45 * sin(uT * 9.0 + h * 40.0));
          acc += mix(vec3(1.0, 0.55, 0.2), vec3(1.0, 0.25, 0.04), fract(h * 7.1)) * l * 1.4 / (1.0 + fl);
        }
        gl_FragColor = vec4(acc * uRad.z * (1.0 - uWhite), 1.0);
      }`,
  });
  const embers = fsQuad(emberMat); embers.renderOrder = 101;
  scene.add(embers);
  // the impact winter (the 'after' cut only): grey ash flakes drifting down like snow
  if (AFTER) {
    const snowMat = new THREE.ShaderMaterial({
      uniforms: tu, vertexShader: RAY_VS, depthTest: false, depthWrite: false, transparent: true,
      fragmentShader: /* glsl */ `
        ${NOISE}
        varying vec3 vDir;
        uniform vec3 uOC; uniform float uSnow, uWhite, uT;
        void main(){
          vec3 rd = normalize(vDir);
          vec2 q = vec2(atan(rd.x, -rd.z), asin(clamp(rd.y, -1.0, 1.0)));
          float a = 0.0;
          for (int L = 0; L < 4; L++){
            float fl = float(L), sc = 14.0 + 12.0 * fl;
            vec2 g = q * sc + vec2(uT * 0.12 * (1.0 + fl) + 0.4 * sin(uT * 0.35 + fl * 2.0), uT * (0.3 + 0.22 * fl)) + fl * 13.1;
            vec2 id = floor(g), f = fract(g) - 0.5;
            float h = hash12(id + fl * 3.7);
            if (h < 0.55) continue;
            vec2 pa = f - (hash22(id) - 0.5) * 0.6;
            pa += 0.08 * vec2(sin(uT * 1.3 + h * 30.0), 0.0);
            a = max(a, exp(-dot(pa, pa) / (0.006 / (1.0 + 0.6 * fl))) * (0.35 + 0.65 * fract(h * 7.3)) * (0.5 + 0.25 * fl));
          }
          gl_FragColor = vec4(uOC * 1.7 + 0.05, min(a, 1.0) * uSnow * (1.0 - uWhite));
        }`,
    });
    const snow = fsQuad(snowMat); snow.renderOrder = 102;
    scene.add(snow);
  }

  // ---------- lights for the rasterised animals (matched to the terrain shader's sun and sky) ----------
  const sunL = new THREE.DirectionalLight(new THREE.Color(...SUNCOL), SUNI * Math.PI);
  sunL.castShadow = true;
  sunL.shadow.mapSize.set(4096, 4096);
  sunL.shadow.bias = -0.0004; sunL.shadow.normalBias = 0.04;
  scene.add(sunL, sunL.target);
  tu.uSMat.value = sunL.shadow.matrix;               // updated by three while it renders the shadow map, before the terrain draws
  const hemi = new THREE.HemisphereLight(new THREE.Color(0.32 * 0.55, 0.4 * 0.55, 0.58 * 0.55), new THREE.Color(0.06, 0.045, 0.03), Math.PI);
  scene.add(hemi);
  const aimShadow = (cx, cz, r) => {
    sunL.target.position.set(cx, 0, cz);
    sunL.position.set(cx, 0, cz).addScaledVector(SUN, 800);
    const c = sunL.shadow.camera; c.left = -r; c.right = r; c.top = r; c.bottom = -r; c.near = 1; c.far = 1600; c.updateProjectionMatrix();
  };

  // ---------- timeline ----------
  const DUR = 22, STREAK = 15.5, IMP = 23.2, END = 44;
  // the aftermath, in seconds after the impact: the shock dome reaches the camera at SHOCK, the dust front at FRONT
  const DIMP = 36000, SHOCK = IMP + 7.6, FRONT = IMP + 8.2, SUNUP = 36.5;

  // ---------- animals ----------
  const loader = new GLTFLoader();
  const load = (f) => new Promise((res, rej) => loader.load('/assets/models/' + f, res, undefined, rej));
  const [apatoG, trexG, paraG] = await Promise.all(['apato.glb', 'trex.glb', 'para.glb'].map(load));
  const animU = { uCam: { value: new THREE.Vector3() }, uSun: { value: SUN }, uRad: tu.uRad, uDC: tu.uDC,
    uT: tu.uT, uScar: tu.uScar, uRegrow: tu.uRegrow, uOver: tu.uOver, uOC: tu.uOC, uFogK: tu.uFogK, uBurnK: { value: 1 } };
  const FOG = /* glsl */ `
    float dens = exp(-max(uCam.y, 0.0) / 2500.0);
    vec3 rdF = normalize(vWP - uCam); float tF = length(vWP - uCam);
    float fF = 1.0 - exp(-tF * dens * uFogK / 16000.0);
    vec3 fcF = mix(vec3(0.62, 0.7, 0.82), vec3(1.0, 0.8, 0.6), pow(max(dot(rdF, uSun), 0.0), 4.0) * 0.6);
    fcF = mix(fcF, uOC * 0.95, min(uOver * 1.5, 1.0));
    gl_FragColor.rgb = mix(gl_FragColor.rgb, fcF, fF);
    if (uRad.z > 0.0) gl_FragColor.rgb = mix(gl_FragColor.rgb, uDC * (0.8 + 0.3 * smoothstep(-0.3, 0.8, rdF.y)), (1.0 - exp(-tF / uRad.w)) * uRad.z);`;
  // skin: object-space mottling, darker back, paler belly; fine scale bump; warm rim where the sun is behind the animal
  const skinMat = (base, { mottle = 0.35, freq = 40, bump = 0.6, belly = null, rough = 0.85 } = {}) => {
    const m = new THREE.MeshStandardMaterial({ color: new THREE.Color(...base), roughness: rough, metalness: 0 });
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, animU);
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vObj; varying vec3 vWP; varying vec3 vWN;')
        .replace('#include <skinning_vertex>', '#include <skinning_vertex>\nvObj = position; vWP = (modelMatrix * vec4(transformed, 1.0)).xyz;')
        .replace('#include <defaultnormal_vertex>', '#include <defaultnormal_vertex>\nvWN = normalize(mat3(modelMatrix) * objectNormal);');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', `#include <common>\n${NOISE}\nvarying vec3 vObj; varying vec3 vWP; varying vec3 vWN; uniform vec3 uCam, uSun, uDC; uniform vec4 uRad;
          uniform float uT, uOver, uFogK, uBurnK; uniform vec4 uScar; uniform vec2 uRegrow; uniform vec3 uOC; float chr = 0.0;
          vec3 perturb(vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float fd){
            vec3 vSigmaX = normalize(dFdx(surf_pos)), vSigmaY = normalize(dFdy(surf_pos)), vN = surf_norm;
            vec3 R1 = cross(vSigmaY, vN), R2 = cross(vN, vSigmaX); float fDet = dot(vSigmaX, R1) * fd;
            vec3 vGrad = sign(fDet) * (dHdxy.x * R1 + dHdxy.y * R2); return normalize(abs(fDet) * surf_norm - vGrad); }`)
        .replace('#include <color_fragment>', `#include <color_fragment>
          vec3 oq = vObj * ${freq.toFixed(2)};
          float mt = fbm3(oq * 0.25, 4), sp = smoothstep(0.25, 0.6, fbm3(oq * 0.8 + 3.0, 3));
          diffuseColor.rgb *= 1.0 + ${mottle.toFixed(2)} * (mt - 0.25 * sp);
          float up = vWN.y;
          diffuseColor.rgb *= mix(0.78, 1.0, smoothstep(0.9, 0.2, up));
          ${belly ? `diffuseColor.rgb = mix(diffuseColor.rgb, vec3(${belly.join(', ')}), smoothstep(-0.2, -0.7, up) * 0.6);` : ''}
          // burnt by the heat behind the front: charred skin spreading in patches, then grey ash settling on the carcass
          if (uScar.x > 0.0){
            float sb = uScar.x * uBurnK;
            chr = sb * smoothstep(-0.3, 0.2, fbm3(oq * 0.5 + 7.0, 3) + 1.4 * sb - 0.9);
            diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.03, 0.025, 0.022) * (0.7 + 0.6 * mt), chr);
            diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.34, 0.33, 0.32) * (0.85 + 0.3 * mt), uScar.z * smoothstep(-0.1, 0.7, up));
          }
          float scl = voronoi3(oq * 2.2).x;`)
        .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
          { float hb = ${bump.toFixed(2)} * (scl * 0.6 + 0.4 * fbm3(oq * 1.2, 3)) * 0.02;
            normal = perturb(-vViewPosition, normal, vec2(dFdx(hb), dFdy(hb)), faceDirection); }`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
          { vec3 vd = normalize(uCam - vWP); float rim = pow(1.0 - max(dot(normalize(vWN), vd), 0.0), 3.0);
            totalEmissiveRadiance += diffuseColor.rgb * vec3(${SUNCOL.join(', ')}) * rim * pow(max(dot(-vd, uSun), 0.0), 2.0) * 1.6; }
          // still burning: glowing cracks in the char and flames licking up off the back
          if (uScar.y > 0.0 && chr > 0.0){
            vec3 vc = voronoi3(oq * 0.35);
            float crack = smoothstep(0.1, 0.0, vc.y - vc.x) * (0.6 + 0.4 * sin(uT * 6.0 + vc.z * 40.0));
            float flame = smoothstep(0.35, 0.75, fbm3(vWP * 0.45 - vec3(0.0, uT * 2.8, 0.0), 4) + 0.3 * vWN.y);
            totalEmissiveRadiance += vec3(1.0, 0.32, 0.05) * uScar.y * uBurnK * chr * (crack * 2.5 + flame * 4.0); }`)
        .replace('#include <fog_fragment>', FOG);
    };
    return m;
  };
  // per material name: a realistic, desaturated palette (the source models are toy-coloured)
  const PAL = {
    apato: { Material: [0.27, 0.24, 0.2], Brown: [0.16, 0.12, 0.09] },
    trex: { LightYellow: [0.26, 0.2, 0.13], LightGreen: [0.19, 0.15, 0.1], Green: [0.11, 0.09, 0.06], Black: [0.02, 0.02, 0.02], Red: [0.3, 0.08, 0.06] },
    para: { LightYellow: [0.45, 0.4, 0.3], Green: [0.25, 0.22, 0.14], LightGreen: [0.32, 0.28, 0.18], Red: [0.45, 0.2, 0.1] },
  };
  const prep = (g, kind, len, opt) => {
    const root = g.scene;
    root.traverse((o) => {
      if (!o.isMesh) return;
      let geo = o.geometry.clone();
      geo.deleteAttribute('normal');
      geo = mergeVertices(geo, 1e-6);
      geo.computeVertexNormals();
      o.geometry = geo;
      const c = PAL[kind][o.material.name] || [0.3, 0.27, 0.2];
      o.material = skinMat(c, { ...opt, ...(o.material.name === 'Black' ? { mottle: 0, bump: 0.1, rough: 0.3 } : {}) });
      o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
    });
    // normalise to a real body length; nose direction is found from the walk clip later (models face +z)
    root.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(root, true), s = new THREE.Vector3(); b.getSize(s);
    const k = len / Math.max(s.x, s.z);
    return { root, k, minY: b.min.y * k, clips: g.animations };
  };
  const apato = prep(apatoG, 'apato', 25, { freq: 30, mottle: 0.4 });
  const trex = prep(trexG, 'trex', 12, { freq: 60, mottle: 0.35, belly: [0.32, 0.28, 0.22] });
  const para = prep(paraG, 'para', 9, { freq: 70, mottle: 0.3, belly: [0.5, 0.45, 0.35] });
  const clip = (P, name) => P.clips.find((c) => c.name.endsWith(name));
  const actors = [];
  const spawn = (P, anim, { speed = 1, phase = 0, path, scale = 1 }) => {
    const o = SkeletonUtils.clone(P.root);
    const g = new THREE.Group(); g.add(o); o.scale.setScalar(P.k * scale);
    scene.add(g);
    const mix = new THREE.AnimationMixer(o);
    const a = mix.clipAction(clip(P, anim)); a.play();
    const A = { g, o, mix, a, speed, phase, path, P, scale, len: clip(P, anim).duration };
    actors.push(A);
    return A;
  };
  // herd: walking across the ford, right to left, staggered
  const R = rng(9);
  for (let i = 0; i < 7; i++) {
    const x0 = 10 + i * 15 + R() * 8, z0 = riverZ(x0) - 14 + (R() - 0.5) * 16 - (i % 3) * 8, sc = i === 3 ? 0.65 : 0.85 + R() * 0.3;
    const yaw = -0.35 + 0.08 * Math.sin(i * 3.1);
    spawn(apato, 'Apatosaurus_Walk', { speed: 0.9 + R() * 0.15, phase: R() * 3, scale: sc,
      path: (t) => [x0 + 1.5 * t * Math.sin(yaw), z0 + 1.5 * t * Math.cos(yaw), yaw] });
  }
  // a few hadrosaurs on the near bank
  for (let i = 0; i < 4; i++) {
    // the yaw is drawn once here: drawing it inside path() gave the idle ones a new random heading every frame
    const x0 = 60 + i * 13 + R() * 8, z0 = riverZ(x0) + 35 + R() * 15, yaw0 = R() * 6;
    spawn(para, i % 2 ? 'Parasaurolophus_Idle' : 'Parasaurolophus_Walk', { phase: R() * 4, scale: 0.9 + R() * 0.2,
      path: (t) => [x0 + (i % 2 ? 0 : 0.9 * t), z0, i % 2 ? yaw0 : Math.PI / 2] });
  }
  // the tyrannosaur walks in, stops when the streak appears, looks round, then roars at the sky
  const REX_STOP = 15.5;
  const rexX = (t) => -40 + 1.3 * (t < REX_STOP ? t : REX_STOP + (1 - Math.exp(-(t - REX_STOP) * 1.3)) / 1.3);
  const rex = spawn(trex, 'TRex_Walk', { path: (t) => [rexX(t), -128 - 0.3 * Math.min(t, REX_STOP), Math.PI * 0.55 + 0.8 * smooth(REX_STOP + 0.3, REX_STOP + 3.5, t)] });
  {
    const idle = rex.mix.clipAction(clip(trex, 'TRex_Idle')), roar = rex.mix.clipAction(clip(trex, 'TRex_Attack'));
    const lenI = clip(trex, 'TRex_Idle').duration, lenR = clip(trex, 'TRex_Attack').duration;
    idle.play(); roar.play(); roar.setLoop(THREE.LoopOnce); roar.clampWhenFinished = true;
    const ROAR = 18.6;
    rex.layers = (t) => {
      const wR = smooth(ROAR - 0.3, ROAR, t) * (1 - smooth(ROAR + lenR - 0.4, ROAR + lenR, t));
      const wW = 1 - smooth(REX_STOP - 0.2, REX_STOP + 0.6, t);
      return [[rex.a, wW * (1 - wR), (t * rex.speed) % rex.len], [idle, (1 - wW) * (1 - wR), Math.max(0, t - REX_STOP) % lenI], [roar, wR, clamp(t - ROAR, 0, lenR - 1e-3)]];
    };
  }

  // the heat behind the dust front kills them where they stand: each one stops and collapses (its Death clip) a moment
  // after the front reaches it, and stays down. In the 'after' cut they lie where they fell (A.die far in the past).
  const RD = rng(77);
  for (const A of actors) {
    const c = clip(A.P, 'Death');
    A.tStop = FRONT + 0.15 + RD() * 1.6;
    A.die = AFTER ? -100 : A.tStop;
    A.dAct = A.mix.clipAction(c); A.dAct.setLoop(THREE.LoopOnce); A.dAct.clampWhenFinished = true; A.dAct.play(); A.dAct.enabled = false;
    A.dLen = c.duration; A.dRate = 0.75 + 0.3 * RD();
    A.sink = (A.P === apato ? 4.5 : A.P === trex ? 2.4 : 1.6) * A.scale;
  }
  // sinks a carcass into the ground as it decays under the regrowth ('after' cut)
  let sinkK = 0;
  function placeActors(t) {
    for (const A of actors) {
      const tp = AFTER ? A.tStop : Math.min(t, A.tStop);
      const [x, z, yaw] = A.path(tp);
      A.g.position.set(x, groundY(x, z) - A.P.minY * A.scale - sinkK * A.sink, z);
      A.g.rotation.y = yaw;
      const wD = smooth(A.die, A.die + 0.3, t);
      if (wD <= 0) {
        A.dAct.enabled = false;
        if (A.layers) {
          for (const [act, w, tt] of A.layers(t)) { act.enabled = true; act.setEffectiveWeight(w); act.time = tt; }
          A.mix.update(0);
        } else A.mix.setTime((t * A.speed + A.phase) % A.len);
        continue;
      }
      if (A.layers) for (const [act, w, tt] of A.layers(tp)) { act.enabled = true; act.setEffectiveWeight(w * (1 - wD)); act.time = tt; }
      else { A.a.enabled = true; A.a.setEffectiveWeight(1 - wD); A.a.time = (tp * A.speed + A.phase) % A.len; }
      A.dAct.enabled = true; A.dAct.setEffectiveWeight(wD); A.dAct.time = clamp((t - A.die) * A.dRate, 0, A.dLen - 1e-3);
      A.mix.update(0);
    }
  }

  // ---------- pterosaurs (procedural: a slim body with membrane wings, gliding with bursts of beats) ----------
  const pteroGeo = (() => {
    // half-wing outline in the x/z plane (x out along the wing, z forward); the body is a thin tube
    const P = [], I = [];
    const wing = (sgn) => {
      const b = P.length / 3;
      const pts = [[0, 0.35], [0.9, 0.3], [2.2, 0.18], [3.6, 0.0], [4.2, -0.15], [3.0, -0.45], [1.6, -0.8], [0.0, -1.0]];
      for (const [x, z] of pts) P.push(sgn * x, 0, z);
      for (let i = 1; i < pts.length - 1; i++) sgn > 0 ? I.push(b, b + i, b + i + 1) : I.push(b, b + i + 1, b + i);
    };
    wing(1); wing(-1);
    const b = P.length / 3, seg = 8;
    const prof = [[1.9, 0.0], [1.4, 0.12], [0.6, 0.22], [-0.4, 0.2], [-1.4, 0.06], [-2.0, 0.0]];   // beak .. tail
    for (const [z, r] of prof) for (let j = 0; j < seg; j++) { const a = (j / seg) * Math.PI * 2; P.push(Math.cos(a) * r * 0.8, Math.sin(a) * r, z); }
    for (let i = 0; i < prof.length - 1; i++) for (let j = 0; j < seg; j++) {
      const a = b + i * seg + j, c = b + i * seg + ((j + 1) % seg);
      I.push(a, a + seg, c, c, a + seg, c + seg);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setIndex(I); g.computeVertexNormals();
    return g;
  })();
  const pteroMat = skinMat([0.3, 0.22, 0.16], { freq: 6, mottle: 0.3, bump: 0.2 });
  pteroMat.side = THREE.DoubleSide;
  const pteros = [], RP = rng(31);
  for (let i = 0; i < 6; i++) {
    const m = new THREE.Mesh(pteroGeo, pteroMat);
    m.castShadow = true; m.frustumCulled = false;
    m.userData = { ph: RP() * 6, x0: -330 + RP() * 60 + i * 9, y0: 120 + RP() * 30 - i * 4, z0: 30 - i * 14 + RP() * 10, sp: 13 + RP() * 3, sc: 0.9 + RP() * 0.4 };
    scene.add(m); pteros.push(m);
  }
  const pW = pteroGeo.attributes.position, pBase = Float32Array.from(pW.array);
  function placePteros(t) {
    for (const m of pteros) {
      const o = m.userData, tf = Math.min(t, SHOCK), k = tf * o.sp;
      m.position.set(o.x0 + k * 0.85, o.y0 - tf * 1.6 + 2 * Math.sin(tf * 0.4 + o.ph), o.z0 - k * 0.5);
      m.rotation.set(0.05, Math.atan2(0.85, -0.5), 0.25 * Math.sin(tf * 0.5 + o.ph), 'YXZ');
      m.scale.setScalar(o.sc * 1.6);
      // the shock wave tears them out of the air: flung away from the impact, tumbling, burning, falling
      if (t > SHOCK) {
        const d = t - SHOCK;
        m.position.x += o.sp * 0.85 * d - sBh.x * 25 * d; m.position.z += -o.sp * 0.5 * d - sBh.z * 25 * d;
        m.position.y -= 4.9 * d * d;
        m.rotation.x += d * (2 + o.ph * 0.3); m.rotation.z += d * (3 - o.ph * 0.4);
        m.visible = m.position.y > groundY(m.position.x, m.position.z) - 2;
      }
    }
    // one shared wing pose per frame (they are small); the 16 wing vertices bend up/down, the body stays rigid
    const beat = Math.sin(t * 4.2) * smooth(-0.2, 0.4, Math.sin(t * 0.9));
    for (let v = 0; v < 16; v++) {
      const ax = Math.abs(pBase[v * 3]);
      pW.array[v * 3 + 1] = pBase[v * 3 + 1] + (beat * 0.35 + 0.06) * ax + (ax > 2.0 ? -0.18 * (ax - 2.0) * (1 + beat) : 0);
    }
    pW.needsUpdate = true;
  }

  // ---------- camera ----------
  const tmpM = new THREE.Matrix4();
  const look = (p, tgt) => { cam.position.set(...p); cam.lookAt(...tgt); cam.updateMatrixWorld(); };
  const setRay = () => {
    const ty = Math.tan((cam.fov * Math.PI) / 360);
    tu.uTan.value.set(ty * cam.aspect, ty); tu.uCamWorld.value.copy(cam.matrixWorld); tu.uCam.value.copy(cam.position);
    tu.uVP.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    animU.uCam.value.copy(cam.position);
  };
  // one continuous descent from pterosaur height to the tyrannosaur's shoulder
  const camP = new THREE.CatmullRomCurve3([V(-260, 150, 70), V(-170, 85, -10), V(-100, 34, -70), V(-55, 12, -90), V(-32, 4.5, -100)], false, 'centripetal');
  const camT = new THREE.CatmullRomCurve3([V(40, 0, -190), V(40, 0, -200), V(30, 2, -200), V(5, 5, -180), V(25, 26, -200)], false, 'centripetal');
  const sA = V(0.05, 0.42, -0.9).normalize(), sB = V(0.62, 0.003, -0.785).normalize(), sD = new THREE.Vector3();
  const camEnd = camP.getPoint(1), sBh = V(sB.x, 0, sB.z).normalize();
  tu.uP0.value.set(camEnd.x + sBh.x * DIMP, 0, camEnd.z + sBh.z * DIMP);
  const dirA = new THREE.Vector3(), dirS = SUN.clone().add(V(0, -0.06, 0)).normalize();
  function update(t) {
    tu.uT.value = t;
    const u = ease.sine(clamp(t / DUR, 0, 1)) * 0.75 + 0.25 * clamp(t / DUR, 0, 1);
    cam.fov = keys([[0, 42], [10, 38], [DUR, 40], [SHOCK, 40], [SHOCK + 4, 46]], t); cam.updateProjectionMatrix();
    const p = camP.getPoint(u), q = camT.getPoint(u);
    // after the impact: the camera drops its gaze to the horizon; the ground shakes as the seismic wave passes,
    // then hard as the shock dome hits, and keeps trembling in the dust
    const dw = smooth(IMP - 0.5, IMP + 3.5, t);
    const sh = 0.14 * smooth(IMP + 1.0, IMP + 1.6, t) * (1 - smooth(IMP + 3.5, IMP + 6.0, t))
      + 1.1 * smooth(SHOCK - 0.05, SHOCK + 0.08, t) * Math.exp(-Math.max(t - SHOCK - 0.08, 0) * 0.8)
      + 0.1 * smooth(FRONT, FRONT + 1, t) * (1 - smooth(38, 41, t));
    const shx = sh * (Math.sin(t * 37) + 0.6 * Math.sin(t * 59 + 1)), shy = sh * (Math.sin(t * 43 + 2) + 0.5 * Math.sin(t * 71));
    const cp = [p.x + shx * 0.05, p.y + 0.15 * Math.sin(t * 0.7) + shy * 0.05, p.z];
    // as the dust thins, the camera turns and lifts its gaze to the sun burning through
    dirA.set(q.x + 6 * dw + shx - cp[0], q.y - 18 * dw + shy - cp[1], q.z - cp[2]).normalize();
    dirA.lerp(dirS, ease.inOut(smooth(SUNUP, SUNUP + 5.5, t))).normalize();
    look(cp, [cp[0] + dirA.x * 100, cp[1] + dirA.y * 100, cp[2] + dirA.z * 100]);
    setRay();
    placeActors(t);
    placePteros(t);
    aimShadow(lerp(-20, -10, u), lerp(-160, -140, u), lerp(170, 90, u));
    // the asteroid: a fire streak from high left sliding down towards the horizon
    const k = clamp((t - STREAK) / (IMP - STREAK), 0, 1);
    sD.copy(sA).lerp(sB, k * k * 0.6 + k * 0.4).normalize();
    tu.uStreak.value.set(sD.x, sD.y, sD.z, t < IMP ? smooth(STREAK, STREAK + 1.2, t) * (1 + 1.5 * k) : 0);
    const s = t - IMP;
    tu.uImp.value.set(sB.x, 0, sB.z, t >= IMP ? s : -1);
    tu.uRad.value.set(s > 0 ? DIMP * Math.pow(s / 7.6, 0.85) : 0, s > 0 ? DIMP * Math.pow(s / 8.2, 0.85) : 0,
      smooth(FRONT - 0.12, FRONT + 0.2, t), keys([[FRONT, 16], [35, 28], [38.5, 90], [41.5, 260], [END, 900]], t));
    tu.uDC.value.set(...keys([[FRONT, [0.15, 0.07, 0.04]], [35, [0.2, 0.09, 0.05]], [38.5, [0.48, 0.3, 0.19]], [41, [0.8, 0.64, 0.5]], [43.2, [1.3, 1.2, 1.1]]], t));
    tu.uSG.value.set(...keys([[34, [0, 0, 0]], [36.5, [0.5, 0.1, 0.02]], [39.5, [1.6, 0.8, 0.35]], [42.5, [3, 2.8, 2.5]]], t));
    // the sun dims and reddens behind the spreading ash
    const ash = smooth(IMP, IMP + 8, t);
    tu.uSunK.value.set(1 - 0.35 * ash, 1 - 0.55 * ash, 1 - 0.65 * ash);
    sunL.intensity = SUNI * Math.PI * (1 - 0.45 * ash);
    sunL.color.setRGB(SUNCOL[0], SUNCOL[1] * (1 - 0.25 * ash), SUNCOL[2] * (1 - 0.4 * ash));
    tu.uDust.value = 0;
    // behind the front everything burns: the plants char, fires run through the undergrowth, the animals burn where they fall
    tu.uScar.value.set(smooth(FRONT - 0.1, FRONT + 3.0, t), smooth(FRONT, FRONT + 1.5, t), 0, 0);
    // opens out of the sun glare (the climb out of the Cambrian sea) and closes into the white of S8's cloud deck
    tu.uWhite.value = Math.max(1 - smooth(0, 1.4, t), smooth(42.6, 43.9, t));
  }

  // ---------- the 'after' cut (S11): impact winter, then the recovery ----------
  // 0-13 the burnt valley under a low ash sky, ash falling like snow, the carcasses smouldering; 13-25 time-lapse:
  // the cloud races, days flicker, the light slowly returns; ferns spread over the ash first (17-28), then the forest
  // and the meadow (25-35) while the carcasses sink into the regrowth; birds cross the valley; white at the end.
  const AEND = 39;
  const aP = new THREE.CatmullRomCurve3([V(-36, 2.6, -110), V(-28, 3.2, -112), V(-12, 9, -108), V(15, 28, -95), V(45, 62, -70), V(70, 95, -45)], false, 'centripetal');
  const aT = new THREE.CatmullRomCurve3([V(-19, 1.5, -133), V(-12, 1.2, -140), V(10, 0, -170), V(60, 0, -260), V(150, 10, -600), V(300, 40, -1300)], false, 'centripetal');
  const birds = [];
  if (AFTER) {
    for (const m of pteros) m.visible = false;
    const birdMat = skinMat([0.1, 0.085, 0.075], { freq: 6, mottle: 0.2, bump: 0.1 });
    birdMat.side = THREE.DoubleSide;
    const RB = rng(53);
    for (let i = 0; i < 9; i++) {
      const m = new THREE.Mesh(pteroGeo, birdMat);
      m.frustumCulled = false;
      m.userData = { d: 55 + RB() * 40, y: -4 + RB() * 14, x0: -70 - RB() * 30 - i * 6, sp: 11 + RB() * 3, ph: RB() * 6 };
      scene.add(m); birds.push(m);
    }
  }
  const fwd = new THREE.Vector3(), rgt = new THREE.Vector3(), upv = V(0, 1, 0);
  function placeBirds(t) {
    cam.getWorldDirection(fwd); rgt.crossVectors(fwd, upv).normalize();
    for (const m of birds) {
      const o = m.userData, x = o.x0 + (t - 28) * o.sp;
      m.visible = t > 27 && t < AEND;
      m.position.copy(cam.position).addScaledVector(fwd, o.d).addScaledVector(rgt, x).addScaledVector(upv, o.y + 1.5 * Math.sin(t * 0.8 + o.ph));
      m.rotation.set(0, Math.atan2(rgt.x, rgt.z), 0.15 * Math.sin(t + o.ph), 'YXZ');
      m.scale.setScalar(0.32);
    }
    const beat = Math.sin(t * 9.0);
    for (let v = 0; v < 16; v++) {
      const ax = Math.abs(pBase[v * 3]);
      pW.array[v * 3 + 1] = pBase[v * 3 + 1] + (beat * 0.5 + 0.1) * ax;
    }
    pW.needsUpdate = true;
  }
  const dayDip = (t) => (0.5 - 0.5 * Math.cos((2 * Math.PI * (t - 13)) / 2.4)) * smooth(13, 14, t) * (1 - smooth(23.5, 25.5, t));
  function updateAfter(t) {
    tu.uT.value = t;
    const v = clamp(t / AEND, 0, 1), u = 0.7 * ease.inOut(v) + 0.3 * v;
    cam.fov = 40; cam.updateProjectionMatrix();
    const p = aP.getPointAt(u), q = aT.getPointAt(u);
    look([p.x, p.y + 0.1 * Math.sin(t * 0.6), p.z], [q.x, q.y, q.z]);
    setRay();
    sinkK = smooth(20, 32, t);
    placeActors(t);
    placeBirds(t);
    aimShadow(lerp(-15, 20, u), lerp(-140, -170, u), lerp(120, 220, u));
    tu.uStreak.value.set(0, 0, 0, 0);
    tu.uImp.value.set(sB.x, 0, sB.z, -1);
    tu.uRad.value.set(0, 0, 0, 1);
    tu.uScar.value.set(1, keys([[0, 0.35], [9, 0]], t), keys([[0, 0.5], [7, 1]], t), 0);
    tu.uRegrow.value.set(smooth(17, 28, t), smooth(25, 35, t));
    tu.uOver.value = keys([[0, 1], [20, 1], [26, 0.55], [32, 0.15], [35, 0]], t);
    tu.uOC.value.set(...keys([[0, [0.13, 0.125, 0.13]], [12, [0.16, 0.155, 0.16]], [20, [0.38, 0.37, 0.38]], [28, [0.7, 0.7, 0.72]]], t));
    tu.uOSun.value = keys([[14, 0], [22, 0.4], [30, 1]], t);
    tu.uTc.value = t + 17 * clamp(t - 13, 0, 12.5);
    const sk = keys([[0, [0.1, 0.1, 0.12]], [12, [0.12, 0.12, 0.14]], [22, [0.45, 0.42, 0.4]], [30, [0.85, 0.83, 0.8]], [35, [1, 1, 1]]], t);
    tu.uSunK.value.set(...sk);
    sunL.intensity = SUNI * Math.PI * (sk[0] + sk[1] + sk[2]) / 3;
    sunL.color.setRGB(SUNCOL[0] * sk[0], SUNCOL[1] * sk[1], SUNCOL[2] * sk[2]).multiplyScalar(3 / (sk[0] + sk[1] + sk[2]));
    const am = keys([[0, [0.35, 0.33, 0.32]], [20, [0.6, 0.58, 0.58]], [32, [1, 1, 1]]], t);
    tu.uAmb.value.set(...am);
    hemi.intensity = Math.PI * (am[0] + am[1] + am[2]) / 3;
    tu.uFogK.value = keys([[0, 7], [18, 4], [30, 1.3], [35, 1]], t);
    tu.uSnow.value = keys([[0, 0.9], [13, 0.8], [19, 0]], t);
    tu.uWhite.value = Math.max(1 - smooth(0, 2.0, t), smooth(37.4, 38.8, t));
  }
  const gradeAfter = (t) => ({
    flash: [1, 1, 1, 0],
    exposure: 0.9 * (1 - 0.7 * dayDip(t)), bloom: 0.3, bloomThreshold: 0.85, bloomRadius: 0.4, hdrMax: 6,
    vignette: 0.4, sat: keys([[0, 0.75], [20, 0.85], [32, 1.08]], t), contrast: 1.08, chroma: 0.001, lift: [0.006, 0.004, 0.006], gain: [1.0, 0.98, 0.95],
  });
  let firstDraw = true;
  function draw(renderer) {
    renderer.setClearColor(0x000000, 1); renderer.clear(true, true, true);
    const au = renderer.shadowMap.autoUpdate;
    renderer.shadowMap.autoUpdate = false; renderer.shadowMap.needsUpdate = true;
    if (firstDraw && !sunL.shadow.map) { renderer.render(scene, cam); renderer.shadowMap.needsUpdate = true; renderer.clear(true, true, true); }
    firstDraw = false;
    tu.uSM.value = sunL.shadow.map ? sunL.shadow.map.texture : null;
    tu.uSMon.value = sunL.shadow.map ? 1 : 0;
    renderer.render(scene, cam);
    renderer.shadowMap.autoUpdate = au;
  }
  const grade = (t) => ({
    // the impact flash: a hard white blink that leaves the sky glowing
    flash: [1, 0.9, 0.78, (t >= IMP ? 0.16 * Math.exp(-(t - IMP) * 4.0) * smooth(IMP, IMP + 0.06, t) : 0)
      + (t >= SHOCK ? 0.025 * Math.exp(-(t - SHOCK) * 5.0) : 0)],
    exposure: 0.9, bloom: 0.35 + (t >= IMP ? 0.35 * Math.exp(-(t - IMP) * 0.4) : 0), bloomThreshold: 0.85, bloomRadius: 0.4, hdrMax: 6,
    vignette: 0.4, sat: 1.08, contrast: 1.08, chroma: 0.001, lift: [0.006, 0.004, 0.006], gain: [1.0, 0.98, 0.95],
  });
  return {
    scene, camera: cam, update: AFTER ? updateAfter : update, draw, grade: AFTER ? gradeAfter : grade,
    dispose() { scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); sunL.shadow.map?.dispose(); },
  };
}
