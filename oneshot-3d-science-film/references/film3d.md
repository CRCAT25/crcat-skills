# 3D film pipeline (three.js → headless Chrome → ffmpeg)

Built for Episode 1 ("Trái Đất ra đời") and extended through Episode 3 ("Siêu bão": holds, linked transitions,
motion blur, the HUD layer). The template in `template/` is that engine with the episode-specific parts removed;
`scripts/init_film.py` scaffolds it.

## Layout of an episode

```
<slug>/
  episode.json          speed, music track + loop body or per-scene score, dips, voice nudges/take2, spell map
  render_chunks.sh      draft|final [from to]  → exports/chunks-*/c_NNN.mp4 (+ .done markers)
  assemble.sh           draft|final [audio.wav] [out.mp4]  → concat copy + mux
  phim3d/
    film.js             SCENES = [{id, t0, t1, xf?, tx?}] in film seconds, HOLDS, unhold(), END
    scenes/<id>.js      one module per scene
    lib/kit.js          clamp, lerp, smooth, ease.{inOut,out,in,expo,sine}, keys([[t,v]…], t, ease), pxf(), rng(seed),
                        softPoints({count, place(i)→{p,s,c}}), vnoise3, rockGeo({radius, detail, seed, amp, freq, stretch, oct}),
                        fsQuad(mat), rockMaterial({frost, scale, heat, tint, roughness}), NOISE
    lib/glsl.js         NOISE (hash, snoise, fbm3, ridge3, voronoi3), RAY_VS
    lib/post.js         makePost(): HDR half-float → soft ceiling → UnrealBloom → GRADE
    lib/magma.js        magmaMaterial (lava sea), lib/plume.js plume({kind 0 fireball | 1 steam}) ray-marched
    page.html           loads film.js, keeps one scene alive (two during a transition), window.frame(t) → JPEG
    render.mjs          playwright-core + Chrome (--use-angle=metal), pipes frames to ffmpeg (--film, --mb, --sh)
    hud.js / hud.html   narration cues drawn on a 2D canvas in final time; land110.js = Natural Earth land
    hud.mjs             overlays hud.js on an already rendered video (or writes --stills)
    sheet.sh/sheet.py   contact sheet of stills (2 per row)
  audio/  captions/  review/serve.py  exports/  sources.md
```

## Scene contract

`export async function build({THREE, renderer, W, H, dur})` returns
`{scene, camera, update(tl), grade?(tl), draw?(renderer), dispose?()}`. `tl` is local film time.

`grade(tl)` overrides any of: `exposure, contrast, sat, lift[3], gain[3], vignette, chroma, grain, flash[r,g,b,a],
bloom, bloomRadius, bloomThreshold, hdrMax`. Defaults: contrast 1.05, sat 1.08, vignette 0.35, grain 0.035, bloom 0.6.
`draw(renderer)` replaces the render pass when a scene composites several layers itself.
`mb: true` in the returned object opts the scene into motion blur (below).

A scene can reuse another scene's world with a mode flag (S11 = `valley({...o, mode: 'after'})` of S9): the same
valley burnt, then recovering. Cheap, and it ties the story together.

## Commands

```bash
python3 $SKILL/scripts/init_film.py <slug> --title "…"
node phim3d/render.mjs exports/stills/ --w 960 --h 540 --stills 3,12,20     # look at frames while building a scene
./phim3d/sheet.sh exports/sheet.jpg exports/stills/*.jpg                   # contact sheet to Read
./render_chunks.sh draft            # 540p, 30 fps of output, at episode speed
./assemble.sh draft                 # silent draft → copy to review/draft.mp4
./render_chunks.sh final            # 1080p60 HEVC crf 16, 6 s film chunks, resumable, --mb 8 --sh 0.012
node phim3d/render.mjs exports/stills/ --film /dev.js --stills 2,5   # one scene in isolation (scratch film)
node phim3d/hud.mjs review/draft.mp4 exports/hud/ --stills 17,23,28.5   # HUD stills over the draft
node phim3d/hud.mjs review/draft.mp4 review/draft_hud.mp4 --audio audio/final.wav          # 540p30 HUD draft
node phim3d/hud.mjs exports/base_1080.mp4 exports/final.mp4 --w 1920 --h 1080 --fps 60 --hevc 1 --crf 16 \
  --audio audio/final.wav --ab 320k                                     # final: HUD burned over the 1080p60 film
python3 review/serve.py 8797        # review page on 127.0.0.1 with Range support (the video can be scrubbed)
./assemble.sh final audio/final.wav "exports/<Tiêu đề>.mp4"
```

