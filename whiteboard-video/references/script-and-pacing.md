# Script and pacing

## Format of `script.md`

```
# <working title>

## Lời đọc

### 0 · Mở đầu
Câu ngắn. Câu ngắn tiếp theo.

Đoạn mới (dòng trống = nghỉ dài hơn 0,55 s).

### 1 · <Tên chương>
...
```

- `narration.py` splits sentences at `. ? !` and keeps decimal commas and points ("2,4 kWh", "1.000 km").
- Run `python3 narration.py` to see `(chapter, k)` for every sentence. **Changing a sentence shifts k for the rest of that chapter**: recheck the builders.
- Other sections in the file (`## Nguồn`, notes) are ignored.

## Length

- ≈ 16.5 characters/second of narration: 1,000 characters ≈ 1 minute.
- Long videos: **> 8:00** (mid-roll ads), so ≥ ~8,000 characters plus the 11 s end hold.
- A Short is ≤ 60 s (≈ 900 characters) and still opens with the title card.

## Structure (from approved episodes)

1. **Cold open, 20–40 s.**
   - A concrete question the viewer has asked themselves ("Is an electric scooter really cheaper than a petrol one?").
   - One surprising hint.
   - The promise of what we will calculate or show.
2. **4–7 chapters.** Each one follows the arc: *question → explain/calculate → reveal → bridge to the next chapter*.
   - The chapter title is a short noun phrase, and it becomes the YouTube chapter.
3. **A re-hook at least every ~60 s.** Use an open loop ("con số này sẽ đảo ngược ở phần 4"), a twist, or a character with a problem.
4. **Subscribe CTA, twice.**
   - Mid-video (≈ 60–70 %): one short, natural sentence ("Nếu thấy cách tính này có ích, bấm đăng ký để xem tập sau nhé").
   - At the end: thank the viewer, ask for like + subscribe, *then* the line pointing to the other episode.
   - Show both on screen: a `text:ĐĂNG KÝ` pill sticker or the host pointing.
5. **End.**
   - A short recap (3 checks).
   - The verdict for each type of viewer ("nếu bạn đi < 200 km/tháng…").
   - The teaser of the linked episode, which must use its **real title**.

## Writing rules

- Talk like a person explaining to a friend: "mình", "bạn", short sentences of 8–20 words. One number per sentence.
- **Every number can be verified.** Keep `sources.md` (link, date, quoted figure).
  - Write the assumptions on screen with `note("giả định …")`.
  - Use round numbers in the voice ("khoảng 240 km"); use the same rounding on screen ("≈ 240 km").
- No promises the channel cannot keep (e.g. "tập sau sẽ có …" only when that episode is planned).
- Write each sentence with its picture in mind. If you cannot picture a board for a sentence, rewrite it.

## Scene pacing

- A new board every 1–4 sentences (4–8 s).
- Inside a board, add a new element on almost every sentence.
- `slide` between boards of one chapter, `zoom` into a new chapter, `match` only for the very first scene.
- `PAUSE = {(ch, k): 0.6}` in `scenes.py` adds a beat before a punchline (in the draft). In the final, the real voice decides.
