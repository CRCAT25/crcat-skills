#!/usr/bin/env python3
"""A narration voice from a VoiceStudio clone profile (free, local, 127.0.0.1:3900). Set NP_PROFILE and NP_REF.

Project mode (whiteboard-video / any project with audio/tts-input-TAG-chN.txt):
  python3 voice_np.py PROJECT --tag v01 [--channel gkp|mtn] [--takes 3] [--max-takes 7]
  -> audio/voice-raw-TAG.wav (48 kHz mono) + audio/voice-offsets-TAG.json + audio/np-report-TAG.json
     (the same files build_voice.py writes, so align_captions / stretch_pauses / mix continue unchanged)
Single text mode (tests, Shorts):
  python3 voice_np.py --text lines.txt --out voice.wav [--channel ...]
Lines mode (oneshot-3d-science-film: audio/vo/lines.json {lines: [{t, text}]}):
  python3 voice_np.py --lines audio/vo/lines.json --out-dir audio/vo/el_dl --channel mtn
  -> el_dl/NN_g1.mp3, one per line, so build_el.py / make_srt.py continue unchanged

Per sentence: N seeded takes -> whisper -> pick (voice closest to the reference, every word heard, natural pace,
breathes at the script's pauses, livelier pitch) -> more seeds if no take is clean -> split a sentence the model
keeps dropping words from at its middle pause.
Smooth join, so a sentence never stutters: one whole take per sentence, a single gentle tempo (±5 %), pauses are only
lengthened inside breaths the take already has (crossfaded room tone, never a cut through speech), nothing is
shortened except a stray mid-phrase hesitation over 0.45 s (cut inside its own silence).
Takes are cached in audio/np-TAG/ (or next to --out), so a rerun only generates what is missing."""
import argparse, difflib, hashlib, json, os, re, subprocess, sys, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
API = "http://127.0.0.1:3900"
# NP_PROFILE / NP_REF pick another VoiceStudio clone profile and its reference recording
PROFILE = os.environ.get("NP_PROFILE", "")
REF = Path(os.environ.get("NP_REF", HERE / "ref" / "ref-nhat-phong-12s.wav"))
SEEDS = [625743482, 11, 22, 33, 44, 55, 66, 77, 88, 99]
SR = 24000
FADE = int(.015 * SR)
# measured on a Vietnamese narrator reference: 4.65 syll/s; pause after ',' 0.41 s, ':' 0.45, '.' 0.61, '?' 0.67
CHANNEL = {"gkp": {"rate": 4.65, "pause": 1.00}, "mtn": {"rate": 4.35, "pause": 1.15}}
MARK = {",": 0.41, "—": 0.41, ":": 0.45, ";": 0.45, "…": 0.45, "!": 0.36}
END = {".": 0.53, "!": 0.53, "?": 0.59, "…": 0.59}  # + ~0.08 s clip tail
CHAPTER_GAP = 0.9
CHAIN = ("highpass=f=70,afftdn=nr=8:nf=-40:tn=1,deesser=i=0.3,lowpass=f=10000,"
         "acompressor=threshold=0.12:ratio=2:attack=15:release=150,loudnorm=I=-16:TP=-2")
MAX_SYL = 24  # longer lines lose words in OmniVoice: split them up front

# ---------- text ----------
DIG = "không một hai ba bốn năm sáu bảy tám chín".split()
LETTER = dict(a="a", b="bê", c="xê", d="dê", e="e", f="ép", g="giê", h="hát", i="i", j="gi", k="ca", l="lờ", m="mờ",
              n="nờ", o="o", p="pê", q="quy", r="rờ", s="ét", t="tê", u="u", v="vê", w="vê kép", x="ích", y="i", z="dét")
SYN = {"linh": "lẻ", "ngàn": "nghìn", "tư": "bốn"}

