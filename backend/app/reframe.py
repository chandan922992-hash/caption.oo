from pathlib import Path
from typing import List, Optional, Tuple

from . import ffmpeg_tools as ff


def crop_geometry(src_w: int, src_h: int, ratio_value: float) -> Tuple[int, int, int, int]:
    crop_h = src_h
    crop_w = round(crop_h * ratio_value)
    if crop_w > src_w:
        crop_w = src_w
        crop_h = round(crop_w / ratio_value)
    crop_w = min(src_w, max(8, crop_w - (crop_w % 2)))
    crop_h = min(src_h, max(8, crop_h - (crop_h % 2)))
    return crop_w, crop_h, (src_w - crop_w) // 2, (src_h - crop_h) // 2


def _smooth(values: List[float], window: int) -> List[float]:
    if len(values) < 3 or window < 2:
        return list(values)
    prefix = [0.0]
    for v in values:
        prefix.append(prefix[-1] + v)
    half = window // 2
    out = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append((prefix[hi] - prefix[lo]) / (hi - lo))
    return out


def _breakpoints(points: List[Tuple[float, float]], start_px: float, scale: float, max_px: float, max_speed: float) -> List[Tuple[float, float]]:
    cur = start_px
    last_recorded = start_px
    out: List[Tuple[float, float]] = [(0.0, round(start_px, 1))]
    for t, v in points:
        target = v * scale
        limit = max_speed / 10.0
        diff = max(-limit, min(limit, target - cur))
        cur = max(0.0, min(max_px, cur + diff))
        if abs(cur - last_recorded) >= max(3.0, max_px * 0.01) and (t - out[-1][0]) >= 0.3:
            out.append((round(t, 2), round(cur, 1)))
            last_recorded = cur
    return out


def crop_filter(
    video_path,
    src_w: int,
    src_h: int,
    ratio_value: float,
    duration: float,
    framing: str,
    start: float = 0.0,
    cmds_dir: Optional[Path] = None,
) -> str:
    crop_w, crop_h, cx, cy = crop_geometry(src_w, src_h, ratio_value)
    if framing == "original":
        return "crop=iw:ih:0:0"
    max_x = src_w - crop_w
    max_y = src_h - crop_h
    if framing == "center" or (max_x <= 2 and max_y <= 2):
        return f"crop={crop_w}:{crop_h}:{cx}:{cy}"

    points = ff.motion_path(video_path, fps=10, start=start, duration=duration)
    if not points:
        return f"crop={crop_w}:{crop_h}:{cx}:{cy}"

    track_x = max_x > 2
    track_y = max_y > 2
    x_breaks = _breakpoints([(t, x) for t, x, _ in points], cx, float(src_w), float(max_x), 0.12 * src_w) if track_x else None
    y_breaks = None
    if track_y:
        y_breaks = _breakpoints(
            [(t, y) for t, _, y in points], cy, float(src_h), float(max_y), 0.12 * src_h
        ) if max_y > 2 else None
    if not track_x and y_breaks and len(y_breaks) < 2:
        return f"crop={crop_w}:{crop_h}:{cx}:{cy}"
    if track_x and x_breaks is not None and len(x_breaks) < 2 and not (y_breaks and len(y_breaks) >= 2):
        return f"crop={crop_w}:{crop_h}:{cx}:{cy}"

    cmds_file = None
    if cmds_dir is None:
        cmds_dir = Path(video_path).parent
    cmds_dir = Path(cmds_dir)
    cmds_dir.mkdir(parents=True, exist_ok=True)
    cmds_file = cmds_dir / f"track-{abs(hash((round(start, 2), round(duration, 2), crop_w, crop_h)))}.cmds"

    times = sorted({t for t, _ in (x_breaks or [])} | {t for t, _ in (y_breaks or [])})
    def x_at(t: float) -> float:
        if not x_breaks:
            return cx
        val = x_breaks[-1][1]
        for bt, bv in x_breaks:
            if bt <= t:
                val = bv
            else:
                break
        return val
    def y_at(t: float) -> float:
        if not y_breaks:
            return cy
        val = y_breaks[-1][1]
        for bt, bv in y_breaks:
            if bt <= t:
                val = bv
            else:
                break
        return val

    lines = []
    for t in times:
        if track_x:
            lines.append(f"{t:.2f} crop x {x_at(t):.0f};")
        if track_y:
            lines.append(f"{t:.2f} crop y {y_at(t):.0f};")
    cmds_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"sendcmd=f='{cmds_file}',crop={crop_w}:{crop_h}:x={cx}:y={cy}"


def framing_thumb_crop(
    video_path,
    at: float,
    src_w: int,
    src_h: int,
    ratio_value: float,
    framing: str,
) -> str:
    crop_w, crop_h, cx, cy = crop_geometry(src_w, src_h, ratio_value)
    if framing == "original":
        return "scale=iw:ih"
    if framing == "center" or (src_w - crop_w <= 2 and src_h - crop_h <= 2):
        return f"crop={crop_w}:{crop_h}:{cx}:{cy}"
    probe_h = max(16, int(160 * src_h / max(1, src_w)))
    centroid = 0.5
    try:
        points = ff.motion_window(video_path, at, around=2.0, w=160, h=probe_h)
        if points:
            mid = points[len(points) // 2][1]
            centroid = mid
    except Exception:
        pass
    px = max(0, min(src_w - crop_w, int(centroid * src_w - crop_w / 2)))
    return f"crop={crop_w}:{crop_h}:{px}:{cy}"
