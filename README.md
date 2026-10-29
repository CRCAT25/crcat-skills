# crcat-skills

A collection of [Claude Code](https://claude.com/claude-code) skills. Each skill is a folder with a `SKILL.md`.

| Skill | What it does |
|---|---|
| [whiteboard-video](whiteboard-video) | Hand-drawn whiteboard explainer videos: a marker pen draws text, icons, charts and stickman characters in sync with narration. Python (Pillow, numpy, scipy) + ffmpeg. |
| [me-thien-nhien-video](me-thien-nhien-video) | Text-free, one-shot 3D science films for the Mẹ Thiên Nhiên channel: procedural three.js scenes rendered in headless Chrome, real nature sounds, sparse Vietnamese narration, ducked music bed, captions and a YouTube publishing package. Node (three, playwright-core) + ffmpeg + Python. |

## Install

All skills:

```sh
git clone https://github.com/CRCAT25/crcat-skills.git
cp -R crcat-skills/*/ ~/.claude/skills/
```

One skill only: copy its folder into `~/.claude/skills/`, for example
`cp -R crcat-skills/whiteboard-video ~/.claude/skills/`.

In [Video Studio](https://github.com/CRCAT25/video-studio): Skills tab, import from GitHub, paste
`https://github.com/CRCAT25/crcat-skills/tree/main/whiteboard-video` (or `.../tree/main/me-thien-nhien-video`).

## Licence

MIT for the code (see `LICENSE`). Bundled third-party assets keep their own licences, listed in `THIRD_PARTY.md`; the stickman sprites are original and MIT too.

## Adding a skill

Create a new folder with a `SKILL.md`, add a row to the table above, commit, push.
