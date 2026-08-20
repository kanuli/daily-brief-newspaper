(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value = "") => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const dedupe = (ids = []) => [...new Set(ids.filter(Boolean))];

  function articleById(data, id) {
    return (data.articles || []).find((article) => article.id === id);
  }

  async function getJson(path, optional = false) {
    const res = await fetch(path, { cache: "no-store" });
    if (optional && res.status === 404) return null;
    if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
    return res.json();
  }

  async function applyEditorialOverride(data) {
    if (!data?.date) return data;
    const override = await getJson(`data/editorial-overrides/${data.date}.json`, true);
    if (!override) return data;

    const incoming = Array.isArray(override.articles) ? override.articles : [];
    const incomingById = new Map(incoming.map((article) => [article.id, article]));
    const existingIds = new Set((data.articles || []).map((article) => article.id));
    data.articles = (data.articles || []).map((article) => incomingById.get(article.id) || article);
    incoming.forEach((article) => {
      if (!existingIds.has(article.id)) data.articles.push(article);
    });

    data.sections = (data.sections || []).map((section) => ({ ...section, articleIds: [...(section.articleIds || [])] }));
    Object.entries(override.sectionOverrides || {}).forEach(([slug, config]) => {
      let section = data.sections.find((item) => item.slug === slug);
      if (!section) {
        section = { slug, title: config.title || slug, subtitle: config.subtitle || "", articleIds: [] };
        data.sections.push(section);
      }
      if (config.title) section.title = config.title;
      if (config.subtitle) section.subtitle = config.subtitle;
      if (Array.isArray(config.articleIds)) section.articleIds = dedupe(config.articleIds);
    });

    const financeIds = dedupe(override.moveToMarketEconomy || []);
    if (financeIds.length) {
      data.sections.forEach((section) => {
        if (section.slug !== "market-economy") {
          section.articleIds = (section.articleIds || []).filter((id) => !financeIds.includes(id));
        }
      });
      let market = data.sections.find((section) => section.slug === "market-economy");
      if (!market) {
        market = { slug: "market-economy", title: "📈 財經 / 全球市場", subtitle: "香港 · 日本 · 美國 · 全球", articleIds: [] };
        data.sections.push(market);
      }
      market.title = "📈 財經 / 全球市場";
      market.articleIds = dedupe([...(market.articleIds || []), ...financeIds]);
    }
    return data;
  }

  async function applyTopicExtras(data) {
    if (!data?.date) return data;
    const extras = await getJson(`data/topic-more/${data.date}.json`, true);
    if (!extras) return data;

    const incoming = Array.isArray(extras.articles) ? extras.articles : [];
    const incomingById = new Map(incoming.map((article) => [article.id, article]));
    const existing = new Set((data.articles || []).map((article) => article.id));
    data.articles = (data.articles || []).map((article) => incomingById.get(article.id) || article);
    incoming.forEach((article) => {
      if (!existing.has(article.id)) data.articles.push(article);
    });

    const extraSections = Array.isArray(extras.sections) ? extras.sections : [];
    extraSections.forEach((addition) => {
      let section = (data.sections || []).find((item) => item.slug === addition.slug);
      if (!section) {
        section = { slug: addition.slug, title: addition.title || addition.slug, subtitle: addition.subtitle || "", articleIds: [] };
        data.sections.push(section);
      }
      if (addition.title) section.title = addition.title;
      if (addition.subtitle) section.subtitle = addition.subtitle;
      section.articleIds = dedupe([...(section.articleIds || []), ...(addition.articleIds || [])]);
    });
    return data;
  }

  function sourceMarkup(article) {
    if (!article.sourceUrl) return "";
    return `<a class="source-link" href="${esc(article.sourceUrl)}" target="_blank" rel="noopener noreferrer">來源：${esc(article.sourceName || "原文")} ↗</a>`;
  }

  function renderArticle(article, featured = false) {
    return `
      <article class="topic-story ${featured ? "topic-feature" : ""}">
        <div class="tag">${esc(article.section || "NEWS")}</div>
        <h2>${esc(article.title)}</h2>
        ${article.dek ? `<p class="topic-dek">${esc(article.dek)}</p>` : ""}
        <p>${esc(article.summary || "")}</p>
        ${article.why ? `<p class="why-mini"><strong>為何重要：</strong> ${esc(article.why)}</p>` : ""}
        <div class="story-meta">${esc(article.timeLabel || "")} ${article.sourceName ? `· ${esc(article.sourceName)}` : ""}</div>
        ${sourceMarkup(article)}
      </article>
    `;
  }

  function renderTopic(data) {
    const host = $("#topic-sections");
    if (!host) return;
    const slugs = (document.body.dataset.topicSlugs || "").split(",").map((item) => item.trim()).filter(Boolean);
    const wanted = new Set(slugs);
    const sections = (data.sections || []).filter((section) => wanted.has(section.slug));

    $("#topic-date")?.replaceChildren(document.createTextNode(data.dateLabel || data.date || ""));
    const editionCount = sections.reduce((sum, section) => sum + (section.articleIds || []).length, 0);
    const count = $("#topic-count");
    if (count) count.textContent = `${editionCount} stories`;

    host.innerHTML = sections.map((section) => {
      const stories = (section.articleIds || []).map((id) => articleById(data, id)).filter(Boolean);
      if (!stories.length) return "";
      return `
        <section class="topic-section" id="${esc(section.slug)}">
          <div class="section-heading">
            <h2>${esc(section.title)}</h2>
            <span>${esc(section.subtitle || `${stories.length} 則`)}</span>
          </div>
          <div class="topic-story-grid">
            ${stories.map((article, index) => renderArticle(article, index === 0)).join("")}
          </div>
        </section>
      `;
    }).join("") || `<p class="notice">今日暫未有足夠具獨立閱讀價值的新聞放入本版。</p>`;
  }

  async function init() {
    try {
      let data = await getJson("data/latest.json");
      data = await applyEditorialOverride(data);
      data = await applyTopicExtras(data);
      renderTopic(data);
    } catch (error) {
      console.error(error);
      const host = $("#topic-sections");
      if (host) host.innerHTML = `<p class="notice">本版暫時未能載入。請返回頭版或稍後重試。</p>`;
    }
  }

  init();
})();
