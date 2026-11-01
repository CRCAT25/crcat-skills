// Storm layers for the coast and ocean worlds: wind-driven rain (and spume drops) as motion-blurred streaks in a box
// that travels with the camera, so there is always weather around the lens without filling the whole sky with
// geometry. Streak length is the distance a drop moves during the shutter, so in a gale the rain runs sideways.
import * as THREE from 'three';
import { rng } from './kit.js';

export function makeRain(scene, { count = 9000, box = [70, 34, 70], y0 = 0, seed = 3, color = [0.75, 0.8, 0.85], alpha = 0.22, width = 1, shutter = 0.022, low = 0, near = 3 } = {}) {
  const r = rng(seed);
  const pos = new Float32Array(count * 2 * 3), end = new Float32Array(count * 2), sd = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    const a = r(), b = r(), c = r(), s = r();
    for (let k = 0; k < 2; k++) { pos.set([a, b, c], (i * 2 + k) * 3); end[i * 2 + k] = k; sd[i * 2 + k] = s; }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aEnd', new THREE.BufferAttribute(end, 1));
  g.setAttribute('aSd', new THREE.BufferAttribute(sd, 1));
  const u = {
    uT: { value: 0 }, uCen: { value: new THREE.Vector3() }, uBox: { value: new THREE.Vector3(...box) },
    uVel: { value: new THREE.Vector3(30, -9, 0) }, uShut: { value: shutter }, uA: { value: alpha }, uC: { value: new THREE.Vector3(...color) },
    uNear: { value: near }, uY0: { value: y0 }, uFwd: { value: new THREE.Vector3(0, 0, 1) }, uLow: { value: low }, uCam: { value: new THREE.Vector3() },
  };
  const m = new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      attribute float aEnd, aSd; uniform float uT, uShut, uY0, uLow, uNear; uniform vec3 uCen, uBox, uVel, uCam, uFwd; varying float vA;
      void main(){
        vec3 v = uVel * (0.75 + 0.5 * aSd);
        // wrap each drop inside the box around the camera; the box scrolls with the drop velocity
        vec3 q = fract(position + v * uT / uBox) - 0.5;
        vec3 p = uCen + q * uBox;
        // low mode (spume): drops hug the sea surface, thinning with height
        if (uLow > 0.0) p.y = uY0 + pow(position.y, 2.5) * uBox.y;
        // both ends must sit in front of the lens, or the projected line smears across the frame
        float z0 = dot(p - uCam, uFwd), z1 = dot(p - v * uShut - uCam, uFwd);
        p -= v * uShut * aEnd;
        float d = length(p - uCam);
        if (min(z0, z1) < uNear) d = 0.0;
        vA = (1.0 - aEnd * 0.85) * smoothstep(uNear, uNear * 3.0, d) * (1.0 - smoothstep(uBox.x * 0.25, uBox.x * 0.5, d));
        gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: /* glsl */ `uniform float uA; uniform vec3 uC; varying float vA; void main(){ gl_FragColor = vec4(uC * uA * vA, 1.0); }`,
  });
  const ls = new THREE.LineSegments(g, m); ls.frustumCulled = false; ls.renderOrder = 5;
  scene.add(ls);
  // cam: the camera; vel: [x, y, z] m/s; light: overall brightness multiplier
  const update = (t, cam, { vel, light = 1, y0: yy } = {}) => {
    u.uT.value = t; u.uCam.value.copy(cam.position);
    const f = new THREE.Vector3(); cam.getWorldDirection(f);
    u.uFwd.value.copy(f); u.uCen.value.copy(cam.position).addScaledVector(f, box[0] * 0.3);
    if (vel) u.uVel.value.set(...vel);
    if (yy !== undefined) u.uY0.value = yy;
    u.uA.value = alpha * light;
  };
  return { mesh: ls, u, update };
}
