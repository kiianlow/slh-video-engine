"""Frame compositor for SLH videos.

One public entry point: render_frame(). Everything is drawn from config, so a
copy change never means a code change.

PIL gotcha, learned the hard way: after ANY alpha_composite the old ImageDraw
handle points at a dead buffer and leaves ghost artifacts. Every composite here
is followed by a fresh ImageDraw. Do not "optimise" that away.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import motion as mo
from icons import get_icon

_FONT_CACHE = {}


def font(repo_root, cfg, role, size):
    key = (role, size)
    if key not in _FONT_CACHE:
        path = os.path.join(repo_root, cfg["type"][role]["file"])
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def text_size(draw, s, f):
    box = draw.textbbox((0, 0), s, font=f)
    return box[2] - box[0], box[3] - box[1]


def fit_text(draw, s, repo_root, cfg, role, max_w, start, floor=34):
    """Shrink until the string fits max_w. Mirrors the thumbnail's binary fit."""
    size = start
    while size > floor:
        f = font(repo_root, cfg, role, size)
        if text_size(draw, s, f)[0] <= max_w:
            return f
        size -= 2
    return font(repo_root, cfg, role, floor)


def wrap(draw, s, f, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textbbox((0, 0), trial, font=f)[2] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------ background ----

def _background(cfg, mcfg, W, H, t_global, accent):
    bg = mo.hex_to_rgb(cfg["palette"]["video"]["bg"])
    img = Image.new("RGBA", (W, H), bg + (255,))

    # slow drifting blobs, barely there
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    per = mcfg["continuous"]["blob_period_s"]
    dr = mcfg["continuous"]["blob_drift_px"]
    a = mo.hex_to_rgb(accent)
    for i, (cx, cy, r) in enumerate([(0.20, 0.22, 0.46), (0.86, 0.60, 0.38), (0.44, 0.90, 0.34)]):
        dx = dr * math.sin((t_global / per + i * 0.33) * math.tau)
        dy = dr * math.cos((t_global / per + i * 0.21) * math.tau)
        x, y, rr = cx * W + dx, cy * H + dy, r * W
        bd.ellipse([x - rr, y - rr, x + rr, y + rr], fill=a + (10,))
    blob = blob.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img, blob)
    return img


def _particles(cfg, mcfg, W, H, t_global, accent):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    n = mcfg["continuous"]["particle_count"]
    spd = mcfg["continuous"]["particle_speed_px_s"]
    op = int(255 * mcfg["continuous"]["particle_opacity"])
    a = mo.hex_to_rgb(accent)
    for i in range(n):
        seed = (i * 97) % 1000 / 1000.0
        x = (0.05 + seed * 0.9) * W + 30 * math.sin((t_global / 7.0 + seed) * math.tau)
        y = H - ((t_global * spd * (0.6 + seed * 0.8) + seed * H * 2.2) % (H * 1.15))
        r = 3 + seed * 6
        d.ellipse([x - r, y - r, x + r, y + r], fill=a + (op,))
    return layer


