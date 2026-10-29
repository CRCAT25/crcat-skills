# Episode settings shared by the audio and caption scripts: episode.json + the film length from phim3d/film.js.
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'episode.json')))
SPEED = CFG['speed']
FILM_END = float(re.findall(r't1:\s*([\d.]+)', open(os.path.join(ROOT, 'phim3d', 'film.js')).read())[-1])
LENGTH = round(FILM_END / SPEED, 3)          # final (sped-up) length in seconds
NUDGE = {int(k): v for k, v in CFG.get('nudge', {}).items()}   # line index -> start time (final time) overriding lines.json
TAKE2 = set(CFG.get('take2', []))            # line indexes that use the second ElevenLabs take
DIPS = [tuple(d) for d in CFG.get('dips', [])]   # (start, end) in final time: music near silent, the SFX carry the moment
SPELL = CFG.get('spell', {})                 # voice spelling -> caption spelling
VO = os.path.join(ROOT, 'audio', 'vo')
TRIM = ('silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,'
        'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.15,areverse')


def lines():
    return json.load(open(os.path.join(VO, 'lines.json')))['lines']


def take(i):
    return os.path.join(VO, 'el_dl', f'{i:02d}_{"g2" if i in TAKE2 else "g1"}.mp3')


def start(i, ls):
    return NUDGE.get(i, ls[i]['t'])