def read3(n, full):
    h, t, u = n // 100, n // 10 % 10, n % 10
    w = [DIG[h], "trăm"] if full or h else []
    if t > 1: w += [DIG[t], "mươi"] + (["mốt"] if u == 1 else ["lăm"] if u == 5 else [DIG[u]] if u else [])
    elif t == 1: w += ["mười"] + (["lăm"] if u == 5 else [DIG[u]] if u else [])
    elif u: w += (["lẻ"] if w else []) + [DIG[u]]
    return w

def num2vi(n):
    if n == 0: return ["không"]
    out, units, i = [], ["", "nghìn", "triệu", "tỷ"], 0
    groups = []
    while n: groups.append(n % 1000); n //= 1000
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g: out += read3(g, full=i < len(groups) - 1) + ([units[i % 4]] if units[i % 4] else [])
        if i and i % 4 == 0 and not g: out.append("tỷ")
    return out

def spoken(s):
    """words as heard, for comparing script vs whisper: digits and abbreviations are spelled the Vietnamese way"""
    s = re.sub(r"(\d)\.(?=\d{3})", r"\1", s)
    s = re.sub(r"(\d),(\d)", r"\1 phẩy \2", s)
    out = []
    for t in re.findall(r"[^\W_]+", s.replace("-", " ")):
        for p in re.findall(r"\d+|\D+", t):
            if p.isdigit(): out += num2vi(int(p))
            elif p.isascii() and p.isupper(): out += " ".join(LETTER.get(c, c) for c in p.lower()).split()  # SH -> ét hát
            else: out.append(SYN.get(p.lower(), p.lower()))
    return out

def syllables(s): return len(re.findall(r"[^\W_]+", s.replace("-", " ")))

def sentences(text):
    """one sentence per unit; a break followed by a lowercase word ('đó… là') stays inside the sentence"""
    out = []
    for para in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        for line in para.splitlines():
            for piece in re.split(r"(?<=[.!?…])\s+", line.strip()):
                if not piece: continue
                if out and not out[-1][1] and piece[0].islower(): out[-1] = (out[-1][0] + " " + piece, False)
                else: out.append((piece, False))
            if out: out[-1] = (out[-1][0], out[-1][1])
        if out: out[-1] = (out[-1][0], True)  # paragraph end
    return out

def halves(s):
    """split a long sentence at the pause mark nearest its middle"""
    toks = s.split(); best = None
    for i, t in enumerate(toks[:-1]):
        if t == "—" or t[-1] in MARK:
            d = abs(i + 1 - len(toks) / 2)
            if best is None or d < best[0]: best = (d, i)
    if best is None: i = len(toks) // 2 - 1
    else: i = best[1]
    a, b = " ".join(toks[:i + 1]), " ".join(toks[i + 1:])
    return [a, b] if a and b else [s]

# ---------- audio ----------
def load(f):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(b, np.int16).astype(np.float32) / 32768

def frames_db(x, w):
    n = len(x) // w; r = np.sqrt(np.mean(x[:n * w].reshape(n, w) ** 2, 1)) + 1e-9
    return 20 * np.log10(r / r.max())

def trim(x):
    w = int(.02 * SR); on = np.where(frames_db(x, w) > -28)[0]
    a, b = max(0, on[0] * w - int(.04 * SR)), min(len(x), (on[-1] + 1) * w + int(.12 * SR))
    y = x[a:b].copy(); f = int(.01 * SR)
    y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y

def prof(x):
    """median f0, median spectral centroid, pitch span p10–p90 in semitones"""
    f0s, cents, w = [], [], int(.04 * SR)
    for i in range(0, len(x) - w, w):
        s = x[i:i + w]
        if np.sqrt(np.mean(s ** 2)) < 0.03: continue
        s = s - s.mean(); ac = np.correlate(s, s, "full")[w - 1:]
        lo, hi = int(SR / 300), int(SR / 70); l = lo + np.argmax(ac[lo:hi])
        if ac[l] > 0.5 * ac[0]: f0s.append(SR / l)
        sp = np.abs(np.fft.rfft(s * np.hanning(w))); fr = np.fft.rfftfreq(w, 1 / SR); cents.append((sp * fr).sum() / sp.sum())
    if len(f0s) < 3: return 1.0, 1.0, 0.0
    f0s = np.array(f0s); st = 12 * np.log2(f0s / np.median(f0s))
    return np.median(f0s), np.median(cents), np.percentile(st, 90) - np.percentile(st, 10)

