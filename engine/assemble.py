"""ffmpeg stage: frames to MP4, then narration + background music mux.

Background music sits at gain 0.10 -- volume 10 out of 100, matching what Kiian
sets in CapCut. That value is locked in config/brand.json, not here.
"""
import json
import os
import subprocess


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{p.stderr[-3000:]}")
    return p


def duration_of(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    return float(p.stdout.strip())


def encode_frames(frames_dir, out_path, cfg, fps=None):
    c = cfg["canvas"]
    fps = fps or c["fps"]
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "f_%06d.png"),
        "-c:v", c["codec"], "-pix_fmt", c["pix_fmt"], "-crf", str(c["crf"]),
        "-preset", "medium",
    ]
    if c.get("faststart"):
        cmd += ["-movflags", "+faststart"]
    cmd += [out_path]
    _run(cmd)
    return out_path


def mux_audio(video, out_path, cfg, repo_root, narration=None, music=True):
    """Lay narration and background music under the silent render."""
    a = cfg["audio"]
    vdur = duration_of(video)
    inputs = ["-i", video]
    filters, tags = [], []
    idx = 1

    if narration and os.path.exists(narration):
        inputs += ["-i", narration]
        filters.append(f"[{idx}:a]volume={a['narration_volume']},"
                       f"apad=whole_dur={vdur}[vo]")
        tags.append("[vo]")
        idx += 1

    if music:
        mpath = os.path.join(repo_root, a["bg_music"])
        if os.path.exists(mpath):
            inputs += ["-stream_loop", "-1", "-i", mpath]
            filters.append(
                f"[{idx}:a]volume={a['bg_music_volume']},"
                f"atrim=0:{vdur},"
                f"afade=t=in:st=0:d={a['fade_in_s']},"
                f"afade=t=out:st={max(0, vdur - a['fade_out_s'])}:d={a['fade_out_s']}[bg]"
            )
            tags.append("[bg]")
            idx += 1

    if not tags:
        _run(["ffmpeg", "-y", "-i", video, "-c", "copy", out_path])
        return out_path

    if len(tags) == 1:
        filters.append(f"{tags[0]}anull[aout]")
    else:
        filters.append(f"{''.join(tags)}amix=inputs={len(tags)}:"
                       f"duration=first:dropout_transition=0:normalize=0[aout]")

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", out_path,
    ]
    _run(cmd)
    return out_path


def probe(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration,size", "-of", "json", path],
        capture_output=True, text=True)
    return json.loads(p.stdout)
