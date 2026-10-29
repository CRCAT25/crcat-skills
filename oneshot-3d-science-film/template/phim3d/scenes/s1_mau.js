// Scene template: a slow push in on a lit planet through drifting dust. Copy it for each new scene.
// build() runs once; update(tl) and grade(tl) run every frame with the scene's local time tl (film seconds).
import { keys, ease, rng, softPoints, rockGeo, rockMaterial } from '../lib/kit.js';

export async function build({ THREE, W, H, dur }) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, W / H, 0.01, 1000);

  const sun = new THREE.DirectionalLight(0xfff1dd, 3.2);
  sun.position.set(5, 2, 4);
  scene.add(sun, new THREE.AmbientLight(0x223344, 0.08));

  const planet = new THREE.Mesh(rockGeo({ radius: 1, detail: 6, seed: 3, amp: 0.04 }), rockMaterial({ tint: [0.6, 0.55, 0.5] }));
  scene.add(planet);

  // seeded: separately rendered chunks must draw the same dust
  const r = rng(11);
  const dust = softPoints({ count: 1500, place: () => ({
    p: [(r() - 0.5) * 20, (r() - 0.5) * 12, -r() * 15], s: 0.01 + r() * 0.03, c: [0.9, 0.8, 0.7] }) });
  scene.add(dust);

  const update = (tl) => {
    camera.position.set(0, keys([[0, 0.3], [dur, 0]], tl), keys([[0, 6], [dur, 3]], tl, ease.inOut));
    camera.lookAt(0, 0, 0);
    planet.rotation.y = tl * 0.03;
  };
  const grade = (tl) => ({ exposure: keys([[0, 0], [2, 1]], tl, ease.out), bloom: 0.5 });
  const dispose = () => scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); });
  return { scene, camera, update, grade, dispose };
}
