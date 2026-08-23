(() => {
  "use strict";
  const REFRESH_MS = 60 * 1000;
  let timer = null;
  let lastKey = "";

  async function refresh(force = false) {
    const host = document.querySelector("#live-summary");
    if (!host) return;
    try {
      const url = new URL("data/live.json", document.baseURI);
      url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const key = `${data.lastUpdated || ""}|${data.windowLabel || ""}|${(data.items || []).map((item) => `${item.id}:${item.status}`).join("|")}`;
      if (!force && key === lastKey) return;
      lastKey = key;
      if (typeof window.renderLiveSummary === "function") {
        window.renderLiveSummary(data);
        return;
      }
      // Safe fallback if the main newspaper script has not exposed its renderer.
      const esc = (value = "") => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
      const items = Array.isArray(data.items) ? data.items.slice(0, 4) : [];
      host.innerHTML = `<div class="live-summary-head"><div><div class="live-kicker"><span class="live-dot"></span> LIVE UPDATE</div><h2>最新新聞更新</h2><p>Last updated ${esc(data.lastUpdatedLabel || "—")} · ${esc(data.nextUpdateLabel || "")}</p></div></div><div class="live-summary-grid">${items.map((item) => `<article class="live-mini-card"><div><span class="live-badge live-${esc(String(item.status || "UPDATED").toLowerCase())}">${esc(item.status || "UPDATED")}</span> <span class="live-time">${esc(item.timeLabel || "")}</span></div><h3>${esc(item.title || "")}</h3><p>${esc(item.summary || "")}</p></article>`).join("")}</div><div class="live-more"><a href="live.html">查看完整 Live Update →</a></div>`;
    } catch (error) {
      console.warn("Home Live summary refresh failed", error);
    }
  }

  function start() {
    if (timer) clearInterval(timer);
    // newspaper.js performs the initial render; this refreshes shortly after and then continuously.
    setTimeout(() => refresh(true), 1500);
    timer = setInterval(() => refresh(false), REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refresh(true);
    });
    window.addEventListener("pageshow", () => refresh(true));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
