// Ray-marched plumes in a unit box [-1,1]^3 (ground at y = -1): impact fireballs and steam columns.
// The ray stops at the planet surface (analytic sphere) so plumes behind the horizon lose their base naturally.
import * as THREE from 'three';
import { NOISE } from './glsl.js';

const geo = new THREE.BoxGeometry(2, 2, 2);

// kind 0 = impact fireball (self-lit, smoke), 1 = steam column (lit from below by lava, and by lightning)
export function plume({ kind = 0, seed = 0, steps = 48 }) {
  const u = {
    uAge: { value: 0 }, uSeed: { value: seed }, uCamO: { value: new THREE.Vector3() }, uPlanet: { value: new THREE.Vector3(0, -1e9, 0) }, uPR: { value: 1 },
    uGlow: { value: new THREE.Vector3(1.2, 0.3, 0.06) }, uFlash: { value: 0 }, uFlashD: { value: new THREE.Vector3(0, 1, 0) }, uAmb: { value: new THREE.Vector3(0.01, 0.01, 0.012) },
    uGain: { value: 1 }, uWind: { value: new THREE.Vector2(0.3, 0) }, uT: { value: 0 },
  };
  const m = new THREE.ShaderMaterial({
    uniforms: u, side: THREE.BackSide, transparent: true, depthWrite: false, depthTest: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    vertexShader: `varying vec3 vO; void main(){ vO = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `${NOISE}
      uniform float uAge, uSeed, uPR, uFlash, uGain, uT; uniform vec3 uCamO, uPlanet, uGlow, uFlashD, uAmb; uniform vec2 uWind; varying vec3 vO;
      float smin(float a, float b, float k){ float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }
      // density, temperature
      vec2 field(vec3 p){
        float a = uAge; vec3 s = vec3(uSeed * 7.1, uSeed * 3.3, uSeed * 5.7);
        float Y = p.y * 0.5 + 0.5;
${kind === 0 ? `
        float g = 1.0 - exp(-a * 0.75);
        // a dome of rock vapour that swells out of the crater, then slowly lifts and rolls
        float rb = 0.12 + 0.4 * (1.0 - exp(-a * 0.9));
        vec3 c = vec3(uWind.x * g * 0.3, -1.0 + rb * 0.55 + 0.5 * g * g, uWind.y * g * 0.3);
        vec3 q = p + rb * 0.55 * vec3(fbm3(p * 2.6 + s + vec3(0.0, -a * 0.5, 0.0), 4), fbm3(p * 2.6 + s + 4.0, 4), fbm3(p * 2.6 + s + 9.0, 4));
        vec3 dq = q - c; dq.y *= 1.35;
        float ball = length(dq) - rb;
        // the cap rolls: a torus round the fireball's waist
        vec2 tq = vec2(length(dq.xz) - rb * 0.8, dq.y + rb * 0.25); float tor = length(tq) - rb * 0.42;
        float stem = max(length(q.xz - c.xz * (Y * 0.9)) - (0.1 + 0.26 * g) * (1.25 - 0.6 * Y), q.y - c.y);
        float skirt = max(length(q.xz) - (0.15 + 0.7 * g), q.y + 1.0 - 0.12 * g * (1.0 - smoothstep(0.0, 0.9, length(q.xz))));
        float d = smin(smin(min(ball, tor), stem, 0.12), skirt, 0.15);
        float n = fbm3(q * 6.0 + s - vec3(0.0, a * 0.4, 0.0), 4);
        float den = smoothstep(0.06, -0.12, d + 0.1 * n) * (1.0 - smoothstep(0.75, 1.0, Y));
        float T = exp(-a * 0.42) * smoothstep(0.05, -0.35, ball + 0.12 * n) + 0.75 * exp(-a * 0.55) * smoothstep(0.0, -0.2, stem + 0.08 * n) * (1.0 - 0.6 * Y);
        return vec2(den * (0.9 + 0.3 * n), clamp(T, 0.0, 1.0));` : `
        float grow = clamp(a * 0.45, 0.0, 1.05);
        vec2 off = uWind * pow(Y, 1.6);
        vec3 q = p - vec3(off.x, 0.0, off.y);
        q += 0.18 * (0.3 + Y) * vec3(fbm3(p * 2.2 + s - vec3(0.0, uT * 0.35, 0.0), 3), 0.0, fbm3(p * 2.2 + s + 5.0 - vec3(0.0, uT * 0.35, 0.0), 3));
        float rc = 0.05 + 0.42 * pow(Y, 0.8);
        float d = length(q.xz) - rc;
        float n = fbm3(vec3(q.x * 4.0, q.y * 2.6 - uT * 0.9, q.z * 4.0) + s, 5);
        float den = smoothstep(0.08, -0.2, d + 0.22 * n) * smoothstep(grow + 0.02, grow - 0.25, Y) * smoothstep(1.0, 0.55, Y);
        return vec2(den * (0.55 + 0.6 * smoothstep(-0.3, 0.5, n)), 0.0);`}
      }
      // transmittance towards a light, a few coarse steps (self-shadowing gives the billows their shape)
      float lightT(vec3 p, vec3 L, float sig){
        float od = 0.0;
        for (int k = 1; k <= 5; k++){ vec3 q = p + L * (0.07 * float(k * k) * 0.5); od += field(q).x * 0.035 * float(k); }
        return exp(-od * sig);
      }
      void main(){
        vec3 ro = uCamO, rd = normalize(vO - uCamO);
        vec3 inv = 1.0 / rd, t0s = (vec3(-1.0) - ro) * inv, t1s = (vec3(1.0) - ro) * inv;
        vec3 tmin = min(t0s, t1s), tmax = max(t0s, t1s);
        float ta = max(max(max(tmin.x, tmin.y), tmin.z), 0.0), tb = min(min(tmax.x, tmax.y), tmax.z);
        // planet
        vec3 oc = ro - uPlanet; float b = dot(oc, rd), c = dot(oc, oc) - uPR * uPR, h = b * b - c;
        if (h > 0.0){ float tp = -b - sqrt(h); if (tp > 0.0) tb = min(tb, tp); }
        if (tb <= ta) discard;
        float dt = (tb - ta) / float(${steps});
        float t = ta + dt * hash12(gl_FragCoord.xy + uSeed * 13.0);
        vec3 col = vec3(0.0); float tr = 1.0;
        for (int i = 0; i < ${steps}; i++){
          vec3 p = ro + rd * t;
          vec2 f = field(p);
          if (f.x > 0.002){
            float Y = p.y * 0.5 + 0.5;
${kind === 0 ? `
            float sig = f.x * 9.0;
            float Tm = f.y;
            vec3 em = blackbody(0.25 + 0.75 * Tm) * (0.15 + 9.0 * Tm * Tm * Tm + 2.0 * Tm) * smoothstep(0.02, 0.25, Tm);
            float lb = lightT(p, vec3(0.0, -1.0, 0.0), 9.0);
            vec3 sm = vec3(0.16, 0.12, 0.1) * (uAmb * 20.0 + uGlow * (exp(-Y * 1.6) * 1.8 * lb + 0.08) + uFlash * 0.6);` : `
            float sig = f.x * 6.0;
            vec3 em = vec3(0.0);
            float lb = lightT(p, vec3(0.0, -1.0, 0.0), 6.0), lf = lightT(p, uFlashD, 6.0), lu = lightT(p, vec3(0.0, 1.0, 0.0), 6.0);
            float powder = 1.0 - exp(-f.x * 4.0);
            vec3 sm = vec3(0.8, 0.78, 0.76) * (uGlow * (exp(-Y * 2.2) * 1.3 + 0.1) * lb * (0.5 + 0.5 * powder)
              + uAmb * (0.4 + 0.6 * lu) + vec3(0.75, 0.82, 1.0) * uFlash * lf * (0.4 + 0.6 * powder));`}
            float a = 1.0 - exp(-sig * dt);
            col += tr * a * (sm + em / max(sig, 1e-3) * sig);
            tr *= 1.0 - a;
            if (tr < 0.01) break;
          }
          t += dt;
        }
        float al = (1.0 - tr) * uGain;
        gl_FragColor = vec4(col * uGain, al);
      }`,
  });
  const mesh = new THREE.Mesh(geo, m);
  mesh.frustumCulled = false;
  const inv = new THREE.Matrix4(), v = new THREE.Vector3();
  // call every frame after placing the mesh: camera + planet into box space
  mesh.userData.sync = (camera, planetC, planetR) => {
    mesh.updateMatrixWorld();
    inv.copy(mesh.matrixWorld).invert();
    u.uCamO.value.copy(camera.position).applyMatrix4(inv);
    u.uPlanet.value.copy(planetC).applyMatrix4(inv);
    u.uPR.value = planetR / mesh.scale.y;
  };
  mesh.userData.u = u;
  return mesh;
}
