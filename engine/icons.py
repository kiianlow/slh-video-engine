"""Icon loading for the SLH engine.

Order of resolution for a scene's `icon` key:
  1. assets/icons/<folder>/<file>.png  -- your real Flaticon/Fluent pack
  2. assets/icons/_generated/<key>.png -- cached procedural fallback
  3. generate a Fluent-style fallback now, cache it, and flag it

The brand rule is NO RED. Any icon whose manifest entry is flagged `red: true`
gets hue-shifted into the scene accent before use.
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFilter

from motion import hex_to_rgb

ICON_SIZE = 512
_SUBSTITUTIONS = []


def substitutions():
    """Anything the engine had to fake. build.py prints this at the end."""
    return list(_SUBSTITUTIONS)


def load_manifest(repo_root):
    path = os.path.join(repo_root, "config", "icons.json")
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------ red removal ---

def strip_red(img, accent_hex):
    """Push red-dominant pixels toward the scene accent. Keeps luminance."""
    accent = hex_to_rgb(accent_hex)
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r > 110 and r > g * 1.45 and r > b * 1.45:
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                lum = 0.45 + lum * 0.55
                px[x, y] = (
                    int(min(255, accent[0] * lum)),
                    int(min(255, accent[1] * lum)),
                    int(min(255, accent[2] * lum)),
                    a,
                )
    return img


# ------------------------------------------------- procedural fallback -----

def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _soft_shadow(size, shape_fn, blur=26, opacity=70, offset=(0, 16)):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shape_fn(d, (0, 0, 0, opacity))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    shifted = Image.new("RGBA", size, (0, 0, 0, 0))
    shifted.paste(layer, offset)
    return shifted


def _gradient_ball(size, top_hex, bottom_hex):
    """A soft 3D sphere-ish gradient used as the base of generated icons."""
    top, bot = hex_to_rgb(top_hex), hex_to_rgb(bottom_hex)
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / max(1, size - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=c + (255,))
    return g


PALETTES = {
    "property": ("#8FA9C9", "#4E6E96"),
    "house": ("#E5B76A", "#C07B4F"),
    "money": ("#8FBF7A", "#4F8A5C"),
    "coin": ("#F2CF6B", "#C7A24B"),
    "doc": ("#9EC6E0", "#5E8CA8"),
    "check": ("#93C47D", "#4F8A5C"),
    "warn": ("#E8B75E", "#C7852B"),
    "bank": ("#B7A9D9", "#7A6BAE"),
    "chat": ("#7FC7C0", "#5E8C86"),
    "default": ("#D4B896", "#B0764F"),
}


def _shape_for(kind):
    """Return a drawing routine for the generated icon body."""
    def house(d, S, top, bot):
        roof = [(S * 0.5, S * 0.20), (S * 0.88, S * 0.50), (S * 0.12, S * 0.50)]
        d.polygon(roof, fill=_shade(bot, 0.92))
        d.rounded_rectangle([S * 0.22, S * 0.48, S * 0.78, S * 0.84], radius=int(S * 0.06), fill=top)
        d.rounded_rectangle([S * 0.42, S * 0.60, S * 0.58, S * 0.84], radius=int(S * 0.03), fill=_shade(bot, 0.80))

    def tower(d, S, top, bot):
        d.rounded_rectangle([S * 0.20, S * 0.22, S * 0.50, S * 0.86], radius=int(S * 0.05), fill=top)
        d.rounded_rectangle([S * 0.52, S * 0.40, S * 0.80, S * 0.86], radius=int(S * 0.05), fill=_shade(bot, 0.95))
        for row in range(4):
            for col in range(2):
                x = S * (0.26 + col * 0.11)
                y = S * (0.30 + row * 0.13)
                d.rounded_rectangle([x, y, x + S * 0.07, y + S * 0.08], radius=int(S * 0.015),
                                    fill=_shade(bot, 0.65))

    def coin(d, S, top, bot):
        d.ellipse([S * 0.14, S * 0.18, S * 0.86, S * 0.82], fill=top)
        d.ellipse([S * 0.24, S * 0.27, S * 0.76, S * 0.73], fill=_shade(bot, 1.06))

    def note(d, S, top, bot):
        d.rounded_rectangle([S * 0.12, S * 0.30, S * 0.88, S * 0.72], radius=int(S * 0.06), fill=top)
        d.ellipse([S * 0.40, S * 0.40, S * 0.60, S * 0.62], fill=_shade(bot, 0.85))

    def doc(d, S, top, bot):
        d.rounded_rectangle([S * 0.22, S * 0.14, S * 0.78, S * 0.86], radius=int(S * 0.07), fill=top)
        for i in range(4):
            y = S * (0.32 + i * 0.13)
            d.rounded_rectangle([S * 0.32, y, S * 0.68, y + S * 0.045], radius=int(S * 0.02),
                                fill=_shade(bot, 0.75))

    def check(d, S, top, bot):
        d.ellipse([S * 0.12, S * 0.12, S * 0.88, S * 0.88], fill=top)
        d.line([(S * 0.32, S * 0.52), (S * 0.45, S * 0.66), (S * 0.70, S * 0.36)],
               fill=(255, 255, 255, 255), width=int(S * 0.09), joint="curve")

    def cross(d, S, top, bot):
        d.ellipse([S * 0.12, S * 0.12, S * 0.88, S * 0.88], fill=top)
        for a, b in (((0.35, 0.35), (0.65, 0.65)), ((0.65, 0.35), (0.35, 0.65))):
            d.line([(S * a[0], S * a[1]), (S * b[0], S * b[1])],
                   fill=(255, 255, 255, 255), width=int(S * 0.085))

    def arrow(d, S, top, bot):
        d.rounded_rectangle([S * 0.14, S * 0.16, S * 0.86, S * 0.84], radius=int(S * 0.12), fill=_shade(top, 1.02))
        d.line([(S * 0.28, S * 0.66), (S * 0.45, S * 0.48), (S * 0.58, S * 0.58), (S * 0.75, S * 0.34)],
               fill=(255, 255, 255, 255), width=int(S * 0.065), joint="curve")
        d.polygon([(S * 0.78, S * 0.30), (S * 0.78, S * 0.48), (S * 0.60, S * 0.32)], fill=(255, 255, 255, 255))

    def bank(d, S, top, bot):
        d.polygon([(S * 0.50, S * 0.16), (S * 0.90, S * 0.38), (S * 0.10, S * 0.38)], fill=_shade(bot, 0.92))
        for i in range(4):
            x = S * (0.20 + i * 0.17)
            d.rounded_rectangle([x, S * 0.42, x + S * 0.10, S * 0.76], radius=int(S * 0.02), fill=top)
        d.rounded_rectangle([S * 0.12, S * 0.78, S * 0.88, S * 0.88], radius=int(S * 0.03), fill=_shade(bot, 0.95))

    def chat(d, S, top, bot):
        d.rounded_rectangle([S * 0.12, S * 0.20, S * 0.88, S * 0.70], radius=int(S * 0.12), fill=top)
        d.polygon([(S * 0.30, S * 0.68), (S * 0.30, S * 0.88), (S * 0.50, S * 0.68)], fill=top)
        for i in range(3):
            cx = S * (0.34 + i * 0.16)
            d.ellipse([cx, S * 0.42, cx + S * 0.07, S * 0.49], fill=(255, 255, 255, 235))

    def handshake(d, S, top, bot):
        d.rounded_rectangle([S * 0.10, S * 0.42, S * 0.48, S * 0.62], radius=int(S * 0.08), fill=top)
        d.rounded_rectangle([S * 0.52, S * 0.42, S * 0.90, S * 0.62], radius=int(S * 0.08), fill=_shade(bot, 0.95))
        d.ellipse([S * 0.38, S * 0.36, S * 0.62, S * 0.68], fill=_shade(top, 1.10))

    def calc(d, S, top, bot):
        d.rounded_rectangle([S * 0.20, S * 0.12, S * 0.80, S * 0.88], radius=int(S * 0.09), fill=top)
        d.rounded_rectangle([S * 0.29, S * 0.21, S * 0.71, S * 0.37], radius=int(S * 0.03),
                            fill=(255, 255, 255, 225))
        for r in range(3):
            for c in range(3):
                x = S * (0.29 + c * 0.15)
                y = S * (0.44 + r * 0.14)
                d.ellipse([x, y, x + S * 0.09, y + S * 0.09], fill=_shade(bot, 0.72))

    return {
        "house": house, "tower": tower, "coin": coin, "note": note, "doc": doc,
        "check": check, "cross": cross, "arrow": arrow, "bank": bank,
        "chat": chat, "handshake": handshake, "calc": calc,
    }.get(kind, house)


def generate_icon(kind, palette_key="default", size=ICON_SIZE):
    """Build a colourful, rounded, soft-3D icon in the Fluent Emoji spirit."""
    top_hex, bot_hex = PALETTES.get(palette_key, PALETTES["default"])
    top, bot = hex_to_rgb(top_hex), hex_to_rgb(bot_hex)
    S = size

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shape = _shape_for(kind)

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    shape(sd, S, (0, 0, 0, 90), (0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(S * 0.045)))
    off = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    off.paste(shadow, (0, int(S * 0.03)))
    img = Image.alpha_composite(img, off)

    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    shape(bd, S, top + (255,), bot + (255,))
    img = Image.alpha_composite(img, body)

    # top-left sheen for the soft 3D read
    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shd = ImageDraw.Draw(sheen)
    shd.ellipse([-S * 0.15, -S * 0.30, S * 0.75, S * 0.45], fill=(255, 255, 255, 42))
    sheen = sheen.filter(ImageFilter.GaussianBlur(int(S * 0.05)))
    mask = body.getchannel("A")
    img = Image.alpha_composite(img, Image.composite(sheen, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))
    return img


# ---------------------------------------------------------------- loader ----

def get_icon(repo_root, key, accent_hex, size=ICON_SIZE):
    manifest = load_manifest(repo_root)
    entry = manifest["icons"].get(key)
    if entry is None:
        entry = {"file": None, "red": False, "fallback": "house", "palette": "default"}
        _SUBSTITUTIONS.append(f"icon '{key}' is not in config/icons.json -- generated a generic fallback")

    real = None
    if entry.get("file"):
        candidate = os.path.join(repo_root, "assets", "icons", entry["file"])
        if os.path.exists(candidate):
            real = candidate

    if real:
        img = Image.open(real).convert("RGBA")
        if entry.get("red"):
            img = strip_red(img, accent_hex)
    else:
        cache_dir = os.path.join(repo_root, "assets", "icons", "_generated")
        os.makedirs(cache_dir, exist_ok=True)
        cache = os.path.join(cache_dir, f"{key}.png")
        if os.path.exists(cache):
            img = Image.open(cache).convert("RGBA")
        else:
            img = generate_icon(entry.get("fallback", "house"), entry.get("palette", "default"))
            img.save(cache)
            _SUBSTITUTIONS.append(
                f"icon '{key}' -> {entry.get('file') or 'no file mapped'} not found in assets/icons/, "
                f"generated a Fluent-style stand-in"
            )

    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    return img
