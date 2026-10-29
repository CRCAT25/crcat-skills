#!/usr/bin/env python3
"""Scaffold a new Mẹ Thiên Nhiên 3D film episode from the skill's template/.

python3 init_film.py <slug> --title "Tiêu đề" [--root DIR] [--from trai-dat-hinh-thanh] [--no-audio-lib]

Creates <root>/<slug>/ (root: --root, else $MTN_ROOT, else ./ai-video-projects) (no date in the name). node_modules (three + playwright-core) and the licensed
audio library (audio/lib with LICENSES.md) are cloned from the previous episode (--from) so the setup works offline;
without a previous episode, node_modules comes from `npm install`.
"""
import argparse, json, os, shutil, subprocess
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / 'template'


def clone(src, dst):
    # APFS clone: instant and takes no extra space; plain copy elsewhere
    if subprocess.run(['cp', '-cR', str(src), str(dst)]).returncode:
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, symlinks=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slug')
    ap.add_argument('--title', default='')
    ap.add_argument('--root', default=os.environ.get('MTN_ROOT', 'ai-video-projects'))
    ap.add_argument('--from', dest='prev', default='trai-dat-hinh-thanh')
    ap.add_argument('--no-audio-lib', action='store_true')
    a = ap.parse_args()

    root = Path(a.root).expanduser().resolve()
    out = root / a.slug
    if out.exists():
        ap.error(f'{out} already exists')
    shutil.copytree(TEMPLATE, out)
    cfg = json.loads((out / 'episode.json').read_text())
    cfg['title'] = a.title
    (out / 'episode.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n')

    prev = root / a.prev
    nm = prev / 'phim3d' / 'node_modules'
    if nm.is_dir():
        clone(nm, out / 'phim3d' / 'node_modules')
    else:
        subprocess.run(['npm', 'install', '--no-audit', '--no-fund'], cwd=out / 'phim3d', check=True)
    lib = prev / 'audio' / 'lib'
    if not a.no_audio_lib and lib.is_dir():
        shutil.rmtree(out / 'audio' / 'lib')
        clone(lib, out / 'audio' / 'lib')
    for d in ('exports', 'audio/vo/el_dl', 'review'):
        (out / d).mkdir(parents=True, exist_ok=True)
    print(out)


if __name__ == '__main__':
    main()
