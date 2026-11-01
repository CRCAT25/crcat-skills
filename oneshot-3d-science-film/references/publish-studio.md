# Publishing package and YouTube Studio

## exports/publish.md (Vietnamese; example: `examples/trai-dat/publish.md`)

- File line: name, 1920×1080, 60 fps, HEVC/AAC, duration; subtitle file; thumbnail description.
- **3 titles**, one marked "← đề xuất". Patterns that worked: `<Event>: <big number> trong <N> phút` (Tập 1) and
  a "what if" question (`Nếu siêu bão mạnh nhất lịch sử đổ bộ thì sao?`, Tập 3). Never "Hạt bụi".
- **Description:** 1 paragraph hook-summary; 1 line about the real nature sounds; chapters (00:00 first, ≥3,
  each ≥10 s, in final time); one line "Hình ảnh là mô phỏng 3D dựa trên các giả thuyết khoa học hiện nay" plus
  any hypothesis named as such; 3 hashtags (#…, #KhoaHoc, #MeThienNhien). **No credits section.**
- **Tags:** ~12, Vietnamese, comma-separated.
- **Settings:** not made for kids; category Science & Technology; language Vietnamese + upload the .srt;
  altered/synthetic content **No** (simulated animation of natural events, not real people or events);
  playlist **"Hành tinh dữ dội"** (public, episodes oldest first, Shorts included).
- **Pinned comment:** one question that invites answers ("Nếu được quay về… bạn chọn lúc nào…? 👇").
- **End screen:** subscribe button + a video element over the final calm shot (last ~14 s). Link the previous
  episode; then open the previous episode's end screen and switch its video element to the new one.

## Thumbnail (exports/thumbnail.jpg, 1280×720)

The most dramatic frame of the film (render a 1080p still at that moment), plus 2 lines of large bold text with
a dark outline (title + the number).

## Delivery

When the user approves the final: copy (never move) into `videos/<Tiêu đề>/` the mp4, .srt, thumbnail.jpg and
publish.md, named after the recommended title (NFC, `:` → ` - `). Verify with `cmp`. Then delete every other
render (chunks, drafts, previews) after listing them for a look, and keep the code. 4K is not rendered.

## Uploading through YouTube Studio (Chrome MCP)

Files over 10 MB cannot be sent through the extension directly. Either the user drags the file in, or serve it
from a temporary local CORS server on 127.0.0.1, `fetch` it in the Studio page and set it on the upload input
through a DataTransfer + change event (works for the video, the thumbnail and the .srt). Stop the server after.
Chrome "Browser 1" is shared with the Góc Khám Phá session: check which channel Studio shows and ask before
switching. Click Publish/Schedule only when the user explicitly asked to publish ("đăng ngay"); otherwise
leave the final click to them.

- Title / description: the fields are contenteditable; focus them and use `document.execCommand('insertText', …)`
  so YouTube registers the change (setting textContent does not save).
- Thumbnail: serve the jpg from a temporary local CORS server on 127.0.0.1 (any free port), fetch it in the
  page, and set it on `#file-loader` through a DataTransfer + change event. Custom thumbnails need the channel to
  be phone-verified.
- Captions: same technique with `#captions-file-loader`. Then check Subtitles: a track uploaded in the dialog can
  stay as a draft ("Bản nháp"); publish it in the subtitle editor.
- Visibility/schedule: choose the time from the dropdown with a real click; typed times are not saved.
- If YouTube is still running its checks, "Vẫn xuất bản" publishes anyway; tell the user to look at the
  Checks tab later.
- Radios by name: `VIDEO_MADE_FOR_KIDS_NOT_MFK`, `VIDEO_HAS_ALTERED_CONTENT_NO`.
- Do not reload the page while an upload is running; it cancels the upload.
- Avoid anything that opens a JS dialog. Stop and ask after 2–3 failed attempts at the same step.
- After publishing: post and pin the comment, set the end screen, add to the playlist, switch the previous
  episode's end screen, then make the Shorts ([shorts.md](shorts.md)). Update memory with the links.
