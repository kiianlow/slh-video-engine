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
    def active(self, t):
        for w, s, e in self.words:
            if s <= t < e:
                return w, (t - s) / max(1e-6, e - s), s
        return None

    def draw(self, img, repo_root, cfg, t):
        conf = cfg["captions_burned"]
        if not conf.get("enabled"):
            return img
        hit = self.active(t)
        if hit is None:
            return img
        word, prog, start = hit

        W, H = img.size
        size = conf["size"]
        fpath = os.path.join(repo_root, cfg["type"][conf["font"]]["file"])
        text = word.upper() if conf["case"] == "upper" else word
        text = text.strip(",.;:!?")
        if not text:
            return img
        f = ImageFont.truetype(fpath, size)
        maxw = conf.get("max_width", 930)
        minsz = conf.get("min_size", 56)
        while size > minsz and ImageDraw.Draw(img).textbbox((0, 0), text, font=f)[2] > maxw:
            size -= 2
            f = ImageFont.truetype(fpath, size)

        pop = max(0.0, min(1.0, mo.window(t, start, conf["pop_in_ms"], "back_out")))
        scale = mo.lerp(conf.get("pop_from", 0.72), 1.0, pop)

        d0 = ImageDraw.Draw(img)
        bb = d0.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        cx = W / 2
        cy = H * cfg["layout"]["caption_y_factor"]

        pad = 40
        layer = Image.new("RGBA", (int(tw + pad * 2), int(th + pad * 2)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)

        sh = conf["shadow"]
        shadow_rgb = mo.hex_to_rgb(sh.get("color", "#463428"))
        ld.text((pad - bb[0], pad - bb[1]), text, font=f,
                fill=shadow_rgb + (int(255 * sh["opacity"]),))
        layer = layer.filter(ImageFilter.GaussianBlur(sh["blur"]))
        ld = ImageDraw.Draw(layer)
        ld.text((pad - bb[0], pad - bb[1]), text, font=f, fill=(255, 255, 255, 255))

        if scale != 1.0:
            layer = layer.resize((max(2, int(layer.width * scale)),
                                  max(2, int(layer.height * scale))), Image.LANCZOS)

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
    header = (
        f'Voice: {vo["voice"]}  |  Stability {vo["stability"]}  |  '
        f'Similarity {vo["similarity"]}  |  Style {vo["style"]}  |  '
        f'Speaker Boost {"ON" if vo["speaker_boost"] else "OFF"}\n'
    )
    alt = vo.get("calm_variant") or vo.get("upbeat_variant")
    if alt:
        header += (f'Alt read: Stability {alt.get("stability", vo["stability"])}, '
                   f'Style {alt.get("style", vo["style"])}\n')
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
