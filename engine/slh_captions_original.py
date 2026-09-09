"""
slh_captions.py — Burned-in word-by-word captions for the SLH render pipeline.

Style matches the locked SLH look: single active word, all-caps, white fill,
heavy soft dark shadow, centred, sitting in the lower-middle caption zone.
Pops in per word with a back-out scale.

Timing sources, in priority order:
  1. ElevenLabs word alignment JSON  -> CaptionTrack.from_elevenlabs(path)
  2. An .srt file                    -> CaptionTrack.from_srt(path)
  3. Auto-distribute from the script -> CaptionTrack.from_scenes(scenes)  [APPROX — flag it]

Usage in the frame loop:
    track = CaptionTrack.from_elevenlabs("vo_alignment.json")   # or from_scenes(...)
    ...
    frame = track.draw(frame, t)   # t = seconds; returns the frame with the active word burned in

Anti-ghost: every call composites onto a FRESH RGBA layer with a FRESH ImageDraw,
then alpha_composites onto the frame. Never reuses a draw handle across frames.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------------------------------------------------------------------
# LOCKED CAPTION STYLE  (edit here only)
# ----------------------------------------------------------------------------
W, H = 1080, 1920

# Brand font. Nunito Sans Black 900 is spec; Poppins Bold is the env fallback.
FONT_PATH_PRIMARY = "/home/claude/NunitoSans_10pt-Black.ttf"   # swap-in when synced
FONT_PATH_FALLBACK = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

FONT_SIZE      = 96            # active word size (large, single word)
CAP_Y_FRAC     = 0.58         # vertical centre of the caption, fraction of H
FILL           = (255, 255, 255, 255)        # white word
OUTLINE        = (255, 255, 255, 0)          # no hard outline (reference has none)
OUTLINE_W      = 0
SHADOW_COLOR   = (70, 52, 40, 95)            # soft, light brown-grey shadow (low opacity)
SHADOW_OFFSET  = (0, 5)                       # small, down
SHADOW_BLUR    = 9                            # soft, not heavy
ALL_CAPS       = True
POP_DURATION   = 0.12         # per-word pop-in length (s)
POP_FROM       = 0.72         # start scale of the pop
HOLD_SCALE     = 1.0

# group tiny words (<= this many chars) onto the next word so cues read cleanly.
# set to 0 to force strictly one word per cue (matches the reference frames).
GROUP_SHORT_WORDS = 0

# ----------------------------------------------------------------------------
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for p in (FONT_PATH_PRIMARY, FONT_PATH_FALLBACK):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _back_out(x: float, overshoot: float = 1.7) -> float:
    """back-out easing, clamps on output so it never glitches past rest."""
    x = max(0.0, min(1.0, x))
    c1 = overshoot
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _syllables(word: str) -> int:
    """rough English syllable / weight estimate for timing distribution."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        # numbers / $ figures: weight by character count (they read slower)
        digits = re.sub(r"[^0-9]", "", word)
        return max(1, round(len(digits) / 2)) if digits else 1
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


@dataclass
class Cue:
    text: str
    start: float
    end: float


