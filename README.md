# CLEAPYFLY

**AI-powered automatic viral video clipping** — paste an authorized long-form video, let the local AI find the strongest moments, and export vertical, social-ready MP4 clips. Inspired by Opus Clip, built local-first: no paid AI APIs, no mandatory cloud services, no key setup.

## What it does

1. **Source** — upload a local video (the reliable path), a direct video file URL, or paste a YouTube link (metadata is fetched through the official oEmbed API — CLEAPYFLY never bypasses platform protections or DRM, and tells you honestly when a file can't be acquired; optional gated `yt-dlp` acquisition can be enabled by deployments where the operator owns the rights).
2. **Analyze** — a fully local heuristic engine scans speech energy, sentence silences, scene changes, and loudness dynamics to find engaging moments: hooks, emotional peaks, explanations, stories.
3. **Score** — every candidate clip gets eight scores (0–100): hook, emotional, information value, context completeness, standalone quality, visual engagement, audio quality, and an overall viral potential. These are **predictions, not guarantees**.
4. **Clip** — up to 20 clips per video (AI Auto, 5, 10, 15, 20), with AI Auto duration or fixed 15/30/45/60/90 sec, silence-aware boundaries, complete sentences, and no duplicate or padding moments.
5. **Reframe** — 9:16 (default), 1:1, 16:9 with **AI Smart Tracking** (motion-based subject tracking with smooth, slew-limited crop movement), Center Crop, or Original Framing.
6. **Export** — H.264/AAC MP4 at 720p / 1080p / 1440p presets, 24/30/60 fps, bitrate and audio-quality options, estimated size, individual downloads, batch render, and ZIP export. Output never exceeds the true source resolution — no fake upscales.

## Stack

| Layer    | Tech |
|----------|------|
| Frontend | React 18 + Vite, custom premium dark design system (charcoal / violet), fully responsive |
| Backend  | Python FastAPI, background job engine, JSON project store |
| Media    | FFmpeg (static via `imageio-ffmpeg` on Linux x86_64, or system ffmpeg) |
| AI       | Local heuristic engine v1 (`cleapyfly-local-heuristic-v1`) — audio loudness statistics, silence/sentence detection, scene-change detection, motion-based tracking. No downloads, no API keys, works offline. |

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8734
```

Requires ffmpeg on the PATH (or set `CLEAPYFLY_FFMPEG=/path/to/ffmpeg`). On Linux x86_64 the pinned `imageio-ffmpeg` wheel installs a static ffmpeg automatically as a fallback.

### Frontend (development)

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api and /media to :8734
```

### Production

```bash
cd frontend && npm run build   # outputs frontend/dist
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8734
```

The FastAPI app automatically serves the built SPA from `frontend/dist` when it exists.

## Configuration (environment)

| Variable | Default | Meaning |
|----------|---------|---------|
| `CLEAPYFLY_FFMPEG` | auto-detect | Path to the ffmpeg binary |
| `CLEAPYFLY_DATA_DIR` | `backend/data` | Where media, projects, and exports live |
| `CLEAPYFLY_MAX_UPLOAD_MB` | `4096` | Upload size limit |
| `CLEAPYFLY_MAX_URL_DOWNLOAD_MB` | `4096` | Direct-URL download limit |
| `CLEAPYFLY_YTDLP_ENABLED` | `0` | Opt-in gated acquisition of videos the operator is authorized to download (requires `yt-dlp` installed; never bypasses DRM or platform restrictions and fails honestly) |

## API overview

Interactive docs: `http://localhost:8734/api/docs`

- `POST /api/projects/upload` — create a project from a local video
- `POST /api/projects/url` — create from a direct video URL (or a YouTube link; refuses non-downloadable sources with a clear explanation)
- `POST /api/sources/inspect` — inspect a URL's metadata before committing
- `POST /api/projects/{id}/analyze` — run AI analysis (count, duration, ratio, framing)
- `POST /api/projects/{id}/clips/{cid}/render` — render a clip (ratio, framing, quality, fps, bitrate, audio)
- `GET  /api/projects/{id}/clips/{cid}/download` — download a rendered MP4
- `POST /api/projects/{id}/export/zip` — batch ZIP export
- `GET  /api/system/status` — engine status, storage usage, statistics

## Compliance & honesty notes

- The YouTube Data API does not provide video file downloads; CLEAPYFLY reads only public oEmbed metadata for YouTube links and never fakes a download or analysis. Local upload and direct video URLs are the reliable acquisition paths.
- Viral scores are heuristic predictions based on audio/visual signals — clearly labeled as such in the UI.
- Rendered "1440p" output only exists when the source genuinely contains at least that resolution; otherwise the render is capped at source size and the UI states it.

## Repository layout

```
backend/
  app/
    main.py          FastAPI routes & static SPA serving
    analysis.py      heuristic clip analysis & 8-dimension scoring
    reframe.py       smart/center/original crop + subject tracking
    export.py        H.264/AAC render pipeline + ZIP bundling
    sources.py       uploads, direct URLs, YouTube metadata, gated yt-dlp
    ffmpeg_tools.py  probe, loudness, silence, scenes, motion decoding
    jobs.py          background analysis/render jobs
    store.py         project persistence
  requirements.txt
frontend/
  src/
    components/      sidebar, dashboard, icons
    pages/           project workspace (clips, scores, export)
    styles.css       dark charcoal/violet design system
  vite.config.js     dev proxy to the backend
```
