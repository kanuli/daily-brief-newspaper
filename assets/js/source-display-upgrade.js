(() => {
  "use strict";

  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function sources(story) {
    if (Array.isArray(story?.sources) && story.sources.length) return story.sources.filter((item) => item?.url);
    return story?.sourceUrl ? [{ name: story.sourceName || "原文", url: story.sourceUrl }] : [];
  }

  function markup(story) {
    const items = sources(story);
    if (!items.length) return "";
    return `<div class="article-sources"><strong>核實來源：</strong> ${items.map((item) => `<a class="source-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function titleOf(node) {
    return (node.querySelector("h2, h3")?.textContent || "").trim();
  }

  function upgradeNode(node, byTitle) {
    const story = byTitle.get(titleOf(node));
    if (!story) return;
    const html = markup(story);
    if (!html) return;
    node.querySelectorAll(":scope > .article-sources, :scope > .source-link").forEach((element) => element.remove());
    node.insertAdjacentHTML("beforeend", html);
  }

  function upgradeAll(byTitle) {
    const lead = document.querySelector("#lead-story");
    if (lead) upgradeNode(lead, byTitle);
    document.querySelectorAll("#dynamic-sections .story-card").forEach((node) => upgradeNode(node, byTitle));
  }

  async function start() {
    try {
      const url = new URL("data/latest.json", document.baseURI);
      url.searchParams.set("v", String(Date.now()));
      const response = await fetch(url.href, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const byTitle = new Map(
        (Array.isArray(data.articles) ? data.articles : [])
          .filter((story) => story?.title)
          .map((story) => [String(story.title).trim(), story])
      );
      upgradeAll(byTitle);

      const roots = [document.querySelector("#lead-story"), document.querySelector("#dynamic-sections")].filter(Boolean);
      const observer = new MutationObserver(() => upgradeAll(byTitle));
      roots.forEach((root) => observer.observe(root, { childList: true, subtree: true }));
      window.setTimeout(() => observer.disconnect(), 15000);
    } catch (error) {
      // Deploy-time prerender already contains full sources; do not erase it on failure.
      console.warn("Homepage source upgrade unavailable", error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
