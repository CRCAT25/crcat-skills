# Nature SFX bed from licensed library files only (lib/LICENSES.md): python3 mix.py sfx.wav
# Times are FILM time (before the speed-up) in scene time; build() moves them onto the timeline with the film.js holds.
# music_bed.py plays this at the episode speed.
# Each cue: (file, start s, source offset s, length s, gain dB, fade in s, fade out s[, extra ffmpeg filters])
import subprocess, sys, os
from episode import FILM_END, hold

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
M = lambda n: os.path.join(LIB, 'music', n)
S = lambda n: os.path.join(LIB, 'sfx', n)
far = lambda hz: f'lowpass=f={hz}'                                                         # distance
pitch = lambda r, hz=20000: f'asetrate={int(48000 * r)},aresample=48000,lowpass=f={hz}'   # slower + deeper (r < 1)

class Tiled(tuple):
    """A bed tile: already on the timeline."""


def bed(f, t0, t1, flen, db, fi=2.0, fo=2.0, fx=None, off=0.0):
    """Tile a short loop from t0 to t1 with 1.5 s crossfades (source window off..flen)."""
    t0, t1 = hold(t0), hold(t1)
    out, t, step = [], t0, flen - off - 1.5
    while t < t1:
        ln = min(flen - off, t1 - t)
        first, last = t == t0, t + ln >= t1
        out.append(Tiled((f, t, off, ln, db, fi if first else 1.5, fo if last else 1.5, *([fx] if fx else []))))
        t += step
    return out


WIND = S('mixkit-2407_strong-wild-wind-in-a-storm.wav')
RAIN = S('mixkit-2400_heavy-storm-rain-loop.wav')
HUM = S('mixkit-1177_deep-cinematic-wind-hum.wav')
ROUGH = S('mixkit-1194_rough-sea-waves-loop.wav')
BREAK = S('mixkit-1206_sea-coast-breaking-waves.wav')
LAP = S('freesound-318064_water-lapping-river_ceich93.mp3')

CUES = [
    # s01 0-9: inside the eyewall, ends in a white flash at ~8.6
    *bed(WIND, 0.0, 9.4, 13.65, -3, fi=0.3, fo=0.6),
    *bed(RAIN, 0.0, 9.4, 18.0, -8, fi=0.3, fo=0.6),
    (S('mixkit-1300_strong-close-thunder-explosion.wav'), 8.45, 0.0, 6.5, -1, 0.0, 3.5),
    # s02 9-30: a glassy, too-warm sea
    (S('freesound-218387_calm-waves-beach_motion-s.mp3'), 9.5, 0.0, 22.0, -15, 2.5, 3.0),
    (S('mixkit-2658_wind-blowing-ambience.wav'), 10.0, 0.0, 21.0, -26, 4.0, 3.0),
    # s03-s04b 30-102: from orbit, the storm forms and winds up
    (HUM, 29.0, 0.0, 40.0, -16, 4.0, 3.0),
    (S('mixkit-1301_distant-long-thunder-rumble.wav'), 40.0, 0.0, 14.0, -18, 0.5, 4.0, far(900)),
    (S('mixkit-1301_distant-long-thunder-rumble.wav'), 55.0, 0.0, 14.0, -16, 0.5, 4.0, far(900)),
    (S('mixkit-2343_cinematic-whoosh-magic-gust.wav'), 64.0, 0.0, 7.5, -12, 0.5, 3.0),
    (HUM, 66.0, 6.0, 38.0, -11, 3.0, 3.0),
    *bed(S('mixkit-2413_dark-storm-wind.wav'), 72.0, 101.0, 3.38, -14, fi=4.0, fo=3.0, fx=far(1500)),
    (S('mixkit-1297_big-thunder-rumble.wav'), 92.0, 0.0, 12.0, -14, 0.3, 4.0, far(1200)),
    # s05 102-120: the eyewall reaches the island
    *bed(WIND, 101.0, 191.0, 13.65, -5, fi=3.0, fo=4.5),
    (ROUGH, 101.0, 0.0, 44.0, -8, 3.0, 4.0),
    *bed(RAIN, 104.0, 192.0, 18.0, -9, fi=3.0, fo=5.0),
    # s05b 120-142: the village in the wind
    (S('mixkit-1280_cinematic-thunder-hit.wav'), 127.0, 0.0, 12.0, -6, 0.0, 4.0),
    (S('mixkit-2407_strong-wild-wind-in-a-storm.wav'), 132.0, 0.0, 13.0, -9, 2.0, 3.0, pitch(0.85)),
    # s06 142-187: the surge
    (BREAK, 140.0, 0.0, 48.0, -5, 4.0, 5.0),
    (ROUGH, 143.0, 30.0, 40.0, -9, 3.0, 4.0),
    (S('mixkit-1297_big-thunder-rumble.wav'), 160.0, 0.0, 14.0, -10, 0.3, 4.0),
    # s07 187-217: the eye passes over, calm (wind fades over the first 5 s)
    (LAP, 189.0, 0.0, 28.0, -12, 3.0, 2.0),
    (S('mixkit-1301_distant-long-thunder-rumble.wav'), 200.0, 0.0, 14.0, -22, 1.0, 4.0, far(700)),
    (S('mixkit-1474_transition-windy-swoosh.wav'), 215.0, 0.0, 3.2, -6, 0.3, 1.0),
    # s08 217-242: the back eyewall, wind from the other side
    *bed(WIND, 216.5, 244.0, 13.65, -3, fi=1.0, fo=4.0),
    *bed(RAIN, 217.0, 244.0, 18.0, -8, fi=1.0, fo=4.0),
    (ROUGH, 217.0, 10.0, 27.0, -9, 1.0, 4.0),
    (S('mixkit-1300_strong-close-thunder-explosion.wav'), 221.0, 0.0, 8.0, -3, 0.0, 3.0),
    (S('freesound-434359_close-lightning-strike_csengeri.mp3'), 231.0, 2.0, 8.0, -7, 0.0, 3.0),
    # s09 242-270: dawn after the storm
    (S('freesound-518670_dawn-chorus-distant-ocean_jackmichaelking.mp3'), 242.0, 5.0, 29.0, -12, 4.0, 4.0),
    (LAP, 242.0, 28.0, 29.0, -14, 4.0, 4.0),
    # s10 270-290: from orbit again, new towers gather
    (HUM, 269.0, 0.0, 21.0, -18, 3.0, 4.0),
    (S('mixkit-1301_distant-long-thunder-rumble.wav'), 278.0, 0.0, 12.0, -22, 1.0, 4.0, far(800)),
]


