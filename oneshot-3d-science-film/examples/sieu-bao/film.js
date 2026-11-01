// Film timeline in film seconds (before the speed-up in episode.json). Each scene lives in scenes/<id>.js and gets its
// local time. Keep this list in play order: render_chunks.sh and assemble.sh concatenate the chunks as listed.
export const SCENES = [
  { id: 's01_mo', t0: 0, t1: 9 },
  { id: 's02_bien', t0: 9, t1: 30, xf: 1.0 },
  { id: 's03_hinhthanh', t0: 30, t1: 65, xf: 1.5, tx: { c: '#e4eaf0', a: 0.9 } },
  { id: 's04_xoay', t0: 65, t1: 90, xf: 1.5 },
  { id: 's04b_mat', t0: 90, t1: 102, xf: 1.5 },
  { id: 's05_thanhbao', t0: 102, t1: 120, xf: 1.5, tx: { c: '#a7afb6', a: 0.9 } },
  { id: 's05b_lang', t0: 120, t1: 142, xf: 1.5 },
  { id: 's06_nuocdang', t0: 142, t1: 187, xf: 1.5 },
  { id: 's07_matbao', t0: 187, t1: 217, xf: 1.5 },
  { id: 's08_thanhsau', t0: 217, t1: 242, xf: 1.5, tx: { c: '#4a525a', a: 0.7 } },
  { id: 's09_binhminh', t0: 242, t1: 270, xf: 1.5 },
  { id: 's10_ket', t0: 270, t1: 290, xf: 1.5, tx: { c: '#ebe5da', a: 0.9 } },
];

// Holds give the narration more room without re-staging a scene: [a, d] adds d film seconds at film time a (scene
// times above). Over 2.5·d seconds the picture eases into slow motion (down to 0.4×) and back, so nothing freezes.
// Keep this line plain JSON: audio/episode.py reads it too.
export const HOLDS = [[21.5, 4.0], [80, 2.9], [94.3, 4.0], [272.6, 2.9]];
const S = (x) => x * x * (3 - 2 * x);
// timeline time (what is rendered and heard) -> scene time (the times above)
export function unhold(n) {
  let off = 0;
  for (const [a, d] of HOLDS) {
    const s = a + off, L = 2.5 * d;
    if (n < s) break;
    if (n < s + L) return n - off - d * S((n - s) / L);
    off += d;
  }
  return n - off;
}
export const END = SCENES[SCENES.length - 1].t1 + HOLDS.reduce((s, h) => s + h[1], 0);
