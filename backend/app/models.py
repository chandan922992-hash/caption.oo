from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Ratio = Literal["9:16", "1:1", "16:9"]
FramingMode = Literal["smart", "center", "original"]
Quality = Literal["720", "1080", "1440"]
Bitrate = Literal["balanced", "high", "ultra"]
AudioBitrate = Literal["standard", "high", "studio"]


class AnalyzeRequest(BaseModel):
    target_count: int = Field(default=10, ge=1, le=20)
    duration_preset: Optional[int] = Field(default=None, ge=10, le=180)
    ratio: Ratio = "9:16"
    framing: FramingMode = "smart"


class RenderRequest(BaseModel):
    ratio: Ratio = "9:16"
    framing: FramingMode = "smart"
    quality: Quality = "1080"
    fps: int = Field(default=30)
    bitrate: Bitrate = "high"
    audio: AudioBitrate = "high"


class SourceInfo(BaseModel):
    kind: str
    locator: str
    title: str = ""
    thumbnail_url: str = ""
    author: str = ""
    downloadable: bool = False
    notes: List[str] = Field(default_factory=list)


class ProjectSource(BaseModel):
    youtube_url: Optional[str] = None
    direct_url: Optional[str] = None
    local_file_name: Optional[str] = None


class ScoreSet(BaseModel):
    hook: float = Field(ge=0, le=100)
    emotion: float = Field(ge=0, le=100)
    information: float = Field(ge=0, le=100)
    context_completeness: float = Field(ge=0, le=100)
    standalone: float = Field(ge=0, le=100)
    visual: float = Field(ge=0, le=100)
    audio: float = Field(ge=0, le=100)
    viral_potential: float = Field(ge=0, le=100)


class RenderedVariant(BaseModel):
    quality: str
    ratio: str
    framing: str
    fps: int
    width: int
    height: int
    size_bytes: int
    file_name: str
    upscaled_to_source_limit: bool = False


class Clip(BaseModel):
    id: str
    title: str
    moment_type: str
    start: float
    end: float
    duration: float
    scores: ScoreSet
    highlights: List[str] = Field(default_factory=list)
    thumbnail: Optional[str] = None
    renders: List[RenderedVariant] = Field(default_factory=list)
    selected: bool = True


class Project(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    source: ProjectSource
    source_info: SourceInfo
    duration: float = 0.0
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    thumbnail: Optional[str] = None
    status: str = "ready"
    stage: str = "idle"
    progress: float = 0.0
    stage_message: str = ""
    error: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    clips: List[Clip] = Field(default_factory=list)
    archived: bool = False


class SystemStatus(BaseModel):
    app: str = "CLEAPYFLY"
    version: str
    engine: str
    engine_version: str
    ffmpeg_found: bool
    ffmpeg_path: Optional[str] = None
    ytdlp_available: bool
    ytdlp_enabled: bool
    storage_used_mb: float
    project_count: int
    clip_count: int
    rendered_count: int
    disclaimer: str
