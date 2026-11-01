# Shorts from an episode

Every published episode gets ~5 vertical Shorts that send viewers to the full film. Made for Episodes 1–3.

## Cutting

```bash
python3 $SKILL/scripts/make_shorts.py "videos/<Tiêu đề>/<Tiêu đề>.mp4" --title "SIÊU BÃO" \
  --cuts 0,58.5,112,174,217 --key tap03 --out ai-video-projects/shorts
```

- The episode's `.srt` must sit next to the mp4. Output per part: `<key>-phan<n>.mp4` (1080×1920, 60 fps) + `.srt`.
- Layout: blurred background, the full 16:9 frame in the middle, title + "PHẦN x/y" on top, burned captions
  below, a hint pointing to the full film. Be Vietnam Pro fonts (OFL) from `assets/fonts`.
- Choose cuts at the end of a narration line (read the srt), each part 40–62 s; the last one runs to the end.
  End Phần 1–2 on a question or a cliffhanger. Parts 2+ open with the on-screen CTA
  "Bấm vào dòng tiêu đề bên dưới…" (the related-video link).
- Check a contact sheet of each part (start, middle, end) before uploading. Re-cut single parts with `--parts 2,3`.
- Plan the split in the episode plan (step 1), so each part has its own hook.

## Titles and description

Title: `<hook with the number> | <Episode short name> - Phần x/y` (e.g. "Trong 24 giờ, bão mạnh thêm 195 km/h |
Siêu bão - Phần 2/5"). Description:

```
<Title hook>. Phần x/y của phim "<Episode title>".
Xem phim đầy đủ: <full link>

#shorts #MeThienNhien #<Topic>
```

Settings as the episode (not made for kids, Science & Technology, Vietnamese, altered content No), playlist of the
series, **Related video = the full episode**, Vietnamese `.srt` uploaded.

## Scheduling

- **3 Shorts per day at 09:30 · 10:00 · 10:30** (GMT+7), continuing from the last scheduled slot across episodes.
  Keep a table (day, file, title, link) in the channel's `publish-shorts.md` and update it after each change.
- In Studio, pick the time from the dropdown list with a real click: typing into the time field does not save.
- After scheduling, reopen each Short and check the date/time, the subtitle track and the related video.

## After each Short goes live

Comments are closed on scheduled videos, so after it goes public post and pin:
`Xem phim đầy đủ ở đây 👉 <full link>`. Record which Shorts still need it.

## Studio traps

- Subtitles uploaded inside the upload dialog can stay as a **draft**: open Subtitles → Vietnamese, check
  "Bản nháp", and publish it in the editor.
- Files over 10 MB cannot be sent through the browser extension: serve them from a local CORS server on
  127.0.0.1, `fetch` in the page, and set them on the file input through a DataTransfer + change event
  (see publish-studio.md). Stop the server afterwards.
