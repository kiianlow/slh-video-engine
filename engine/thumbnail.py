"""1080x1920 thumbnail generator.

A faithful port of docs/SLH_Thumbnail_Generator.html so thumbnails come out of
the same pipeline as the video instead of a separate manual step. Same layout
constants, same auto-fit behaviour, same optional decoration set.

Constants lifted verbatim from the HTML: TARGET_W 760, MAX_SIZE 158,
MIN_SIZE 34, highlight padding 44.
"""
import os

from PIL import Image, ImageDraw, ImageFont

import motion as mo

TARGET_W = 760
MAX_SIZE = 158
MIN_SIZE = 34
HL_PAD = 44

# Matched against 13 approved thumbnails: header, title, one highlighted line,
# SAVE THIS pill. No divider, no dots, no kicker, no bottom wordmark.
DEFAULT_DECOR = {
    "divider": False, "dots": False, "frame": False, "corners": False,
    "kicker": False, "cta": True, "bottom": False, "watermark": False,
}
OUT_W, OUT_H = 2160, 3840   # approved export size, measured from the references


def _fit(draw, text, fpath, avail):
    """Binary search the largest size that fits, mirroring fitLine()."""
    lo, hi, best = MIN_SIZE, MAX_SIZE, MIN_SIZE
    for _ in range(22):
        mid = (lo + hi) / 2
        f = ImageFont.truetype(fpath, int(mid))
        w = draw.textbbox((0, 0), text, font=f)[2]
        if w <= avail:
            best, lo = mid, mid
        else:
            hi = mid
    return ImageFont.truetype(fpath, int(best))


