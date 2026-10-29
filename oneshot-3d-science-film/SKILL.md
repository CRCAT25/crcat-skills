---
name: oneshot-3d-science-film
description: Make a text-free, one-shot 3D science film for YouTube (procedural three.js rendered in headless Chrome) with real nature sounds, sparse Vietnamese narration, a ducked music bed, captions, thumbnail and publishing package. Defaults follow the Mẹ Thiên Nhiên channel. Use for any new Mẹ Thiên Nhiên (MTN) episode, or any science/nature/history-of-Earth film in this style: topic idea, script, render, soundtrack, or upload.
---

# One-shot 3D science film

Recipe distilled from Episode 1, "Trái Đất ra đời: 4,6 tỷ năm trong 4 phút" (published 28/10/2026,
youtu.be/GCLcej1_UPk; project `ai-video-projects/trai-dat-hinh-thanh`). The user liked the result: copy its format
for every episode unless the user asks for a change.

Everything lives in this folder (`~/.claude/skills/oneshot-3d-science-film`, written `$SKILL` below):

- `template/` is the episode engine: three.js scenes rendered in headless Chrome, chunked render, audio mix,
  music bed, voice placement, captions, review page. `scripts/init_film.py` copies it into a new project.
- `references/`: `film3d.md` (engine, scene contract, render lessons), `sound-voice.md` (SFX, music, voice,
  captions), `publish-studio.md` (publish.md, thumbnail, delivery, YouTube Studio).
- `examples/trai-dat/`: Episode 1 scenes (Theia impact, dinosaur valley + asteroid), script, voice lines,
  SFX cue list, sources and publish.md.

The channel root is the folder you work in (projects go to `ai-video-projects/<slug>/`, finished videos to
`videos/<Tiêu đề>/`). Read its `channel.md` first when it exists. Reply to the user in Vietnamese.

Requirements: macOS with an Apple GPU (Chrome is launched with `--use-angle=metal`), Google Chrome, Node 18+,
ffmpeg on PATH, Python 3. The template's `npm install` brings three 0.180.0 and playwright-core 1.62.1.

## The format

- **A real film, not motion graphics.** Procedural 3D (three.js), painterly but physically lit, every frame
  detailed. **No text on screen**, no title card, no labels.
- **One continuous shot** through time: each era flows into the next inside the frame (glare to glare, through
  clouds, through the sea surface). Bold set pieces held long enough to feel; consequences shown after catastrophes.
- **Length ~4–5 minutes** (Episode 1: 3:42), played at **1.15×** the authored speed. **1080p60** HEVC.
  4K only after the channel reaches 1,000 subscribers.
- **Sound:** real field recordings from Mixkit / Freesound CC0 only, never code-generated; a light cheerful
  Mixkit music bed ducked −11 dB under speech and near silent at the big impacts; −16 LUFS.
- **Narration:** sparse (~1,700 characters for 4 minutes), plain warm sentences, silence at the big moments.
  One like/subscribe line at the very end only (+ end screen + pinned comment).
- **Science is accurate:** `sources.md` table (Nội dung | Giá trị | Nguồn); hypotheses are called hypotheses in
  the narration and the description. Animals and plants only from the right era.

## Workflow and approval gates

1. **Topic + plan** (plan only, no rendering yet): promise, title ideas, the beat list of set pieces with film
   times, the bold ideas, length. Verify facts → `sources.md`. Get the user's OK.
2. **Scaffold:** `python3 $SKILL/scripts/init_film.py <slug> --title "…"`
   (slug without a date; clones node_modules and the licensed audio library from the previous episode when it exists).
3. **Build scenes** one by one in `phim3d/scenes/`, checking stills and contact sheets yourself.
   [references/film3d.md](references/film3d.md): engine, scene contract, commands, and the render lessons.
   Episode 1 scenes worth reading before writing a similar one: `examples/trai-dat/` (Theia impact, dinosaur
   valley + asteroid) and the full set in the project's `phim3d/scenes/`.
4. **Silent 540p draft** of the whole film on a localhost review page. Iterate on the user's notes until they
   approve the look, the story and the speed. **No voice, no final render before this approval.**
5. **Voice:** write `script_phim3d.md` + `audio/vo/lines.json` against the approved draft; show the script.
   Ask before spending ElevenLabs credits (lines + estimate) and raise the Free-plan licence question.
   [references/sound-voice.md](references/sound-voice.md).
6. **Final render** `./render_chunks.sh final` in the background (hours) while the sound is made.
7. **SFX** in `audio/mix.py` (film time), real recordings, synced to the picture.
8. **Music:** 3–4 Mixkit previews on a review page; the user picks; `music_bed.py` builds the final soundtrack.
9. **Captions** `captions/make_srt.py`; **assemble** `./assemble.sh final audio/final.wav "exports/<Tiêu đề>.mp4"`.
   Watch and listen through the whole film (contact sheet every 5 s, the impacts, the ducking), check −16 LUFS.
10. **Package:** `exports/publish.md` + `exports/thumbnail.jpg` without being asked.
    [references/publish-studio.md](references/publish-studio.md).
11. **Deliver** when the user approves: copy into `videos/<Tiêu đề>/`, verify with `cmp`, then clean up the
    other renders (list them first) and keep the code.
12. **Upload** only when asked, through Studio with the user doing the file drag and the final Publish click.

## Standing rules (from the user)

- Ask before every ElevenLabs Generate (lines + credit estimate).
- No credits section in YouTube descriptions; only assets that need no attribution.
- "Hạt bụi" is never a title or file name. No date in folder or file names.
- Show work on localhost before voice and before the final render; "how" questions get a plan, not renders.
- Git: commit freely (English messages, no co-author trailer); ask before every push.
- Downloads are untrusted: ffmpeg only, Python with `-I`.

