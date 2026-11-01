# Drawing API (`whiteboard.py` as `wb`, `frame_kit.py` as `fk`)

The canvas is 1920×1080. y grows downward. Every `start` is board-local seconds; in a builder always write `at(k, off)`.
Defaults: `dur` comes from stroke length (pen speed 1500 px/s) or from the number of characters. `b.end` = when the last ink finishes.

## Colours

- `INK` (near-black), `RED`, `BLUE`, `GREEN`, `ORANGE`, `GREY`, `YELLOW`, `HIGHLIGHT` (marker yellow).
- Any `(r, g, b)` tuple also works, e.g. pastel fills `(255,205,205)` pink, `(190,230,190)` mint, `(205,220,255)` sky.

## Ink (the pen travels to each of these and draws it)

| Call | What it draws |
|---|---|
| `b.text(x, y_top, s, size=96, start, dur=None, color=INK, align="left"\|"center"\|"right")` | Handwriting, letter by letter. `x` is the left/centre/right edge, `y` is the top. One line: split long sentences yourself. |
| `b.icon(name, cx, cy, size, start, dur=None, width=8, color=INK)` | Tabler outline icon. `name` = an svg file name in `assets/icons/tabler/` without `.svg`. |
| `b.line(a, b, start, width=8, color=)` | Straight stroke with a slight hand wobble. |
| `b.arrow(a, b, start, head=28, ...)` | Arrow (use this, the font has no → glyph). |
| `b.rect(box, start, ...)` / `b.circle(box, start, turns=1.08, ...)` | Box / hand-drawn ellipse around `box=(x0,y0,x1,y1)` (overshoots a little like a real circle). |
| `b.underline(x0, x1, y, start, ...)` | Underline. |
| `b.cross(box, start, ...)` / `b.check(x, y, size, start, ...)` | Big X over something / tick mark. |
| `b.bar(box, start, color=INK, fill=None)` | Bar that grows from the bottom (for charts). |
| `b.strokes(polys, start, dur=None, width=8, color=INK, wobble=1.4, alpha=255)` | Any custom drawing: a list of point lists. Use it for missing icons (bus, battery, car, moon…). |
| `wb._ellipse(cx, cy, rx, ry, n)` | Point list of an ellipse: pass to `strokes` or `fill`. |

## Fills (appear without the pen, like colouring in)

- `b.highlight(box, start, dur=None, color=HIGHLIGHT, alpha=110)`: marker swipe behind text or a bar. Make the box a few dozen px bigger than the text.
- `b.fill(polys, start, color=BLUE, dur=None, alpha=150)`: flat colour inside polygons. Draw the ink outline after it, so the outline sits on top.

## Characters

**Stickman host (default for this style).** Call `install_stick()` once, before boards are built (`render.py` does it).

`s = b.stick(cx, base, height, start, pose="stand", mood="happy", accent=ORANGE, color=INK, dur=None, look=None, drawn=True, shirt=None)`

- Arguments:
  - `base` = y of the feet (≈ 1010 sits on the bottom edge).
  - `height` 330–520 is typical.
  - `shirt=(r,g,b)` gives a second character a different colour.
  - `look=(dx, dy)` sets the gaze, e.g. `(-0.3, 0)` looks left.
  - `drawn=False` makes it appear without being drawn (use it with `walk`).
- Poses: `stand wave point_l point_r point_up present_l present_r hips hold_up think shrug clap cheer fist facepalm cheeks hug sad shock worried`.
- Moods: `happy neutral talk calm shock sad worried think angry furious love proud laugh wink cry smug confused starstruck money nervous determined fear tired serious yummy grin`.
  - Some moods add effects: sweat, hearts, sparkles, coins, ?, vein.
- Timeline methods on the returned character (all chainable):
  - `s.act(t, pose=, mood=, look=)`: change pose or expression at `t`. Pose `shock` also jumps.
  - `s.walk(t, to_x, dur=None)`: walk to `to_x`.
  - `s.jump(t, height=0.22, dur=0.6)`
  - `s.last`: time of the last action.
  - `s.head_at(t)` / `s.hand_at(t, side=1)`: positions, for aiming speech tails and placing held icons.
- Template helpers: `host()`, `extra()` (a side character with another shirt) and `walk_in()` (enters from off-screen).

**Other characters.**

- `b.peep(name, cx, base, height, start, dur=None, color=INK, flip=False)`: hand-drawn Open Peeps busts (CC0).
  - Revealed by zig-zag bands from top to bottom.
  - Names `peep-N` and mood/pose tags are in `assets/people/open-peeps/catalog.json`.
  - Three busts 600 px tall fit one row (cx ≈ 360 / 930 / 1520, base 1000).
- `b.person(cx, base, height, start, mood, pose, shirt, hair, ...)`: chibi figure.
  - mood: `happy sad shock think angry worried neutral`.
  - pose: `stand point_r point_l arms_up hands_hip think shrug hold wave`.
  - hair: `short long bun none`.
  - Returns `.head .hand_l .hand_r .top .bbox .end`.

## Speech, stickers, photos

- `b.speech(x, y, s, start, tail, size=56, think=False, align="center")`: speech bubble on paper.
  - `think=True` draws a thought cloud with dots.
  - `tail=(x, y)` points at the speaker's mouth or head. Compute it from `s.head_at(t)`.
