"""Time the video to the actual recorded narration.

The problem this solves: captions are burned in, so if their timing is guessed
from the script the words drift against Kiian's real ElevenLabs delivery and
there is no fixing it in CapCut.

The fix: render AFTER the voiceover exists. The narration script puts a
0.6s <break> between every scene, and ElevenLabs renders those as real
silence. ffmpeg silencedetect finds those gaps, which gives the true start and
end of every scene in the recorded audio. Scene durations are then rewritten to
match, and words are distributed inside each scene's real span.

Result: video length equals audio length, and the MP3 drops on the CapCut
timeline at 0:00 with no cutting.

No ElevenLabs alignment JSON needed. If one IS available it is still better --
captions.py prefers it.
"""
import json
import re
import subprocess

VOWELS = "aeiouy"


def duration_of(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    return float(p.stdout.strip())


def find_silences(path, min_gap=0.35, noise_db=-34):
    """Return [(start, end)] of every silent stretch in the narration."""
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path,
         "-af", f"silencedetect=noise={noise_db}dB:d={min_gap}", "-f", "null", "-"],
        capture_output=True, text=True)
    log = p.stderr
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", log)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration_of(path)
        out.append((s, e))
    return out


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    n, prev = 0, False
    for ch in w:
        v = ch in VOWELS
        if v and not prev:
            n += 1
        prev = v
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def speech_runs(audio_path, s0, s1, min_gap=0.09, noise_db=-38):
    """Actual speaking stretches inside [s0, s1], pauses removed.

    Coarse scene spans still leave drift: the reader breathes mid-sentence and
    the words after that pause arrive late. Splitting the span into real speech
    runs and laying words only on those runs removes it.
    """
    gaps = [g for g in find_silences(audio_path, min_gap, noise_db)
            if g[1] > s0 and g[0] < s1]
    runs, cur = [], s0
    for gs, ge in gaps:
        gs, ge = max(gs, s0), min(ge, s1)
        if gs - cur > 0.05:
            runs.append((cur, gs))
        cur = max(cur, ge)
    if s1 - cur > 0.05:
        runs.append((cur, s1))
    return runs or [(s0, s1)]


def lay_words(audio_path, s0, s1, tokens):
    """Place tokens across the real speech runs in a span."""
    runs = speech_runs(audio_path, s0, s1)
    total_speech = sum(e - b for b, e in runs)
    if total_speech <= 0:
        total_speech = s1 - s0
        runs = [(s0, s1)]

    weights = [syllables(t) for t in tokens]
    total_w = sum(weights) or 1

    # how many syllables each run should carry, by its share of speech time
    out, wi, carried = [], 0, 0.0
    for ri, (rb, re) in enumerate(runs):
        share = (re - rb) / total_speech
        target = share * total_w
        take, acc = [], 0.0
        while wi < len(tokens) and (acc + weights[wi] / 2 <= target or
                                    (ri == len(runs) - 1)):
            take.append(wi)
            acc += weights[wi]
            wi += 1
            if ri == len(runs) - 1 and wi >= len(tokens):
                break
        if not take and wi < len(tokens):
            take = [wi]
            acc = weights[wi]
            wi += 1
        if not take:
            continue
        sub = sum(weights[i] for i in take) or 1
        t = rb
        for i in take:
            span = (re - rb) * (weights[i] / sub)
            out.append((tokens[i], t, t + span))
            t += span
        carried += acc
    while wi < len(tokens):
        out.append((tokens[wi], s1 - 0.05, s1))
        wi += 1
    return out


def scene_spans(audio_path, n_scenes, min_gap=0.35, noise_db=-34):
    """Split the recording into n_scenes spans using the largest silent gaps.

    The script writes a 0.6s break between scenes and 0.3s inline, so the
    scene boundaries are the longest gaps. Take the n-1 longest.
    """
    total = duration_of(audio_path)
    gaps = find_silences(audio_path, min_gap, noise_db)
    # ignore leading and trailing silence
    inner = [g for g in gaps if g[0] > 0.25 and g[1] < total - 0.25]
    inner.sort(key=lambda g: (g[1] - g[0]), reverse=True)
    cuts = sorted(g[0] + (g[1] - g[0]) / 2 for g in inner[:max(0, n_scenes - 1)])

    bounds = [0.0] + cuts + [total]
    spans = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    return spans, total, len(inner)


def build_alignment(audio_path, scenes, out_path, tail_pad=0.35):
    """Rewrite scene durations to the real audio and emit word timings.

    Returns (alignment_dict, total_duration, warning_or_None).
    """
    spoken = [s for s in scenes if (s.get("narration") or "").strip()]
    spans, total, found = scene_spans(audio_path, len(spoken))

    warn = None
    if len(spans) != len(spoken):
        warn = (f"silence detection found {found} usable gaps for "
                f"{len(spoken)} spoken scenes; timing may be off")

    words = []
    si = 0
    for sc in scenes:
        text = (sc.get("narration") or "").strip()
        if not text:
            sc["duration"] = sc.get("duration", 2.0)
            continue
        s0, s1 = spans[si]
        si += 1
        sc["duration"] = round(s1 - s0, 3)
        sc["_audio_start"] = round(s0, 3)

        toks = text.split()
        for tok, ws, we in lay_words(audio_path, s0, s1, toks):
            # captions show acronyms clean; the hyphens are voice-only
            clean = tok.replace("-", "") if re.fullmatch(r"([A-Z]-)+[A-Z][.,!?]?", tok) else tok
            words.append({"word": clean, "start": round(ws, 3), "end": round(we, 3)})

    alignment = {"source": "speech-run aligned from narration audio",
                 "audio": audio_path, "duration": total, "words": words}
    with open(out_path, "w") as f:
        json.dump(alignment, f, indent=1)
    return alignment, total, warn