def render_thumbnail(repo_root, cfg, title_lines, highlight=(1,), kicker="SINGAPORE PROPERTY",
                     cta="SAVE THIS", decor=None, out_path=None, supersample=3):
    """Rendered at `supersample`x then LANCZOS-downsampled.

    PIL rasterises glyphs at the requested pixel size with no hinting, so a
    direct 1080x1920 render reads soft next to the browser canvas version.
    Drawing at 3x and downsampling recovers the edge definition.
    """
    S = max(1, int(supersample))
    W, H = 1080 * S, 1920 * S
    pal = cfg["palette"]["thumbnail"]
    bg, ink, box = (mo.hex_to_rgb(pal["bg"]), mo.hex_to_rgb(pal["ink"]),
                    mo.hex_to_rgb(pal["accent"]))
    black = os.path.join(repo_root, cfg["type"]["headline"]["file"])
    light = os.path.join(repo_root, cfg["type"]["body"]["file"])

    global TARGET_W, MAX_SIZE, MIN_SIZE, HL_PAD
    _TW, _MAX, _MIN, _HL = TARGET_W, MAX_SIZE, MIN_SIZE, HL_PAD
    TARGET_W, MAX_SIZE, MIN_SIZE, HL_PAD = _TW * S, _MAX * S, _MIN * S, _HL * S

    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    dec = dict(DEFAULT_DECOR)
    dec.update(decor or {})
    hl = set(highlight or ())

    img = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(img)

    if dec["watermark"]:
        badge = Image.open(os.path.join(repo_root, cfg["brand"]["badge"])).convert("RGBA")
        wm = badge.resize((780*S, 780*S), Image.LANCZOS)
        wm.putalpha(wm.getchannel("A").point(lambda v: int(v * 0.05)))
        img.alpha_composite(wm, ((W - 780*S) // 2, (H - 780*S) // 2))
        d = ImageDraw.Draw(img)

    if dec["frame"]:
        d.rounded_rectangle([54*S, 54*S, W - 54*S, H - 54*S], radius=18*S, outline=box + (255,), width=5*S)
    if dec["corners"]:
        s, t = 78*S, 6*S
        for cx, cy, hx, hy in ((60*S, 60*S, 1, 1), (W - 60*S - s, 60*S, -1, 1),
                               (60*S, H - 60*S - s, 1, -1), (W - 60*S - s, H - 60*S - s, -1, -1)):
            x = cx if hx > 0 else cx + s
            y = cy if hy > 0 else cy + s
            d.rectangle([min(x, x + hx * s), y - (t if hy < 0 else 0),
                         max(x, x + hx * s), y + (t if hy > 0 else 0)], fill=box + (255,))
            d.rectangle([x - (t if hx < 0 else 0), min(y, y + hy * s),
                         x + (t if hx > 0 else 0), max(y, y + hy * s)], fill=box + (255,))

    # --- measure the centred stack -------------------------------------
    blocks = []
    if dec["kicker"]:
        kf = ImageFont.truetype(black, 30*S)
        blocks.append(("kicker", kicker.upper(), kf, (30 + 18)*S))
    blocks.append(("header", None, None, (74 + 22)*S))
    if dec["divider"]:
        blocks.append(("divider", None, None, (6 + 26)*S))

    lines = [l.strip().upper() for l in title_lines if l.strip()]
    tfonts = []
    for i, ln in enumerate(lines):
        avail = TARGET_W - (HL_PAD if i in hl else 0)
        f = _fit(d0, ln, black, avail)
        tfonts.append(f)
        blocks.append(("tline", ln, f, int(f.size * 0.92) + (15*S if i in hl else 11*S)))

    if dec["cta"]:
        cf = ImageFont.truetype(black, 28*S)
        blocks.append(("cta", cta.upper(), cf, (28 + 32 + 30)*S))
    if dec["dots"]:
        blocks.append(("dots", None, None, (15 + 34)*S))

    trail = {"kicker": 18, "header": 22, "divider": 26, "cta": 30, "dots": 34}
    total = sum(b[3] for b in blocks)
    last = blocks[-1]
    if last[0] == "tline":
        total -= (15 * S if (len(lines) - 1) in hl else 11 * S)
    else:
        total -= trail.get(last[0], 0) * S
    y = (H - total) / 2

    # --- draw ------------------------------------------------------------
    idx = 0
    for kind, text, f, adv in blocks:
        if kind == "kicker":
            sp = 0.22 * f.size
            wtot = sum(d.textbbox((0, 0), c, font=f)[2] + sp for c in text) - sp
            x = (W - wtot) / 2
            for c in text:
                d.text((x, y), c, font=f, fill=box + (255,))
                x += d.textbbox((0, 0), c, font=f)[2] + sp

        elif kind == "header":
            badge = Image.open(os.path.join(repo_root, cfg["brand"]["badge"])).convert("RGBA")
            badge = badge.resize((74*S, 74*S), Image.LANCZOS)
            hf = ImageFont.truetype(black, 32*S)
            handle = cfg["brand"]["handle"]
            sp = 0.06 * 32*S
            hw = sum(d.textbbox((0, 0), c, font=hf)[2] + sp for c in handle) - sp
            tot = 74*S + 18*S + hw
            x = (W - tot) / 2
            img.alpha_composite(badge, (int(x), int(y)))
            d = ImageDraw.Draw(img)
            x += 74*S + 18*S
            for c in handle:
                d.text((x, y + 20*S), c, font=hf, fill=ink + (255,))
                x += d.textbbox((0, 0), c, font=hf)[2] + sp

        elif kind == "divider":
            d.rounded_rectangle([(W - 120*S) / 2, y, (W + 120*S) / 2, y + 6*S], radius=3*S, fill=box + (255,))

        elif kind == "tline":
            bb = d.textbbox((0, 0), text, font=f)
            tw = bb[2] - bb[0]
            if idx in hl:
                bx0, bx1 = (W - tw) / 2 - 22*S, (W + tw) / 2 + 22*S
                d.rectangle([bx0, y - 2*S, bx1, y + f.size + 8*S], fill=box + (255,))
                d.text(((W - tw) / 2 - bb[0], y - bb[1] + 2*S), text, font=f, fill=(255, 255, 255, 255))
            else:
                d.text(((W - tw) / 2 - bb[0], y - bb[1] + 2*S), text, font=f, fill=ink + (255,))
            idx += 1

        elif kind == "cta":
            bb = d.textbbox((0, 0), text, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            pw, ph = tw + 80*S, th + 32*S
            d.rounded_rectangle([(W - pw) / 2, y, (W + pw) / 2, y + ph],
                                radius=int(ph / 2), fill=ink + (255,))
            d.text(((W - tw) / 2 - bb[0], y + 16*S - bb[1]), text, font=f, fill=bg + (255,))

        elif kind == "dots":
            tot = 3 * 15*S + 2 * 18*S
            x = (W - tot) / 2
            for _ in range(3):
                d.ellipse([x, y, x + 15*S, y + 15*S], fill=box + (255,))
                x += 15*S + 18*S
        y += adv

    if dec["bottom"]:
        bf = ImageFont.truetype(light, 26*S)
        name = cfg["brand"]["name"]
        sp = 0.14 * 26*S
        wtot = sum(d.textbbox((0, 0), c, font=bf)[2] + sp for c in name) - sp
        x = (W - wtot) / 2
        for c in name:
            d.text((x, H - 70*S - 26*S), c, font=bf, fill=ink + (255,))
            x += d.textbbox((0, 0), c, font=bf)[2] + sp

    TARGET_W, MAX_SIZE, MIN_SIZE, HL_PAD = _TW, _MAX, _MIN, _HL
    out = img.convert("RGB")
    if (W, H) != (OUT_W, OUT_H):
        out = out.resize((OUT_W, OUT_H), Image.LANCZOS)
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        out.save(out_path, quality=95)
    return out
