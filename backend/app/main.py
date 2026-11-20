from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, export, ffmpeg_tools as ff, jobs, sources, store
from .models import AnalyzeRequest, Project, ProjectSource, RenderRequest, SourceInfo, SystemStatus

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config.ensure_dirs()

_preamble_cache: dict = {}


@app.get("/api/system/status", response_model=SystemStatus)
def system_status() -> SystemStatus:
    stats = store.stats()
    stats["storage_used_mb"] = round(stats.pop("storage_used_bytes") / (1024 * 1024), 1)
    return SystemStatus(
        version=config.APP_VERSION,
        engine="Local heuristic analysis engine (+FFmpeg)",
        engine_version="cleapyfly-local-heuristic-v1",
        ffmpeg_found=Path(ff.ffmpeg_path()).exists(),
        ffmpeg_path=ff.ffmpeg_path(),
        ytdlp_available=sources.ytdlp_available(),
        ytdlp_enabled=config.YTDLP_ENABLED,
        disclaimer=config.VIRAL_DISCLAIMER,
        **stats,
    )


@app.post("/api/sources/inspect")
def inspect_source(payload: dict) -> dict:
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(422, "Provide a 'url'.")
    kind = sources.classify_url(url)
    if kind == "invalid":
        raise HTTPException(400, "That does not look like a valid http(s) URL.")
    if kind == "youtube":
        try:
            return sources.fetch_youtube_metadata(url)
        except RuntimeError as exc:
            raise HTTPException(502, str(exc))
        except httpx.HTTPError:
            raise HTTPException(502, "Could not reach the video platform. Check the URL and your connection.")
    try:
        head = sources.probe_direct_url(url)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Could not reach this URL: {exc}")
    if head["status"] >= 400:
        raise HTTPException(502, f"The remote server answered HTTP {head['status']}.")
    ctype = head["content_type"]
    ext = Path(url.split("?")[0]).suffix.lower()
    if ctype.startswith("video/") or ext in config.DIRECT_URL_EXTENSIONS:
        return {
            "kind": "direct_url",
            "locator": url,
            "title": Path(url.split("?")[0]).name,
            "thumbnail_url": "",
            "author": "",
            "downloadable": True,
            "notes": [
                f"Content type: {ctype or 'unknown'}",
                f"File size: {head['content_length'] / (1024 * 1024):.1f} MB" if head["content_length"] else "File size unknown",
            ],
        }
    raise HTTPException(400, "This URL is not a direct video file and is not a supported platform page.")


@app.post("/api/projects/upload")
def create_project_from_upload(file: UploadFile = File(...)) -> Project:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_LOCAL_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext or 'unknown'}'. Allowed: {', '.join(sorted(config.ALLOWED_LOCAL_EXTENSIONS))}.",
        )
    pid = store.new_id()
    dest_dir = config.VIDEOS_DIR / pid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"source{ext}"
    size = 0
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    with open(dest, "wb") as fh:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                fh.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Upload exceeds the {config.MAX_UPLOAD_MB} MB limit.")
            fh.write(chunk)
    try:
        info = ff.probe(dest)
    except ff.FFmpegError as exc:
        store.delete(pid)
        raise HTTPException(400, f"This file could not be read as video: {exc}")
    project = _new_project(
        pid=pid,
        name=Path(file.filename or "Local video").stem[:80] or "Local video",
        source=ProjectSource(local_file_name=file.filename),
        info=SourceInfo(
            kind="local_upload",
            locator=file.filename or "local file",
            title=Path(file.filename or "").stem,
            downloadable=True,
            notes=["Uploaded from your device. Processing happens locally on this machine."],
        ),
        media_info=info,
    )
    return project


@app.post("/api/projects/url")
def create_project_from_url(payload: dict) -> Project:
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(422, "Provide a 'url'.")
    kind = sources.classify_url(url)
    if kind == "invalid":
        raise HTTPException(400, "That does not look like a valid http(s) URL.")

    pid = store.new_id()
    project = Project(
        id=pid,
        name="Fetching source…",
        created_at=store.now_iso(),
        updated_at=store.now_iso(),
        source=ProjectSource(youtube_url=url if kind == "youtube" else None, direct_url=url if kind != "youtube" else None),
        source_info=SourceInfo(kind=kind, locator=url),
    )
    store.save(project)

    dest_dir = config.VIDEOS_DIR / pid
    video: Optional[Path] = None
    info: SourceInfo
    try:
        if kind == "youtube":
            try:
                meta = sources.fetch_youtube_metadata(url)
            except RuntimeError as exc:
                raise HTTPException(502, str(exc))
            except httpx.HTTPError:
                raise HTTPException(502, "Could not reach YouTube for metadata. Check the URL and your connection.")
            project.source_info = SourceInfo(
                kind="youtube",
                locator=url,
                title=meta["title"],
                author=meta["author"],
                thumbnail_url=meta["thumbnail_url"],
                downloadable=meta["downloadable"],
                notes=meta["notes"],
            )
            project.name = meta["title"][:80]
            store.save(project)
            try:
                video = sources.try_ytdlp(url, dest_dir)
                info = SourceInfo(kind="youtube_downloaded", locator=url, title=meta["title"], downloadable=True)
                if video and video.name != "source.mp4":
                    video = video.rename(dest_dir / "source.mp4")
            except RuntimeError as exc:
                store.delete(pid)
                raise HTTPException(422, str(exc))
        else:
            try:
                video, meta = sources.download_direct_url(url, dest_dir)
            except RuntimeError as exc:
                store.delete(pid)
                raise HTTPException(422, str(exc))
            except httpx.HTTPError as exc:
                store.delete(pid)
                raise HTTPException(502, f"Download failed: {exc}")
            title = Path(url.split("?")[0]).stem or "Direct video"
            info = SourceInfo(kind="direct_url", locator=url, title=title, downloadable=True, notes=meta["content_type"])
            project.source_info = info
            project.name = title[:80]
    except HTTPException:
        raise
    if video is None:
        store.delete(pid)
        raise HTTPException(422, "The video could not be acquired. Upload a local file instead.")
    try:
        media = ff.probe(video)
    except ff.FFmpegError as exc:
        store.delete(pid)
        raise HTTPException(422, f"The acquired file is not readable video: {exc}")
    _attach_media_info(project, media)
    return store.save(project)


