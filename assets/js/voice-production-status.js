(() => {
  "use strict";

  const MANIFEST_PATH = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/main/data/tts-manifest.json";
  const WORKFLOW_API = "https://api.github.com/repos/kanuli/daily-brief-newspaper/actions/workflows/cosyvoice-publish.yml/runs?branch=main&per_page=6";
  const MAX_PARALLEL = 10;
  const MANIFEST_REFRESH_MS = 15000;
  const INVENTORY_REFRESH_MS = 30000;
  const WORKFLOW_REFRESH_MS = 45000;
  const RECENT_PUBLISH_MS = 8 * 60 * 1000;
  const HARD_FAILURE_MS = 30 * 60 * 1000;
  const ACTIVE_STATUSES = new Set(["in_progress", "queued", "waiting", "pending", "requested"]);
  const STORY_FIELDS = ["dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep"];

  let manifestTimer = null;
  let inventoryTimer = null;
  let workflowTimer = null;
  let latestManifest = null;
  let latestInventory = null;
  let latestWorkflows = [];

  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

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
      .voice-progress-stats span{white-space:nowrap}.voice-progress-detail{margin-top:4px!important}
      .voice-production-row.status-warn .voice-progress-fill{background:#c17b00}
      .voice-production-row.status-fail .voice-progress-fill{background:#b00016}
    `;
    document.head.appendChild(style);
  }

  function formatHKT(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("zh-HK", {
      timeZone: "Asia/Hong_Kong", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
    }).format(date) + " HKT";
  }

  function trueLastVoiceIso(manifest) {
    const direct = clean(manifest?.lastVoicePublishedAt);
    if (direct) return direct;
    const times = Object.values(manifest?.articles || {})
      .map((entry) => clean(entry?.publishedAt))
      .filter(Boolean)
      .sort();
    return times.length ? times[times.length - 1] : "";
  }

  function looksLikeStory(obj) {
    return !!(obj && typeof obj === "object" && !Array.isArray(obj) && clean(obj.title) && STORY_FIELDS.some((key) => clean(obj[key])));
  }

  function collectTitles(node, target) {
    if (Array.isArray(node)) {
      node.forEach((item) => collectTitles(item, target));
      return;
    }
    if (!node || typeof node !== "object") return;
    if (looksLikeStory(node)) target.add(clean(node.title));
    Object.values(node).forEach((value) => collectTitles(value, target));
  }

  async function fetchJson(path) {
    const url = new URL(path, document.baseURI);
    url.searchParams.set("status", String(Date.now()));
    const response = await fetch(url.href, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
    return response.json();
  }

  async function loadInventory() {
    try {
      const latest = await fetchJson("data/latest.json");
      const date = clean(latest?.date);
      const paths = [
        "data/desk-latest.json",
        "data/live.json",
        "data/stocks-latest.json",
        ...(date ? [`data/topic-more/${date}.json`, `data/editorial-overrides/${date}.json`] : [])
      ];
      const results = await Promise.all(paths.map(async (path) => {
        try { return await fetchJson(path); } catch (_) { return null; }
      }));
      const titles = new Set();
      collectTitles(latest, titles);
      results.forEach((data) => { if (data) collectTitles(data, titles); });
      latestInventory = { date, titles, total: titles.size, loadedAt: new Date().toISOString() };
    } catch (error) {
      console.warn("Current news inventory unavailable", error);
      latestInventory = null;
    }
    render();
  }

  function manifestSnapshot(manifest) {
    const manifestEntries = Object.values(manifest?.articles || {});
    const readyTitles = new Set(manifestEntries.filter((entry) => clean(entry?.audio)).map((entry) => clean(entry?.title)).filter(Boolean));

    if (latestInventory?.total > 0) {
      let done = 0;
      latestInventory.titles.forEach((title) => { if (readyTitles.has(title)) done += 1; });
      const total = latestInventory.total;
      const pending = Math.max(0, total - done);
      const percent = total > 0 ? Math.min(100, Math.max(0, (done / total) * 100)) : 0;
      return { done, total, pending, percent, source: "current-inventory" };
    }

    const done = manifestEntries.filter((entry) => clean(entry?.audio)).length;
    const manifestTotal = Number(manifest?.collectedStoryCount);
    const total = Math.max(done, Number.isFinite(manifestTotal) ? manifestTotal : done);
    const pending = Math.max(0, total - done);
    const percent = total > 0 ? Math.min(100, Math.max(0, (done / total) * 100)) : 0;
    return { done, total, pending, percent, source: "manifest-fallback" };
  }

  function workflowState() {
    const active = latestWorkflows.find((run) => ACTIVE_STATUSES.has(run?.status));
    if (active) {
      if (active.status === "in_progress") return { state: "active", creating: null, label: "10-worker pool active" };
      return { state: "queued", creating: 0, label: "Worker pool queued / starting" };
    }
    const run = latestWorkflows[0];
    if (!run) return { state: "unknown", creating: null, label: "Checking workers" };
    if (run.status === "completed" && run.conclusion === "success") return { state: "idle", creating: 0, label: "Worker run completed" };
    if (run.status === "completed" && run.conclusion === "cancelled") return { state: "cancelled", creating: 0, label: "Previous worker run cancelled / replaced" };
    if (run.status === "completed" && run.conclusion) return { state: "failed", creating: 0, label: `Worker run ${run.conclusion}` };
    return { state: "unknown", creating: null, label: run.status || "Checking workers" };
  }

  function render() {
    const row = document.getElementById("voice-production-status-row");
    if (!row || !latestManifest) return;

    const snap = manifestSnapshot(latestManifest);
    const wf = workflowState();
    const lastVoiceIso = trueLastVoiceIso(latestManifest);
    // Transitional manifests created before true publish timestamps existed may
    // still have audio but no lastVoicePublishedAt. Do not display generatedAt
    // as a fake "Last voice" time. It may be a reconcile-only timestamp.
    const lastPublish = Date.parse(lastVoiceIso || "");
    const ageMs = Number.isFinite(lastPublish) ? Math.max(0, Date.now() - lastPublish) : Infinity;
    const recentlyPublishing = Number.isFinite(lastPublish) && ageMs <= RECENT_PUBLISH_MS;
    const hardStale = Number.isFinite(lastPublish) ? ageMs >= HARD_FAILURE_MS : false;
    const manifestDate = clean(latestManifest.date);
    const inventoryDrift = !!(latestInventory?.date && manifestDate && latestInventory.date !== manifestDate);

    let creating = wf.creating;
    let state = wf.state;
    let stateLabel = wf.label;

    if (wf.state === "active") creating = Math.min(MAX_PARALLEL, snap.pending);

    if (snap.pending > 0 && wf.state === "cancelled") {
      creating = 0;
      state = hardStale ? "failed" : "maintenance";
      stateLabel = hardStale ? "Worker cancelled · current F01 backlog is stale" : "Previous pending run replaced · active/maintenance pool continues";
    }
    if (snap.pending > 0 && wf.state === "idle") {
      state = "maintenance";
      stateLabel = "Worker ended · auto maintenance continuing current backlog";
    }
    if (snap.pending > 0 && wf.state === "failed") {
      state = hardStale ? "failed" : "maintenance";
      stateLabel = recentlyPublishing
        ? "Partial worker failure · recent F01 progress · auto maintenance continuing"
        : (hardStale ? `${wf.label} · current backlog has no recent F01 progress` : `${wf.label} · auto maintenance retrying`);
    }
    if (snap.pending > 0 && wf.state === "unknown" && recentlyPublishing) {
      state = "active";
      creating = null;
      stateLabel = "Recent F01 publishing detected · worker API pending";
    }
    if (inventoryDrift && snap.pending > 0 && wf.state !== "active" && wf.state !== "queued") {
      state = hardStale ? "failed" : "maintenance";
      stateLabel = `Manifest ${manifestDate || "old"} ≠ current ${latestInventory.date} · auto maintenance repairing`;
    }
    if (snap.pending === 0) {
      creating = 0;
      state = "complete";
      stateLabel = "Current news coverage complete";
    }

    row.classList.remove("status-ok", "status-check", "status-warn", "status-fail");
    row.classList.add(state === "complete" || state === "active" ? "status-ok" : state === "failed" ? "status-fail" : "status-warn");

    row.querySelector(".voice-progress-percent").textContent = `${snap.percent.toFixed(1)}%`;
    const progress = row.querySelector(".voice-progress-track");
    progress?.setAttribute("aria-valuenow", snap.percent.toFixed(1));
    row.querySelector(".voice-progress-fill").style.width = `${snap.percent.toFixed(2)}%`;
    row.querySelector(".voice-done").textContent = `Done ${snap.done}/${snap.total}`;
    row.querySelector(".voice-creating").textContent = creating == null
      ? `Creating ?/${snap.pending} pending`
      : `Creating ${creating}/${snap.pending} pending`;
    const maintenance = snap.pending > 0 ? " · Auto maintenance: ON" : "";
    const countSource = snap.source === "current-inventory" ? "current news inventory" : "manifest fallback";
    const lastVoiceLabel = lastVoiceIso ? formatHKT(lastVoiceIso) : "not recorded yet";
    row.querySelector(".voice-progress-detail").textContent = `${stateLabel}${maintenance} · ${countSource} · Last voice ${lastVoiceLabel} · F01 only`;

    const systemLabel = document.querySelector("#system-status-button .system-status-label");
    if (systemLabel) systemLabel.textContent = "SYSTEM";
    const systemButton = document.getElementById("system-status-button");
    if (systemButton) systemButton.title = "System status";
  }

  async function loadManifest() {
    try {
      latestManifest = await fetchJson(MANIFEST_PATH);
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
      const response = await fetch(`${WORKFLOW_API}&statusCache=${Date.now()}`, { cache: "no-store", headers: { "Accept": "application/vnd.github+json" } });
      if (!response.ok) throw new Error(`workflow HTTP ${response.status}`);
      const data = await response.json();
      latestWorkflows = Array.isArray(data.workflow_runs) ? data.workflow_runs : [];
    } catch (error) {
      console.warn("Voice production workflow status unavailable", error);
      latestWorkflows = [];
    }
    render();
  }

  function stopLiveRefresh() {
    if (manifestTimer) window.clearInterval(manifestTimer);
    if (inventoryTimer) window.clearInterval(inventoryTimer);
    if (workflowTimer) window.clearInterval(workflowTimer);
    manifestTimer = inventoryTimer = workflowTimer = null;
  }

  function startLiveRefresh() {
    stopLiveRefresh();
    loadManifest(); loadInventory(); loadWorkflow();
    manifestTimer = window.setInterval(loadManifest, MANIFEST_REFRESH_MS);
    inventoryTimer = window.setInterval(loadInventory, INVENTORY_REFRESH_MS);
    workflowTimer = window.setInterval(loadWorkflow, WORKFLOW_REFRESH_MS);
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
        <small class="voice-progress-detail">Loading current news inventory…</small>
      </div>`;
    const systemRows = Array.from(panel.querySelectorAll(".system-panel-row"));
    const voiceRow = systemRows.find((item) => item.querySelector("strong")?.textContent?.includes("Cantonese Voice"));
    if (voiceRow) voiceRow.insertAdjacentElement("afterend", row);
    else panel.appendChild(row);
    startLiveRefresh();
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopLiveRefresh(); else startLiveRefresh();
    });
    return true;
  }

  if (!mount()) {
    const observer = new MutationObserver(() => { if (mount()) observer.disconnect(); });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
