(() => {
  "use strict";
  const esc = (v = "") => String(v).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const byTitle = new Map();

  async function json(path) {
    try {
      const r = await fetch(path, { cache: "no-store" });
      return r.ok ? await r.json() : null;
    } catch (_) { return null; }
  }

  function addStory(story) {
    if (!story?.title) return;
    const old = byTitle.get(story.title) || {};
    byTitle.set(story.title, { ...old, ...story });
  }

  async function buildIndex() {
    const latest = await json("data/latest.json");
    (latest?.articles || []).forEach(addStory);
    if (latest?.date) {
      const more = await json(`data/topic-more/${latest.date}.json`);
      (more?.articles || []).forEach(addStory);
    }
    const desks = await json("data/desk-latest.json");
    Object.values(desks?.desks || {}).forEach((rows) => (rows || []).forEach(addStory));
    const live = await json("data/live.json");
    (live?.items || []).forEach(addStory);
  }

  function paragraphs(text = "") {
    return String(text).split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean).map((p) => `<p>${esc(p)}</p>`).join("");
  }

  function sourceLinks(story) {
    const sources = Array.isArray(story.sources) && story.sources.length ? story.sources : (story.sourceUrl ? [{ name: story.sourceName || "原文", url: story.sourceUrl }] : []);
    if (!sources.length) return "";
    return `<div class="source-cluster"><strong>核實來源：</strong> ${sources.map((s) => `<a class="source-link" href="${esc(s.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(s.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function upgradeArticle(article) {
    if (article.classList.contains("live-story") || article.classList.contains("topic-live-story")) return;

    const title = article.querySelector("h2, h3")?.textContent?.trim();
    if (!title) return;
    const story = byTitle.get(title);
    if (!story) return;
    const body = String(story.body || "").trim();
    const combined = `${story.summary || ""}${story.context || ""}${story.why || ""}${story.watchNext || ""}`;
    if (!body && combined.length < 100) return;

    let host = article.querySelector(".topic-article-body, .story-body");
    if (!host) {
      host = document.createElement("div");
      host.className = "topic-article-body";
      const meta = article.querySelector(".story-meta");
      if (meta?.nextSibling) article.insertBefore(host, meta.nextSibling); else article.appendChild(host);
    }

    const intro = story.summary ? `<p class="article-summary"><strong>摘要：</strong>${esc(story.summary)}</p>` : "";
    const main = body ? `<div class="article-main-copy">${paragraphs(body)}</div>` : "";
    const context = story.context ? `<p><strong>背景：</strong>${esc(story.context)}</p>` : "";
    const why = story.why ? `<p><strong>為何重要：</strong>${esc(story.why)}</p>` : "";
    const next = story.watchNext ? `<p><strong>下一步：</strong>${esc(story.watchNext)}</p>` : "";
    host.innerHTML = `${intro}${main}${context}${why}${next}`;

    const existingSource = article.querySelector(".topic-sources, .source-cluster");
    if (!existingSource && (story.sources?.length || story.sourceUrl)) article.insertAdjacentHTML("beforeend", sourceLinks(story));
    article.classList.add("newspaper-expanded");
  }

  async function apply() {
    // The rebuilt Live page has one renderer only: live-rebuild.js.
    if (document.body?.dataset?.page === "live") return;
    await buildIndex();
    document.querySelectorAll(".topic-story, .story-card, .lead-story").forEach(upgradeArticle);
  }

  [400, 1000, 2200].forEach((delay) => setTimeout(apply, delay));
})();