import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .models import Clip, Project

_LOCK = threading.Lock()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_all() -> Dict[str, Project]:
    with _LOCK:
        if not config.STORE_FILE.exists():
            return {}
        try:
            raw = json.loads(config.STORE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    projects: Dict[str, Project] = {}
    for pid, data in raw.items():
        try:
            projects[pid] = Project.model_validate(data)
        except Exception:
            continue
    return projects


def save(project: Project) -> Project:
    project.updated_at = now_iso()
    with _LOCK:
        try:
            raw = json.loads(config.STORE_FILE.read_text(encoding="utf-8")) if config.STORE_FILE.exists() else {}
        except (json.JSONDecodeError, OSError):
            raw = {}
        raw[project.id] = project.model_dump(mode="json")
        tmp = config.STORE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(config.STORE_FILE)
    return project


def get(pid: str) -> Optional[Project]:
    return load_all().get(pid)


def delete(pid: str) -> None:
    with _LOCK:
        if not config.STORE_FILE.exists():
            return
        try:
            raw = json.loads(config.STORE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        raw.pop(pid, None)
        tmp = config.STORE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(config.STORE_FILE)
    for base in (config.VIDEOS_DIR / pid, config.CLIPS_DIR / pid, config.THUMBS_DIR / pid, config.WAVS_DIR / pid):
        if base.exists():
            for f in base.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass


def project_listing() -> List[Project]:
    items = [p for p in load_all().values() if not p.archived]
    items.sort(key=lambda p: p.created_at, reverse=True)
    return items


def stats() -> dict:
    projects = load_all()
    clip_count = sum(len(p.clips) for p in projects.values())
    rendered = sum(len(c.renders) for p in projects.values() for c in p.clips)
    used = 0
    for f in config.DATA_DIR.rglob("*") if config.DATA_DIR.exists() else []:
        try:
            if f.is_file():
                used += f.stat().st_size
        except OSError:
            continue
    return {
        "project_count": len(projects),
        "clip_count": clip_count,
        "rendered_count": rendered,
        "storage_used_bytes": used,
    }
