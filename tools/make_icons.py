#!/usr/bin/env python3
"""Generate the SLH icon set: 23 icons in a 3D Fluent-Emoji style.

Built because the original Flaticon pack was lost. These are drawn, not traced
from anything, so there is no licence question.

Technique, which is what separates this from the flat fallbacks:
  - every element is a mask, filled with a vertical gradient
  - a blurred white ellipse clipped to the mask gives the top-left sheen
  - a blurred dark band clipped to the bottom of the mask gives the roll-off
  - a soft drop shadow sits under the whole icon
  - drawn at 4x and downsampled, so curves and diagonals stay clean

Run:  python tools/make_icons.py
Out:  assets/icons/slh/<name>.png  (512x512 RGBA)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

SS = 4                      # supersample
OUT = 512
S = OUT * SS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "assets", "icons", "slh")

# Brand-safe palettes. No red anywhere -- warnings use amber, negatives use slate.
PAL = {
    "sand":   ("#F0D9B5", "#C89A63"),
    "clay":   ("#D9A273", "#A86A3E"),
    "brick":  ("#C98D6B", "#96593A"),
    "teal":   ("#8FC9C2", "#4E8880"),
    "blue":   ("#9BBEDC", "#5A7FA6"),
    "navy":   ("#7C93B8", "#3D5478"),
    "green":  ("#A6CE8E", "#5B8E52"),
    "olive":  ("#C2CE93", "#7E8A4C"),
    "gold":   ("#F5D778", "#C9A038"),
    "amber":  ("#F0BC72", "#C4873A"),
    "plum":   ("#BFA8CE", "#7E639B"),
    "slate":  ("#B4B9C2", "#6E7684"),
    "cream":  ("#FBF3E6", "#DCCBB2"),
    "white":  ("#FFFFFF", "#E4E4E4"),
}


def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient(size, top, bot):
    g = Image.new("RGB", (1, size))
    d = ImageDraw.Draw(g)
    t, b = hx(top), hx(bot)
    for y in range(size):
        f = y / max(1, size - 1)
        d.point((0, y), fill=tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3)))
    return g.resize((size, size))


def shape(mask_fn, palette, sheen=0.42, roll=0.30):
    """One 3D element: gradient body + top-left sheen + bottom roll-off."""
    mask = Image.new("L", (S, S), 0)
    mask_fn(ImageDraw.Draw(mask))

    top, bot = PAL[palette]
    body = gradient(S, top, bot).convert("RGBA")
    body.putalpha(mask)

    if sheen > 0:
        sh = Image.new("L", (S, S), 0)
        ImageDraw.Draw(sh).ellipse(
            [-S * 0.20, -S * 0.34, S * 0.78, S * 0.46], fill=int(255 * sheen))
        sh = sh.filter(ImageFilter.GaussianBlur(S * 0.055))
        light = Image.new("RGBA", (S, S), (255, 255, 255, 0))
        light.putalpha(Image.composite(sh, Image.new("L", (S, S), 0), mask))
        body = Image.alpha_composite(body, light)

    if roll > 0:
        rl = Image.new("L", (S, S), 0)
        ImageDraw.Draw(rl).ellipse(
            [S * 0.06, S * 0.62, S * 1.06, S * 1.30], fill=int(255 * roll))
        rl = rl.filter(ImageFilter.GaussianBlur(S * 0.05))
        dark = Image.new("RGBA", (S, S), (60, 40, 25, 0))
        dark.putalpha(Image.composite(rl, Image.new("L", (S, S), 0), mask))
        body = Image.alpha_composite(body, dark)

    return body, mask


def build(parts, shadow=True):
    """Compose elements bottom-up, then lay a soft drop shadow under them."""
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    union = Image.new("L", (S, S), 0)
    layers = []
    for fn, pal, kw in parts:
        img, m = shape(fn, pal, **kw)
        layers.append(img)
        union = Image.composite(Image.new("L", (S, S), 255), union, m)

    if shadow:
        sh = union.filter(ImageFilter.GaussianBlur(S * 0.035)).point(lambda v: int(v * 0.34))
        sl = Image.new("RGBA", (S, S), (58, 40, 28, 0))
        sl.putalpha(sh)
        off = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        off.paste(sl, (0, int(S * 0.028)))
        canvas = Image.alpha_composite(canvas, off)

    for img in layers:
        canvas = Image.alpha_composite(canvas, img)
    return canvas.resize((OUT, OUT), Image.LANCZOS)


def R(x0, y0, x1, y1, r=0.05):
    return lambda d: d.rounded_rectangle([S * x0, S * y0, S * x1, S * y1],
                                         radius=S * r, fill=255)


def E(x0, y0, x1, y1):
    return lambda d: d.ellipse([S * x0, S * y0, S * x1, S * y1], fill=255)


def P(pts):
    return lambda d: d.polygon([(S * x, S * y) for x, y in pts], fill=255)


def T(ch, cx, cy, size):
    """Glyph mask in Nunito Black. Currency symbols drawn as polygons come out
    malformed; the real glyph does not."""
    from PIL import ImageFont
    path = os.path.join(ROOT, "assets", "fonts", "NunitoSans-Black.ttf")

    def draw(d):
        f = ImageFont.truetype(path, int(S * size))
        bb = d.textbbox((0, 0), ch, font=f)
        d.text((S * cx - (bb[2] - bb[0]) / 2 - bb[0],
                S * cy - (bb[3] - bb[1]) / 2 - bb[1]), ch, font=f, fill=255)
    return draw


def multi(*fns):
    def draw(d):
        for f in fns:
            f(d)
    return draw


N = {}          # no sheen/roll tweaks
FLAT = {"sheen": 0.30, "roll": 0.20}
DEEP = {"sheen": 0.50, "roll": 0.36}


def windows(x0, y0, cols, rows, w=0.075, h=0.085, gx=0.115, gy=0.135):
    def draw(d):
        for r in range(rows):
            for c in range(cols):
                x, y = x0 + c * gx, y0 + r * gy
                d.rounded_rectangle([S * x, S * y, S * (x + w), S * (y + h)],
                                    radius=S * 0.016, fill=255)
    return draw


# ------------------------------------------------------------------ icons ---

def house_base(pal="sand", roof="brick"):
    return [
        (P([(0.50, 0.14), (0.93, 0.47), (0.07, 0.47)]), roof, DEEP),
        (R(0.19, 0.45, 0.81, 0.84, 0.05), pal, N),
        (R(0.41, 0.60, 0.59, 0.84, 0.02), "brick", FLAT),
        (E(0.44, 0.50, 0.56, 0.57), "cream", FLAT),
    ]


ICONS = {
    # --- property -------------------------------------------------------
    "ownership": house_base("sand", "brick"),
    "landed": [
        (P([(0.50, 0.16), (0.90, 0.44), (0.10, 0.44)]), "olive", DEEP),
        (R(0.16, 0.42, 0.84, 0.82, 0.05), "cream", N),
        (R(0.38, 0.56, 0.54, 0.82, 0.02), "olive", FLAT),
        (R(0.60, 0.54, 0.74, 0.66, 0.02), "blue", FLAT),
        (R(0.14, 0.82, 0.86, 0.88, 0.03), "green", FLAT),
    ],
    "newlaunch": [
        (R(0.20, 0.16, 0.52, 0.86, 0.04), "blue", N),
        (R(0.52, 0.34, 0.80, 0.86, 0.04), "navy", N),
        (windows(0.245, 0.235, 2, 4), "cream", FLAT),
        (windows(0.575, 0.415, 2, 3), "cream", FLAT),
    ],
    "resale": [
        (R(0.24, 0.22, 0.76, 0.86, 0.05), "clay", N),
        (windows(0.295, 0.30, 3, 4), "cream", FLAT),
        (R(0.20, 0.16, 0.80, 0.24, 0.03), "brick", DEEP),
    ],
    "skyline": [
        (R(0.10, 0.40, 0.34, 0.88, 0.03), "navy", N),
        (R(0.36, 0.18, 0.64, 0.88, 0.035), "blue", N),
        (R(0.66, 0.48, 0.90, 0.88, 0.03), "slate", N),
        (windows(0.135, 0.455, 2, 3), "cream", FLAT),
        (windows(0.395, 0.245, 2, 4), "cream", FLAT),
        (windows(0.695, 0.535, 2, 2), "cream", FLAT),
    ],
    "neighbourhood": [
        (P([(0.26, 0.30), (0.46, 0.44), (0.06, 0.44)]), "brick", DEEP),
        (R(0.10, 0.43, 0.42, 0.86, 0.04), "sand", N),
        (P([(0.70, 0.20), (0.94, 0.37), (0.46, 0.37)]), "olive", DEEP),
        (R(0.50, 0.36, 0.90, 0.86, 0.04), "cream", N),
        (R(0.60, 0.52, 0.72, 0.66, 0.02), "olive", FLAT),
    ],
    "rental": [
        (P([(0.42, 0.12), (0.80, 0.38), (0.04, 0.38)]), "teal", DEEP),
        (R(0.10, 0.36, 0.74, 0.76, 0.05), "cream", N),
        (E(0.54, 0.56, 0.74, 0.76), "gold", DEEP),
        (E(0.60, 0.62, 0.68, 0.70), "cream", FLAT),
        (R(0.70, 0.645, 0.94, 0.685, 0.018), "gold", FLAT),
        (R(0.84, 0.685, 0.88, 0.755, 0.014), "gold", FLAT),
        (R(0.905, 0.685, 0.945, 0.745, 0.014), "gold", FLAT),
    ],

    # --- money ----------------------------------------------------------
    "coin": [
        (E(0.12, 0.16, 0.88, 0.84), "gold", DEEP),
        (E(0.21, 0.24, 0.79, 0.76), "amber", FLAT),
        (T("$", 0.50, 0.50, 0.44), "cream", FLAT),
    ],
    "cash": [
        (R(0.08, 0.30, 0.92, 0.70, 0.06), "green", N),
        (R(0.15, 0.36, 0.85, 0.64, 0.04), "olive", FLAT),
        (E(0.41, 0.40, 0.59, 0.60), "gold", DEEP),
    ],
    "profit": [
        (R(0.06, 0.36, 0.78, 0.72, 0.06), "olive", N),
        (R(0.14, 0.28, 0.86, 0.64, 0.06), "green", N),
        (E(0.41, 0.36, 0.59, 0.56), "gold", DEEP),
    ],
    "income": [
        (R(0.10, 0.24, 0.90, 0.76, 0.06), "teal", N),
        (R(0.18, 0.32, 0.62, 0.38, 0.02), "cream", FLAT),
        (R(0.18, 0.44, 0.50, 0.50, 0.02), "cream", FLAT),
        (E(0.62, 0.50, 0.86, 0.72), "gold", DEEP),
    ],
    "price": [
        (P([(0.14, 0.46), (0.48, 0.12), (0.88, 0.12), (0.88, 0.52),
            (0.54, 0.86), (0.14, 0.46)]), "green", DEEP),
        (E(0.70, 0.20, 0.80, 0.30), "cream", FLAT),
        (T("$", 0.44, 0.50, 0.34), "cream", FLAT),
    ],
    "growth": [
        (R(0.10, 0.12, 0.90, 0.88, 0.10), "cream", N),
        (R(0.22, 0.58, 0.34, 0.78, 0.02), "teal", FLAT),
        (R(0.38, 0.46, 0.50, 0.78, 0.02), "green", FLAT),
        (R(0.54, 0.32, 0.66, 0.78, 0.02), "olive", FLAT),
        (P([(0.70, 0.24), (0.86, 0.24), (0.86, 0.40), (0.80, 0.34),
            (0.72, 0.44), (0.66, 0.38), (0.74, 0.28)]), "gold", DEEP),
    ],
    "bank": [
        (P([(0.50, 0.14), (0.94, 0.36), (0.06, 0.36)]), "navy", DEEP),
        (R(0.16, 0.38, 0.26, 0.76, 0.02), "blue", N),
        (R(0.34, 0.38, 0.44, 0.76, 0.02), "blue", N),
        (R(0.56, 0.38, 0.66, 0.76, 0.02), "blue", N),
        (R(0.74, 0.38, 0.84, 0.76, 0.02), "blue", N),
        (R(0.08, 0.78, 0.92, 0.88, 0.03), "navy", FLAT),
    ],
    "card": [
        (R(0.08, 0.26, 0.92, 0.74, 0.07), "plum", N),
        (R(0.08, 0.36, 0.92, 0.47, 0.0), "navy", FLAT),
        (R(0.16, 0.56, 0.44, 0.63, 0.02), "cream", FLAT),
        (R(0.68, 0.54, 0.86, 0.66, 0.03), "gold", FLAT),
    ],
    "affordability": [
        (R(0.22, 0.10, 0.78, 0.90, 0.09), "slate", N),
        (R(0.30, 0.18, 0.70, 0.34, 0.03), "cream", FLAT),
        (windows(0.305, 0.42, 3, 3, 0.09, 0.09, 0.13, 0.14), "blue", FLAT),
    ],
    "deal": [
        (P([(0.04, 0.36), (0.24, 0.30), (0.56, 0.52), (0.44, 0.66)]), "sand", N),
        (P([(0.96, 0.36), (0.76, 0.30), (0.44, 0.52), (0.56, 0.66)]), "clay", N),
        (R(0.38, 0.44, 0.62, 0.64, 0.08), "gold", DEEP),
        (R(0.02, 0.28, 0.16, 0.44, 0.05), "sand", FLAT),
        (R(0.84, 0.28, 0.98, 0.44, 0.05), "clay", FLAT),
    ],

    # --- signs ----------------------------------------------------------
    "contract": [
        (R(0.22, 0.10, 0.78, 0.90, 0.07), "cream", N),
        (R(0.32, 0.26, 0.68, 0.32, 0.02), "slate", FLAT),
        (R(0.32, 0.40, 0.68, 0.46, 0.02), "slate", FLAT),
        (R(0.32, 0.54, 0.56, 0.60, 0.02), "slate", FLAT),
        (E(0.54, 0.66, 0.76, 0.84), "clay", DEEP),
    ],
    "otp": [
        (R(0.18, 0.12, 0.74, 0.82, 0.06), "cream", N),
        (R(0.28, 0.28, 0.64, 0.34, 0.02), "blue", FLAT),
        (R(0.28, 0.42, 0.64, 0.48, 0.02), "blue", FLAT),
        (E(0.50, 0.56, 0.88, 0.92), "green", DEEP),
    ],
    "yes": [
        (E(0.10, 0.10, 0.90, 0.90), "green", DEEP),
        (P([(0.30, 0.50), (0.38, 0.42), (0.45, 0.58), (0.66, 0.34),
            (0.74, 0.42), (0.46, 0.72)]), "white", FLAT),
    ],
    "no": [
        (E(0.10, 0.10, 0.90, 0.90), "slate", DEEP),
        (P([(0.34, 0.28), (0.50, 0.44), (0.66, 0.28), (0.72, 0.34),
            (0.56, 0.50), (0.72, 0.66), (0.66, 0.72), (0.50, 0.56),
            (0.34, 0.72), (0.28, 0.66), (0.44, 0.50), (0.28, 0.34)]),
         "white", FLAT),
    ],
    "mistake": [
        (P([(0.50, 0.10), (0.94, 0.86), (0.06, 0.86)]), "amber", DEEP),
        (R(0.465, 0.36, 0.535, 0.62, 0.02), "white", FLAT),
        (E(0.455, 0.66, 0.545, 0.75), "white", FLAT),
    ],

    # --- lifestyle, location, timing -------------------------------------
    "clock": [
        (E(0.10, 0.10, 0.90, 0.90), "blue", DEEP),
        (E(0.19, 0.19, 0.81, 0.81), "cream", FLAT),
        (R(0.478, 0.28, 0.522, 0.52, 0.018), "navy", FLAT),
        (R(0.50, 0.478, 0.70, 0.522, 0.018), "navy", FLAT),
        (E(0.465, 0.465, 0.535, 0.535), "clay", FLAT),
    ],
    "calendar": [
        (R(0.10, 0.18, 0.90, 0.88, 0.07), "cream", N),
        (R(0.10, 0.18, 0.90, 0.36, 0.07), "clay", DEEP),
        (R(0.26, 0.10, 0.34, 0.26, 0.03), "brick", FLAT),
        (R(0.66, 0.10, 0.74, 0.26, 0.03), "brick", FLAT),
        (windows(0.19, 0.46, 4, 2, 0.10, 0.11, 0.155, 0.17), "blue", FLAT),
    ],
    "lock": [
        (R(0.30, 0.14, 0.70, 0.52, 0.20), "slate", N),
        (R(0.38, 0.24, 0.62, 0.52, 0.12), "cream", FLAT),
        (R(0.16, 0.44, 0.84, 0.88, 0.09), "gold", DEEP),
        (E(0.44, 0.58, 0.56, 0.70), "amber", FLAT),
        (R(0.475, 0.65, 0.525, 0.78, 0.016), "amber", FLAT),
    ],
    "mrt": [
        (R(0.20, 0.12, 0.80, 0.74, 0.14), "blue", N),
        (R(0.28, 0.22, 0.72, 0.44, 0.05), "cream", FLAT),
        (E(0.28, 0.54, 0.40, 0.66), "gold", FLAT),
        (E(0.60, 0.54, 0.72, 0.66), "gold", FLAT),
        (R(0.22, 0.76, 0.40, 0.90, 0.04), "navy", FLAT),
        (R(0.60, 0.76, 0.78, 0.90, 0.04), "navy", FLAT),
    ],
    "school": [
        (P([(0.50, 0.10), (0.92, 0.38), (0.08, 0.38)]), "brick", DEEP),
        (R(0.14, 0.36, 0.86, 0.86, 0.05), "sand", N),
        (R(0.42, 0.56, 0.58, 0.86, 0.02), "brick", FLAT),
        (R(0.22, 0.48, 0.34, 0.60, 0.02), "blue", FLAT),
        (R(0.66, 0.48, 0.78, 0.60, 0.02), "blue", FLAT),
    ],
    "location": [
        (P([(0.50, 0.92), (0.16, 0.46), (0.84, 0.46)]), "clay", FLAT),
        (E(0.16, 0.08, 0.84, 0.76), "brick", DEEP),
        (E(0.34, 0.26, 0.66, 0.58), "cream", FLAT),
    ],
    "compare": [
        (R(0.475, 0.12, 0.525, 0.86, 0.018), "slate", N),
        (R(0.20, 0.84, 0.80, 0.90, 0.025), "slate", FLAT),
        (R(0.10, 0.26, 0.90, 0.32, 0.025), "navy", FLAT),
        (P([(0.20, 0.32), (0.34, 0.56), (0.06, 0.56)]), "teal", DEEP),
        (P([(0.80, 0.32), (0.94, 0.56), (0.66, 0.56)]), "gold", DEEP),
    ],
    "shield": [
        (P([(0.50, 0.08), (0.86, 0.24), (0.86, 0.54), (0.50, 0.92),
            (0.14, 0.54), (0.14, 0.24)]), "teal", DEEP),
        (P([(0.32, 0.48), (0.40, 0.40), (0.46, 0.56), (0.66, 0.34),
            (0.74, 0.42), (0.47, 0.70)]), "white", FLAT),
    ],
    "family": [
        (E(0.10, 0.20, 0.34, 0.44), "sand", DEEP),
        (P([(0.06, 0.86), (0.10, 0.54), (0.34, 0.54), (0.38, 0.86)]), "clay", N),
        (E(0.62, 0.16, 0.90, 0.44), "cream", DEEP),
        (P([(0.58, 0.86), (0.62, 0.52), (0.90, 0.52), (0.94, 0.86)]), "teal", N),
        (E(0.40, 0.44, 0.58, 0.62), "gold", DEEP),
        (P([(0.36, 0.86), (0.40, 0.66), (0.58, 0.66), (0.62, 0.86)]), "amber", N),
    ],
    "briefcase": [
        (R(0.36, 0.12, 0.64, 0.28, 0.05), "brick", FLAT),
        (R(0.08, 0.26, 0.92, 0.84, 0.07), "clay", N),
        (R(0.08, 0.46, 0.92, 0.56, 0.0), "brick", FLAT),
        (R(0.44, 0.44, 0.56, 0.58, 0.03), "gold", FLAT),
    ],
    "park": [
        (E(0.22, 0.10, 0.78, 0.58), "green", DEEP),
        (E(0.10, 0.28, 0.52, 0.66), "olive", DEEP),
        (E(0.50, 0.30, 0.90, 0.66), "olive", DEEP),
        (R(0.455, 0.56, 0.545, 0.90, 0.02), "brick", N),
    ],
    "portfolio": [
        (E(0.10, 0.10, 0.90, 0.90), "cream", DEEP),
        (P([(0.50, 0.50), (0.50, 0.10), (0.86, 0.26), (0.84, 0.46)]), "teal", FLAT),
        (P([(0.50, 0.50), (0.84, 0.50), (0.72, 0.84)]), "gold", FLAT),
        (P([(0.50, 0.50), (0.66, 0.86), (0.24, 0.76)]), "clay", FLAT),
        (E(0.42, 0.42, 0.58, 0.58), "cream", FLAT),
    ],
    "best": [
        (R(0.30, 0.66, 0.70, 0.74, 0.03), "brick", FLAT),
        (R(0.42, 0.52, 0.58, 0.70, 0.02), "brick", N),
        (P([(0.28, 0.12), (0.72, 0.12), (0.68, 0.44), (0.50, 0.58),
            (0.32, 0.44)]), "gold", DEEP),
        (R(0.24, 0.76, 0.76, 0.88, 0.04), "amber", N),
        (E(0.44, 0.22, 0.56, 0.34), "cream", FLAT),
    ],
    "tip": [
        (E(0.26, 0.08, 0.74, 0.56), "gold", DEEP),
        (R(0.42, 0.46, 0.58, 0.72, 0.03), "amber", N),
        (R(0.40, 0.72, 0.60, 0.78, 0.02), "slate", FLAT),
        (R(0.42, 0.80, 0.58, 0.86, 0.02), "slate", FLAT),
    ],
    "search": [
        (E(0.10, 0.08, 0.72, 0.70), "blue", DEEP),
        (E(0.20, 0.18, 0.62, 0.60), "cream", FLAT),
        (R(0.60, 0.62, 0.92, 0.76, 0.06), "navy", N),
    ],
    "dm": [
        (R(0.08, 0.18, 0.92, 0.68, 0.11), "teal", N),
        (P([(0.28, 0.66), (0.28, 0.90), (0.52, 0.66)]), "teal", FLAT),
        (E(0.26, 0.38, 0.35, 0.47), "cream", FLAT),
        (E(0.455, 0.38, 0.545, 0.47), "cream", FLAT),
        (E(0.65, 0.38, 0.74, 0.47), "cream", FLAT),
    ],
}


def main():
    os.makedirs(DEST, exist_ok=True)
    for name, parts in ICONS.items():
        img = build(parts)
        img.save(os.path.join(DEST, f"{name}.png"))
        print("wrote", name)
    print(f"\n{len(ICONS)} icons -> {DEST}")


if __name__ == "__main__":
    main()
