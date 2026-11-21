const BASE = "";

async function handle(res) {
  if (res.ok) return res.json();
  let detail = `Request failed (${res.status})`;
  try {
    const data = await res.json();
    if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
  } catch {
    /* keep default */
  }
  const err = new Error(detail);
  err.status = res.status;
  throw err;
}

export async function getSystemStatus() {
  return handle(await fetch(`${BASE}/api/system/status`));
}

export async function inspectSource(url) {
  return handle(await fetch(`${BASE}/api/sources/inspect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  }));
}

export async function uploadProject(file) {
  const form = new FormData();
  form.append("file", file);
  return handle(await fetch(`${BASE}/api/projects/upload`, { method: "POST", body: form }));
}

export async function createProjectFromUrl(url) {
  return handle(await fetch(`${BASE}/api/projects/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  }));
}

export async function listProjects() {
  const data = await handle(await fetch(`${BASE}/api/projects`));
  return data.projects;
}

export async function getProject(pid) {
  return handle(await fetch(`${BASE}/api/projects/${pid}`));
}

export async function deleteProject(pid) {
  return handle(await fetch(`${BASE}/api/projects/${pid}`, { method: "DELETE" }));
}

export async function analyzeProject(pid, opts) {
  return handle(await fetch(`${BASE}/api/projects/${pid}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  }));
}

export async function renderClip(pid, cid, opts) {
  return handle(await fetch(`${BASE}/api/projects/${pid}/clips/${cid}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  }));
}

export function downloadClipUrl(pid, cid) {
  return `${BASE}/api/projects/${pid}/clips/${cid}/download`;
}

export async function exportZip(pid, clipIds) {
  try {
    const res = await fetch(`${BASE}/api/projects/${pid}/export/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clip_ids: clipIds }),
    });
    if (!res.ok) {
      let detail = `Export failed (${res.status})`;
      try {
        const data = await res.json();
        if (data.detail) detail = data.detail;
      } catch { /* keep default */ }
      throw new Error(detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${pid}-clips.zip`;
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    /* no-op */
  }
}
