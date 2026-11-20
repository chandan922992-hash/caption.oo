import os
from pathlib import Path

APP_NAME = "CLEAPYFLY"
APP_VERSION = "1.0.0"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CLEAPYFLY_DATA_DIR", ROOT_DIR / "data"))
MEDIA_DIR = DATA_DIR / "media"
PROJECTS_DIR = DATA_DIR / "projects"
EXPORTS_DIR = DATA_DIR / "export"
TEMP_DIR = DATA_DIR / "tmp"
VIDEOS_DIR = MEDIA_DIR / "videos"
CLIPS_DIR = MEDIA_DIR / "clips"
THUMBS_DIR = MEDIA_DIR / "thumbs"
WAVS_DIR = MEDIA_DIR / "audio"

STORE_FILE = DATA_DIR / "projects.json"

MAX_UPLOAD_MB = int(os.environ.get("CLEAPYFLY_MAX_UPLOAD_MB", "4096"))
MAX_URL_DOWNLOAD_MB = int(os.environ.get("CLEAPYFLY_MAX_URL_DOWNLOAD_MB", "4096"))

YTDLP_ENABLED = os.environ.get("CLEAPYFLY_YTDLP_ENABLED", "0") == "1"

MIN_CLIPS = 1
MAX_CLIPS = 20

DURATION_PRESETS = [15, 30, 45, 60, 90]
CUSTOM_DURATION_RANGE = (10, 180)

RATIOS = {
    "9:16": 9 / 16,
    "1:1": 1.0,
    "16:9": 16 / 9,
}

QUALITY_PRESETS = {
    "720": {"label": "720p HD", "base_w": 1280, "base_h": 720},
    "1080": {"label": "1080p Full HD", "base_w": 1920, "base_h": 1080},
    "1440": {"label": "1440p QHD", "base_w": 2560, "base_h": 1440},
}

BITRATE_PRESETS = {
    "balanced": 8,
    "high": 12,
    "ultra": 24,
}

AUDIO_BITRATE_PRESETS = {
    "standard": 128,
    "high": 192,
    "studio": 320,
}

FPS_OPTIONS = [24, 30, 60]

ALLOWED_LOCAL_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv", ".ts"}

DIRECT_URL_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts", ".mpg", ".mpeg"}

DIRECT_URL_CONTENT_TYPES = ("video/", "application/octet-stream", "binary/octet-stream")

VIRAL_DISCLAIMER = (
    "Viral potential scores are AI-generated predictions based on local audio/visual heuristics. "
    "They are estimates, not guarantees of real-world engagement."
)


def ensure_dirs() -> None:
    for d in (DATA_DIR, MEDIA_DIR, PROJECTS_DIR, EXPORTS_DIR, TEMP_DIR, VIDEOS_DIR, CLIPS_DIR, THUMBS_DIR, WAVS_DIR):
        d.mkdir(parents=True, exist_ok=True)
