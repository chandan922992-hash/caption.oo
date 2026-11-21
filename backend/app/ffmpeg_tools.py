import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional


class FFmpegError(RuntimeError):
    pass


def _candidate_paths() -> list[str]:
    paths: list[str] = []
    env = os.environ.get("CLEAPYFLY_FFMPEG")
    if env:
        paths.append(env)
    paths.append(shutil.which("ffmpeg") or "")
    try:
        import imageio_ffmpeg

        paths.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    return [p for p in paths if p]


_FFMPEG_CACHE: Optional[str] = None


def ffmpeg_path() -> str:
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE is None:
        candidates = _candidate_paths()
        if not candidates:
            raise FFmpegError(
                "ffmpeg was not found on this machine. Install ffmpeg (https://ffmpeg.org) "
                "or set CLEAPYFLY_FFMPEG to the binary path."
            )
        _FFMPEG_CACHE = candidates[0]
    return _FFMPEG_CACHE


def run_ffmpeg(
    args: list[str],
    timeout: float = 3600,
    on_progress: Optional[Callable[[float], None]] = None,
    total_duration: Optional[float] = None,
    full_log: bool = True,
) -> str:
    cmd = [ffmpeg_path(), "-hide_banner", "-nostdin", *args]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stderr is not None
    lines: list[str] = []
    consumed = 0

    def _drain() -> None:
        nonlocal consumed
        for line in proc.stderr:
            if full_log or consumed < 500:
                lines.append(line)
            consumed += 1
            if on_progress and total_duration and line.startswith("frame="):
                m = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                if m:
                    seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                    on_progress(min(0.999, max(0.0, seconds / total_duration)))

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
        raise FFmpegError(f"ffmpeg timed out after {timeout:.0f}s")
    reader.join(timeout=60)
    if proc.returncode != 0 and full_log is False:
        lines.extend("... [output truncated] ...")
    if proc.returncode != 0:
        raise FFmpegError("ffmpeg failed:\n" + "".join(lines[-40:]))
    return "".join(lines)


_TIME_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
_VIDEO_RES_RE = re.compile(r"(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"([\d.]+)\s*fps")
_RATE_RE = re.compile(r"(\d+)\s*Hz")


def probe(path: Path) -> dict:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise FFmpegError(f"Media file is missing or empty: {path}")
    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    info = proc.stderr
    duration = None
    m = _TIME_RE.search(info)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    streams = re.findall(r"Stream #0:(\d+)\(?\w*\)?[^\n]*?:\s*(Video|Audio): ([^\n]+)", info)
    result: dict = {
        "duration": duration or 0.0,
        "width": None,
        "height": None,
        "fps": None,
        "video_codec": None,
        "audio_codec": None,
        "audio_rate": None,
        "bitrate_kbps": None,
        "has_audio": False,
        "has_video": False,
    }
    tb = re.search(r"bitrate:\s*(\d+)\s*kb/s", info)
    if tb:
        result["bitrate_kbps"] = int(tb.group(1))
    for _, kind, payload in streams:
        if kind == "Video":
            rm = _VIDEO_RES_RE.search(payload)
            if rm and result["width"] is None:
                result["width"] = int(rm.group(1))
                result["height"] = int(rm.group(2))
            fm = _FPS_RE.search(payload)
            if fm and result["fps"] is None:
                try:
                    result["fps"] = round(float(fm.group(1)), 3)
                except ValueError:
                    pass
            if result["video_codec"] is None:
                result["video_codec"] = payload.split(",")[0].strip().lower()
            result["has_video"] = True
        elif kind == "Audio":
            tm = _RATE_RE.search(payload)
            if tm and result["audio_rate"] is None:
                result["audio_rate"] = int(tm.group(1))
            if result["audio_codec"] is None:
                result["audio_codec"] = payload.split(",")[0].strip().lower()
            result["has_audio"] = True
    if not result["has_video"]:
        raise FFmpegError("No video stream found in the provided file.")
    if not result["duration"] and result["bitrate_kbps"]:
        approx = path.stat().st_size * 8 / 1000 / result["bitrate_kbps"]
        result["duration"] = approx
    return result


def extract_audio(video: Path, wav_out: Path) -> Path:
    wav_out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_out)],
        full_log=False,
    )
    return wav_out


