# Scene recipes (copy, then adapt)

These are builders from approved videos. `at(k, off)` = sentence k of this scene's chapter + off seconds.
The helpers (`chapter_head host extra walk_in paper bill hbar dot note bus photo`) live in `template/scenes.py`.
Colours used below that are not in `wb` (`PINK`, `GAS_C`, `RENT_C`, `OWN_C`) are your own constants.
Define them at the top of `scenes.py`.

## 1. A vs B opener (cold open)

```python
def s0_vs(b, at):
    b.icon("motorbike", 480, 380, 300, at(0, 0.2), color=RED)
    b.text(480, 580, "xe máy", 90, at(0, 0.9), align="center")
    bus(b, 1440, 380, 380, at(0, 1.4))                      # custom-stroke icon (no Tabler bus)
    b.text(1440, 580, "xe buýt", 90, at(0, 2.4), color=BLUE, align="center")
    b.sticker("text:VS", 960, 380, at(0, 3.0), color=ORANGE, font=90, rot=-8)
    s = host(b, 960, at(1, 0.0), h=330, pose="shrug", mood="think")
    b.speech(1330, 720, "Xe máy rẻ hơn chứ?", at(1, 0.8), tail=(1060, 790), size=56, think=True)
```

## 2. Chapter opener

- Start with `chapter_head(b, at, n, "Tên chương")`, then one big visual that sums up the chapter.
- Use the `zoom` transition.

## 3. Receipt (hoá đơn): rows appear sentence by sentence

```python
rows = [("xăng 20 km", "15.000 đ", INK), ("gửi xe", "5.000 đ", INK)]
bill(b, rows, lambda k: at(0, 1.0) if k == 0 else at(1, 0.0), L=200, R=820, y0=330,
     total=("1 ngày", "20.000 đ", RED, at(1, 2.2)))
b.sticker("face:shock", 1600, 560, at(1, 3.0), size=140)    # reaction on the total
note(b, "số liệu ví dụ", at(0, 2.0))
```

## 4. Bar comparison

The bars use the hand-coloured `hbar`.

- Scale both bars with the same factor.
- Put the value above each bar and the name below the base line.
- Then circle the winner or write the difference.

```python
base, k = 820, 0.025                                         # px per đồng
for i, (name, v, col, fill) in enumerate([("xe máy", 20000, RED, (255,205,205)), ("xe buýt", 10000, BLUE, (205,220,255))]):
    x = 600 + i * 600; h = v * k
    hbar(b, (x - 110, base - h, x + 110, base), at(2, 0.4 + i * 1.2), fill, color=col)
    b.text(x, base - h - 90, f"{v:,} đ".replace(",", "."), 64, at(2, 0.8 + i * 1.2), color=col, align="center")
    b.text(x, base + 20, name, 60, at(2, 0.6 + i * 1.2), align="center")
```

## 5. Line chart / break-even (axes + lines + marked crossing)

```python
def axes(b, t, x0=240, y0=850, x1=1500, y1=200, xl="km / tháng", yl="đ / tháng"):
    b.arrow((x0, y0), (x1, y0), t, width=6); b.arrow((x0, y0), (x0, y1), t + 0.4, width=6)
    b.text(x1, y0 + 20, xl, 52, t + 0.8, color=GREY, align="right"); b.text(x0 + 20, y1 - 10, yl, 52, t + 1.0, color=GREY)

X = lambda km: 240 + km * 1.9; Y = lambda d: 850 - d * 1.4
b.strokes([[(X(0), Y(0)), (X(620), Y(620 * 0.72))]], at(14, 0.6), 0.8, width=8, color=RED)   # rising cost
b.line((X(0), Y(175)), (X(620), Y(175)), at(14, 1.2), width=8, color=BLUE)                  # flat fee
dot(b, X(243), Y(175), at(14, 3.4), r=16)
b.line((X(243), Y(175)), (X(243), 850), at(14, 3.6), width=4, color=RED)
b.text(X(243), 862, "≈ 240 km", 56, at(14, 3.8), color=RED, align="center")
```