class CaptionTrack:
    def __init__(self, cues: list[Cue]):
        self.cues = sorted(cues, key=lambda c: c.start)
        self._font = _load_font(FONT_SIZE)

    # ---- builders ----------------------------------------------------------
    @classmethod
    def from_scenes(cls, scenes: list[dict]) -> "CaptionTrack":
        """
        APPROXIMATE timing. scenes = [{"text": narration, "start": s, "end": s}, ...]
        Words are spread across each scene's window, weighted by syllable count.
        Flag this as approximate whenever it is used.
        """
        cues: list[Cue] = []
        for sc in scenes:
            words = cls._tokenize(sc["text"])
            if not words:
                continue
            span = max(0.001, sc["end"] - sc["start"])
            weights = [_syllables(w) for w in words]
            total = sum(weights)
            t = sc["start"]
            for w, wt in zip(words, weights):
                dur = span * (wt / total)
                cues.append(Cue(w, t, t + dur))
                t += dur
        return cls(cues)

    @classmethod
    def from_srt(cls, path: str) -> "CaptionTrack":
        cues: list[Cue] = []
        blocks = open(path, encoding="utf-8").read().strip().split("\n\n")
        for b in blocks:
            lines = [l for l in b.splitlines() if l.strip()]
            if len(lines) < 2:
                continue
            tl = next((l for l in lines if "-->" in l), None)
            if not tl:
                continue
            a, bb = [x.strip() for x in tl.split("-->")]
            txt = " ".join(lines[lines.index(tl) + 1:])
            cues.append(Cue(txt, cls._srt_t(a), cls._srt_t(bb)))
        return cls(cues)

    @classmethod
    def from_elevenlabs(cls, path: str) -> "CaptionTrack":
        """
        ElevenLabs alignment JSON. Supports both the word-level export and the
        character-level `alignment` payload (characters + start/end times).
        """
        data = json.load(open(path, encoding="utf-8"))

        # word-level export: [{"word": "...", "start": .., "end": ..}, ...]
        if isinstance(data, list) and data and "word" in data[0]:
            return cls([Cue(d["word"], float(d["start"]), float(d["end"])) for d in data])

        # character-level alignment payload
        al = data.get("alignment") or data
        chars = al.get("characters") or al.get("chars")
        starts = al.get("character_start_times_seconds") or al.get("charStartTimesMs")
        ends = al.get("character_end_times_seconds") or al.get("charEndTimesMs")
        scale = 0.001 if "charStartTimesMs" in al else 1.0
        cues, buf, w_start = [], "", None
        for ch, s, e in zip(chars, starts, ends):
            if ch.isspace():
                if buf:
                    cues.append(Cue(buf, w_start * scale, prev_e * scale))
                    buf, w_start = "", None
            else:
                if not buf:
                    w_start = s
                buf += ch
            prev_e = e
        if buf:
            cues.append(Cue(buf, w_start * scale, prev_e * scale))
        return cls(cues)

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        raw = text.split()
        if GROUP_SHORT_WORDS <= 0:
            return raw
        out, i = [], 0
        while i < len(raw):
            w = raw[i]
            while (len(w) <= GROUP_SHORT_WORDS and i + 1 < len(raw)):
                i += 1
                w = w + " " + raw[i]
            out.append(w)
            i += 1
        return out

    @staticmethod
    def _srt_t(s: str) -> float:
        s = s.replace(",", ".")
        h, m, rest = s.split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest)

    def _active(self, t: float) -> Cue | None:
        for c in self.cues:
            if c.start <= t < c.end:
                return c
        return None

    # ---- render ------------------------------------------------------------
    def draw(self, frame: Image.Image, t: float) -> Image.Image:
        cue = self._active(t)
        if cue is None:
            return frame
        word = cue.text.upper() if ALL_CAPS else cue.text

        # pop-in scale
        prog = (t - cue.start) / POP_DURATION
        scale = POP_FROM + (HOLD_SCALE - POP_FROM) * _back_out(prog) if prog < 1 else HOLD_SCALE

        # FRESH layer + FRESH draw every frame — kills the PIL stale-layer ghost bug
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        # render the word big on its own tile, then scale the tile (crisp pop)
        pad = OUTLINE_W * 2 + SHADOW_BLUR * 2 + 8
        bbox = _load_font(FONT_SIZE).getbbox(word, stroke_width=OUTLINE_W)
        tw = (bbox[2] - bbox[0]) + pad * 2
        th = (bbox[3] - bbox[1]) + pad * 2
        tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        ox, oy = pad - bbox[0], pad - bbox[1]

        # soft shadow pass (separate blurred layer)
        sh = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text(
            (ox + SHADOW_OFFSET[0], oy + SHADOW_OFFSET[1]), word,
            font=self._font, fill=SHADOW_COLOR,
            stroke_width=OUTLINE_W, stroke_fill=SHADOW_COLOR,
        )
        sh = sh.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
        tile = Image.alpha_composite(tile, sh)

        # word with dark outline + white fill
        d = ImageDraw.Draw(tile)
        d.text((ox, oy), word, font=self._font, fill=FILL,
               stroke_width=OUTLINE_W, stroke_fill=OUTLINE)

        if scale != 1.0:
            tile = tile.resize((max(1, int(tw * scale)), max(1, int(th * scale))),
                               Image.LANCZOS)

        cx, cy = W // 2, int(H * CAP_Y_FRAC)
        layer.alpha_composite(tile, (cx - tile.width // 2, cy - tile.height // 2))

        base = frame.convert("RGBA") if frame.mode != "RGBA" else frame
        return Image.alpha_composite(base, layer)


# quick self-test / specimen frame
if __name__ == "__main__":
    scenes = [
        {"text": "If you're earning up to fourteen thousand a month you can buy",
         "start": 0.0, "end": 3.0},
    ]
    track = CaptionTrack.from_scenes(scenes)
    bg = Image.new("RGBA", (W, H), (232, 224, 208, 255))   # beige
    track.draw(bg, 1.4).convert("RGB").save("caption_specimen.jpg", quality=92)
    print("wrote caption_specimen.jpg")