def energy_timeline(wav: Path, step_ms: float = 10.0) -> list[dict]:
    samples_per_window = max(16, int(16000 * step_ms / 1000))
    out = run_ffmpeg(
        [
            "-i", str(wav),
            "-af", f"asetnsamples=n={samples_per_window}:p=0,astats=metadata=1:reset=1,"
            "ametadata=print:key=lavfi.astats.Overall.RMS_level",
            "-f", "null", "-",
        ],
        full_log=True,
        timeout=2400,
    )
    timeline: list[dict] = []
    for line in out.splitlines():
        line = line.strip()
        idx = line.find("lavfi.astats.Overall.RMS_level=")
        if idx != -1:
            try:
                db = float(line[idx + len("lavfi.astats.Overall.RMS_level="):])
            except ValueError:
                db = -90.0
            t = round(len(timeline) * step_ms / 1000, 3)
            timeline.append({"t": t, "db": db})
    return timeline


def silence_boundaries(wav: Path, noise_db: float = -32.0, min_silence: float = 0.35) -> list[tuple[float, Optional[float]]]:
    try:
        out = run_ffmpeg(
            ["-i", str(wav), "-af", f"silencedetect=n={noise_db}dB:d={min_silence}", "-f", "null", "-"],
            full_log=True,
        )
    except FFmpegError:
        return []
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", out)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", out)]
    pairs: list[tuple[float, Optional[float]]] = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        pairs.append((s, e))
    return pairs


def scene_times(video: Path, threshold: float = 0.32) -> list[float]:
    try:
        out = run_ffmpeg(
            [
                "-an", "-i", str(video),
                "-vf", f"scale=192:-2,select='gt(scene\\,{threshold})',metadata=print",
                "-f", "null", "-",
            ],
            full_log=True,
            timeout=2400,
        )
    except FFmpegError:
        return []
    times: list[float] = []
    for line in out.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m and "lavfi.scene_score" not in line:
            t = float(m.group(1))
            if not times or t - times[-1] > 0.25:
                times.append(t)
    return times


def motion_window(
    video: Path, at: float, around: float = 2.0, w: int = 160, h: int = 90
) -> list[tuple[float, float]]:
    cols = w * h
    cmd = [
        ffmpeg_path(), "-hide_banner", "-nostdin",
        "-ss", f"{max(0.0, at):.3f}", "-t", f"{around:.3f}",
        "-i", str(video),
        "-vf", f"fps=10,scale={w}:{h},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None
    result: list[tuple[float, float]] = []
    prev: Optional[bytes] = None
    t = 0.0
    try:
        while True:
            frame = proc.stdout.read(cols)
            if not frame or len(frame) < cols:
                break
            if prev is not None:
                sx = swe = 0.0
                for i in range(0, cols):
                    d = abs(frame[i] - prev[i])
                    if d > 16:
                        weight = d / 255.0
                        _, x = divmod(i, w)
                        sx += weight * (x / (w - 1))
                        swe += weight
                if swe > 0.5:
                    result.append((round(t, 3), round(sx / swe, 4)))
            prev = frame
            t += 0.1
    finally:
        proc.stdout.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    return result


def thumbnail(video: Path, at_seconds: float, out: Path, width: int = 480) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-y", "-ss", f"{max(0.0, at_seconds):.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", f"scale={width}:-2", str(out),
        ],
        full_log=False,
        timeout=180,
    )
    return out


def motion_path(
    video: Path, fps: int = 10, start: float = 0.0, duration: Optional[float] = None
) -> list[tuple[float, float, float]]:
    w, h = 64, 36
    cols = w * h
    ffmpeg = ffmpeg_path()
    cmd = [
        ffmpeg, "-hide_banner", "-nostdin",
        *(["-ss", f"{start:.3f}"] if start > 0 else []),
        *(["-t", f"{duration:.3f}"] if duration else []),
        "-i", str(video),
        "-vf", f"fps={fps},scale={w}:{h},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdout is not None
    path: list[tuple[float, float, float]] = []
    prev: Optional[bytes] = None
    step = 1.0 / fps
    t = 0.0
    try:
        while True:
            frame = proc.stdout.read(cols)
            if not frame or len(frame) < cols:
                break
            if prev is not None:
                sx = sy = sw = 0.0
                for i in range(0, cols):
                    d = abs(frame[i] - prev[i])
                    if d > 14:
                        weight = d / 255.0
                        y, x = divmod(i, w)
                        sx += weight * (x / (w - 1))
                        sy += weight * (y / (h - 1))
                        sw += weight
                if sw > 0.5:
                    path.append((round(t, 3), round(sx / sw, 4), round(sy / sw, 4)))
            prev = frame
            t += step
    finally:
        proc.stdout.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    return path
