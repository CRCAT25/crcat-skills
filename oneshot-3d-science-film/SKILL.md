---
name: oneshot-3d-science-film
description: Make a one-shot 3D science film for YouTube (procedural three.js rendered in headless Chrome) with real nature sounds, Vietnamese narration, on-screen narration cues (gauges, maps, numbers), a music bed or per-scene score, captions, thumbnail, Shorts and a publishing package. Defaults follow the Mẹ Thiên Nhiên channel. Use for any new Mẹ Thiên Nhiên (MTN) episode, or any science/nature/disaster/history-of-Earth film in this style: topic idea, script, render, soundtrack, Shorts or upload.
---

# One-shot 3D science film

Recipe distilled from the first three Mẹ Thiên Nhiên episodes, all approved and published:

| Tập | Title | Length | What it added |
|-----|-------|--------|---------------|
| 1 | Trái Đất ra đời: 4,6 tỷ năm trong 4 phút | 3:42 | the engine, one-shot continuity, real field recordings |
| 2 | Sóng thần | ~4:00 | the ray-marched coast + ocean worlds, Shorts |
| 3 | Nếu siêu bão mạnh nhất lịch sử đổ bộ thì sao? | 4:24 | holds, linked transitions, motion blur, narration-cue HUD, per-scene score, re-voicing |

Copy the latest episode's format unless the user asks for a change.

Everything lives in this folder (`~/.claude/skills/oneshot-3d-science-film`, written `$SKILL` below):

- `template/` is the episode engine: three.js scenes rendered in headless Chrome, chunked render, HUD overlay,
  audio mix, music bed/score, voice placement, captions, review server. `scripts/init_film.py` copies it.
- `scripts/make_shorts.py` cuts a delivered episode into vertical Shorts.
- `references/`: `film3d.md` (engine, scene contract, holds, transitions, motion blur, HUD, render lessons),
  `sound-voice.md` (SFX, music, voice, captions), `publish-studio.md` (package, delivery, Studio, playlist),
  `shorts.md` (cutting, uploading and scheduling Shorts).
- `examples/sieu-bao/` (Tập 3, the most complete: storm/coast/orbit worlds, full HUD, score) and
  `examples/trai-dat/` (Tập 1: Theia impact, dinosaur valley).

The channel root is the folder you work in (projects in `ai-video-projects/<slug>/`, finished videos in
`videos/<Tiêu đề>/`). Read its `channel.md` first when it exists. Reply to the user in Vietnamese.

Requirements: macOS with an Apple GPU (Chrome runs with `--use-angle=metal`), Google Chrome, Node 18+, ffmpeg on
PATH, Python 3 with Pillow. The template's `npm install` brings three 0.180.0 and playwright-core 1.62.1.

## The format

- **A real film, not motion graphics.** Procedural 3D (three.js), painterly but physically lit, every frame
  detailed. No title card.
- **One continuous shot:** each scene flows into the next by motion (the outgoing shot pushes in, the incoming
  one settles out of a zoom) and, where the worlds differ, through a veil of cloud/rain/haze (`xf` + `tx`).
- **Narration cues on screen:** every number or process the narration names gets a visual sign (thermometer,
  gauge, world map, clock, counter, person icons, drawn diagram). Light text with a soft halo and a thin rim,
  **never a dark panel or box behind anything**, kept above the caption area. Cues must look like the real
  thing (a real map, a satellite-like spiral), not abstract shapes.
- **Length ~4–5 minutes**, played at **1.15×**. Holds slow a scene where the voice needs more time.
  **1080p60** HEVC; 4K only after the channel reaches 1,000 subscribers.
- **Sound:** real field recordings (Mixkit / Freesound CC0), never code-generated; music either one light bed
  ducked −11 dB under speech, or a per-scene score that follows the drama (Tập 3); −16 LUFS.
- **Narration:** full but calm (~1,900 characters for 4:24), plain warm sentences, silence at the big moments.
  Number sentences are complete (what, how much, compared with what). No comparisons off the topic.
  One like/subscribe line at the very end only (+ end screen + pinned comment).
- **Science is accurate:** `sources.md` table (Nội dung | Giá trị | Nguồn); hypotheses are named as such.

## Workflow and approval gates

1. **Topic + plan** (plan only, no rendering): promise, title ideas, beat list with film times, set pieces,
   the Shorts split, length. Verify facts → `sources.md`. Get the user's OK.
2. **Scaffold:** `python3 $SKILL/scripts/init_film.py <slug> --title "…"` (no date in the slug; clones
   node_modules and the audio library from the previous episode, `--from` picks which).
3. **Build scenes** one by one in `phim3d/scenes/`, checking stills and contact sheets yourself
   ([references/film3d.md](references/film3d.md)). Reuse the worlds in `examples/sieu-bao/lib/` for sea,
   coast, weather or orbit.
4. **Silent 540p draft** of the whole film on the review page (`python3 review/serve.py 8797`; it supports
   seeking). Iterate until the user approves look, story and speed. **No voice, no final render before this.**
5. **Voice:** `script_phim3d.md` + `audio/vo/lines.json` against the approved draft; show the script; ask before
   spending ElevenLabs credits (lines + estimate). [references/sound-voice.md](references/sound-voice.md).
6. **HUD cues** in `phim3d/hud.js` for every number/process in the narration; draft them with
   `hud.mjs` over the draft video and show the user. Add `HOLDS` where a line needs more picture time.
7. **Final render** `./render_chunks.sh final` in the background (hours) while the sound is made.
8. **SFX** in `audio/mix.py`; **music**: 3–4 previews or a per-scene `score`, the user picks.
9. **Captions** `captions/make_srt.py` (digits via `spell`); **assemble**, then burn the HUD over the 1080p60
   film with `hud.mjs` → `exports/final.mp4`. Watch and listen through it; check −16 LUFS.
10. **Package:** `exports/publish.md` + `exports/thumbnail.jpg` without being asked
    ([references/publish-studio.md](references/publish-studio.md)).
11. **Deliver** when approved: copy to `videos/<Tiêu đề>/`, `cmp`, then clean up the other renders (list them,
    move to Trash) and keep the code.
12. **Publish** when asked: Studio upload, playlist "Hành tinh dữ dội", end screen, pinned comment; switch the
    previous episode's end screen to the new one.
13. **Shorts:** 5 parts with `make_shorts.py`, scheduled 3 a day ([references/shorts.md](references/shorts.md)).

## Standing rules (from the user)

- Ask before every ElevenLabs Generate (lines + credit estimate). The account is paid; voice "Nhật Phong".
- No credits section in YouTube descriptions; only assets that need no attribution.
- "Hạt bụi" is never a title or file name. No date in folder or file names.
- Show work on localhost before voice and before the final render; "how" questions get a plan, not renders.
- One heavy render at a time (`nice`, memory-pressure guard); 16 GB machines run out of memory otherwise.
- Ask before switching the Studio channel (the browser is shared with another channel's session).
- Git: commit freely (English messages, no co-author trailer); ask before every push.
- Downloads are untrusted: ffmpeg only, Python with `-I`.