def tempo(y, f):
    if abs(f - 1) < 0.01: return y
    b = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", f"atempo={f:.4f}",
                        "-f", "f32le", "-"], input=y.astype(np.float32).tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(b, np.float32).copy()

def gaps_of(y):
    """internal quiet stretches ≥ 60 ms, in 10 ms frames"""
    wn = int(.01 * SR); db = frames_db(y, wn); out, i = [], 0
    while i < len(db):
        j = i
        while j < len(db) and db[j] < -35: j += 1
        if j - i >= 6 and i > 0 and j < len(db): out.append((i, j))
        i = max(j, i + 1)
    return out, len(db)

def marks_of(line):
    toks, marks = [], []
    for t in line.replace("—", " — ").split():
        if t == "—": marks.append((len(toks) - 1, MARK["—"])); continue
        toks.append(t)
        if t[-1] in MARK: marks.append((len(toks) - 1, MARK[t[-1]]))
    return [m for m in marks if 0 <= m[0] < len(toks) - 1], len(toks)

def match_marks(line, y):
    """{gap: pause} — each script pause takes the take's breath nearest to where it should fall (≤ 0.5 s away)"""
    gaps, n = gaps_of(y); marks, ntok = marks_of(line); pause, free = {}, list(gaps)
    for i, p in marks:
        want = (i + 1) / ntok * n
        near = min(free, key=lambda g: abs((g[0] + g[1]) / 2 - want), default=None)
        if near and abs((near[0] + near[1]) / 2 - want) / 100 < 0.5: pause[near] = p; free.remove(near)
    return pause, gaps, len(marks)

def noise(sec, rms, seed=0):
    z = np.random.default_rng(seed).standard_normal(max(1, int(sec * SR))).astype(np.float32)
    z = np.convolve(z, np.ones(8) / 8, "same")
    return z / (np.sqrt(np.mean(z ** 2)) + 1e-9) * rms

def xjoin(a, b, n=FADE):
    """overlap-add a's tail with b's head (equal power), so a join inside silence leaves no edge"""
    n = min(n, len(a), len(b))
    if n == 0: return np.concatenate([a, b])
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    mid = a[-n:] * np.cos(t) + b[:n] * np.sin(t)
    return np.concatenate([a[:-n], mid, b[n:]])

