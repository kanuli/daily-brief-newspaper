(() => {
  "use strict";

  const LIVE_JSON = "data/live.json";
  const REFRESH_MS = 60 * 1000;
  let refreshTimer = null;
  let lastKey = "";

  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const META_SENTENCE = /(?:本輪|本報|incremental|duplicate|重複刊登|搜集規則|collection (?:design|test|rule)|coverage (?:test|check)|每一輪Football|之後每一輪|固定檢查(?:HKFA|J-?League|賽程|賽果)?|不應由全球搜尋排名決定|應該看到的核心新聞)/i;

  function cleanCopy(value = "") {
    return String(value)
      .split(/(?<=[。！？!?])\s*/)
      .filter((sentence) => sentence && !META_SENTENCE.test(sentence))
      .join("")
      .trim();
  }

  function bodyParagraphs(value = "") {
    return String(value)
      .split(/\n\s*\n/)
      .map(cleanCopy)
      .filter(Boolean)
      .map((paragraph) => `<p>${esc(paragraph)}</p>`)
      .join("");
  }

  const badge = (status = "UPDATED") => {
    const safe = String(status).toUpperCase();
    return `<span class="live-badge live-${esc(safe.toLowerCase())}">${esc(safe)}</span>`;
  };

  function sourceMarkup(item) {
    const sources = Array.isArray(item.sources) && item.sources.length
      ? item.sources
      : (item.sourceUrl ? [{ name: item.sourceName || "原文", url: item.sourceUrl }] : []);
    if (!sources.length) return "";
    return `<div class="article-sources topic-sources"><strong>核實來源：</strong> ${sources.map((source) => `<a class="source-link" href="${esc(source.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(source.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function paragraph(label, value, className) {
    const clean = cleanCopy(value);
    if (!clean) return "";
    return `<p class="${className}"><strong>${label}</strong>${esc(clean)}</p>`;
  }

  function renderStory(item, index) {
    const body = bodyParagraphs(item.body || "");
    const feature = index === 0 ? " topic-feature" : "";
    return `<article class="topic-story live-story live-story-rich${feature}">
      <div class="live-story-meta">${badge(item.status)} <span>${esc(item.section || "Live")}</span> <span>${esc(item.timeLabel || "")}</span></div>
      <h2>${esc(item.title || "")}</h2>
      ${item.dek ? `<p class="topic-dek live-article-dek">${esc(cleanCopy(item.dek))}</p>` : ""}
      <div class="topic-article-body live-article-body">
        ${paragraph("摘要：", item.summary, "live-article-summary")}
        ${body ? `<div class="live-body-main">${body}</div>` : ""}
        ${paragraph("背景：", item.context || item.background, "live-article-context")}
        ${paragraph("為何重要：", item.why || item.whyImportant, "live-article-why")}
        ${paragraph("下一步：", item.watchNext || item.nextStep, "live-article-next")}
      </div>
      ${sourceMarkup(item)}
    </article>`;
  }

  function keyFor(data) {
    return [data?.lastUpdated || "", data?.windowLabel || "", (data?.items || []).map((item) => `${item.id}:${item.status}`).join("|")].join("::");
  }

  function render(data) {
    const host = document.querySelector("#live-page-items");
    if (!host) return;
    const items = Array.isArray(data.items) ? data.items : [];
    const actual = items.reduce((counts, item) => {
      const key = String(item.status || "").toUpperCase();
      if (key in counts) counts[key] += 1;
      return counts;
    }, { NEW: 0, UPDATED: 0, DEVELOPING: 0 });

    const headerTime = document.querySelector("#live-header-time");
    if (headerTime) headerTime.textContent = data.lastUpdatedLabel || data.windowLabel || "Live";

    const stats = document.querySelector("#live-page-stats");
    if (stats) {
      stats.innerHTML = `<div><strong>${actual.NEW}</strong><span>NEW</span></div><div><strong>${actual.UPDATED}</strong><span>UPDATED</span></div><div><strong>${actual.DEVELOPING}</strong><span>DEVELOPING</span></div><p>${esc(data.nextUpdateLabel || "")}</p>`;
    }

    const coverage = data.coverage || {};
    const audit = document.querySelector("#live-audit");
    if (audit) {
      const sourceCount = Number(coverage.sourceOrganizationCount || 0);
      const searchCount = Number(coverage.freshSearchCount || 0);
      const rawCount = Number(coverage.rawFreshCandidateCount || 0);
      const verifiedCount = Number(coverage.verifiedCandidateCount || 0);
      const incrementalCount = Number(coverage.incrementalCandidateCount || 0);
      audit.innerHTML = sourceCount || searchCount || rawCount || verifiedCount || incrementalCount
        ? `<strong>最新搜集：</strong>${sourceCount} 個新聞機構 · ${searchCount} 次 fresh searches · raw ${rawCount} · verified ${verifiedCount} · incremental ${incrementalCount}`
        : `<strong>最新出版：</strong>${esc(data.lastUpdatedLabel || data.windowLabel || "已更新")}`;
    }

    host.innerHTML = items.length
      ? items.map((item, index) => renderStory(item, index)).join("")
      : `<p class="notice">暫未能載入本小時新聞；系統會自動重新讀取最新 Live publication。</p>`;
  }

  async function refresh({ force = false } = {}) {
    try {
      const url = new URL(LIVE_JSON, document.baseURI);
      url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const nextKey = keyFor(data);
      if (force || nextKey !== lastKey) {
        lastKey = nextKey;
        render(data);
      }
    } catch (error) {
      console.error("Live refresh failed", error);
      const audit = document.querySelector("#live-audit");
      if (audit) audit.textContent = "Live data 暫時讀取失敗，系統會自動重試。";
    }
  }

  function start() {
    if (refreshTimer) window.clearInterval(refreshTimer);
    refresh({ force: true });
    refreshTimer = window.setInterval(refresh, REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refresh({ force: true });
    });
    window.addEventListener("pageshow", () => refresh({ force: true }));
  }

  start();
})();