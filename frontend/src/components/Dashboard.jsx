import { useEffect, useRef, useState } from "react";
import * as api from "../api.js";
import { IconClipboard, IconPlay, IconSpark, IconUpload, IconChart, IconFilm, IconScissors } from "./icons.jsx";

const fmtDuration = (s) => {
  if (!s) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
};

const fmtDate = (iso) => {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
};

export default function Dashboard({ status, onCreated, onOpenProject, toast }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState(null);
  const [projects, setProjects] = useState([]);
  const fileRef = useRef(null);

  const refreshProjects = () => api.listProjects().then(setProjects).catch(() => {});

  useEffect(() => {
    refreshProjects();
  }, []);

  const proceedToProject = (project) => {
    refreshProjects();
    onOpenProject(project);
  };

  const handleInspect = async () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setError("");
    setInfo(null);
    setBusy("inspect");
    try {
      const meta = await api.inspectSource(trimmed);
      setInfo({ ...meta, url: trimmed });
      const acq = meta.acquisition || {};
      if (meta.kind === "youtube" && !meta.downloadable && !acq.can_process) {
        setError(acq.reason || "This video cannot be acquired through an authorized source on this deployment.");
      } else if (!meta.downloadable) {
        setError(
          "This video page can be read for metadata, but its video file cannot be downloaded through official APIs. " +
          "For a guaranteed workflow, upload the video file directly below."
        );
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const handleCreateFromUrl = async () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setError("");
    setBusy("create");
    try {
      const project = await api.createProjectFromUrl(trimmed);
      toast(`Loaded: ${project.name}`, "success");
      setUrl("");
      setInfo(null);
      proceedToProject(project);
    } catch (e) {
      setError(e.message);
      try {
        const meta = await api.inspectSource(trimmed);
        setInfo({ ...meta, url: trimmed });
      } catch { /* ignore */ }
    } finally {
      setBusy("");
    }
  };

  const handleUpload = async (file) => {
    if (!file) return;
    setError("");
    setInfo(null);
    setBusy("upload");
    try {
      const project = await api.uploadProject(file);
      toast(`Uploaded: ${project.name}`, "success");
      proceedToProject(project);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setUrl(text.trim());
    } catch {
      toast("Clipboard access was blocked by the browser. Paste manually with Ctrl+V.", "error");
    }
  };

  const stats = status || {};
  const isYouTube = url.trim().length > 0 && /youtu\.?be/i.test(url.trim());

  return (
    <>
      <section className="hero">
        <div className="eyebrow"><IconSpark size={14} /> Local-first AI · No paid APIs required</div>
        <h2>Turn Long Videos Into <em>Viral-Ready Clips</em></h2>
        <p>Let AI discover your best moments and automatically create short-form videos.</p>

        <div className="source-card">
          <div className="source-row">
            <input
              className="input"
              placeholder="Paste an authorized YouTube link or a direct video file URL…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleInspect()}
              disabled={busy !== ""}
            />
            <button className="btn" onClick={paste} disabled={busy !== ""}>
              <IconClipboard size={15} /> Paste
            </button>
            <button className="btn primary" onClick={handleInspect} disabled={busy !== "" || !url.trim()}>
              {busy === "inspect" ? <><span className="spinner" /> Checking…</> : <><IconPlay size={15} /> Inspect Video</>}
            </button>
          </div>

          {info && (info.can_process || info.downloadable) && (
            <div className="source-options">
              <span className="hint">
                {info.kind === "youtube"
                  ? "Acquisition authorized on this deployment — you confirm you hold the rights to this video."
                  : "Ready for full local processing."}
              </span>
              <button className="btn primary" onClick={handleCreateFromUrl} disabled={busy !== ""}>
                {busy === "create" ? <><span className="spinner" /> Acquiring video…</> : <><IconScissors size={15} /> Generate Clips</>}
              </button>
            </div>
          )}

          <div className="source-options">
            <span className="dash" />
            <span className="hint">or use a file from this device</span>
            <input ref={fileRef} className="hidden-input" type="file"
              accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/*"
              onChange={(e) => handleUpload(e.target.files?.[0])} />
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={busy !== ""}>
              {busy === "upload" ? <><span className="spinner" /> Uploading…</> : <><IconUpload size={15} /> Local Video</>}
            </button>
            <span className="dash" />
          </div>

          {(busy === "create") && (
            <div className="alert info">Acquiring the video file… This can take a while for large downloads.</div>
          )}
          {info && (
            <div className="alert info">
              <strong>{info.title || "Source detected"}</strong>
              {info.author ? ` — ${info.author}` : ""}
              <div style={{ marginTop: 4 }}>
                Source type: {info.kind}
                {info.kind === "youtube" && " · metadata via official oEmbed API"}
                {info.content_type && ` · ${info.content_type}`}
              </div>
              <div style={{ marginTop: 4, fontWeight: 600 }}>
                {info.can_process || info.downloadable
                  ? "✓ Video can be acquired through an authorized source — proceed below."
                  : info.acquisition
                    ? "✕ Video file acquisition is not authorized on this deployment."
                    : "✕ Not directly downloadable — use Local Video below."}
              </div>
              {info.notes?.length > 0 && (
                <ul style={{ margin: "6px 0 0 16px", opacity: 0.85 }}>
                  {info.notes.slice(0, 3).map((n, i) => <li key={i} style={{ marginBottom: 3 }}>{n}</li>)}
                </ul>
              )}
            </div>
          )}
          {error && <div className="alert error">{error}</div>}
          {isYouTube && !error && !info && (
            <div className="alert info">
              YouTube pages are analyzed for metadata only — CLEAPYFLY never bypasses platform protections.
              You can load your own authorized video via direct URL or start from a local file.
            </div>
          )}
        </div>
      </section>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label"><IconFilm size={14} /> Projects</div>
          <div className="value">{stats.project_count ?? "—"}</div>
          <div className="sub">on this workspace</div>
        </div>
        <div className="stat-card">
          <div className="label"><IconScissors2 size={14} /> Clips generated</div>
          <div className="value">{stats.clip_count ?? "—"}</div>
          <div className="sub">up to 20 per video</div>
        </div>
        <div className="stat-card">
          <div className="label"><IconDownload2 size={14} /> Rendered exports</div>
          <div className="value">{stats.rendered_count ?? "—"}</div>
          <div className="sub">H.264 / AAC MP4</div>
        </div>
        <div className="stat-card">
          <div className="label"><IconChart size={14} /> Storage used</div>
          <div className="value">
            {stats.storage_used_mb == null ? "—" : (stats.storage_used_mb > 1024 ? `${(stats.storage_used_mb / 1024).toFixed(1)} GB` : `${Math.round(stats.storage_used_mb)} MB`)}
          </div>
          <div className="sub">media + projects</div>
        </div>
      </div>

      <div className="topbar" style={{ marginTop: 10 }}>
        <h1>Recent projects</h1>
        <div className="actions">
          <button className="btn ghost small" onClick={refreshProjects}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3"/><path d="M20 4v4h-4M4 20v-4h4"/></svg>
            Refresh
          </button>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="empty">
          No projects yet. Paste a link above or upload a local video, and the AI will find your best moments.
        </div>
      ) : (
        <div className="project-grid">
          {projects.map((p) => (
            <button key={p.id} className="project-card" onClick={() => proceedToProject(p)}>
              <div className="project-thumb">
                {p.thumbnail ? <img src={p.thumbnail} alt="" /> : <span className="no-thumb">No preview</span>}
                <span className={`status-pill ${p.status}`}>{p.status}</span>
              </div>
              <div className="project-meta">
                <div className="name">{p.name || p.id}</div>
                <div className="meta-row">
                  <span>{fmtDuration(p.duration)}</span>
                  {p.width && p.height && <span>{p.width}×{p.height}</span>}
                  <span>{p.clips.length} clips</span>
                  <span style={{ marginLeft: "auto" }}>{fmtDate(p.created_at)}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="disclaimer">
        Viral scores are local AI predictions, not guarantees. CLEAPYFLY only processes videos you are authorized to use
        and never bypasses DRM or platform access restrictions.
      </div>
    </>
  );
}

function IconScissors2({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><path d="M8.1 7.6 20 19M8.1 16.4 20 5" />
    </svg>
  );
}

function IconDownload2({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M12 4v12m0 0 4-4m-4 4-4-4" /><path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" />
    </svg>
  );
}
