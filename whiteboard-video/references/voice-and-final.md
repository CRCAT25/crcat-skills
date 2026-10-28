# Voice, alignment, mix, final export

Only start here after the user approved the **whole silent draft**.

## 1. Voice

- **Consent first.** State the voice/provider, the number of characters, and the estimated cost (ElevenLabs ≈ 1 credit/char; 8 min ≈ 7–9k credits). Wait for a clear yes.
- **Voice:** any TTS provider; pick a calm narrative voice in the video language (ElevenLabs, a local TTS, etc.).
  - Settings: Eleven v4, stability 0.5, similarity 0.75, native speed.
- **Generate per chapter**, each ≤ ~1,500 characters, with the text taken exactly from `script.md`.
  - Join the chapters with ~0.9 s of silence between them into `audio/voice-raw.wav` (48 kHz).
  - Use ffmpeg `concat`, or numpy in a short script.
- **Numbers must be read the Vietnamese way.** If TTS misreads "1.000 km", write it out in the TTS text only ("một nghìn ki-lô-mét"). Keep `script.md` and the screen in digits.

## 2. Cues

```
R="uv run --offline --no-project --python 3.12 --with pillow --with numpy --with scipy python"
$R render.py plan                                   # audio/plan-TAG.json: one phrase per sentence
uv run --offline --no-project --python 3.12 --with mlx-whisper --with numpy python \
  $SKILL/scripts/align_captions.py audio/plan-TAG.json audio/voice-raw.wav \
  --out-dir captions --tag TAG --padded-audio audio/voiceover-TAG.wav
python3 $SKILL/scripts/fix_onsets.py captions/pacing-TAG.json audio/voiceover-TAG.wav \
  captions/pacing-TAGb.json --plan audio/plan-TAG.json
```

- The `--offline` Whisper model must be cached; if it is not, ask before downloading.
- `mlx-whisper` needs Apple Silicon. On other machines use any word aligner and write the same `pacing-TAGb.json` (`{"cues": [[start, end], …]}`, one cue per sentence).
- From now on, `render.py` uses the real cues automatically ("voiced cues" in its first line).
- Run `timing` again and fix every `drawing runs past scene end`. The real voice is rarely as fast as 16.5 cps.
- Run `preview` again.

## 3. Mix

```
$R render.py beds                                  # pad bed + pops + audio/mix-spec-TAG.json
$R $SKILL/scripts/mix_audio.py audio/mix-spec-TAG.json audio/mix-TAG
```

- Read `output_i` from the result: it should be ≈ −14 LUFS, with true peak ≤ −2.
- The levels are: music −24 dB ducked −5 dB under the voice, pops −21 dB relative to the voice, **no pen sound**.

## 4. Render + QA

```
$R render.py render                                # exports/<slug>-TAG.mp4, 60 fps (≈ 2× slower than the draft)
$R $SKILL/scripts/qa_export.py exports/<slug>-TAG.mp4 --duration <END> --out-dir exports/qa-TAG \
  --report exports/qa-TAG/report.json
```

- Run the render in the background and wait for the notification.
- QA checks duration, size, fps, loudness and black or frozen frames, and writes contact sheets.
- A silent draft "failing" loudness is normal; a voiced final must pass.
- Then look at the contact sheets (one frame per 5 s) and every cut. Passing QA is not enough.
- Never say you listened to or watched something you did not.

## 5. Deliver

- **`exports/thumbnail.jpg`** (1280×720) and a 320×180 check copy.
- **`exports/publish.md`:**
  - 3 title options, one of them recommended.
  - The description: hook, chapters `00:00 …` (≥ 3, each ≥ 10 s), sources.
  - Tags and hashtags.
  - A pinned comment.
  - The end-screen plan.
  - The "altered or synthetic content" answer.
  - No "Ghi công"/credits section unless an asset licence requires one; prefer assets that need no attribution.
- **SRT:** from the aligned captions (`captions/` holds the words).
- **Copy, never move,** the finished files into the user's delivery folder, but only once they confirm the final. Never overwrite an earlier delivery without asking.
- **Uploading to YouTube** is a separate step that needs its own OK.
