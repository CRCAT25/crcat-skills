#!/usr/bin/env python3
"""Technical QA of an encoded export (from the iPhone V20 QA): decode, per-second frames,
static-run check, contact sheets, frame-by-frame transition and flash sheets, encoded loudness.
Landscape 1920x1080 by default (YouTube long-form); pass --size 1080x1920 for a Short.

  uv run --offline --no-project --with pillow python qa_export.py exports/final-v01.mp4 \
      --out-dir tmp/qa-v01 --duration 480 --fps 30 --timeline audio/sfx-events-v01.json \
      --report exports/qa-v01.json

Long videos: the static check still uses every second, but contact sheets show one frame every
--sheet-every seconds (default: 1 s up to 90 s, else 5 s) so 8 minutes fit on a few pages.

--timeline accepts sfx_timeline.py output (bounds + flashes) or pacing JSON (bounds).
Exits 1 when a check fails. The report always keeps visual_inspection="pending" and
audible_listening=false: look at the sheets and listen before calling the video finished.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_path import find_ffmpeg  # noqa: E402


def sheet(paths, out, cols, tile, labels):
    rows = -(-len(paths) // cols)
    im = Image.new("RGB", (cols * (tile[0] + 6), rows * (tile[1] + 22)), (8, 13, 22))
    d = ImageDraw.Draw(im)
    for n, p in enumerate(paths):
        t = Image.open(p)
        t.thumbnail(tile)
        x, y = n % cols * (tile[0] + 6), n // cols * (tile[1] + 22)
        im.paste(t, (x, y + 20))
        d.text((x + 2, y + 3), labels[n], fill="white")
    im.save(out, quality=92)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--region", help="foreground crop x0,y0,x1,y1 for the static check (excludes captions); "
                    "default 160,80,1760,820 landscape / 60,340,1020,1170 vertical")
    ap.add_argument("--sheet-every", type=int, help="seconds between contact-sheet frames")
    ap.add_argument("--static-diff", type=float, default=0.05)
    ap.add_argument("--max-static-run", type=int, default=3, help="consecutive near-identical seconds allowed (exclusive)")
    ap.add_argument("--min-contrast", type=float, default=8)
    ap.add_argument("--lufs", type=float, default=-14)
    ap.add_argument("--lufs-tolerance", type=float, default=0.35)
    ap.add_argument("--max-true-peak", type=float, default=-1.0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if args.report.exists() and not args.overwrite:
        ap.error(f"refusing to overwrite {args.report}")
    for p in [args.video] + ([args.timeline] if args.timeline else []):
        if not p.is_file():
            ap.error(f"not found: {p}")
    vw, vh = (int(v) for v in args.size.split("x"))
    landscape = vw > vh
    args.region = args.region or ("160,80,1760,820" if landscape else "60,340,1020,1170")
    tile = (384, 216) if landscape else (260, 462)
    cut_scale, cut_tile = ("384:216", (240, 135)) if landscape else ("216:384", (135, 240))
    flash_scale, flash_tile = ("640:360", (640, 360)) if landscape else ("360:640", (360, 640))
    sheet_every = args.sheet_every or (1 if args.duration <= 90 else 5)
    ff = find_ffmpeg()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    failures = []

    def check(ok, message):
        if not ok:
            failures.append(message)
        return ok

    # 1. Full decode: no errors, exact frame count, header matches.
    decoded = subprocess.run([ff, "-v", "error", "-i", str(args.video), "-progress", "pipe:1", "-f", "null", "-"], capture_output=True, text=True)
    frames = int(re.findall(r"frame=(\d+)", decoded.stdout)[-1]) if "frame=" in decoded.stdout else 0
    expected_frames = round(args.duration * args.fps)
    check(decoded.returncode == 0 and not decoded.stderr.strip(), f"decode errors: {decoded.stderr[:300]}")
    check(abs(frames - expected_frames) <= 1, f"frames {frames} != {expected_frames}")

    # 2. One frame per second + header info.
    step = args.fps
    log = subprocess.run([ff, "-hide_banner", "-y", "-i", str(args.video), "-vf", f"select=not(mod(n\\,{step}))",
                          "-fps_mode", "vfr", "-q:v", "3", str(out / "second-%03d.jpg")], capture_output=True, text=True)
    (out / "decode.log").write_text(log.stderr)
    check(args.size in log.stderr, f"resolution is not {args.size}")
    check(re.search(rf"\b{args.fps} fps", log.stderr) is not None, f"stream is not {args.fps} fps")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log.stderr)
    container = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    check(container is not None and abs(container - args.duration) < 0.05, f"container duration {container}")
    seconds = sorted(out.glob("second-*.jpg"))

    # 3. Static foreground runs (subtitle area excluded by --region).
    box = tuple(int(v) for v in args.region.split(","))
    diffs = []
    for a, b in zip(seconds, seconds[1:]):
        aa = Image.open(a).crop(box).resize((240, 210))
        bb = Image.open(b).crop(box).resize((240, 210))
        diffs.append(sum(ImageStat.Stat(ImageChops.difference(aa, bb)).mean) / 3)
    run = maxrun = 0
    for v in diffs:
        run = run + 1 if v < args.static_diff else 0
        maxrun = max(maxrun, run)
    check(maxrun < args.max_static_run, f"foreground static for {maxrun} consecutive seconds")
    picked = list(range(0, len(seconds), sheet_every))
    for page in range(0, len(picked), 20):
        chunk = picked[page:page + 20]
        sheet([seconds[k] for k in chunk], out / f"contact-{page // 20 + 1}.jpg", 5, tile,
              [f"{k // 60}:{k % 60:02}" for k in chunk])

    # 4. Transitions and flashes, frame by frame from the encoded file.
    bounds, flashes = [], []
    if args.timeline:
        tl = json.loads(args.timeline.read_text(encoding="utf-8"))
        bounds, flashes = tl.get("bounds", []), tl.get("flashes", [])
    min_contrast = None
    for i, cut in enumerate(bounds[1:-1], 1):
        folder = out / f"cut-{i:02}"
        folder.mkdir(exist_ok=True)
        start = max(0, cut - 0.35)
        subprocess.run([ff, "-v", "error", "-y", "-ss", f"{start:.4f}", "-i", str(args.video), "-t", "0.9",
                        "-vf", f"fps={args.fps},scale={cut_scale}", "-q:v", "3", str(folder / "shot-%02d.jpg")], check=True)
        shots = sorted(folder.glob("shot-*.jpg"))
        for n, f in enumerate(shots):
            im = Image.open(f)
            c = max(ImageStat.Stat(im.crop((2, 2, im.width - 2, int(im.height * 0.68)))).stddev)
            min_contrast = c if min_contrast is None else min(c, min_contrast)
            check(c > args.min_contrast, f"cut {i} frame {n}: near-empty frame (contrast {c:.1f})")
        sheet(shots, out / f"cut-{i:02}-all-frames.jpg", 9, cut_tile, [f"{start + n / args.fps:.3f}s" for n in range(len(shots))])
    for j, fl in enumerate(flashes):
        n = round(fl["time"] * args.fps)
        folder = out / f"flash-{j:02}"
        folder.mkdir(exist_ok=True)
        subprocess.run([ff, "-v", "error", "-y", "-i", str(args.video), "-vf", f"select=between(n\\,{n - 2}\\,{n + 3}),scale={flash_scale}",
                        "-fps_mode", "vfr", "-frames:v", "6", "-q:v", "2", str(folder / "shot-%02d.jpg")], check=True)
        shots = sorted(folder.glob("shot-*.jpg"))
        sheet(shots, out / f"flash-{j:02}-frames.jpg", 6, flash_tile, [f"{(n - 2 + k) / args.fps:.3f}s" for k in range(len(shots))])

    # 5. Encoded loudness (measured on the AAC track actually delivered).
    stats = subprocess.run([ff, "-hide_banner", "-i", str(args.video), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True)
    loud = json.loads(stats.stderr[stats.stderr.rfind("{"): stats.stderr.rfind("}") + 1]) if stats.returncode == 0 else {}
    tp, lufs = float(loud.get("input_tp", 99)), float(loud.get("input_i", -99))
    check(tp <= args.max_true_peak, f"true peak {tp} > {args.max_true_peak}")
    check(abs(lufs - args.lufs) <= args.lufs_tolerance, f"integrated {lufs} LUFS not within {args.lufs_tolerance} of {args.lufs}")

    report = dict(video=str(args.video), duration_seconds=args.duration, container_duration=container, size=args.size, fps=args.fps,
                  decoded_frames=frames, expected_frames=expected_frames, frames_sampled=len(seconds),
                  foreground_static_run_seconds=maxrun, foreground_difference_minimum_1s=min(diffs) if diffs else None,
                  transitions_checked=max(0, len(bounds) - 2), minimum_transition_frame_contrast=min_contrast,
                  flash_sample_sets=len(flashes), encoded_audio_integrated_lufs=lufs, encoded_audio_true_peak_dbfs=tp,
                  qa_dir=str(out), failures=failures, passed=not failures,
                  audible_listening=False, visual_inspection="pending")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