def _grain(W, H, mcfg, t_global):
    import random
    op = mcfg["continuous"]["grain_opacity"]
    if op <= 0:
        return None
    rnd = random.Random(int(t_global * 12) % 997)
    small = Image.new("L", (W // 8, H // 8))
    small.putdata([rnd.randint(0, 255) for _ in range(small.width * small.height)])
    g = small.resize((W, H), Image.BILINEAR)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.putalpha(g.point(lambda v: int(v * op)))
    return layer


# ----------------------------------------------------------------- chrome ---

def _ov(img, fn):
    """Draw through a transparent layer, then composite.

    PIL's ImageDraw REPLACES pixels on an RGBA image -- it does not blend. Any
    fill with alpha < 255 drawn straight onto the base punches a hole instead of
    tinting. Everything semi-transparent goes through here.
    """
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    return Image.alpha_composite(img, layer)


def _handles(img, repo_root, cfg, W, H):
    hf = font(repo_root, cfg, "body", 30)
    handle = cfg["brand"]["handle"]
    ink = mo.hex_to_rgb(cfg["palette"]["video"]["handle"])
    tw = ImageDraw.Draw(img).textbbox((0, 0), handle, font=hf)[2]

    def paint(d):
        d.text(((W - tw) / 2, cfg["layout"]["handle_top_y"]), handle, font=hf, fill=ink + (210,))
        d.text(((W - tw) / 2, cfg["layout"]["handle_bottom_y"]), handle, font=hf, fill=ink + (210,))
    return _ov(img, paint)


def _pulse_rings(cfg, mcfg, W, H, t_local, cx, cy, accent):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pr = mcfg["pulse_ring"]
    a = mo.hex_to_rgb(accent)
    for b in mcfg["beats"]["pulse_ring"]:
        p = mo.window(t_local, b, pr["duration_ms"], "ease_out_cubic")
        if 0 < p < 1:
            r = mo.lerp(pr["start_radius_px"], pr["end_radius_px"], p)
            op = int(255 * pr["start_opacity"] * (1 - p))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=a + (op,), width=pr["stroke_px"])
    return layer


def _shine(cfg, mcfg, box, t_local):
    """Diagonal light band sweeping across a text box."""
    x0, y0, x1, y1 = box
    w, h = int(x1 - x0), int(y1 - y0)
    if w <= 0 or h <= 0:
        return None, None
    sh = mcfg["shine"]
    prog = None
    for b in mcfg["beats"]["headline_shine"]:
        pr = mo.window(t_local, b, sh["sweep_duration_ms"], "ease_in_out_cubic")
        if 0 < pr < 1:
            prog = pr
    if prog is None:
        return None, None
    band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bw = sh["band_width_px"]
    x = mo.lerp(-bw, w + bw, prog)
    off = math.tan(math.radians(sh["angle_deg"])) * h
    bd.polygon([(x, 0), (x + bw, 0), (x + bw - off, h), (x - off, h)],
               fill=(255, 255, 255, int(255 * sh["band_opacity"])))
    band = band.filter(ImageFilter.GaussianBlur(22))
    return band, (int(x0), int(y0))


# ------------------------------------------------------------ icon badge ----

def _icon_badge(repo_root, cfg, mcfg, scene, t_local, accent, size=300):
    key = scene.get("icon", "ownership")
    icon = get_icon(repo_root, key, accent, size=int(size * 0.62))

    move = scene.get("icon_move", "float_bob")
    im = mcfg["icon_moves"]
    scale, rot = 1.0, 0.0

    bob = mo.float_bob(t_local, mcfg["continuous"]["icon_float_amplitude_px"],
                       mcfg["continuous"]["icon_float_period_s"])
    rot += mo.sway(t_local, mcfg["continuous"]["icon_sway_deg"], 4.1)

    for b in mcfg["beats"]["icon_spring_bounce"]:
        p = mo.window(t_local, b, 620, "spring_out")
        if 0 < p < 1:
            scale *= 1 + 0.14 * (1 - p) * math.sin(p * math.pi * 2)
    for b in mcfg["beats"]["icon_wiggle"]:
        p = mo.window(t_local, b, 520, "ease_out_cubic")
        if 0 < p < 1:
            rot += 9 * (1 - p) * math.sin(p * math.pi * 3)

    if move == "spin360":
        p = mo.window(t_local, 1.0, im["spin360_duration_ms"], "ease_in_out_cubic")
        if 0 < p < 1:
            rot += 360 * p
    elif move in ("coin_flip", "card_flip"):
        p = mo.window(t_local, 1.0, im["flip_duration_ms"], "ease_in_out_cubic")
        if 0 < p < 1:
            sx = abs(math.cos(p * math.pi))
            icon = icon.resize((max(2, int(icon.width * sx)), icon.height), Image.LANCZOS)
    elif move == "drop_squash":
        p = mo.window(t_local, 0.2, im["drop_squash_ms"], "back_out")
        bob += mo.lerp(-260, 0, p)
        if p > 0.85:
            q = (p - 0.85) / 0.15
            scale *= 1 + 0.10 * math.sin(q * math.pi)
    elif move == "pulse_scale":
        scale *= 1 + 0.05 * math.sin(t_local * 2.4)

    entrance = mo.window(t_local, mcfg["entrance_stagger"]["icon_ms"] / 1000.0,
                         mcfg["entrance_stagger"]["each_duration_ms"], "back_out")
    scale *= max(0.05, entrance)

    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    card = mo.hex_to_rgb(cfg["palette"]["video"]["card"])
    ea = max(0.0, min(1.0, entrance))
    bd.ellipse([0, 0, size - 1, size - 1], fill=card + (int(240 * ea),))
    bd.ellipse([0, 0, size - 1, size - 1], outline=mo.hex_to_rgb(accent) + (int(90 * ea),), width=4)

    if scale > 0.02:
        w2 = max(2, int(icon.width * scale))
        h2 = max(2, int(icon.height * scale))
        ic = icon.resize((w2, h2), Image.LANCZOS).rotate(rot, resample=Image.BICUBIC, expand=True)
        badge.alpha_composite(ic, ((size - ic.width) // 2, (size - ic.height) // 2))
        bd = ImageDraw.Draw(badge)  # refresh after composite

    return badge, bob


# ----------------------------------------------------------- scene bodies ---

def _draw_point(img, repo_root, cfg, mcfg, scene, t_local, accent, idx, total):
    W, H = img.size
    M = cfg["layout"]["side_margin"]
    ink = mo.hex_to_rgb(cfg["palette"]["video"]["ink"])
    a = mo.hex_to_rgb(accent)
    st = mcfg["entrance_stagger"]
    Lp = cfg["layout"]
    M = Lp["side_margin"]
    probe = ImageDraw.Draw(img)

    # ghosted scene number behind everything
    Lg = cfg["layout"]
    gf = font(repo_root, cfg, "headline", Lg["ghost_size"])
    num = f"{idx:02d}"
    gw, gh = text_size(probe, num, gf)
    _con = mcfg["continuous"]
    _dy = _con.get("ghost_parallax_px", 6) * math.sin(
        (t_local / _con.get("ghost_period_s", 6.0)) * math.tau)
    _ga = int(255 * Lg["ghost_alpha"])
    img = _ov(img, lambda d: d.text(((W - gw) / 2, Lg["ghost_cy"] - gh / 2 + _dy),
                                    num, font=gf, fill=ink + (_ga,)))

    # kicker
    kp = max(0.0, mo.window(t_local, st["kicker_ms"] / 1000.0, st["each_duration_ms"], "ease_out_quint"))
    if kp > 0:
        kf = font(repo_root, cfg, "headline", 32)
        kicker = scene.get("kicker", f"POINT {idx:02d}")
        kw, _ = text_size(probe, kicker, kf)
        _uw = max(0.0, min(1.0, mo.window(t_local, 0.28, 620, "ease_out_quint")))

        def paint_kicker(d):
            d.text((Lp["kicker_x"], Lp["kicker_y"] + (1 - kp) * 12), kicker,
                   font=kf, fill=a + (int(255 * min(1, kp)),))
            d.rounded_rectangle([Lp["kicker_x"], Lp["kicker_y"] + 46,
                                 Lp["kicker_x"] + kw * _uw, Lp["kicker_y"] + 51],
                                radius=3, fill=a + (200,))
        img = _ov(img, paint_kicker)

    # icon badge
    _isz = Lp["icon_size"]
    badge, bob = _icon_badge(repo_root, cfg, mcfg, scene, t_local, accent, size=_isz)
    _bx = int(Lp["icon_cx"] - _isz / 2)
    by = int(Lp["icon_cy"] - _isz / 2 + bob)
    img.alpha_composite(badge, (_bx, by))
    img = Image.alpha_composite(img, _pulse_rings(cfg, mcfg, W, H, t_local,
                                                  Lp["icon_cx"], by + _isz // 2, accent))
    probe = ImageDraw.Draw(img)

    # headline
    hp = max(0.0, mo.window(t_local, st["headline_ms"] / 1000.0, st["each_duration_ms"], "back_out"))
    head = scene.get("headline", "").upper()
    _mw = W - M - 130
    hf = fit_text(probe, head, repo_root, cfg, "headline", _mw, Lp["headline_size"], 52)
    lines = wrap(probe, head, hf, _mw)
    if len(lines) > 1:
        hf = fit_text(probe, max(lines, key=len), repo_root, cfg, "headline", _mw,
                      Lp["headline_size"], 52)
        lines = wrap(probe, head, hf, _mw)
    y = Lp["headline_y"]
    lh = int(hf.size * cfg["type"]["headline"]["line_height"])
    box = [W, y, 0, y + lh * len(lines)]
    placed = []
    for ln in lines:
        tw, _ = text_size(probe, ln, hf)
        x = M - (1 - hp) * 60
        placed.append((x, y, ln))
        box[0], box[2] = min(box[0], x), max(box[2], x + tw)
        y += lh

    def paint_head(d):
        for x, yy, ln in placed:
            d.text((x, yy), ln, font=hf, fill=ink + (int(255 * min(1, hp)),))
    img = _ov(img, paint_head)

    band, pos = _shine(cfg, mcfg, box, t_local)
    if band is not None:
        img.alpha_composite(band, pos)
    probe = ImageDraw.Draw(img)

    # sub-text card with accent bar wipe
    sub = scene.get("sub", "")
    if sub:
        cp = max(0.0, mo.window(t_local, st["card_ms"] / 1000.0, st["each_duration_ms"], "ease_out_quint"))
        wp = max(0.0, mo.window(t_local, st["accent_bar_wipe_ms"] / 1000.0,
                                st["each_duration_ms"], "ease_out_quint"))
        if cp > 0:
            sf = font(repo_root, cfg, "body", Lp["subtext_size"])
            sy = max(Lp["subtext_y"], y + 24)
            slines = wrap(probe, sub, sf, W - Lp["subtext_x"] - M)
            lhs = int(Lp["subtext_size"] * cfg["type"]["body"]["line_height"])
            wx0, _wy0, wx1, _wy1 = Lp["accent_wipe"]
            bar_h = lhs * len(slines) - 4

            def paint_sub(d):
                d.rounded_rectangle([wx0, sy, wx1, sy + bar_h * min(1.0, wp)],
                                    radius=5, fill=a + (int(255 * min(1, cp)),))
                yy = sy
                for ln in slines:
                    d.text((Lp["subtext_x"], yy + (1 - cp) * 10), ln, font=sf,
                           fill=ink + (int(235 * min(1, cp)),))
                    yy += lhs
            img = _ov(img, paint_sub)

    # segmented progress rail, one block per content scene
    L = cfg["layout"]
    track = mo.hex_to_rgb(cfg["palette"]["video"].get("track", "#CEC2B0"))
    x0, x1 = L["progress_x0"], L["progress_x1"]
    gap, ph, py = L["progress_gap"], L["progress_h"], L["progress_y"]
    seg = (x1 - x0 - gap * (total - 1)) / max(1, total)

    def paint_bar(d):
        for i in range(total):
            sx = x0 + i * (seg + gap)
            d.rounded_rectangle([sx, py, sx + seg, py + ph], radius=ph / 2,
                                fill=(a + (235,)) if i < idx else (track + (140,)))
    return _ov(img, paint_bar)


def _draw_hook(img, repo_root, cfg, mcfg, scene, t_local, accent):
    W, H = img.size
    M = cfg["layout"]["side_margin"]
    ink = mo.hex_to_rgb(cfg["palette"]["video"]["ink"])
    a = mo.hex_to_rgb(accent)

    badge, bob = _icon_badge(repo_root, cfg, mcfg, scene, t_local, accent, size=340)
    by = int(380 + bob)
    img.alpha_composite(badge, ((W - 340) // 2, by))
    img = Image.alpha_composite(img, _pulse_rings(cfg, mcfg, W, H, t_local, W // 2, by + 170, accent))
    probe = ImageDraw.Draw(img)

    head = scene.get("headline", "").upper()
    hf = fit_text(probe, head, repo_root, cfg, "headline", W - 2 * M, 118, 58)
    lines = wrap(probe, head, hf, W - 2 * M)
    if len(lines) > 1:
        hf = fit_text(probe, max(lines, key=len), repo_root, cfg, "headline", W - 2 * M, 118, 58)
        lines = wrap(probe, head, hf, W - 2 * M)
    y = 790
    lh = int(hf.size * cfg["type"]["headline"]["line_height"])
    box = [W, y, 0, y + lh * len(lines)]
    placed = []
    for i, ln in enumerate(lines):
        lp = max(0.0, mo.window(t_local, 0.25 + i * 0.12, 620, "back_out"))
        tw, _ = text_size(probe, ln, hf)
        x = (W - tw) / 2
        placed.append((x, y + (1 - lp) * 40, ln, lp))
        box[0], box[2] = min(box[0], x), max(box[2], x + tw)
        y += lh

    def paint_head(d):
        for x, yy, ln, lp in placed:
            d.text((x, yy), ln, font=hf, fill=ink + (int(255 * min(1, lp)),))
    img = _ov(img, paint_head)

    band, pos = _shine(cfg, mcfg, box, t_local)
    if band is not None:
        img.alpha_composite(band, pos)
    probe = ImageDraw.Draw(img)

    sub = scene.get("sub", "")
    if sub:
        sp = max(0.0, mo.window(t_local, 0.85, 620, "ease_out_cubic"))
        sf = font(repo_root, cfg, "body", 46)
        slines = wrap(probe, sub, sf, W - 2 * M - 60)
        widths = [text_size(probe, ln, sf)[0] for ln in slines]
        sy = y + 30

        def paint_sub(d):
            yy = sy
            for ln, tw in zip(slines, widths):
                d.text(((W - tw) / 2, yy), ln, font=sf, fill=ink + (int(220 * min(1, sp)),))
                yy += int(46 * 1.4)
        img = _ov(img, paint_sub)
        y = sy + len(slines) * int(46 * 1.4)

    uw = max(0.0, mo.window(t_local, 1.2, 700, "ease_out_quint"))
    return _ov(img, lambda d: d.rounded_rectangle(
        [W / 2 - 130 * min(1, uw), y + 34, W / 2 + 130 * min(1, uw), y + 44], radius=5, fill=a + (235,)))


def _draw_cta(img, repo_root, cfg, mcfg, scene, t_local, accent):
    W, H = img.size
    M = cfg["layout"]["side_margin"]
    ink = mo.hex_to_rgb(cfg["palette"]["video"]["ink"])
    bgc = mo.hex_to_rgb(cfg["palette"]["video"]["bg"])

    badge, bob = _icon_badge(repo_root, cfg, mcfg, scene, t_local, accent, size=300)
    img.alpha_composite(badge, ((W - 300) // 2, int(390 + bob)))
    probe = ImageDraw.Draw(img)

    head = scene.get("headline", "").upper()
    hp = max(0.0, mo.window(t_local, 0.2, 620, "back_out"))
    hf = fit_text(probe, head, repo_root, cfg, "headline", W - 2 * M, 104, 54)
    lines = wrap(probe, head, hf, W - 2 * M)
    y = 760
    lh = int(hf.size * 1.1)
    placed = []
    for ln in lines:
        tw, _ = text_size(probe, ln, hf)
        placed.append(((W - tw) / 2, y + (1 - hp) * 34, ln))
        y += lh

    def paint_head(d):
        for x, yy, ln in placed:
            d.text((x, yy), ln, font=hf, fill=ink + (int(255 * min(1, hp)),))
    img = _ov(img, paint_head)
    probe = ImageDraw.Draw(img)

    keyword = scene.get("keyword")
    if keyword:
        pp = max(0.0, min(1.0, mo.window(t_local, 0.9, 700, "back_out")))
        pf = font(repo_root, cfg, "headline", 56)
        label = "COMMENT \u201c" + keyword.upper() + "\u201d"
        tw, th = text_size(probe, label, pf)
        pw, ph = tw + 92, th + 58
        px, py = (W - pw) / 2, y + 40

        def paint_pill(d):
            d.rounded_rectangle([px, py, px + pw * pp, py + ph], radius=int(ph / 2), fill=ink + (245,))
            if pp > 0.6:
                d.text(((W - tw) / 2, py + 22), label, font=pf, fill=bgc + (255,))
        img = _ov(img, paint_pill)
        y = py + ph
        probe = ImageDraw.Draw(img)

    sub = scene.get("sub", "")
    if sub:
        sp = max(0.0, mo.window(t_local, 1.5, 620, "ease_out_cubic"))
        sf = font(repo_root, cfg, "body", 42)
        slines = wrap(probe, sub, sf, W - 2 * M - 60)
        widths = [text_size(probe, ln, sf)[0] for ln in slines]
        sy = y + 34

        def paint_sub(d):
            yy = sy
            for ln, tw in zip(slines, widths):
                d.text(((W - tw) / 2, yy), ln, font=sf, fill=ink + (int(215 * min(1, sp)),))
                yy += int(42 * 1.4)
        img = _ov(img, paint_sub)

    cf = font(repo_root, cfg, "body", 26)
    cea = cfg["brand"]["cea_number"]
    cw, _ = text_size(ImageDraw.Draw(img), cea, cf)
    return _ov(img, lambda d: d.text(((W - cw) / 2, cfg["layout"]["handle_bottom_y"] + 40),
                                     cea, font=cf, fill=ink + (150,)))


# ------------------------------------------------------------------ entry ---

def render_frame(repo_root, cfg, mcfg, scene, t_local, t_global, idx, total):
    W, H = cfg["canvas"]["width"], cfg["canvas"]["height"]
    accent = scene["accent"]

    img = _background(cfg, mcfg, W, H, t_global, accent)

    kind = scene.get("type", "point")
    if kind == "hook":
        img = _draw_hook(img, repo_root, cfg, mcfg, scene, t_local, accent)
    elif kind == "cta":
        img = _draw_cta(img, repo_root, cfg, mcfg, scene, t_local, accent)
    else:
        img = _draw_point(img, repo_root, cfg, mcfg, scene, t_local, accent, idx, total)

    img = Image.alpha_composite(img, _particles(cfg, mcfg, W, H, t_global, accent))
    img = _handles(img, repo_root, cfg, W, H)

    g = _grain(W, H, mcfg, t_global)
    if g is not None:
        img = Image.alpha_composite(img, g)
    return img
