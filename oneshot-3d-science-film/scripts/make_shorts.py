#!/usr/bin/env python3
"""Cut a delivered episode into vertical ~1 min Shorts (Phần 1..N), with burned captions and a per-part .srt.

python3 make_shorts.py <video.mp4> --title "SIÊU BÃO" --cuts 0,58.5,112,174,217 [--key tap03] [--out DIR] [--parts 2,3]

The episode's .srt must sit next to the .mp4 (same name). Cut at the end of a narration line, ideally on a question
or a cliffhanger (Phần 1-2), each part 40-62 s; the last part runs to the end. Output: <out>/<key>/p<n>/<key>-phan<n>.mp4
+ .srt (upload both; the srt is the Short's subtitle track).
Layout 1080x1920: blurred background, full 16:9 frame in the middle, title + "PHẦN x/y" on top, burned captions
below, a "phim đầy đủ ở bình luận" hint. Fonts: Be Vietnam Pro (OFL) from the skill's assets/fonts.
"""
import argparse, os, subprocess
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'fonts')
OUT = 'shorts'
W, H = 1080, 1920
VID_Y = 560            # top of the 1080x608 landscape frame
CAP_Y = 1210           # caption block top


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, f'BeVietnamPro-{name}.ttf'), size)


def srt(path):
    def ts(s):
        h, m, r = s.split(':'); sec, ms = r.split(',')
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000
    cues = []
    for block in open(path, encoding='utf-8').read().strip().split('\n\n'):
        lines = block.strip().split('\n')
        a, b = lines[1].split(' --> ')
        cues.append((ts(a), ts(b), ' '.join(lines[2:])))
    return cues


def centered(d, y, text, f, fill, sw=0):
    l, t, r, b = d.textbbox((0, 0), text, font=f, stroke_width=sw)
    d.text(((W - (r - l)) // 2 - l, y), text, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0))
    return b - t


def header_png(path, title, part, total):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    centered(d, 250, title, font('ExtraBold', 96), (255, 255, 255), 6)
    pill = f'PHẦN {part}/{total}'
    f = font('ExtraBold', 60)
    l, t, r, b = d.textbbox((0, 0), pill, font=f)
    pw, ph = r - l + 64, b - t + 32
    x0, y0 = (W - pw) // 2, 390
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=ph // 2, fill=(255, 205, 40))
    d.text((x0 + 32 - l, y0 + 16 - t), pill, font=f, fill=(20, 20, 20))
    hint = 'Phim đầy đủ: link ở bình luận' if part == total else f'Xem tiếp Phần {part + 1} • Phim đầy đủ ở bình luận'
    centered(d, 1470, hint, font('SemiBold', 40), (235, 235, 235), 3)
    im.save(path)


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def caption_png(path, text):
    im = Image.new('RGBA', (W, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font('Bold', 56)
    lines = wrap(d, text, f, 960)
    y = 0
    for ln in lines[:3]:
        y += centered(d, y, ln, f, (255, 255, 255), 5) + 14
    im.save(path)


def build(key, ep, only=None):
    src = ep['src']
    cues = srt(src + '.srt')
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                         '-of', 'csv=p=0', src + '.mp4']).decode())
    cuts = ep['cuts'][:-1] + [dur]
    total = len(cuts) - 1
    for i in range(total):
        part, s, e = i + 1, cuts[i], cuts[i + 1]
        if only and part not in only:
            continue
        d = os.path.join(OUT, key, f'p{part}')
        os.makedirs(d, exist_ok=True)
        header_png(os.path.join(d, 'header.png'), ep['title'], part, total)
        inputs, chain, last = ['-i', os.path.join(d, 'header.png')], [], 'v1'
        chain.append(f'[0:v]split[a][b];'
                     f'[a]scale=-2:480,crop=270:480,boxblur=12:2,scale={W}:{H},eq=brightness=-0.18[bg];'
                     f'[b]scale={W}:608[fg];[bg][fg]overlay=0:{VID_Y}[v0];[v0][1:v]overlay=0:0[v1]')
        n = 2
        sub = []
        for (a, b, text) in cues:
            if b <= s or a >= e:
                continue
            a2, b2 = max(a, s) - s, min(b, e) - s
            p = os.path.join(d, f'cap{n:02d}.png')
            caption_png(p, text)
            inputs += ['-i', p]
            chain.append(f"[{last}][{n}:v]overlay=0:{CAP_Y}:enable='between(t,{a2:.3f},{b2:.3f})'[v{n}]")
            last = f'v{n}'
            sub.append((a2, b2, text))
            n += 1
        L = e - s
        chain.append(f'[{last}]format=yuv420p[vout];[0:a]afade=t=in:d=0.15,afade=t=out:st={L - 0.5:.3f}:d=0.5[aout]')
        out = os.path.join(d, f'{key}-phan{part}.mp4')
        cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', f'{s:.3f}', '-t', f'{L:.3f}', '-i', src + '.mp4', *inputs,
               '-filter_complex', ';'.join(chain), '-map', '[vout]', '-map', '[aout]',
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-r', '60',
               '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out]
        subprocess.run(cmd, check=True)
        with open(os.path.join(d, f'{key}-phan{part}.srt'), 'w', encoding='utf-8') as fh:
            for k, (a2, b2, text) in enumerate(sub, 1):
                f = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)) % 1000:03d}'
                fh.write(f'{k}\n{f(a2)} --> {f(b2)}\n{text}\n\n')
        print(key, part, f'{s:.1f}-{e:.1f}', f'{L:.1f}s', out, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--title', required=True)
    ap.add_argument('--cuts', required=True, help='part starts in seconds, e.g. 0,58.5,112')
    ap.add_argument('--key', default='short')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--parts', default='')
    a = ap.parse_args()
    OUT = a.out
    build(a.key, dict(src=os.path.splitext(a.video)[0], title=a.title,
                      cuts=[float(x) for x in a.cuts.split(',')] + [None]),
          [int(x) for x in a.parts.split(',') if x] or None)
