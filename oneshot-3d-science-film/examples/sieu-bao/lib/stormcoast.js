// The village coast under a hurricane: one call sets the storm look on a coast world (sky, light, haze, sea state,
// palms in the gale, rain and spume around the camera). k = 0 calm tropical day .. 1 eyewall.
import { makeRain } from './storm.js';
import { lerp, clamp } from './kit.js';

const mix3 = (a, b, k) => a.map((v, i) => lerp(v, b[i], k));
export function stormCoast(C, P, { rain = 14000 } = {}) {
  const R = makeRain(C.scene, { count: rain, alpha: 0.08, shutter: 0.014 });
  const S = makeRain(C.scene, { count: 5000, box: [80, 7, 80], low: 1, alpha: 0.14, color: [0.85, 0.88, 0.9], shutter: 0.02, seed: 9, near: 10 });
  const day = { sun: [3.0, 2.64, 2.16], zen: [0.05, 0.17, 0.5], hor: [0.5, 0.66, 0.83], amb: [0.32, 0.42, 0.6], fog: [0.6, 0.7, 0.82] };
  const gale = { sun: [0.35, 0.37, 0.4], zen: [0.1, 0.11, 0.12], hor: [0.24, 0.26, 0.28], amb: [0.26, 0.29, 0.32], fog: [0.2, 0.22, 0.24] };
  // o: { sky (storm ceiling 0..1, defaults from k), k (storm 0..1), wind (0..1 visual gale), wd [x, z], rain (0..1), spume (0..1), fogK, t, light }
  const set = (o) => {
    const k = clamp(o.k), u = C.u, w = o.wind ?? k;
    u.uStorm.value = o.sky ?? clamp(k * 1.4);
    u.uSunC.value.set(...mix3(day.sun, gale.sun, k));
    u.uZen.value.set(...mix3(day.zen, gale.zen, k)); u.uHor.value.set(...mix3(day.hor, gale.hor, k));
    u.uAmb.value.set(...mix3(day.amb, gale.amb, k)); u.uFogC.value.set(...mix3(day.fog, gale.fog, k));
    u.uStormC.value.set(...gale.hor.map((v) => v * 0.75 * (o.light ?? 1)));
    u.uFogK.value = o.fogK ?? lerp(1, 14, k * k);
    u.uSwell.value = 1 + 2.5 * w;
    u.uSpume.value = o.spume ?? w;
    u.uScud.value = 0.3 + 2.5 * w;
    const wd = o.wd || [0.6, 0.8], n = Math.hypot(wd[0], wd[1]);
    u.uWd.value.set(wd[0] / n, wd[1] / n);
    if (P) P.gale(w, [wd[0] / n, wd[1] / n]);
    const sp = 10 + 80 * w;
    const rk = o.rain ?? k;
    R.update(o.t, C.cam, { vel: [wd[0] / n * sp, -9 - 6 * w, wd[1] / n * sp], light: rk * (o.light ?? 1) });
    S.update(o.t, C.cam, { vel: [wd[0] / n * sp * 1.1, -1, wd[1] / n * sp * 1.1], light: clamp((o.spume ?? w) * 1.3 - 0.3) * (o.light ?? 1), y0: C.u.uSea.value.x + 0.3 });
    R.mesh.visible = rk > 0.01; S.mesh.visible = (o.spume ?? w) > 0.25;
  };
  return { set, rain: R, spume: S };
}
