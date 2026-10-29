# 3D film pipeline (three.js → headless Chrome → ffmpeg)

Built for Episode 1 ("Trái Đất ra đời", `ai-video-projects/trai-dat-hinh-thanh/phim3d`). The template in
`template/` is that engine with the episode-specific parts removed; `scripts/init_film.py` scaffolds it.

## Layout of an episode

```
<slug>/
  episode.json          speed, music track + loop body, music dips, voice nudges/take2, voice→caption spellings
  render_chunks.sh      draft|final [from to]  → exports/chunks-*/c_NNN.mp4 (+ .done markers)
  assemble.sh           draft|final [audio.wav] [out.mp4]  → concat copy + mux
  phim3d/
    film.js             SCENES = [{id, t0, t1}] in film seconds, in play order
    scenes/<id>.js      one module per scene
    lib/kit.js          clamp, lerp, smooth, ease.{inOut,out,in,expo,sine}, keys([[t,v]…], t, ease), pxf(), rng(seed),
                        softPoints({count, place(i)→{p,s,c}}), vnoise3, rockGeo({radius, detail, seed, amp, freq, stretch, oct}),
                        fsQuad(mat), rockMaterial({frost, scale, heat, tint, roughness}), NOISE
    lib/glsl.js         NOISE (hash, snoise, fbm3, ridge3, voronoi3), RAY_VS
    lib/post.js         makePost(): HDR half-float → soft ceiling → UnrealBloom → GRADE
    lib/magma.js        magmaMaterial (lava sea), lib/plume.js plume({kind 0 fireball | 1 steam}) ray-marched
    page.html           loads film.js, keeps one scene alive, window.frame(t) → JPEG
    render.mjs          playwright-core + Chrome (--use-angle=metal), pipes frames to ffmpeg
    sheet.sh/sheet.py   contact sheet of stills (2 per row)
  audio/  captions/  review/  exports/  sources.md
```

## Scene contract

`export async function build({THREE, renderer, W, H, dur})` returns
`{scene, camera, update(tl), grade?(tl), draw?(renderer), dispose?()}`. `tl` is local film time.

`grade(tl)` overrides any of: `exposure, contrast, sat, lift[3], gain[3], vignette, chroma, grain, flash[r,g,b,a],
bloom, bloomRadius, bloomThreshold, hdrMax`. Defaults: contrast 1.05, sat 1.08, vignette 0.35, grain 0.035, bloom 0.6.
`draw(renderer)` replaces the render pass when a scene composites several layers itself.

A scene can reuse another scene's world with a mode flag (S11 = `valley({...o, mode: 'after'})` of S9): the same
valley burnt, then recovering. Cheap, and it ties the story together.

## Commands

```bash
python3 $SKILL/scripts/init_film.py <slug> --title "…"
node phim3d/render.mjs exports/stills/ --w 960 --h 540 --stills 3,12,20     # look at frames while building a scene
./phim3d/sheet.sh exports/sheet.jpg exports/stills/*.jpg                   # contact sheet to Read
./render_chunks.sh draft            # 540p, 30 fps of output, at episode speed
./assemble.sh draft                 # silent draft → copy to review/draft.mp4
./render_chunks.sh final            # 1080p60 HEVC crf 16, 6 s film chunks, resumable
./assemble.sh final audio/final.wav "exports/<Tiêu đề>.mp4"
```

Speed: the user approved **1.15×** ("nhịp nhanh hơn, khoảng 1.15"). Frames are sampled every 1.15/60 s of film time
(`--fps 52.17 --ofps 60`), so motion stays smooth at 60 fps. Narration, captions and the music bed live in final
(sped-up) time; the SFX cue list lives in film time and is played with `atempo`.

Run long renders in the background (`run_in_background`) and wait for the notification. If a chunk fails, read
its `.log`, fix, and rerun the same command: `.done` chunks are skipped.

## Speed of rendering (M-series Mac, GPU-bound)

About 0.4 s/frame at 540p, 1.3 s at 1080p, 4.5 s at 4K. Rendering chunks in parallel does not help (one GPU).
A 4-minute 1080p60 film is ~14,000 frames ≈ 5 hours, so render the final overnight or while the voice is made.
**1080p60 only.** 4K waits until the channel has 1,000 subscribers.

## Look and direction (what made Episode 1 work)

- **No text on screen at all.** A real film, not motion graphics. Science that needs words goes in the narration.
- **One-shot continuity:** every era flows into the next inside the frame (white glare to white glare, diving through
  the cloud deck, breaking the sea surface). No hard cuts, no wipes. A crossfade (1 s) only where the two worlds
  share light and colour.
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

## Review gates

1. Stills/contact sheet of new scenes → read them yourself first; fix what is obviously wrong.
2. Silent 540p draft of the whole film → `review/index.html` on localhost (python http.server on a free port,
   bound to 127.0.0.1), with notes of what changed. The user approves look, story and speed.
3. Only then: voice, SFX, music, 1080p60 final.
