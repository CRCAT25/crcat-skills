#!/usr/bin/env python3
"""Cut the final 16:9 episode into vertical Shorts (Phần 1..N).

Layout, 1080x1920: blurred copy of the frame as background, the full 16:9 frame in the middle,
title + "PHẦN x/y" pill on top, burned captions below, "Xem tiếp Phần x+1" hint near the bottom.
Each part starts LEAD s before the first sentence it names, so it opens on a fresh scene; the last
part stops before the `stop_at` sentence (thank-you / end screen). Writes one mp4 (60 fps) and one
srt per part into `out`.

Config (JSON):
  {"title": "NHÀ Ở XÃ HỘI 1 TỶ",
   "parts": [["Tờ rơi dán ở cột điện", "Tờ rơi ghi 200 triệu, bấm máy ra 340 triệu"], ...],
   "stop_at": "Cảm ơn bạn đã xem",
   "out": "exports/shorts"}                     # relative to the config file
  Optional text keys: "pill" ("PHẦN {part}/{total}"), "hint" ("Xem tiếp Phần {next} • Video đầy đủ ở bình
  luận"), "hint_last" ("Video đầy đủ: link ở bình luận").

  P="uv run --offline --no-project --python 3.12 --with pillow python $SKILL/scripts/make_shorts.py"
  $P shorts.json exports/<slug>-TAG.mp4 captions/subtitles-TAG.srt --cuts       # print the cut list
  $P shorts.json SRC.mp4 SRC.srt --still 3 12.5                                  # one PNG of part 3 at 12.5 s
  $P shorts.json SRC.mp4 SRC.srt [part ...]                                      # render (all parts by default)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ffmpeg_path import find_ffmpeg  # noqa: E402

FONTS = HERE.parent / "assets/fonts"
W, H = 1080, 1920
VID_Y = 560
CAP_Y = 1210
LEAD = 0.6
DEFAULTS = {"pill": "PHẦN {part}/{total}", "hint": "Xem tiếp Phần {next} • Video đầy đủ ở bình luận",
            "hint_last": "Video đầy đủ: link ở bình luận", "out": "exports/shorts"}


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"BeVietnamPro-{name}.ttf"), size)


def read_srt(path):
    def sec(s):
        h, m, r = s.split(":")
        s, ms = r.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in Path(path).read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.strip().split("\n")
        a, b = lines[1].split(" --> ")
        cues.append((sec(a), sec(b), " ".join(lines[2:])))
    return cues


def cuts_from(cues, cfg):
    def find(prefix):
        hits = [i for i, c in enumerate(cues) if c[2].startswith(prefix)]
        assert len(hits) == 1, f"{prefix!r} starts {len(hits)} captions; use a longer prefix"
        return hits[0]
    cuts = []
    for prefix, _ in cfg["parts"]:
        i = find(prefix)
        cuts.append(0.0 if i == 0 else max(cues[i][0] - LEAD, cues[i - 1][1] + 0.15))
    j = find(cfg["stop_at"])
    cuts.append(cues[j - 1][1] + 0.9)
    return cuts


def centered(d, y, text, f, fill, sw=0):
    l, t, r, b = d.textbbox((0, 0), text, font=f, stroke_width=sw)
    d.text(((W - (r - l)) // 2 - l, y), text, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0))
    return b - t


def header_png(path, cfg, part, total):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    centered(d, 250, cfg["title"], font("ExtraBold", 96), (255, 255, 255), 6)
    pill = cfg["pill"].format(part=part, total=total)
    f = font("ExtraBold", 60)
    l, t, r, b = d.textbbox((0, 0), pill, font=f)
    pw, ph = r - l + 64, b - t + 32
    x0, y0 = (W - pw) // 2, 390
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=ph // 2, fill=(255, 205, 40))
    d.text((x0 + 32 - l, y0 + 16 - t), pill, font=f, fill=(20, 20, 20))
    hint = cfg["hint_last"] if part == total else cfg["hint"].format(next=part + 1)
    centered(d, 1580, hint, font("SemiBold", 40), (235, 235, 235), 3)
    im.save(path)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def split_long(cues):
    """Captions longer than 3 wrapped lines become several screens, timed by character count."""
    d, f = ImageDraw.Draw(Image.new("RGBA", (1, 1))), font("Bold", 56)
    out = []
    for a, b, text in cues:
        lines = wrap(d, text, f, 960)
        if len(lines) <= 3:
            out.append((a, b, text))
            continue
        n = -(-len(lines) // 3)
        per = -(-len(lines) // n)
        chunks = [" ".join(lines[k:k + per]) for k in range(0, len(lines), per)]
        total, t = sum(len(c) for c in chunks), a
        for c in chunks:
            t2 = t + (b - a) * len(c) / total
            out.append((t, t2, c))
            t = t2
    return out


def caption_png(path, text):
    im = Image.new("RGBA", (W, 320), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font("Bold", 56)
    y = 0
    lines = wrap(d, text, f, 960)
    assert len(lines) <= 3, text
    for ln in lines:
        y += centered(d, y, ln, f, (255, 255, 255), 5) + 14
    im.save(path)


def stamp(t):
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)) % 1000:03d}"


def build(cfg, src, srt_path, only=None, still=None):
    cues = read_srt(srt_path)
    cuts = cuts_from(cues, cfg)
    cues = split_long(cues)
    total = len(cuts) - 1
    ff = find_ffmpeg()
    for i in range(total):
        part, s, e = i + 1, cuts[i], cuts[i + 1]
        if only and part not in only:
            continue
        d = cfg["out"] / f"p{part}"
        d.mkdir(parents=True, exist_ok=True)
        header_png(d / "header.png", cfg, part, total)
        inputs, last = ["-i", str(d / "header.png")], "v1"
        chain = [f"[0:v]split[a][b];"
                 f"[a]scale=-2:480,crop=270:480,boxblur=12:2,scale={W}:{H},eq=brightness=-0.18[bg];"
                 f"[b]scale={W}:608[fg];[bg][fg]overlay=0:{VID_Y}[v0];[v0][1:v]overlay=0:0[v1]"]
        n, sub = 2, []
        for a, b, text in cues:
            if b <= s or a >= e:
                continue
            a2, b2 = max(a, s) - s, min(b, e) - s
            p = d / f"cap{n:02d}.png"
            caption_png(p, text)
            inputs += ["-i", str(p)]
            chain.append(f"[{last}][{n}:v]overlay=0:{CAP_Y}:enable='between(t,{a2:.3f},{b2:.3f})'[v{n}]")
            last = f"v{n}"
            sub.append((a2, b2, text))
            n += 1
        L = e - s
        if still is not None:
            out = d / f"still-{still:.1f}.png"
            subprocess.run([ff, "-y", "-v", "error", "-ss", f"{s:.3f}", "-t", f"{L:.3f}", "-i", str(src), *inputs,
                            "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-ss", f"{still:.3f}",
                            "-frames:v", "1", str(out)], check=True)
            print(out)
            continue
        chain.append(f"[{last}]format=yuv420p[vout];"
                     f"[0:a]afade=t=in:d=0.15,afade=t=out:st={L - 0.5:.3f}:d=0.5[aout]")
        name = f"Phan {part} - {cfg['parts'][i][1].replace(':', ' -').replace('?', '').replace('/', '-')}"
        out = d / f"{name}.mp4"
        assert not out.exists(), f"{out} exists"
        subprocess.run(["nice", "-n", "10", ff, "-v", "error", "-ss", f"{s:.3f}", "-t", f"{L:.3f}",
                        "-i", str(src), *inputs, "-filter_complex", ";".join(chain), "-map", "[vout]",
                        "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", "60",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
        with open(d / f"{name}.srt", "w", encoding="utf-8") as fh:
            for k, (a2, b2, text) in enumerate(sub, 1):
                fh.write(f"{k}\n{stamp(a2)} --> {stamp(b2)}\n{text}\n\n")
        print(part, f"{s:.1f}-{e:.1f}", f"{L:.1f}s", out, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", type=Path)
    ap.add_argument("src", type=Path, help="final episode mp4")
    ap.add_argument("srt", type=Path, help="its subtitles (one caption per sentence)")
    ap.add_argument("parts", nargs="*", type=int)
    ap.add_argument("--cuts", action="store_true", help="only print the cut list")
    ap.add_argument("--still", nargs=2, metavar=("PART", "T"), help="write one preview PNG")
    args = ap.parse_args()
    cfg = {**DEFAULTS, **json.loads(args.config.read_text())}
    cfg["out"] = (args.config.resolve().parent / cfg["out"]).resolve()
    if args.cuts:
        c = cuts_from(read_srt(args.srt), cfg)
        for i in range(len(c) - 1):
            print(f"Phần {i + 1}: {c[i]:7.2f} → {c[i + 1]:7.2f}  ({c[i + 1] - c[i]:5.1f} s)  {cfg['parts'][i][1]}")
    elif args.still:
        build(cfg, args.src, args.srt, [int(args.still[0])], still=float(args.still[1]))
    else:
        build(cfg, args.src, args.srt, args.parts or None)


if __name__ == "__main__":
    main()
