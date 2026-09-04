(() => {
  "use strict";

  const LIVE_JSON = "data/live.json";
  const REFRESH_MS = 60 * 1000;
  let timer = null;
  let lastKey = "";

  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function clean(value = "") {
    return String(value).trim();
  }

  function paragraphs(value = "") {
    return String(value)
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => `<p>${esc(p)}</p>`)
      .join("");
  }

  function sources(item) {
    const list = Array.isArray(item.sources) && item.sources.length
      ? item.sources
      : (item.sourceUrl ? [{ name: item.sourceName || "原文", url: item.sourceUrl }] : []);
    if (!list.length) return "";
    return `<div class="topic-sources"><strong>核實來源：</strong> ${list.map((source) => `<a class="source-link" href="${esc(source.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(source.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function detail(label, value, className) {
    const text = clean(value);
    return text ? `<p class="${className}"><strong>${label}</strong>${esc(text)}</p>` : "";
  }

  function renderStory(item, index) {
    const feature = index === 0 ? " topic-feature" : "";
    const status = esc(String(item.status || "LIVE").toUpperCase());
    const section = esc(item.section || item.deskLabel || "Live");
    const body = paragraphs(item.body || "");
    return `<article class="topic-story topic-live-story${feature}">
      <div class="tag"><span class="topic-live-badge">${status}</span>${section}</div>
      <h2>${esc(item.title || "")}</h2>
      ${item.dek ? `<p class="topic-dek">${esc(item.dek)}</p>` : ""}
      <div class="topic-article-body">
        ${detail("最新：", item.summary, "topic-summary")}
        ${body ? `<div class="topic-full-body">${body}</div>` : ""}
        ${detail("背景：", item.context || item.background, "topic-context")}
        ${detail("為何重要：", item.why || item.whyImportant, "why-mini")}
        ${detail("下一步：", item.watchNext || item.nextStep, "topic-next")}
      </div>
      <div class="story-meta">${esc(item.timeLabel || "")}${item.sourceName ? ` · ${esc(item.sourceName)}` : ""}</div>
      ${sources(item)}
    </article>`;
  }

  function keyFor(data) {
    return [data?.lastUpdated || "", (data?.items || []).map((item) => `${item.id || item.title}:${item.status || ""}`).join("|")].join("::");
  }

  function render(data) {
    const host = document.querySelector("#live-page-items");
    if (!host) return;
    const items = Array.isArray(data.items) ? data.items : [];

    const headerTime = document.querySelector("#live-header-time");
    if (headerTime) headerTime.textContent = data.lastUpdatedLabel || data.windowLabel || "Live";

    const date = document.querySelector("#live-topic-date");
    if (date) date.textContent = data.lastUpdatedLabel || data.windowLabel || data.lastUpdated || "Live";

    const count = document.querySelector("#live-topic-count");
    if (count) count.textContent = `${items.length} stories`;

    const audit = document.querySelector("#live-audit");
    if (audit) audit.innerHTML = `<p>${esc(data.nextUpdateLabel || "")}</p>`;

    host.innerHTML = items.length
      ? items.map(renderStory).join("")
      : `<p class="notice">目前沒有新增 Live 新聞；Daily Edition 及各分版最新內容仍然保留。</p>`;
  }

  async function refresh(force = false) {
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
    refresh(true);
    timer = window.setInterval(() => refresh(false), REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refresh(true);
    });
    window.addEventListener("pageshow", () => refresh(true));
  }

  start();
})();
