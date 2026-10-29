# Final soundtrack: SFX bed (film time, played at the episode speed) ducked under the narration + a light music bed
# + the narration, normalised to -16 LUFS. python3 music_bed.py out.wav [--track file.mp3 --body 10:234] [--to 42]
# The music loops its body (the steady part after the intro) with a crossfade, drops 11 dB while the narration speaks
# (down 0.3 s before each phrase, back up over 1 s after) and to near silence through the DIPS in episode.json.
# Without --track it uses episode.json "music". Preview several tracks with --to 42 for the user to choose.
import subprocess, sys, os, re
import numpy as np
from episode import CFG, LENGTH, DIPS, SPEED, ROOT

SFX = os.path.join(ROOT, 'audio', 'sfx.wav')
VO = os.path.join(ROOT, 'audio', 'vo', 'vo_el.wav')
XF, RATE = 3.0, 1000
DUCK_DB, LEAD, RELEASE, DIP_DB = -11.0, 0.3, 1.0, -24.0


def run(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True)


def speech():
    err = run('ffmpeg', '-nostats', '-i', VO, '-af', 'silencedetect=n=-40dB:d=0.6', '-f', 'null', '-').stderr
    st = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', err)]
    en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', err)]
    edges = [0.0] + [v for pair in zip(st, en) for v in pair] + [LENGTH]
    return [(edges[i], edges[i + 1]) for i in range(0, len(edges) - 1, 2) if edges[i + 1] > edges[i]]


def envelope(path):
    t = np.arange(int(LENGTH * RATE)) / RATE
    duck = np.zeros_like(t)
    for a, b in speech():
        duck = np.maximum(duck, np.clip(np.minimum((t - (a - LEAD)) / LEAD, ((b + RELEASE) - t) / RELEASE), 0, 1))
    dip = np.zeros_like(t)
    for a, b in DIPS:
        dip = np.maximum(dip, np.clip(np.minimum(t - (a - 1), (b + 1.5) - t), 0, 1))
    g = (10 ** ((DUCK_DB * duck * (1 - dip) + DIP_DB * dip) / 20)).astype('<f4')
    open(path + '.raw', 'wb').write(g.tobytes())
    run('ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(RATE), '-ac', '1', '-i', path + '.raw', path)
    os.remove(path + '.raw')


def loudness(track, a, b):
    err = run('ffmpeg', '-nostats', '-ss', str(a), '-t', str(b - a), '-i', track, '-af', 'ebur128', '-f', 'null', '-').stderr
    return float(err.split('Integrated loudness:')[1].split('I:')[1].split('LUFS')[0])


def build(track, body, out, to, lufs=-21.0):
    s0, s1 = body
    gain = lufs - loudness(track, s0, s1)
    n = int(LENGTH // (s1 - s0 - XF)) + 1
    parts = [f'[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit={n}' + ''.join(f'[r{i}]' for i in range(n))]
    parts += [f'[r{i}]atrim={s0}:{s1},asetpts=PTS-STARTPTS[m{i}]' for i in range(n)]
    chain = '[m0]'
    for i in range(1, n):
        parts.append(f'{chain}[m{i}]acrossfade=d={XF}:c1=qsin:c2=qsin[x{i}]')
        chain = f'[x{i}]'
    parts += [
        '[3:a]aresample=48000,aformat=channel_layouts=stereo[env]',
        f'{chain}atrim=0:{LENGTH},volume={gain:.2f}dB,afade=t=in:d=2,afade=t=out:st={LENGTH - 6}:d=6[bm]',
        '[bm][env]amultiply[bed]',
        '[2:a]aresample=48000,volume=1.3dB,asplit[vo][sc]',
        f'[1:a]atempo={SPEED},aresample=48000[s]',
        '[s][sc]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=600[sd]',
        f'[sd][bed][vo]amix=inputs=3:normalize=0,atrim=0:{to},loudnorm=I=-16:TP=-1.5:LRA=11[a]',
    ]
    env = out + '.env.wav'
    envelope(env)
    run('ffmpeg', '-y', '-v', 'error', '-i', track, '-i', SFX, '-i', VO, '-i', env,
        '-filter_complex', ';'.join(parts), '-map', '[a]', '-ar', '48000', out)
    os.remove(env)


if __name__ == '__main__':
    a = sys.argv
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    track = opt('--track', os.path.join(ROOT, CFG['music']['track']))
    body = [float(x) for x in opt('--body', ':'.join(map(str, CFG['music']['body']))).split(':')]
    build(track, body, a[1], float(opt('--to', LENGTH)))
