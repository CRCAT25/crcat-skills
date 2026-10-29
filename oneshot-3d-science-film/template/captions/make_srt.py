# SRT for the final cut, timed from the ElevenLabs takes as placed by audio/vo/build_el.py: python3 make_srt.py final.srt
# Long lines split at sentence/comma breaks, time shared by character count; voice spellings mapped back (episode.json "spell").
import re, subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audio'))
from episode import TRIM, SPELL, lines, take, start


def dur(f):
    pcm = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', f, '-af', TRIM, '-f', 'f32le', '-ac', '1', '-ar', '16000', '-'],
                         capture_output=True, check=True).stdout
    return len(pcm) / 4 / 16000


def ts(t):
    ms = int(round(t * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def chunks(text, n=60):
    out = []
    for p in [p for p in re.split(r'(?<=[.!?])\s+', text) if p]:
        while len(p) > n and ', ' in p[:n + 10]:
            k = p.rfind(', ', 0, n + 10) + 1
            out.append(p[:k]); p = p[k:].strip()
        out.append(p)
    return out


ls, cues = lines(), []
for i, l in enumerate(ls):
    t, d = start(i, ls), dur(take(i))
    text = l['text']
    for a, b in SPELL.items():
        text = text.replace(a, b)
    cs = chunks(text)
    tot = sum(len(c) for c in cs)
    for c in cs:
        cd = d * len(c) / tot; cues.append((t, t + cd, c)); t += cd
with open(sys.argv[1], 'w') as f:
    for k, (a, b, c) in enumerate(cues, 1):
        nxt = cues[k][0] if k < len(cues) else 1e9
        f.write(f'{k}\n{ts(a)} --> {ts(min(b + 0.15, nxt - 0.05))}\n{c}\n\n')
print(len(cues), 'cues, last ends', round(cues[-1][1], 2))
