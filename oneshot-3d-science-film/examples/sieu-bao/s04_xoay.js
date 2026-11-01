// Scene 4: the storm explodes into a giant: the spiral winds tight and the eye shrinks to a pinhole (Patricia 2015).
import { makeOrbit } from '../lib/orbit.js';
import { coastGrade } from '../lib/coast.js';
import { keys, ease } from '../lib/kit.js';

export async function build({ W, H, dur }) {
  const O = makeOrbit({ W, H, fov: 36 });
  const c = O.ll(14, -12); O.u.uHC.value.copy(c);
  const update = (tl) => {
    const k = tl / dur;
    O.u.uHI.value = keys([[0, 0.62], [dur * 0.6, 1]], tl, ease.inOut);
    O.u.uSpin.value = (tl + 35) * 0.04;
    O.u.uEye.value = keys([[0, 0.008], [dur, 0.0032]], tl, ease.inOut);
    const p = O.ll(7 - 3 * k, -19 - 3 * k).multiplyScalar(1 + keys([[0, 2.0], [dur, 0.75]], tl, ease.inOut));
    O.setCam(p.toArray(), c.toArray(), 36);
    O.sync(tl + 35);
  };
  const grade = () => coastGrade({ exposure: 1.0, vignette: 0.3 });
  return { scene: O.scene, camera: O.cam, update, grade, draw: O.draw, dispose: O.dispose };
}
