#!/usr/bin/env python3
"""Voice + ducked music bed + SFX bus + two-pass loudnorm (from the iPhone V20 mix).

Run from the project directory (relative paths resolve against --root, default cwd):
  uv run --offline --no-project --with numpy --with scipy python mix_audio.py audio/mix-spec-v01.json audio/mix-v01

Spec JSON (everything except duration/voice is optional):
  {"duration": 78, "voice": "audio/voiceover-v01.wav",
   "music": {"file": "audio/library/track.mp3", "source_bpm": 129, "target_bpm": 112, "phase": 0.15744,
             "bed_db": -22, "duck_db": -4, "attack_ms": 50, "release_ms": 300, "pad_db": -35,
             "fade_in": 0.08, "fade_out": 0.8},
   "sfx": {"events": "audio/sfx-events-v01.json",
           "assets": {"whoosh-slide": {"file": "audio/library/mixkit-1492.wav", "start": 0.88, "end": 1.16, "length": 0.28},
                      "riser": {"file": "audio/library/mixkit-784.wav", "start": 0.11, "end": 2.61, "length": 1.2,
                                "reverse": true, "ramp": true}}},
   "loudness": {"I": -14, "TP": -1.3, "LRA": 9}}

Levels are relative to the measured voice RMS (speech frames only). Writes <prefix>.wav (master),
<prefix>-report.json and stems in <prefix>-stems/. Never claims audible listening: report sets
audible_listening=false until a human/agent has actually listened.
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_path import find_ffmpeg  # noqa: E402

SR = 48000
VOICE_FILTERS = ("highpass=f=80,equalizer=f=4000:t=q:w=0.85:g=1.8,"
                 "acompressor=threshold=0.09:ratio=3:attack=10:release=120:knee=2.5:makeup=1")


def decode(path, channels=2, filters=None):
    cmd = [find_ffmpeg(), "-v", "error", "-i", str(path)]
    if filters:
        cmd += ["-af", filters]
    raw = subprocess.check_output(cmd + ["-ar", str(SR), "-ac", str(channels), "-f", "f32le", "-"])
    return np.frombuffer(raw, np.float32).reshape(-1, channels).copy()


def write(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def rms(x):
    return float(np.sqrt(np.mean(x * x)) + 1e-12)


def db(x):
    return float(20 * np.log10(x + 1e-12))


def fit(x, n):
    return np.vstack([x, np.zeros((n - len(x), x.shape[1]), np.float32)]) if len(x) < n else x[:n]


def faded(x, ms=8):
    """Raised-cosine edges so trimmed samples never click."""
    x = x.copy()
    m = min(round(SR * ms / 1000), len(x) // 3)
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, m)))[:, None]
    x[:m] *= ramp
    x[-m:] *= ramp[::-1]
    return x


def stereo(x):
    """Dual-mono samples get a small sample-derived decorrelation; real stereo is left alone."""
    if rms(x[:, 0] - x[:, 1]) < 1e-6:
        y = x[:, 1].copy()
        d = round(SR * 0.006)
        x[:, 1] = 0.85 * y + 0.15 * np.r_[np.zeros(d), y[:-d]]
    return x


def mono_safe(x):
    """If L/R cancel in mono (out-of-phase bass), rebuild from the stronger channel."""
    if rms(x[:, 0] + x[:, 1]) < rms(x[:, 0] - x[:, 1]):
        ch = x[:, int(np.argmax(np.mean(x ** 2, axis=0)))].copy()
        return stereo(np.column_stack([ch, ch]))
    return x


def loudnorm(src, dst, target):
    spec = f"loudnorm=I={target['I']}:TP={target['TP']}:LRA={target['LRA']}"
    ff = find_ffmpeg()
    first = subprocess.run([ff, "-hide_banner", "-i", str(src), "-af", spec + ":print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, check=True)
    stats = json.JSONDecoder().raw_decode(first.stderr[first.stderr.rfind("{"):])[0]
    keys = [("measured_I", "input_i"), ("measured_TP", "input_tp"), ("measured_LRA", "input_lra"),
            ("measured_thresh", "input_thresh"), ("offset", "target_offset")]
    second = subprocess.run([ff, "-hide_banner", "-y", "-i", str(src), "-af",
                             spec + ":linear=true:print_format=json:" + ":".join(f"{a}={stats[b]}" for a, b in keys),
                             "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(dst)], capture_output=True, text=True, check=True)
    return stats, json.JSONDecoder().raw_decode(second.stderr[second.stderr.rfind("{"):])[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("prefix", help="output prefix, e.g. audio/mix-v01")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))

    def path(p):
        p = Path(p)
        return p if p.is_absolute() else root / p

    master_path = path(args.prefix + ".wav")
    report_path = path(args.prefix + "-report.json")
    stems = path(args.prefix + "-stems")
    for p in (master_path, report_path, stems):
        if p.exists() and not args.overwrite:
            ap.error(f"refusing to overwrite {p}; use a new version prefix")
    stems.mkdir(parents=True, exist_ok=True)
    duration = float(spec["duration"])
    N = round(duration * SR)
    report = dict(duration=duration, sample_rate=SR, channels=2, voice_native_speed=True, audible_listening=False)

    # Voice: centered, cleaned, compressed. Never time-stretched here.
    voice = fit(decode(path(spec["voice"]), 1, spec.get("voice_filters", VOICE_FILTERS)), N)
    write(stems / "voice.wav", voice)
    chunks = voice[: N // 480 * 480, 0].reshape(-1, 480)
    env = np.sqrt(np.mean(chunks ** 2, axis=1))
    reference = rms(chunks[env > 0.018]) if (env > 0.018).any() else rms(voice)
    report.update(voice_rms_dbfs=db(reference), voice_filters=spec.get("voice_filters", VOICE_FILTERS), voice_stereo_center=True)

    bed = np.zeros((N, 2), np.float32)
    m = spec.get("music")
    if m:
        filters = []
        if m.get("source_bpm") and m.get("target_bpm"):
            ratio = m["target_bpm"] / m["source_bpm"]
            assert 0.5 <= ratio <= 2, "atempo ratio out of range"
            filters.append(f"atempo={ratio:.10f}")
            phase = m.get("phase", 0) / ratio
        else:
            ratio, phase = 1.0, m.get("phase", 0)
        if phase:
            filters.append(f"atrim=start={phase:.8f},asetpts=PTS-STARTPTS")
        music = fit(decode(path(m["file"]), 2, ",".join(filters) or None), N)
        music *= reference * 10 ** (m.get("bed_db", -22) / 20) / rms(music)
        attack, release = m.get("attack_ms", 50) / 1000, m.get("release_ms", 300) / 1000
        target = np.where(env > 0.012, 10 ** (m.get("duck_db", -4) / 20), 1.0)
        gains, last = [], 1.0
        for q in target:  # 10 ms control rate sidechain follower
            alpha = np.exp(-0.01 / (attack if q < last else release))
            last = alpha * last + (1 - alpha) * q
            gains.append(last)
        gain = np.interp(np.arange(N), np.arange(len(gains)) * 480, gains).astype(np.float32)
        music *= gain[:, None]
        bed = music
        if m.get("pad_db") is not None:  # low-passed copy of the same track fills long clauses
            pad = signal.sosfilt(signal.butter(2, 650, fs=SR, output="sos"), music, axis=0).astype(np.float32)
            bed = music + pad * reference * 10 ** (m["pad_db"] / 20) / rms(pad)
        fi, fo = round(m.get("fade_in", 0.08) * SR), round(m.get("fade_out", 0.8) * SR)
        bed[:fi] *= np.linspace(0, 1, fi)[:, None]
        bed[-fo:] *= np.linspace(1, 0, fo)[:, None]
        write(stems / "music-ducked.wav", bed)
        report.update(music_file=m["file"], music_atempo=ratio, music_phase_trim_seconds=phase,
                      music_base_relative_voice_db=m.get("bed_db", -22),
                      music_speech_relative_voice_db=m.get("bed_db", -22) + m.get("duck_db", -4),
                      duck_attack_ms=attack * 1000, duck_release_ms=release * 1000, ambient_relative_voice_db=m.get("pad_db"),
                      music_side_energy_dbfs=db(rms((bed[:, 0] - bed[:, 1]) / 2)))

    bus = np.zeros((N, 2), np.float32)
    layers = np.zeros(N, np.uint8)
    s = spec.get("sfx")
    if s:
        assets = {}
        for name, a in s["assets"].items():
            x = mono_safe(stereo(decode(path(a["file"]))))
            x = x[round(a.get("start", 0) * SR): round(a["end"] * SR) if a.get("end") else None]
            if a.get("reverse"):
                x = x[::-1]
            if a.get("length"):
                x = signal.resample(x, round(a["length"] * SR))
            x = signal.sosfilt(signal.butter(2, a.get("lowpass", 10000), fs=SR, output="sos"), x, axis=0)
            if a.get("ramp"):
                x *= np.linspace(0.12, 1, len(x))[:, None] ** 0.7
            assets[name] = faded(x, a.get("fade_ms", 8)).astype(np.float32)
            write(stems / f"sfx-{name}.wav", assets[name])
        events = s["events"]
        if isinstance(events, str):
            events = json.loads(path(events).read_text(encoding="utf-8"))["events"]
        for e in events:
            x = assets[e["sfx"]].copy()
            g = reference * 10 ** (e["relative_voice_db"] / 20) / rms(x)
            x *= g
            start = round(e["time"] * SR)
            stop = min(N, start + len(x))
            bus[start:stop] += x[: stop - start]
            layers[start:stop] += 1
            e["gain_db"] = round(db(g), 3)
        max_layers = s.get("max_layers", 2)
        assert layers.max() <= max_layers, f"{layers.max()} SFX overlap (max {max_layers}); move or drop an event"
        write(stems / "sfx-bus.wav", bus)
        report.update(events=events, max_simultaneous_sfx=int(layers.max()), sfx_side_energy_dbfs=db(rms((bus[:, 0] - bus[:, 1]) / 2)))

    mix = np.repeat(voice, 2, axis=1) + bed + bus
    peak = float(np.abs(mix).max())
    assert peak < 1, f"premaster clips ({db(peak):.2f} dBFS); lower bed/SFX levels"
    premaster = stems / "premaster.wav"
    write(premaster, mix)
    target = {"I": -14, "TP": -1.3, "LRA": 9, **spec.get("loudness", {})}
    measured, final = loudnorm(premaster, master_path, target)
    report.update(premaster_peak_dbfs=db(peak), loudness_target=target, loudnorm_measurement=measured, loudnorm_final=final)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("events", "loudnorm_measurement")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
