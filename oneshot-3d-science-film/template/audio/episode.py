# Episode settings shared by the audio and caption scripts: episode.json + the film length from phim3d/film.js.
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'episode.json')))
SPEED = CFG['speed']
_FILM = re.sub(r'//.*', '', open(os.path.join(ROOT, 'phim3d', 'film.js')).read())   # skip commented-out scenes
HOLDS = json.loads(re.search(r'HOLDS = (\[.*\]);', _FILM).group(1))   # slow-motion holds, see film.js
FILM_END = float(re.findall(r't1:\s*([\d.]+)', _FILM)[-1]) + sum(d for a, d in HOLDS)   # timeline length incl. holds
LENGTH = round(FILM_END / SPEED, 3)          # final (sped-up) length in seconds
NUDGE = {int(k): v for k, v in CFG.get('nudge', {}).items()}   # line index -> start time (final time) overriding lines.json
TAKE2 = set(CFG.get('take2', []))            # line indexes that use the second ElevenLabs take
DIPS = [tuple(d) for d in CFG.get('dips', [])]   # (start, end) in final time: music near silent, the SFX carry the moment
SPELL = CFG.get('spell', {})                 # voice spelling -> caption spelling


def _S(x):
    return x * x * (3 - 2 * x)


def unhold(n):
    """Timeline film time -> scene film time (same as film.js)."""
    off = 0
    for a, d in HOLDS:
        s, L = a + off, 2.5 * d
        if n < s:
            break
        if n < s + L:
            return n - off - d * _S((n - s) / L)
        off += d
    return n - off


def hold(t):
    """Scene film time -> timeline film time (inverse of unhold)."""
    lo, hi = t, t + sum(d for a, d in HOLDS)
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if unhold(m) < t else (lo, m)
    return round((lo + hi) / 2, 3)


def hold_final(t):
    """Same as hold() for final (sped-up) times."""
    return round(hold(t * SPEED) / SPEED, 3)


VO = os.path.join(ROOT, 'audio', 'vo')
TRIM = ('silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,'
        'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.15,areverse')


def lines():
    return json.load(open(os.path.join(VO, 'lines.json')))['lines']


def take(i):
    return os.path.join(VO, 'el_dl', f'{i:02d}_{"g2" if i in TAKE2 else "g1"}.mp3')


def start(i, ls):
    return NUDGE.get(i, ls[i]['t'])
