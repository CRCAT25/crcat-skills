// Film timeline in film seconds (before the speed-up in episode.json). Each scene lives in scenes/<id>.js and gets its
// local time. Keep this list in play order: render_chunks.sh and assemble.sh concatenate the chunks as listed.
// xf: the scene starts xf seconds early and dissolves in over the previous one (outgoing pushes in, incoming settles).
// tx: { c, a } adds a colour veil at the dissolve midpoint (light cloud, grey rain, warm haze) so the cut reads as one move.
export const SCENES = [
  { id: 's1_mau', t0: 0, t1: 20 },
  // { id: 's2_next', t0: 20, t1: 45, xf: 1.5, tx: { c: '#e4eaf0', a: 0.9 } },
];

// Holds give the narration more room without re-staging a scene: [a, d] adds d film seconds at film time a (scene
// times above). Over 2.5·d seconds the picture eases into slow motion (down to 0.4×) and back, so nothing freezes.
// Keep this line plain JSON: audio/episode.py reads it too.
export const HOLDS = [];
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
