# Publishing package and YouTube Studio

## exports/publish.md (Vietnamese; example: `examples/trai-dat/publish.md`)

- File line: name, 1920×1080, 60 fps, HEVC/AAC, duration; subtitle file; thumbnail description.
- **3 titles**, one marked "← đề xuất". Pattern that worked: `<Event>: <big number> trong <N> phút`. Never "Hạt bụi".
- **Description:** 1 paragraph hook-summary; 1 line about the real nature sounds; chapters (00:00 first, ≥3,
  each ≥10 s, in final time); one line "Hình ảnh là mô phỏng 3D dựa trên các giả thuyết khoa học hiện nay" plus
  any hypothesis named as such; 3 hashtags (#…, #KhoaHoc, #MeThienNhien). **No credits section.**
- **Tags:** ~12, Vietnamese, comma-separated.
- **Settings:** not made for kids; category Science & Technology; language Vietnamese + upload the .srt;
  altered/synthetic content **No** (simulated animation of natural events, not real people or events);
  playlist "Trái Đất kể chuyện" (create it if missing).
- **Pinned comment:** one question that invites answers ("Nếu được quay về… bạn chọn lúc nào…? 👇").
- **End screen:** subscribe button + a video element over the final calm shot (last ~14 s). Link the previous
  episode; update the previous episode's end screen to point at the new one.

## Thumbnail (exports/thumbnail.jpg, 1280×720)

The most dramatic frame of the film (render a 1080p still at that moment), plus 2 lines of large bold text with
a dark outline (title + the number). Text on the thumbnail is fine; text in the video is not.

## Delivery

When the user approves the final: copy (never move) into `videos/<Tiêu đề>/` the mp4, .srt, thumbnail.jpg and
publish.md, named after the recommended title (NFC, `:` → ` - `). Verify with `cmp`. Then delete every other
render (chunks, drafts, previews) after listing them for a look, and keep the code. 4K is not rendered.

## Uploading through YouTube Studio (Chrome MCP)

The user uploads the video file by dragging it in (files over 10 MB cannot be sent through the extension).
Chrome "Browser 1" is shared with the Góc Khám Phá session: check which channel Studio shows and ask before
switching. The user clicks "Xuất bản" (Publish) themselves.

- Title / description: the fields are contenteditable; focus them and use `document.execCommand('insertText', …)`
  so YouTube registers the change (setting textContent does not save).
- Thumbnail: serve the jpg from a temporary local CORS server on 127.0.0.1 (any free port), fetch it in the
  page, and set it on `#file-loader` through a DataTransfer + change event. Custom thumbnails need the channel to
  be phone-verified.
- Captions: same technique with `#captions-file-loader`.
- Radios by name: `VIDEO_MADE_FOR_KIDS_NOT_MFK`, `VIDEO_HAS_ALTERED_CONTENT_NO`.
- Do not reload the page while an upload is running; it cancels the upload.
- Avoid anything that opens a JS dialog. Stop and ask after 2–3 failed attempts at the same step.
- After publishing: post and pin the comment, set the end screen, add to the playlist, update memory with the link.
