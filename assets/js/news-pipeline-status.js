(() => {
  "use strict";

  const STAGING_URL = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/news-staging/data/search-staging.json";
  const MAIN_LIVE_URL = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/main/data/live.json";
  const PAGES_STATUS_URL = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/pages-status/data/pages-live-status.json";
  const REFRESH_MS = 60 * 1000;
  const ROLLING_WARN_MS = 22 * 60 * 1000;
  const PAGES_PROBE_WARN_MS = 20 * 60 * 1000;

  let timer = null;

  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  async function fetchJson(url) {
    const target = new URL(url, document.baseURI);
    target.searchParams.set("status", String(Date.now()));
    const response = await fetch(target.href, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function ageMs(iso) {
    const time = Date.parse(iso || "");
    return Number.isFinite(time) ? Math.max(0, Date.now() - time) : Infinity;
  }

  function formatHKT(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("zh-HK", {
      timeZone: "Asia/Hong_Kong",
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: false
    }).format(date) + " HKT";
  }

  function ensureRow() {
    const panel = document.getElementById("system-status-panel");
    if (!panel) return null;
    let row = document.getElementById("news-pipeline-status-row");
    if (row) return row;

    row = document.createElement("div");
    row.id = "news-pipeline-status-row";
    row.className = "system-panel-row status-check";
    row.innerHTML = `
      <span class="status-dot" aria-hidden="true"></span>
      <div>
        <strong>News Pipeline</strong>
        <small class="news-pipeline-summary">Checking rolling discovery, main Live and public Pages…</small>
        <small class="news-pipeline-detail"></small>
      </div>`;

    const rows = [...panel.querySelectorAll(".system-panel-row")];
    const publishRow = rows.find((item) => item.querySelector("strong")?.textContent?.includes("Daily / Live / Stocks"));
    if (publishRow) publishRow.insertAdjacentElement("afterend", row);
    else panel.appendChild(row);
    return row;
  }

  async function refresh() {
    const row = ensureRow();
    if (!row) return;

    const [stagingResult, mainResult, pagesResult] = await Promise.allSettled([
      fetchJson(STAGING_URL), fetchJson(MAIN_LIVE_URL), fetchJson(PAGES_STATUS_URL)
    ]);

    const staging = stagingResult.status === "fulfilled" ? stagingResult.value : null;
    const main = mainResult.status === "fulfilled" ? mainResult.value : null;
    const pages = pagesResult.status === "fulfilled" ? pagesResult.value : null;

    const searchIso = clean(staging?.lastSearchAt || staging?.lastSearchStartedAt);
    const searchFresh = !!searchIso && ageMs(searchIso) <= ROLLING_WARN_MS;
    const mainIso = clean(main?.lastUpdated);
    const publicIso = clean(pages?.publicLastUpdated);
    const probeFresh = clean(pages?.checkedAt) && ageMs(pages.checkedAt) <= PAGES_PROBE_WARN_MS;
    const pagesMatch = !!(pages?.match && mainIso && publicIso === mainIso);

    let level = "ok";
    let summary = "Background discovery + Live publication + public Pages healthy";

    if (!staging || !main || !pages) {
      level = "warn";
      summary = "Status source incomplete · auto maintenance remains enabled";
    }
    if (!searchFresh) {
      level = "fail";
      summary = "Rolling discovery stale · collector auto maintenance repairing";
    } else if (!pagesMatch || !probeFresh) {
      level = "warn";
      summary = "Background discovery healthy · public Pages sync being checked/repaired";
    }

    row.classList.remove("status-ok", "status-check", "status-warn", "status-fail");
    row.classList.add(level === "ok" ? "status-ok" : level === "fail" ? "status-fail" : "status-warn");
    row.querySelector(".news-pipeline-summary").textContent = summary;

    const searchText = staging
      ? `Search ${formatHKT(searchIso)}${searchFresh ? " ✓" : " ⚠"}`
      : "Search status unavailable";
    const mainText = main
      ? `Main ${clean(main.windowLabel || main.lastUpdatedLabel || formatHKT(mainIso))}`
      : "Main Live unavailable";
    const publicText = pages
      ? `Public ${clean(pages.publicWindowLabel || formatHKT(publicIso))}${pagesMatch ? " ✓" : " ⚠"}`
      : "Public Pages probe unavailable";
    row.querySelector(".news-pipeline-detail").textContent = `${searchText} · ${mainText} · ${publicText}`;
  }

  function start() {
    const row = ensureRow();
    if (!row) return false;
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refresh();
    });
    return true;
  }

  if (!start()) {
    const observer = new MutationObserver(() => {
      if (start()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
