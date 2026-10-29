"""VieNeu narration: python gen_vo.py lines.json OUT_DIR  (preset voices only, no cloning)"""
import json, subprocess, sys, time
from pathlib import Path
import numpy as np, soundfile as sf
from vieneu import Vieneu
FF = "ffmpeg"
TRIM = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
V = {"narr":   ("Thiện Minh", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=10:release=200,equalizer=f=160:t=q:w=1:g=2"),
     "bavong": ("Ngọc Linh", "asetrate=SR*0.93,aresample=SR,atempo=0.97,highpass=f=160,lowpass=f=6000,aecho=0.8:0.5:60|130:0.22|0.12,acompressor=threshold=-22dB:ratio=2.5"),
     "toi":    ("Trúc Ly", "asetrate=SR*1.06,aresample=SR,atempo=0.96,highpass=f=120,acompressor=threshold=-22dB:ratio=2.5")}
tts = Vieneu()
sr = tts.sample_rate
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for i, l in enumerate(json.load(open(sys.argv[1]))["lines"]):
    name, af = V[l["spk"]]
    t0 = time.time()
    wav = tts.infer(l["text"], voice=tts.get_preset_voice(name), temperature=0.7)
    raw = out / f"{i:02d}_raw.wav"
    sf.write(raw, np.asarray(wav, np.float32), sr)
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(raw), "-af", TRIM + "," + af.replace("SR", str(sr)),
                    "-ar", "48000", "-ac", "1", str(out / f"{i:02d}.wav")], check=True)
    print(i, l["spk"], f"{len(wav)/sr:.2f}s audio in {time.time()-t0:.1f}s", flush=True)
