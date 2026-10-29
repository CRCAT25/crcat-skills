# Nature SFX bed from licensed library files only (lib/LICENSES.md): python3 mix.py sfx.wav
# Times are FILM time (before the speed-up); music_bed.py plays this at the episode speed.
# Each cue: (file, start s, source offset s, length s, gain dB, fade in s, fade out s[, extra ffmpeg filters])
import subprocess, sys, os
from episode import FILM_END

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
M = lambda n: os.path.join(LIB, 'music', n)
S = lambda n: os.path.join(LIB, 'sfx', n)
far = lambda hz: f'lowpass=f={hz}'                                                         # distance
pitch = lambda r, hz=20000: f'asetrate={int(48000 * r)},aresample=48000,lowpass=f={hz}'   # slower + deeper (r < 1)

CUES = [
    # (S('freesound-385098_volcano_morganpurkis.mp3'), 2.0, 0.0, 22.0, -18, 4.0, 4.0, far(300)),
]


def build(out, to):
    cues = [c for c in CUES if c[1] < to]
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
