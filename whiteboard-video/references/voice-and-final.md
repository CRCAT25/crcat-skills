# Voice, alignment, mix, final export

Only start here after the user approved the **whole silent draft**.

## 1. Voice

- **Consent first.** State the voice/provider, the number of characters, and the estimated cost (ElevenLabs ≈ 1 credit/char; 8 min ≈ 7–9k credits; two takes per chapter cost double). Wait for a clear yes.
- **Voice:** any TTS provider; pick a calm narrative voice in the video language (ElevenLabs, a local TTS, etc.).
  - Settings: Eleven v4, stability 0.5, similarity 0.75, native speed.
- **TTS text per chapter:** `audio/tts-input-TAG-chN.txt` (N = the `### N ·` heading), each ≤ ~1,500 characters.
  - The text is `script.md` with **numbers spelled out the Vietnamese way** ("1.000 km" becomes "một nghìn ki-lô-mét", "340 triệu" becomes "ba trăm bốn mươi triệu"). Keep `script.md` and the screen in digits.
- **Two takes per chapter** (ElevenLabs gives 2 per Generate). Save them as `audio/voice-TAG-chN-take1.mp3`, `…-take2.mp3`.
- **Pick and join:**

```
R="uv run --offline --no-project --python 3.12 --with pillow --with numpy --with scipy python"
W="uv run --offline --no-project --python 3.12 --with mlx-whisper --with numpy python"
$W $SKILL/scripts/pick_takes.py . --tag TAG          # audio/take-scores-TAG.json: Whisper ratio per take, best pick
$R $SKILL/scripts/build_voice.py . --tag TAG         # audio/voice-raw-TAG.wav (48 kHz) + voice-offsets-TAG.json
```

  - Read the `diffs` of every picked take: a high ratio can still hide one wrong number. Regenerate just that chapter if a number is misread.
  - `mlx-whisper` needs Python **3.12** (not 3.13+) and Apple Silicon.

## 2. Cues

```
$R render.py plan                                   # audio/plan-TAG.json: one phrase per sentence
$W $SKILL/scripts/align_captions.py audio/plan-TAG.json audio/voice-raw-TAG.wav \
  --out-dir captions --tag TAG --padded-audio audio/voiceover-TAG.wav
python3 $SKILL/scripts/fix_onsets.py captions/pacing-TAG.json audio/voiceover-TAG.wav \
  captions/pacing-TAGb.json --plan audio/plan-TAG.json
```

- The `--offline` Whisper model must be cached; if it is not, ask before downloading.
- On machines without Apple Silicon use any word aligner and write the same `pacing-TAGb.json` (`{"cues": [[start, end], …]}`, one cue per sentence).
- From now on, `render.py` uses the real cues automatically ("voiced cues" in its first line).
- **The real voice is usually faster than the 16.5 cps estimate** (one 8-minute script was read in 7:10). Do not speed up or slow down the speech. Stretch the pauses between sentences instead:

```
$R $SKILL/scripts/stretch_pauses.py . --src v01 --tag v02 --base 0.15 --para 0.65 --chapter 1.8
```

  - It inserts silence at the quietest point of every gap: `base` everywhere, plus `para` after a paragraph end, `chapter` before a new chapter, plus `PAUSE[(ch, k)]` from `scenes.py`.
  - It writes `audio/voiceover-v02.wav`, `captions/pacing-v02b.json` and `captions/subtitles-v02.srt`. Continue with `TAG=v02`.
  - Tune the numbers until the length is right (e.g. > 8:00), with no beat longer than ~2.5 s.
- Run `timing` again and fix every `drawing runs past scene end`. Run `preview` again.

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
  - **Finance or price content:** the date of the figures ("số liệu tra đến …") and "không phải lời khuyên đầu tư", both in the voice at the end and in the description.
  - No "Ghi công"/credits section unless an asset licence requires one; prefer assets that need no attribution.
- **SRT:** `captions/subtitles-TAG.srt` (written by `stretch_pauses.py`; otherwise build it from the aligned captions).
- **Copy, never move,** the finished files into the user's delivery folder, but only once they confirm the final. Never overwrite an earlier delivery without asking.

## 6. Shorts (after the final is approved)

Cut the final 16:9 video into vertical parts. Each part opens on a fresh scene and ends on a hook to the next part.

```
// shorts.json
{"title": "NHÀ Ở XÃ HỘI 1 TỶ",
 "parts": [["<first words of the opening sentence>", "<hook title of the part>"], ...],
 "stop_at": "Cảm ơn bạn đã xem",
 "out": "exports/shorts"}
```

```
P="uv run --offline --no-project --python 3.12 --with pillow python $SKILL/scripts/make_shorts.py"
$P shorts.json exports/<slug>-TAG.mp4 captions/subtitles-TAG.srt --cuts      # cut list; each part ≤ 60 s
$P shorts.json exports/<slug>-TAG.mp4 captions/subtitles-TAG.srt --still 3 12.5
$P shorts.json exports/<slug>-TAG.mp4 captions/subtitles-TAG.srt              # all parts: mp4 (60 fps) + srt
```

- Layout (1080×1920): blurred background, the full frame in the middle, title + "PHẦN x/y" pill on top, burned captions below, and a "Xem tiếp Phần x+1" hint.
- A part starts at a sentence that makes sense on its own (a question or a new board), never in the middle of a calculation. Use 6–9 parts of 30–60 s.
- Show the cut list and a few stills before rendering all parts. Render them one at a time (one heavy job at a time).
- Bundled font: Be Vietnam Pro (OFL).

## 7. YouTube publishing (each upload or schedule needs the user's OK)

- **Schedule:** the long video first, at the time the user names; the Shorts after it, on the days and times the user names.
- Fill in: title, description, tags, thumbnail, playlist, "altered or synthetic content" answer, chapters (from the description).
- **Related video on Shorts:** link each Short to the long video. This only works **after the long video is public**, so do it once it goes live (or schedule a reminder).
- **Short subtitles:** set the video language first, then upload the part's srt in the editor: Phụ đề → ⋮ → Tải tệp lên → Có thời gian. Then check the **"Bản dịch nháp"** tab: an upload can stay a draft until you press Xuất bản.
- **Pinned comments:**
  - On the long video: the question for viewers + the sources/disclaimer.
  - On each Short, once it is live: "Xem video đầy đủ ở đây 👉 <link of the long video>".
- Do not change channel-wide settings (default language, etc.) while doing this.
