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
    ["hong-kong", "香港", "社會 · 法庭 · 公共政策 · 民生 · 文化"],
    ["japan", "日本", "社會 · 法庭 · 政策 · 交通 · 教育 · 醫療 · 生活"],
    ["market-economy", "📈 財經 / 全球市場", "美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球"],
    ["ai-tech", "AI / 科技", "AI · 半導體 · 軟件 · 網安 · 消費科技"],
    ["science-new-tech", "🧪 科學 / 新技術", "科研 · 新技術"],
    ["cybersecurity", "🔐 網絡安全", "Cybersecurity"],
    ["software-apps", "📱 軟件 / App / 消費科技", "Software · Apps"],
    ["manga-anime", "漫畫 / Anime", "作品 · 產業 · 票房 · 聲優 · 出版"],
    ["manchester-united", "Manchester United", "Club · Squad · Transfers"],
    ["football", "Football", "Europe · J-League · Hong Kong · Worldwide"],
    ["breaking-news", "📰 突發新聞", "Breaking"],
    ["worth-following", "🔎 今日值得跟進", "Follow-up"],
    ["upcoming-events", "📅 Upcoming events / 明日焦點", "Upcoming"]
  ];
  const SECTION_META = new Map(SECTION_DEFS.map(([slug, title, subtitle]) => [slug, { slug, title, subtitle }]));

  function oneSlug(value = "") {
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

  function sectionSlugs(value = "", explicit = []) {
    const result = [];
    (Array.isArray(explicit) ? explicit : []).forEach((slug) => {
      const normalized = oneSlug(slug);
      if (normalized !== "worth-following") result.push(normalized);
    });
    const raw = String(value || "");
    const lower = raw.toLowerCase();
    const add = (slug, hit) => { if (hit) result.push(slug); };
    add("world", raw.includes("世界") || lower.includes("world"));
    add("asia", raw.includes("亞洲") || lower.includes("asia"));
    add("hong-kong", raw.includes("香港") || lower.includes("hong kong"));
    add("japan", raw.includes("日本") || lower.includes("japan"));
    add("market-economy", raw.includes("財經") || raw.includes("市場") || lower.includes("finance"));
    add("ai-tech", raw.includes("AI") || raw.includes("科技") || lower.includes("tech"));
    add("science-new-tech", raw.includes("科學"));
    add("cybersecurity", raw.includes("網絡安全") || raw.includes("網路安全") || lower.includes("cyber"));
    add("software-apps", raw.includes("軟件") || raw.includes("App") || lower.includes("software"));
    add("manga-anime", raw.includes("漫畫") || raw.includes("Anime") || lower.includes("anime"));
    add("manchester-united", raw.includes("Manchester United") || lower.includes("manchester united"));
    add("football", raw.includes("Football") || raw.includes("足球") || lower.includes("football"));
    if (!result.length) result.push(oneSlug(raw));
    return dedupe(result);
  }

  function ensureSection(data, slug) {
    let section = data.sections.find((item) => item.slug === slug);
    if (!section) {
      section = { ...(SECTION_META.get(slug) || { slug, title: slug, subtitle: "" }), articleIds: [] };
      data.sections.push(section);
    }
    return section;
  }

  function ensureSections(data) {
    data = data || {};
    data.articles = Array.isArray(data.articles) ? data.articles : [];
    const valid = Array.isArray(data.sections) && data.sections.every((section) => section && typeof section === "object" && !Array.isArray(section));
    if (valid && data.sections.length) {
      data.sections = data.sections.map((section) => ({ ...section, articleIds: dedupe(section.articleIds || []) }));
      return data;
    }
    const grouped = new Map();
    data.articles.forEach((article) => {
      if (!article?.id) return;
      const slug = oneSlug(article.section);
      if (!grouped.has(slug)) grouped.set(slug, []);
      grouped.get(slug).push(article.id);
    });
    data.sections = SECTION_DEFS.filter(([slug]) => grouped.has(slug)).map(([slug, title, subtitle]) => ({ slug, title, subtitle, articleIds: dedupe(grouped.get(slug)) }));
    return data;
  }

  function mergeArticle(data, article, slugs = [], prepend = true) {
    if (!article?.id) return;
    const index = data.articles.findIndex((item) => item.id === article.id);
    if (index >= 0) data.articles[index] = { ...data.articles[index], ...article };
    else data.articles.push(article);
    slugs.forEach((slug) => {
      if (!SECTION_META.has(slug)) return;
      const section = ensureSection(data, slug);
      section.articleIds = prepend ? dedupe([article.id, ...(section.articleIds || [])]) : dedupe([...(section.articleIds || []), article.id]);
    });
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
    (Array.isArray(override.articles) ? override.articles : []).forEach((article) => mergeArticle(data, article, sectionSlugs(article.section), false));
    Object.entries(override.sectionOverrides || {}).forEach(([slug, config]) => {
      const section = ensureSection(data, slug);
      if (config.title) section.title = config.title;
      if (config.subtitle) section.subtitle = config.subtitle;
      if (Array.isArray(config.articleIds)) section.articleIds = dedupe(config.articleIds);
    });
    const financeIds = dedupe(override.moveToMarketEconomy || []);
    if (financeIds.length) {
      data.sections.forEach((section) => {
        if (section.slug !== "market-economy") section.articleIds = (section.articleIds || []).filter((id) => !financeIds.includes(id));
      });
      ensureSection(data, "market-economy").articleIds = dedupe([...(ensureSection(data, "market-economy").articleIds || []), ...financeIds]);
    }
    return data;
  }

  async function applyTopicExtras(data) {
    if (!data?.date) return data;
    const extras = await getJson(`data/topic-more/${data.date}.json`, true);
    if (!extras) return data;
    (Array.isArray(extras.articles) ? extras.articles : []).forEach((article) => mergeArticle(data, article, sectionSlugs(article.section), false));
    (Array.isArray(extras.sections) ? extras.sections : []).forEach((entry) => {
      if (typeof entry === "string") return;
      if (!entry || typeof entry !== "object") return;
      const slug = oneSlug(entry.slug || entry.section || entry.title);
      const section = ensureSection(data, slug);
      if (entry.title) section.title = entry.title;
      if (entry.subtitle) section.subtitle = entry.subtitle;
      section.articleIds = dedupe([...(section.articleIds || []), ...(entry.articleIds || [])]);
    });
    return data;
  }

  function normalizeRollingStory(story, fallbackStatus = "LATEST") {
    return {
      ...story,
      section: story.section || "Rolling Desk",
      dek: story.dek || story.lede || "",
      context: story.context || story.background || "",
      why: story.why || story.whyImportant || "",
      watchNext: story.watchNext || story.nextStep || "",
      status: story.status || fallbackStatus,
      isRolling: true
    };
  }

  async function applyDeskLatest(data) {
    const deskLatest = await getJson("data/desk-latest.json", true);
    if (!deskLatest) return data;
    const desks = deskLatest.desks && typeof deskLatest.desks === "object" ? deskLatest.desks : {};
    Object.entries(desks).forEach(([slug, stories]) => {
      (Array.isArray(stories) ? stories : []).slice().reverse().forEach((story) => {
        const article = normalizeRollingStory(story, "LATEST");
        mergeArticle(data, article, sectionSlugs(article.section, article.deskSlugs || [slug]), true);
      });
    });
    return data;
  }

  async function applyLive(data) {
    const live = await getJson("data/live.json", true);
    if (!live) return data;
    (Array.isArray(live.items) ? live.items : []).slice().reverse().forEach((item) => {
      const article = normalizeRollingStory(item, item.status || "UPDATED");
      article.isLive = true;
      mergeArticle(data, article, sectionSlugs(article.section, article.deskSlugs), true);
    });
    return data;
  }

  function sourceMarkup(article) {
    const sources = Array.isArray(article.sources) && article.sources.length
      ? article.sources
      : (article.sourceUrl ? [{ name: article.sourceName || "原文", url: article.sourceUrl }] : []);
    if (!sources.length) return "";
    return `<div class="topic-sources"><strong>核實來源：</strong> ${sources.map((source) => `<a class="source-link" href="${esc(source.url || "#")}" target="_blank" rel="noopener noreferrer">${esc(source.name || "原文")} ↗</a>`).join(" · ")}</div>`;
  }

  function detail(label, value, cls) {
    if (!value) return "";
    return `<p class="${cls}"><strong>${label}</strong>${esc(value)}</p>`;
  }

  function renderArticle(article, featured = false) {
    const badge = article.isLive
      ? `<span class="topic-live-badge">${esc(article.status || "LIVE")}</span>`
      : (article.isRolling ? `<span class="topic-latest-badge">${esc(article.status || "LATEST")}</span>` : "");
    return `<article class="topic-story ${featured ? "topic-feature" : ""} ${article.isLive ? "topic-live-story" : ""}">
      <div class="tag">${badge}${esc(article.section || "NEWS")}</div>
      <h2>${esc(article.title || "")}</h2>
      ${article.dek ? `<p class="topic-dek">${esc(article.dek)}</p>` : ""}
      <div class="topic-article-body">
        ${detail("最新：", article.summary, "topic-summary")}
        ${detail("背景：", article.context || article.background, "topic-context")}
        ${detail("為何重要：", article.why || article.whyImportant, "why-mini")}
        ${detail("下一步：", article.watchNext || article.nextStep, "topic-next")}
      </div>
      <div class="story-meta">${esc(article.timeLabel || "")} ${article.sourceName ? `· ${esc(article.sourceName)}` : ""}</div>
      ${sourceMarkup(article)}
    </article>`;
  }

  function renderTopic(data) {
    const host = $("#topic-sections");
    if (!host) return;
    const slugs = (document.body.dataset.topicSlugs || "").split(",").map((item) => item.trim()).filter(Boolean);
    const wanted = new Set(slugs);
    const sections = (data.sections || []).filter((section) => wanted.has(section.slug));

    $("#topic-date")?.replaceChildren(document.createTextNode(data.dateLabel || data.date || ""));
    const editionCount = sections.reduce((sum, section) => sum + dedupe(section.articleIds || []).filter((id) => articleById(data, id)).length, 0);
    const count = $("#topic-count");
    if (count) count.textContent = `${editionCount} stories · Daily + Rolling Desk + Live`;

    host.innerHTML = sections.map((section) => {
      const stories = dedupe(section.articleIds || []).map((id) => articleById(data, id)).filter(Boolean);
      if (!stories.length) return "";
      return `<section class="topic-section" id="${esc(section.slug)}"><div class="section-heading"><h2>${esc(section.title)}</h2><span>${esc(section.subtitle || `${stories.length} 則`)}</span></div><div class="topic-story-grid">${stories.map((article, index) => renderArticle(article, index === 0)).join("")}</div></section>`;
    }).join("") || `<p class="notice">本版目前未有可核實內容；這會被視為 Desk coverage gap，而不是「沒有新聞」。</p>`;
  }

  async function init() {
    try {
      let data = ensureSections(await getJson("data/latest.json"));
      data = await applyEditorialOverride(data);
      data = await applyTopicExtras(data);
      data = await applyDeskLatest(data);
      data = await applyLive(data);
      renderTopic(data);
    } catch (error) {
      console.error(error);
      const host = $("#topic-sections");
      if (host) host.innerHTML = `<p class="notice">本版暫時未能載入。請返回頭版或稍後重試。</p>`;
    }
  }

  init();
})();