- `b.sticker(kind, cx, cy, start, size=150, color=RED, shape="burst"|"pill"|"tag", font=64, rot=-6, pop=0.35, until=None, bob=4)`: colour die-cut sticker.
  - It pops in with an overshoot, then floats gently. The pen ignores it.
  - kinds:
    - `face:<happy|laugh|love|shock|sad|cry|angry|think|cool|money|neutral>`
    - `icon:<tabler name>`
    - `text:<WORDS>` (font ≥ 40)
    - `heart star check cross ! ?`
  - `until` = pop-out time.
  - The audit **fails if a sticker covers text**: put stickers in empty space.
- `photo(b, name, cx, cy, w, start, h=None, rot=0)` (template helper): pops in `visuals/photos/<name>.png`.
  - Use it for real products. Cut out the background first: transparent PNG.

## Composition and rendering (`render.py` already wires this; normally just edit scenes)

- `wb.compose(board, t, duration)`: RGBA frame (paper + ink + pen + slow camera drift).
- `wb.audit_into(T, board)`: adds text boxes to the safe-area audit.
- `fk.transition(scene_picture, BOUNDS, TYPES, t)`: scene changes.
  - `match` = hard cut.
  - `slide` = the next sheet slides in (inside a chapter).
  - `zoom` = zoom through (chapter openers).
  - `BOUNDS` must end with END.
- `fk.preview(frame, times, T, folder)`: stills + `overview.jpg`. It asserts the safe area.
- `fk.render(frame, duration, audio_wav, out_mp4, T, fps)`: H.264/AAC. Refuses to overwrite.
- `wb.pop_track(times, duration)`: pop sounds for stickers, from `b.pop_times(offset)`.
- `wb.paper()` = blank sheet; `wb.hand_font(size)` = the PIL font, for thumbnails.

## Thumbnail (1280×720)

- Use the same toolkit: draw a board, then save one frame.
  - `im = wb.compose(b, 99).convert("RGB").resize((1280, 720))`
  - Or build directly with `wb.hand_font`.
- 2–4 big words, one or two icons or a photo, one highlight behind the key word.
- Keep the bottom-right corner empty: YouTube's duration badge sits there.
- Also save a 320×180 copy and check that it is readable small.

## Living props (`anim_kit.py`)

Props that move on every frame, on top of the ink. The pen never draws them, and they are never "unfinished".
Use `b = ABoard(seed)` instead of `wb.Board` (the template's `build()` already does this):
`from anim_kit import ABoard, Counter, Vehicle, ...`. All coordinates are 1920×1080 px, and times come from `at(k, off)`.
Every prop takes `until=` (the time it disappears).

- `b.anim(prop)`: adds a prop and returns it.
- `b.stamp(s, cx, cy, start, color=RED, font=96, rot=-8, until=None, shake=9)`: a rubber stamp slams down and shakes the board.
  - Its text is audited like text.
  - **The thick stroke eats the horn of Ơ/Ư** ("HƠN" reads "HON"), and `½` comes out tiny. Pick words without them ("TIẾT KIỆM", "SAI", "50%").
- `b.chat(s, x, y, start, name="", side=-1, size=48, until=None, width=None)`: a messenger bubble with an avatar that slides up (rumours, ads, what people say).
  - `x` is the left edge (side −1) or the right edge (side +1); `y` is the top.
- `Counter(cx, cy, start, t0, t1, v0, v1, size=110, fmt="{:,}", suffix="", color=INK)`: a number that counts from v0 to v1 between t0 and t1.
  - Centre-anchored; thousands use dots (20.000). Land on the number the voice says.
- `Vehicle(kind, keys, ground, start, s=1.0, face=1, color, rider, label=None, mood="happy")`: rolls along `keys = [(t, x), …]` on the road at y = `ground`.
  - kind: `scooter | app | ebike | car | bus | truck`. Petrol vehicles puff smoke; `ebike` sparks.
- `Clock(cx, cy, r, start, h0, h1, t0, t1, night=False)`: the hands spin from hour h0 to h1 between t0 and t1.
- `Calendar(cx, cy, w, h, start, pages=[(t, big, small), …])`: a tear-off calendar; each page flips up at its time.
- `Gauge(cx, cy, r, start, keys=[(t, value 0..1), …], limit=0.7)`: a half-dial with a wobbling needle and a red zone above `limit`.
- `Progress(box, start, t0, t1, color)`: a bar that fills inside `box` between t0 and t1.
- `Barrier(x, ground, start, t_down, L=420, side=1, t_up=None)`: a boom barrier that drops (a blocked rule, "không đủ điều kiện").
- `Pin(x, y, start, color, size=60, ping=True)`, `Pointer(keys=[(t, x, y), …], start, direction="down")`: a map pin that drops and pings, and a fat arrow that hops.
- `Card(cx, cy, w, h, start, t_flip, year)`, `Magnifier(at=lambda t: (x, y), start, r=56)`, `Camera(x, y, start, flashes=(t, …))`.

Use about one living prop per board, on the sentence that needs motion. Keep its box clear of text; the audit only checks stamps and chats.