Speed: the user approved **1.15×** ("nhịp nhanh hơn, khoảng 1.15"). Frames are sampled every 1.15/60 s of film time
(`--fps 52.17 --ofps 60`), so motion stays smooth at 60 fps. Narration, captions and the music bed live in final
(sped-up) time; the SFX cue list lives in film time and is played with `atempo`.

Run long renders in the background (`run_in_background`) and wait for the notification. If a chunk fails, read
its `.log`, fix, and rerun the same command: `.done` chunks are skipped. `render_chunks.sh` runs under `nice 15`
and waits while macOS memory free is below `MINFREE` (default 25 %): one heavy render at a time on 16 GB.

## Holds (slowing a scene for the voice)

`HOLDS = [[a, d], …]` in film.js: at film time `a` the picture eases down to 0.4× over 2.5·d seconds and back,
adding `d` seconds. Use it when the re-written narration needs more time over one image; no scene code changes.
`unhold(t)` maps timeline → scene time and is shared by page.html, hud.js and `audio/episode.py` (`hold`, `unhold`,
`hold_final`), so SFX (`mix.py` `place()`), captions and the score follow automatically. `END` includes the holds.
After adding holds, re-time lines.json, nudge and HUD cues (`N()` in hud.js converts heard-timeline times).

## Transitions (`xf`, `tx`)

`{id, t0, t1, xf: 1.6, tx: {c: '#c9d2da', a: 0.85}}`: the scene starts `xf` s early and overlaps the previous one.
The outgoing shot keeps pushing in (zoom 1 → 1.05/1.1), the incoming one settles out of the same zoom, so the
cut reads as one camera move. With `tx` the blend happens mid-way behind a colour veil (light cloud when rising,
grey cloud when descending, dark rain into the storm, warm haze into dawn). Plain cross-dissolves looked like a
ghosted double exposure; the user asked for "chuyển cảnh mượt, liên kết".

## Motion blur

`?mb=N&sh=S`: scenes returning `mb: true` render N sub-frames over a shutter of S film seconds and average them.
Final uses `--mb 8 --sh 0.012` (fast debris, rain, surf), ~2.6 s/frame at 1080p for those scenes; drafts use 1.

## HUD layer (narration cues)

`phim3d/hud.js` draws on a 1920×1080-unit canvas in **final time**, separate from the 3D render, so cues can be
changed without re-rendering the film. Each cue is `cue(win(t, a, b), () => …)`: blurs/slides in, holds, fades out (one block per narration line).
Helpers: `T` (text with a wide soft halo + thin dark rim), `pill`, `head`, `gauge`, `thermo`, `worldMap`/`map`
(`lon2x`, `lat2y`), `people` (icon grid), `keys`, `fmt`, `win`. Rules the user set in Episode 3:
- **No dark panels, discs or boxes** behind text or charts; only halo + rim. Text must not look sunken.
- Every number or process in the narration gets a cue at the moment it is said (26,5 °C → thermometer crossing a
  mark, "hơi nước bốc lên, ngưng thành mây" → drawn arrows and droplets, 49 % of deaths → 100 person icons).
- Make cues **look real**: Natural Earth map (not a blob), a satellite-like cloud spiral, drawn tin sheet/branch/
  brick for debris. Keep them above y ≈ 900 (captions below) and away from the subject of the shot.
- Draft with `--stills` at each cue, then a 540p HUD draft, then burn over the 1080p60 film.

## Look of a storm (Episode 3)