@app.get("/api/projects")
def list_projects() -> dict:
    return {"projects": [p.model_dump(mode="json") for p in store.project_listing()]}


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> Project:
    project = store.get(pid)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project


@app.delete("/api/projects/{pid}")
def delete_project(pid: str) -> dict:
    store.delete(pid)
    return {"deleted": pid}


@app.post("/api/projects/{pid}/analyze")
def analyze(pid: str, req: AnalyzeRequest) -> Project:
    project = store.get(pid)
    if not project:
        raise HTTPException(404, "Project not found.")
    src = jobs.video_path(pid)
    if src is None:
        raise HTTPException(409, "This project has no video file on disk.")
    project.status = "processing"
    project.error = None
    store.save(project)
    jobs.submit(jobs.run_analysis, project, req.target_count, req.duration_preset, req.ratio, req.framing)
    return store.get(pid) or project


@app.post("/api/projects/{pid}/clips/{cid}/render")
def render_clip(pid: str, cid: str, req: RenderRequest) -> Project:
    project = store.get(pid)
    if not project:
        raise HTTPException(404, "Project not found.")
    clip = next((c for c in project.clips if c.id == cid), None)
    if clip is None:
        raise HTTPException(404, "Clip not found.")
    if req.fps not in config.FPS_OPTIONS:
        raise HTTPException(422, f"fps must be one of {config.FPS_OPTIONS}.")
    project.status = "processing"
    store.save(project)
    jobs.submit(jobs.run_render, project, clip, req)
    return project


@app.get("/api/projects/{pid}/clips/{cid}/download")
def download_clip(pid: str, cid: str, quality: Optional[str] = None) -> FileResponse:
    project = store.get(pid)
    if not project:
        raise HTTPException(404, "Project not found.")
    clip = next((c for c in project.clips if c.id == cid), None)
    if clip is None:
        raise HTTPException(404, "Clip not found.")
    renders = clip.renders
    if quality:
        renders = [r for r in renders if r.quality == quality]
    if not renders:
        raise HTTPException(409, "Render this clip first, then download it.")
    newest = renders[-1]
    f = config.CLIPS_DIR / pid / cid / newest.file_name
    if not f.exists():
        raise HTTPException(410, "The rendered file is gone. Re-render the clip.")
    safe_title = "".join(ch if ch.isalnum() or ch in " -_" else "-" for ch in clip.title) or clip.id
    return FileResponse(f, media_type="video/mp4", filename=f"{safe_title}-{newest.quality}p.mp4")


@app.post("/api/projects/{pid}/export/zip")
def export_zip(pid: str, payload: dict):
    project = store.get(pid)
    if not project:
        raise HTTPException(404, "Project not found.")
    ids = (payload or {}).get("clip_ids") or [c.id for c in project.clips if c.renders]
    try:
        zip_path = export.build_zip(project, ids)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "-" for ch in project.name) or pid
    return FileResponse(zip_path, media_type="application/zip", filename=f"{safe}-clips.zip")


@app.get("/media/videos/{pid}/{fname}", response_class=FileResponse)
def media_source_video(pid: str, fname: str) -> FileResponse:
    f = (config.VIDEOS_DIR / pid / fname).resolve()
    _assert_inside(f, config.VIDEOS_DIR)
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp4")


@app.get("/media/thumbs/{pid}/{fname}", response_class=FileResponse)
def media_thumb(pid: str, fname: str) -> FileResponse:
    f = (config.THUMBS_DIR / pid / fname).resolve()
    _assert_inside(f, config.THUMBS_DIR)
    if not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg")


def _assert_inside(f: Path, base: Path) -> None:
    if base.resolve() not in f.parents:
        raise HTTPException(403)


_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")


def _new_project(pid: str, name: str, source: ProjectSource, info: SourceInfo, media_info: Optional[dict]) -> Project:
    project = Project(
        id=pid,
        name=name,
        created_at=store.now_iso(),
        updated_at=store.now_iso(),
        source=source,
        source_info=info,
    )
    if media_info:
        _attach_media_info(project, media_info)
    return store.save(project)


def _attach_media_info(project: Project, media: dict) -> None:
    project.duration = round(media["duration"], 2)
    project.width = media["width"]
    project.height = media["height"]
    project.fps = media["fps"]
    project.video_codec = media["video_codec"]
    project.audio_codec = media["audio_codec"]
    project.status = "ready"
    project.stage = "ready"
    project.progress = 1.0
    try:
        thumb_rel = f"{project.id}/source.jpg"
        ff.thumbnail(
            jobs.video_path(project.id),
            min(1.0, project.duration / 3),
            config.THUMBS_DIR / thumb_rel,
            width=640,
        )
        project.thumbnail = f"/media/thumbs/{thumb_rel}"
    except Exception:
        project.thumbnail = None


@app.on_event("startup")
def startup() -> None:
    config.ensure_dirs()
    for p in store.load_all().values():
        if p.status == "processing":
            p.status = "interrupted" if not p.clips else "ready"
            p.stage = "idle"
            store.save(p)