## 6. Table that fills row by row

See `table()`, `cell()` and `row()` in xe-dien `scenes.py`. In short:

- Fixed origin `TX, TY`, column width `CW`, row height `RH`.
- Draw the header line and the column line first, then the column names in each option's colour.
- Each `row(b, r, values, at(k))` writes its values with staggered offsets.
- Finish with a highlight over the cheapest column and an arrow or a short comment.
- At most 4 rows × 3 columns at font 76.

## 7. Custom icon from strokes (battery, bus, car, anything missing)

```python
def battery(b, cx, cy, w, h, start, level=0.8, color=INK, fill=GREEN):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    b.rect((x0, y0, x1, y1), start, color=color, width=7)
    b.rect((x1, cy - h * 0.2, x1 + w * 0.08, cy + h * 0.2), start + 0.5, color=color, width=6)
    if level:
        b.highlight((x0 + 12, y0 + 12, x0 + 12 + (w - 24) * level, y1 - 12), start + 0.8, color=fill, alpha=170)
```

- Build shapes from `rect`, `circle`, `line` and `wb._ellipse` point lists.
- Fill first (`b.fill`), then ink on top.
- Keep it simple: 4–10 strokes.

## 8. Character with a problem (story beat)

```python
near = extra(b, 520, at(16, 0.0), pose="hold_up")            # side character, other shirt colour
b.icon("basket", 700, 640, 140, at(16, 0.8), color=ORANGE)
b.speech(1050, 250, "Mỗi ngày có 7 km thôi", at(16, 1.4), tail=(near.head_at(at(16, 1.6))[0] + 60, 420), size=64)
near.act(at(17, 0.0), mood="shock")                           # the twist
```

## 9. Host reacts and walks

```python
s = walk_in(b, 520, at(1, 0.0), h=400, pose="present_r", mood="happy")
s.act(at(2, 0.0), pose="wave", mood="laugh")
s.walk(at(3, 0.0), 1400).act(s.last, pose="point_l", mood="talk")
```

## 10. Big number punch

Use this when the voice says one striking number.

```python
b.text(960, 300, "≈ 134 km", 200, at(k, 0.0), color=GREEN, align="center")
b.circle((560, 260, 1360, 560), at(k, 1.4), color=RED, width=7)
b.sticker("face:money", 1560, 300, at(k, 2.0), size=150, color=YELLOW)
```

## 11. Recap checklist

```python
for i, s in enumerate(["Tính theo tháng", "Cộng cả phí ẩn", "So 5 năm"]):
    b.check(260, 260 + i * 170, 70, at(i, 0.0), color=GREEN)
    b.text(340, 220 + i * 170, s, 80, at(i, 0.3))
```

## 12. End screen (last scene)

- The scene lasts `END_HOLD` (~11 s) past the last sentence.
- Draw the cross-link frame `BOX`. `render.py` fades the next episode's thumbnail (`NEXT_THUMB`) into it at `T_IN`.

```python
def s_end(b, at):
    b.text(110, 240, "Tập sau:", 64, at(k, 0.0), color=GREY)
    b.text(110, 320, "<tiêu đề thật của tập kia>", 72, at(k, 0.4))
    b.rect(BOX, at(k, 1.0), color=GREY, width=5)               # pen leaves the box before T_IN
    b.arrow((760, 470), (980, 470), at(k, 2.0), color=RED)
    s = host(b, 420, at(k + 1, 0.0), h=380, pose="wave", mood="happy")
    b.sticker("text:ĐĂNG KÝ", 500, 560, at(k + 1, 0.8), color=RED, shape="pill", font=56)
```

- Check with `preview` that the ink inside `BOX` has stopped before `T_IN`.
- Leave the bottom-right free for YouTube's subscribe element.
