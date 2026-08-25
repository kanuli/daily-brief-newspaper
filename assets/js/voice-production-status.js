(() => {
  "use strict";

  const MANIFEST_PATH = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/main/data/tts-manifest.json";
  const WORKFLOW_API = "https://api.github.com/repos/kanuli/daily-brief-newspaper/actions/workflows/canto-nano-production.yml/runs?branch=main&per_page=6";
  const MAX_PARALLEL = 6;
  const MANIFEST_REFRESH_MS = 15000;
  const WORKFLOW_REFRESH_MS = 45000;
  const ACTIVE = new Set(["in_progress", "queued", "waiting", "pending", "requested"]);
  let manifestTimer = null, workflowTimer = null, latestManifest = null, latestRuns = [];

  function ensureStyles() {
    if (document.getElementById("voice-production-status-style")) return;
    const s = document.createElement("style");
    s.id = "voice-production-status-style";
    s.textContent = `.voice-production-row .voice-production-copy{min-width:0;flex:1}.voice-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.voice-progress-percent{font-size:12px;font-weight:900;color:#79000e;white-space:nowrap}.voice-progress-track{height:8px;margin:6px 0 5px;border:1px solid #111;background:#ddd5c7;overflow:hidden}.voice-progress-fill{display:block;height:100%;width:0;background:#198754;transition:width .25s ease}.voice-progress-stats{display:flex!important;flex-wrap:wrap;gap:4px 10px;color:#312d27!important;font-weight:800}.voice-progress-stats span{white-space:nowrap}.voice-progress-detail{margin-top:4px!important}.voice-production-row.status-warn .voice-progress-fill{background:#c17b00}.voice-production-row.status-fail .voice-progress-fill{background:#b00016}`;
    document.head.appendChild(s);
  }

  async function fetchJson(url) {
    const u = new URL(url, document.baseURI); u.searchParams.set("statusCache", String(Date.now()));
    const r = await fetch(u.href, { cache: "no-store", headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  function manifestSnapshot() {
    const done = Number(latestManifest?.availableArticleCount ?? latestManifest?.articleCount ?? 0);
    const total = Math.max(done, Number(latestManifest?.collectedStoryCount ?? done));
    const pending = Math.max(0, total - done);
    const percent = total ? Math.min(100, Math.max(0, done / total * 100)) : 0;
    return { done, total, pending, percent };
  }

  function pageSnapshot() {
    const buttons = [...document.querySelectorAll("main article .site-tts-button")];
    if (!buttons.length) return null;
    const done = buttons.filter((b) => b.dataset.ttsState === "ready" || (!b.disabled && !String(b.textContent || "").includes("準備中"))).length;
    const total = buttons.length;
    const pending = Math.max(0, total - done);
    const percent = total ? Math.min(100, Math.max(0, done / total * 100)) : 0;
    return { done, total, pending, percent };
  }

  function runState() {
    const active = latestRuns.find((r) => ACTIVE.has(r?.status));
    if (active) return active.status === "in_progress" ? { state: "active", label: "Canto Nano female worker pool active" } : { state: "queued", label: "Canto Nano female worker pool queued / starting" };
    const r = latestRuns[0];
    if (!r) return { state: "unknown", label: "Checking Canto Nano workers" };
    if (r.status === "completed" && r.conclusion === "success") return { state: "idle", label: "Latest Canto Nano worker run completed" };
    if (r.status === "completed" && r.conclusion === "cancelled") return { state: "queued", label: "Previous run replaced; next Canto Nano run pending" };
    if (r.status === "completed" && r.conclusion) return { state: "failed", label: `Canto Nano worker ${r.conclusion}` };
    return { state: "unknown", label: r.status || "Checking Canto Nano workers" };
  }

  function render() {
    const row = document.getElementById("voice-production-status-row");
    if (!row || !latestManifest) return;
    const m = manifestSnapshot(), p = pageSnapshot(), wf = runState();
    const visible = p && p.total > 0 ? p : null;
    const shown = visible || m;
    const correctEngine = latestManifest.engine === "typangaa/canto-tts-nano" && latestManifest.voice === "verified-female-reference" && latestManifest.assetNamespace === "cnf1";
    let state = wf.state, label = wf.label;

    if (!correctEngine) {
      state = "failed"; label = "Production manifest is not Canto Nano verified female";
    } else if (visible?.pending > 0) {
      state = wf.state === "active" ? "active" : "queued";
      label = `${visible.pending} visible article voice link${visible.pending === 1 ? "" : "s"} not playable yet`;
    } else if (m.pending === 0 && m.total > 0) {
      state = "complete";
      label = visible ? "Visible page playable · current manifest snapshot complete" : "Current manifest snapshot complete";
    } else if (wf.state === "idle") {
      state = "queued"; label = "Current manifest backlog remains; scheduled Canto Nano continuation enabled";
    }

    row.classList.remove("status-ok", "status-check", "status-warn", "status-fail");
    row.classList.add(state === "complete" || state === "active" ? "status-ok" : state === "failed" ? "status-fail" : "status-warn");
    row.querySelector(".voice-progress-percent").textContent = `${shown.percent.toFixed(1)}%`;
    row.querySelector(".voice-progress-track")?.setAttribute("aria-valuenow", shown.percent.toFixed(1));
    row.querySelector(".voice-progress-fill").style.width = `${shown.percent.toFixed(2)}%`;
    row.querySelector(".voice-done").textContent = visible ? `Playable ${visible.done}/${visible.total} visible` : `Done ${m.done}/${m.total}`;
    const creating = wf.state === "active" ? Math.min(MAX_PARALLEL, m.pending) : 0;
    row.querySelector(".voice-creating").textContent = `Manifest ${m.done}/${m.total} · Creating ${creating}/${m.pending} pending`;
    const last = latestManifest.lastVoicePublishedAt || "not published yet";
    row.querySelector(".voice-progress-detail").textContent = `${label} · canto-tts-nano verified female · Jyutping Cantonese-first · Last voice ${last}`;
  }

  async function loadManifest() {
    try { latestManifest = await fetchJson(MANIFEST_PATH); }
    catch (e) { console.warn("Canto Nano manifest status unavailable", e); latestManifest = null; }
    render();
  }
  async function loadWorkflow() {
    try {
      const data = await fetchJson(WORKFLOW_API);
      latestRuns = Array.isArray(data.workflow_runs) ? data.workflow_runs : [];
    } catch (e) {
      console.warn("Canto Nano workflow status unavailable", e); latestRuns = [];
    }
    render();
  }

  function mount() {
    const panel = document.getElementById("system-status-panel");
    if (!panel) return false;
    if (document.getElementById("voice-production-status-row")) return true;
    ensureStyles();
    const row = document.createElement("div");
    row.id = "voice-production-status-row";
    row.className = "system-panel-row status-check voice-production-row";
    row.innerHTML = `<span class="status-dot" aria-hidden="true"></span><div class="voice-production-copy"><div class="voice-progress-top"><strong>Voice Creation</strong><span class="voice-progress-percent">—</span></div><div class="voice-progress-track" role="progressbar" aria-label="Canto Nano verified female voice production and visible playback progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="voice-progress-fill"></span></div><small class="voice-progress-stats"><span class="voice-done">Done —/—</span><span class="voice-creating">Creating —/—</span></small><small class="voice-progress-detail">Loading Canto Nano production and playback state…</small></div>`;
    const voiceRow = [...panel.querySelectorAll(".system-panel-row")].find((x) => x.querySelector("strong")?.textContent?.includes("Cantonese Voice"));
    if (voiceRow) voiceRow.insertAdjacentElement("afterend", row); else panel.appendChild(row);
    loadManifest(); loadWorkflow();
    manifestTimer = window.setInterval(loadManifest, MANIFEST_REFRESH_MS);
    workflowTimer = window.setInterval(loadWorkflow, WORKFLOW_REFRESH_MS);
    return true;
  }

  let tries = 0;
  const boot = () => {
    if (mount() || ++tries > 40) return;
    window.setTimeout(boot, 250);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true }); else boot();
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") { loadManifest(); loadWorkflow(); } });
})();
