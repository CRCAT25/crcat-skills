// Film timeline in film seconds (before the speed-up in episode.json). Each scene lives in scenes/<id>.js and gets its
// local time. Keep this list in play order: render_chunks.sh and assemble.sh concatenate the chunks as listed.
export const SCENES = [
  { id: 's1_mau', t0: 0, t1: 20 },
];
