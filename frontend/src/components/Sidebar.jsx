import { IconHome, IconFilm, IconSpark } from "./icons.jsx";

const fmtMB = (mb) => (mb > 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${Math.round(mb)} MB`);

export default function Sidebar({ view, onNav, status }) {
  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-mark">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
            <path d="M8 5.5l10 6.5-10 6.5v-13z" />
          </svg>
        </div>
        <div className="logo-name">CLEA<span>PYFLY</span></div>
      </div>

      <button className={`nav-item ${view === "dashboard" ? "active" : ""}`} onClick={() => onNav("dashboard")}>
        <IconHome /> Dashboard
      </button>
      <button className={`nav-item ${view === "project" ? "active" : ""}`} onClick={() => onNav("project")} disabled={view !== "project"}>
        <IconFilm /> Current project
      </button>
      <button className="nav-item" onClick={() => onNav("dashboard")}>
        <IconSpark /> New clip session
      </button>

      <div className="nav-section">Platform</div>
      <div className="nav-item" style={{ cursor: "default" }}>
        AI engine <span className="nav-badge">local</span>
      </div>

      <div className="sidebar-footer">
        {status && (
          <div className="engine-card">
            <div className="engine-title">
              <span className={`engine-dot ${status.ffmpeg_found ? "" : "off"}`} />
              AI model status
            </div>
            <div className="engine-meta">
              <span>Analysis engine</span>
              <span>{status.engine_version.replace("cleapyfly-", "")}</span>
            </div>
            <div className="engine-meta" style={{ marginTop: 3 }}>
              <span>FFmpeg</span>
              <span>{status.ffmpeg_found ? "ready" : "missing"}</span>
            </div>
            <div className="storage-bar">
              <div className="storage-fill" style={{ width: `${Math.min(100, (status.storage_used_mb / 2048) * 100)}%` }} />
            </div>
            <div className="engine-meta" style={{ marginTop: 6 }}>
              <span>Storage used</span>
              <span>{fmtMB(status.storage_used_mb)}</span>
            </div>
          </div>
        )}
        <div className="user-chip">
          <div className="avatar">CL</div>
          <div>
            <div className="name">Local workspace</div>
            <div className="sub">{status ? `${status.clip_count} clips · ${status.rendered_count} rendered` : "connecting…"}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
