#!/usr/bin/env python3
"""Locate an FFmpeg binary without assuming it is on PATH.

Order: $FFMPEG, PATH, imageio_ffmpeg (if importable), then any imageio-ffmpeg
binary already present in the uv cache. Never installs anything.
"""
import glob
import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(None)
def find_ffmpeg():
    env = os.environ.get("FFMPEG")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    pattern = str(Path.home() / ".cache/uv/archive-v0/*/lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-*")
    candidates = [p for p in glob.glob(pattern) if os.access(p, os.X_OK)]
    if candidates:
        return max(candidates, key=os.path.getmtime)
    raise FileNotFoundError(
        "FFmpeg not found. Set $FFMPEG, put ffmpeg on PATH, or run with "
        "`uv run --offline --no-project --with imageio-ffmpeg ...`."
    )


if __name__ == "__main__":
    try:
        print(find_ffmpeg())
    except FileNotFoundError as error:
        sys.exit(str(error))
