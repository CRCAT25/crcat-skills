---
name: whiteboard-video
description: Make a hand-drawn whiteboard explainer video (YouTube 16:9, Vietnamese by default). A marker pen draws text, icons, charts, receipts and stickman characters on paper, in sync with the narration. Use when asked for a "video vẽ tay", "whiteboard", "bút vẽ lên bảng", a sketch/doodle explainer. Self-contained Python (Pillow + numpy + scipy) library, fonts, icons, characters and a runnable template project.
---

# Whiteboard video (vẽ tay bằng bút)

The output is an MP4 made of "boards". On each board a pen draws text letter by letter, icons, arrows, bars,
receipts and stickman characters. Colour stickers pop in at the emotional beats. Each element starts at the moment
its sentence is spoken. Everything is code: no image generator and no paid service is needed, except the voice.

Everything lives in this folder (`~/.claude/skills/whiteboard-video`, written `$SKILL` below):

- `scripts/` holds the libraries:
  - `whiteboard.py` (wb): boards, pen, text, icons, characters, stickers.
  - `frame_kit.py` (fk): transitions, previews, rendering.
  - `stickman.py` with `mascot_v03.py` and `mascot_v04.py`: the stickman host.
  - Audio and alignment tools: `make_music_pad.py`, `mix_audio.py`, `align_captions.py`, `fix_onsets.py`.
  - `qa_export.py`.
  - `ffmpeg_path.py`.
- `assets/`:
  - Font: Patrick Hand (OFL).
  - Tabler icons (MIT): **only the ~60 listed in `assets/icons/tabler/`**.
  - Open Peeps (CC0).
  - Stickman face sprites.
- `template/` is a working 45-second demo project. It contains:
  - `script.md`: the narration.
  - `narration.py`: splits the narration into sentences.
  - `scenes.py`: one builder per board, plus helpers.
  - `render.py`: timing, preview, draft, plan, beds and render.

## Run command

Every Python command uses this:

```
R="uv run --offline --no-project --python 3.12 --with pillow --with numpy --with scipy python"
```

- ffmpeg does not need to be on PATH; `ffmpeg_path.find_ffmpeg()` finds it. If it is missing, ask the user before installing anything.
- zsh does not word-split `$R`. Write the full command out, or define a shell function.

## Workflow (follow in order)

1. **New project.**
   - Copy the template: `cp -R $SKILL/template <projects>/<slug>`. The slug has no date. Ask where projects live if that is unknown.
   - Run once with no changes: `$R render.py preview`. This proves the environment works.
2. **Script.** Write `script.md` with the same headings:
   - `## Lời đọc`
   - `### <n> · <Chương>`
   - Paragraphs separated by a blank line.
   - Pacing: ~16.5 characters per second, so 8 minutes is about 8,000 characters.
   - One sentence = one cue. Keep the sentences short.
   - `python3 narration.py` prints the sentence numbers k for each chapter. Builders refer to those numbers.
   - Script craft, chapter arcs and the subscribe CTA are in [references/script-and-pacing.md](references/script-and-pacing.md).
3. **Scenes.** Write `scenes.py`:
   - One builder `fn(b, at)` per board. A new board starts every 1–4 sentences, so the picture changes every 4–8 s.
   - Register each builder in `SCENES` as `(chapter, first_sentence, builder, transition, chapter_title)`.
   - API: [references/drawing-api.md](references/drawing-api.md).
   - Layout and look rules: [references/layout-rules.md](references/layout-rules.md).
   - Ready-made board patterns (VS, receipt, bars, chart, table, character dialogue, end screen): [references/scene-recipes.md](references/scene-recipes.md).
4. **Check.** Fix every problem before moving on.
   - `$R render.py timing` must show no `drawing runs past scene end`.
   - `$R render.py preview` writes the last frame of every scene to `visuals/preview-<TAG>/overview.jpg`.
     - It asserts the safe area and stickers covering text, and stops at the first error.
   - Open the stills and look at them. Then preview a few in-between times too, e.g. `preview 12.5 30`.
5. **Silent draft for approval.**
   - `$R render.py draft` writes `exports/draft-v01-NO-VOICE.mp4` (30 fps, music pad + pops). It renders at ~2.4× real time.
   - Run it in the background and wait for the notification.
   - Show the user the **whole** draft, ideally on a localhost review page, and wait for their OK. Do not create the voice before that.
6. **Voice.** Only after approval, and only with consent for the cost. Then the final export.
   - Voice: ElevenLabs or any TTS, generated per chapter.
   - Alignment: `render.py plan`, then `align_captions.py`, then `fix_onsets.py`. This writes `captions/pacing-<TAG>b.json`.
   - Mix: `render.py beds`, then `mix_audio.py` (−14 LUFS).
   - Export: `render.py render` (60 fps), then `qa_export.py`.
   - Exact commands: [references/voice-and-final.md](references/voice-and-final.md).
7. **Deliver.** The deliverables are:
   - The inspected MP4.
   - A thumbnail (1280×720, same drawing style, 2–4 big words).
   - A publish note: title options, description with chapters, tags.
   - Never claim you listened to audio or watched video that you did not.

## Non-negotiable style rules (from the approved videos)

- **Title card on frame 0.** A big title in the centre over an 80% paper wash. It holds 0.3 s, then fades over 1.0 s. `render.py` already does this; just edit `LINES`.
- **Sync.** `LEAD = 0.6`: ink starts 0.6 s before the words. Every element is timed with `at(k, off)`, never with absolute seconds.
- **Ink finishes before the scene ends.** A board is never left half-drawn when the cut comes.
- **Safe area.** x 96–1824, bottom ≤ 1000, font ≥ 40 px. Circles and highlights must not touch text.
- **The screen shows exactly the numbers the voice says.** Label assumptions "giả định" or "ví dụ" in grey with `note()`.
- **Liveliness, in moderation.** About 1 character or 1–2 stickers per board, placed on emotional beats (shock, question, punchline). Not everywhere.
- **Sound** is voice + calm music pad (≈ −24 dB, ducked −5 dB under the voice) + sticker pops. **No pen or scribble sound** (by design).
- **Glyphs the hand font lacks:**
  - `→ ← ↓ ✓` are missing. Draw them with `b.arrow` / `b.check`.
  - `≈ ≤ ≠ × ÷ đ % ½` work.
- **Icons:** `ls $SKILL/assets/icons/tabler/` first.
  - If the icon you need is missing (bus, car, battery, clock…), draw it from strokes. See `bus()` in the template and `battery()` in scene-recipes.
  - For money in VND use `currency-dong`, not `coin`.
- **Real products** (a specific motorbike, phone…): use a transparent PNG cut-out with `photo()`.
  - Use only images the user supplies, or images that are free to use.
  - They pop in like stickers.
- **Never overwrite an export.** Bump `TAG=v02`. `fk.render` refuses to overwrite.
- For a real video aim for **> 8:00** so mid-roll ads are possible. Hold the end screen ~20 s (`END_HOLD ≈ 11`) with the grey `BOX` for YouTube's end-screen element.

## When something breaks

- `AssertionError` from `audit_into` or `preview` means an element is out of the safe area or a sticker covers text. Move the element, then rerun.
- `drawing runs past scene end`: start elements earlier (smaller `off`), give them a shorter `dur`, or move the next scene one sentence later.
- `KeyError (chapter, k)`: the builder uses a sentence number that does not exist. Check `python3 narration.py`.
- `ModuleNotFoundError: whiteboard`: run from the project folder. `scenes.py` adds `$SKILL/scripts` to `sys.path`; set `WHITEBOARD_SKILL` if the skill lives elsewhere.
