(() => {
  "use strict";

  const MANIFEST_PATH = "data/tts-manifest.json";
  const WORKFLOW_API = "https://api.github.com/repos/kanuli/daily-brief-newspaper/actions/workflows/cosyvoice-publish.yml/runs?branch=main&per_page=1";
  const MAX_PARALLEL = 10;
  const MANIFEST_REFRESH_MS = 15000;
  const WORKFLOW_REFRESH_MS = 60000;
  const RECENT_PUBLISH_MS = 20 * 60 * 1000;

  let manifestTimer = null;
  let workflowTimer = null;
  let latestManifest = null;
  let latestWorkflow = null;

  function ensureStyles() {
    if (document.getElementById("voice-production-status-style")) return;
    const style = document.createElement("style");
    style.id = "voice-production-status-style";
    style.textContent = `
      .voice-production-row .voice-production-copy{min-width:0;flex:1}
      .voice-progress-top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
      .voice-progress-percent{font-size:12px;font-weight:900;color:#79000e;white-space:nowrap}
      .voice-progress-track{height:8px;margin:6px 0 5px;border:1px solid #111;background:#ddd5c7;overflow:hidden}
      .voice-progress-fill{display:block;height:100%;width:0;background:#198754;transition:width .25s ease}
      .voice-progress-stats{display:flex!important;flex-wrap:wrap;gap:4px 10px;color:#312d27!important;font-weight:800}
      .voice-progress-stats span{white-space:nowrap}
      .voice-progress-detail{margin-top:4px!important}
      .voice-production-row.status-warn .voice-progress-fill{background:#c17b00}
      .voice-production-row.status-fail .voice-progress-fill{background:#b00016}
    `;
    document.head.appendChild(style);
  }

  function numberOr(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function formatHKT(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("zh-HK", {
      timeZone: "Asia/Hong_Kong",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    }).format(date) + " HKT";
  }

  function manifestSnapshot(manifest) {
    const fallbackDone = Object.keys(manifest?.articles || {}).length;
    const done = Math.max(0, numberOr(manifest?.availableArticleCount ?? manifest?.articleCount, fallbackDone));
    const total = Math.max(done, numberOr(manifest?.collectedStoryCount, done));
    const pending = Math.max(0, numberOr(manifest?.pendingArticleCount, total - done));
    const percent = total > 0 ? Math.min(100, Math.max(0, (done / total) * 100)) : 0;
    return { done, total, pending, percent };
  }

  function workflowState() {
    const run = latestWorkflow;
    if (!run) return { state: "unknown", creating: null, label: "Checking workers" };
    if (run.status === "in_progress") return { state: "active", creating: null, label: "10-worker pool active" };
    if (run.status === "queued" || run.status === "waiting" || run.status === "pending") return { state: "queued", creating: 0, label: "Worker pool queued" };
    if (run.status === "completed" && run.conclusion === "success") return { state: "idle", creating: 0, label: "Worker run completed" };
    if (run.status === "completed" && run.conclusion) return { state: "failed", creating: 0, label: `Worker run ${run.conclusion}` };
    return { state: "unknown", creating: null, label: run.status || "Checking workers" };
  }

  function render() {
    const row = document.getElementById("voice-production-status-row");
    if (!row || !latestManifest) return;

    const snap = manifestSnapshot(latestManifest);
    const wf = workflowState();
    const lastPublish = Date.parse(latestManifest.generatedAt || "");
    const recentlyPublishing = Number.isFinite(lastPublish) && (Date.now() - lastPublish) <= RECENT_PUBLISH_MS;

    let creating = wf.creating;
    let state = wf.state;
    let stateLabel = wf.label;
    if (wf.state === "active") creating = Math.min(MAX_PARALLEL, snap.pending);
    if (wf.state === "unknown" && snap.pending > 0 && recentlyPublishing) {
      creating = Math.min(MAX_PARALLEL, snap.pending);
      state = "active";
      stateLabel = "Publishing recently · worker API pending";
    }
    if (snap.pending === 0) {
      creating = 0;
      state = "complete";
      stateLabel = "Coverage complete";
    }

    row.classList.remove("status-ok", "status-check", "status-warn", "status-fail");
    row.classList.add(state === "complete" || state === "active" ? "status-ok" : state === "failed" ? "status-fail" : "status-warn");

    const percentText = `${snap.percent.toFixed(1)}%`;
    row.querySelector(".voice-progress-percent").textContent = percentText;
    const progress = row.querySelector(".voice-progress-track");
    progress?.setAttribute("aria-valuenow", snap.percent.toFixed(1));
    row.querySelector(".voice-progress-fill").style.width = `${snap.percent.toFixed(2)}%`;
    row.querySelector(".voice-done").textContent = `Done ${snap.done}/${snap.total}`;
    row.querySelector(".voice-creating").textContent = creating == null
      ? `Creating ?/${snap.pending} pending`
      : `Creating ${creating}/${snap.pending} pending`;
    row.querySelector(".voice-progress-detail").textContent = `${stateLabel} · Last voice ${formatHKT(latestManifest.generatedAt)} · F01 only`;

    const systemLabel = document.querySelector("#system-status-button .system-status-label");
    if (systemLabel) systemLabel.textContent = `SYSTEM · VOICE ${percentText}`;
    const systemButton = document.getElementById("system-status-button");
    if (systemButton) systemButton.title = `Voice ${percentText} · Done ${snap.done}/${snap.total} · Pending ${snap.pending}`;
  }

  async function loadManifest() {
    try {
      const url = new URL(MANIFEST_PATH, document.baseURI);
      url.searchParams.set("status", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`manifest HTTP ${response.status}`);
      latestManifest = await response.json();
      render();
    } catch (error) {
      const row = document.getElementById("voice-production-status-row");
      if (row) {
        row.classList.remove("status-ok", "status-check", "status-warn");
        row.classList.add("status-fail");
        row.querySelector(".voice-progress-detail").textContent = `Cannot read production manifest · ${error.message}`;
      }
    }
  }

  async function loadWorkflow() {
    try {
      const response = await fetch(WORKFLOW_API, {
        cache: "no-store",
        headers: { "Accept": "application/vnd.github+json" }
      });
      if (!response.ok) throw new Error(`workflow HTTP ${response.status}`);
      const data = await response.json();
      latestWorkflow = Array.isArray(data.workflow_runs) ? (data.workflow_runs[0] || null) : null;
    } catch (error) {
      console.warn("Voice production workflow status unavailable", error);
      latestWorkflow = null;
    }
    render();
  }

  function startLiveRefresh() {
    stopLiveRefresh();
    loadManifest();
    loadWorkflow();
    manifestTimer = window.setInterval(loadManifest, MANIFEST_REFRESH_MS);
    workflowTimer = window.setInterval(loadWorkflow, WORKFLOW_REFRESH_MS);
  }

  function stopLiveRefresh() {
    if (manifestTimer) window.clearInterval(manifestTimer);
    if (workflowTimer) window.clearInterval(workflowTimer);
    manifestTimer = null;
    workflowTimer = null;
  }

  function mount() {
    const panel = document.getElementById("system-status-panel");
    if (!panel) return false;
    if (document.getElementById("voice-production-status-row")) return true;
    ensureStyles();

    const row = document.createElement("div");
    row.id = "voice-production-status-row";
    row.className = "system-panel-row status-check voice-production-row";
    row.innerHTML = `
      <span class="status-dot" aria-hidden="true"></span>
      <div class="voice-production-copy">
        <div class="voice-progress-top"><strong>Voice Creation</strong><span class="voice-progress-percent">—</span></div>
        <div class="voice-progress-track" role="progressbar" aria-label="F01 voice production progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="voice-progress-fill"></span></div>
        <small class="voice-progress-stats"><span class="voice-done">Done —/—</span><span class="voice-creating">Creating —/—</span></small>
        <small class="voice-progress-detail">Loading production status…</small>
      </div>`;

    const cantoneseRow = Array.from(panel.querySelectorAll(".system-panel-row")).find((item) => item.textContent.includes("Cantonese Voice"));
    if (cantoneseRow) cantoneseRow.insertAdjacentElement("afterend", row);
    else panel.querySelector(".system-panel-links")?.insertAdjacentElement("beforebegin", row);

    const button = document.getElementById("system-status-button");
    const syncOpenState = () => {
      if (!panel.hidden) startLiveRefresh();
      else stopLiveRefresh();
    };
    button?.addEventListener("click", () => window.setTimeout(syncOpenState, 0));
    panel.querySelector(".system-panel-close")?.addEventListener("click", () => window.setTimeout(syncOpenState, 0));

    const observer = new MutationObserver(syncOpenState);
    observer.observe(panel, { attributes: true, attributeFilter: ["hidden"] });

    loadManifest();
    return true;
  }

  if (!mount()) {
    const observer = new MutationObserver(() => {
      if (mount()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
