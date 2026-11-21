import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

import httpx

from . import config

YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com")

YTDLP_NOTES = "By using URL acquisition you confirm you are the rightful owner of, or otherwise hold the rights to, this content and that downloading it does not violate the platform's terms of service."


def classify_url(url: str) -> str:
    try:
        parts = urlparse(url)
    except ValueError:
        return "invalid"
    if not parts.scheme or parts.scheme not in ("http", "https"):
        return "invalid"
    host = (parts.hostname or "").lower()
    if not host or "." not in host and host != "localhost":
        return "invalid"
    if host in YOUTUBE_HOSTS:
        return "youtube"
    return "direct"


def youtube_id(url: str) -> Optional[str]:
    m = re.search(r"(?:v=|/shorts/|/embed/|youtu\.be/|/live/)([\w-]{6,})", url)
    if m:
        return m.group(1)
    qs = parse_qs(urlparse(url).query)
    if "v" in qs and len(qs["v"][0]) >= 6:
        return qs["v"][0]
    return None


def youtube_acquisition_status(url: str, client: Optional[httpx.Client] = None) -> dict:
    installed = ytdlp_available()
    gated_open = config.YTDLP_ENABLED
    can_process = gated_open and installed
    if gated_open and not installed:
        reason = (
            "Gated URL acquisition is enabled but yt-dlp is not installed on this machine. "
            "Install it (pip install yt-dlp) or upload the video file directly."
        )
    elif not gated_open:
        reason = (
            "This deployment has authorized URL acquisition disabled. CLEAPYFLY will not download from "
            "YouTube unless the operator enables CLEAPYFLY_YTDLP_ENABLED=1 and installs yt-dlp — and you "
            "hold the download rights to the video. Upload the file directly or use a direct video URL."
        )
    else:
        reason = ""
    return {
        "can_process": can_process,
        "reason": reason,
        "ytdlp_installed": installed,
        "authorization_required": True,
    }


def fetch_youtube_metadata(url: str, client: Optional[httpx.Client] = None) -> dict:
    vid = youtube_id(url)
    own = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    data: dict = {}
    try:
        r = client.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; CLEAPYFLY/1.0)"},
        )
        if r.status_code == 200:
            data = r.json()
        elif r.status_code == 401:
            raise RuntimeError(
                "This video's owner has disabled embedding and metadata access, so CLEAPYFLY cannot read it. "
                "If this is your video, upload the file directly instead."
            )
        elif r.status_code == 404:
            raise RuntimeError("This YouTube video does not exist, is private, or the link is malformed.")
        else:
            raise RuntimeError(f"YouTube metadata service answered with HTTP {r.status_code}.")
    finally:
        if own:
            client.close()
    title = data.get("title") or "YouTube video"
    info = {
        "kind": "youtube",
        "locator": url,
        "title": title,
        "author": data.get("author_name", ""),
        "thumbnail_url": data.get("thumbnail_url", "") or (
            f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""
        ),
        "video_id": vid,
        "downloadable": False,
        "notes": [
            "YouTube does not allow third-party apps to download video files through its official API.",
            "For guaranteed results, upload the video file directly or share an authorized direct video URL.",
            YTDLP_NOTES,
        ],
    }
    if config.YTDLP_ENABLED:
        info["notes"].insert(
            2,
            "Optional yt-dlp acquisition is enabled in this deployment, gated on you having the download rights to this video.",
        )
    return info


def probe_direct_url(url: str, client: Optional[httpx.Client] = None) -> dict:
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        r = client.head(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CLEAPYFLY/1.0)"})
        ctype = (r.headers.get("content-type") or "").lower()
        length = r.headers.get("content-length")
        accepts_ranges = r.headers.get("accept-ranges", "")
        return {
            "status": r.status_code,
            "content_type": ctype,
            "content_length": int(length) if length and length.isdigit() else None,
            "accepts_ranges": accepts_ranges == "bytes",
        }
    finally:
        if own:
            client.close()