def src_len(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout)


def place(c):
    """A one-shot cue keeps its sound; a hold inside it only lengthens it (as far as the source file goes)."""
    if isinstance(c, Tiled):
        return c
    f, st, off, ln, *rest = c
    a, b = hold(st), hold(st + ln)
    return (f, a, off, min(b - a, src_len(f) - off), *rest)


def build(out, to):
    cues = [c for c in map(place, CUES) if c[1] < to]
    args = ['ffmpeg', '-y', '-v', 'error']
    parts = []
    for i, (f, st, off, ln, db, fi, fo, *fx) in enumerate(cues):
        ln = min(ln, to - st)
        args += ['-ss', str(off), '-t', str(ln), '-i', f]
        fo = min(fo, ln)
        fx = f'{fx[0]},' if fx else ''
        parts.append(
            f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,{fx}volume={db}dB,'
            f'afade=t=in:d={fi},afade=t=out:st={max(ln - fo, 0):.3f}:d={fo},adelay={int(st * 1000)}:all=1[a{i}]')
    mix = ''.join(f'[a{i}]' for i in range(len(cues)))
    parts.append(f'{mix}amix=inputs={len(cues)}:normalize=0:dropout_transition=0,'
                 f'apad,atrim=0:{to},alimiter=limit=0.89:level=false,loudnorm=I=-16:TP=-1.5:LRA=11[out]')
    tmp = out + '.tmp.wav'
    args += ['-filter_complex', ';'.join(parts), '-map', '[out]', '-ar', '48000', tmp]
    subprocess.run(args, check=True)
    # single-pass loudnorm misses the target by ~1 LU: measure and trim linearly to -16 integrated
    r = subprocess.run(['ffmpeg', '-nostats', '-i', tmp, '-af', 'ebur128', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    i = float(r.split('Integrated loudness:')[1].split('I:')[1].split('LUFS')[0])
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', tmp, '-af', f'volume={-16 - i:.2f}dB', out], check=True)
    os.remove(tmp)


if __name__ == '__main__':
    to = float(sys.argv[sys.argv.index('--to') + 1]) if '--to' in sys.argv else FILM_END
    build(sys.argv[1], to)
