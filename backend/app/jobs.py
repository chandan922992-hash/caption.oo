import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from . import analysis, config, export, ffmpeg_tools as ff, reframe, sources, store
from .models import Clip, Project, RenderedVariant, ScoreSet

_executor: Optional[ThreadPoolExecutor] = None
_lock = threading.Lock()


def _pool() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cleapyfly")
        return _executor


def submit(fn: Callable, *args) -> None:
    _pool().submit(fn, *args)


def video_path(pid: str) -> Optional[Path]:
    d = config.VIDEOS_DIR / pid
    if not d.exists():
        return None
    for f in sorted(d.iterdir()):
        if f.name != "incoming.download" and f.suffix.lower() != ".wav":
            return f
    return None


def set_stage(project: Project, stage: str, message: str, progress: float) -> None:
    project.stage = stage
    project.stage_message = message
    project.progress = progress
    store.save(project)


def run_analysis(project: Project, target_count: int, target_duration: Optional[float], ratio: str, framing: str) -> None:
    try:
        project.status = "processing"
        set_stage(project, "analysis", "Inspecting source video", 0.02)
        src = video_path(project.id)
        if src is None:
            raise RuntimeError("The video file for this project is missing.")
        info = ff.probe(src)
        project.duration = round(info["duration"], 2)
        project.width = info["width"]
        project.height = info["height"]
        project.fps = info["fps"]
        project.video_codec = (info["video_codec"] or "").split(" ")[0]
        project.audio_codec = info["audio_codec"]
        store.save(project)

        def on_progress(p: float, message: str) -> None:
            set_stage(project, "analysis", message, max(0.02, min(0.95, p)))

        report = analysis.analyze_video(src, info["duration"], target_count, target_duration, on_progress)

        thumbs_dir = config.THUMBS_DIR / project.id
        ratio_value = config.RATIOS[ratio]
        clips: list[Clip] = []
        for i, c in enumerate(report["clips"], start=1):
            clip = Clip(
                id=store.new_id(),
                title=f"Clip {i}",
                moment_type=c["moment_type"],
                start=c["start"],
                end=c["end"],
                duration=c["duration"],
                scores=ScoreSet(**c["scores"]),
                highlights=c.get("highlights", []),
            )
            try:
                thumb_rel = f"{project.id}/{clip.id}.jpg"
                at = clip.start + min(1.5, clip.duration * 0.25)
                at = min(at, max(0.0, project.duration - 0.2))
                vf = reframe.framing_thumb_crop(src, at, info["width"], info["height"], ratio_value, framing)
                ff.run_ffmpeg(
                    ["-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(src),
                     "-frames:v", "1", "-vf", vf, str(thumbs_dir / f"{clip.id}.jpg")],
                    full_log=False, timeout=240,
                )
                clip.thumbnail = f"/media/thumbs/{thumb_rel}"
            except Exception:
                clip.thumbnail = None
            clips.append(clip)

        project.clips = clips
        project.analysis = {k: v for k, v in report.items() if k != "clips"}
        project.error = None
        project.status = "ready"
        set_stage(project, "ready", f"{len(clips)} clips generated", 1.0)
    except Exception as exc:
        project.status = "error"
        project.error = str(exc)
        set_stage(project, "error", str(exc), 0.0)
    finally:
        store.save(project)


def run_render(project: Project, clip: Clip, req) -> None:
    try:
        project.status = "processing"
        set_stage(project, "render", f"Rendering {clip.title}", 0.01)
        src = video_path(project.id)
        if src is None:
            raise RuntimeError("The video file for this project is missing.")
        out_dir = config.CLIPS_DIR / project.id / clip.id
        out_name = f"{clip.id}-{req.quality}-{req.ratio.replace(':', 'x')}-{req.framing}.mp4"
        out_path = out_dir / out_name

        def on_progress(p: float) -> None:
            set_stage(project, "render", f"Rendering {clip.title}", max(0.01, p))

        manifest = export.render_clip(
            project, clip.model_dump(), src, out_path,
            ratio=req.ratio, framing=req.framing, quality=req.quality,
            fps=req.fps, bitrate=req.bitrate, audio=req.audio,
            on_progress=on_progress,
        )
        variant = RenderedVariant(**manifest)
        clip.renders = [r for r in clip.renders if not (r.quality == variant.quality and r.ratio == variant.ratio and r.framing == variant.framing)]
        clip.renders.append(variant)
        project.error = None
        project.status = "ready"
        set_stage(project, "ready", f"{clip.title} rendered at {variant.height}p", 1.0)
    except Exception as exc:
        project.status = "error"
        project.error = f"Rendering {clip.title} failed: {exc}"
        set_stage(project, "error", project.error, 0.0)
    finally:
        store.save(project)
