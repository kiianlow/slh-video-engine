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

DEFAULT_DECOR = {
    "divider": False, "dots": False, "frame": False, "corners": False,
    "kicker": False, "cta": False, "bottom": False, "watermark": False,
}


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
                     cta="SAVE THIS", decor=None, out_path=None):
    W, H = 1080, 1920
    pal = cfg["palette"]["thumbnail"]
    bg, ink, box = (mo.hex_to_rgb(pal["bg"]), mo.hex_to_rgb(pal["ink"]),
                    mo.hex_to_rgb(pal["accent"]))
    black = os.path.join(repo_root, cfg["type"]["headline"]["file"])
    light = os.path.join(repo_root, cfg["type"]["body"]["file"])

    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    dec = dict(DEFAULT_DECOR)
    dec.update(decor or {})
    hl = set(highlight or ())

    img = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(img)

    if dec["watermark"]:
        badge = Image.open(os.path.join(repo_root, cfg["brand"]["badge"])).convert("RGBA")
        wm = badge.resize((780, 780), Image.LANCZOS)
        wm.putalpha(wm.getchannel("A").point(lambda v: int(v * 0.05)))
        img.alpha_composite(wm, ((W - 780) // 2, (H - 780) // 2))
        d = ImageDraw.Draw(img)

    if dec["frame"]:
        d.rounded_rectangle([54, 54, W - 54, H - 54], radius=18, outline=box + (255,), width=5)
    if dec["corners"]:
        s, t = 78, 6
        for cx, cy, hx, hy in ((60, 60, 1, 1), (W - 60 - s, 60, -1, 1),
                               (60, H - 60 - s, 1, -1), (W - 60 - s, H - 60 - s, -1, -1)):
            x = cx if hx > 0 else cx + s
            y = cy if hy > 0 else cy + s
            d.rectangle([min(x, x + hx * s), y - (t if hy < 0 else 0),
                         max(x, x + hx * s), y + (t if hy > 0 else 0)], fill=box + (255,))
            d.rectangle([x - (t if hx < 0 else 0), min(y, y + hy * s),
                         x + (t if hx > 0 else 0), max(y, y + hy * s)], fill=box + (255,))

    # --- measure the centred stack -------------------------------------
    blocks = []
    if dec["kicker"]:
        kf = ImageFont.truetype(black, 30)
        blocks.append(("kicker", kicker.upper(), kf, 30 + 18))
    blocks.append(("header", None, None, 74 + 22))
    if dec["divider"]:
        blocks.append(("divider", None, None, 6 + 26))

    lines = [l.strip().upper() for l in title_lines if l.strip()]
    tfonts = []
    for i, ln in enumerate(lines):
        avail = TARGET_W - (HL_PAD if i in hl else 0)
        f = _fit(d0, ln, black, avail)
        tfonts.append(f)
        blocks.append(("tline", ln, f, int(f.size * 0.92) + (15 if i in hl else 11)))

    if dec["cta"]:
        cf = ImageFont.truetype(black, 28)
        blocks.append(("cta", cta.upper(), cf, 28 + 32 + 30))
    if dec["dots"]:
        blocks.append(("dots", None, None, 15 + 34))

    total = sum(b[3] for b in blocks)
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
            badge = badge.resize((74, 74), Image.LANCZOS)
            hf = ImageFont.truetype(black, 32)
            handle = cfg["brand"]["handle"]
            sp = 0.06 * 32
            hw = sum(d.textbbox((0, 0), c, font=hf)[2] + sp for c in handle) - sp
            tot = 74 + 18 + hw
            x = (W - tot) / 2
            img.alpha_composite(badge, (int(x), int(y)))
            d = ImageDraw.Draw(img)
            x += 74 + 18
            for c in handle:
                d.text((x, y + 20), c, font=hf, fill=ink + (255,))
                x += d.textbbox((0, 0), c, font=hf)[2] + sp

        elif kind == "divider":
            d.rounded_rectangle([(W - 120) / 2, y, (W + 120) / 2, y + 6], radius=3, fill=box + (255,))

        elif kind == "tline":
            bb = d.textbbox((0, 0), text, font=f)
            tw = bb[2] - bb[0]
            if idx in hl:
                bx0, bx1 = (W - tw) / 2 - 22, (W + tw) / 2 + 22
                d.rectangle([bx0, y - 2, bx1, y + f.size + 8], fill=box + (255,))
                d.text(((W - tw) / 2 - bb[0], y - bb[1] + 2), text, font=f, fill=(255, 255, 255, 255))
            else:
                d.text(((W - tw) / 2 - bb[0], y - bb[1] + 2), text, font=f, fill=ink + (255,))
            idx += 1

        elif kind == "cta":
            bb = d.textbbox((0, 0), text, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            pw, ph = tw + 80, th + 32
            d.rounded_rectangle([(W - pw) / 2, y, (W + pw) / 2, y + ph],
                                radius=int(ph / 2), fill=ink + (255,))
            d.text(((W - tw) / 2 - bb[0], y + 16 - bb[1]), text, font=f, fill=bg + (255,))

        elif kind == "dots":
            tot = 3 * 15 + 2 * 18
            x = (W - tot) / 2
            for _ in range(3):
                d.ellipse([x, y, x + 15, y + 15], fill=box + (255,))
                x += 15 + 18
        y += adv

    if dec["bottom"]:
        bf = ImageFont.truetype(light, 26)
        name = cfg["brand"]["name"]
        sp = 0.14 * 26
        wtot = sum(d.textbbox((0, 0), c, font=bf)[2] + sp for c in name) - sp
        x = (W - wtot) / 2
        for c in name:
            d.text((x, H - 70 - 26), c, font=bf, fill=ink + (255,))
            x += d.textbbox((0, 0), c, font=bf)[2] + sp

    out = img.convert("RGB")
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        out.save(out_path, quality=95)
    return out
