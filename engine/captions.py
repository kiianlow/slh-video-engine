"""Burned-in word-by-word captions.

Two timing sources, in order of preference:
  1. from_elevenlabs(alignment.json) -- zero drift, the correct way
  2. from_scenes(scenes)             -- auto-distributed, APPROXIMATE, flagged

Captions sit in the band defined by layout.caption_band_y so they never collide
with scene graphics above or the handle strip below.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import motion as mo


class CaptionTrack:
    _chunks = None

    def __init__(self, words, approximate=False):
        # words: [(text, start_s, end_s), ...]
        self.words = words
        self.approximate = approximate

    # ------------------------------------------------------------ sources --
    @classmethod
    def from_elevenlabs(cls, path):
        """Accepts the alignment JSON ElevenLabs returns with a VO render."""
        with open(path) as f:
            data = json.load(f)

        if "words" in data:
            out = [(w["word"], float(w["start"]), float(w["end"]))
                   for w in data["words"] if w.get("word", "").strip()]
            return cls(out, approximate=False)

        # character-level alignment: stitch characters into words
        chars = data.get("characters") or data.get("alignment", {}).get("characters")
        starts = data.get("character_start_times_seconds") or \
            data.get("alignment", {}).get("character_start_times_seconds")
        ends = data.get("character_end_times_seconds") or \
            data.get("alignment", {}).get("character_end_times_seconds")
        if not chars:
            raise ValueError("Unrecognised ElevenLabs alignment format")

        out, cur, cs = [], "", None
        for ch, s, e in zip(chars, starts, ends):
            if ch.strip() == "":
                if cur:
                    out.append((cur, cs, e))
                    cur, cs = "", None
                continue
            if cs is None:
                cs = s
            cur += ch
            last_e = e
        if cur:
            out.append((cur, cs, last_e))
        return cls(out, approximate=False)

    @classmethod
    def from_scenes(cls, scenes):
        """Fallback: spread each scene's narration evenly across its duration.

        Weighted by word length so long words hold longer. Still approximate --
        build.py prints a warning whenever this path is used.
        """
        words, clock = [], 0.0
        for sc in scenes:
            text = (sc.get("narration") or sc.get("headline") or "").strip()
            dur = float(sc["duration"])
            toks = text.split()
            if not toks:
                clock += dur
                continue
            speech = dur * 0.88          # leave a beat of air at the tail
            weights = [max(2, len(t)) for t in toks]
            total = sum(weights)
            t = clock + dur * 0.06
            for tok, wgt in zip(toks, weights):
                span = speech * (wgt / total)
                words.append((tok, t, t + span))
                t += span
            clock += dur
        return cls(words, approximate=True)

    # ------------------------------------------------------------- render --
    def chunks(self, conf):
        """Group words so fast speech stays readable.

        A word lasting 0.15s flashes, and at that length a 60ms timing error is
        obvious. Grouping into short phrases means the text is on screen long
        enough to read, while the active-word highlight keeps it word-for-word.
        """
        if getattr(self, "_chunks", None) is not None:
            return self._chunks
        mx = conf.get("max_words", 3)
        lo = conf.get("min_chunk_s", 0.42)
        hi = conf.get("max_chunk_s", 1.9)
        out, cur = [], []
        for w in self.words:
            cur.append(w)
            span = cur[-1][2] - cur[0][1]
            ends_clause = w[0].rstrip().endswith((".", ",", "?", "!", ":", ";"))
            sentence_end = w[0].rstrip().endswith((".", "?", "!"))
            if sentence_end or len(cur) >= mx or span >= hi or (span >= lo and ends_clause):
                out.append(cur)
                cur = []
        if cur:
            if out and (cur[-1][2] - cur[0][1]) < lo * 0.6 and len(out[-1]) < mx + 1:
                out[-1].extend(cur)
            else:
                out.append(cur)
        # absorb any chunk still too brief into its neighbour
        merged = []
        for c in out:
            prev_ends_sentence = (merged and
                                  merged[-1][-1][0].rstrip().endswith((".", "?", "!")))
            if (merged and not prev_ends_sentence
                    and (c[-1][2] - c[0][1]) < lo
                    and len(merged[-1]) + len(c) <= mx + 1):
                merged[-1].extend(c)
            else:
                merged.append(c)
        self._chunks = merged
        return merged

    def active(self, t):
        for w, s, e in self.words:
            if s <= t < e:
                return w, (t - s) / max(1e-6, e - s), s
        return None

    def draw(self, img, repo_root, cfg, t):
        conf = cfg["captions_burned"]
        if not conf.get("enabled"):
            return img
        tt = t - conf.get("offset_ms", 0) / 1000.0

        chunks = self.chunks(conf)
        hit = None
        for c in chunks:
            if c[0][1] <= tt < c[-1][2]:
                hit = c
                break
        if hit is None:
            return img

        W, H = img.size
        fpath = os.path.join(repo_root, cfg["type"][conf["font"]]["file"])
        upper = conf.get("case") == "upper"

        def clean(w):
            w = w.strip(",.;:!?")
            return w.upper() if upper else w

        words = [clean(w[0]) for w in hit]
        words = [w for w in words if w]
        if not words:
            return img

        size = conf["size"]
        maxw = conf.get("max_width", 930)
        minsz = conf.get("min_size", 46)
        d0 = ImageDraw.Draw(img)
        f = ImageFont.truetype(fpath, size)
        gap = int(size * 0.30)
        while size > minsz:
            f = ImageFont.truetype(fpath, size)
            gap = int(size * 0.30)
            total = sum(d0.textbbox((0, 0), w, font=f)[2] for w in words) + gap * (len(words) - 1)
            if total <= maxw:
                break
            size -= 2

        widths = [d0.textbbox((0, 0), w, font=f)[2] for w in words]
        total = sum(widths) + gap * (len(words) - 1)
        asc, desc = f.getmetrics()
        th = asc + desc

        start = hit[0][1]
        pop = max(0.0, min(1.0, mo.window(tt, start, conf["pop_in_ms"], "back_out")))
        scale = mo.lerp(conf.get("pop_from", 0.72), 1.0, pop)

        # which word is being spoken right now
        live = -1
        for i, w in enumerate(hit):
            if w[1] <= tt < w[2]:
                live = i
                break
        if live < 0:
            live = len(hit) - 1

        sh = conf["shadow"]
        pad = 46
        layer = Image.new("RGBA", (int(total + pad * 2), int(th + pad * 2)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        x = pad
        for i, w in enumerate(words):
            ld.text((x, pad), w, font=f, fill=(0, 0, 0, int(255 * sh["opacity"])))
            x += widths[i] + gap
        layer = layer.filter(ImageFilter.GaussianBlur(sh["blur"]))
        ld = ImageDraw.Draw(layer)

        dim = int(255 * conf.get("inactive_opacity", 0.38))
        x = pad
        for i, w in enumerate(words):
            on = (i == live) or not conf.get("active_word", True)
            ld.text((x, pad), w, font=f, fill=(255, 255, 255, 255 if on else dim))
            x += widths[i] + gap

        if scale != 1.0:
            layer = layer.resize((max(2, int(layer.width * scale)),
                                  max(2, int(layer.height * scale))), Image.LANCZOS)

        cx = W / 2
        cy = H * cfg["layout"]["caption_y_factor"]
        img.alpha_composite(layer, (int(cx - layer.width / 2),
                                    int(cy - layer.height / 2 + sh["offset"][1])))
        return img



def narration_script(scenes, cfg):
    """Build the ElevenLabs-ready script with break tags and acronym spelling."""
    vo = cfg["voiceover"]
    acr = {"CPF": "C-P-F", "ABSD": "A-B-S-D", "BSD": "B-S-D", "TDSR": "T-D-S-R",
           "MSR": "M-S-R", "PSF": "P-S-F", "TOP": "T-O-P", "HDB": "H-D-B",
           "BTO": "B-T-O", "LTV": "L-T-V", "SSD": "S-S-D", "OTP": "O-T-P",
           "CEA": "C-E-A", "URA": "U-R-A", "IPA": "I-P-A"}
    out = []
    for sc in scenes:
        line = (sc.get("narration") or "").strip()
        if not line:
            continue
        for k, v in acr.items():
            line = line.replace(k, v)
        out.append(line)
    body = f'\n<break time="{vo["break_tags"]["between_scenes"]}" />\n'.join(out)
    # The break between scenes is load-bearing: build.py silence-detects it to
    # time the video to the recording. Do not remove it from the pasted script.
    header = (
        f'Voice:  {vo["voice"]}\n'
        f'Model:  {vo.get("model", "Eleven Multilingual v2")}\n'
        f'Speed:  {vo.get("speed", "max")}\n'
        f'Stability {vo["stability"]}  |  Similarity {vo["similarity"]}  |  '
        f'Style {vo["style"]}\n'
        f'Speaker Boost {"ON" if vo["speaker_boost"] else "OFF"}  |  '
        f'Output {vo.get("output_format", "MP3 44.1 kHz (128kbps)")}\n'
    )
    header += (
        "\nPaste everything below the line into ElevenLabs exactly as it is.\n"
        "Do not delete the <break> tags -- the build reads them to sync the\n"
        "captions to your delivery. Save the result as narration.mp3.\n"
    )
    header += "-" * 64 + "\n\n"
    return header + body + "\n"


def write_srt(track, path):
    """SRT companion file. Part of the approved deliverable bundle."""
    def ts(x):
        h = int(x // 3600); m = int((x % 3600) // 60)
        sec = int(x % 60); ms = int(round((x - int(x)) * 1000))
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
    lines, n, buf, start = [], 0, [], None
    for w, s0, e0 in track.words:
        if start is None:
            start = s0
        buf.append(w)
        if len(buf) >= 6 or w.endswith((".", "?", "!")):
            n += 1
            lines.append(f"{n}\n{ts(start)} --> {ts(e0)}\n{' '.join(buf)}\n")
            buf, start = [], None
    if buf:
        n += 1
        lines.append(f"{n}\n{ts(start)} --> {ts(track.words[-1][2])}\n{' '.join(buf)}\n")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path
