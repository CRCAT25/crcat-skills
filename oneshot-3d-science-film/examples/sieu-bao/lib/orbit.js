// The Earth from orbit (units = Earth radii), after the planet layer of the first film: oceans, land, polar ice, a
// satellite-like cloud field, single-scattering air and the blue limb. One hero hurricane lives in the cloud field:
// log-spiral rain bands wound round a central dense overcast, the eye a clear hole whose walls throw shade on the
// sea, all turning counter-clockwise (northern hemisphere). uHI grows it from scattered towers (0) to a mature
// storm (1); uEye sets the eye radius; uWarm tints the open tropical ocean like a sea-temperature map.
import * as THREE from 'three';
import { NOISE, RAY_VS } from './glsl.js';
import { softPoints, fsQuad, rng } from './kit.js';

const RE = 6.371e6;
const CLOUD = 9000;

export function makeOrbit({ W, H, fov = 36 }) {
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(fov, W / H, 1e-4, 1e4);
  const SUN = new THREE.Vector3(0.55, 0.45, 0.7).normalize();
  const r = rng(88);
  const stars = softPoints({
    count: 6000, sizeAtten: false, place: () => {
      const u = r() * 2 - 1, a = r() * Math.PI * 2, s = Math.sqrt(1 - u * u), m = Math.pow(r(), 6);
      const k = r(); const c = k < 0.3 ? [0.75, 0.85, 1.1] : k < 0.85 ? [1, 0.95, 0.9] : [1.1, 0.85, 0.65];
      return { p: [s * Math.cos(a) * 3000, u * 3000, s * Math.sin(a) * 3000], s: 1.1 + 3 * m, c: c.map((x) => x * (0.12 + 1.5 * m)) };
    },
  });
  scene.add(stars);

  const u = {
    uTan: { value: new THREE.Vector2() }, uCamWorld: { value: new THREE.Matrix4() }, uCam: { value: new THREE.Vector3() },
    uSun: { value: SUN }, uT: { value: 0 }, uCloud: { value: 0.5 },
    uHC: { value: new THREE.Vector3(0, 0.26, 0.97).normalize() }, uHR: { value: 0.14 }, uHI: { value: 1 }, uEye: { value: 0.0035 },
    uSpin: { value: 0 }, uWarm: { value: 0 }, uWhite: { value: 0 }, uWC: { value: new THREE.Vector3(1.5, 1.5, 1.5) },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, vertexShader: RAY_VS, depthTest: false, depthWrite: false, transparent: true,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    fragmentShader: /* glsl */ `
      ${NOISE}
      varying vec3 vDir;
      uniform vec3 uCam, uSun, uHC, uWC; uniform float uT, uCloud, uHR, uHI, uEye, uSpin, uWarm, uWhite;
      const float RC = 1.0 + ${CLOUD.toFixed(1)} / 6.371e6;
      const float HS = 0.0014;
      const float RA = 1.0 + HS * 14.0;
      const vec3 BR = vec3(5.8, 13.5, 33.1) * 6.371;
      const float BM = 6.0;
      vec2 sphT(vec3 ro, vec3 rd, float r){ float b = dot(ro, rd), c = dot(ro, ro) - r * r, h = b * b - c; if (h < 0.0) return vec2(-1.0); h = sqrt(h); return vec2(-b - h, -b + h); }
      float airmass(float c){ float z = degrees(acos(clamp(c, -1.0, 1.0))); return 1.0 / (max(c, 0.0) + 0.50572 * pow(max(96.08 - z, 0.05), -1.6364)); }
      vec3 sunT(vec3 p){
        float r = length(p), h = max(r - 1.0, 0.0), c = dot(p / r, uSun);
        float shad = smoothstep(-0.03, 0.04, c + sqrt(max(2.0 * h, 0.0)));
        float c2 = c + sqrt(max(2.0 * h, 0.0)) * 0.9;
        return exp(-(BR + BM) * HS * exp(-h / HS) * min(airmass(clamp(c2, -0.2, 1.0)), 40.0)) * shad;
      }
      vec3 rotA(vec3 p, vec3 c, float w){ float cw = cos(w), sw = sin(w); return p * cw + cross(c, p) * sw + c * dot(c, p) * (1.0 - cw); }
      float elev(vec3 p, float camD){
        vec3 w = p + 0.18 * vec3(fbm3(p * 1.3 + 4.0, 4), fbm3(p * 1.3 + 9.0, 4), fbm3(p * 1.3 + 1.0, 4));
        float e = fbm3(w * 1.6 + 2.3, 7) + 0.35 * ridge3(w * 3.1 + 7.0, 5) - 0.4;
        e += 0.03 * fbm3(p * 420.0, 5) * smoothstep(0.5, 0.05, camD);
        e -= 0.6 * exp(-pow(acos(clamp(dot(p, uHC), -1.0, 1.0)) / (uHR * 3.5), 2.0));   // the storm sits on open sea
        return e;
      }
      // the hero storm in its own polar frame. Returns cover; hgt = cloud-top relief for shading; core = 1 in the CDO
      float storm(vec3 p, float camD, out float hgt, out float core){
        hgt = 0.0; core = 0.0;
        float a = acos(clamp(dot(p, uHC), -1.0, 1.0));
        float rn = a / uHR;
        if (rn > 2.6) return 0.0;
        vec3 t1 = normalize(cross(vec3(0.0, 1.0, 0.0), uHC)), t2 = cross(uHC, t1);
        // inner air turns faster (texture only, kept small so it never winds into a lollipop); bands turn rigidly
        float om = uSpin * (0.5 + 0.5 / (0.3 + rn));
        vec3 q = rotA(p, uHC, -om);
        float phi = atan(dot(p, t2), dot(p, t1)) - uSpin * 0.7;
        float tex = fbm3(q * 30.0, 3), fine = fbm3(q * 300.0, 3) * smoothstep(0.3, 0.05, camD);
        // spiral coordinates: sp is constant along an arm, lr runs along it. Noise fast across arms, slow along
        float lr = log(rn + 0.08), sp = phi + 1.8 * lr;
        float st = fbm3(vec3(cos(sp) * 3.0, sin(sp) * 3.0, lr * 0.8 + 3.0), 4);
        float st2 = fbm3(vec3(cos(sp) * 10.0, sin(sp) * 10.0, lr * 1.5), 3);
        // five broad arms with cloud between them (three thin ones read as a throwing star)
        float s = smoothstep(-1.0, 0.9, cos(5.0 * sp + 0.8 * st));
        // density, not a hard mask: soft wispy edges where the streak noise thins the arm out
        float bd = s * 0.8 + 0.6 * st + 0.3 * st2 + 0.3 * tex - 0.3 + 0.45 * smoothstep(1.5, 0.5, rn);
        float bands = smoothstep(-0.2, 0.45, bd) * smoothstep(2.5, 0.7, rn) * smoothstep(0.1, 0.4, rn);
        // the central dense overcast grows with intensity, its rim combed into the spiral
        float cR = mix(0.4, 0.9, uHI);
        float ci = fbm3(vec3(cos(sp) * 10.0, sin(sp) * 10.0, lr * 16.0), 4) * smoothstep(0.25, 0.04, camD);
        core = smoothstep(cR + 0.16, cR - 0.08, rn - 0.25 * st - 0.08 * st2);
        // the eye: a clear round hole, sharper and smaller as the storm matures; a raised wall round it
        float ea = a + uEye * 0.25 * fbm3(q * 900.0, 3);
        float eye = smoothstep(uEye * 0.75, uEye * 1.25, ea);
        float wall = exp(-pow((ea - uEye * 1.35) / (uEye * 0.7), 2.0));
        // formation: scattered convective towers instead of organised bands
        float towers = smoothstep(0.0, 0.55, fbm3(q * 22.0 + 3.0, 4) + 0.8 * fbm3(q * 7.0 + 1.0, 3) - 0.1) * smoothstep(2.2, 0.4, rn);
        float org = smoothstep(0.15, 0.6, uHI);
        float cov = max(core * org, mix(towers, max(bands, towers * 0.3 * (1.0 - uHI)), org));
        cov = clamp(cov * (0.8 + 0.2 * smoothstep(-0.2, 0.3, fbm3(q * 90.0, 3))) + 0.12 * fine * cov, 0.0, 1.0) * mix(1.0, eye, smoothstep(0.4, 0.8, uHI));
        // tops: domed over the core, highest in the eyewall, turrets of overshooting tops, cirrus streaks outward
        hgt = cov * (0.35 + 0.65 * core) + 0.9 * wall * smoothstep(0.4, 0.8, uHI) + 0.15 * ridge3(q * 120.0, 3) * core + 0.25 * ci * core + 0.2 * smoothstep(0.0, 1.0, bd) * (1.0 - core) + 0.04 * fine;
        hgt *= eye;
        return cov;
      }
      float cloudCov(vec3 p, float camD, out float hgt, out float core){
        // the general cloud field, wound into the storm near it and cleared by its subsidence ring
        float a = acos(clamp(dot(p, uHC), -1.0, 1.0)), g = exp(-pow(a / (uHR * 2.2), 2.0));
        vec3 pp = rotA(p, uHC, 2.5 * g * uHI);
        float la = asin(clamp(pp.y, -1.0, 1.0));
        float ang = 0.3 * sin(la * 5.0) + 0.25 * fbm3(pp * 1.2 + 3.0, 3);
        vec3 qq = vec3(pp.x * cos(ang) - pp.z * sin(ang), pp.y, pp.x * sin(ang) + pp.z * cos(ang)) * vec3(1.0, 1.9, 1.0);
        vec3 w = qq * 2.0 + 0.55 * vec3(fbm3(qq * 1.6 + uT * 0.004, 5), fbm3(qq * 1.6 + 5.0, 5), fbm3(qq * 1.6 + 9.0, 5));
        float n = fbm3(w * 1.7, 7) + 0.25 * fbm3(pp * 300.0 + w, 4) * smoothstep(0.3, 0.02, camD);
        float y = abs(pp.y);
        float fr = pow(1.0 - abs(fbm3(qq * 1.3 + w * 0.35 + 11.0, 5)), 5.0) * smoothstep(0.4, 0.6, y) * smoothstep(0.95, 0.8, y);
        float dry = exp(-pow((y - 0.45) / 0.13, 2.0));
        float base = smoothstep(0.05, 0.75, n * 0.85 + fr * 1.1 - dry * 0.22 + (uCloud - 0.5) * 0.6);
        base *= 1.0 - 0.97 * exp(-pow(a / (uHR * 2.3), 4.0)) * uHI;
        float sc = storm(p, camD, hgt, core);
        hgt = max(hgt, base * 0.3);
        return max(base, sc);
      }
      vec3 surface(vec3 p, vec3 V, float camD){
        float e = elev(p, camD);
        vec3 n = p; vec3 sx = dFdx(p), sy = dFdy(p);
        vec3 r1 = cross(sy, n), r2 = cross(n, sx); float dt = dot(sx, r1);
        float eh = max(e, 0.0);
        vec3 grad = sign(dt) * (dFdx(eh) * r1 + dFdy(eh) * r2);
        n = normalize(abs(dt) * n - grad * 0.0022);
        float land = smoothstep(-0.004, 0.004, e), y = abs(p.y);
        float depth = clamp(-e, 0.0, 1.0);
        vec3 sea = mix(vec3(0.015, 0.07, 0.1), vec3(0.003, 0.014, 0.045), smoothstep(0.0, 0.08, depth));
        sea = mix(sea, vec3(0.002, 0.012, 0.045), smoothstep(0.1, 0.4, depth));
        // sea-surface temperature look: warm tropics glow orange-red, a little patchy, cooler toward the poles
        float sst = smoothstep(0.55, 0.05, y + 0.12 * fbm3(p * 4.0 + 2.0, 4)) * (0.75 + 0.5 * fbm3(p * 9.0, 3));
        vec3 heat = mix(vec3(0.05, 0.03, 0.12), mix(vec3(0.5, 0.12, 0.03), vec3(0.75, 0.35, 0.05), smoothstep(0.6, 1.0, sst)), smoothstep(0.1, 0.5, sst));
        sea = mix(sea, heat, uWarm * 0.75);
        float dn = fbm3(p * 25.0 + 8.0, 5), rr = ridge3(p * 40.0 + 3.0, 5);
        vec3 rock = mix(vec3(0.17, 0.12, 0.08), vec3(0.3, 0.23, 0.15), smoothstep(-0.3, 0.5, dn));
        rock = mix(rock, vec3(0.5, 0.4, 0.28), smoothstep(0.55, 0.85, rr) * 0.6);
        float wet = 1.0 - smoothstep(0.0, 0.9, abs(y - 0.25) * 1.6 + smoothstep(0.0, 0.14, e) * 0.8 + 0.4 * fbm3(p * 5.0 + 2.0, 5));
        float gr = smoothstep(0.0, 0.25, 1.6 - (1.0 - wet) * 0.95 - 0.12 * dn - 1.0);
        vec3 green = mix(vec3(0.09, 0.15, 0.045), mix(vec3(0.02, 0.075, 0.025), vec3(0.05, 0.13, 0.035), smoothstep(-0.2, 0.4, dn)), smoothstep(0.35, 0.8, wet + 0.2 * dn));
        vec3 ground = mix(rock, green, gr * (1.0 - smoothstep(0.2, 0.34, e)));
        float ice = max(land * smoothstep(0.2, 0.42, e) * 0.9, smoothstep(0.86, 0.95, y + 0.05 * fbm3(p * 9.0, 3)));
        vec3 alb = mix(mix(sea, ground, land), vec3(0.85, 0.9, 0.97), ice);
        float L = max(dot(n, uSun), 0.0), wrap = smoothstep(-0.12, 0.25, dot(p, uSun));
        vec3 st = sunT(p); vec3 sunc = mix(vec3(dot(st, vec3(0.3, 0.4, 0.3))), st, 0.45) * vec3(0.95, 1.0, 1.06) * 1.9;
        vec3 col = alb * sunc * L + alb * vec3(0.05, 0.08, 0.13) * wrap + alb * vec3(0.006, 0.008, 0.014);
        col += sea * uWarm * 0.35 * wrap;                                      // the map tint reads on the dark ocean too
        vec3 Hh = normalize(uSun + V); float wat = (1.0 - land) * (1.0 - ice);
        float nh = max(dot(p, Hh), 0.0);
        col += vec3(1.0, 0.92, 0.8) * wat * (pow(nh, 900.0) * 1.6 + pow(nh, 200.0) * 0.04) * wrap * (1.0 - uWarm * 0.6);
        col += wat * vec3(0.25, 0.45, 0.8) * pow(1.0 - max(dot(p, V), 0.0), 5.0) * 0.35 * wrap;
        return col;
      }
      void main(){
        vec3 rd = normalize(vDir), ro = uCam;
        float camD = length(ro) - 1.0;
        vec2 g = sphT(ro, rd, 1.0), a = sphT(ro, rd, RA), cs = sphT(ro, rd, RC);
        float tg = g.x > 0.0 ? g.x : -1.0;
        vec3 col = vec3(0.0); float al = 0.0;
        if (tg > 0.0){
          vec3 p = normalize(ro + rd * tg);
          col = surface(p, -rd, camD); al = 1.0;
          float h1, c1;
          float sh = cloudCov(normalize(p + uSun * 0.0018), camD, h1, c1);
          col *= 1.0 - 0.7 * sh * smoothstep(0.0, 0.2, dot(p, uSun));
        }
        float tc = cs.x;
        if (tc > 0.0 && (tg < 0.0 || tc < tg)){
          vec3 p = normalize(ro + rd * tc);
          float hgt, core;
          float cv = cloudCov(p, camD, hgt, core);
          // tops lit by their slope: compare the relief one step toward the sun (no screen derivatives, no sparkle)
          vec3 sT = normalize(uSun - p * dot(uSun, p));
          float h2, c2; cloudCov(normalize(p + sT * 0.0025), camD, h2, c2);
          float ls = dot(p, uSun);
          float rg = mix(1.3, 2.6, smoothstep(0.3, 0.05, camD)), rc = mix(0.2, 0.3, smoothstep(0.3, 0.05, camD));
          float L = clamp(ls * 1.4 + clamp((h2 - hgt) * rg, -rc, rc), 0.0, 1.0);
          vec3 stc = sunT(p * RC); vec3 sunc = mix(vec3(dot(stc, vec3(0.3, 0.4, 0.3))), stc, 0.45) * 1.9;
          float th = fbm3(p * 160.0, 4);
          vec3 cc = sunc * (0.4 + 0.6 * L) * (0.82 + 0.18 * th) * (0.8 + 0.25 * hgt) + vec3(0.04, 0.06, 0.1) * smoothstep(-0.2, 0.2, ls);
          float ca = clamp(cv * (0.85 + 0.15 * th), 0.0, 1.0);
          col = mix(col, cc, ca); al = max(al, ca);
          // the eye seen in depth: the rim is at the cloud tops, the floor (low swirls) ~14 km below, so the floor
          // shows shifted away from the camera and the far inner wall shows between them, lit or in its own shade
          float ae = acos(clamp(dot(p, uHC), -1.0, 1.0));
          if (ae < uEye * 2.0 && uHI > 0.4){
            const float WH = 0.0022;
            vec3 d = uCam - uHC; float hz = max(dot(d, uHC), 1e-4);
            vec3 off = (d - uHC * hz) / hz * WH;
            vec3 pf = normalize(p - off);
            float af = acos(clamp(dot(pf, uHC), -1.0, 1.0));
            float rimN = uEye * (1.0 + 0.12 * fbm3(p * 2500.0, 3));
            float hole = 1.0 - smoothstep(rimN * 0.85, rimN * 1.05, ae);
            float fl = 1.0 - smoothstep(rimN * 0.7, rimN * 0.95, af);
            // floor: grey-white low cloud, shaded where the wall stands between it and the sun
            vec3 sT2 = uSun - pf * dot(uSun, pf);
            float tz = length(sT2) / max(dot(uSun, pf), 0.05);
            vec3 ps = normalize(pf + normalize(sT2 + 1e-6) * tz * WH);
            float lit = smoothstep(rimN * 0.95, rimN * 0.7, acos(clamp(dot(ps, uHC), -1.0, 1.0)));
            float sw = fbm3(rotA(pf, uHC, uSpin * 3.0) * 4000.0, 4);
            vec3 floorC = sunc * (0.35 + 0.45 * lit) * (0.75 + 0.3 * sw) * vec3(0.95, 0.97, 1.0);
            // wall: faces the eye's centre and leans out as it climbs; streaked by rising convection
            vec3 rad = normalize(p - uHC * dot(p, uHC));
            vec3 wn = normalize(-rad * 0.85 + p * 0.5);
            float wl = clamp(dot(wn, uSun) * 1.3 + 0.15, 0.0, 1.0);
            float stk = fbm3(vec3(atan(dot(p, cross(uHC, rad)), 1.0) * 0.0 + dot(rad, cross(uHC, vec3(0.0, 1.0, 0.0))) * 60.0, af * 900.0, ae * 3000.0), 3);
            vec3 wallC = sunc * (0.12 + 0.8 * wl) * (0.8 + 0.3 * stk);
            vec3 eyeC = mix(wallC, floorC, fl);
            col = mix(col, eyeC, hole); al = max(al, hole);
          }
        }
        if (a.y > 0.0){
          float t0 = max(a.x, 0.0), t1 = tg > 0.0 ? tg : a.y;
          float dt = (t1 - t0) / 16.0, tt = t0 + dt * hash12(gl_FragCoord.xy);
          vec3 tau = vec3(0.0), sR = vec3(0.0);
          for (int i = 0; i < 16; i++){
            vec3 q = ro + rd * tt;
            float d = exp(-(length(q) - 1.0) / HS) * dt;
            tau += (BR + BM) * d;
            sR += exp(-tau) * sunT(q) * d;
            tt += dt;
          }
          float mu = dot(rd, uSun), gg = 0.6;
          float pR = 0.0597 * (1.0 + mu * mu), pM = 0.0597 * 1.5 * (1.0 - gg * gg) * (1.0 + mu * mu) / ((2.0 + gg * gg) * pow(1.0 + gg * gg - 2.0 * gg * mu, 1.5));
          vec3 ext = exp(-tau);
          col = col * ext + (sR * BR * pR + sR * BM * pM) * (tg > 0.0 ? 5.5 : 9.0);
          al = tg > 0.0 ? 1.0 : max(al, 1.0 - dot(ext, vec3(0.333)));
        }
        // the thin blue rim round the lit limb
        float bq = -dot(ro, rd);
        vec3 pc = ro + rd * max(bq, 0.0);
        float hm = length(pc) - 1.0;
        float lit = 0.12 + 0.88 * smoothstep(-0.25, 0.35, dot(normalize(pc), uSun));
        float rim = (tg > 0.0 ? pow(1.0 - max(dot(normalize(ro + rd * tg), -rd), 0.0), 3.0) * 0.55 : exp(-max(hm, 0.0) / 0.0045) * 0.9 + exp(-max(hm, 0.0) / 0.02) * 0.12) * lit;
        col += vec3(0.28, 0.55, 1.25) * rim;
        al = max(al, clamp(rim, 0.0, 1.0));
        col = mix(col, uWC, uWhite); al = mix(al, 1.0, uWhite);
        gl_FragColor = vec4(col, al);
      }`,
  });
  const quad = fsQuad(mat); quad.renderOrder = 10;
  scene.add(quad);

  const pxScale = () => H / (2 * Math.tan((cam.fov * Math.PI) / 360));
  // pos, look in Earth radii; up defaults to the planet's north
  function setCam(pos, look, fv = cam.fov, up = [0, 1, 0]) {
    cam.position.set(...pos); cam.up.set(...up); cam.lookAt(...look);
    cam.fov = fv; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    const ty = Math.tan((fv * Math.PI) / 360);
    u.uTan.value.set(ty * cam.aspect, ty); u.uCamWorld.value.copy(cam.matrixWorld); u.uCam.value.copy(cam.position);
    stars.material.uniforms.uScale && (stars.material.uniforms.uScale.value = pxScale());
  }
  // a point on the sphere from latitude/longitude (degrees); longitude 0 faces +z
  const ll = (lat, lon) => {
    const a = (lat * Math.PI) / 180, b = (lon * Math.PI) / 180;
    return new THREE.Vector3(Math.cos(a) * Math.sin(b), Math.sin(a), Math.cos(a) * Math.cos(b));
  };
  function sync(t) { u.uT.value = t; stars.material.uniforms.uTime && (stars.material.uniforms.uTime.value = t); }
  function draw(renderer) {
    renderer.setClearColor(0x000000, 1); renderer.clear(true, true, true);
    renderer.render(scene, cam);
  }
  return { scene, cam, u, stars, setCam, ll, sync, draw, RE, dispose() { scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); } };
}
