(() => {
  "use strict";

  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const badge = (status = "UPDATED") => {
    const safe = String(status).toUpperCase();
    return `<span class="live-badge live-${esc(safe.toLowerCase())}">${esc(safe)}</span>`;
  };

  function sourceMarkup(item) {
    const sources = Array.isArray(item.sources) && item.sources.length
      ? item.sources
      : (item.sourceUrl ? [{ name: item.sourceName || "原文", url: item.sourceUrl }] : []);
    if (!sources.length) return "";
    return `<div class="article-sources"><strong>核實來源：</strong> ${sources.map((source) => `<a class="source-link" href="${esc(source.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(source.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function paragraph(label, value, className) {
    if (!value) return "";
    return `<p class="${className}"><strong>${label}</strong>${esc(value)}</p>`;
  }

  function renderStory(item) {
    return `<article class="live-story live-story-rich">
      <div class="live-story-meta">${badge(item.status)} <span>${esc(item.section || "Live")}</span> <span>${esc(item.timeLabel || "")}</span></div>
      <h2>${esc(item.title || "")}</h2>
      ${item.dek ? `<p class="live-article-dek">${esc(item.dek)}</p>` : ""}
      <div class="live-article-body">
        ${paragraph("最新：", item.summary, "live-article-summary")}
        ${paragraph("背景：", item.context || item.background, "live-article-context")}
        ${paragraph("為何重要：", item.why || item.whyImportant, "live-article-why")}
        ${paragraph("下一步：", item.watchNext || item.nextStep, "live-article-next")}
      </div>
      ${sourceMarkup(item)}
    </article>`;
  }

  async function init() {
    try {
      const response = await fetch("data/live.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const host = document.querySelector("#live-page-items");
      if (!host) return;

      const items = Array.isArray(data.items) ? data.items : [];
      const actual = items.reduce((counts, item) => {
        const key = String(item.status || "").toUpperCase();
        if (key in counts) counts[key] += 1;
        return counts;
      }, { NEW: 0, UPDATED: 0, DEVELOPING: 0 });

      const stats = document.querySelector("#live-page-stats");
      if (stats) {
        stats.innerHTML = `<div><strong>${actual.NEW}</strong><span>NEW</span></div><div><strong>${actual.UPDATED}</strong><span>UPDATED</span></div><div><strong>${actual.DEVELOPING}</strong><span>DEVELOPING</span></div><p>${esc(data.nextUpdateLabel || "")}</p>`;
      }

      const coverage = data.coverage || {};
      const audit = document.querySelector("#live-audit");
      if (audit) {
        audit.innerHTML = `<strong>本輪搜集：</strong>${Number(coverage.sourceOrganizationCount || 0)} 個新聞機構 · ${Number(coverage.freshSearchCount || 0)} 次 fresh searches · raw ${Number(coverage.rawFreshCandidateCount || 0)} · verified ${Number(coverage.verifiedCandidateCount || 0)} · incremental ${Number(coverage.incrementalCandidateCount || 0)}`;
      }

      host.innerHTML = items.length ? items.map(renderStory).join("") : `<p class="notice">本輪未有可刊出的 incremental story；頁面仍保留各 Desk 最新已核實內容。</p>`;
    } catch (error) {
      console.error(error);
    }
  }

  init();
})();
