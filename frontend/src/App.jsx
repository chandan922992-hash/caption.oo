import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Dashboard from "./components/Dashboard.jsx";
import ProjectPage from "./pages/ProjectPage.jsx";
import * as api from "./api.js";

export default function App() {
  const [view, setView] = useState("dashboard");
  const [projectId, setProjectId] = useState(null);
  const [status, setStatus] = useState(null);
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    api.getSystemStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  const toast = useCallback((message, kind = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const openProject = (p) => {
    setProjectId(p.id);
    setView("project");
  };

  const toDashboard = () => {
    setView("dashboard");
    setProjectId(null);
    api.getSystemStatus().then(setStatus).catch(() => {});
  };

  return (
    <div className="app-shell">
      <Sidebar view={view} onNav={(v) => { if (v === "dashboard") toDashboard(); }} status={status} />

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", height: "100vh" }}>
        <div className="mobile-header">
          <div className="logo" style={{ padding: 0 }}>
            <div className="logo-mark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><path d="M8 5.5l10 6.5-10 6.5v-13z" /></svg>
            </div>
            <div className="logo-name">CLEA<span>PYFLY</span></div>
          </div>
          <button className="btn small" onClick={toDashboard}>Dashboard</button>
        </div>

        <main className="main">
          <div className="page" style={view === "project" ? { padding: "26px 40px 80px" } : undefined}>
            {view === "dashboard" ? (
              <Dashboard status={status} onOpenProject={openProject} toast={toast} />
            ) : (
              <ProjectPage
                projectId={projectId}
                onBack={toDashboard}
                toast={toast}
                onDeleted={toDashboard}
              />
            )}
          </div>
        </main>
      </div>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>{t.message}</div>
        ))}
      </div>
    </div>
  );
}
