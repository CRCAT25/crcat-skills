# Layout and look rules (learned from user reviews)

## Grid of a 1920×1080 board

- **Safe area:** x 96–1824, bottom ≤ 1000, smallest font 40 px. `preview` asserts this and stops at the first error; fix that one, then rerun.
- Title of a board: centred at y 40–80, size 88–104.
- Chapter opener (`chapter_head`): grey "Phần n" at size 56, with the chapter name under it.
- Two-column "A vs B" layout:
  - Centres at x ≈ 480 and 1440, with a `VS` sticker at x 960.
  - Icons ~200–300 px, label under them at ~90 px.
- Character standing at the bottom: `base` 1010, height 330–520. Put the speech bubble above the other half of the screen, with its tail at the head.
- Bottom-left (x 110, y 945) is reserved for the small grey `note()` with the source or assumption.
- Text sizes:
  - Big punch number: 150–220.
  - Normal line: 60–96.
  - Labels: 52–64.
  - Notes: 40.

## Rules

1. **One idea per board.** At most ~3 lines of text plus one visual. If it needs more, split it into two boards with `slide`.
2. **Visuals change every 4–8 s.** No still board longer than ~6 s without something new: an element, a character action, a sticker.
3. **Ink is finished before the cut.** Check `timing` and the last-frame stills.
4. **Circles and highlights never touch text.** Pad the box by 20–40 px.
5. **Bar labels must not collide.** Value above the bar, name below the base line.
6. **The screen matches the voice**: the same number, the same unit. Write "≈" when the voice says "khoảng".
7. **Stickers** go on beats (shock, punchline, verdict): 1–2 per board at most, never over text or numbers.
8. **Characters tell the story.** A person with a problem ("người đi chợ gần nhà"), the host reacting with a mood change on the twist (`s.act(at(k), mood="shock")`).
9. **Colours carry meaning across the whole video.** Give each option one colour (e.g. xăng = RED, thuê pin = BLUE, mua pin = GREEN) and never swap them.
10. **The font lacks some glyphs** (`→ ← ↓ ✓`): draw them with `arrow`/`check`. `≈ ≤ ≠ × ÷ % đ ½` are fine. Vietnamese diacritics are fine.
11. **Only icons that exist.** Run `ls $SKILL/assets/icons/tabler/`. Draw the rest with `strokes`.
    - Do not use `coin` (it shows "$"). Use `currency-dong`.
    - There is no clock icon: use `hourglass`.
12. **Title card** opens every video and every Short (HOLD 0.3 s + FADE 1.0 s; a 3.4 s card was rejected as too long).
13. **End screen.**
    - Text on the left half (previous or next episode).
    - On the right, a grey frame `BOX = (1000, 230, 1780, 670)` for YouTube's end-screen video element.
    - That episode's thumbnail fades into the frame only after the pen has left it.
    - The teaser line must match that episode's real title.