def download_direct_url(url: str, dest_dir: Path, on_progress=None) -> Tuple[Path, dict]:
    head = probe_direct_url(url)
    ctype = head["content_type"]
    reported = head["content_length"] or 0
    if head["status"] >= 400:
        raise RuntimeError(f"The direct video URL returned HTTP {head['status']} and was not downloaded.")
    if head["content_length"] and head["content_length"] > config.MAX_URL_DOWNLOAD_MB * 1024 * 1024:
        raise RuntimeError(
            f"This file is too large ({head['content_length'] // (1024 * 1024)} MB). "
            f"The URL download limit is {config.MAX_URL_DOWNLOAD_MB} MB."
        )
    path_hint = urlparse(url).path
    ext = Path(path_hint).suffix.lower()
    if ext not in config.DIRECT_URL_EXTENSIONS and not ctype.startswith("video/"):
        raise RuntimeError(
            "This URL does not point at a recognized video file (no video content type, no .mp4/.mov/.webm/... suffix). "
            "YouTube and other streaming platform pages cannot be downloaded this way; upload a local file instead."
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    partial = dest_dir / "incoming.download"
    final = dest_dir / f"source{ext or '.mp4'}"
    size = 0
    limit = config.MAX_URL_DOWNLOAD_MB * 1024 * 1024
    with httpx.Client(timeout=httpx.Timeout(30, read=120), follow_redirects=True) as client:
        with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0 (compatible; CLEAPYFLY/1.0)"}) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"Download failed: the server answered HTTP {r.status_code}.")
            if ctype and ctype not in config.DIRECT_URL_CONTENT_TYPES and not ctype.startswith("video/"):
                raise RuntimeError(f"Unsupported content type '{ctype}'. Only direct video files are supported.")
            with open(partial, "wb") as fh:
                total = r.headers.get("content-length")
                total = int(total) if total and total.isdigit() else 0
                for chunk in r.iter_bytes(chunk_size=1024 * 512):
                    size += len(chunk)
                    if size > limit:
                        fh.close()
                        partial.unlink(missing_ok=True)
                        raise RuntimeError("Download exceeded the configured size limit and was aborted.")
                    fh.write(chunk)
                    if on_progress and total:
                        on_progress(min(0.999, size / total))
    partial.replace(final)
    meta = {"kind": "direct_url", "locator": url, "content_type": ctype or "video/unknown"}
    return final, meta


def ytdlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def try_ytdlp(url: str, dest_dir: Path, on_progress=None) -> Path:
    if not config.YTDLP_ENABLED:
        raise RuntimeError(
            "CLEAPYFLY will not download from YouTube without your explicit authorization. "
            "Upload the video file directly, or share a direct video URL. "
            "Deployments can enable gated yt-dlp acquisition with CLEAPYFLY_YTDLP_ENABLED=1 plus yt-dlp installed."
        )
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp is not installed on this machine, so URL acquisition is unavailable. Upload the file directly.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "source.%(ext)s"
    cmd = [
        ytdlp, "--no-playlist", "--no-warnings", "--restrict-filenames",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", str(out), url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    last = ""
    for line in proc.stdout:
        last = line.strip()
        if on_progress and "%" in last:
            try:
                pct = float(last.split("%")[0].split()[-1]) / 100.0
                on_progress(min(0.99, pct))
            except ValueError:
                pass
    code = proc.wait()
    files = sorted(dest_dir.glob("source.*"))
    if code != 0 or not files:
        raise RuntimeError(
            "URL acquisition failed. This is expected for restricted, DRM-protected, or non-downloadable videos: "
            + (last or "yt-dlp exited with error")
        )
    return files[0]


def fetch_direct(url: str, dest_dir: Path, on_progress=None) -> Tuple[Path, dict]:
    return download_direct_url(url, dest_dir, on_progress)
