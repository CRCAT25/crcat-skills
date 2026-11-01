// Wreckage carried by the gale: the props' debris pieces streak downwind through a box around the camera, tumbling,
// each on its own looping path so a still frame always has a few in view.
import { rng } from './kit.js';

export function flyDebris(P, t, { cam, wd, speed = 50, spread = 60, y0 = 1, lift = 10, seed = 7, clear = 32 }) {
  const n = Math.hypot(wd[0], wd[1]), dx = wd[0] / n, dz = wd[1] / n;
  const r = rng(seed), J = [];
  for (let i = 0; i < 64; i++) J.push([r(), r(), r(), r()]);
  P.drift((p) => {
    const [a, b, c, d] = J[p.i % 64];
    const L = spread * 3, sp = speed * (0.6 + 0.6 * a);
    const s = ((t * sp + b * L) % L) - L / 2;                       // along the wind, looping
    const side = Math.sign(c - 0.5) * (clear + Math.abs(c - 0.5) * spread);  // across the wind, never grazing the lens
    const x = cam[0] + 30 * dx + dx * s - dz * side, z = cam[2] + 30 * dz + dz * s + dx * side;
    const y = y0 + d * lift + 1.5 * Math.sin(t * 2 + p.ph);
    // fast, uneven tumble from a random starting attitude so no sheet ever reads as a flat static card
    return { x, y, z, ry: t * (4 + 6 * a) + p.ph * 3, tx: t * (6 + 8 * c) + d * 6.28, tz: t * (3 + 5 * d) + b * 6.28 };
  });
}
