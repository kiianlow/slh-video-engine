"""Easing curves and animation primitives for the SLH render engine.

Every value returned is a 0..1 progress factor unless noted. Never use linear
for entrances -- only for continuous spins and ambient particles.
"""
import math


# ---------------------------------------------------------------- easing ----

def linear(t):
    return t


def ease_out_cubic(t):
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def back_out(t, overshoot=1.70158):
    c3 = overshoot + 1
    return 1 + c3 * pow(t - 1, 3) + overshoot * pow(t - 1, 2)


def spring_out(t, damping=0.42):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 1 - math.exp(-t / damping) * math.cos(t * math.pi * 2.6)


def ease_out_quint(t):
    return 1 - pow(1 - t, 5)


EASING = {
    "linear": linear,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "back_out": back_out,
    "spring_out": spring_out,
    "ease_out_quint": ease_out_quint,
}


def ease(name, t):
    t = max(0.0, min(1.0, t))
    return EASING.get(name, ease_out_cubic)(t)


# --------------------------------------------------------------- helpers ----

def window(now_s, start_s, duration_ms, easing="ease_out_cubic"):
    """Progress 0..1 of an animation starting at start_s. Clamped both ends."""
    dur = duration_ms / 1000.0
    if dur <= 0:
        return 1.0
    return ease(easing, (now_s - start_s) / dur)


def pulse(now_s, beats, duration_ms):
    """Return the progress of the most recent beat, or None if between beats."""
    dur = duration_ms / 1000.0
    best = None
    for b in beats:
        if b <= now_s < b + dur:
            best = (now_s - b) / dur
    return best


def float_bob(now_s, amplitude_px, period_s, phase=0.0):
    return amplitude_px * math.sin((now_s / period_s + phase) * math.tau)


def sway(now_s, degrees, period_s, phase=0.3):
    return degrees * math.sin((now_s / period_s + phase) * math.tau)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgba(hex_color, alpha=1.0):
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, int(round(255 * max(0.0, min(1.0, alpha)))))


def stagger(index, step_ms):
    """Seconds of delay for the nth element in an entrance stagger."""
    return index * step_ms / 1000.0
