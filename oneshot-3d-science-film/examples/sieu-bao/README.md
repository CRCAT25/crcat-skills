# Episode 3 example files

From "Nếu siêu bão mạnh nhất lịch sử đổ bộ thì sao?" (youtu.be/po7r7N-clMI, 4:24, 1080p60). Read them as models;
they do not run on their own inside this folder. This is the most complete episode so far: holds, linked
transitions, motion blur, a narration-cue HUD and a per-scene music score.

- `film.js`: the 12-scene timeline with `xf`/`tx` transitions and `HOLDS` (slow-downs added after the voice was
  re-written, so longer sentences fit without re-authoring scenes).
- `s04_xoay.js`: the storm seen from orbit (`lib/orbit.js` globe + spiral storm: 5 tightly wound arms, wide bands,
  big central dense overcast; an earlier 3-arm version looked like a throwing star).
- `s06_nuocdang.js`: the storm surge flooding the village (`lib/coast.js` ray-marched bay + `lib/coastProps.js`
  palms/huts/boats + `lib/stormcoast.js` gale look + `lib/debris.js` flying wreckage), `mb: true` for motion blur.
- `lib/`: the coast, ocean, storm and orbit worlds these scenes need. Copy them into `phim3d/lib/` next to the
  template's `kit.js`, `glsl.js` and `post.js` (identical to the template's). They reuse well for any sea, coast or
  weather episode (Tập 2 tsunami used the same coast).
- `hud.js`: all 22 narration cues of the episode (thermometers, gauges, the Natural Earth world map with the
  tropics band, the satellite-like cloud spiral, drawn debris, 100 person icons). Uses `../land110.js`
  (Natural Earth 1:110m, public domain), which ships in `template/phim3d/`.
- `mix.py`: SFX cue list (gale, rain, thunder, surf, dawn) placed with `place()` so cues follow the holds.
- `episode.json`: `score` (music changing per scene), `spell` (spoken numbers → digits in captions), `nudge`.
- `script_phim3d.md`, `lines.json`: narration (31 lines, ~1,900 characters) in final time.
- `sources.md`: fact table (Patricia 345 km/h, Haiyan surge, Rappaport 2014, AR6). `publish.md`: the package.