def smooth(y, line, rate, pscale):
    """whole take, one tempo, pauses grown inside existing breaths only"""
    syl = syllables(line); fct = min(1.05, max(0.95, rate / (syl / (len(y) / SR))))
    y = tempo(y, fct); wn = int(.01 * SR)
    pause, gaps, nmarks = match_marks(line, y)
    out, last, edits = None, 0, 0
    for g in gaps:
        a, b = g[0] * wn, g[1] * wn; have = (b - a) / SR; seg = y[a:b]
        rms = float(np.sqrt(np.mean(seg[len(seg) // 4: -len(seg) // 4 or None] ** 2))) + 1e-6
        if g in pause:
            want = pause[g] * pscale
            if want <= have + 0.03: continue
            m = (a + b) // 2; head = y[last:m]; fill = noise(want - have + 2 * FADE / SR, rms, seed=a)
            out = xjoin(head, fill) if out is None else xjoin(out, xjoin(head, fill)); last = m; edits += 1
        elif have > 0.45:  # stray hesitation mid-phrase: shorten to 0.30 s inside its own silence
            m1, m2 = a + int(.15 * SR), b - int(.15 * SR); head = y[last:m1]
            out = head if out is None else xjoin(out, head); last = m2; edits += 1
    tail = y[last:]
    y = tail if out is None else xjoin(out, tail)
    return y, fct, len(pause), nmarks, edits

# ---------- VoiceStudio ----------
def gen(text, seed, out):
    if out.exists() and out.stat().st_size > 1000: return True
    for _ in range(3):
        r = subprocess.run(["curl", "-s", "-m", "900", "-o", str(out), "-w", "%{http_code}", "-X", "POST", f"{API}/generate",
                            "-F", f"text={text}", "-F", "language=Vietnamese", "-F", f"seed={seed}", "-F", f"profile_id={PROFILE}"],
                           capture_output=True, text=True).stdout
        if r == "200" and out.stat().st_size > 1000: return True
    out.unlink(missing_ok=True); return False

def heard(f):
    j = f.with_suffix(".txt")
    if not j.exists():
        r = subprocess.run(["curl", "-s", "-F", f"file=@{f}", "-F", "model=whisper-1", "-F", "language=vi",
                            f"{API}/v1/audio/transcriptions"], capture_output=True, check=True).stdout
        j.write_text(json.loads(r).get("text", ""))
    return j.read_text()

REFP = None
def score(f, line, rate):
    global REFP
    if REFP is None: REFP = prof(load(REF))
    rf0, rc, _ = REFP; y = trim(load(f)); f0, c, span = prof(y); h = heard(f)
    words = difflib.SequenceMatcher(None, spoken(line), spoken(h), autojunk=False).ratio()
    r = syllables(line) / (len(y) / SR)
    pause, _, nm = match_marks(line, y)
    s = (abs(f0 / rf0 - 1) + abs(c / rc - 1) + 0.5 * abs(np.log(r / rate)) + 3 * (1 - words)
         + (0.3 * (1 - len(pause) / nm) if nm else 0) - 0.03 * span)
    return dict(file=f.name, score=round(float(s), 3), words=round(words, 3), heard=h, rate=round(r, 2), span=round(float(span), 1))

def best_take(line, cache, rate, takes, max_takes, log):
    key = hashlib.sha1(line.encode()).hexdigest()[:10]
    rows = []
    for n, seed in enumerate(SEEDS[:max_takes]):
        if n >= takes and rows and max(r["words"] for r in rows) >= 0.92: break
        f = cache / f"{key}-s{seed}.wav"
        if not gen(line, seed, f): continue
        rows.append(score(f, line, rate))
    rows.sort(key=lambda r: r["score"])
    ok = [r for r in rows if r["words"] >= 0.92]
    pick = (ok or rows)[0]
    log(f"   {pick['words']:.2f} {pick['file']}  «{pick['heard']}»")
    return cache / pick["file"], pick, rows

def render_text(text, cache, ch, takes, max_takes, log):
    cfg = CHANNEL[ch]; cache.mkdir(parents=True, exist_ok=True)
    units = sentences(text); parts, report = [], []
    for k, (s, para_end) in enumerate(units):
        pieces = halves(s) if syllables(s) > MAX_SYL else [s]
        log(f"{k:3d} {s}")
        for attempt in range(2):
            got = [best_take(p, cache, cfg["rate"], takes, max_takes, log) for p in pieces]
            if all(g[1]["words"] >= 0.92 for g in got) or len(pieces) > 1: break
            log("   words missing in every take -> split at the middle pause"); pieces = halves(s)
            if len(pieces) == 1: break
        seq = []
        for i, (p, (f, pick, rows)) in enumerate(zip(pieces, got)):
            y, fct, kept, nm, edits = smooth(trim(load(f)), p, cfg["rate"], cfg["pause"])
            floor = float(np.percentile(np.abs(y), 5)) + 1e-5
            if i < len(pieces) - 1:
                y = np.concatenate([y, noise(MARK.get(p.rstrip()[-1], 0.41) * cfg["pause"], floor)])
            seq.append(y)
            report.append(dict(k=k, text=p, pick=pick, tempo=round(fct, 3), pauses=f"{kept}/{nm}", edits=edits,
                               alternatives=[(r["file"], r["score"], r["words"]) for r in rows]))
        y = np.concatenate(seq); floor = float(np.percentile(np.abs(y), 5)) + 1e-5
        parts.append(y)
        if k < len(units) - 1: parts.append(noise(END.get(s.rstrip()[-1], 0.53) * cfg["pause"], floor, seed=k))
    return np.concatenate(parts), report

def write_48k(x, out):
    raw = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-n", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-af", CHAIN + ",aresample=48000", "-ar", "48000", "-ac", "1",
                    *(["-b:a", "192k"] if str(out).endswith(".mp3") else ["-c:a", "pcm_s16le"]), str(out)],
                   input=raw, check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?", type=Path)
    ap.add_argument("--tag", default="v01")
    ap.add_argument("--text", type=Path); ap.add_argument("--out", type=Path)
    ap.add_argument("--lines", type=Path); ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--channel", choices=CHANNEL, default="gkp")
    ap.add_argument("--takes", type=int, default=3, help="takes per sentence before picking")
    ap.add_argument("--max-takes", type=int, default=7, help="extra seeds when no take has every word")
    a = ap.parse_args()
    log = lambda m: print(m, flush=True)
    assert PROFILE and REF.exists(), "set NP_PROFILE (VoiceStudio profile id) and NP_REF (its reference wav)"
    if a.lines:
        od = a.out_dir or a.lines.parent / "el_dl"; od.mkdir(parents=True, exist_ok=True); report = {}
        for i, ln in enumerate(json.loads(a.lines.read_text())["lines"]):
            out = od / f"{i:02d}_g1.mp3"
            if out.exists(): log(f"{i:02d} kept {out.name}"); continue
            x, report[i] = render_text(ln["text"], od / "np-cache", a.channel, a.takes, a.max_takes, log)
            write_48k(x, out); log(f"{i:02d} {len(x) / SR:.1f}s -> {out.name}")
        (od / "np-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1)); return
    if a.text:
        out = a.out or a.text.with_suffix(".wav"); assert not out.exists(), f"{out} exists; pick a new name"
        x, rep = render_text(a.text.read_text(), out.parent / f"np-{out.stem}", a.channel, a.takes, a.max_takes, log)
        write_48k(x, out); out.with_suffix(".report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        log(f"voice {len(x) / SR:.1f}s -> {out}"); return
    audio = a.project.resolve() / "audio"
    raw_out, offs_out, rep_out = (audio / f"{n}-{a.tag}{e}" for n, e in
                                  (("voice-raw", ".wav"), ("voice-offsets", ".json"), ("np-report", ".json")))
    for p in (raw_out, offs_out): assert not p.exists(), f"{p} exists; bump the tag"
    chs = sorted(audio.glob(f"tts-input-{a.tag}-ch*.txt"), key=lambda p: int(re.search(r"ch(\d+)", p.name)[1]))
    assert chs, f"no audio/tts-input-{a.tag}-chN.txt"
    parts, offsets, report, t = [], {}, {}, 0.0
    for i, p in enumerate(chs):
        ch = re.search(r"ch(\d+)", p.name)[1]; log(f"== chapter {ch}")
        x, rep = render_text(p.read_text(), audio / f"np-{a.tag}", a.channel, a.takes, a.max_takes, log)
        if i: parts.append(noise(CHAPTER_GAP, float(np.percentile(np.abs(x), 5)) + 1e-5)); t += CHAPTER_GAP
        offsets[ch] = {"take": f"np-{a.tag}", "start": round(t, 3), "dur": round(len(x) / SR, 3)}
        parts.append(x); t += len(x) / SR; report[ch] = rep
    write_48k(np.concatenate(parts), raw_out)
    offs_out.write_text(json.dumps(offsets, ensure_ascii=False, indent=1))
    rep_out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    log(f"voice {t:.2f}s -> {raw_out}")

if __name__ == "__main__":
    main()