Seen from orbit: 5 tightly wound arms (`sp = phi + 1.8*lr`), wide bands, a large central dense overcast and a
clear eye; 3 arms looked like a throwing star. At ground level: `stormcoast.js` sets sky, light, haze, sea state,
bending palms, sideways rain and spume around the camera from one `k` (0 calm … 1 eyewall); wreckage streaks
downwind (`debris.js`); the surge raises the sea level over the village. Keep the camera above the waves (13 → 12 m
went under them once).

## Speed of rendering (M-series Mac, GPU-bound)

About 0.4 s/frame at 540p, 1.3 s at 1080p, 4.5 s at 4K. Rendering chunks in parallel does not help (one GPU).
A 4-minute 1080p60 film is ~14,000 frames ≈ 5 hours, so render the final overnight or while the voice is made.
**1080p60 only.** 4K waits until the channel has 1,000 subscribers.

## Look and direction (what made Episode 1 work)

- A real film, not motion graphics: the 3D picture carries the story; the only overlay is the HUD layer of
  narration cues (light, no panels). No title card, no labels on objects.
- **One-shot continuity:** every era flows into the next inside the frame (white glare to white glare, diving through
  the cloud deck, breaking the sea surface). No hard cuts, no wipes; `xf`/`tx` transitions where worlds differ.
- Painterly but physically lit: HDR, bloom, ACES-like grade, grain, vignette, small chromatic aberration.
- Every frame detailed: dust and particles in the foreground, depth haze, something moving in every layer.
- Bold set pieces, held long enough to read: the Theia impact, the Moon forming from the ring, the magma sea under
  meteor strikes, rain for millions of years, the snowball Earth, the Cambrian reef, dinosaurs then the asteroid
  with a full shockwave, the burnt valley, ferns returning over the ash.
- Living things: animals of the right era only (check `sources.md`), schools of fish moving as a flock, herds at
  a river ford, pterosaurs crossing. The user asked for animals; they bring the film to life.
- After a catastrophe, show its consequence (everything burnt, impact winter, recovery) before moving on.

## Render lessons (each one cost a re-render)

- **Pixel constants scale with `pxf()`** (point sizes, line widths, bloom reach), tuned at 1080 (`--ref 1080`),
  otherwise the look changes with resolution. GPU point size caps at 511 px: huge sprites must be camera-facing quads.
- **Seed every random draw** (`rng(seed)`). Chunks are rendered in separate browser sessions; unseeded randomness
  makes them disagree at the joins.
- **Never draw randomness per frame for state**: a yaw drawn each frame made distant dinosaurs spin. Draw once in build().
- `Curve.getPoint` is not arc-length: camera paths use `getPointAt` or the camera surges.
- A mesh that does not show is usually culling or winding: rain sheets and thin shells need `side: DoubleSide`.
- Impacts **explode on contact**: no frames of the impactor sinking into the planet first. Flash on the rim at touch.
- `flash` in grade is multiplied ×6 in post: keep its alpha tiny (0.018) or the frame whites out.
- Early-Earth surfaces use their own noise; never anything that resembles today's continents.
- 4K only: long draws trip the GPU watchdog and the WebGL context is lost (black frames). page.html splits draws into
  scissor strips (`--strips`, auto at >1080p) and throws if the context is lost. Compare against the draft by
  mean luma per second to find black stretches.
- Check stills at the hardest moments (impact peak, whiteouts, the darkest frames) before rendering motion.
- `episode.py` reads film.js with regexes: comments are stripped first, so a commented example scene cannot
  change `FILM_END`. Keep `SCENES` entries on one line each.
- Heavy ray-marched scenes (coast, ocean) can lose the WebGL context when two Chrome instances share the GPU:
  render them with one job, and re-run the chunk if the log says "context lost".

## Review gates

1. Stills/contact sheet of new scenes → read them yourself first; fix what is obviously wrong.
2. Silent 540p draft of the whole film → `review/index.html` served by `review/serve.py` (127.0.0.1, Range
   support; plain http.server cannot seek), chapter buttons and notes of what changed. The user approves look,
   story and speed.
3. Only then: voice, SFX, music, HUD, 1080p60 final.
