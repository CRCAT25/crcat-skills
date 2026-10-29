// Scene 3 — out of the orange light we skim a magma ocean, pull back to reveal the molten proto-Earth,
// and Theia slides in from the dark and strikes it at a grazing angle. A curtain of incandescent rock
// sprays into space and starts to curl around the planet (it becomes the ring of scene 4).
import { NOISE } from '../lib/glsl.js';
import { magmaMaterial } from '../lib/magma.js';
import { keys, ease, smooth, rng, softPoints, rockGeo, rockMaterial, clamp, pxf } from '../lib/kit.js';

export async function build({ THREE, W, H }) {
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(38, W / H, 0.001, 5000);
  const r = rng(31);
  const pxScale = H / (2 * Math.tan((cam.fov * Math.PI) / 360));
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  const SUN = V(-0.62, 0.32, 0.72).normalize();
  const IMP = V(0.86, 0.22, 0.46).normalize();                       // impact site (planet object space)
  const TRAV = V(-1, -0.2, 0.15); TRAV.addScaledVector(IMP, -TRAV.dot(IMP)).normalize(); // Theia's tangent heading
  const T_IMP = 8.2;

  // ---------- stars + distant Sun ----------
  const stars = softPoints({
    count: 6000, sizeAtten: false, place: () => {
      const u = r() * 2 - 1, a = r() * Math.PI * 2, s = Math.sqrt(1 - u * u), m = Math.pow(r(), 6);
      return { p: [s * Math.cos(a) * 3000, u * 3000, s * Math.sin(a) * 3000], s: 1.1 + 3 * m, c: [1, 0.93, 0.88].map((x) => x * (0.15 + 1.6 * m)) };
    },
  });
  scene.add(stars);
  const sunP = softPoints({ count: 3, place: (i) => ({ p: SUN.clone().multiplyScalar(900).toArray(), s: [9, 40, 140][i], c: [[6, 5, 4], [1.2, 0.8, 0.5], [0.15, 0.09, 0.05]][i] }) });
  sunP.material.uniforms.uScale.value = pxScale; sunP.material.uniforms.uMinPx.value = 0;
  scene.add(sunP);

  // ---------- the magma planet ----------
  const pu = { uT: { value: 0 }, uSun: { value: SUN }, uImp: { value: IMP }, uAge: { value: -1 }, uCamO: { value: new THREE.Vector3() } };
  const planetMat = magmaMaterial(pu);
  const planet = new THREE.Mesh(new THREE.SphereGeometry(1, 512, 256), planetMat);
  scene.add(planet);
  // thin glowing haze shell
  const atm = new THREE.Mesh(new THREE.SphereGeometry(1.045, 128, 64), new THREE.ShaderMaterial({
    uniforms: { uCamO: pu.uCamO, uSun: pu.uSun },
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform vec3 uCamO, uSun; varying vec3 vW;
      void main(){ vec3 n = normalize(vW), V = normalize(uCamO - vW); float mu = abs(dot(n, V));
        float g = pow(1.0 - mu, 5.0) * smoothstep(0.0, 0.25, mu);
        vec3 c = mix(vec3(0.8, 0.22, 0.05), vec3(1.0, 0.6, 0.35), max(dot(n, uSun), 0.0)) * g * 0.35;
        gl_FragColor = vec4(c, 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
  }));
  scene.add(atm);

  // ---------- Theia ----------
  const light = new THREE.DirectionalLight(0xfff0dd, 2.6); light.position.copy(SUN).multiplyScalar(10); scene.add(light);
  const bounce = new THREE.PointLight(0xff6020, 3, 0, 2); scene.add(bounce);       // glow of the magma ocean on Theia's belly
  scene.add(new THREE.AmbientLight(0x221418, 0.15));
  const theia = new THREE.Mesh(rockGeo({ radius: 1, detail: 7, seed: 77, amp: 0.1, freq: 1.3, oct: 6 }), rockMaterial({ heat: 0.15, roughness: 0.75 }));
  const TR = 0.42;
  scene.add(theia);
  const theiaHit = IMP.clone().multiplyScalar(1 + TR * 1.04);   // surfaces just touch at T_IMP (no sinking in before the blast)

  // ---------- ejecta: incandescent spray that cools and starts to orbit ----------
  const EN = 120000, eg = new THREE.BufferGeometry(), ev = new Float32Array(EN * 4), ex = new Float32Array(EN * 4);
  const tan2 = new THREE.Vector3().crossVectors(IMP, TRAV).normalize();
  for (let i = 0; i < EN; i++) {
    const sp = 0.05 + Math.pow(r(), 2.2) * 0.5;
    const d = IMP.clone().multiplyScalar(0.55 + r() * 0.5).addScaledVector(TRAV, 0.4 + r() * 0.9).addScaledVector(tan2, (r() - 0.5) * 1.1)
      .add(V(r() - 0.5, r() - 0.5, r() - 0.5).multiplyScalar(0.35)).normalize();
    const delay = Math.pow(r(), 2) * 1.2;
    ev.set([d.x * sp, d.y * sp, d.z * sp, delay], i * 4);
    ex.set([0.0025 + Math.pow(r(), 4) * 0.02, 0.15 + r() * 0.35, r(), r()], i * 4);   // size, cooling rate, tint, spare
  }
  eg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(EN * 3), 3));
  eg.setAttribute('vel', new THREE.BufferAttribute(ev, 4));
  eg.setAttribute('ex', new THREE.BufferAttribute(ex, 4));
  const ejecta = new THREE.Points(eg, new THREE.ShaderMaterial({
    uniforms: { uAge: { value: -1 }, uO: { value: IMP.clone() }, uScale: { value: pxScale }, uSun: { value: SUN } },
    vertexShader: /* glsl */ `${NOISE}
      attribute vec4 vel, ex; uniform float uAge, uScale; uniform vec3 uO, uSun; varying vec3 vC;
      void main(){
        float a = max(uAge - vel.w, 0.0);
        vec3 p = uO + vel.xyz * a;
        p -= normalize(p) * 0.02 * a * a;                      // gravity pulls the slow ones back
        float rr = length(p);
        float ang = 0.5 * a / pow(max(rr, 1.0), 1.5);          // the rest are swept into orbit
        float c = cos(ang), s = sin(ang); p.xz = mat2(c, -s, s, c) * p.xz;
        vec4 mv = viewMatrix * vec4(p, 1.0); float z = -mv.z;
        const float PXF = ${pxf().toFixed(4)};
        float px = ex.x * uScale / z, px2 = max(px, PXF);
        float cool = exp(-a * ex.y);
        vec3 hot = blackbody(clamp(cool * 0.85, 0.0, 1.0)) * (0.15 + 0.5 * cool) * smoothstep(0.0, 0.12, a);
        vec3 dust = vec3(0.22, 0.19, 0.17) * (0.2 + 0.8 * max(dot(normalize(p), uSun), 0.0)) * 2.0;
        float alive = step(0.0, uAge - vel.w) * smoothstep(0.98, 1.02, rr) * smoothstep(0.0, 0.08, a + 0.01);
        vC = (hot + dust) * alive * min(1.0, px * px / (px2 * px2) + 0.2 / (PXF * PXF));
        gl_PointSize = min(px2, 48.0 * PXF); gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `varying vec3 vC; void main(){ vec2 d = gl_PointCoord * 2.0 - 1.0; float r = dot(d, d); if (r > 1.0) discard;
      gl_FragColor = vec4(vC * exp(-r * 2.8), 1.0); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  ejecta.frustumCulled = false;
  scene.add(ejecta);
  const flashP = softPoints({ count: 2, place: (i) => ({ p: IMP.clone().multiplyScalar(1.02).toArray(), s: [0.12, 0.4][i], c: [[4, 3, 2], [2.0, 0.8, 0.25], [0.4, 0.14, 0.04]][i] }) });
  flashP.material.uniforms.uScale.value = pxScale; flashP.material.uniforms.uMinPx.value = 0;
  flashP.material.depthTest = false;   // the contact flash blazes around Theia's rim the instant they touch
  scene.add(flashP);

  // ---------- camera: skim the magma, pull back, witness the hit, drift out with the spray ----------
  const S0 = V(0.1, 0.36, 1).normalize();              // start point on the surface (sunlit-terminator zone)
  const head0 = V(1, 0.05, -0.1); head0.addScaledVector(S0, -head0.dot(S0)).normalize();
  const D1 = V(0.18, 0.28, 1).normalize();
  const tmp = new THREE.Vector3(), tg = new THREE.Vector3();

  function update(t) {
    pu.uT.value = t;
    const k = t - T_IMP;
    // camera
    const pull = ease.inOut(clamp(t / 6.5));
    const dist = 1.012 * Math.pow(3.6 / 1.012, pull) * (1 + 0.25 * ease.inOut(clamp((t - 10.5) / 3)));
    const dir = tmp.copy(S0).lerp(D1, ease.inOut(clamp(t / 6))).normalize();
    // swing a little toward the spray at the end
    dir.applyAxisAngle(V(0, 1, 0), 0.32 * ease.inOut(clamp((t - 10) / 6)));
    cam.position.copy(dir).multiplyScalar(dist);
    const lookNear = S0.clone().multiplyScalar(1.0).addScaledVector(head0, 0.25).addScaledVector(S0, -0.004);
    const lookFar = V(0.12, 0.02, 0).add(IMP.clone().multiplyScalar(0.25 * smooth(5, 9, t)));
    tg.copy(lookNear).lerp(lookFar, ease.inOut(clamp((t - 0.8) / 5.2)));
    tg.addScaledVector(TRAV, 0.9 * ease.inOut(clamp((t - 10) / 6)));
    cam.lookAt(tg);
    if (k > 0 && k < 2.5) { const s = 0.006 * Math.exp(-k * 1.6) * dist; cam.position.add(V(Math.sin(t * 61) * s, Math.sin(t * 47 + 1) * s, Math.sin(t * 53 + 2) * s)); }
    cam.updateMatrixWorld();
    pu.uCamO.value.copy(cam.position);
    // Theia: approaches along a gentle arc, slams in, sinks and is swallowed by the flash
    const app = Math.max(-k, 0);
    const pos = theiaHit.clone().addScaledVector(TRAV, -app * 0.5).addScaledVector(IMP, app * app * 0.012);
    let sc = TR;
    if (k > 0) { pos.addScaledVector(TRAV, Math.min(k, 3) * 0.22).addScaledVector(IMP, -Math.min(k, 3) * 0.5); sc = TR * (1 - 0.75 * smooth(0, 2.0, k)); }
    theia.position.copy(pos); theia.scale.setScalar(sc);
    theia.rotation.set(0.3, t * 0.18, 0.2);
    theia.visible = k < 3;
    theia.material.userData.uHeat.value = 0.15 + 0.5 * smooth(-3, 0, k) + 0.6 * smooth(0, 0.4, k);
    bounce.position.copy(IMP).multiplyScalar(1.05);
    bounce.intensity = 1.5 + 30 * (k > 0 ? Math.exp(-k * 1.2) : 0);
    pu.uAge.value = k;
    ejecta.material.uniforms.uAge.value = k;
    flashP.material.uniforms.uGain.value = k > 0 ? Math.exp(-k * 2.2) * 0.9 : 0;
    stars.material.uniforms.uTime.value = t;
  }

  const grade = (t) => {
    const k = t - T_IMP;
    return {
      exposure: 1.0,
      flash: k < 0 ? [1.0, 0.22, 0.03, keys([[0, 0.22], [0.7, 0]], t, ease.out)] : [1.0, 0.5, 0.15, keys([[0, 0.018], [0.15, 0]], k, ease.out)],
      bloom: keys([[0, 0.7], [T_IMP, 0.5], [T_IMP + 0.3, 0.55], [T_IMP + 2, 0.45]], t),
      bloomThreshold: 0.8, bloomRadius: 0.25, hdrMax: 4, vignette: 0.45, sat: 1.1, contrast: 1.08, chroma: 0.001, lift: [0.006, 0.003, 0.01],
    };
  };

  return { scene, camera: cam, update, grade, dispose() { scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); } };
}
