#!/usr/bin/env python3
"""Self-synthesized music bed (no samples, no licence needed): calm 72 BPM night pad with a soft felt-piano
arpeggio, almost nothing above 4 kHz so it never masks narration. First used 2026-10-07 ("Sạc qua đêm") after a
bright stock track sounded noisy under the voice. Mix with mix_audio.py at bed about -21..-24 dB, duck -4 dB.
  uv run --offline --no-project --with numpy --with scipy python make_music_pad.py audio/library/night-pad.wav SECONDS"""
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
out, length = sys.argv[1], float(sys.argv[2])
BPM = 72
beat = 60 / BPM
bar = 4 * beat
n = int(SR * length)
t = np.arange(n) / SR
rng = np.random.default_rng(2026)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


# Fmaj9 - Am7 - Dm9 - Bbmaj7(#11) ; one chord per bar
CHORDS = [[41, 57, 60, 64, 67], [45, 55, 60, 64, 67], [38, 57, 60, 64, 65], [46, 57, 62, 64, 65]]
pad = np.zeros((n, 2))
arp = np.zeros((n, 2))
k = 0
while k * bar < length:
    ch = CHORDS[k % 4]
    a, b = int(k * bar * SR), min(n, int(((k + 1) * bar + 1.5) * SR))
    tt = np.arange(b - a) / SR
    env = np.minimum(1, tt / 1.4) * np.clip((bar + 1.5 - tt) / 1.5, 0, 1)
    for j, m in enumerate(ch):
        for side, det in ((0, -0.08), (1, 0.08)):
            f = hz(m + det)
            v = np.sin(2 * np.pi * f * tt + j) + 0.18 * np.sin(4 * np.pi * f * tt) + 0.05 * np.sin(6 * np.pi * f * tt)
            pad[a:b, side] += v * env * (0.55 if j == 0 else 0.22)
    # arpeggio: eighth notes, soft, sparse (skips some steps)
    notes = [m + 12 for m in ch[1:]] + [ch[2] + 24]
    for s in range(8):
        if (k * 8 + s) % 5 == 3:
            continue
        st = int((k * bar + s * beat / 2) * SR)
        if st >= n:
            break
        m = notes[(s * 3 + k) % len(notes)]
        f = hz(m)
        ln = min(n - st, int(2.4 * SR))
        u = np.arange(ln) / SR
        tone = (np.sin(2 * np.pi * f * u) + 0.25 * np.sin(4 * np.pi * f * u) * np.exp(-u * 6)) * np.exp(-u * 2.6) * np.minimum(1, u / 0.006)
        vel = 0.16 + 0.06 * rng.random()
        pan = 0.5 + 0.3 * np.sin(s)
        arp[st:st + ln, 0] += tone * vel * (1 - pan)
        arp[st:st + ln, 1] += tone * vel * pan
    k += 1

pad = signal.sosfilt(signal.butter(2, 1400, "low", fs=SR, output="sos"), pad, axis=0)
mix = pad * 0.5 + arp
# room: exponential-decay noise IR
ir_t = np.arange(int(2.2 * SR)) / SR
ir = rng.standard_normal((len(ir_t), 2)) * np.exp(-ir_t * 2.8)[:, None]
ir = signal.sosfilt(signal.butter(2, 3500, "low", fs=SR, output="sos"), ir, axis=0)
wet = np.stack([signal.fftconvolve(mix[:, c], ir[:, c])[:n] for c in range(2)], axis=1)
mix = mix + 0.35 * wet / np.abs(wet).max() * np.abs(mix).max()
mix = signal.sosfilt(signal.butter(2, 60, "high", fs=SR, output="sos"), mix, axis=0)
fade = np.minimum(1, t / 1.0) * np.clip((length - t) / 2.0, 0, 1)
mix *= fade[:, None]
mix = mix / np.abs(mix).max() * 0.7
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("wrote", out)
