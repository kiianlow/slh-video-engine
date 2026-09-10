#!/usr/bin/env python3
"""SLH video engine -- one entry point.

    python build.py --topic hidden-costs --preview       # 1 still per scene
    python build.py --topic hidden-costs --frames 3 5    # re-render 2 scenes only
    python build.py --topic hidden-costs --full          # full render + mux
    python build.py --topic hidden-costs --thumbnail
    python build.py --topic hidden-costs --captions

Long renders: wrap in setsid so a bash timeout does not kill the job.
    setsid python build.py --topic x --full > output/x.log 2>&1 &
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "engine"))

from PIL import Image  # noqa: E402

import assemble  # noqa: E402
import icons  # noqa: E402
import audio_align  # noqa: E402
from captions import CaptionTrack, narration_script, write_srt  # noqa: E402
from scenes import render_frame  # noqa: E402
from thumbnail import render_thumbnail  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, "config", name)) as f:
        return json.load(f)


def load_topic(slug):
    path = os.path.join(ROOT, "topics", f"{slug}.json")
    with open(path) as f:
        return json.load(f)


def recap_points(topic, scenes):
    """Headlines of the content scenes, for the closing checklist."""
    custom = topic.get("recap_points")
    if custom:
        return custom
    return [sc.get("sub") or sc.get("headline", "")
            for sc in scenes if sc.get("type", "point") == "point"]


def prepare(topic, cfg):
    """Fill in durations and accents so scenes.json stays minimal to write."""
    d = cfg["duration"]
    rot = cfg["palette"]["accent_rotation"]
    scenes = topic["scenes"]
    for i, sc in enumerate(scenes):
        if "duration" not in sc:
            sc["duration"] = {"hook": d["hook_s"], "cta": d["cta_s"],
                              "recap": d.get("recap_s", 5)}.get(
                sc.get("type", "point"), d["scene_s"])
        if "accent" not in sc:
            sc["accent"] = rot[i % len(rot)]["hex"]
    return scenes


def scene_at(scenes, t):
    clock = 0.0
    for i, sc in enumerate(scenes):
        if t < clock + sc["duration"]:
            return i, sc, t - clock
        clock += sc["duration"]
    return len(scenes) - 1, scenes[-1], scenes[-1]["duration"]


def total_duration(scenes):
    return sum(s["duration"] for s in scenes)


def content_count(scenes):
    return sum(1 for s in scenes if s.get("type", "point") == "point")


def point_index(scenes, i):
    return sum(1 for s in scenes[:i + 1] if s.get("type", "point") == "point")


# ---------------------------------------------------------------- actions ---

def do_preview(args, cfg, mcfg, topic, scenes):
    pts = recap_points(topic, scenes)
    out = os.path.join(ROOT, "output", args.topic, "preview")
    os.makedirs(out, exist_ok=True)
    want = set(args.frames) if args.frames else None
    total = content_count(scenes)
    made = []
    clock = 0.0
    for i, sc in enumerate(scenes):
        if want is None or (i + 1) in want:
            t_local = min(sc["duration"] * 0.55, sc["duration"] - 0.1)
            img = render_frame(ROOT, cfg, mcfg, sc, t_local, clock + t_local,
                               point_index(scenes, i), total, points=pts)
            p = os.path.join(out, f"scene_{i + 1:02d}_{sc.get('type', 'point')}.png")
            img.convert("RGB").save(p)
            made.append(p)
        clock += sc["duration"]
    return made


def do_full(args, cfg, mcfg, topic, scenes):
    fps = args.fps or (cfg["canvas"]["draft_fps"] if args.draft else cfg["canvas"]["fps"])
    work = os.path.join(ROOT, "output", args.topic)
    frames = os.path.join(work, "frames")
    if os.path.exists(frames):
        shutil.rmtree(frames)
    os.makedirs(frames, exist_ok=True)

    align = args.alignment or os.path.join(work, "alignment.json")
    narr = args.narration or os.path.join(work, "narration.mp3")

    if os.path.exists(align):
        track = CaptionTrack.from_elevenlabs(align)
        src = "ElevenLabs word alignment (exact)"
    elif os.path.exists(narr):
        # Time the whole video to the real recording. Scene durations are
        # rewritten in place, so the render comes out the same length as the
        # audio and needs no cutting in CapCut.
        _, adur, warn = audio_align.build_alignment(narr, scenes, align)
        track = CaptionTrack.from_elevenlabs(align)
        src = f"silence-detected from narration.mp3 ({adur:.2f}s)"
        if warn:
            print(f"  ! {warn}", flush=True)
    else:
        track = CaptionTrack.from_scenes(scenes)
        src = "auto-distributed from script (APPROXIMATE - no narration.mp3)"

    pts = recap_points(topic, scenes)
    dur = total_duration(scenes)
    n = int(round(dur * fps))
    total = content_count(scenes)
    print(f"[render] {dur:.1f}s @ {fps}fps = {n} frames | captions: {src}", flush=True)

    for f in range(n):
        t = f / fps
        i, sc, t_local = scene_at(scenes, t)
        img = render_frame(ROOT, cfg, mcfg, sc, t_local, t, point_index(scenes, i),
                           total, points=pts)
        img = track.draw(img, ROOT, cfg, t)
        img.convert("RGB").save(os.path.join(frames, f"f_{f:06d}.png"))
        if f % 300 == 0:
            print(f"  {f}/{n}  {100 * f / n:.0f}%", flush=True)

    silent = os.path.join(work, f"{args.topic}_silent.mp4")
    assemble.encode_frames(frames, silent, cfg, fps=fps)
    print(f"[encode] {silent}", flush=True)

    final = os.path.join(work, f"{args.topic}.mp4")
    assemble.mux_audio(silent, final, cfg, ROOT,
                       narration=narr if os.path.exists(narr) else None,
                       music=not args.no_music)
    if cfg.get("outro", {}).get("enabled"):
        with_outro = os.path.join(work, f"{args.topic}_full.mp4")
        assemble.append_outro(final, with_outro, cfg, ROOT)
        if os.path.exists(with_outro):
            os.replace(with_outro, final)
            print("[outro ] appended", flush=True)

    srt = os.path.join(work, f"{args.topic}.srt")
    write_srt(track, srt)
    print(f"[srt   ] {srt}", flush=True)
    print(f"[final ] {final}", flush=True)
    return final, track


def do_thumbnail(args, cfg, topic):
    tn = topic.get("thumbnail", {})
    out = os.path.join(ROOT, "output", args.topic, f"{args.topic}_thumbnail.png")
    render_thumbnail(
        ROOT, cfg,
        title_lines=tn.get("lines", [topic.get("title", "SG LAUNCH HOMES")]),
        highlight=tn.get("highlight", [1]),
        kicker=tn.get("kicker", "SINGAPORE PROPERTY"),
        cta=tn.get("cta", "SAVE THIS"),
        decor=tn.get("decor"),
        out_path=out,
    )
    return out


def do_captions(args, cfg, topic, scenes):
    work = os.path.join(ROOT, "output", args.topic)
    os.makedirs(work, exist_ok=True)
    p = os.path.join(work, "narration_script.txt")
    with open(p, "w") as f:
        f.write(narration_script(scenes, cfg))
    c = topic.get("captions")
    cp = os.path.join(work, "captions.md")
    tn = topic.get("thumbnail", {})
    with open(cp, "w") as f:
        f.write(f"# {topic.get('title', args.topic)}\n\n")
        lines = tn.get("lines", [])
        if lines:
            hl = set(tn.get("highlight", [1]))
            f.write("## THUMBNAIL TITLE\n\n")
            f.write("Paste into the HTML thumbnail generator, one line per field.\n\n")
            for i, ln in enumerate(lines):
                mark = "   <- highlight this line" if i in hl else ""
                f.write(f"Line {i + 1}: {ln}{mark}\n")
            f.write(f"\nCTA pill: {tn.get('cta', 'SAVE THIS')}\n\n")
        if c:
            for platform in ("instagram", "tiktok", "rednote"):
                if platform in c:
                    f.write(f"## {platform.upper()}\n\n{c[platform].strip()}\n\n")
    return p, cp


# ------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--thumbnail", action="store_true")
    ap.add_argument("--captions", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--frames", nargs="*", type=int, help="scene numbers to re-render")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--draft", action="store_true", help="render at draft_fps")
    ap.add_argument("--narration", help="path to narration mp3")
    ap.add_argument("--alignment", help="path to ElevenLabs alignment json")
    ap.add_argument("--no-music", action="store_true")
    args = ap.parse_args()

    cfg, mcfg = load("brand.json"), load("motion.json")
    topic = load_topic(args.topic)
    scenes = prepare(topic, cfg)

    if not any([args.preview, args.full, args.thumbnail, args.captions, args.all]):
        args.preview = True

    if args.preview or args.all:
        for p in do_preview(args, cfg, mcfg, topic, scenes):
            print("preview:", p)
    if args.captions or args.all:
        a, b = do_captions(args, cfg, topic, scenes)
        print("script:", a)
        if b:
            print("captions:", b)
    if args.thumbnail:
        print("thumbnail:", do_thumbnail(args, cfg, topic))
    if args.full or args.all:
        final, track = do_full(args, cfg, mcfg, topic, scenes)
        if track.approximate:
            print("\n!! caption timing is APPROXIMATE. Drop alignment.json in "
                  f"output/{args.topic}/ and re-run --full for exact timing.")

    subs = icons.substitutions()
    if subs:
        print("\n--- substitutions (flagged, not silent) ---")
        for s in subs:
            print(" *", s)


if __name__ == "__main__":
    main()
