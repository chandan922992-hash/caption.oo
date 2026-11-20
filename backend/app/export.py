import math
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from . import config, ffmpeg_tools as ff, reframe


def target_dimensions(
    src_w: int, src_h: int, ratio_value: float, quality: str
) -> Tuple[int, int, int, int, bool]:
    preset = config.QUALITY_PRESETS[quality]
    crop_w, crop_h, _, _ = reframe.crop_geometry(src_w, src_h, ratio_value)
    scale_factor = min(preset["base_w"] / crop_w, preset["base_h"] / crop_h)
    out_w = int(round(crop_w * scale_factor))
    out_h = int(round(crop_h * scale_factor))
    out_w -= out_w % 2
    out_h -= out_h % 2
    capped = scale_factor > 1.0
    if capped:
        max_w = max(2, crop_w - crop_w % 2)
        max_h = max(2, crop_h - crop_h % 2)
        if out_w > max_w or out_h > max_h:
            shrink = min(max_w / out_w, max_h / out_h, 1.0)
            out_w = max(2, int(out_w * shrink) - int(out_w * shrink) % 2)
            out_h = max(2, int(out_h * shrink) - int(out_h * shrink) % 2)
    return crop_w, crop_h, out_w, out_h, capped


def estimate_size_bytes(duration: float, bitrate: str, audio: str, capped_w: int, capped_h: int) -> int:
    rate_kbps = config.BITRATE_PRESETS[bitrate] * 1000
    audio_kbps = config.AUDIO_BITRATE_PRESETS[audio]
    pixels = capped_w * capped_h
    ref = 1920 * 1080
    adjusted = rate_kbps * min(1.5, max(0.4, pixels / ref))
    return int((adjusted + audio_kbps) * 1000 * duration / 8)


def render_clip(
    project,
    clip,
    src_path: Path,
    out_path: Path,
    ratio: str,
    framing: str,
    quality: str,
    fps: int,
    bitrate: str,
    audio: str,
    on_progress=None,
) -> dict:
    probe = ff.probe(src_path)
    src_w = probe["width"] or 1280
    src_h = probe["height"] or 720
    ratio_value = config.RATIOS[ratio]
    crop_w, crop_h, out_w, out_h, capped = target_dimensions(src_w, src_h, ratio_value, quality)

    duration = clip["end"] - clip["start"]
    out_dir = out_path.parent
    tracking_cmds = out_dir / "tracking.cmds"
    if tracking_cmds.exists():
        tracking_cmds.unlink()
    crop_expr = reframe.crop_filter(
        src_path, src_w, src_h, ratio_value, duration, framing,
        start=clip["start"], cmds_dir=out_dir,
    )

    audio_stream_args = ["-map", "0:a:0?", "-c:a", "aac", "-b:a", f"{config.AUDIO_BITRATE_PRESETS[audio]}k", "-ar", "48000"]
    if not probe["has_audio"]:
        audio_stream_args = ["-an"]

    vf_parts = [
        crop_expr,
        f"scale={out_w}:{out_h}:flags=bicubic",
    ]
    if fps and abs(fps - (probe["fps"] or fps)) > 0.01:
        vf_parts.insert(0, f"fps={fps}")

    args = [
        "-y",
        "-ss", f"{clip['start']:.3f}",
        "-i", str(src_path),
        "-t", f"{duration:.3f}",
        "-vf", ",".join(vf_parts),
        "-map", "0:v:0",
        *audio_stream_args,
        "-c:v", "libx264",
        "-preset", "faster",
        "-b:v", f"{config.BITRATE_PRESETS[bitrate]}k",
        "-maxrate", f"{int(config.BITRATE_PRESETS[bitrate] * 1.45)}k",
        "-bufsize", f"{config.BITRATE_PRESETS[bitrate] * 2}k",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-r", str(fps),
        "-movflags", "+faststart",
        str(out_path),
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ff.run_ffmpeg(args, on_progress=on_progress, total_duration=duration, full_log=False)

    size = out_path.stat().st_size
    rendered = {
        "quality": quality,
        "ratio": ratio,
        "framing": framing,
        "fps": fps,
        "width": out_w,
        "height": out_h,
        "size_bytes": size,
        "file_name": out_path.name,
        "upscaled_to_source_limit": capped,
    }
    return rendered


def build_zip(project, clip_ids: List[str]) -> Path:
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = config.EXPORTS_DIR / f"{project.id}-{len(clip_ids)}-clips.zip"
    if zip_path.exists() and zip_path.stat().st_size > 0:
        return zip_path
    tmp = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
        added = 0
        for cid in clip_ids:
            clip = next((c for c in project.clips if c.id == cid), None)
            if not clip or not clip.renders:
                continue
            newest = clip.renders[-1]
            f = config.CLIPS_DIR / project.id / cid / newest.file_name
            if f.exists():
                zf.write(f, arcname=f"{clip.title or cid}-{newest.quality}p.mp4")
                added += 1
    if added == 0:
        tmp.unlink(missing_ok=True)
        raise ValueError("No rendered clips available for ZIP export. Render clips first.")
    tmp.replace(zip_path)
    return zip_path
