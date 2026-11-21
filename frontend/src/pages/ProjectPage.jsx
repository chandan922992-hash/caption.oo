import { useEffect, useRef, useState } from "react";
import * as api from "../api.js";
import { IconBack, IconDownload, IconRefresh, IconScissors, IconSpark, IconTrash } from "../components/icons.jsx";

const DURATIONS = [
  { value: "", label: "AI Auto" },
  { value: 20, label: "20 sec" },
  { value: 30, label: "30 sec" },
  { value: 50, label: "50 sec" },
  { value: 60, label: "60 sec" },
  { value: "custom", label: "Custom duration" },
];

export default function ProjectPage({ projectId, onBack, toast, onDeleted }) {
  const [project, setProject] = useState(null);
  const [error, setError] = useState("");
  const [count, setCount] = useState(10);
  const [duration, setDuration] = useState("");
  const [ratio, setRatio] = useState("9:16");
  const [framing, setFraming] = useState("smart");
  const [quality, setQuality] = useState("1080");
  const [fps, setFps] = useState(30);
  const [bitrate, setBitrate] = useState("high");
  const [audio, setAudio] = useState("high");
  const [rendering, setRendering] = useState({});
  const [customDuration, setCustomDuration] = useState("45");
  const pollRef = useRef(null);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const p = await api.getProject(projectId);
        if (stop) return;
        setProject(p);
        setError(p.status === "error" ? p.error : "");
        if (p.status !== "processing") return;
        pollRef.current = setTimeout(tick, 2000);
      } catch (e) {
        if (!stop) setError(e.message);
      }
    };
    tick();
    return () => { stop = true; if (pollRef.current) clearTimeout(pollRef.current); };
  }, [projectId]);

  const refresh = () => api.getProject(projectId).then(setProject).catch(() => {});

  const runAnalysis = async () => {
    setError("");
    let preset = duration && duration !== "custom" ? Number(duration) : null;
    if (duration === "custom") {
      const n = Math.round(Number(customDuration));
      if (!Number.isFinite(n) || n < 10 || n > 180) {
        toast("Custom duration must be between 10 and 180 seconds.", "error");
        return;
      }
      preset = n;
    }
    try {
      await api.analyzeProject(projectId, {
        target_count: count === 0 ? 12 : count,
        duration_preset: preset,
        ratio,
        framing,
      });
      const tick = async () => {
        const p = await api.getProject(projectId);
        setProject(p);
        if (p.status === "processing") {
          setTimeout(tick, 2000);
        } else if (p.status === "error") {
          setError(p.error);
        } else {
          toast(`${p.clips.length} clips ready`, "success");
        }
      };
      tick();
    } catch (e) {
      setError(e.message);
    }
  };

  const renderOne = async (clip, overrides = {}) => {
    setRendering((r) => ({ ...r, [clip.id]: true }));
    try {
      await api.renderClip(projectId, clip.id, {
        ratio, framing: overrides.framing ?? framing, quality,
        fps: Number(fps), bitrate, audio,
      });
      const tick = async () => {
        const p = await api.getProject(projectId);
        setProject(p);
        const target = p.clips.find((c) => c.id === clip.id);
        const hasThis = target?.renders?.some((r) => r.quality === quality && r.ratio === ratio && r.framing === (overrides.framing ?? framing));
        if (p.status === "error" && !(target && target.renders.some((r) => r.quality === quality))) {
          if (p.stage_message.includes(clip.title)) { setError(p.error); return; }
        }
        if (hasThis) {
          toast(`${clip.title} rendered`, "success");
        } else {
          setTimeout(tick, 2000);
        }
      };
      tick();
    } catch (e) {
      setError(e.message);
    } finally {
      setTimeout(() => setRendering((r) => ({ ...r, [clip.id]: false })), 1500);
    }
  };

  const renderAll = async () => {
    const clips = project?.clips || [];
    for (const c of clips) {
      // eslint-disable-next-line no-await-in-loop
      await renderOne(c);
    }
    toast("Batch render finished", "success");
  };

  const doDelete = async () => {
    try {
      await api.deleteProject(projectId);
      toast("Project deleted", "success");
      onDeleted();
    } catch (e) {
      setError(e.message);
    }
  };

  if (!project) {
    return (
      <div className="page">
        <button className="btn ghost small" onClick={onBack}><IconBack size={14} /> Back to dashboard</button>
        <div className="empty" style={{ marginTop: 20 }}>Loading project…</div>
      </div>
    );
  }

  const processing = project.status === "processing";
  const clips = project.clips || [];
  const renderedCount = clips.filter((c) => c.renders?.length).length;

  return (
    <div className="page">
      <button className="btn ghost small" onClick={onBack}><IconBack size={14} /> Back to dashboard</button>

      <div className="detail-head" style={{ marginTop: 16 }}>
        <div className="detail-thumb">
          {project.thumbnail
            ? <img src={project.thumbnail} alt="" />
            : <div style={{ aspectRatio: "16/9", display: "grid", placeItems: "center", color: "var(--text-faint)", fontSize: 12 }}>No preview</div>}
        </div>
        <div className="detail-info">
          <h2>{project.name}</h2>
          <div className="badge-row">
            <span className="badge violet">{project.source_info?.kind === "youtube" ? "YouTube source" : project.source_info?.kind || "source"}</span>
            {project.duration ? <span className="badge">{Math.floor(project.duration / 60)}m {Math.round(project.duration % 60)}s</span> : null}
            {project.width && project.height && <span className="badge">{project.width}×{project.height}</span>}
            {project.fps && <span className="badge">{Math.round(project.fps)} fps</span>}
            {project.video_codec && <span className="badge">{project.video_codec}</span>}
            {project.audio_codec && <span className="badge">{project.audio_codec}</span>}
          </div>
          {project.source_info?.notes?.length > 0 && (
            <div className="source-notes">
              <ul>
                {project.source_info.notes.slice(0, 4).map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
          {project.source_info?.thumbnail_url && (
            <div style={{ marginTop: 12 }}>
              <img src={project.source_info.thumbnail_url} alt="" style={{ maxHeight: 60, borderRadius: 8, border: "1px solid var(--border)" }}
                onError={(e) => { e.currentTarget.style.display = "none"; }} />
            </div>
          )}
        </div>
      </div>

      {project.status === "error" && (
        <div className="error-band">{project.error || error}</div>
      )}
      {error && project.status !== "error" && <div className="error-band">{error}</div>}

      {processing && (
        <div className="processing-band">
          <div className="row"><span className="spinner" /> {project.stage_message || "Working…"} · AI analysis runs entirely on this machine.</div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${Math.round((project.progress || 0) * 100)}%` }} /></div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <h3><IconSpark size={16} /> AI clip generation</h3>
        <div className="controls-row">
          <div className="field">
            <label>Number of clips</label>
            <select className="input select" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              <option value={0}>AI Auto</option>
              {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n} clips</option>)}
            </select>
          </div>
          <div className="field">
            <label>Clip duration</label>
            <select className="input select" value={duration} onChange={(e) => setDuration(e.target.value)}>
              {DURATIONS.map((d) => <option key={d.label} value={d.value}>{d.label}</option>)}
            </select>
          </div>
          {duration === "custom" && (
            <div className="field">
              <label>Duration (10–180 s)</label>
              <input
                className="input"
                type="number"
                min={10}
                max={180}
                value={customDuration}
                onChange={(e) => setCustomDuration(e.target.value)}
                style={{ width: 110 }}
              />
            </div>
          )}
          <div className="field">
            <label>Aspect ratio</label>
            <select className="input select" value={ratio} onChange={(e) => setRatio(e.target.value)}>
              <option value="9:16">9:16 — Shorts / Reels</option>
              <option value="1:1">1:1 — Square</option>
              <option value="16:9">16:9 — Landscape</option>
            </select>
          </div>
          <div className="field">
            <label>Framing</label>
            <select className="input select" value={framing} onChange={(e) => setFraming(e.target.value)}>
              <option value="smart">AI Smart Tracking</option>
              <option value="center">Center Crop</option>
              <option value="original">Original Framing</option>
            </select>
          </div>
          <button className="btn primary" onClick={runAnalysis} disabled={processing}>
            {processing ? <><span className="spinner" /> Analyzing…</> : <><IconScissors size={15} /> {clips.length ? "Re-analyze" : "Generate clips"}</>}
          </button>
        </div>
        <div className="hint">
          The AI never pads the list with weak moments — expect fewer clips than requested when the source has fewer strong
          candidates. Viral scores are local predictions, not guarantees.
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3><IconRefresh size={15} /> Export settings</h3>
        <div className="controls-row">
          <div className="field">
            <label>Resolution</label>
            <select className="input select" value={quality} onChange={(e) => setQuality(e.target.value)}>
              <option value="720">720p HD</option>
              <option value="1080">1080p Full HD</option>
              <option value="1440">1440p QHD (capped by source)</option>
            </select>
          </div>
          <div className="field">
            <label>Frame rate</label>
            <select className="input select" value={fps} onChange={(e) => setFps(e.target.value)}>
              {[24, 30, 60].map((f) => <option key={f} value={f}>{f} fps</option>)}
            </select>
          </div>
          <div className="field">
            <label>Video bitrate</label>
            <select className="input select" value={bitrate} onChange={(e) => setBitrate(e.target.value)}>
              <option value="balanced">Balanced (8 Mbps)</option>
              <option value="high">High (12 Mbps)</option>
              <option value="ultra">Ultra (24 Mbps)</option>
            </select>
          </div>
          <div className="field">
            <label>Audio</label>
            <select className="input select" value={audio} onChange={(e) => setAudio(e.target.value)}>
              <option value="standard">Standard (128 kbps)</option>
              <option value="high">High (192 kbps)</option>
              <option value="studio">Studio (320 kbps)</option>
            </select>
          </div>
          <button className="btn" onClick={renderAll} disabled={processing || !clips.length}>
            <IconRefresh size={15} /> Batch render all
          </button>
          <button className="btn primary" disabled={!renderedCount}
            onClick={() => {
              api.exportZip(projectId, clips.filter((c) => c.renders?.length).map((c) => c.id))
                .then(() => toast("ZIP downloaded", "success"))
                .catch((e) => toast(e.message, "error"));
            }}>
            <IconDownload size={15} /> Download ZIP ({renderedCount})
          </button>
        </div>
        <div className="hint">
          Output resolution never exceeds the source resolution — if the source is smaller than the chosen preset,
          CLEAPYFLY exports at the source's true size instead of upscaling, and marks the file accordingly.
        </div>
      </div>

      <div className="topbar">
        <h1>Generated clips ({clips.length})</h1>
        <div className="actions">
          <button className="btn ghost small" onClick={refresh}><IconRefresh size={13} /> Refresh</button>
          <button className="btn danger small" onClick={doDelete}><IconTrash size={13} /> Delete project</button>
        </div>
      </div>

      {clips.length === 0 && !processing && (
        <div className="empty">
          No clips yet. Run <strong>Generate clips</strong> above — the AI will scan speech, scenes and silence to pick
          the strongest moments of this video.
        </div>
      )}

      <div className="clip-grid">
        {clips.map((c) => (
          <ClipCard key={c.id} clip={c} project={project} rendering={!!rendering[c.id]}
            onRender={() => renderOne(c)}
            onToast={toast} />
        ))}
      </div>

      <div className="disclaimer">
        {project.analysis?.engine
          ? `Analyzed with ${project.analysis.engine} · ${project.analysis.speech_regions?.length ?? 0} speech regions · ${project.analysis.scene_change_count ?? 0} scene changes`
          : "Local AI analysis"} — viral scores are predictions, not guarantees.
      </div>
    </div>
  );
}

function ClipCard({ clip, project, rendering, onRender, onToast }) {
  const s = clip.scores;
  const viral = s.viral_potential;
  const viralClass = viral >= 70 ? "score-good" : viral >= 45 ? "score-mid" : "score-low";
  const newest = clip.renders?.[clip.renders.length - 1];

  return (
    <div className="clip-card">
      <div className="clip-thumb">
        {clip.thumbnail
          ? <img src={clip.thumbnail} alt={clip.title} loading="lazy" />
          : <span style={{ color: "var(--text-faint)", fontSize: 12 }}>No preview</span>}
        <span className="range">{fmtTime(clip.start)} → {fmtTime(clip.end)}</span>
      </div>
      <div className="clip-body">
        <div className="head">
          <span className="title">{clip.title}</span>
          <span className="type">{clip.moment_type}</span>
        </div>
        <div className="viral-row">
          <span className={`viral-score ${viralClass}`}>{viral.toFixed(0)}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 2 }}>Viral potential · {clip.duration.toFixed(1)}s</div>
            <div className="score-row">
              <span>Hook</span>
              <span className="bar"><i style={{ width: `${s.hook}%` }} /></span>
              <span className="num">{s.hook.toFixed(0)}</span>
            </div>
            <div className="score-row">
              <span>Emotion</span>
              <span className="bar"><i style={{ width: `${s.emotion}%` }} /></span>
              <span className="num">{s.emotion.toFixed(0)}</span>
            </div>
          </div>
        </div>
        <div className="score-rows">
          <ScoreRow label="Information value" value={s.information} />
          <ScoreRow label="Context complete" value={s.context_completeness} />
          <ScoreRow label="Standalone" value={s.standalone} />
          <ScoreRow label="Visual" value={s.visual} />
          <ScoreRow label="Audio quality" value={s.audio} />
        </div>
        {clip.highlights?.length > 0 && (
          <div className="chip-row">
            {clip.highlights.slice(0, 3).map((h, i) => <span key={i} className="mini-chip">{h}</span>)}
          </div>
        )}
        <div className="clip-actions">
          <button className="btn small primary" onClick={onRender} disabled={rendering}>
            {rendering ? <><span className="spinner" /> Rendering…</> : newest ? "Re-render" : "Render"}
          </button>
          {newest && (
            <a className="btn small" href={api.downloadClipUrl(project.id, clip.id)}>
              <IconDownload size={14} /> {newest.height}p · {(newest.size_bytes / 1048576).toFixed(1)} MB
            </a>
          )}
          {!newest && <span className="renders-note">Not rendered yet</span>}
        </div>
        {newest?.upscaled_to_source_limit && (
          <div className="settings-toggle">Source-resolution export: output capped at true source size (no fake upscale).</div>
        )}
      </div>
    </div>
  );
}

function ScoreRow({ label, value }) {
  return (
    <div className="score-row">
      <span>{label}</span>
      <span className="bar"><i style={{ width: `${value}%` }} /></span>
      <span className="num">{value.toFixed(0)}</span>
    </div>
  );
}

function fmtTime(t) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}
