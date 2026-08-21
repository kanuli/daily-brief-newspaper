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

  const SECTION_DEFS = [
    ["world", "世界", "歐洲 · 中東 · 美洲 · 非洲 · 大洋洲"],
    ["asia", "亞洲", "中國 · 台灣 · 韓國 · 東南亞 · 南亞"],
    ["hong-kong", "香港", "本地 · 社會 · 公共政策 · 民生"],
    ["japan", "日本", "社會 · 政策 · 交通 · 生活"],
    ["market-economy", "📈 財經 / 全球市場", "美國 · 歐洲 · 台灣 · 日本 · 香港 · 全球"],
    ["ai-tech", "AI / 科技", "AI · 半導體 · 軟件 · 科技"],
    ["science-new-tech", "🧪 科學 / 新技術", "科研 · 新技術"],
    ["cybersecurity", "🔐 網絡安全", "Cybersecurity"],
    ["software-apps", "📱 軟件 / App / 消費科技", "Software · Apps"],
    ["manga-anime", "漫畫 / Anime", "作品 · 產業 · 票房 · 聲優"],
    ["manchester-united", "Manchester United", "Club · Squad · Transfers"],
    ["football", "Football", "Worldwide football"],
    ["breaking-news", "📰 突發新聞", "Breaking"],
    ["worth-following", "🔎 今日值得跟進", "Follow-up"],
    ["upcoming-events", "📅 Upcoming events / 明日焦點", "Upcoming"]
  ];
  const SECTION_META = new Map(SECTION_DEFS.map(([slug, title, subtitle]) => [slug, { slug, title, subtitle }]));

  function sectionSlug(value = "") {
    const raw = String(value).trim();
    const lower = raw.toLowerCase();
    if (!raw) return "worth-following";
    if (raw.startsWith("世界") || lower === "world") return "world";
    if (raw.startsWith("亞洲") || lower === "asia") return "asia";
    if (raw.startsWith("香港") || lower === "hong-kong") return "hong-kong";
    if (raw.startsWith("日本") || lower === "japan") return "japan";
    if (raw.startsWith("📈") || raw.startsWith("財經") || lower === "market-economy") return "market-economy";
    if (raw.startsWith("AI / 科技") || raw.startsWith("AI／科技") || lower === "ai-tech") return "ai-tech";
    if (raw.startsWith("科學") || lower === "science-new-tech") return "science-new-tech";
    if (raw.startsWith("網絡安全") || raw.startsWith("網路安全") || lower === "cybersecurity") return "cybersecurity";
    if (raw.startsWith("軟件") || raw.startsWith("App") || lower === "software-apps") return "software-apps";
    if (raw.startsWith("漫畫") || raw.startsWith("Anime") || lower === "manga-anime") return "manga-anime";
    if (raw.startsWith("Manchester United") || lower === "manchester-united") return "manchester-united";
    if (raw.startsWith("Football") || lower === "football") return "football";
    if (lower === "breaking-news") return "breaking-news";
    if (lower === "upcoming-events") return "upcoming-events";
    return "worth-following";
  }

  function ensureSections(data) {
    data = data || {};
    data.articles = Array.isArray(data.articles) ? data.articles : [];
    const valid = Array.isArray(data.sections) && data.sections.length > 0 && data.sections.every((section) => section && typeof section === "object" && !Array.isArray(section));
    if (valid) {
      data.sections = data.sections.map((section) => ({ ...section, articleIds: dedupe(section.articleIds || []) }));
      return data;
    }
    const grouped = new Map();
    data.articles.forEach((article) => {
      if (!article?.id) return;
      const slug = sectionSlug(article.section);
      if (!grouped.has(slug)) grouped.set(slug, []);
      grouped.get(slug).push(article.id);
    });
    data.sections = SECTION_DEFS.filter(([slug]) => grouped.has(slug)).map(([slug, title, subtitle]) => ({ slug, title, subtitle, articleIds: dedupe(grouped.get(slug)) }));
    return data;
  }

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
    data = ensureSections(data);
    if (!data?.date) return data;
    const override = await getJson(`data/editorial-overrides/${data.date}.json`, true);
    if (!override) return data;

    const incoming = Array.isArray(override.articles) ? override.articles : [];
    const incomingById = new Map(incoming.map((article) => [article.id, article]));
    const existingIds = new Set((data.articles || []).map((article) => article.id));
    data.articles = (data.articles || []).map((article) => incomingById.get(article.id) || article);
    incoming.forEach((article) => { if (!existingIds.has(article.id)) data.articles.push(article); });

    Object.entries(override.sectionOverrides || {}).forEach(([slug, config]) => {
      let section = data.sections.find((item) => item.slug === slug);
      if (!section) {
        section = { ...(SECTION_META.get(slug) || { slug, title: slug, subtitle: "" }), articleIds: [] };
        data.sections.push(section);
      }
      if (config.title) section.title = config.title;
      if (config.subtitle) section.subtitle = config.subtitle;
      if (Array.isArray(config.articleIds)) section.articleIds = dedupe(config.articleIds);
    });

    const financeIds = dedupe(override.moveToMarketEconomy || []);
    if (financeIds.length) {
      data.sections.forEach((section) => {
        if (section.slug !== "market-economy") section.articleIds = (section.articleIds || []).filter((id) => !financeIds.includes(id));
      });
      let market = data.sections.find((section) => section.slug === "market-economy");
      if (!market) {
        market = { ...SECTION_META.get("market-economy"), articleIds: [] };
        data.sections.push(market);
      }
      market.articleIds = dedupe([...(market.articleIds || []), ...financeIds]);
    }
    return ensureSections(data);
  }

  function normalizeExtraSections(extras, incoming) {
    const bySlug = new Map();
    incoming.forEach((article) => {
      const slug = sectionSlug(article.section);
      if (!bySlug.has(slug)) bySlug.set(slug, []);
      if (article.id) bySlug.get(slug).push(article.id);
    });

    const raw = Array.isArray(extras.sections) ? extras.sections : [];
    const normalized = [];
    raw.forEach((entry) => {
      if (typeof entry === "string") {
        const slug = sectionSlug(entry);
        const meta = SECTION_META.get(slug) || { slug, title: slug, subtitle: "" };
        normalized.push({ ...meta, articleIds: dedupe(bySlug.get(slug) || []) });
        return;
      }
      if (entry && typeof entry === "object") {
        const slug = sectionSlug(entry.slug || entry.section || entry.title);
        const meta = SECTION_META.get(slug) || { slug, title: entry.title || slug, subtitle: entry.subtitle || "" };
        normalized.push({
          ...meta,
          ...entry,
          slug,
          articleIds: dedupe([...(entry.articleIds || []), ...(bySlug.get(slug) || [])])
        });
      }
    });

    bySlug.forEach((articleIds, slug) => {
      if (!normalized.some((section) => section.slug === slug)) {
        const meta = SECTION_META.get(slug) || { slug, title: slug, subtitle: "" };
        normalized.push({ ...meta, articleIds: dedupe(articleIds) });
      }
    });
    return normalized;
  }

  async function applyTopicExtras(data) {
    data = ensureSections(data);
    if (!data?.date) return data;
    const extras = await getJson(`data/topic-more/${data.date}.json`, true);
    if (!extras) return data;

    const incoming = Array.isArray(extras.articles) ? extras.articles : [];
    const incomingById = new Map(incoming.map((article) => [article.id, article]));
    const existing = new Set((data.articles || []).map((article) => article.id));
    data.articles = (data.articles || []).map((article) => incomingById.get(article.id) || article);
    incoming.forEach((article) => { if (!existing.has(article.id)) data.articles.push(article); });

    normalizeExtraSections(extras, incoming).forEach((addition) => {
      let section = data.sections.find((item) => item.slug === addition.slug);
      if (!section) {
        section = { ...addition, articleIds: [] };
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
    return `<article class="topic-story ${featured ? "topic-feature" : ""}"><div class="tag">${esc(article.section || "NEWS")}</div><h2>${esc(article.title)}</h2>${article.dek ? `<p class="topic-dek">${esc(article.dek)}</p>` : ""}<p>${esc(article.summary || "")}</p>${article.why ? `<p class="why-mini"><strong>為何重要：</strong> ${esc(article.why)}</p>` : ""}<div class="story-meta">${esc(article.timeLabel || "")} ${article.sourceName ? `· ${esc(article.sourceName)}` : ""}</div>${sourceMarkup(article)}</article>`;
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
      return `<section class="topic-section" id="${esc(section.slug)}"><div class="section-heading"><h2>${esc(section.title)}</h2><span>${esc(section.subtitle || `${stories.length} 則`)}</span></div><div class="topic-story-grid">${stories.map((article, index) => renderArticle(article, index === 0)).join("")}</div></section>`;
    }).join("") || `<p class="notice">今日暫未有足夠具獨立閱讀價值的新聞放入本版。</p>`;
  }

  async function init() {
    try {
      let data = ensureSections(await getJson("data/latest.json"));
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
