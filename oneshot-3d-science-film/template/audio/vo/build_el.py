# Lay the ElevenLabs takes on one narration track in final (sped-up) time: python3 build_el.py vo_el.wav
# Uses el_dl/NN_g1.mp3 (NN_g2 for lines in episode.json "take2"); trims edge silence; each line starts at its "t"
# in lines.json, or at episode.json "nudge" when the take runs longer than planned. Prints gaps and OVERLAPs.
import subprocess, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from episode import LENGTH, TRIM, lines, take, start

SR = 48000
ls = lines()
track = np.zeros(int(LENGTH * SR), np.float32)
for i in range(len(ls)):
    pcm = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', take(i), '-af', TRIM,
                          '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(pcm, np.float32)
    t = start(i, ls)
    s = int(t * SR); end = min(len(track), s + len(a))
    track[s:end] += a[:end - s]
    e = t + len(a) / SR
    nxt = start(i + 1, ls) if i + 1 < len(ls) else LENGTH
    print(f"{i:02d} {t:6.1f}-{e:6.1f}  gap {nxt - e:5.1f}" + ('  OVERLAP' if e > nxt - 0.3 else ''))
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', sys.argv[1]],
               input=track.astype('<f4').tobytes(), check=True)
