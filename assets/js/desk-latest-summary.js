(() => {
  "use strict";

  const REFRESH_MS = 60 * 1000;
  const DESKS = [
    ["world", "世界", "world.html"],
    ["asia", "亞洲", "asia.html"],
    ["hong-kong", "香港", "hong-kong.html"],
    ["japan", "日本", "japan.html"],
    ["market-economy", "財經 / 全球市場", "finance.html"],
    ["ai-tech", "AI / 科技", "technology.html"],
    ["manga-anime", "漫畫 / Anime", "manga-anime.html"],
    ["manchester-united", "Manchester United", "manchester-united.html"],
    ["football", "Football", "football.html"],
  ];
  let timer = null;
  let lastKey = "";

  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function sources(story) {
    if (Array.isArray(story?.sources) && story.sources.length) return story.sources;
    return story?.sourceUrl ? [{ name: story.sourceName || "原文", url: story.sourceUrl }] : [];
  }

  function sourceMarkup(story) {
    const items = sources(story).filter((item) => item?.url);
    if (!items.length) return "";
    return `<div class="article-sources"><strong>核實來源：</strong> ${items.map((item) => `<a class="source-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function keyFor(data) {
    const desks = data?.desks || {};
    return [
      data?.generatedAt || "",
      ...DESKS.map(([slug]) => {
        const first = Array.isArray(desks[slug]) ? desks[slug][0] : null;
        return `${slug}:${first?.id || ""}:${first?.title || ""}`;
      }),
    ].join("|");
  }

  function render(data) {
    const host = document.querySelector("#desk-latest-summary");
    if (!host) return;
    const desks = data?.desks || {};
    const cards = DESKS.map(([slug, title, page]) => {
      const stories = Array.isArray(desks[slug]) ? desks[slug] : [];
      const story = stories.find((item) => item && typeof item === "object");
      if (!story) return "";
      return `<article class="story-card desk-latest-card">
        <div class="tag">${esc(title)} · LATEST</div>
        <h3><a href="${esc(page)}">${esc(story.title || "")}</a></h3>
        <p>${esc(story.summary || story.dek || "")}</p>
        <div class="story-meta">${esc(story.timeLabel || "")}</div>
        ${sourceMarkup(story)}
      </article>`;
    }).filter(Boolean).join("");

    host.innerHTML = `<div class="section-heading"><h2>各版最新</h2><span>DESK LATEST · ${esc(data?.generatedAt || "")}</span></div>
      <p class="notice">Live 只顯示今小時真正有變化的新聞；這裡保留各新聞 Desk 目前最新的重要內容，避免把「沒有新增卡片」誤解成「沒有新聞」。</p>
      <div class="story-grid">${cards || '<p class="notice">各版最新內容暫未能整理。</p>'}</div>`;
  }

  async function refresh(force = false) {
    const host = document.querySelector("#desk-latest-summary");
    if (!host) return;
    try {
      const url = new URL("data/desk-latest.json", document.baseURI);
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
      // Keep the deploy-time prerendered content visible if refreshing fails.
      console.warn("Desk Latest refresh failed", error);
    }
  }

  function start() {
    refresh(true);
    if (timer) clearInterval(timer);
    timer = setInterval(() => refresh(false), REFRESH_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refresh(true);
    });
    window.addEventListener("pageshow", () => refresh(true));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
