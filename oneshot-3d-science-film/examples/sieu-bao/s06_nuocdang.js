// Scene 6: the storm surge. The sea rises steadily over the beach, the boats, then the village floor, metres deep,
// with storm waves riding on top. (Simulation: a +5 m surge, in the range measured at Tacloban during Haiyan.)
import { makeCoast, coastGrade, track } from '../lib/coast.js';
import { addCoastProps } from '../lib/coastProps.js';
import { stormCoast } from '../lib/stormcoast.js';
import { flyDebris } from '../lib/debris.js';
import { keys, ease } from '../lib/kit.js';

export const surge = (T) => keys([[0, 1.4], [40, 5.4]], T, ease.inOut);
export async function build({ W, H, dur }) {
  const C = makeCoast({ W, H, fov: 46 });
  const P = addCoastProps(C, { palms: 420, debris: 36 });
  const S = stormCoast(C, P);
  const wd = [0.9, 0.45];
  const path = track([[0, -200, 16, -30, -80, 2, 70], [dur * 0.5, -185, 12, -10, -60, 2, 75], [dur, -170, 10, 0, -40, 3, 80]]);
  const update = (tl) => {
    const [x, y, z, lx, ly, lz] = path(tl);
    C.setCam([x, y, z], [lx, ly, lz], 46, 0.02 * Math.sin(tl * 2.6));
    C.setSea({ level: surge(tl), front: -1e5, boreH: 0, back: 0 });
    C.aimShadow(x + 30, z + 60, 180);
    S.set({ k: 0.95, t: tl, wd });
    flyDebris(P, tl, { cam: [x, y, z], wd, speed: 30, spread: 90, y0: surge(tl) + 0.3, lift: 3 });
    C.sync(tl + 90);
  };
  const grade = () => coastGrade({ exposure: 1.0, sat: 0.85, contrast: 1.1 });
  return { scene: C.scene, camera: C.cam, mb: true, update, grade, draw: C.draw, dispose: C.dispose };
}
